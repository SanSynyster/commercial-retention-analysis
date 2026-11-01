# COMMERCIAL-DS-002-R — Independent Data Foundation Review

**Reviewer:** Claude Code (independent of the implementation agent)<br>
**Review date:** 2026-10-30<br>
**Subject:** COMMERCIAL-DS-002 [data audit](COMMERCIAL_DS_002_DATA_AUDIT.md), [decision proposal](COMMERCIAL_DS_002_DECISION_PROPOSAL.md), [review handover](COMMERCIAL_DS_002_REVIEW_HANDOVER.md) and [analysis script](COMMERCIAL_DS_002_ANALYSIS.py), read against the COMMERCIAL-DS-001 [data contracts](COMMERCIAL_DS_001_DATA_CONTRACTS.md), [decision log](COMMERCIAL_DS_001_DECISION_LOG.md) and [evaluation protocol](COMMERCIAL_DS_001_EVALUATION_PROTOCOL.md).<br>
**Status:** Review only. No production code, raw data, dependency, model output, existing report or COMMERCIAL-DS-002 document was modified. Nothing was committed or pushed.

---

## 1. Overall verdict

| Dimension | Verdict |
| --- | --- |
| **Numerical reproducibility** | **PASS.** All eleven requested findings reproduce exactly. The method was independent: a different parser, exact `Decimal` arithmetic and `Counter` multisets, with no use of Codex's code. No material numerical discrepancy was found. |
| **Methodological validity** | **PASS WITH CONDITIONS.** The core data-correction decisions are sound and safe to approve: corrected V2 as canonical, the source-boundary overlap correction, retaining and flagging incidental repeats, and the line identity. Four material issues were missed or under-evidenced. All four need revision or explicit conditions before the affected contracts are encoded. |
| **Product / non-product taxonomy (D-002-05)** | **FAIL as proposed.** The code list is incomplete, and the proposal lets unknown codes default to "product". |
| **Readiness for Phase 3** | **Not ready.** Owner decisions plus a bounded evidence addendum are required first (§10). |

The four material issues:

1. **The product / non-product taxonomy is incomplete.** It misses `ADJUST`, `ADJUST2`, `TEST001`, `TEST002` and numeric code `23444` "Next Day Carriage". Under the proposal, unknown codes silently become product.
2. **Acquisition-proxy misclassification is not quantified.** A pseudo-boundary test shows that even a 12-month look-back admits a material, cohort-dependent share of returning customers. The lower bound is 3.0–13.6%.
3. **The 365-day active window cannot be fully observed for anchors before 2010-12-01.** This conflicts with the R3 development anchors in the evaluation protocol.
4. **Same-day multiple invoices count as "second purchases".** This inflates the 90-day second-purchase rate, for example 42.32% → 39.47% under the 12-month policy.

---

## 2. Independent reproduction results

### 2.1 Method (independent of Codex's code path)

| Aspect | Codex | This review |
| --- | --- | --- |
| V2 parsing | `pandas.read_csv`, dtype inference | stdlib `csv` reader; every field parsed explicitly from its raw string |
| V1 parsing | `pandas.read_excel` | `openpyxl` read-only cell values, with header asserted |
| Prices / revenue | `float64` | `decimal.Decimal` from the source string (V2) or `repr(float)` (V1): exact currency sums |
| Multiset equality | 64-bit `hash_pandas_object` + `value_counts` | Python `collections.Counter` over full 8-field tuples: exact, no hashing collisions |
| V1-period customers | Derived from corrected V2 ≥ 2010-12-01 | Derived from the **V1 file itself**, then matched to V2 history before 2010-12-01 |
| Look-back cutoff | `min(order_date).normalize() + L` (data-derived) | Fixed constant `D_start = 2009-12-01 + L` |

Codex's script was also run unchanged. Its JSON output has SHA-256 `821340995a747ccf4bea3fabc6bfb0212a19a82dc91f54a3c22801eac877cd84`, identical to the hash in the handover. Source hashes match the audit: V1 `43465a06…676d`, V2 `32569a66…d3a9`. The CSV has 1,067,371 data rows and 1,067,372 physical lines, with no embedded newlines, so row number and file line differ only by the header offset.

My reproduction scripts were kept outside the repository, in the session scratchpad (`independent_repro.py`, `independent_history.py`).

### 2.2 Results

| # | Finding | Codex value | Independent value | Verdict |
| --- | --- | --- | --- | --- |
| 1 | V2 source reset | Zero-based row 525,461 (only reset) | Only negative timestamp step at index 525,461. Row 525,460 = invoice 538171, 2010-12-09 20:01; row 525,461 = invoice 536365, 2010-12-01 08:26 (V1's first row). Block 1 has 0 rows after 2010-12-09; block 2 has 0 rows before 2010-12-01 | **PASS** |
| 2 | Two exact 22,523-row copies | Both exact multiset matches to V1 | `Counter(block1 window) == Counter(V1 window) == Counter(block2 window)`: True / True; 22,523 rows each | **PASS** |
| 3 | £311,878 identifiable revenue correction | GBP 311,878.00 per copy; GBP 623,756.00 combined | Exact Decimal `311878.00` per copy; `623756.00` combined. Also reproduced: 14,504 valid lines, 573 customers, 776 orders, gross positive 438,852.65, net transactional 377,488.45, identifiable gross product 309,523.75 | **PASS** |
| 4 | 22,523 vs 22,844 | 22,844 = 22,523 + 321 within-copy repeats | V1 window has 22,523 rows with 22,202 distinct tuples: 321 within-copy excess. Combined-window `duplicated` equivalent = 22,844 | **PASS** |
| 5 | Corrected V2 = 1,044,848 rows | 1,044,848 | 1,044,848 (1,067,371 − 22,523) | **PASS** |
| 6 | Extra £18 `POST` line | Invoice 581587, `POST`, qty 1, GBP 18, customer 12680, France, 2011-12-09 12:50 | `Counter(block2) − Counter(V1)` = exactly that one row; `Counter(V1) − Counter(block2)` = empty | **PASS** |
| 7 | Global dedupe: 11,812 rows / £56,746.91 | 11,812; GBP 56,746.91 | Global dedupe = 1,033,036 rows. Corrected V2 has 11,812 total excess exact repeats (11,491 outside overlap + 321 inside). Identifiable gross 17,431,551.178 − 17,374,804.268 = **56,746.91** | **PASS** |
| 8 | 62.8% V1 left-censoring | 2,726 / 4,338 = 62.84% (current); 2,722 / 4,334 = 62.81% (product) | Same, with V1 customers taken from the V1 file: 2,726 / 4,338 = 62.84%; 2,722 / 4,334 = 62.81%; 1,612 first-seen in V1 under both | **PASS** |
| 9 | 3/6/9/12-month eligibility | 4,152 / 3,166 / 2,552 / 1,612; mature 90-day 3,556 / 2,570 / 1,956 / 1,016; 90-day rate 41.51 / 41.75 / 41.00 / 42.32% | Identical on every value, including 60-day mature counts and rates, cohort-month counts (22/19/16/13), 12-month M1 1,393 / 22.83%, M6 669 / 17.94%, M12 0 | **PASS** (see §3.4 and §3.6) |
| 10 | 1,612 acquisition-proxy customers | 1,612 across 13 cohort months | 1,612. The population is **identical** to "V1-period customers never seen in V2 before 2010-12-01", by construction | **PASS** |
| 11 | Revenue reconciliations (corrected V2) | Gross positive 20,533,741.92; refunds −1,465,303.66; net 19,068,438.26; identifiable gross 17,431,551.18; non-product 302,114.63; gross product 17,129,436.55; product refunds −714,532.55; net product 16,414,904.00 | Exact: 20,533,741.918; −1,465,303.66; 19,068,438.258; 17,431,551.178; 302,114.628; 17,129,436.55; −714,532.55; 16,414,904.00. Bridge identity product + non-product = identifiable gross holds exactly | **PASS** |

Other items reproduced exactly:

- Raw-V2 and global-dedupe candidate rows in audit §5.
- Excess repeats outside the overlap: 11,491 across 4,303 invoices.
- Zero invoices map to more than one customer.
- Inter-order gap quantiles: p50 25.0, p75 62.1, p90 135.9, p95 207.0; 1.07% of gaps exceed 365 days.
- Unit tests: 14 run, 13 pass, 1 skipped (Spark/Java). The docs link validator passes.

---

## 3. Numerical discrepancies and omissions

No reported number was wrong. The following are convention differences or unreported quantities:

| # | Item | Detail | Materiality |
| --- | --- | --- | --- |
| N-1 | Three-decimal currency | Audit amounts are rounded to 2 dp. Exact values carry 3 dp (e.g. 20,533,741.918) because **18 corrected-V2 rows have 3-decimal prices**. Float sums differ from exact Decimal by ≈4×10⁻⁹ and are order-dependent at that scale. | Low. Affects the contract choice: integer pence is **not** an exact representation. |
| N-2 | Maturity convention | The script tests maturity at timestamp level (`first_ts + h ≤ 2011-12-09 12:50`). DS-001 `C-TIME-5` specifies date-level comparison. At h = 60 under the 12-month policy, mature customers are 1,252 (timestamp) vs **1,258** (date level). The difference is 6 customers at every look-back for h = 60 and 0 at h = 90. | Low. The convention must be fixed once. |
| N-3 | Product-only population not reported | Audit §1 states that customers (5,878) and orders (36,969) are unchanged. That is true under **current** logic. Under the proposed product-only order definition, corrected V2 has **5,861 customers and 36,639 orders**: 17 customers and 330 non-product-only invoices drop out. | Low. A population change that must be disclosed. |
| N-4 | "22,844 exact duplicates" in DS-001 | `COMMERCIAL_DS_001_RISK_REGISTER.md` R-18 and `COMMERCIAL_DS_001_AGENT_HANDOVER.md` still describe 22,844 as the duplicate count. DS-001 P-01 says "V2 (deduplicated)". | Medium (documentary). Wording could lead an implementer to call `drop_duplicates`. |
| N-5 | Evidence not in the script | The gap quantiles, the sorted `assert_frame_equal`, the identification of the `POST` row and the V1 full-period repeat figures (5,268 / 5,192 / GBP 24,199.01) came from "additional bounded checks" (handover §4) that are not in the committed script. All of them reproduce. | Low. A reproducibility gap. |

---

## 4. Methodological concerns

### M-1. Non-product taxonomy is incomplete and fails open (High)

A scan of every non-numeric stock code in corrected V2, plus description checks on numeric codes, finds valid identifiable positive revenue on codes outside the proposed list:

| Code | Description | Valid identifiable positive revenue | Identified negatives |
| --- | --- | ---: | ---: |
| `ADJUST` | "Adjustment by Peter / john on …" | GBP 3,538.52 | GBP −1,500.40 |
| `ADJUST2` | "Adjustment by Peter on Jun 25 2010" | GBP 731.05 | 0 |
| `TEST001` | "This is a test product." | GBP 225.00 | GBP −22.50 |
| `TEST002` | "This is a test product." | GBP 1.00 | 0 |
| `23444` (numeric) | "Next Day Carriage" (80 rows) | GBP 1,200.00 | — |

These codes carry GBP 5,695.57 of identifiable revenue across 30+ customers. Gift vouchers (`GIFT_0001_*`), `DCGS*` and `C3` are present with zero valid revenue in this file. `SP1002` looks like merchandise.

The amount is small (≈0.03% of gross product revenue). The rule design is the defect. D-002-05 classes "all normal merchandise codes" as product by default, so any unmapped code is silently treated as product, and test or adjustment lines enter customer value and RFM features. This is a fail-open contract.

### M-2. Acquisition-proxy misclassification is unquantified and cohort-dependent (High)

The audit correctly rejects "first-ever purchase". It does not, however, measure how often a 12-month look-back admits returning customers. V2 can estimate a **lower bound** empirically. Pretend the data begins at a pseudo-start S′ = 2009-12-01 + *k* months, apply the look-back to the truncated data, and count "acquired" customers who actually had orders in the hidden *k* months:

| Hidden history *k* | Look-back L | Eligible "acquired" | Actually returning | Lower-bound misclassification |
| ---: | ---: | ---: | ---: | ---: |
| 3 months | 12 | 1,381 | 42 | **3.04%** |
| 6 months | 12 | 1,031 | 88 | **8.54%** |
| 9 months | 12 | 727 | 99 | **13.62%** |
| 6 months | 6 | 1,872 | 260 | 13.89% |
| 6 months | 9 | 1,514 | 175 | 11.56% |

These are lower bounds, because the real hidden history before 2009-12-01 is unbounded, while the test hides only *k* months. Two consequences follow:

- **False acquisition claims.** Some of the 1,612 customers, plausibly more than 10%, are customers returning after a gap of more than 12 months. Annual or seasonal buyers are the obvious risk: the 271–365-day recency band has an 18.3% 90-day return rate (§M-4).
- **Differential misclassification across cohorts.** Observed look-back ranges from 365 days (December 2010 cohort) to 738 days (December 2011). Early cohorts are therefore more contaminated than late ones. Any cohort trend in second-purchase or retention rates is partly an artefact of the observation window. This confounds R1 cohort comparisons and R5 eligibility.

The 3/6/9/12-month comparison in audit §6.3 shows stable repeat rates, but that does not test contamination: the populations, calendar periods and seasonality all differ.

### M-3. The 365-day active window is truncated for early anchors (High)

The active definition `[T−365d, T)` is only fully observable for T ≥ 2010-12-01:

| Anchor | History available | Active-365 product customers |
| --- | ---: | ---: |
| 2010-06-01 | 182 days | 2,695 |
| 2010-09-01 | 274 days | 3,309 |
| 2010-11-01 | 335 days | 3,923 |
| 2010-12-01 | 365 days (first complete) | 4,249 |
| 2011-01-01 … 2011-09-01 | ≥ 365 days | 4,215 – 4,326 |

The proposed R3 split in the [evaluation protocol](COMMERCIAL_DS_001_EVALUATION_PROTOCOL.md) §4 uses development anchors 2010-06-01 … 2011-04-01. Six of those eleven anchors have a truncated active window, along with truncated trailing-365-day monetary and frequency features. The apparent growth of the "active" population from 2,695 to 4,249 is largely an observation artefact.

Customer eligibility is therefore inconsistent across anchors, and development and holdout periods are not comparable. Restricting canonical anchors to complete windows leaves only **10 mature month-start anchors** (2010-12-01 … 2011-09-01 at h = 90) for development, purge and holdout. The R3 split has to be redesigned.

### M-4. The active-window justification uses the wrong statistic (Medium)

"98.93% of observed inter-order gaps ≤ 365 days" is conditional on a return being observed. It is also bounded by a window of about two years, so it does not measure the return probability of customers who are currently dormant. The relevant evidence is the forward return rate by recency. Pooled over complete-window anchors 2010-12-01 … 2011-09-01:

| Recency at T (days) | Customer-anchors | Return in `[T, T+90d)` |
| --- | ---: | ---: |
| 0–90 | 21,027 | 54.08% |
| 91–180 | 9,880 | 28.85% |
| 181–270 | 6,951 | 17.88% |
| 271–365 | 5,043 | 18.30% |
| 366–450 | 2,398 | 7.59% |
| 451+ | 2,006 | 6.43% |

This evidence **supports** 365 days better than the gap statistic does. Return propensity is flat from 181 to 365 days, which looks like an annual purchase cycle, and it then roughly halves. Customers with recency over 365 days account for 1.86% of next-90-day returners. A 180- or 270-day window would cut off the annual-cycle buyers. The conclusion holds, but the evidence cited for it should be replaced.

### M-5. Same-day multiple invoices inflate "second purchase" (Medium)

Order = customer × invoice is verified as an identity (zero invoices map to multiple customers). It is not, however, a verified **purchase occasion**. Some second invoices fall on the same calendar day as the first:

| Policy | 90-day repeaters | Same-day second invoice | Rate (invoice) | Rate (excluding same-day) |
| --- | ---: | ---: | ---: | ---: |
| L = 12m | 430 / 1,016 | 29 | 42.32% | 39.47% |
| L = 3m | 1,476 / 3,556 | 154 | 41.51% | 37.18% |

Split invoices on the same day, often order corrections, inflate repeat purchase, `C-T2` (time to second purchase near zero) and R5 conversion outcomes. Neither DS-001 nor DS-002 makes a decision on this.

### M-6. Net product revenue mixes in returns of unobserved purchases (Medium)

Returns cannot be linked to their original invoices (audit §12.7). Left truncation adds a further bias:

- 33 customers have identified product returns but **no** observed product purchase (GBP −1,643.28).
- 37 customers have negative net product revenue.
- Identified product returns in the first three months of V2 total GBP −39,466.28, and some relate to purchases before 2009-12-01.

Net product value is therefore biased downwards early in the window and at customer level. Gross product revenue is the right primary behavioural metric, as Codex recommends. Net product revenue needs a stated treatment for negative and returns-only customers before R4 uses it.

### M-7. Line identity specification is incomplete for multi-engine use (Medium)

`(source_sha256, source_row_number)` is the right choice. To be safe in practice it needs four additions:

1. **Base and header semantics.** Zero-based data-row index, excluding the header. The CSV has no embedded newlines, so this equals physical line − 2. That property should be asserted.
2. **Single point of assignment.** Row numbers are assigned once at raw ingestion and materialised. dbt and Spark consume them as data and must never recompute them: Spark CSV reads are partitioned and `monotonically_increasing_id` is not a row number.
3. **V1 identity.** V1 `line_id`s are a different identity space. Legacy V1/V2 comparison is by multiset, not by line ID.
4. **Re-export changes IDs.** Any byte change to the source file changes the SHA, and with it every ID. That is acceptable, but it must be documented as intended behaviour.

DS-001 `transaction_lines` still specifies "hash of source fields + occurrence index" and must be superseded.

### M-8. Smaller points

- **Overlap correction is fail-open in the script.** The script computes the SHA but never asserts it. Multiset equality is reported as a boolean, so a mismatch would not fail the run. Only the reset position (`[525461]`) is asserted. The canonical implementation must fail closed on hash mismatch, on reset-count mismatch and on multiset inequality.
- **`inactive_90d_at_T` lacks a denominator.** Its population must be defined: customers with ≥1 prior product order, optionally `C-ACTIVE`. Otherwise never-seen customers become trivially "inactive". The lapse label counts only product orders, so a customer whose only purchase in `[T, T+h)` is postage or a manual line counts as lapsed. That behaviour should be stated.
- **R1 is missing a field.** The field family has no all-customer product revenue measure. Unidentified customers account for GBP 3,102,190.74 (15.1%) of gross positive revenue. R1 commercial reporting needs `gross_product_revenue_all` and an explicit unidentified bridge line.
- **Year-over-year windows.** V2's two "years" overlap on 1–9 December 2010 in raw form. After correction, R1 should define non-overlapping 365-day windows and disclose the partial December 2011.
- **Look-back cutoff in the script is data-derived** (`orders.min().normalize()`), not a contract constant. It is harmless here (both give 2009-12-01) but fragile.

---

## 5. Assessment of each proposed policy

| Policy | Verdict | Rationale | Conditions |
| --- | --- | --- | --- |
| Corrected V2 as canonical (D-002-01) | **PASS** | V1 is 62.8% left-censored. The corrected V2 matches V1 exactly over V1's period except for one real GBP 18 postage row, and it adds 365 days of history. | Use the name `v2c` / "overlap-corrected V2", never "deduplicated". |
| Source-boundary-only overlap correction (D-002-02) | **PASS WITH CONDITIONS** | Proven by exact multiset equality of both copies. Removes exactly one copy. Keeping block 2 preserves a contiguous source year. | Tie the rule to the V2 SHA. Fail closed on hash, reset or multiset mismatch. Use a half-open window `[2010-12-01, 2010-12-10)`. Materialise `source_block_id`. |
| Retain incidental exact repeats (D-002-03) | **PASS WITH CONDITIONS** | There is no field to separate export duplicates from repeated lines. Removal changes identifiable gross revenue by only 0.33%, and only 1,685 of 11,812 excess rows are adjacent duplicates, so there is no strong signal of export duplication. Retaining is the conservative, reversible choice. | A one-per-tuple sensitivity is mandatory in R1 and R4 headline tables. Flags `is_exact_repeat` / `exact_repeat_group_size` are computed after the overlap correction. |
| Transaction-line identity (D-002-04) | **PASS WITH CONDITIONS** | Business fields are provably non-unique, and an occurrence index is unstable. | The four additions in §M-7. Supersede DS-001 `transaction_lines` PK. |
| Product vs non-product classification (D-002-05) | **FAIL (revise)** | The category structure is sound. The code list is incomplete and unknown codes default to product (§M-1). | Rework as a full inventory of every observed code (§10). Unknown or unmapped codes → `unclassified`, which fails the contract test. Add description-level exceptions such as `23444` "Next Day Carriage". Owner decides `ADJUST*`, `TEST*`, `M`, `D`, `CRUK`, `PADS`, `B`, `S`. |
| Gross vs net revenue (D-002-06) | **PASS WITH CONDITIONS** | Gross product as the primary behavioural metric is defensible, and net is biased by unlinkable and left-truncated returns (§M-6). Prohibiting an unqualified `revenue` field is correct. | Exact decimal at ≥3 dp, not integer pence. Add `gross_product_revenue_all`. Define handling of negative-net and returns-only customers. Use the parity tolerances from DS-001 §7. |
| 12-month acquisition-proxy look-back (D-002-07) | **PASS WITH CONDITIONS** | 12 months is the most conservative option available, and the proposed terminology is correct. Misclassification is still material and cohort-dependent (§M-2). | Publish the pseudo-boundary misclassification table with every acquisition-proxy result. Carry `observed_lookback_days` per customer. Run a sensitivity restricted to cohorts with ≥18 months observed look-back. Never compare early and late cohorts without a caveat. |
| 365-day active window (D-002-08) | **PASS WITH CONDITIONS** | Supported by return-by-recency evidence (§M-4), though not by the gap statistic cited. | Add `active_window_complete` (T ≥ 2010-12-01). Canonical snapshots and model anchors use complete windows only, unless a study pre-registers otherwise. Replace the cited evidence. |
| Separate historical inactivity from future lapse (D-002-09) | **PASS** | Removes a real conflation between the KPI document and `src/churn_prediction.py`, which also uses an inclusive endpoint. Half-open windows are correct. | Define the `inactive_<d>d_at_T` population. State the product-only label semantics. |

**Additional decisions not raised by Codex**

| New decision | Recommendation |
| --- | --- |
| D-002-10 — Repeat-purchase occasion | Define `second_purchase` as the first order on a **later calendar day** than the first observed order. Keep invoice-level repeat as a sensitivity. Order identity remains customer × invoice. |
| D-002-11 — Label maturity convention | Adopt the date-level `C-TIME-5` rule (`normalize(T) + h ≤ normalize(D_end)`) everywhere, including acquisition horizons. |

---

## 6. Impact on the six research workstreams

One population and one revenue metric do not serve every workstream:

| Workstream | Supported by proposed contracts? | Additional or different definitions required |
| --- | --- | --- |
| **R1** Commercial performance and retention | **Partly** | All-customer revenue including unidentified (15.1% of gross positive), all-customer product revenue, a signed bridge, and non-overlapping YoY windows with the partial December 2011 disclosed. Acquisition-proxy cohort tables carry the misclassification disclosure and per-cohort observed look-back. The time-to-second-purchase survival analysis uses the D-002-10 occasion rule. |
| **R2** Customer segmentation | **Yes, with conditions** | Population = active customers at T with a **complete** 365-day window. Monetary = trailing-365d gross product revenue with net as a sensitivity. All thresholds fitted at T. One canonical anchor (or a stated set). The acquisition proxy is irrelevant here and must not filter the R2 population. |
| **R3** Lapse prediction | **Yes, but the evaluation split must change** | Complete-window anchors leave 10 mature month starts (2010-12-01 … 2011-09-01), so the evaluation protocol's 6-month burn-in and its 2010-06 … 2011-04 development window are inconsistent with D-002-08 (§M-3). Development, purge and holdout must be re-planned in the R3 pre-registration. The label is product-only `no_purchase_next_90d` over `[T, T+90d)`. |
| **R4** Customer value and forecasting | **Yes, with conditions** | Fixed-horizon gross product and net product outcomes, with an explicit treatment for negative or returns-only customers. 180-day labels mature only up to the 2011-06-01 anchor. "Historical value" is labelled as left-truncated observed value. Aggregate forecasting uses all-customer revenue, not identifiable revenue. Lifetime CLV remains unsupported. |
| **R5** Experimentation design and simulation | **Partly** | The acquisition-proxy frame is small: 1,016 customers mature at 90 days. A 50/50 split at 42% baseline, α = 0.05 and 80% power gives an MDE of about 8.7 percentage points. R5 should allow other eligibility frames, for example active-customer win-back on complete-window anchors, and must use the D-002-10 occasion rule for conversion outcomes. This is acceptable for a simulation and design study, not for effect claims. |
| **R6** pandas / dbt / Spark parity | **Yes, with conditions** | Line IDs materialised at ingestion and consumed, not recomputed (§M-7). Taxonomy as a versioned seed table shared by every engine. Exact decimals or the DS-001 §7 relative tolerances. The overlap rule implemented once (pandas reference) and mirrored by reading the materialised `source_block_id`, not by re-deriving row order in Spark. Spark remains unverified without a JDK. |

---

## 7. Missing tests and safeguards

Required in the contract-encoding task. None was implemented here.

**Source integrity**

1. Source SHA-256 assertion before any correction is applied; fail closed on mismatch.
2. Exactly one chronological reset, at the asserted row; zero block-1 rows after 2010-12-09; zero block-2 rows before 2010-12-01.
3. Exact multiset equality of each overlap copy with V1 using Counter or a sorted frame, not only a 64-bit hash. Corrected row count = 1,044,848. Corrected V2 versus "V2 pre-V1 + V1" differs by exactly the one `POST` row.

**Line identity**

4. `(source_sha256, source_row_number)` unique and contiguous from 0; row count equals physical lines − 1; no embedded newlines; IDs identical across two ingestions and across engines.

**Taxonomy**

5. Every observed stock code maps to a category, and `unclassified` = 0 rows. Includes a fixture with a new unseen code (must fail) and a fixture for description exceptions such as `23444` "Next Day Carriage".

**Revenue**

6. Revenue bridge identities in exact decimal: product + non-product = identifiable gross; gross + signed adjustments = net; per-category totals; at least one 3-dp price fixture.

**Time and windows**

7. Boundary fixtures for half-open windows at T, T+h−ε, T+h and D_end, with date-level maturity.
8. Truncation test for snapshots (DS-001 `C-SNAP`) and an `active_window_complete` flag test.

**Customer histories**

9. A pseudo-boundary misclassification report generated by code, not by hand.
10. A same-day second-order fixture for the D-002-10 rule.
11. Population-change report for current vs product-only rules (5,878 → 5,861 customers; 36,969 → 36,639 orders).

**Governance**

12. A guard that no canonical dataset contains a column named exactly `revenue` or `acquisition_known`.
13. Evidence-script hardening for the addendum: assert the SHA and multiset equality, include the gap and sorted-equality checks, use a fixed `D_START` constant, and use Decimal sums.

---

## 8. Blocking and non-blocking findings

| ID | Severity | Finding | Evidence | Why it matters | Recommended correction | Blocks owner approval | Blocks Phase 3 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| F-01 | **High** | Taxonomy incomplete; unknown codes default to product | §M-1: `ADJUST`, `ADJUST2`, `TEST001/002`, `23444` carry GBP 5,695.57 | Test and adjustment lines enter customer value; a fail-open contract hides future codes | Full code inventory; `unclassified` fails; owner rules per code | **Yes**, for D-002-05 only (the category structure can be approved) | **Yes** |
| F-02 | **High** | Acquisition-proxy misclassification unquantified and cohort-dependent | §M-2: lower bound 3.0–13.6% at L = 12 | False acquisition claims; confounded cohort trends; R5 eligibility | Mandatory misclassification disclosure, `observed_lookback_days`, late-cohort sensitivity | No, if approval includes these conditions | No for the foundation; **yes** for any R1/R5 acquisition claim |
| F-03 | **High** | 365-day active window truncated before 2010-12-01; conflicts with R3 split | §M-3 table | Inconsistent eligibility; development and holdout not comparable; leakage-free but biased features | `active_window_complete` flag; complete-window anchors; redo R3 split in pre-registration | No, if conditioned | **Yes**, for the snapshot contract |
| F-04 | Medium | Same-day multi-invoice counted as second purchase | §M-5: 29 of 430 repeaters (12m) | Inflates repeat rate, `C-T2` and R5 outcomes | New D-002-10 occasion rule | **Yes**, needs a new owner decision | **Yes**, for `C-REPEAT` / `C-T2` encoding |
| F-05 | Medium | Wrong statistic cited for the 365-day window | §M-4 | Weak justification, though the conclusion holds | Replace with return-by-recency evidence | No | No |
| F-06 | Medium | Net product biased by unlinkable / left-truncated returns | §M-6: 33 returns-only, 37 negative-net, GBP −39,466 in first 3 months | Incorrect revenue attribution in R4 | Define negative / returns-only treatment; keep gross primary | No | No (R4 pre-registration) |
| F-07 | Medium | Line-identity spec incomplete for multi-engine use | §M-7 | Unstable IDs and broken parity if engines recompute row order | Add base/header, single assignment, materialisation rules | No, if conditioned | **Yes**, for contract encoding |
| F-08 | Medium | Evidence script fail-open; some evidence not scripted | §M-8; N-5 | A changed source could silently pass; evidence not fully reproducible | Harden script in the addendum (§7.13) | No | No |
| F-09 | Medium | DS-001 documents contradict DS-002 ("22,844 duplicates", "deduplicated", `acquisition_known`, occurrence-index PK) | N-4; DS-001 contracts §4–5 | Risk of implementing superseded definitions | Record supersession in the decision log when decisions are approved | No | **Yes**, until superseded |
| F-10 | Low | Maturity convention differs from `C-TIME-5` | N-2: 1,252 vs 1,258 | Inconsistent eligibility counts across studies | D-002-11 date-level rule | No | Yes (trivial) |
| F-11 | Low | Currency precision (3-dp prices) | N-1 | Integer-pence contracts would be inexact | Exact decimal ≥ 3 dp | No | No |
| F-12 | Low | Product-only population change not reported | N-3 | Small undisclosed selection effect | Disclose in contract and tests | No | No |
| F-13 | Low | R1 lacks all-customer product revenue; `inactive` denominator undefined | §M-8 | Incorrect commercial totals; trivial inactivity | Add fields and definitions | No | No |

---

## 9. Recommended owner decisions

| Decision | Recommendation |
| --- | --- |
| **P-01 / D-002-01** Canonical dataset | **Approve** corrected V2 (`v2c`) as canonical; V1 is the legacy / golden comparison. |
| **P-01b / D-002-02** Overlap correction | **Approve** with the fail-closed conditions in §5. |
| **P-09a / D-002-03** Incidental repeats | **Approve** retain-and-flag with a mandatory sensitivity. |
| **D-002-04** Line identity | **Approve** with the §M-7 additions. |
| **P-09b / D-002-05** Taxonomy | **Approve the category structure only.** Request a revised full code inventory before approving the mapping. Decide `M`, `D`, `CRUK`, `PADS`, `B`, `S`, `ADJUST`, `ADJUST2`, `TEST001`, `TEST002` and `23444` "Next Day Carriage". |
| **P-09c / D-002-06** Revenue fields | **Approve** the field family and gross product as the primary behavioural metric. Add `gross_product_revenue_all` and exact-decimal precision. |
| **P-17a / D-002-07** Acquisition proxy | **Approve** 12 months and the revised terminology, **conditional on** the misclassification disclosure, the `observed_lookback_days` field and the late-cohort sensitivity. |
| **P-17b / D-002-08** Active window | **Approve** 365 days **conditional on** `active_window_complete` and complete-window canonical anchors. Instruct that the R3 split be revised in pre-registration. |
| **D-002-09** Lapse terminology | **Approve** `inactive_<d>d_at_T` and `no_purchase_next_<h>d`, with half-open windows and the inactivity population defined. |
| **D-002-10 (new)** Repeat-purchase occasion | **Decide.** Recommendation: later-calendar-day rule as primary; invoice-level as sensitivity. |
| **D-002-11 (new)** Maturity | **Approve** the date-level `C-TIME-5` convention everywhere. |
| P-16, P-03, R2/R4/R5 method choices, Spark | **Defer**, as Codex proposed. Deferral is safe. |

---

## 10. Exact requirements for closing COMMERCIAL-DS-002

COMMERCIAL-DS-002 can be closed when all of the following are true:

1. **Owner decisions recorded** in `COMMERCIAL_DS_001_DECISION_LOG.md` for D-002-01 through D-002-11, with the conditions in §9 written into the decision text.
2. **Taxonomy addendum (read-only, Codex).** A complete inventory of every stock code observed in corrected V2 and V1, with row counts and valid, negative and zero-value revenue. It must include description-based exceptions found within numeric codes (at least `23444` "Next Day Carriage" and the "adjustment" descriptions on numeric codes). Each code gets a proposed category, with an explicit `unclassified` default that fails the contract test. The owner then approves the mapping.
3. **Evidence addendum (read-only, Codex)** adding to the audit:
   - (a) the pseudo-boundary misclassification table (§M-2);
   - (b) the return-by-recency table replacing the gap-only justification (§M-4);
   - (c) the anchor completeness table (§M-3);
   - (d) same-day second-order counts (§M-5);
   - (e) product-only population counts (N-3);
   - (f) left-truncated return figures (§M-6).
4. **Script hardening** in the evidence script, still writing only to stdout:
   - SHA assertion;
   - fail-on-inequality multiset checks;
   - the gap, sorted-equality, `POST`-row and V1 full-period repeat checks moved into the script;
   - fixed `D_START`;
   - Decimal or tolerance-checked sums;
   - date-level maturity.
5. **Supersession note.** The decision log records that DS-002 decisions supersede the DS-001 `C-ACQ` `acquisition_known` field, the `transaction_lines` occurrence-index key, "V2 (deduplicated)" wording and the "22,844 exact duplicates" statements. DS-001 text may be annotated rather than rewritten, per CD-07.
6. **Evaluation-protocol flag.** The decision log or protocol notes that the R3 reference split must be revised for complete-window anchors before R3 pre-registration.
7. **Re-review.** An independent check of items 2–4, which can be lightweight.

Once items 1–7 are complete, the next bounded task is creating `contracts/business_definitions.yml` with the synthetic and real-data tests listed in §7. **Phase 3 stays unauthorised** until that artifact passes its own independent review.

---

## Working-tree verification

`git status --short --branch` at the end of the review:

```text
## main...origin/main [ahead 1]
?? .vscode/
?? PROJECT_TECHNICAL_HANDOVER.md
?? docs/recovery/
```

- `git diff --stat` is empty, so no tracked file was modified.
- The only file created in the repository is this review.
- No `__pycache__` was left in `docs/recovery/`.
- Independent scripts and the captured Codex JSON were kept in the session scratchpad outside the repository.
- Nothing was committed or pushed.

---

**HANDOVER FOR CHATGPT — OWNER DECISION GATE**

**Numerical evidence: PASS.** All eleven COMMERCIAL-DS-002 findings reproduce exactly using an independent parser, Decimal arithmetic and exact multisets. The V2 defect is exactly one duplicated 22,523-row source block, GBP 311,878.00 of identifiable revenue. 22,844 is a diagnostic count, not a removal count.

**Safe to approve now:**

- corrected V2 as canonical (P-01);
- the source-boundary overlap correction with fail-closed checks (P-01b);
- retain-and-flag for incidental repeats;
- `(source_sha256, source_row_number)` line identity with the materialisation conditions;
- the gross and net revenue field family with gross product as the primary metric;
- the split between inactivity status and future non-purchase label;
- the date-level maturity rule.

**Safe to approve with explicit conditions:**

- **12-month acquisition proxy.** Mandatory misclassification disclosure (empirical lower bound 3–14%, cohort-dependent), per-customer observed look-back and a late-cohort sensitivity.
- **365-day active window.** `active_window_complete` flag, complete-window anchors only, and an R3 split redesign at pre-registration.

**Requires revision before approval:**

- **Non-product taxonomy mapping.** It is incomplete (`ADJUST`, `ADJUST2`, `TEST001/002`, `23444` "Next Day Carriage") and must fail closed on unknown codes. The owner may approve the category structure now.
- **New decision D-002-10.** Same-day split invoices currently count as second purchases, so the repeat-purchase occasion rule must be decided.

**May Codex proceed?** Yes, to one bounded, read-only task: **COMMERCIAL-DS-002A**, the taxonomy inventory, evidence addendum, script hardening and supersession notes in §10 items 2–5. Codex must not author `contracts/business_definitions.yml`, change pipelines or begin Phase 3 until the owner has recorded the decisions and the addendum has passed a light independent re-review. Phase 3 remains **not authorised**.
