# COMMERCIAL-DS-001 — Roadmap, Phases and Review Gates

Part of the [recovery index](README.md). Each phase implements parts of the [architecture](COMMERCIAL_DS_001_ARCHITECTURE.md) under the [evaluation protocol](COMMERCIAL_DS_001_EVALUATION_PROTOCOL.md). Risks referenced as `R-nn` are in the [risk register](COMMERCIAL_DS_001_RISK_REGISTER.md), and decisions as `P-nn` in the [decision log](COMMERCIAL_DS_001_DECISION_LOG.md).

**Authorisation rule:** completing a phase does **not** authorise the next. Each phase starts only after the owner records approval of the previous gate in the decision log.

**Command status:** commands marked *(exists)* run today. Commands marked *(proposed)* are targets to be created in the phase that lists them.

---

## Recommended order

| # | Phase | Change from the requested order | Reason |
| --- | --- | --- | --- |
| 1 | Repository recovery & specification | — | This document set |
| 2 | Data contracts & canonical definitions | — | Everything depends on these |
| 3 | Core engineering consolidation **+ pandas↔dbt foundation parity** | dbt parity for *foundation* datasets moved here from Phase 9 | Parity is the cheapest guard against re-divergence and needs no JDK |
| 4 | Commercial analytics research (R1) | — | Produces the distributions that R2–R5 depend on |
| 5 | Predictive modelling research (R3) | **Swapped with segmentation** | R3 has the clearest success criterion and corrects the most visible existing claim. R2's usefulness test reuses R3's snapshot/label machinery |
| 6 | Segmentation research (R2) | Swapped | See above. The canonical `C-SEG` is decided here, before CRM priority is rebuilt |
| 7 | Forecasting & customer value (R4) | — | Reuses snapshots and R1 series |
| 8 | Experimentation framework (R5) | **May run in parallel with 5–7** once Phase 3 passes | Depends only on foundation + `C-ACQ`/`C-EXP` |
| 9 | Spark engineering study & Databricks readiness (R6) | Narrowed to Spark/benchmarks | Foundation parity was done in Phase 3. Spark needs a JDK |
| 10 | BI, reporting & research finalisation | — | Consumes the results registry |

If the owner prefers the original order (segmentation before prediction), the only cost is that R2's usefulness test must wait for the snapshot labels from Phase 3. That is acceptable.

---

## Phase 1 — Repository recovery and specification
| Field | Content |
| --- | --- |
| Objective | Establish verified understanding and an approved programme |
| Prerequisites | Technical handover |
| Scope | Documentation only (`docs/recovery/`) |
| Deliverables | The 10 recovery documents |
| Verification | `.venv/bin/python -m src.docs_validation` *(exists)*; `.venv/bin/python -m unittest discover -s tests` *(exists)*; `git status` shows only new docs |
| Acceptance | Docs exist, links valid, tests unchanged (13 pass / 1 skip), no tracked file modified |
| Failure | Any tracked file modified; broken links; contradictions with the audit |
| Independent review | Owner + external advisor read the executive blueprint and decision log |
| Rollback | Delete `docs/recovery/` (untracked) |

## Phase 2 — Data contracts and canonical definitions
| Field | Content |
| --- | --- |
| Objective | Approve and encode the business-definition contract |
| Prerequisites | Phase 1 approved; decisions P-01, P-01b, P-09 answered |
| Scope | `contracts/business_definitions.yml`; exploratory checks for Q-C1…Q-C7 in a scratch directory; **no change to executable definitions yet** |
| Deliverables | Approved contract YAML + doc; V2 overlap dedupe specification validated in scratch; written answers to the contract questions |
| Verification | Scratch script shows that deduped V2 for 2010-12-01…09 reconciles to V1 (rows and revenue within tolerance), and that the 2011 period reconciles to V1 (the known 1-row/GBP 18 difference explained) |
| Acceptance | All `Q-C*` resolved or explicitly deferred; owner sign-off |
| Failure | Dedupe cannot be reconciled → V2 canonical status reconsidered (fall back to V1 with acquisition analyses marked NOT SUPPORTED) |
| Review | Independent check of the reconciliation evidence |
| Rollback | Contract is versioned; revert the YAML |

## Phase 3 — Core engineering consolidation (+ foundation parity)
| Field | Content |
| --- | --- |
| Objective | Single reference implementation, point-in-time snapshots, provenance, pandas↔dbt parity |
| Prerequisites | Phase 2 approved |
| Scope | Migration steps M1–M5 (architecture §3); pinned CI dependencies (P-12); notebooks 01–02 import `src` |
| Deliverables | `v2c` dataset; `foundation/snapshots.py`, `foundation/manifest.py`; contract tests; parity tests; golden V1 reproduction test |
| Verification | `make test` *(exists)*; `make pipeline-v1` reproduces the stored V1 audit byte-for-byte *(exists)*; `make foundation DATASET=v2c` *(proposed)*; `make parity-dbt` *(proposed)*; truncation (point-in-time) tests *(proposed)* |
| Acceptance | All tests green; parity exact or within tolerance; every output has a manifest; B0 lapse model reproduces stored V1 metrics |
| Failure | Any unexplained parity difference; golden V1 drift without an approved contract change |
| Review | Code review of the diff against "as-is definitions" (data contracts §1) |
| Rollback | Each migration step is its own commit; revert per step |

## Phase 4 — Commercial analytics research (R1)
| Field | Content |
| --- | --- |
| Objective | Answer R1-Q1…Q7 with uncertainty |
| Prerequisites | Phase 3 passed |
| Scope | `research/r1_commercial/`; `src/stats/` utilities |
| Deliverables | Pre-registration; report; results registry entries; V1-vs-canonical reconciliation |
| Verification | `make research-r1` *(proposed)* regenerates the report tables; results-consistency test |
| Acceptance | Every headline number has a CI and an evidence class; no causal wording |
| Failure | Numbers not reproducible from the manifest; causal claims |
| Review | Independent reviewer checks 5 random numbers against the registry |
| Rollback | Results are versioned by run ID; discard the run |

## Phase 5 — Predictive modelling research (R3)
| Field | Content |
| --- | --- |
| Objective | Determine whether ML beats simple baselines for 90-day lapse, honestly |
| Prerequisites | Phases 3–4 passed; R3 pre-registration approved before any model is fit |
| Scope | `src/models/`, `research/r3_lapse/`; B0 frozen |
| Deliverables | Lapse-definition analysis; baseline results; tuned models; one-shot holdout; calibration; error analysis; simulated targeting economics; model card |
| Verification | `make research-r3` *(proposed)*; holdout access count = 1 per frozen model; purge test |
| Acceptance | Report states the model-vs-baseline result with a paired CI, **whatever the outcome** |
| Failure | Holdout touched during development; selection on test; missing baseline |
| Review | Independent re-run from a clean checkout reproduces the holdout metrics |
| Rollback | Discard the run; the pre-registration remains |

## Phase 6 — Segmentation research (R2)
| Field | Content |
| --- | --- |
| Objective | Select the canonical `C-SEG` scheme with a pre-declared usefulness test |
| Prerequisites | Phase 5 snapshot/label machinery; R2 pre-registration |
| Deliverables | RFM vs clustering comparison; stability report; canonical segment definition; legacy schemes documented as historical |
| Verification | `make research-r2` *(proposed)*; bootstrap ARI; usefulness test |
| Acceptance | One canonical scheme, chosen by the pre-declared rule (RFM is an acceptable winner) |
| Failure | Scheme chosen by visual appeal; unstable clusters adopted |
| Review | Interpretability review by someone outside the study |
| Rollback | Interim RFM scheme remains canonical |

## Phase 7 — Forecasting and customer value (R4)
| Field | Content |
| --- | --- |
| Objective | Fixed-horizon customer revenue and aggregate weekly forecasts vs baselines |
| Prerequisites | Phases 3–4; dependency decision P-10 (statsmodels / CLV library) |
| Deliverables | Value glossary; customer-level comparison; aggregate backtest with interval coverage; explicit non-estimates |
| Verification | `make research-r4` *(proposed)*; rolling-origin backtests |
| Acceptance | MASE vs seasonal-naive reported with interpretation; no unbounded-CLV claims |
| Failure | Models evaluated on the training period; intervals without coverage checks |
| Review | Independent reproduction |
| Rollback | Discard the run |

## Phase 8 — Experimentation framework (R5)
| Field | Content |
| --- | --- |
| Objective | A validated design/readout framework; A/A and synthetic recovery |
| Prerequisites | Phase 3 (can run in parallel with 5–7) |
| Scope | `src/experiments/`; reclassify the dbt experiment marts (P-04) |
| Deliverables | Pre-registration template; power/MDE study; A/A report; synthetic recovery report; exposure-table schema; economics template |
| Verification | `make research-r5` *(proposed)*; A/A false-positive rate within the binomial CI; synthetic CI coverage ≈ nominal |
| Acceptance | Every output labelled with its evidence class; no "scale" decisions on non-causal evidence |
| Failure | Any output implying a real treatment effect |
| Review | Statistical review of the simulation design |
| Rollback | Legacy marts remain (reclassified) |

## Phase 9 — Spark engineering study and Databricks readiness (R6)
| Field | Content |
| --- | --- |
| Objective | Spark parity and a defensible benchmark; Databricks readiness checklist |
| Prerequisites | Owner installs a JDK 17 (P-06); Phase 3 contracts |
| Deliverables | Spark parity tests; benchmark report (×1/×10/×50 synthetic scale-ups); plan analysis; Databricks checklist |
| Verification | `make spark-v1` *(exists; currently fails without Java)*; `make parity-spark` *(proposed)*; `make bench` *(proposed)*; `make databricks-validate` *(exists; CLI absent)* |
| Acceptance | Parity passes; benchmark methodology documented; Databricks status stated accurately (verified, or "unverified" with reasons) |
| Failure | Parity differences; benchmark claims without repetitions/IQR |
| Review | Independent re-run of the benchmarks |
| Rollback | Spark tests skip with an explicit reason; status reverts to "unverified" |

## Phase 10 — BI, reporting and research finalisation
| Field | Content |
| --- | --- |
| Objective | Regenerated README/reports, BI exports, skills ledger |
| Prerequisites | All research phases that are to be presented have passed their gates |
| Deliverables | Generated README tables; five-minute summary; per-study reports; BI exports from the registry; skills ledger; legacy reports bannered as superseded; archive moves (P-11) |
| Verification | Results-consistency CI check; notebooks execute headless; docs-link check; clean-checkout reproduction |
| Acceptance | Research quality standard (executive blueprint §8) met |
| Failure | Any hand-typed number; any untested claim labelled as working |
| Review | External reviewer performs the five-minute and deep review paths |
| Rollback | Previous README is retained in history |

---

## Gate record template (for the decision log)

```text
Gate: Phase N
Date:
Evidence reviewed (run IDs, test output):
Acceptance criteria met: yes/no (list)
Open issues carried forward:
Approved by:
Next phase authorised: yes/no
```
