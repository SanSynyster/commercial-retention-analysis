# COMMERCIAL-DS-002A — Evidence addendum

**Purpose:** close the numerical evidence gaps in the independent review without changing production logic.<br>
**Evidence generator:** `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python docs/recovery/COMMERCIAL_DS_002_ANALYSIS.py`<br>
**Interpretation labels:** **Descriptive** reports observed data; **Sensitivity** changes a defensible analytical convention; **Inferred** is a bounded interpretation rather than a directly observed fact.

## 1. Acquisition-proxy contamination

**Sensitivity analysis.** For pseudo-start `S′ = 2009-12-01 + k months`, the test hides the first `k` months, applies look-back `L` to the truncated data, then checks whether each eligible “acquisition” proxy was actually observed in hidden history.

| Hidden history | Look-back | Eligible proxies | Observed returning in hidden history | Lower-bound misclassification |
| ---: | ---: | ---: | ---: | ---: |
| 3 months | 12 months | 1,381 | 42 | 3.04% |
| 6 months | 12 months | 1,031 | 88 | 8.54% |
| 9 months | 12 months | 727 | 99 | 13.62% |
| 6 months | 6 months | 1,872 | 260 | 13.89% |
| 6 months | 9 months | 1,514 | 175 | 11.56% |

**Inference.** The rates are lower bounds: history before 2009-12-01 is unavailable. A 12-month observed clean period is the most conservative supported policy, but it does not establish first-ever acquisition. Every result must use “acquisition proxy”, carry observed look-back days, disclose this table, and include a late-cohort/≥18-month-history sensitivity. Early-to-late cohort comparisons remain differentially contaminated.

## 2. Return probability by recency

**Descriptive.** Product-order customer-anchors are pooled across complete-window month starts 2010-12-01 through 2011-09-01. Recency is elapsed whole days at midnight T; return is a product order in `[T,T+90d)`.

| Recency at T | Customer-anchors | 90-day returners | Return probability |
| --- | ---: | ---: | ---: |
| 0–90 | 21,027 | 11,371 | 54.08% |
| 91–180 | 9,880 | 2,850 | 28.85% |
| 181–270 | 6,951 | 1,243 | 17.88% |
| 271–365 | 5,043 | 923 | 18.30% |
| 366–450 | 2,398 | 182 | 7.59% |
| 451+ | 2,006 | 129 | 6.43% |

**Inference.** The 181–365-day bands have similar forward return probability, consistent with an annual-cycle segment; probability falls sharply beyond 365 days. This supports 365 days better than the earlier inter-order-gap statistic, which was conditional on an observed return. It does not prove 365 days is universally optimal.

## 3. Complete and truncated active windows

**Descriptive.** A canonical `[T−365d,T)` window is complete only when `T ≥ 2010-12-01`.

| Anchor | Observable history | Active product customers | Complete? |
| --- | ---: | ---: | --- |
| 2010-06-01 | 182d | 2,695 | No |
| 2010-07-01 | 212d | 2,962 | No |
| 2010-08-01 | 243d | 3,147 | No |
| 2010-09-01 | 274d | 3,309 | No |
| 2010-10-01 | 304d | 3,548 | No |
| 2010-11-01 | 335d | 3,923 | No |
| 2010-12-01 | 365d | 4,249 | Yes |
| 2011-01-01 … 2011-09-01 | 365d | 4,215–4,326 | Yes |

**Inference.** Six of the eleven DS-001 R3 development anchors have truncated features. Only ten month-start anchors are both 365-day complete and 90-day label-mature (2010-12-01 … 2011-09-01). The R3 split must be redesigned during pre-registration; retaining the old split would make early and later feature populations incomparable.

## 4. Same-day second invoices

**Sensitivity analysis.** Invoice identity is valid, but a second invoice on the first calendar day need not be a second purchase occasion.

| Policy | Mature customers | Invoice repeaters ≤90d | Same-day second invoice | Invoice rate | Rate subtracting same-day cases |
| --- | ---: | ---: | ---: | ---: | ---: |
| L=12m | 1,016 | 430 | 29 | 42.32% | 39.47% |
| L=3m | 3,556 | 1,476 | 154 | 41.51% | 37.18% |

The final column is the reviewer’s simple sensitivity (subtract every same-day second invoice from the numerator). It is not a complete occasion algorithm: a customer can have a same-day split invoice and a genuine later-day purchase within 90 days. Owner decision D-002-10 should use later-calendar-day purchase occasion as primary and preserve invoice-level repeat as sensitivity, with a tested definition for later qualifying invoices.

## 5. Population bridge and return truncation

**Descriptive.** Under the reviewed DS-002 code list, the current valid-purchase population is **5,878 customers / 36,969 invoices**. Product-only filtering gives **5,861 / 36,639**, a reduction of 17 customers and 330 invoices. The revised taxonomy may change this again and must publish the same bridge after approval.

There are **33 returns-only customers** with no observed product purchase (signed product revenue **£−1,643.28**), **37 customers with negative exact-decimal net product revenue**, and **£−39,466.28** of identified product returns in the first three months.

**Inference.** Some early returns plausibly relate to purchases before the source begins, but individual origin invoices cannot be established from the available data. Gross product revenue should remain the primary behavioural monetary field. Net product revenue needs explicit treatment of returns-only and negative-net customers before R4.

## 6. Monetary precision and reconciliation

**Descriptive.** Corrected V2 contains 18 rows whose unit price has three fractional decimal places; the maximum observed precision is three. Integer pence is therefore not exact. Canonical storage and calculations need exact decimal with at least three fractional places and adequate integral precision.

The hardened script asserts this exact Decimal bridge:

| Field | Corrected V2 |
| --- | ---: |
| Gross positive revenue, all customers | £20,533,741.918 |
| Refund/cancellation revenue, all | £−1,465,303.660 |
| Net transactional revenue, all | £19,068,438.258 |
| Identifiable gross current | £17,431,551.178 |
| DS-002 identifiable non-product | £302,114.628 |
| DS-002 identifiable gross product | £17,129,436.550 |
| Identified product refunds | £−714,532.550 |
| Identifiable net product | £16,414,904.000 |

These totals reproduce the reviewed DS-002 baseline; they do not pre-approve the revised taxonomy.

## 7. Date-level maturity and history policies

**Descriptive/sensitivity.** Maturity is now asserted using calendar date: `date(first_observed)+h ≤ date(D_end)`. This changes the 12-month-policy 60-day mature count from the prior timestamp result 1,252 to **1,258**; the 90-day count remains **1,016**. Candidate look-back results are:

| L | Eligible proxies | Cohort months | Mature/repeat 60d | Mature/repeat 90d | Mature/repeat 180d |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 3m | 4,152 | 22 | 3,798 / 1,287 | 3,556 / 1,476 | 3,253 / 1,798 |
| 6m | 3,166 | 19 | 2,812 / 976 | 2,570 / 1,073 | 2,267 / 1,202 |
| 9m | 2,552 | 16 | 2,198 / 772 | 1,956 / 802 | 1,653 / 820 |
| 12m | 1,612 | 13 | 1,258 / 441 | 1,016 / 430 | 713 / 371 |

## 8. Hardened overlap and repeat evidence

**Descriptive.** Both physical V2 overlap blocks contain exactly 22,523 rows and are exact full-value multisets of V1 for 1–9 December 2010. The corrected in-memory dataset has 1,044,848 rows. The full second V2 block equals V1 plus exactly invoice `581587`, code `POST`, timestamp `2011-12-09 12:50`, £18, customer 12680, France.

The diagnostic duplicate count after correction is 11,812 excess full rows, including 1,685 adjacent physical repeats. V1 has 5,268 repeat excess rows, of which 5,192 are current-valid and contribute £24,199.01. Corrected-V2 repeat gaps range from 1 to 254 source rows (median 9). These diagnostics support retain-and-flag; they do not justify global `drop_duplicates`.

## 9. Effects on R1–R6

| Workstream | Evidence effect | Status |
| --- | --- | --- |
| R1 commercial/cohorts | Acquisition cohorts are proxy cohorts with 3.04–13.62% measured lower-bound contamination in pseudo-boundary tests. Taxonomy changes product/non-product and all-customer bridge fields. Existing raw-V2 overlap results remain invalid. | Feasible only after taxonomy and terminology decisions; cohort sensitivities mandatory |
| R2 segmentation | RFM customer/order/monetary populations change with approved taxonomy; three-decimal exact monetary values and same-day occasion choice affect frequency/value features. | Feasible after mapping and occasion decisions; existing segment outputs require regeneration |
| R3 lapse | Six old development anchors have incomplete 365-day features. Complete-window eligibility leaves ten mature anchors, so evaluation split must be redesigned. Return-by-recency supports 365d. | Existing split invalid; pre-registration redesign required |
| R4 value/forecasting | Returns-only and negative-net customers plus early left-truncated returns bias net value; gross product is primary. Taxonomy and exact Decimal are prerequisites. | Feasible with explicit net-return policy; existing values require regeneration |
| R5 experiments | “Acquired” eligibility is proxy-based and cohort-dependent; same-day split invoices alter conversion by 2.85–4.33 percentage points in the simple sensitivity. | Eligibility/outcome rules blocked on owner decisions |
| R6 pandas/dbt/Spark parity | One versioned mapping, exact description exceptions, source-row identity, exact decimal, half-open windows and date maturity must be shared. Unknown codes must fail in all engines. | Feasible only after contract encoding; no parity claim yet |

No business report or model was regenerated. Any published output using raw V2, global deduplication, known-acquisition language, the DS-001 R3 split, integer-pence assumptions, or a fail-open taxonomy requires a banner and later regeneration after contracts are approved.
