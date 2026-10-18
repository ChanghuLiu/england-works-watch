"""Minimal Google Play one-time product verification and consumption adapter."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import quote

PACKAGE_NAME = "com.regevidencehub.workswatch"
PRODUCT_ID = os.getenv("EWW_PLAY_PRODUCT_ID", "works_watch_30d").strip()
PURCHASE_OPTION_ID = os.getenv("EWW_PLAY_PURCHASE_OPTION_ID", "one-watch").strip()
API_ROOT = "https://androidpublisher.googleapis.com/androidpublisher/v3/applications"


class PlayVerifierUnavailable(RuntimeError):
    pass


class PlayPurchaseRejected(ValueError):
    pass


def _authorized_session():
    raw = os.getenv("EWW_PLAY_SERVICE_ACCOUNT_JSON", "").strip()
    if not raw:
        raise PlayVerifierUnavailable("Play purchase verification is not configured")
    try:
        from google.auth.transport.requests import AuthorizedSession
        from google.oauth2 import service_account

        if raw.startswith("{"):
            info = json.loads(raw)
        else:
            info = json.loads(Path(raw).expanduser().read_text(encoding="utf-8"))
        credentials = service_account.Credentials.from_service_account_info(
            info,
            scopes=["https://www.googleapis.com/auth/androidpublisher"],
        )
        return AuthorizedSession(credentials)
    except Exception as exc:
        raise PlayVerifierUnavailable("Play purchase verification credentials are unavailable") from exc


def verify_purchase(purchase_token: str) -> dict[str, Any]:
    """Verify the product and purchase option with the Android Publisher API."""
    if not PRODUCT_ID or not PURCHASE_OPTION_ID:
        raise PlayVerifierUnavailable("Play product configuration is unavailable")
    session = _authorized_session()
    encoded_token = quote(purchase_token, safe="")
    url = f"{API_ROOT}/{PACKAGE_NAME}/purchases/productsv2/tokens/{encoded_token}"
    try:
        response = session.get(url, timeout=10)
        if response.status_code in {401, 403} or response.status_code >= 500:
            raise PlayVerifierUnavailable("Google Play verifier credentials or service are unavailable")
        if response.status_code != 200:
            raise PlayPurchaseRejected("Google Play did not verify this purchase")
        purchase = response.json()
        if not isinstance(purchase, dict) or purchase.get("packageName") not in {None, PACKAGE_NAME}:
            raise PlayPurchaseRejected("Purchase package does not match")
        state = (purchase.get("purchaseStateContext") or {}).get("purchaseState")
        if state not in {"PURCHASED", "PURCHASE_STATE_PURCHASED"}:
            raise PlayPurchaseRejected("Purchase is not complete")
        items = purchase.get("productLineItem")
        if not isinstance(items, list) or len(items) != 1 or not isinstance(items[0], dict):
            raise PlayPurchaseRejected("Purchase does not contain the expected one-time product")
        item = items[0]
        offer = item.get("productOfferDetails")
        if not isinstance(offer, dict):
            raise PlayPurchaseRejected("Purchase offer details are missing")
        if item.get("productId") != PRODUCT_ID or offer.get("purchaseOptionId") != PURCHASE_OPTION_ID:
            raise PlayPurchaseRejected("Purchase product or option does not match")
        if offer.get("quantity", 1) != 1:
            raise PlayPurchaseRejected("Purchase quantity does not match")

        return purchase
    except PlayPurchaseRejected:
        raise
    except PlayVerifierUnavailable:
        raise
    except Exception as exc:
        raise PlayVerifierUnavailable("Google Play verification service is unavailable") from exc
    finally:
        session.close()


def consume_purchase(purchase_token: str) -> bool:
    """Consume an already verified and durably bound one-time purchase."""
    session = None
    try:
        session = _authorized_session()
        encoded_token = quote(purchase_token, safe="")
        url = f"{API_ROOT}/{PACKAGE_NAME}/purchases/products/{PRODUCT_ID}/tokens/{encoded_token}:consume"
        return session.post(url, timeout=10).status_code in {200, 204}
    except Exception:
        return False
    finally:
        if session is not None:
            session.close()
