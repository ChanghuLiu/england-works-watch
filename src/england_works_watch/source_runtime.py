from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
import threading
import time
from typing import Any, Callable
import urllib.request

from .policy import DATA, SOURCES, source_status as static_source_status
from .source_evidence import missing_expected_markers, semantic_sha256

STATE_SCHEMA_VERSION = "1.0"
_RUNTIME_LOCK = threading.RLock()
_MONITOR_STARTED = False


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def runtime_dir() -> Path:
    path = Path(os.getenv("EWW_RUNTIME_DIR", "/data" if Path("/data").exists() else "runtime"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def state_path() -> Path:
    return runtime_dir() / "source_state.json"


def baseline_path() -> Path:
    return Path(os.getenv("EWW_SOURCE_BASELINE_PATH", str(DATA / "source_audit_baseline.json")))


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"invalid JSON object: {path}")
    return value


def _registry_by_id() -> dict[str, dict[str, Any]]:
    return {item["source_id"]: item for item in SOURCES["sources"]}


def _seed_from_baseline(now: datetime | None = None) -> dict[str, Any]:
    now = now or _utc_now()
    baseline = _load_json(baseline_path())
    registry = _registry_by_id()
    observed = {item.get("source_id"): item for item in baseline.get("sources", []) if isinstance(item, dict)}
    expected = set(registry)
    if set(observed) != expected:
        missing = sorted(expected - set(observed))
        extra = sorted(set(observed) - expected)
        raise RuntimeError(f"source audit baseline mismatch: missing={missing}, extra={extra}")
    if int(baseline.get("blocking_count", 1)) != 0:
        raise RuntimeError("cannot seed runtime from a blocking source audit baseline")

    sources: dict[str, Any] = {}
    for source_id, meta in registry.items():
        item = observed[source_id]
        semantic = item.get("semantic_sha256")
        if not isinstance(semantic, str) or len(semantic) != 64:
            raise RuntimeError(f"baseline missing semantic fingerprint for {source_id}")
        generated_at = baseline.get("generated_at") or _iso(now)
        sources[source_id] = {
            "source_id": source_id,
            "source_version": meta["version"],
            "valid_from": meta["valid_from"],
            "official_url": meta["url"],
            "baseline_semantic_sha256": semantic,
            "last_semantic_sha256": semantic,
            "last_checked_at": generated_at,
            "last_success_at": generated_at,
            "last_http_status": item.get("http_status", 200),
            "last_fetch_status": "BASELINE_REVIEWED",
            "review_required": False,
            "changed_at": None,
            "missing_markers": [],
            "error": None,
        }
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "registry_version": baseline.get("registry_version") or SOURCES.get("registry_version"),
        "seeded_from": str(baseline_path()),
        "seeded_at": _iso(now),
        "updated_at": _iso(now),
        "sources": sources,
    }


def ensure_runtime_seeded(now: datetime | None = None) -> dict[str, Any]:
    with _RUNTIME_LOCK:
        path = state_path()
        if path.exists():
            state = _load_json(path)
            if state.get("schema_version") != STATE_SCHEMA_VERSION:
                raise RuntimeError("unsupported England Works Watch source-state schema")
            return state
        state = _seed_from_baseline(now)
        _atomic_write(path, state)
        return state


def load_state() -> dict[str, Any]:
    with _RUNTIME_LOCK:
        return ensure_runtime_seeded()


def fetch_official_source(source: dict[str, Any]) -> dict[str, Any]:
    req = urllib.request.Request(
        source["url"],
        headers={"User-Agent": "EnglandWorksWatch-runtime-source-monitor/0.1"},
    )
    with urllib.request.urlopen(req, timeout=float(os.getenv("EWW_SOURCE_FETCH_TIMEOUT_SECONDS", "20"))) as response:
        raw = response.read(2_000_000)
        status = int(getattr(response, "status", 200))
    html = raw.decode("utf-8", "replace")
    return {
        "http_status": status,
        "semantic_sha256": semantic_sha256(html),
        "missing_markers": missing_expected_markers(html, source.get("expected_markers", [])),
    }


def apply_observation(
    state: dict[str, Any],
    source: dict[str, Any],
    observation: dict[str, Any] | None,
    *,
    error: Exception | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Apply one observation without ever promoting a changed hash to baseline."""
    now = now or _utc_now()
    source_id = source["source_id"]
    item = state["sources"][source_id]
    item["last_checked_at"] = _iso(now)

    if error is not None:
        item["last_fetch_status"] = "FETCH_ERROR"
        item["error"] = type(error).__name__
        return state

    observation = observation or {}
    semantic = observation.get("semantic_sha256")
    markers = list(observation.get("missing_markers") or [])
    http_status = observation.get("http_status")
    item["last_http_status"] = http_status
    item["missing_markers"] = markers
    item["error"] = None

    if not isinstance(semantic, str) or len(semantic) != 64:
        item["last_fetch_status"] = "INVALID_OBSERVATION"
        item["review_required"] = True
        item["changed_at"] = item.get("changed_at") or _iso(now)
        return state

    item["last_semantic_sha256"] = semantic
    item["last_success_at"] = _iso(now)
    if markers:
        item["last_fetch_status"] = "MARKER_MISSING"
        item["review_required"] = True
        item["changed_at"] = item.get("changed_at") or _iso(now)
    elif semantic != item["baseline_semantic_sha256"]:
        item["last_fetch_status"] = "CHANGED_PENDING_REVIEW"
        item["review_required"] = True
        item["changed_at"] = item.get("changed_at") or _iso(now)
    else:
        item["last_fetch_status"] = "UNCHANGED"
        # Never auto-clear a prior review item. A changed source must be reviewed
        # explicitly even if the remote page later happens to revert.
    return state


def observe_all(
    fetcher: Callable[[dict[str, Any]], dict[str, Any]] = fetch_official_source,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or _utc_now()
    registry = _registry_by_id()
    with _RUNTIME_LOCK:
        state = ensure_runtime_seeded(now)
        for source_id, source in registry.items():
            try:
                observation = fetcher(source)
                apply_observation(state, source, observation, now=now)
            except Exception as exc:
                apply_observation(state, source, None, error=exc, now=now)
        state["updated_at"] = _iso(now)
        _atomic_write(state_path(), state)
        return state


def production_source_status(*, now: datetime | None = None) -> dict[str, Any]:
    now = now or _utc_now()
    static = static_source_status(now.date().isoformat())
    state = ensure_runtime_seeded(now)
    max_age_hours = float(os.getenv("EWW_SOURCE_MAX_AGE_HOURS", "24"))
    runtime_sources = []
    blocking: list[str] = list(static.get("blocking_sources") or [])
    review_required: list[str] = []
    stale: list[str] = []
    counts: Counter[str] = Counter()

    for source in SOURCES["sources"]:
        source_id = source["source_id"]
        item = dict(state["sources"].get(source_id) or {})
        last_success = _parse(item.get("last_success_at"))
        age_hours = None if last_success is None else max(0.0, (now - last_success).total_seconds() / 3600)
        is_stale = age_hours is None or age_hours > max_age_hours
        needs_review = bool(item.get("review_required"))
        fetch_status = str(item.get("last_fetch_status") or "NO_STATE")
        counts[fetch_status] += 1
        if needs_review:
            review_required.append(source_id)
            blocking.append(source_id)
        if is_stale:
            stale.append(source_id)
            blocking.append(source_id)
        runtime_sources.append(
            {
                **item,
                "age_hours": None if age_hours is None else round(age_hours, 3),
                "stale": is_stale,
                "blocking": needs_review or is_stale or source_id in static.get("blocking_sources", []),
            }
        )

    blocking = sorted(set(blocking))
    baseline_count = sum(1 for item in runtime_sources if item.get("baseline_semantic_sha256"))
    return {
        "product": "England Works Watch",
        "scope": static["scope"],
        "rule_pack_version": static["rule_pack_version"],
        "registry_version": SOURCES.get("registry_version"),
        "total_sources": len(runtime_sources),
        "decision_bearing_sources": len(runtime_sources),
        "sources_with_fingerprint_baseline": baseline_count,
        "decision_sources_with_fingerprint_baseline": baseline_count,
        "coverage_complete": not blocking,
        "blocking_sources": blocking,
        "review_required_sources": sorted(set(review_required)),
        "stale_sources": sorted(set(stale)),
        "fetch_status_counts": dict(sorted(counts.items())),
        "max_age_hours": max_age_hours,
        "runtime_state_path": str(state_path()),
        "runtime_updated_at": state.get("updated_at"),
        "sources": runtime_sources,
    }


def start_background_source_monitor() -> bool:
    global _MONITOR_STARTED
    enabled = os.getenv("EWW_SOURCE_MONITOR_ENABLED", "1").strip().lower() not in {"0", "false", "no", "off"}
    if not enabled:
        return False
    with _RUNTIME_LOCK:
        if _MONITOR_STARTED:
            return False
        _MONITOR_STARTED = True

    interval = max(300.0, float(os.getenv("EWW_SOURCE_CHECK_INTERVAL_SECONDS", "21600")))

    def loop() -> None:
        # Observe immediately after process startup, then on the configured cadence.
        while True:
            try:
                observe_all()
            except Exception as exc:
                print(f"EWW_SOURCE_MONITOR_ERROR {type(exc).__name__}: {exc}", flush=True)
            time.sleep(interval)

    thread = threading.Thread(target=loop, name="eww-source-monitor", daemon=True)
    thread.start()
    return True
