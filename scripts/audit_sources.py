from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import urllib.request

from england_works_watch.source_evidence import missing_expected_markers, normalized_guidance_text, semantic_sha256

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = json.loads((ROOT / "data/source_registry.json").read_text())
results = []
failed = 0

for src in REGISTRY["sources"]:
    try:
        req = urllib.request.Request(
            src["url"], headers={"User-Agent": "EnglandWorksWatch-source-audit/0.2"}
        )
        with urllib.request.urlopen(req, timeout=20) as response:
            raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                raise ValueError("Official source exceeds download size limit")
            http_status = int(getattr(response, "status", 200))
        body = raw.decode("utf-8", "replace")
        missing = missing_expected_markers(body, src.get("expected_markers", []))
        semantic_text = normalized_guidance_text(body)
        semantic = semantic_sha256(body)
        reviewed_match = semantic == src.get("reviewed_semantic_sha256")
        state = "UNCHANGED" if not missing and semantic_text and reviewed_match and http_status == 200 else "REVIEW_REQUIRED"
        failed += int(state != "UNCHANGED")
        results.append(
            {
                "source_id": src["source_id"],
                "state": state,
                "http_status": http_status,
                "http_bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "semantic_sha256": semantic,
                "reviewed_fingerprint_matches": reviewed_match,
                "semantic_chars": len(semantic_text),
                "missing_markers": missing,
                "source_version": src["version"],
                "valid_from": src["valid_from"],
            }
        )
    except Exception as exc:
        failed += 1
        results.append(
            {
                "source_id": src["source_id"],
                "state": "FETCH_FAILED",
                "error": type(exc).__name__,
            }
        )

report = {
    "schema_version": "1.0",
    "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    "registry_version": REGISTRY["registry_version"],
    "sources": results,
    "blocking_count": failed,
}
# This file is intentionally created during the Docker build after a successful
# live official-source audit against the committed reviewed fingerprints. It becomes the immutable seed for the
# production persistent runtime monitor.
(ROOT / "data/source_audit_baseline.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
raise SystemExit(1 if failed else 0)

