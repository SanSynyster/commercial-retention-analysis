# P3-010C1 Public Release Candidate

## Scope and changed files

This update prepares the existing seven-page Streamlit application for independent release review. It does not change research results, bundle contents, Git history, or deployment state.

- `app/streamlit_app.py` — shared Data Sources & Research Limitations section.
- `tests/test_dashboard_app.py` — focused attribution visibility assertion.
- `docs/recovery/COMMERCIAL_DS_003_STAGE_B2B3_GUIDE.md`
- `docs/recovery/COMMERCIAL_DS_003_STAGE_B2B3_OUTCOMES_GUIDE.md`
- `docs/recovery/COMMERCIAL_DS_003_STAGE_B2B3_OUTCOME_FINALIZE_GUIDE.md`
- `docs/research/COMMERCIAL_DS_P2_M1_007_COHORT_SPLIT_IMPLEMENTATION.md` — portable replacements for personal local paths.
- This report.

## Attribution and limitations

The shared sidebar expander is available throughout the app. It cites UCI Online Retail II (Chen, 2012; DOI 10.24432/C5CG6D) under CC BY 4.0, links the licence, and describes removal of duplicated overlap records in the corrected historical dataset. It also cites UCI Online Retail (Chen, 2015; DOI 10.24432/C5BW33) where relevant. The attribution makes no endorsement claim.

The section identifies the MineThatData E-Mail Analytics and Data Mining Challenge as the source of the historical randomised experiment. It describes the app's results as aggregate analysis and states that source records, row-level records, individual assignments and split data are not distributed. It does not claim a formal Hillstrom redistribution licence. It distinguishes historical description and prediction, exploratory modelling, retrospective targeting, randomised experimental findings and hypothetical CRM scenarios, and says the app is not a live scoring or campaign-execution service.

## Release-tree and ancestry checks

The current tracked application uses six aggregate bundles; no raw source dataset, customer-level prediction output, Hillstrom row-level record, assignment file, secret or credential is required or included in the app runtime. The app reads its committed aggregate bundles and performs no model fitting at startup. The two tracked recovery CSVs are reference/taxonomy support files, not customer-level records. `.streamlit/secrets.toml` is ignored and absent. The four previously identified documents no longer contain the personal local path in their current working-tree versions.

The development branch is at `a43e564f363fabeddff790b8ebba750454ac1819` and descends from the rewritten public main `4e326e68e9f082e27f7f792453b391166b8655dc`. It is 41 commits ahead. The local refs inspected contain only `main`, `origin/main` and `origin/HEAD`; no tags or private recovery refs are present. The three removed notebook-output paths have no history on the current `main`, and the three identified pre-remediation commit IDs are not reachable from it. Read-only remote inspection confirmed public `main` still at the rewritten SHA.

One release consideration remains: earlier versions of each of the four corrected documents still exist in older blobs among the 41 local development commits and contain personal absolute paths. The current files are portable, but a later push of all 41 commits would make those historical strings reachable. No further history rewrite was authorised or performed here. Claude review should consider whether that limited path exposure needs a separately approved treatment before the development commits are published. It is distinct from the previously removed customer-level notebook outputs.

## Application verification

- Focused Streamlit application suite: **81 passed, 1 skipped**. The skip is the expected private-source rebuild case; committed-bundle tests run.
- Streamlit AppTest checks cover page registration/rendering and the new shared attribution section; all seven pages remain registered.
- Python compilation and imports passed.
- Python 3.11 deployment dependency dry-run resolved; installed environment reported Streamlit 1.66.1 and Altair 6.3.0, and `pip check` was clean.
- App startup/render paths use aggregate bundles and do not run training or access private source datasets. No unintended external data connections or secrets were found in the application configuration.
- All six bundle content SHA-256 values are unchanged:
  - Customer Overview: `5bd05077dd03d8a053150c752bd9610431c96b35e5b269b045eebf065d006c4c`
  - Propensity: `a4fcc6d60cac7ddc2de3a5c62c457c9f706237792b42b1bdffa1715d09535562`
  - Predictive Intelligence: `40dba007ed5c76ba595413ecdf3ab7f0e24245f13a11d7de9d23a6f8fe57ddfd`
  - Segmentation: `590328678dcb144d94d5d8c54a79d767f0590a22554e9e4bd9dabbbad3f522a8`
  - Causal Evidence: `720a35d13c1de8d5f6db62bacf64bf7945b072a606c3b5ec19d5ea5015c2da4b`
  - CRM Targeting: `44bcf66762056a8746333239e731e6d79809d2a0a29904924dd9b8c858a7c6f9`

## Publication status and review readiness

The P3-010A eligibility assessment remains in force. UCI material carries its documented attribution requirements. Publication of the original aggregate Hillstrom research findings is recommended for owner consideration, but final owner approval remains outstanding; history remediation is not publication permission. The causal evidence page remains in this local release candidate and has not been published.

The candidate is ready for independent Claude scientific and engineering review, with the historical personal-path caveat above explicitly surfaced. No commit, push or deployment was made.
