# COMMERCIAL_DS_P3_009D — Causal Evidence & Experimentation Integration

**Status:** independently reviewed and accepted (PASS with no material defects); no causal experiment rerun and no model refit. Final presentation clarifications identify the selected arms in secondary comparisons and distinguish development from locked-test policy-value populations. No estimates or bundle values changed.
**Base:** P3-009C commit `e7365ba9617fdea8a8ed0160ca04252efea505d3`.

## Implemented functionality

Added **Causal Evidence & Experimentation** to the existing Streamlit navigation while retaining the six prior pages. The page presents the three-arm randomized design and frozen train/development/test sizes, then separates the confirmatory primary locked-test result, Holm-adjusted secondary randomized visit comparisons, and exploratory 20% development policy-value comparisons. Analysts can select a secondary visit contrast and a development model family. Confidence intervals are shown with zero references. The page also summarizes the distinction between average assignment effect, individual response ranking, and policy value.

The page is a research interface. It does not expose individual CATE scores, execute a campaign, estimate unsupported budgets, or apply Hillstrom findings to UCI customer segments.

## Source provenance and bundle

`src/causal_evidence_bundle.py` uses only these fixed report-cited aggregate files and the committed P3-008D synthesis report:

| Source | Exact relative path | Raw SHA-256 |
|---|---|---|
| P3-008A audit/design aggregate | `source_data/hillstrom/p3_008a_outputs/hillstrom_audit_aggregate_private.json` | `58a33907a118990ae12f91f7d560527d84034d06dfb581f02461065e5f756c70` |
| P3-008B development aggregate | `source_data/hillstrom/p3_008b_outputs/hillstrom_uplift_aggregate_private.json` | `baee1318cd1e21c8b51fed04340184dbf68c4cc7e9054bc1a7a87e27b58ff362` |
| P3-008C locked-test aggregate | `source_data/hillstrom/p3_008c_outputs/hillstrom_locked_test_aggregate_private.json` | `ac22045cbb94379295cbd5950ab017608d2d10d3bde5575c854ed8cc2c7fb3ac` |
| P3-008D synthesis report | `docs/research/COMMERCIAL_DS_P3_008D_CAUSAL_RESEARCH_SYNTHESIS.md` | `af639847c792ccfcf8850e0f91b8cdce4aa99ba29fb6ad52fa88799e2fca9ba1` |

The P3-008B source is specifically `p3_008b_outputs`; the different `p3_008b_repro_outputs` aggregate was inspected and not selected. P3-008A's frozen split digest is `0f18d512272cee14da65940cb52a9458eb35e357489e745339ac88cd9a9a00ce`; the source dataset digest is `0e5893329d8b93cefecc571777672028290ab69865718020c78c7284f291aece`. The builder verifies the source aggregates' embedded dataset/split hashes and pins their exact raw JSON bytes. The P3-008D report hash pins the traceable interpretive source.

The deterministic projection includes only arm counts, partition sizes, aggregate arm outcomes, primary/secondary estimates and the 20% development comparison table. It excludes the raw CSV, P3-008A row-split assignment CSV, P3-008B development-prediction Parquet, P3-008C test-row Parquet, their private artifact references, and absolute paths. Bundle schema/content integrity and exact provenance are validated. Bundle content SHA-256: `720a35d13c1de8d5f6db62bacf64bf7945b072a606c3b5ec19d5ea5015c2da4b`.

## Evidence displayed

### Design and population

The MineThatData Hillstrom experiment has 64,000 observations randomized among Men's email (21,307), Women's email (21,387), and no email (21,306). The outcome is website visit during the original two weeks. The frozen split has 38,400 training, 12,800 development, and 12,800 locked-test rows. Men's/no-email pairwise rows total 25,568 training, 8,522 development, and 8,523 locked test. Hillstrom is a separate experimental population from the observational UCI Online Retail II data.

### Confirmatory primary locked-test result

The labeled primary estimand is assignment to Men's email versus no email on a two-week website visit. Men's email had 802/4,262 visits (18.8175%); no email had 454/4,261 (10.6548%). The risk difference is **+8.1626807 percentage points**, with a 95% Newcombe/Wilson interval **[+6.6670193, +9.6584816] pp**, exact two-sided randomization p-value **1.5255029 × 10⁻²⁶**, and **81.6268 additional visits per 1,000 assigned**. This is the effect of randomized assignment/offer; delivery, opening, and reading were not observed.

### Secondary randomized visit comparisons

These are the two predeclared secondary website-visit contrasts, Holm-adjusted over the eight secondary outcome/contrast tests:

| Contrast | Difference (pp) | 95% Newcombe/Wilson interval (pp) | Holm-adjusted p |
|---|---:|---:|---:|
| Women's email vs no email | +4.8467439 | [+3.4199228, +6.2745968] | `2.7318746e-10` |
| Men's email vs Women's email | +3.3159368 | [+1.7172365, +4.9138462] | `0.000359276` |

Secondary conversion and spend contrasts were inconclusive after Holm adjustment. The page notes this without presenting those estimates as evidence of zero effect.

### Exploratory development policy-value comparison

P3-008B compares candidate policies with **expected random targeting at the same 20% budget**. The pairwise development population has 8,522 rows, with 1,705 selected at the frozen budget. Values are candidate-minus-expected-random differences in incremental website visits per 1,000 pairwise-eligible experiment rows:

| Development policy | Δ visits / 1,000 | Paired 95% interval |
|---|---:|---:|
| HGB DR-learner | +4.9287921 | [−2.3449672, +11.2652350] |
| Logistic X-learner | +2.0462794 | [−4.6090633, +8.7437944] |
| Logistic T-learner | +0.9432036 | [−5.3719604, +7.8463422] |
| Historical behavior | +2.4901168 | [−3.4512603, +9.0032685] |

The page supports family filtering across logistic S/T/X/DR, HGB S/T/X/DR, the historical benchmark, constant-ATE seeded reference draw, and supplementary XGBoost T-learner. XGBoost is labeled non-promotion-eligible. All paired intervals include zero. Constant ATE / expected random targeting remained the research reference; no personalized model established reliable superiority. The locked test was not used to evaluate candidate models (zero fits; candidate diagnostics not run). A null promotion result does not establish homogeneous treatment effects.

The locked-test **expected random** 20% policy value is shown separately in the interpretation tab, estimated from **8,523 Men's/no-email locked-test eligible experiment rows**: **16.3254 incremental website visits per 1,000 locked-test eligible experiment rows**, with scaled 95% interval **[13.3340, 19.3170]**. This is 20% of the randomized test ATE, not a personalized targeting gain.

## Evidence interpretation and limitations

The locked randomized test supports a positive average assignment effect for this historical Men's-email campaign on visits, subject to randomization, consistency, positivity, complete outcome observation, and no material interference. The trial does not measure engagement or email reading. It is one historical campaign and does not establish transportability to present-day campaigns or UCI Online Retail II customers.

The CATE and policy comparisons are exploratory development results used during selection. They do not provide validated person-level treatment effects; CATE values are model predictions, not observed individual causal effects. Propensity to visit/purchase is distinct from incremental response to an intervention. No personalized model demonstrated reliable policy improvement over expected random allocation at 20%.

Conversion is rare and spend is highly zero-inflated/skewed; secondary conversion/spend comparisons were inconclusive. No margin, contact cost, profit, or ROI estimate is supported. P3-008C did not run candidate test diagnostics. Its predeclared Lin-style adjusted analysis was omitted, with no adjusted estimate available. The locked split is from a widely published dataset and does not provide genuine analyst blinding. No additional ATE, CATE, or policy-value estimate was calculated for this integration.

## Tests and verification

Added bundle tests for schema/content pin, source provenance and exact fixed path selection, deterministic rebuild, missing/mismatched sources, privacy exclusions, primary and secondary results, development units, model-promotion status, and absence of locked-test candidate diagnostics. Added AppTest coverage for rendering, the primary values, secondary contrast switching, and development model-family filtering. Updated application navigation coverage to verify seven pages. The focused application suite passed **77 tests, with 1 existing `LOCAL_DATA_DIR`-dependent rebuild test skipped**. Python compilation/import checks, bundle checksum and privacy checks, and `git diff --check` passed.

Rebuild from the repository root with `.venv/bin/python -m src.causal_evidence_bundle --build`. Tests needing the private aggregates skip if those source files are unavailable; committed bundle validation always runs.
