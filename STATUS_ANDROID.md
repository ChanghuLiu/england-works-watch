# Android v1 implementation status

- Worktree: `/home/kevin/mcp/worktrees/england-works-watch-android`
- Branch: `codex/android-client-v1`, based on `origin/main`.
- Backend-mapped flow: select one or more of the existing four source IDs, create the current backend checkpoint, see free source comparison, optionally start a 30-day repeat-check watch via one-time Google Play purchase, and view status/history.
- Package/product/option: `com.regevidencehub.workswatch` / `works_watch_30d` / `one-watch`.
- Canonical production API: `https://works.regevidencehub.com`.
- 30-day meaning: server-persisted, non-renewing 30-day monitoring access starting once after verified purchase. No subscription or automatic renewal.
- Durable storage: existing pending monitoring store at `$EWW_RUNTIME_DIR/pending-monitoring.json`; Railway's existing Docker runtime uses `/data`. Purchase tokens are persisted only as SHA-256 fingerprints.
- Privacy: random 256-bit case recovery token, app-side Android Keystore AES-GCM encryption, no backup, no customer facts or raw purchase token persistence.
- Play server configuration: `EWW_PLAY_SERVICE_ACCOUNT_JSON`, optional `EWW_PLAY_PRODUCT_ID`, `EWW_PLAY_PURCHASE_OPTION_ID`, and `EWW_PENDING_STORE_PATH`.
- Android build/tests: `./gradlew :app:testDebugUnitTest :app:assembleDebug` passed; 3 JVM unit tests passed. APK: `app/build/outputs/apk/debug/app-debug.apk`.
- Backend focused tests: 30 passed (mobile Play verification/retry/replay prevention/source fail-closed behavior, monitoring persistence/comparison, public/commercial, HTTP routes).
- Backend full suite: 105 passed after installing `.[x402,test]` into `/tmp/eww-android-v1-venv`; one upstream Starlette/AnyIO deprecation warning.
- ADB phone gate: pending; `adb devices -l` returned no attached devices. No device-dependent work is blocking implementation.
- Play blockers: Play Console app/product/option setup, linked Android Publisher service account, license tester validation, localized price validation, and store listing/privacy/data-safety review.
- External actions: no push, PR, GitHub Actions, Railway deploy, Play Console changes, or payment.
