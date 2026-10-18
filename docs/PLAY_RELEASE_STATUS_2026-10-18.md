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

## Play Console and export status — 2026-10-18

- The account owner created **Works Watch** in the authenticated Play Console. Package: `com.regevidencehub.workswatch`. Console app ID: `4973923902800139999`. The agent filled the app name/package form and checked package availability; the owner completed the creation action.
- The app-list shows this entry as **Draft**, with installed audience **0**. No app bundle/release is shown for this app, so Internal Testing distribution has not started.
- The en-GB default store listing text was saved as a draft on 2026-10-18. Its app icon, feature graphic, and at least two phone screenshots are still missing; the listing was not submitted.
- The Play “No ads” declaration was saved after source review found no ad SDK or implementation. It remains in Publishing overview and was not sent for review.
- Play app-content declarations saved: privacy policy URL, no ads, not a government app, no financial features, and no health features. Changes remain in Publishing overview and were not sent for review.
- The required Developer Programme Policy and US export-law statements are part of the Console creation form. The account owner completed app creation; this agent did not submit either declaration. The project files still contain no CCATS, self-classification report, or other export-classification record, so the technical/legal classification has not been independently verified here. See [Google Play export compliance](https://support.google.com/googleplay/android-developer/answer/113770?hl=en), [BIS mass-market encryption guidance](https://www.bis.gov/learn-support/encryption-controls/mass-market), and [BIS encryption items not subject to the EAR](https://www.bis.gov/learn-support/encryption-controls/encryption-items-not-subject-to-ear).
- The one-time product ID expected by the Android client is `works_watch_30d / one-watch`. No product is configured/verified in Play Console yet. The CQC and Waste one-time-product pages explicitly show no products and require a bundle containing the Play Billing permission before product setup; this app also has no bundle/release uploaded in Console.
- The existing Android Publisher service-account user is Active and has app-level Play Console access for this app (13 permissions shown). The owner extended the access to all eight RegEvidenceHub apps on 2026-10-18. This is app-level access; account-level permissions remain unselected. No credential/key was created or downloaded, so backend Android Publisher API authentication is still unconfigured.
- The Console dashboard still requires app information/store-listing setup before a closed test. A signed AAB is unavailable because no per-app upload keystore or signing properties file exists. The Android client manifest includes `com.android.vending.BILLING`; Console cannot verify that permission until an artifact is uploaded.
- Read-only production check on 2026-10-18: `https://works.regevidencehub.com/api/mobile/v1/catalog` returned HTTP 404. No production deployment was performed. The debug APK starts on the connected Huawei device, but production-backed flow and Play Billing installation remain pending.

## Remaining blockers and next actions

- Remaining Play setup includes sign-in/access details, content-rating questionnaire, target-audience declaration, Data safety, and category/contact details. CQC's content-rating flow is known to present IARC Terms of Use and require a contact email; no IARC terms were accepted or questionnaire submitted for any app. Target-audience setup is gated on sign-in details.
1. Provide or create the app-specific upload signing material securely at the documented external path; then build and upload a signed AAB to Internal Testing.
2. After Console accepts the Billing-enabled bundle, create/verify the one-time product `works_watch_30d / one-watch` and its purchase-option ID/price against the Android/backend code. Preserve Works Watch as a non-renewing 30-day purchase.
3. Finish the Play store listing, Data Safety/app-content declarations, privacy/support/terms links, and internal tester setup; then use a Play Internal Testing install for Billing smoke testing.
4. Configure the existing Android Publisher service-account credential through the normal secure backend deployment process; app-level Console access is already verified, but no credential was downloaded or added here.
5. Promote the app's mobile API route through the normal release process, then recheck the production HTTPS route. No deployment was made during this task.
