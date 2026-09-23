"""Thin, fail-closed adapter to the shared human/business commercial service."""
from __future__ import annotations

from dataclasses import dataclass, replace
import json
import os
import secrets
import threading
import time
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4

import httpx

from .attribution import normalize_source_bucket


class CommercialPlatformError(RuntimeError):
    """The shared commercial platform could not satisfy its public contract."""


def commercial_source_channel(value: str) -> str:
    normalized = normalize_source_bucket(value)
    directory_sources = {
        "official_registry", "glama", "docker", "tensorblock", "mcpso",
        "mcpservers_org", "mcpmux", "punkpeye_remote", "mcpindex",
        "mcpbeat", "agent402", "402explorer", "wellknown", "mcpmetrics",
        "smithery", "mcp_directory", "safemcp", "unyly", "truespar",
        "agentshare", "sentineloracle", "proofbench", "mcpcheckup",
        "golemreach", "mcpscan", "agentstatus",
    }
    if normalized in directory_sources:
        return "directory"
    if normalized in {"linkedin", "openai", "claude", "grok", "regevidencehub", "organic", "directory", "direct", "unknown"}:
        return normalized
    return "direct"


def _required_url(name: str, value: str) -> str:
    parts = urlsplit(value)
    if parts.scheme not in {"http", "https"} or not parts.netloc or parts.username or parts.password:
        raise ValueError(f"{name} must be an absolute http(s) URL without credentials")
    return value.rstrip("/") if parts.path in {"", "/"} and not parts.query and not parts.fragment else value


def _with_query(url: str, **values: str) -> str:
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query.update(values)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


@dataclass(frozen=True)
class CommercialSettings:
    platform_url: str = "http://127.0.0.1:8000"
    product_id: str = "england_works_watch"
    human_origin: str = "http://127.0.0.1:8000"
    success_url: str | None = None
    cancel_url: str | None = None
    timeout_seconds: float = 5.0
    pending_ttl_seconds: int = 86400

    @classmethod
    def from_env(cls) -> "CommercialSettings":
        platform_url = _required_url("EWW_COMMERCIAL_PLATFORM_URL", os.getenv("EWW_COMMERCIAL_PLATFORM_URL", cls.platform_url).strip())
        human_origin = _required_url("EWW_HUMAN_ORIGIN", os.getenv("EWW_HUMAN_ORIGIN", cls.human_origin).strip())
        success_url = os.getenv("EWW_COMMERCIAL_SUCCESS_URL", "").strip() or f"{human_origin}/monitoring-report/checkout-success"
        cancel_url = os.getenv("EWW_COMMERCIAL_CANCEL_URL", "").strip() or f"{human_origin}/monitoring-report/checkout-cancelled"
        success_url = _required_url("EWW_COMMERCIAL_SUCCESS_URL", success_url)
        cancel_url = _required_url("EWW_COMMERCIAL_CANCEL_URL", cancel_url)
        try:
            timeout = float(os.getenv("EWW_COMMERCIAL_TIMEOUT_SECONDS", "5"))
            pending_ttl = int(os.getenv("EWW_COMMERCIAL_PENDING_TTL_SECONDS", "86400"))
        except ValueError as exc:
            raise ValueError("commercial timeout/TTL settings are invalid") from exc
        if not 0.1 <= timeout <= 30:
            raise ValueError("EWW_COMMERCIAL_TIMEOUT_SECONDS must be between 0.1 and 30")
        if not 60 <= pending_ttl <= 86400:
            raise ValueError("EWW_COMMERCIAL_PENDING_TTL_SECONDS must be between 60 and 86400")
        product_id = os.getenv("EWW_COMMERCIAL_PRODUCT_ID", cls.product_id).strip()
        if not product_id or len(product_id) > 64:
            raise ValueError("EWW_COMMERCIAL_PRODUCT_ID must be 1-64 characters")
        return cls(platform_url, product_id, human_origin, success_url, cancel_url, timeout, pending_ttl)

    def checkout_success_url(self, return_token: str) -> str:
        return _with_query(str(self.success_url), return_token=return_token)


@dataclass(frozen=True)
class PendingMonitoringCheckout:
    return_token: str
    principal_ref: str
    checkpoint: dict[str, Any]
    source_channel: str
    classification: str
    owner_test: bool
    checkout_id: str | None
    expires_at: float
    paid_access_activated: bool = False


class PendingMonitoringCheckoutStore:
    """Short-lived opaque checkout state with optional restart persistence."""

    def __init__(
        self,
        ttl_seconds: int = 1800,
        *,
        path: str | Path | None = None,
    ) -> None:
        self.ttl_seconds = ttl_seconds
        self.path = Path(path).expanduser() if path else None
        self._rows: dict[str, PendingMonitoringCheckout] = {}
        self._lock = threading.RLock()
        self._load()

    @staticmethod
    def _bounded_checkpoint(checkpoint: Mapping[str, Any]) -> dict[str, Any]:
        """Keep only the opaque source checkpoint contract in local state."""
        if not isinstance(checkpoint, dict):
            raise ValueError("checkpoint must be an object")
        if set(checkpoint) != {"schema_version", "created_at", "sources"}:
            raise ValueError("checkpoint contains unsupported fields")
        if checkpoint.get("schema_version") != "c5-monitoring-v1":
            raise ValueError("checkpoint has an unsupported schema version")
        created_at = checkpoint.get("created_at")
        sources = checkpoint.get("sources")
        if not isinstance(created_at, str) or not created_at or len(created_at) > 80:
            raise ValueError("checkpoint created_at is invalid")
        if not isinstance(sources, list) or not 1 <= len(sources) <= 4:
            raise ValueError("checkpoint sources are invalid")

        bounded_sources: list[dict[str, Any]] = []
        for source in sources:
            if not isinstance(source, dict):
                raise ValueError("checkpoint source row is invalid")
            if set(source) != {"source_id", "source_version", "semantic_sha256", "observed_at"}:
                raise ValueError("checkpoint source row contains unsupported fields")
            source_id = source.get("source_id")
            source_version = source.get("source_version")
            semantic_sha256 = source.get("semantic_sha256")
            observed_at = source.get("observed_at")
            if (
                not isinstance(source_id, str) or not source_id or len(source_id) > 80
                or not isinstance(source_version, str) or not source_version or len(source_version) > 160
                or not isinstance(semantic_sha256, str) or len(semantic_sha256) != 64
                or any(ch not in "0123456789abcdefABCDEF" for ch in semantic_sha256)
                or (observed_at is not None and (not isinstance(observed_at, str) or len(observed_at) > 80))
            ):
                raise ValueError("checkpoint source row has invalid values")
            bounded_sources.append({
                "source_id": source_id,
                "source_version": source_version,
                "semantic_sha256": semantic_sha256,
                "observed_at": observed_at,
            })
        if len({row["source_id"] for row in bounded_sources}) != len(bounded_sources):
            raise ValueError("checkpoint contains duplicate sources")
        return {
            "schema_version": "c5-monitoring-v1",
            "created_at": created_at,
            "sources": bounded_sources,
        }

    @staticmethod
    def _encode(row: PendingMonitoringCheckout) -> dict[str, Any]:
        return {
            "return_token": row.return_token,
            "principal_ref": row.principal_ref,
            "checkpoint": row.checkpoint,
            "source_channel": row.source_channel,
            "classification": row.classification,
            "owner_test": row.owner_test,
            "checkout_id": row.checkout_id,
            "expires_at": row.expires_at,
            "paid_access_activated": row.paid_access_activated,
        }

    @staticmethod
    def _decode(item: Mapping[str, Any]) -> PendingMonitoringCheckout:
        return_token = item.get("return_token")
        principal_ref = item.get("principal_ref")
        checkpoint = item.get("checkpoint")
        source_channel = item.get("source_channel")
        classification = item.get("classification", "unknown")
        owner_test = item.get("owner_test", classification == "owner_test")
        checkout_id = item.get("checkout_id")
        expires_at = item.get("expires_at")
        paid_access_activated = item.get("paid_access_activated", False)

        if not isinstance(return_token, str) or not return_token:
            raise ValueError("invalid persisted return_token")
        if not isinstance(principal_ref, str) or not principal_ref or len(principal_ref) > 160:
            raise ValueError("invalid persisted principal_ref")
        if not isinstance(checkpoint, dict):
            raise ValueError("invalid persisted checkpoint")
        if not isinstance(source_channel, str) or not source_channel:
            raise ValueError("invalid persisted source_channel")
        if not isinstance(classification, str) or classification not in {"unknown", "confirmed_external", "owner_test", "synthetic"}:
            raise ValueError("invalid persisted classification")
        if not isinstance(owner_test, bool) or owner_test != (classification == "owner_test"):
            raise ValueError("invalid persisted owner_test")
        if checkout_id is not None and (not isinstance(checkout_id, str) or not checkout_id or len(checkout_id) > 160):
            raise ValueError("invalid persisted checkout_id")
        if not isinstance(expires_at, (int, float)):
            raise ValueError("invalid persisted expires_at")
        if not isinstance(paid_access_activated, bool):
            raise ValueError("invalid persisted paid_access_activated")

        return PendingMonitoringCheckout(
            return_token=return_token,
            principal_ref=principal_ref,
            checkpoint=PendingMonitoringCheckoutStore._bounded_checkpoint(checkpoint),
            source_channel=normalize_source_bucket(source_channel),
            classification=classification,
            owner_test=owner_test,
            checkout_id=checkout_id,
            expires_at=float(expires_at),
            paid_access_activated=paid_access_activated,
        )

    def _persist_locked(self) -> None:
        if self.path is None:
            return

        self.path.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "version": 1,
            "rows": [
                self._encode(row)
                for row in self._rows.values()
            ],
        }

        tmp = self.path.with_name(
            f".{self.path.name}.{os.getpid()}.tmp"
        )

        tmp.write_text(
            json.dumps(payload, separators=(",", ":"), sort_keys=True),
            encoding="utf-8",
        )

        try:
            tmp.chmod(0o600)
        except OSError:
            pass

        os.replace(tmp, self.path)

    def _load(self) -> None:
        if self.path is None or not self.path.exists():
            return

        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise RuntimeError(
                "persisted monitoring checkout store is unreadable"
            ) from exc

        if (
            not isinstance(payload, dict)
            or payload.get("version") != 1
            or not isinstance(payload.get("rows"), list)
        ):
            raise RuntimeError(
                "persisted monitoring checkout store has invalid format"
            )

        now = time.time()
        loaded: dict[str, PendingMonitoringCheckout] = {}
        expired = False

        try:
            if len(payload["rows"]) > 128:
                raise ValueError("too many persisted rows")
            for item in payload["rows"]:
                if not isinstance(item, dict):
                    raise ValueError("persisted row must be an object")
                row = self._decode(item)
                if row.expires_at <= now:
                    expired = True
                    continue
                loaded[row.return_token] = row
        except ValueError as exc:
            raise RuntimeError(
                "persisted monitoring checkout store contains invalid data"
            ) from exc

        self._rows = loaded

        if expired:
            with self._lock:
                self._persist_locked()

    def _prune_locked(self) -> None:
        now = time.time()
        kept = {
            key: row
            for key, row in self._rows.items()
            if row.expires_at > now
        }

        if len(kept) != len(self._rows):
            self._rows = kept
            self._persist_locked()

    def create(
        self,
        *,
        checkpoint: Mapping[str, Any],
        source_channel: str,
        classification: str = "unknown",
        owner_test: bool = False,
    ) -> PendingMonitoringCheckout:
        with self._lock:
            self._prune_locked()

            if classification not in {"unknown", "confirmed_external", "owner_test", "synthetic"}:
                classification = "unknown"
            if owner_test or classification == "owner_test":
                classification = "owner_test"
                owner_test = True

            row = PendingMonitoringCheckout(
                return_token=secrets.token_urlsafe(32),
                principal_ref=f"eww_human_{uuid4().hex}",
                checkpoint=self._bounded_checkpoint(checkpoint),
                source_channel=normalize_source_bucket(source_channel),
                classification=classification,
                owner_test=bool(owner_test),
                checkout_id=None,
                expires_at=time.time() + self.ttl_seconds,
            )

            self._rows[row.return_token] = row
            self._persist_locked()
            return row

    def attach_checkout(
        self,
        return_token: str,
        checkout_id: str,
    ) -> PendingMonitoringCheckout | None:
        with self._lock:
            self._prune_locked()

            row = self._rows.get(return_token)
            if row is None:
                return None

            updated = replace(row, checkout_id=checkout_id)
            self._rows[return_token] = updated
            self._persist_locked()
            return updated

    def activate_paid_access(self, return_token: str, *, duration_seconds: int = 2592000) -> bool:
        """Extend a verified paid return link once; each visit still rechecks entitlement."""
        if duration_seconds < 60 or duration_seconds > 2592000:
            raise ValueError("paid access duration must be at most 30 days")
        with self._lock:
            self._prune_locked()
            row = self._rows.get(return_token)
            if row is None or row.paid_access_activated:
                return False
            self._rows[return_token] = replace(
                row, expires_at=time.time() + duration_seconds, paid_access_activated=True
            )
            self._persist_locked()
            return True

    def get(
        self,
        return_token: str,
    ) -> PendingMonitoringCheckout | None:
        with self._lock:
            self._prune_locked()
            return self._rows.get(return_token)


class CommercialPlatformClient:
    def __init__(self, settings: CommercialSettings, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.settings = settings
        self.transport = transport

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self.settings.platform_url.rstrip("/"), timeout=self.settings.timeout_seconds, transport=self.transport)

    async def create_checkout(
        self,
        *,
        principal_ref: str,
        source_channel: str,
        success_url: str | None = None,
        cancel_url: str | None = None,
        external_classification: str = "unknown",
        owner_test: bool = False,
    ) -> dict[str, str]:
        payload = {
            "product_id": self.settings.product_id,
            "principal_ref": principal_ref,
            "source_channel": commercial_source_channel(source_channel),
            "success_url": success_url or self.settings.success_url,
            "cancel_url": cancel_url or self.settings.cancel_url,
        }
        if external_classification != "unknown" or owner_test:
            payload["external_classification"] = external_classification
            payload["owner_test"] = owner_test
        async with self._client() as client:
            response = await client.post("/v1/checkout/session", json=payload)
        if response.status_code != 200:
            raise CommercialPlatformError(f"checkout service returned {response.status_code}")
        try:
            data = response.json()
        except ValueError as exc:
            raise CommercialPlatformError("checkout service returned invalid JSON") from exc
        if not isinstance(data, dict) or not all(isinstance(data.get(key), str) and data[key] for key in ("checkout_id", "stripe_session_id", "checkout_url")):
            raise CommercialPlatformError("checkout service returned incomplete checkout")
        if not data["checkout_url"].startswith("https://"):
            raise CommercialPlatformError("checkout service returned invalid checkout_url")
        return {key: data[key] for key in ("checkout_id", "stripe_session_id", "checkout_url")}

    async def verify_entitlement(self, *, principal_ref: str) -> dict[str, Any]:
        async with self._client() as client:
            response = await client.post("/v1/entitlements/verify", json={"product_id": self.settings.product_id, "principal_ref": principal_ref})
        if response.status_code != 200:
            raise CommercialPlatformError(f"entitlement service returned {response.status_code}")
        try:
            data = response.json()
        except ValueError as exc:
            raise CommercialPlatformError("entitlement service returned invalid JSON") from exc
        if not isinstance(data, dict) or (
            data.get("active") is True
            and (not isinstance(data.get("token"), str) or not data["token"])
        ):
            raise CommercialPlatformError("entitlement service returned invalid active entitlement")
        return data

    async def record_event(
        self,
        *,
        event_type: str,
        source_channel: str,
        commercial_intent: str = "monitoring",
        external_classification: str = "unknown",
        owner_test: bool = False,
    ) -> None:
        try:
            async with self._client() as client:
                response = await client.post("/v1/events", json={
                    "product_id": self.settings.product_id,
                    "event_type": event_type,
                    "source_channel": commercial_source_channel(source_channel),
                    "commercial_intent": commercial_intent,
                    "external_classification": external_classification,
                    "owner_test": owner_test,
                })
            if response.status_code != 200:
                raise CommercialPlatformError(f"commercial telemetry returned {response.status_code}")
        except (httpx.HTTPError, CommercialPlatformError):
            # Optional telemetry never changes checkout or monitoring behavior.
            return
