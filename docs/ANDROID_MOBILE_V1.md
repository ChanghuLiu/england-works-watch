# England Works Watch Android v1

## Product flow

The Android app is the fourth Works Watch channel. Home is dashboard-first; the other native destinations are Watches and Activity. Starting a watch presents one question: which of the existing four official GOV.UK sponsor guidance sources to checkpoint. The app submits only those source IDs to the existing source evidence engine. It collects no worker, employer, immigration, or sponsor-case facts and has no rules or monitoring implementation of its own.

The backend returns a free, dated checkpoint and comparison status before displaying a paid offer. The status uses bounded language such as **Ready to watch**, **No verified change**, **Change detected**, **Review needed**, and **Source unavailable**. A source change or unavailable source is a human review signal, not a new regulatory conclusion. Unavailable, stale, invalid, or changed source evidence prevents a new purchase offer.

After a valid server-created checkpoint, the app can offer repeat source checks for one-time payment through Google Play. The offer starts exactly 30 days of access, has no subscription and no auto-renewal, and shows only the localized price returned by Google Play ProductDetails. The app never unlocks on a Play callback alone: the backend verifies the purchase with Google Play before durable activation. Repeat checks compare the same selected checkpoint and use the existing `changed_since` implementation.

## Identifiers and API

- Android application/package: `com.regevidencehub.workswatch`.
- Google Play one-time product: `works_watch_30d`.
- Purchase option: `one-watch`.
- Canonical production API base: `https://works.regevidencehub.com`.
- Mobile routes: `GET /api/mobile/v1/catalog`, `POST /api/mobile/v1/cases`, `POST /api/mobile/v1/status`, and `POST /api/mobile/v1/purchases/verify`.
- Android uses Google Play only for payment. Existing web/Stripe/MCP/x402 routes and flows are unchanged.

`POST /cases` creates the existing pending monitoring checkpoint row, not a parallel case or monitoring store. Recovery and status use that row's 256-bit random `case_token`; there is no unauthenticated lookup by predictable case ID. The app encrypts the token using an Android Keystore AES-GCM key and disables Android backup for app state.

## Play verification and durability

The backend checks Google Android Publisher `ProductPurchaseV2`, using the configured package in the verification endpoint and checking product ID, nested purchase option, quantity, completed purchase state, and consumption state. An already-consumed token is accepted only when its fingerprint is already bound to that active watch; this makes retries safe after a crash between Play consumption and persistence without allowing a consumed token to start a second watch. It hashes the purchase token with SHA-256 and persists only that fingerprint. The raw token is held only in request memory and is not included in responses, logs, or persistence.

Activation binds one fingerprint to one checkpoint token. The durable row is updated with the purchase binding and canonical `30 * 24 * 60 * 60` second expiry **before** the Play consume call. If consumption fails, `consume_pending` remains durable. A repeated verification retries consumption without extending the expiry or activating another watch. A repeated fingerprint cannot be bound to a second case. Missing or unusable Play credentials return 503 and do not activate access.

The existing `PendingMonitoringCheckoutStore` is also used by the web offer. Its path defaults to `$EWW_RUNTIME_DIR/pending-monitoring.json` (or `/data/england-works-watch/pending-monitoring.json` on Railway when no runtime override is set); `EWW_PENDING_STORE_PATH` can explicitly select a path. The existing Railway Docker runtime uses `/data` as `EWW_RUNTIME_DIR`, backed by the service's mounted persistent volume. Set the override only to a persistent mounted location. The store writes atomically with owner-only file permissions. The product's 30-day duration comes from the existing canonical monitoring offer constant, not client input or a Play subscription period.

## Server configuration

- `EWW_PLAY_SERVICE_ACCOUNT_JSON`: service-account JSON content or a path to a JSON key file. The linked Google Play Developer account must have Android Publisher API access for this app.
- `EWW_PLAY_PRODUCT_ID`: optional override; defaults to `works_watch_30d`.
- `EWW_PLAY_PURCHASE_OPTION_ID`: optional override; defaults to `one-watch`.
- `EWW_PENDING_STORE_PATH`: optional persistent store path override.
- `google-auth` is a production dependency in `pyproject.toml`, installed by the existing Docker `.[x402,test]` path.

## Privacy and release behavior

The backend stores the source checkpoint and opaque purchase fingerprint only. The Android app retains no raw purchase token or customer case facts. Mobile status responses are `no-store`; recovery requires the secret case token in a POST body. Android release traffic uses HTTPS with cleartext disabled. Debug builds permit cleartext only for loopback hosts used by local development. No government logos, insignia, endorsement, or approval claims are used.

## Verification and Play blockers

Required local Android command: `./gradlew :app:testDebugUnitTest :app:assembleDebug`.

Backend mobile and existing suites are run separately and results are recorded in `STATUS_ANDROID.md`. No phone/ADB validation is assumed; if no attached device is available, install and purchase UX remain pending.

Before a Play internal test, create the Play app with the exact package name, configure `works_watch_30d` as a consumable one-time product and the `one-watch` buy option, enable/link Android Publisher API access for the verifier service account, and configure the production `EWW_PLAY_SERVICE_ACCOUNT_JSON`. Validate localized price and the full verify/consume/retry path with a Play license tester. Store listing, privacy/data-safety declarations, screenshots, and Play review remain release gates. No Play Console changes or payments are performed as part of this implementation.
