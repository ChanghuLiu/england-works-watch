# Works source review — 10 October 2026

This release reviews all four official sources in `data/source_registry.json`. Each committed `reviewed_semantic_sha256` identifies the normalized visible main text actually examined. The Docker audit must fetch that exact content before producing a runtime seed. Later changes remain blocking until another explicit review.

## Rule mapping checked

| Official source | Current version / valid from | Implemented rules checked | Outcome |
|---|---|---|---|
| Sponsor Part 3 | 08/26 / 28 August 2026 | C1.13–C1.20: worker reporting deadlines, delayed starts and unauthorised absence; C1.21–C1.25: normal location changes versus hybrid/occasional work; C1.26: ending sponsorship; C2.2–C2.5 and C3: organisation changes; C4.1–C4.12: ownership and TUPE | Existing report, absence, location, cessation, organisation and transfer branches remain supported. Use C1.19 for the specific absence deadline. |
| Sponsor Part 2 | 10/26 / 8 October 2026 | S3.15–S3.21: 28-day start window and reporting; S4.19–S4.28: four-week absence threshold, exceptions and compelling reasons; S9.10–S9.17: role and employment changes | Existing ordinary branches remain supported. The accessible document moved to the `accessible--2` URL. |
| Skilled Worker | 04/26 / 8 April 2026 | SK8.1–SK8.8: unpaid leave, permitted salary reductions, notification, new permission and cessation | Existing salary branches remain supported; the engine still requires the caller's salary eligibility facts. |
| Appendix D | 10/26 / 8 October 2026 | Introduction and sections 1, 3–5: retention, right-to-work evidence, pay, skill and other worker records | The general record-retention proposition remains supported. Updated right-to-work coverage must be considered when collecting evidence. |

Part 2 now includes S8.28–S8.29 on individual employment conditions for Skilled Workers identified as victims of modern slavery. The engine does not determine an individual's eligibility for this provision. Two optional input flags route supplied special circumstances to `REVIEW_REQUIRED` instead of applying ordinary employment-change rules. Religious Worker changes scheduled for 29 October remain outside this Skilled Worker product's scope.

Appendix D updates section 1.1 for wider working arrangements and sections 2.1/2.2 for Religious Worker recruitment. The product does not provide a separate right-to-work or Religious Worker eligibility determination.

## Release and persistence controls

The registry explicitly supersedes `2026-09-08.1`. Only that known predecessor can migrate, and only after the live build audit matches every committed reviewed fingerprint. The previous persistent state is archived before replacing its baseline. Restarting the same registry never clears pending reviews; unknown predecessors fail closed. Fetch errors retain the last successful observation, and the 24-hour runtime freshness and 30-day review expiry remain in force. Oversized pages are rejected rather than hashed after truncation.

Source URLs, versions, effective dates, review dates, locators and content fingerprints are recorded in the registry. No payment setting or monitor cadence changes in this release.
