"""Narrow CDP x402 authentication without importing the wallet SDK.

Contract checked against cdp-sdk 1.48.x and CDP REST authentication:
https://docs.cdp.coinbase.com/api-reference/v2/authentication
Only /supported, /verify and /settle are authenticated here.
"""
from __future__ import annotations

import base64
import os
import secrets
import time
from importlib.metadata import PackageNotFoundError, version

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519

FACILITATOR_URL = "https://api.cdp.coinbase.com/platform/v2/x402"


def create_facilitator_config():
    key_id = os.getenv("CDP_API_KEY_ID", "").strip()
    secret = os.getenv("CDP_API_KEY_SECRET", "").strip().replace("\\n", "\n")
    if not key_id or not secret:
        raise RuntimeError("CDP_API_KEY_ID and CDP_API_KEY_SECRET are required")
    try:
        if "-----BEGIN" in secret:
            key = serialization.load_pem_private_key(secret.encode(), password=None)
            if not isinstance(key, ec.EllipticCurvePrivateKey) or not isinstance(key.curve, ec.SECP256R1):
                raise ValueError("Unsupported EC key")
            algorithm = "ES256"
        else:
            raw = base64.b64decode(secret, validate=True)
            if len(raw) != 64:
                raise ValueError("Invalid Ed25519 key length")
            key = ed25519.Ed25519PrivateKey.from_private_bytes(raw[:32])
            algorithm = "EdDSA"
    except Exception:
        # Do not include credential contents or parser diagnostics in logs.
        raise RuntimeError("Invalid CDP API signing key") from None
    try:
        sdk_version = version("cdp-sdk")
    except PackageNotFoundError:
        sdk_version = "rest-auth"
    correlation = f"sdk_version={sdk_version},sdk_language=python,source=x402,source_version=2.0.0"

    def create_headers():
        now = int(time.time())
        headers = {}
        for operation, method in (("verify", "POST"), ("settle", "POST"), ("supported", "GET")):
            token = jwt.encode(
                {"sub": key_id, "iss": "cdp", "aud": None, "nbf": now,
                 "exp": now + 120,
                 "uris": [f"{method} api.cdp.coinbase.com/platform/v2/x402/{operation}"]},
                key, algorithm=algorithm,
                headers={"kid": key_id, "typ": "JWT", "nonce": secrets.token_hex(16)},
            )
            headers[operation] = {"Content-Type": "application/json", "Authorization": f"Bearer {token}",
                                  "Correlation-Context": correlation}
        headers["list"] = {"Correlation-Context": correlation}
        return headers

    return {"url": FACILITATOR_URL, "create_headers": create_headers}
