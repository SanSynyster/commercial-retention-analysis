# COMMERCIAL-DS-001 — Agent Handover

Self-contained context for future ChatGPT, Claude Code and Codex sessions. Read this document first, then the [decision log](COMMERCIAL_DS_001_DECISION_LOG.md) (source of truth for decisions), then the documents relevant to your task via the [recovery index](README.md).

## 1. Operating rules for agents

1. **Check the decision log before acting.** Do not implement any `P-nn` proposal until the owner has moved it to "Confirmed". Do not start a roadmap phase until its predecessor gate is approved in the decision log.
2. **Do not redefine business logic.** Orders, customers, snapshots, lapse, segments, cohorts and assignment are defined in the [data contracts](COMMERCIAL_DS_001_DATA_CONTRACTS.md). Implement them in `src/` and nowhere else; dbt and Spark only mirror `src/`.
3. **Do not touch the holdout** except through the designated final-evaluation path described in the [evaluation protocol](COMMERCIAL_DS_001_EVALUATION_PROTOCOL.md) §5.
4. **Label evidence.** Every reported number carries an evidence class: Observed, Inferred, Model-based, Simulated or Assumed.
5. **Never present** historical splits as A/B tests, simulated uplift as findings, Spark or Databricks as verified (unless they actually ran), or a model that lost to its baseline as successful.
6. **Never hand-type results** into README or report files once the results registry exists. Until then, cite the run and the file you took each number from.
7. **No destructive Git or data operations** without explicit owner approval. This includes deleting, overwriting `data/processed/`, rewriting history and force-pushing. Write experimental outputs to a scratch directory or pass `--processed-dir`.
8. **Run `make test` and `.venv/bin/python -m src.docs_validation`** before declaring any phase complete. The link checker scans every `.md` file in the repo.

## 2. Project in one paragraph

This is a single-author Commercial Data Science research project on the public UCI *Online Retail* data. V1 is `data/raw/Online Retail.xlsx` (2010-12-01 → 2011-12-09, 541,909 lines). V2 is `data/raw/online_retail_II.csv` (2009-12-01 → 2011-12-09, 1,067,371 lines). The data is a UK gift wholesaler with many trade customers, and it has no marketing exposure, margin, channel or demographic data. The repository currently contains:
- a verified pandas pipeline (`src/`) for cleaning and customer metrics;
- a reproducible but methodologically limited lapse model (`src/churn_prediction.py`);
- notebooks 01–09 that duplicate and extend the logic;
- dbt/DuckDB marts, including invalid "experiment" marts;
- PySpark and Databricks scaffolding that has never been executed;
- many docs and reports with hand-copied numbers.

The owner has redirected the project into six research workstreams (R1–R6). Its credibility rests on reproducibility, baselines, uncertainty and honest negative findings.

## 3. State at handover (2026-10-30)

| Item | State |
| --- | --- |
| Branch / commit | `main` @ `1b293c2`, one commit ahead of `origin/main` (`de883bb`); not pushed |
| Untracked | `PROJECT_TECHNICAL_HANDOVER.md`, `docs/recovery/` (this phase), `.vscode/` (editor-created) |
| Tests | `make test` → 14 run, 13 pass, 1 skipped (Spark: no Java) |
| Reproducibility | `make pipeline-v1` and `make churn-v1` reproduce the stored V1 outputs byte-for-byte (verified with `--processed-dir` pointing to a scratch dir) |
| dbt | Last logged `dbt build` 2026-06-02: PASS=89. Warehouse `data/warehouse/commercial_retention.duckdb` |
| Environment | Python 3.11.14 `.venv`; pandas 3.0.2; scikit-learn 1.8.0; DuckDB 1.5.2; dbt-core 1.11.11; PySpark 4.1.2; **no JDK; no Databricks CLI** |
| Phase | Phase 1 (specification) complete, pending owner review. **No later phase authorised.** |

## 4. Facts that must shape every design

| Fact | Value | Implication |
| --- | --- | --- |
| V2 duplicates 1–9 Dec 2010 | V2 has 2× V1's rows and revenue in that window (22,844 exact duplicates) | Dedupe before using V2 (`C-DQ-1`); V2 reports in `reports/` are inflated |
| V1 left-censoring | 62.8% of V1 customers bought before V1 starts | V1 cannot support acquisition, cohort or first-purchase analysis |
| Inter-purchase interval (V2) | median 24 days, p75 61, p90 134 | Informs lapse horizon choice |
| Seasonality | Sep–Nov peaks in both years; only about 2 cycles | Weak seasonal estimation; the Q4 holdout is a distribution shift |
| Lapse model B0 (V1) | ROC-AUC 0.759, PR-AUC 0.692, base rate 0.473 | No baseline comparison yet; selected on the test set |
| Propensity model (V1) | ROC-AUC 0.520 | Negative finding; retire from scoring |
| Experiment marts | A/A on untreated customers; 905/3,591 censored; two hash rules disagree for 449 | Reclassify (P-04) |

## 5. Where things are

| Need | File |
| --- | --- |
| Public data and repository context | [data provenance](../../docs/DATA_PROVENANCE.md) and [documentation index](../../docs/index.md) |
| Mission, scope, definition of done | [executive blueprint](COMMERCIAL_DS_001_EXECUTIVE_BLUEPRINT.md) |
| Study specifications | [research programme](COMMERCIAL_DS_001_RESEARCH_PROGRAMME.md) |
| Definitions, grains, keys | [data contracts](COMMERCIAL_DS_001_DATA_CONTRACTS.md) |
| Module layout and migration | [architecture](COMMERCIAL_DS_001_ARCHITECTURE.md) |
| Splits, baselines, CIs, holdout | [evaluation protocol](COMMERCIAL_DS_001_EVALUATION_PROTOCOL.md) |
| Phases and gates | [roadmap](COMMERCIAL_DS_001_ROADMAP.md) |
| Known problems | [risk register](COMMERCIAL_DS_001_RISK_REGISTER.md) |
| Code entry points | `src/run_pipeline.py`, `src/run_churn_prediction.py`, `src/run_spark_pipeline.py`, `Makefile`, `dbt_project.yml` |

## 6. First tasks once Phase 2 is authorised

1. Resolve `Q-C1`…`Q-C7` in a scratch directory, starting with V2 overlap reconciliation against V1.
2. Draft `contracts/business_definitions.yml` from the approved contract document.
3. Record the outcomes and the owner's sign-off in the decision log.

Do **not** change `src/` definitions in Phase 2.

## 7. Safe command patterns

```bash
# tests and docs (non-destructive)
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests
.venv/bin/python -m src.docs_validation
# reproduce without overwriting repo artifacts
.venv/bin/python -m src.run_pipeline --dataset v1 --processed-dir "$SCRATCH/v1"
.venv/bin/python -m src.run_churn_prediction --dataset v1 --processed-dir "$SCRATCH/v1"
# inspect the warehouse read-only
.venv/bin/python -c "import duckdb; c=duckdb.connect('data/warehouse/commercial_retention.duckdb', read_only=True); print(c.sql('show tables'))"
```

Avoid `make dbt-build`, notebook execution and `make pipeline-*` without `--processed-dir` unless the current phase authorises overwriting artifacts.
