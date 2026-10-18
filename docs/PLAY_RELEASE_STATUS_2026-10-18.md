# Android Play readiness status — 2026-10-18

## Verified locally

- Product: England Works Watch; branch/worktree kept local, no push or merge.
- Android: `:app:testDebugUnitTest :app:assembleDebug` passed after optional upload-signing support was added. Debug APK: `app/build/outputs/apk/debug/app-debug.apk`.
- Backend Python suite: 105 passed.
- ADB: attached Huawei CLT-L04 (`DXU7N18815000043`); APK installed and launcher activity opened. The on-device startup smoke passed. Billing remains pending an Internal Testing install from Google Play.
- Release target/compile SDK: 36; version: 1.0.0 / code 1; BillingClient: 9.1.0; production API: HTTPS. The official Play target policy currently requires API 36 for new apps and updates from 2026-08-31; 9.1.0 is the current listed Google Play Billing release.
- Privacy, terms, and support pages returned HTTP 200 at the URLs in `docs/PLAY_INTERNAL_TESTING.md`.
- Upload signing is configured to read credentials from an external mode-0600 properties file. No app-specific properties or upload keystore was present, so no release AAB was generated.
- `.github/workflows` diff: empty. No production deploy, Play purchase, email, or customer contact occurred.

## Production mobile API check

- Read-only GET `https://works.regevidencehub.com/api/mobile/v1/catalog` returned HTTP 404 (`Not Found`) on 2026-10-18. The mobile API route is not currently available on the production host, so this build cannot complete a production-backed flow until the backend route is promoted through the normal release process. No deploy was performed.
- WorksWatch phone check: the debug app starts; production-backed behavior remains blocked by the 404 above. No purchase was initiated.
- Local phone verification: debug build was pointed to `127.0.0.1:8000` through `adb reverse`, and a temporary test baseline/runtime directory supported the local backend. The app loaded the catalog, created a free checkpoint, and displayed “No verified change”. Non-JSON HTTP errors now produce a safe service-unavailable message. The production route remains 404.

## Play Console state

Reviewed in the authenticated account on 2026-10-18. Only the separate Taxi / PHV Preflight entry (package com.regevidencehub.taxi) appeared among the ten apps in this developer account. This app package has no matching Play Console entry; product, track, and Android Publisher access are therefore not configured/verified for this app.

The Create app form requires the account holder to confirm Developer Programme Policy compliance and personally acknowledge/certify US export-law compliance. I did not submit those declarations. No service-account key was created or downloaded.

## Next human action

In Play Console, the account holder must complete the required Developer Programme Policy and US export-law declarations before creating this package entry. A per-app upload signing properties file/keystore is also missing; create/provide it securely at the documented external path. Once the production mobile API route is live, create/verify the one-time product and Android Publisher access, then upload a signed AAB to Internal Testing.
