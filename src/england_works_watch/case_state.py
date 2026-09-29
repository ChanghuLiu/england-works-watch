from __future__ import annotations
from dataclasses import dataclass
import hashlib, json, os, secrets, time
from pathlib import Path
from typing import Any, Mapping

@dataclass(frozen=True)
class StoredCase:
    case_ref: str
    state_ref: str
    action: str
    payload: dict[str, Any]
    source_bucket: str
    classification: str
    owner_test: bool
    expires_at_epoch: int

class DurableCaseStore:
    def __init__(self, runtime_dir: str | Path, ttl_seconds: int = 86400) -> None:
        self.root = Path(runtime_dir) / "human_cases"
        self.root.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = ttl_seconds

    def _path(self, state_ref: str) -> Path:
        return self.root / f"{state_ref}.json"

    def create(self, *, action: str, payload: Mapping[str, Any], source_bucket: str, classification: str, owner_test: bool) -> StoredCase:
        now = int(time.time())
        state_ref = "ews_" + hashlib.sha256(secrets.token_bytes(32)).hexdigest()[:32]
        row = StoredCase(
            case_ref="eww_" + secrets.token_hex(16),
            state_ref=state_ref,
            action=action,
            payload=dict(payload),
            source_bucket=source_bucket,
            classification=classification,
            owner_test=bool(owner_test),
            expires_at_epoch=now + self.ttl_seconds,
        )
        path = self._path(state_ref)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(row.__dict__, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
        return row

    def get(self, state_ref: str) -> StoredCase | None:
        if not state_ref.startswith("ews_"):
            return None
        path = self._path(state_ref)
        try:
            row = StoredCase(**json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError):
            return None
        if row.expires_at_epoch <= int(time.time()):
            try: path.unlink()
            except OSError: pass
            return None
        return row
