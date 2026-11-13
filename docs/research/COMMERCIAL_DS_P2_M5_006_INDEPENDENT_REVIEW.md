# M5-006R — Final Independent Integration and Release-Readiness Review

## Verdict

**PASS WITH CONDITIONS.**

- **Application: no closure blockers.**
  - All four pages render through the real navigation, and the rename is complete.
  - The three aggregate bundles are byte-identical to the committed baseline, and their pins hold.
  - Every malformed-bundle case tested gives a controlled error.
  - All accepted M5-002 to M5-005 corrections are present.
  - A release-candidate tree with a fresh install passes its tests and serves the app.
  - M5-006 can be committed locally as it stands.
- **Public release: requires preparation.** The conditions below are all release-preparation items, not application defects:
  - **P1:** the configured development `origin` is a public repository, and its history already contains raw data. Do not push this development history.
  - **P2:** publish the frozen research documents byte-identical, not edited. The bundles record their SHA-256 hashes.
  - **P3:** add one short reader-facing index for excluded research artifacts.
  - **P4:** finalise the manifest: include the root README and say how the bundles were produced.

## Scope and baseline

- **Repository:** HEAD `6b4b98d079559b628b277794a2e1eb0a324257bb`.
- **Uncommitted M5-006 changes:**
  - Modified: `README.md`, `app/README.md`, `app/streamlit_app.py`, `tests/test_dashboard_app.py`, `tests/test_targeting_bundle.py`.
  - Renamed: `app/views/placeholders.py` → `app/views/targeting_explorer.py` (only the docstring changed).
  - New: the M5-006 note.
- **Remotes:** both GitHub repositories were inspected read-only (`gh repo view`, `git ls-remote`, GitHub tree API). No remote, commit, branch or file in the repository was changed. Probe trees, venvs and scripts were kept in a session scratch directory.

## A. Four-page integration

| Check | Result |
| --- | --- |
| Navigation | `st.navigation` registers Customer Overview, Purchase Propensity, **CRM Targeting Explorer** and **CRM Experiment Feasibility**. Navigation titles now match the in-page titles. URL paths are unchanged. |
| Rendering (AppTest via real routing, release-candidate tree) | Customer Overview: 4 metrics, 3 tables. Purchase Propensity: 14 metrics, 3 warnings. CRM Targeting Explorer: 5 tables, 1 warning. CRM Experiment Feasibility: 13 metrics, 2 warnings. **0 exceptions, 0 errors.** |
| Rename | `placeholders.py` no longer exists. No remaining `placeholders` reference in `app/`, `src/`, `tests/` or `README.md`, and no old navigation title strings. Both targeting AppTests import `views.targeting_explorer` and pass. |
| Error handling (15 cases) | For each data page, five cases were tested: missing file, invalid JSON, tampered value, null data section, and empty `provenance`. Every case gave exactly one `st.error` with no metrics, tables or exceptions. The M5-002, M5-003 and M5-004 malformed-bundle gaps are closed. |
| Terminology | Each page carries its evidence type: Historical description, Historical prediction, Retrospective targeting, and Hypothetical scenario. "Gross merchandise", "repeat selection" and "net ITT" are used consistently with the accepted reviews. No material usability inconsistency was found. |

## B. Scientific consistency

The page modules are unchanged from the reviewed M5-002 to M5-005 versions except for the navigation titles. All accepted corrections were confirmed present:

| Page | Accepted findings preserved | Evidence |
| --- | --- | --- |
| Customer Overview | Corrected-V2 source; identified versus unattributed merchandise; mature versus immature follow-up kept separate with no pooled rate; descriptive groups only; cohort small-cell display convention disclosed as **not a disclosure guarantee** (M5-002 R1); content hash pinned (R2) | `publication_review.suppression_rule` is shown on the page. `EXPECTED_CONTENT_SHA256 = 5bd05077…` is enforced. |
| Purchase Propensity | M1 weak or inconclusive (criterion not met); M2 stronger; separate tasks, with labelled "M1 — / M2 — Model C ROC-AUC" tiles and a visible head-to-head warning (M5-003 R2); calibration exploratory, with the different-window caption (R1) and an inverse delta colour (R3) | Rendered: 3 warnings, distinct tile labels |
| CRM Targeting Explorer | Retrospective purchasing, not uplift; C − frequency differences small and inconclusive, not equivalence; ~17% tied selections, with tie shifts comparable to the differences (M5-004 R2); repeat selection described as list membership, not contact | Page text confirmed |
| CRM Experiment Feasibility | Hypothetical M4 inputs; no measured effect; net ITT (`g − c`) distinct from cohort-average and total contribution; unresolved operational inputs; **MDE versus assumed effect** shown (M5-005 R1) | `effect_mde_interpretation` uses the frozen `statistical_commercial_comparison` at the *selected* capacity. It is consistent with `abs(g − c) ≥ MDE` across all 1,920 combinations of the M4 input grid × 5 populations × 4 capacities. |

**Wording.** The root README's new "Interactive research application" section and `app/README.md` correctly state that retrospective purchasing is not causal impact, that the pilot is hypothetical, and that the app needs no raw or customer-level data.

No materially misleading language or presentation was found.

## C. Bundle integrity

- `git diff HEAD -- app_data/` is empty. Current SHA-256 values:
  - `customer_overview_v1.json`: `c2555d79…`
  - `propensity_summary_v1.json`: `fa6e5d16…`
  - `targeting_v1.json`: `56dc435c…`
- All three loaders validate against their independent content pins. The tampered-bundle cases above were rejected.
- **Runtime file access:** an audit hook over a full four-page run in the release-candidate tree recorded only the three `app_data/*.json` files as data opens. Nothing under `data/`, `source_data/` or any Parquet file was opened. The feasibility page reads no file.
- No customer-level predictions, selection lists, model binaries or private datasets are needed at runtime.

## D. Reproducibility

| Environment | Command / check | Result |
| --- | --- | --- |
| Development `.venv` | Focused app and M4 suites (7 modules) | **53 run, 52 passed, 1 skipped**: propensity rebuild (`LOCAL_DATA_DIR` unset) |
| Development `.venv` | `unittest discover -s tests` | **170 run, 168 passed, 2 skipped**: Spark (no Java runtime) and propensity rebuild |
| Development `.venv` | `discover -s docs/recovery -p 'test_COMMERCIAL_DS_007*.py'` | 15 OK |
| **Release-candidate tree**: 28 public Phase 1 files + manifest + M5-006 README; no `data/`, no `src/__init__.py`, no private inputs; **fresh** Python 3.11 venv from `requirements-app.txt` only | Focused suites | **53 run, 51 passed, 2 skipped**: corrected-V2 and propensity rebuilds. Both are expected environment-dependent skips. |
| Same | `unittest discover -s tests` (only app tests present) | 53 run, 2 expected skips, 0 failures |
| Same | Corrected-V2 recovery tests | 15 OK |
| Same | `streamlit run app/streamlit_app.py --server.headless true --server.port 8769` | Started; `/_stcore/health` returned `ok`; no errors in the server log |
| Same | Four pages through AppTest | See A: all render |

**Interpretation of skips.** Every skip is a documented environment dependency: private aggregate rebuild inputs, or Java. None is an application test. The M5-006 note's counts are consistent with this.

## E. Public-release candidate

### Manifest completeness

The public Phase 1 repository `SanSynyster/commercial-retention-analytics` is a single curated commit (`24852b5`, "Initial public release") with 28 files. **All 28 are byte-identical to local HEAD** (git blob comparison). The only difference is `README.md`, which M5-006 modified.

The proposed manifest added to that tree is sufficient to install, test and run the app, and to display all approved aggregates. This was verified with the release-candidate tree in D. The manifest correctly excludes the following:

- raw data
- customer-level outputs
- predictions and selections
- model binaries
- external manifests
- `.local`
- logs
- M5 working notes

A scan of all manifest files found **no absolute or machine-specific paths, credentials, secrets or private keys**. The research documents mention excluded artifacts only through `$LOCAL_DATA_DIR`-style placeholders and repository-relative names.

### P1 — The development `origin` is public, and its history is not release-safe (required before any push)

**Evidence.**

- `origin` is `SanSynyster/commercial-retention-analysis`, visibility **PUBLIC**.
- Its `main` (`485bbfc`) is an ancestor of local HEAD. Local `main` is **24 commits ahead**, covering all Phase 2 M1–M5 work and internal review notes.
- The already-published history contains the raw UCI files (`data/raw/online_retail_II.csv`, 95 MB, and `data/raw/Online Retail.xlsx`), added in `f0a6f11` and removed in `76a30db`.

**Impact.**

- A routine `git push` from this repository would publish the entire Phase 2 development history to a public repository. That history includes internal working notes, which the manifest deliberately excludes.
- The raw-data blobs are already public in that repository's history. The UCI dataset is itself publicly licensed, so the incremental risk is low. However, this conflicts with the release policy of excluding raw transaction data.

**Required action.**

- Do not push the development `main` to `origin`.
- Treat `commercial-retention-analysis` as a public development archive. Whether to make it private, archive it, or leave it as is is an owner decision outside this review. No remote change was made.

### P2 — Publish the frozen research documents byte-identical, not edited (required)

**Evidence.**

- The M5-006 note proposes editing the M1–M4 documents to "remove machine-specific paths and private artifact details". The scan found no machine-specific paths.
- `propensity_summary_v1.json` records and pins the SHA-256 of `M1_009_BASELINE_RESULTS`, `M1_009_BASELINE_PROTOCOL`, `M2_007_BASELINE_PROTOCOL`, `M2_008_BASELINE_RESULTS` and `M2_012_SEQUENTIAL_CALIBRATION_RESULTS`. Its builder refuses to run if they differ.
- The targeting and Customer Overview bundles cite M3-002, M3-003 and the corrected-V2 report by path.

**Impact.** Edited copies would no longer match the hashes that the app displays as its verified sources. The published provenance chain would break, and the bundle could not be rebuilt from the published documents.

**Smallest correction.** Publish those documents unchanged. Put any reader-facing explanation in a separate file (P3).

### P3 — One reader-facing index for excluded material (required)

**Evidence.** The included research documents refer to material that will not be in the release:

- **Research code:**
  - `src/monthly_customer_snapshots.py` and `src/day21_baseline.py` (M2-007).
  - `src/monthly_purchase_calibration.py` and its test (M2-012).
  - `src/monthly_targeting_policies.py` and its test (M3-002, M3-003).
- **Other milestone documents:** M1-007, M1-008, M1-010, M2-001, M2-004, M2-005, M2-009 and M3-001.
- **Reproduction commands** that need external prediction or selection Parquets and manifests.

The only broken hyperlink is `M4-001 → ../../src/monthly_customer_snapshots.py`. The other references are textual.

**Smallest correction.** Add a short `docs/research/README.md` that:

- lists the included documents and what each supports in the app;
- states that the referenced research modules, earlier milestone documents, external aggregates, prediction and selection files and model artifacts are **not included**;
- states that reproduction commands therefore cannot run from the public repository, while the app and its tests do;
- notes that M1-009 RESULTS already contains the M1-010 erratum, the holdout disclosure and the corrected calibration.

Alternatively, include the five research modules and tests, which are code only. Then only the M4-001 link and the excluded-artifact note remain to handle.

### P4 — Finalise manifest wording (required, small)

1. **Root README.** The manifest includes `README.md` only "if the root project README is included". It must be included in its M5-006 version: `app/README.md` links to it, and it introduces the application. Nothing else in the Phase 1 tree needs to change.
2. **Bundle provenance in `app/README.md`.** The rewrite removed the maintainer rebuild sections. For a public reader, add one paragraph covering:
   - the bundles were produced by `src/*_bundle.py` from reviewed aggregates that are not distributed;
   - rebuilding needs those inputs (hence the skipped tests);
   - each bundle's content is pinned, which detects changes but is not a cryptographic authenticity guarantee;
   - the Customer Overview small-cell convention is display-only.

### Destination and release strategy

- **Destination:** the intended public target should be **`SanSynyster/commercial-retention-analytics`**. It is the curated Phase 1 repository, and its tree is identical to the local Phase 1 content. The development `origin` (`commercial-retention-analysis`) is a different, already-public development repository.
- **Approach: a fresh curated commit is appropriate.** Assemble the release from a clean checkout of the public Phase 1 repository by:
  - adding the manifest files;
  - adding the updated `README.md`;
  - adding the P3 index;
  - adding the P4 paragraph.

  Then re-run the focused tests and health check in that tree, as done here, and commit once to the public repository's history. The P1 history issue makes it inappropriate to carry development history across. No lengthy history audit is needed for this approach, because nothing from the development history is published.

## F. Findings summary

### 1. Application closure blockers

None.

### 2. Public-release preparation requirements

| ID | Severity | Requirement | Smallest fix |
| --- | --- | --- | --- |
| P1 | High (release process) | The development `origin` is public, 24 local commits are unpushed, and the published history contains raw data | Do not push the development history. Release via a fresh commit to `commercial-retention-analytics`. The owner decides the development repository's visibility. |
| P2 | Medium | Proposed edits to research documents would break the pinned provenance hashes | Publish M1-009, M2-007, M2-008, M2-012, M3-002, M3-003 and M4-001/002/003 byte-identical |
| P3 | Medium | Research documents reference unreleased code, documents and artifacts; one broken link in M4-001 | Add `docs/research/README.md` listing what is included and excluded, or also ship the five research modules and tests |
| P4 | Low | Manifest leaves the root README conditional; the app README no longer explains bundle provenance or rebuild limits | Include the M5-006 `README.md`; add one provenance paragraph to `app/README.md` |

### 3. Optional improvements

- **O1:** `requirements-app.txt` includes all of `requirements-minimal.txt` (scikit-learn, pyarrow, openpyxl), which the app does not use. A lighter app-only pin set would speed installation.
- **O2:** `test_navigation_registers_four_pages` still checks source text. Render-by-default tests like the probe used here would test routing directly.
- **O3:** Carry-over cosmetic items from M5-005R:
  - "−£" formatting for negative values.
  - Treatment − control wording on the sensitivity axis.
  - A note on the 100% capacity option.

## Commit readiness

**M5-006 can be committed to the local development repository now** as one scoped commit:

- the five modified files;
- the rename;
- the M5-006 note;
- this review.

The commit should stay local. P1 to P4 are preparation steps for the separate public release and do not require further application changes.
