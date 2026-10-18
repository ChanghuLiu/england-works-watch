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

Play Console was reviewed in the authenticated developer account on 2026-10-18. The app list showed ten total apps and only the separate Taxi / PHV Preflight package among RegEvidenceHub apps; this package has no matching app entry. Product, internal track, and Android Publisher service-account access are not configured/verified. App creation requires the account holder to attest Developer Programme Policy compliance and US export-law compliance; those declarations were not submitted.

- Debug APK: `android/app/build/outputs/apk/debug/app-debug.apk` (for Works Watch: `app/build/outputs/apk/debug/app-debug.apk`). It was installed and launched on the attached ADB device; this was a sideloaded free-flow smoke only, not a Play Billing test.
- `:app:testDebugUnitTest :app:assembleDebug`: passed after the release signing configuration change.
- Release signing reads a local properties file outside the repository: `~/.config/regevidencehub/works-upload.properties`. Override with `-PworksUploadProperties=/absolute/path/to/file` (see the app Gradle file for the exact property name). Required keys are `storeFile`, `storePassword`, `keyAlias`, and `keyPassword`. Keep the file mode 0600 and the keystore outside the repository. No app-specific signing file was found, so no signed release AAB was generated. Do not reuse the Taxi key for this package.
- Required Play verifier setting: `EWW_PLAY_SERVICE_ACCOUNT_JSON; EWW_PLAY_PRODUCT_ID (optional); EWW_PLAY_PURCHASE_OPTION_ID (optional); EWW_PENDING_STORE_PATH (optional); EWW_RUNTIME_DIR`. This is server-side only; never put it in the Android app. Runtime durability must use persistent Railway volume mounted at /data.
- Data Safety notes: the client sends user-entered preflight data to the existing backend for processing; purchase tokens are sent to the backend for Play verification and retained server-side only as SHA-256 fingerprints. Recovery credentials are stored by the client using Android Keystore. Review the linked privacy notice and the backend retention rules before completing the Play Data Safety form.

## Internal testing checklist

1. Confirm the Play app exists with the exact package above; inspect app access for the existing Android Publisher service account.
2. Confirm the product and option IDs above match the backend. Confirm it is a one-time purchase; Works Watch must be non-renewing, and FactoryTalk/OPC UA packs retain the stated quota and 365-day expiry.
3. Add internal testers and license testers. Publish an Internal Testing release, then install it from the Play opt-in link.
4. Verify the localized price is read from Play `ProductDetails`, then test purchase, pending/cancelled purchase, app restart/recovery, idempotent replay, grant-before-consume, and consume retry.
5. Verify the release listing, privacy/terms/support links, Data Safety form, phone screenshots, and review declarations. Do not submit a production rollout as part of internal testing.

## Phone screenshots and smoke checklist

- Capture a clean home screen with the app name and independent-preflight scope visible.
- Capture one representative input/check screen with no real customer or sensitive data.
- Capture the free result with source/findings and any uncertainty or unsupported-input notice visible.
- Capture the purchase offer only from an Internal Testing install after Play returns its localized `ProductDetails` price; do not use a sideloaded build for this screenshot.
- Capture the recovered report or watch state after a license-tester flow, with test data only.
- Before store upload, review screenshots for personal information, debug banners, stale prices, and claims of approval, certification, compliance, or official affiliation.
- Smoke on a physical phone: cold launch, rotate/relaunch where supported, navigate all tabs, perform one safe free flow, confirm offline/API errors are understandable, background/restore, and check `adb logcat` for crashes. Do not make a real purchase.

## Console access and next human action

The authenticated Play Console account was inspected on 2026-10-18. Only Taxi / PHV Preflight appears among the RegEvidenceHub app entries; this package has no matching app entry, product, or internal track. App creation is blocked until the account holder personally confirms Developer Programme Policy and US export-law declarations. The app-specific upload signing file is also missing. After those human steps, make the production API route available, configure product/service-account access, upload a signed AAB to Internal Testing, and run the listed billing checks.
