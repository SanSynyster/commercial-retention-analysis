# COMMERCIAL-DS-001 — Architecture: Current, Target and Migration

Part of the [recovery index](README.md). Definitions come from the [data contracts](COMMERCIAL_DS_001_DATA_CONTRACTS.md). Sequencing comes from the [roadmap](COMMERCIAL_DS_001_ROADMAP.md).

---

## 1. Current architecture [VERIFIED]

This section summarizes the repository architecture recorded in the public research documentation. See the [documentation index](../../docs/index.md) for current guides and the [reproducibility guide](../../docs/REPRODUCIBILITY.md) for the validated execution boundary. Summary:

| Layer | Location | Status | Problem |
| --- | --- | --- | --- |
| Loading / cleaning | `src/data_loading.py`, `src/cleaning.py` (+ duplicate in notebook 01) | Verified, reproducible | Logic duplicated; no V2 overlap dedupe |
| Customer metrics | `src/customer_metrics.py` (+ notebooks 02/04/05/06, `sql/`, dbt, Spark) | Verified (pandas, dbt) | 5 implementations |
| Lapse model | `src/churn_prediction.py` + notebook 06 | Reproducible | Two diverging implementations; test-set selection; stale scoring |
| Segmentation / CRM priority | notebooks 04/07; dbt `mart_customer_segments` | Unverified | Two incompatible schemes |
| Propensity | notebook 05 only | Unverified | No signal (AUC 0.52) |
| Incrementality simulation | notebook 03 only | Unverified | Assumption-driven |
| Experiment marts | dbt `int_second_purchase_experiment_customers`, `mart_second_purchase_experiment_*`, `mart_experiment_eligibility` | Built | A/A without labelling; censoring; two hash rules |
| Spark / Databricks | `src/spark_pipeline.py`, `src/run_*spark*`, `databricks/` | Never executed | No JDK; bundle packaging doubtful |
| Standalone SQL | `sql/*.sql` | Orphaned | Legacy path |
| Reports / README | `reports/`, `README.md` | Hand-written | Numbers mixed across runs |
| Tests / CI | `tests/test_pipeline.py`, `.github/workflows/tests.yml` | 13/14 pass locally | Unpinned deps; decision layers untested |

---

## 2. Target architecture [PROPOSED]

### 2.1 Principles
1. **One reference implementation per definition.** `src/` (pandas) is the reference; dbt and Spark are parity mirrors.
2. **Extend, don't relocate.** Existing modules stay at their paths. New modules are added beside them. Moves happen only in a dedicated, reviewed migration step with import shims.
3. **No new framework.** There is no orchestrator, feature store or MLflow. `make` plus plain Python CLIs plus JSON run manifests are sufficient for this scale.
4. **Studies consume, never redefine.** Research code imports foundation functions and cannot re-implement orders, customers or snapshots.
5. **Results are data.** Every reported number is written to the results registry and rendered into documents.

### 2.2 Proposed directory structure (to be created incrementally, not now)

```text
src/                                  # existing package, extended in place
├── config.py                         # existing; + canonical dataset "v2c" (V2 deduplicated)
├── data_loading.py                   # existing
├── cleaning.py                       # existing; + C-DQ-1 dedupe, line_type, refund fields (Phase 3)
├── customer_metrics.py               # existing; becomes foundation for orders/customers/cohorts
├── validation.py                     # existing; + contract checks
├── foundation/                       # NEW (Phase 3)
│   ├── contracts.py                  #   loads contracts/business_definitions.yml; constants & tolerances
│   ├── snapshots.py                  #   point-in-time customer snapshots + label maturity
│   └── manifest.py                   #   run manifest write/read (git SHA, data hash, params)
├── features/                         # NEW (Phase 5–7): reusable feature builders over snapshots
├── stats/                            # NEW (Phase 4): bootstrap, KM, proportion CIs, multiplicity
├── models/                           # NEW (Phase 6–7)
│   ├── lapse.py                      #   successor to churn_prediction (which stays as baseline B0)
│   ├── value.py                      #   fixed-horizon revenue, BG/NBD if adopted
│   └── evaluation.py                 #   temporal splits, purging, holdout guard, metrics
├── experiments/                      # NEW (Phase 8): eligibility, assignment, readout, A/A, synthetic
├── engineering/                      # NEW (Phase 9): parity runners, benchmarks, synthetic scale-up
├── reporting/                        # NEW (Phase 10): results registry → markdown tables, BI exports
├── churn_prediction.py               # existing — frozen as historical baseline B0
├── spark_pipeline.py                 # existing — becomes a parity mirror
└── run_*.py                          # existing CLIs, kept

contracts/business_definitions.yml    # NEW (Phase 2): machine-readable contract, versioned
research/                             # NEW (Phase 4+): one folder per study
├── r1_commercial/  r2_segmentation/  r3_lapse/  r4_value_forecasting/  r5_experimentation/  r6_engineering/
│   ├── PREREGISTRATION.md            #   questions, hypotheses, baselines, metrics, holdout (before results)
│   ├── REPORT.md                     #   generated tables + written interpretation
│   └── notebooks/                    #   presentation-only; import src
artifacts/runs/<run_id>/              # NEW (gitignored): outputs + manifest.json
tests/
├── test_pipeline.py                  # existing, kept
├── contracts/                        # NEW: contract tests on synthetic fixtures
├── parity/                           # NEW: pandas↔dbt (↔Spark when JDK present)
└── research/                         # NEW: leakage/purge/holdout guards, results-consistency check
dbt/                                  # existing; marts re-pointed to canonical parquet; experiment marts reclassified
notebooks/, sql/, reports/, data/processed/  # existing — preserved; later archived per §4
```

### 2.3 Module ownership and dependency rules

| Module | Owns | May import | Must not |
| --- | --- | --- | --- |
| `data_loading`, `cleaning` | raw → lines | pandas | compute customer metrics |
| `customer_metrics`, `foundation.snapshots` | orders, customers, cohorts, snapshots | cleaning, contracts | fit models |
| `features` | feature functions over snapshots | foundation | read raw files |
| `stats` | statistical utilities | numpy/scipy | business definitions |
| `models.*` | training/evaluation | features, stats, foundation | touch the holdout outside `evaluation.final_holdout()` |
| `experiments` | eligibility, assignment, readout, simulation | foundation, stats | label any output `causal` without an exposure table |
| `engineering` | Spark/dbt parity, benchmarks | foundation (as oracle) | redefine contracts |
| `reporting` | registry, rendered tables, BI exports | manifests | compute new metrics |

Dependency direction: `contracts → cleaning → foundation → features/stats → models/experiments → reporting`. There are no cycles, and studies never import each other's internals; they exchange datasets.

### 2.4 Role of each technology

| Tool | Purpose | Verification | Keep? |
| --- | --- | --- | --- |
| pandas | Reference implementation | Unit + contract tests | Yes |
| scikit-learn | Models | Protocol-driven evaluation | Yes |
| DuckDB + dbt | SQL modelling demonstration; analytical marts; second implementation | Parity tests vs pandas; dbt tests | Yes |
| PySpark | Distributed-processing study (R6) | Parity + benchmark, requires JDK | Yes, as a study |
| Databricks bundle | Deployment design | `databricks bundle validate` + a real run | Optional; labelled unverified |
| Jupyter | Presentation | Executes headless in CI (Phase 10) | Yes, logic-free |
| Tableau | BI presentation | Exports traceable to registry | Yes (external) |
| statsmodels / lifetimes / PyMC-Marketing / SHAP | Forecasting / CLV / explainability | — | **Dependency decisions** (P-10); not installed in this phase |
| AWS/Azure docs | Design narrative | — | Keep, labelled design-only |

---

## 3. Migration strategy

| Step | What | Safety mechanism |
| --- | --- | --- |
| M1 | Write `contracts/business_definitions.yml` mirroring the approved contract doc | Docs-only diff; review |
| M2 | Add a canonical dataset `v2c` in `src/config.py` and the `C-DQ-1` dedupe in cleaning behind the dataset choice. V1/V2 outputs remain reproducible byte-for-byte | Golden-output test: `make pipeline-v1` still reproduces current V1 artifacts until the contract changes are deliberately applied |
| M3 | Add `foundation/snapshots.py` and `manifest.py`; churn module untouched | Point-in-time tests; B0 reproduces stored metrics |
| M4 | Notebooks 02/04–07 switched to import `src` (copies kept in `notebooks/legacy/` once archiving is approved) | Output diff report per notebook |
| M5 | dbt re-pointed to the canonical parquet via var; segments/experiment marts reclassified or rebuilt to contract | Parity suite |
| M6 | Spark mirror updated to the contract; parity run when JDK available | Parity suite (skips with explicit reason otherwise) |
| M7 | Reporting generates README/report tables; consistency test fails CI on drift | Results-consistency test |

### Archival proposal (not executed; requires approval P-11)

| Component | Proposed fate | Why | When |
| --- | --- | --- | --- |
| `sql/*.sql` | `archive/sql_v0/` with a README | Superseded by dbt; legacy path | After dbt parity passes |
| notebooks 01–02 logic | Keep the notebooks; strip logic in favour of imports; originals in `archive/notebooks_v0/` | Duplication | Phase 3 |
| notebooks 05–07 | Keep as historical; successors in `research/` | Methodological defects | After R2/R3 gates |
| `data/processed/*.csv` (root legacy outputs) | Move to `archive/outputs_v0/` with a manifest describing provenance | Ambiguous provenance | Phase 3 |
| dbt experiment marts | Reclassify as `aa_frame_*` or rebuild per `C-EXP` | Misleading decision flags | Phase 8 |
| `reports/*.md` | Keep; add a banner "historical, superseded by research/…" | Hand-copied numbers | Phase 10 |

Nothing is deleted. Archive moves are reversible `git mv` operations in dedicated commits.
