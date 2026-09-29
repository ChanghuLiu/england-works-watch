from __future__ import annotations
import base64, json, time
import httpx
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

def _decode(v: str) -> bytes:
    return base64.urlsafe_b64decode(v + "=" * (-len(v) % 4))

async def verify_entitlement_token(token: str, *, platform_url: str, expected_product_id: str) -> dict[str, object]:
    async with httpx.AsyncClient(base_url=platform_url.rstrip("/"), timeout=5.0) as client:
        response = await client.get("/v1/entitlements/verification-key")
    if response.status_code != 200:
        raise ValueError("verification key unavailable")
    data = response.json()
    if data.get("algorithm") != "Ed25519":
        raise ValueError("unsupported entitlement algorithm")
    key = Ed25519PublicKey.from_public_bytes(base64.b64decode(data["public_key_b64"]))
    try:
        encoded, signature = token.split(".", 1)
        key.verify(_decode(signature), encoded.encode("ascii"))
        payload = json.loads(_decode(encoded))
    except Exception as exc:
        raise ValueError("invalid entitlement token") from exc
    if payload.get("product_id") != expected_product_id:
        raise ValueError("wrong entitlement product")
    if int(payload.get("exp", 0)) <= int(time.time()):
        raise ValueError("expired entitlement token")
    return payload
