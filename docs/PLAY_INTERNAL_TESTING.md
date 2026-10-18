# Google Play Internal Testing — England Works Watch

## Product identity

- App: England Works Watch
- Package: `com.regevidencehub.workswatch`
- In-app product / option: `works_watch_30d` / `one-watch` (one-time purchase)
- Release API: https://works.regevidencehub.com (HTTPS)
- Privacy: https://works.regevidencehub.com/privacy
- Terms: https://works.regevidencehub.com/terms
- Support: https://works.regevidencehub.com/support
- Play Billing Library: 9.1.0; target SDK 36; version 1.0.0 (code 1)

## Store listing draft

**Short description**

Track selected England source updates with a one-time 30-day watch.

**Full description**

England Works Watch checks selected supported public sources again over a 30-day period and shows changes against the saved checkpoint. Choose sources, review the baseline, and return to the watch status and history. The watch is a one-time 30-day purchase. It does not renew automatically and is not a subscription. Source coverage is limited to the sources shown in the app.

## Local release state (2026-10-18)

Unknown: no Play Console session or app/product listing was exposed for inspection. Verify or create the app/package and the one-time product `works_watch_30d` with option `one-watch`; do not configure it as a subscription. Grant the existing Android Publisher service account access.

- Debug APK: `android/app/build/outputs/apk/debug/app-debug.apk` (for Works Watch: `app/build/outputs/apk/debug/app-debug.apk`). It was installed and launched on the attached ADB device; this was a sideloaded free-flow smoke only, not a Play Billing test.
- `:app:testDebugUnitTest :app:assembleDebug`: passed after the release signing configuration change.
- Release signing reads a local properties file outside the repository: `~/.config/regevidencehub/works-upload.properties`. Override with `-PworksUploadProperties=/absolute/path/to/file` (see the app Gradle file for the exact property name). Required keys are `storeFile`, `storePassword`, `keyAlias`, and `keyPassword`. Keep the file mode 0600 and the keystore outside the repository. No file was found, so no signed release AAB was generated.
- Required Play verifier setting: `EWW_PLAY_SERVICE_ACCOUNT_JSON; EWW_PLAY_PRODUCT_ID (optional); EWW_PLAY_PURCHASE_OPTION_ID (optional); EWW_PENDING_STORE_PATH (optional); EWW_RUNTIME_DIR`. This is server-side only; never put it in the Android app. Runtime durability must use persistent Railway volume mounted at /data.
- Data Safety notes: the client sends user-entered preflight data to the existing backend for processing; purchase tokens are sent to the backend for Play verification and retained server-side only as SHA-256 fingerprints. Recovery credentials are stored by the client using Android Keystore. Review the linked privacy notice and the backend retention rules before completing the Play Data Safety form.

## Internal testing checklist

1. Confirm the Play app exists with the exact package above; inspect app access for the existing Android Publisher service account.
2. Confirm the product and option IDs above match the backend. Confirm it is a one-time purchase; Works Watch must be non-renewing, and FactoryTalk/OPC UA packs retain the stated quota and 365-day expiry.
3. Add internal testers and license testers. Publish an Internal Testing release, then install it from the Play opt-in link.
4. Verify the localized price is read from Play `ProductDetails`, then test purchase, pending/cancelled purchase, app restart/recovery, idempotent replay, grant-before-consume, and consume retry.
5. Verify the release listing, privacy/terms/support links, Data Safety form, phone screenshots, and review declarations. Do not submit a production rollout as part of internal testing.

## Console access and next human action

Console inspection was not possible: the available Chrome browser automation failed to expose tabs, and no Play Console connector is available. Unknown: no Play Console session or app/product listing was exposed for inspection. Verify or create the app/package and the one-time product `works_watch_30d` with option `one-watch`; do not configure it as a subscription. Grant the existing Android Publisher service account access.
