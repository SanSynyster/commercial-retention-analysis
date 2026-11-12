# M5-005R — Independent Review: CRM Experiment Feasibility

## Verdict

**PASS WITH CONDITIONS.**

The page describes the M4 pilot design faithfully and calls the frozen M4 functions correctly. Every displayed number reproduces independently, including the reference scenario and 138 sampled input combinations rendered through AppTest. The page runs from a clean checkout and reads no data.

One bounded correction is required:

| ID | Severity | Topic |
| --- | --- | --- |
| R1 | Low–Medium | The page shows the hypothetical net ITT effect and the MDE in separate sections and never compares them. At the defaults, a positive £400 campaign total sits beside a net effect (£0.80) that is about one-eleventh of the MDE (£8.86). M4-002's central conclusion, that positive expected value is not adequate power, is therefore not visible. |

Note on scope: the review brief received was truncated after "Total campaign". This review covers sections A–B as given. It applies the interactive, reproducibility, verdict and deliverable structure used in M5-002R to M5-004R.

## Scope and baseline

- **Repository:** HEAD `e1367de95e08bca951cb3863fc32951ab4d734ff`.
- **Uncommitted M5-005 changes:**
  - Modified: `app/README.md`, `app/streamlit_app.py`, `app/views/placeholders.py` (the placeholder helper was removed), `tests/test_dashboard_app.py` (the placeholder test was removed).
  - New: `app/views/experiment_feasibility.py`, `src/experiment_feasibility_metrics.py`, `tests/test_experiment_feasibility_page.py`, and the M5-005 note.
- **Sources read:** M4-001 design, M4-002 feasibility and M4-003 review.
- **Frozen calculator:** `src/crm_pilot_feasibility.py` is unchanged since `d01434f`. Its SHA-256 `41dfba67…57bf` equals the module hash recorded in the M4-002 manifest.
- **Earlier corrections:** the M5-004 R1/R2 corrections are present in HEAD. Mistyped targeting sections now raise `BundleError`, and the tie disclosure text is in place.
- **No changes:** no implementation or research file was modified. Probes and clean copies were kept in a session scratch directory.

## A. Scientific design fidelity

| # | Design element (M4-001/M4-002) | Page text | Result |
| --- | --- | --- | --- |
| 1 | Single enrollment wave | "one enrollment wave" | ✔ |
| 2 | Established, contact-eligible customers | "established customers who meet current CRM eligibility rules"; the expander adds a complete 365-day history and ≥1 qualifying purchase | ✔ |
| 3 | Primary 10% capacity | "select the top 10% by 365-day qualifying purchase-date frequency"; 10% is the default; the expander describes the prespecified hash tie-break | ✔ |
| 4 | 1:1 persistent customer-level randomisation | "randomize persistently at customer level 1:1" | ✔ |
| 5 | Treatment receives one non-discount study email | ✔ | ✔ |
| 6 | Control receives no study email | ✔ | ✔ |
| 7 | Comparable BAU in both arms | "Both arms otherwise receive comparable business-as-usual treatment"; displacement flagged as an operational decision (M4-003 Finding 3) | ✔ |
| 8 | 30-day net contribution margin | ✔; the expander lists finance-approved discount, refund, COGS, fulfilment and settlement-lag treatment | ✔ (see O2) |
| 9 | ITT estimand | "intention-to-treat difference in mean outcome between assigned arms"; assignment defines ITT regardless of delivery | ✔ |

**Controls count toward capacity.** The capacity help text and an `st.info` both say that controls count toward enrollment capacity, and that at 10% and 1:1 about 5% of the eligible base is assigned the email. This is correct per M4-001.

**Alternative capacities.** The inputs caption calls them "sensitivity scenarios". The sensitivity caption and the visible warning say that capacity "changes the selected population and potentially the estimand" and that the primary design is 10%.

**Interpretation.**

- The evidence label, the warning and the help texts say that no uplift has been measured.
- All inputs are labelled assumed or hypothetical. The SD is not drawn from UCI.
- The MDE is described as a normal-approximation planning value, "not expected campaign uplift".
- M4-003 Finding 1 is respected. The page labels `g − c` as the "Hypothetical net ITT effect". It reports `n_t(g − c)/n_enrolled` separately as a cohort-average budget quantity, explicitly distinguished from the arm-mean contrast and never compared with the MDE. The headline MDE label uses the corrected wording "treatment − control mean net margin".

## B. Numerical correctness

**Adapter.** `build_scenario` calls the frozen functions directly, with no reimplementation:

- `allocate_enrollment(eligible, capacity)`.
- `mean_difference_mde(n_t, n_c, sd, alpha=0.05, power=0.80)`.
- `commercial_scenarios([eligible], [c], [g], capacity=capacity)`.
- `capacity_sensitivity([eligible], DEFAULT_CAPACITIES, [sd], alpha=0.05, power=0.80)`.

`sensitivity_table` only selects and renames columns. The adapter test confirms that its allocation and MDE equal direct calls to the M4 functions.

**Reference scenario** (10,000 eligible, 10%, SD £50, g £1, c £0.20), reproduced independently. `z₀.₉₇₅ + z₀.₈₀ = 2.801585`.

| Quantity | Formula | Independent | Page |
| --- | --- | ---: | ---: |
| Enrolled | `ceil(10,000 × 0.10)` | 1,000 | 1,000 |
| Treatment / control | `ceil(n/2)` / `floor(n/2)` | 500 / 500 | 500 / 500 |
| MDE (α = 0.05 two-sided, power 80%) | `2.801585 × 50 × √(1/500 + 1/500)` | £8.8594 | £8.86 |
| Net ITT effect | `g − c` | £0.80 | £0.80 |
| Total campaign contribution | `500 × 0.80` | £400.00 | £400.00 |
| Average per enrolled customer | `400 / 1,000` | £0.40 | £0.40 |
| Break-even gross increment | `c` | £0.20 | £0.20 |
| Contact cost (total) | `500 × 0.20` | £100 | (not displayed) |

**Capacity sensitivity** (10,000 eligible, SD £50): 10% gives 1,000 enrolled and an MDE of £8.86; 20%: 2,000 and £6.26; 50%: 5,000 and £3.96; 100%: 10,000 and £2.80. These are identical to the M4-002 sensitivity table and the M4-003 reproduction.

**Rounding and allocation.**

- The odd case 10,050 → 1,005 enrolled = 503 / 502 follows the disclosed convention that treatment gets the extra customer.
- `ceil(p × capacity)` was checked against exact rational arithmetic for **every** eligible count from 100 to 1,000,000 at all four capacities: 0 mismatches. Floating-point `ceil` does not cause off-by-one enrollment anywhere in the page's input range.

**Rendered values across inputs.** AppTest set 138 combinations sampled from population {100; 1,005; 10,000; 10,050; 1,000,000} × capacity {10, 20, 50, 100%} × SD {£20, £50, £100, £200} × g {£0, £0.10, £1, £5} × c {£0.01, £0.20, £1}. For each one, the following were compared with an independent implementation:

- Every displayed metric: enrolled, treatment, control, MDE, net ITT, total, break-even.
- The cohort-average caption.
- All four sensitivity rows.

There were **0 mismatches and no exceptions**.

### R1 — The net effect and the MDE are never compared (Low–Medium)

**Evidence.** The page shows "Approximate MDE for treatment − control mean net margin £8.86" and, in a separate section, "Hypothetical net ITT effect £0.80" and "Total incremental campaign contribution £400.00". No text or indicator relates them. The frozen module already defines the comparison: `statistical_commercial_comparison` uses `net_effect_at_or_above_approx_80pct_power_mde = (g − c) ≥ MDE`. M4-002 makes that comparison its main conclusion: "a campaign can have positive expected value … while being far too small to distinguish from zero in a modest pilot". At the defaults the assumed effect is about 9% of the MDE.

**Impact.** A reader sees a positive campaign total and a feasibility page, and may infer that the default pilot is informative. It would in fact have power far below 80% for the assumed effect. The page does not misstate any number, but it omits the key interpretive link from the research it represents.

**Smallest correction.**

- Add one line in the economics section, computed from the values already on the page. For example, when `g − c < MDE`: "The assumed net ITT effect (£0.80) is below the approximate 80%-power MDE (£8.86); a pilot of this size would be unlikely to detect it. Positive expected value is not adequate power."
- Show the complementary text when `g − c ≥ MDE`, keeping the existing caveat that the MDE is not a pass/fail rule.
- Optionally add an AppTest assertion.

No calculator change is needed.

## C. Interactive application

The checks below were run in a clean copy (HEAD plus M5-005 changes, **no `data/`**, `LOCAL_DATA_DIR` unset) with a fresh Python 3.11 venv from `requirements-app.txt`.

| Check | Result |
| --- | --- |
| Inputs | Eligible customers: `number_input` 100–1,000,000, default 10,000. Capacity selectbox has exactly 10/20/50/100%, default 10%. SD {£20, £50, £100, £200}, default £50. Gross {£0, £0.10, £0.50, £1, £2, £5}, default £1. Cost {£0.01, £0.05, £0.20, £1}, default £0.20. These are the frozen M4 grids. Every label says "(assumed)". |
| Updates | All metrics, the cohort-average caption, and the sensitivity chart and table update consistently (B, 138 combinations). Changing capacity to 20% gives 2,000 / 1,000 / 1,000, as tested. |
| Chart | MDE against capacity, with a zero-based y-axis and a 10–100% x-axis. Tooltips give counts and MDE. Not exaggerated. |
| Limitations | The evidence label and a visible `st.warning` state that no causal uplift was measured, that eligibility, consent, margins, costs and contact rules are unknown, that capacity changes the estimand, displacement and BAU comparability, and the normal-approximation, skew and clustering caveats. The expander lists pre-launch owner decisions. |
| Navigation | Customer Overview, Purchase Propensity, Targeting Explorer and Experiment Feasibility (13 metrics) all render through the real `st.navigation` routing with no exceptions. |
| Runtime file access | An audit hook over a full four-page run shows only the three tracked `app_data/*.json` bundles opened. The feasibility page reads no file. |
| Live server | Clean copy: `/_stcore/health` returned `ok`. |
| Error handling | There is no bundle. The frozen M4 input validation is preserved (tested: population 0, capacity 0, SD 0, negative cost all raise `ValueError`). The page's controls cannot produce those inputs. |

## D. Reproducibility and tests

| Run | Result |
| --- | --- |
| Focused app and M4 suites (7 modules), dev venv | **52 OK, 1 skip** (propensity rebuild with `LOCAL_DATA_DIR` unset) |
| Same, clean copy with fresh venv | **52 OK, 2 skips** (private-input rebuilds) |
| Full `tests/` discovery | **169 OK, 2 skips** (Spark/Java and the propensity rebuild) |
| Corrected-V2 007 recovery tests | 15 OK |
| Frozen M4 tests (`tests.test_crm_pilot_feasibility`) | Included above. Pass. |

The new tests check scientific invariants:

- Reference-example agreement.
- Allocation and MDE identical to the M4 functions.
- Break-even gives zero net value.
- M4 input validation is preserved.
- AppTest rendering, the uplift caveat and the capacity update.

They do not cover R1.

## E. Findings summary

### Required for closure

| ID | Severity | File | Correction |
| --- | --- | --- | --- |
| R1 | Low–Medium | `app/views/experiment_feasibility.py` | Add a one-line comparison of the hypothetical net ITT effect `g − c` with the displayed MDE (below / at or above), stating that positive expected value is not adequate power. Optional AppTest assertion. |

### Optional (not blocking)

- **O1:** Format negative currency as "−£1.00" rather than "£-1.00" (net ITT, total and cohort average at `g < c`).
- **O2:** State the outcome window as `[assignment_time, assignment_time + 30 days)` plus a finance-specified adjustment lag. This is the convention settled by M4-003 Finding 2.
- **O3:** Change the sensitivity column and chart axis wording "£ per randomized customer" to "treatment − control difference in mean net margin", matching the headline label and M4-003 Finding 1.
- **O4:** At the 100% capacity option, note that it is a population-wide experiment, not a targeting pilot, as M4-002 does.
- **O5:** Make the `st.info` treatment share dynamic (`treatment_fraction_eligible`). It currently describes only the 10% case, which is still correct as written.

## Commit readiness

After R1, **M5-005 is ready for a scoped local commit**:

- The four modified files.
- The four new files.
- This review.

The frozen M4 module, the M4 reports and all data bundles are unchanged. Re-run the seven focused modules after editing.
