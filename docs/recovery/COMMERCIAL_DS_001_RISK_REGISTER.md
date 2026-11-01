# COMMERCIAL-DS-001 — Risk Register

Part of the [recovery index](README.md). The `D-nn` identifiers are retained as historical audit labels; the risk descriptions below contain their relevant context. Current decisions are recorded in the [decision log](COMMERCIAL_DS_001_DECISION_LOG.md). Phases refer to the [roadmap](COMMERCIAL_DS_001_ROADMAP.md).

**Severity:** High = invalidates published claims or blocks the programme. Medium = degrades correctness or credibility. Low = hygiene.
**Status:** all risks are **Open** at the end of Phase 1 unless stated otherwise.

## 1. Existing defects (verified)

| ID | Risk | Evidence | Severity | Mitigation | Phase |
| --- | --- | --- | --- | --- | --- |
| R-01 | Reported numbers hand-copied and mixed across runs (D-1) | README lapse metrics combine the `src` and notebook runs | High | Results registry; generated tables; CI consistency check | 3, 10 |
| R-02 | Notebook 06 and `src/churn_prediction.py` overwrite the same files with different logic (D-2) | Risk bands High 1,303 vs 664; file timestamps | High | Freeze `src` as B0; notebooks import `src`; separate output names per model ID | 3 |
| R-03 | Test-set model selection (D-3) | `src/churn_prediction.py:307-311`; notebooks 05/06 | High | Rolling-origin validation; protected holdout | 5 |
| R-04 | CRM scoring on a stale, labelled snapshot; 1,021 unscored customers filled with 0 (D-4) | Notebook 07; `crm_customer_priority_scores.csv` | High | Separate current-anchor scoring dataset; no zero-fill (explicit "unscored" handling) | 5 |
| R-05 | Snapshot anchors at 08:26 (D-5) | `lapse_risk_scores.csv` | Low | `C-TIME-3` normalisation | 3 |
| R-06 | Two incompatible segmentation/priority schemes (D-6) | dbt P1=40 vs notebook P1=22 | High | Single `C-SEG` via R2 | 3 (interim), 6 |
| R-07 | Experiment marts report A/A noise as lift with decision flags (D-7) | `mart_second_purchase_experiment_lift` | High | Reclassify; evidence-class field; no decisions for non-causal evidence | 8 |
| R-08 | Right-censored experiment windows (D-8) | 905 / 3,591 customers lack 90 days of observation | High | `fully_observed` filter (`C-EXP`) | 8 |
| R-09 | Two assignment rules disagreeing for 449 customers (D-9) | DuckDB cross-tab | Medium | One assignment function | 8 |
| R-10 | Databricks bundle likely undeployable (D-10) | Bundle root/sync; no data upload; no libraries | Medium | Readiness checklist; label "unverified" | 9 |
| R-11 | Propensity model at chance level, described as useful (D-11) | AUC 0.520 (V1) | High (credibility) | Report as a negative finding; retire from priority scoring | 5/10 |
| R-12 | Left-censoring treated as acquisition (D-12) | Dec-2010 cohort 885 | High | `C-ACQ` with V2 burn-in (see R-19) | 2 |
| R-13 | Orphaned `sql/` reading a legacy path (D-13) | grep | Low | Archive after dbt parity | 10 |
| R-14 | Duplicates and non-product codes in customer revenue (D-14) | ≈2% of revenue | Medium | `C-DQ-2`, `C-DQ-3` | 2 |
| R-15 | Unpinned CI dependencies (D-15) | `requirements-minimal.txt` | Medium | Lock file for CI (P-12) | 3 |
| R-16 | Unpushed commit; misleading commit messages (D-16) | `git status -sb` ahead 1 | Low | Owner pushes; commit-message convention | — |
| R-17 | Unseen calendar categories in holdout (D-17) | `snapshot_month` | Low | L9 rule | 5 |

## 2. New findings from Phase 1 (verified)

| ID | Risk | Evidence | Severity | Mitigation | Phase |
| --- | --- | --- | --- | --- | --- |
| **R-18** | **V2 double-counts 1–9 Dec 2010.** Every V2 result covering that window is inflated, including `reports/v2_year_over_year_comparison.md` "current year" identifiable revenue (GBP 9.22M vs V1 8.91M) and `reports/dataset_comparison_summary.md` | V2 window 45,046 rows / GBP 623,756 vs V1 22,523 / GBP 311,878; 22,844 exact duplicates | **High** | `C-DQ-1` dedupe, validated against V1; legacy V2 reports bannered | 2–3 |
| **R-19** | **V1 left-censoring is pervasive.** 62.8% of V1 customers bought before V1 starts, including 55% of June-2011 "new" customers. Second-purchase rates, the cohort curve, the propensity model and experiment eligibility in V1 all treat existing customers as new | Cross-reference of V1 first-seen dates with V2 history | **High** | V2 canonical + `C-ACQ` burn-in; V1 acquisition analyses marked legacy | 2 |
| R-20 | `.vscode/` directory appeared (untracked, created 2026-10-30 18:04 by an editor, not by this phase) | `git status` | Low | Owner decides: `.gitignore` or commit | — |
| R-21 | **Resolved in the RELEASE-007A candidate.** The original recovery documents linked to an excluded, untracked handover, causing the all-Markdown link check to fail | `src/docs_validation.py`; candidate link check now passes | Medium (historical) | Replaced the four links with existing public documentation or concise public context; the private handover remains excluded | Complete |

## 3. Methodological risks

| ID | Risk | Severity | Mitigation |
| --- | --- | --- | --- |
| R-30 | Only about 2 seasonal cycles; the Q4 holdout is distributionally different from training | High | Report as a shift; seasonal-naive baselines; per-month error analysis |
| R-31 | Few independent time periods: 16 lapse anchors, few 180-day anchors | Medium | Customer-clustered bootstrap; modest claims |
| R-32 | Heavy-tailed revenue dominated by wholesale buyers | Medium | Log/robust metrics; tail-sensitivity analysis; report with and without the top 1% |
| R-33 | Clustering produces artefacts mistaken for personas | Medium | Pre-declared usefulness and stability tests |
| R-34 | Simulation outputs mistaken for evidence | High | Evidence classes on every output; recommendations cannot rest on simulation alone |
| R-35 | Garden of forking paths (many lapse definitions, models, segments) | Medium | Pre-registration; multiplicity control; deviations section |
| R-36 | Unknown B2B/B2C mix limits external validity of "e-commerce CRM" conclusions | Medium | State explicitly; avoid DTC framing unless justified |
| R-37 | No margin data: economics depend wholly on assumptions | Medium | Sensitivity ranges; "Assumed" labels |

## 4. Infrastructure and process risks

| ID | Risk | Severity | Mitigation |
| --- | --- | --- | --- |
| R-40 | No Java runtime locally: Spark cannot run | High (for R6) | Owner installs JDK 17, or R6 Spark items stay "unverified" |
| R-41 | No Databricks CLI or workspace | Medium | Databricks stays optional |
| R-42 | New libraries needed (statsmodels, a CLV library, SHAP) are not installed | Medium | Dependency decision P-10 before Phases 5/7 |
| R-43 | Scope creep: re-adding tools for coverage | High | Each tool needs a purpose and verification (architecture §2.4) |
| R-44 | Consolidation silently changes legacy numbers | High | Golden V1 reproduction test; contract changes as explicit, reviewed diffs |
| R-45 | Agent sessions lose context and re-diverge | Medium | [Agent handover](COMMERCIAL_DS_001_AGENT_HANDOVER.md); decision log as source of truth |
| R-46 | 1.3 GB `.venv` and 42 MB `.git` (raw data in history) | Low | Optional history rewrite only with explicit approval (destructive) |
