# COMMERCIAL-DS-002 — Data Foundation Audit

**Status:** Evidence and decision proposal only. No raw data, existing pipeline, business logic, model, report, dependency or generated output was changed.

**Audit date:** 2026-10-30<br>
**Repository:** `main` at `1b293c2`, one commit ahead of `origin/main` at the start of this task<br>
**Evidence class:** Numbers in this document are **Observed** unless explicitly labelled otherwise.

## 1. Executive findings

1. **The V2 overlap defect is verified and precisely bounded.** V2 contains two exact full-row multisets of the 22,523 V1 rows dated 1–9 December 2010. Each copy contains GBP 311,878.00 of current identifiable gross revenue. The combined window has 45,046 rows and GBP 623,756.00.
2. **The correct removal count is 22,523, not 22,844.** `22,844` is the count returned by `DataFrame.duplicated()` in the combined window. It includes 321 repeats already present within the source copy. Removing 22,844 rows would over-remove legitimate-or-ambiguous source repetitions.
3. **The overlap is a duplicated source block, not evidence for global full-row deduplication.** V2 has one chronological reset at zero-based row 525,461, where a second source-year block restarts on 1 December 2010. The corrected source still contains 11,491 excess exact-repeat rows outside the overlap. Their source truth cannot be determined because no transaction-line identifier exists.
4. **The narrow correction changes revenue but not orders or customers.** Removing the first block's overlap removes 22,523 rows, 14,504 current-valid lines, GBP 438,852.65 gross-positive revenue, GBP 377,488.45 net transactional revenue, GBP 311,878.00 identifiable gross revenue and GBP 309,523.75 identifiable gross product revenue. Valid customers remain 5,878 and valid invoices remain 36,969.
5. **V1 and the second V2 block agree everywhere else except one row.** V2 has one additional line: invoice `581587`, stock code `POST`, quantity 1, GBP 18.00, customer `12680`, France, at 2011-12-09 12:50. It is non-product postage. Therefore the corrected V2 is one row and GBP 18 identifiable gross revenue above “V2 before 2010-12-01 + V1”, while identifiable gross product revenue is identical.
6. **V1 left-censoring is severe.** Under current valid-line logic, 4,266 customers are observed before V1 begins; 2,726 of V1's 4,338 customers (62.84%) had already purchased. Under the proposed product-only policy, the corresponding values are 4,249 and 2,722 of 4,334 (62.81%). Current V1 cohort logic therefore mislabels those returning customers as newly observed.
7. **A 12-month look-back is the most defensible primary acquisition proxy, but it does not prove first-ever purchase.** V2 supplies 365 calendar days before V1 starts. Under product-only lines, 1,612 customers across 13 first-observed cohort months qualify after a 12-month burn-in. The field proposed as `acquisition_known` should instead state `qualifying_lookback_observed`; customers can still have purchases before V2 begins.
8. **Customer revenue needs multiple explicit fields.** On corrected V2, current identifiable gross revenue is GBP 17,431,551.18. Of this, GBP 302,114.63 is on the proposed non-product-code list. Identifiable gross product revenue is GBP 17,129,436.55 and identified product returns/cancellations are GBP -714,532.55, giving GBP 16,414,904.00 identifiable net product revenue. These are different measures and must not share the label `revenue`.
9. **The foundation is not yet approved for Phase 3.** Evidence supports P-01 and a source-boundary form of P-01b. P-09 and P-17 need owner decisions. The proposed claim that a 12-month burn-in makes acquisition “known” should be revised before approval.

## 2. Reproduction methodology

### 2.1 Sources and hashes

| Source | Rows | Observed period | SHA-256 |
| --- | ---: | --- | --- |
| `data/raw/Online Retail.xlsx` (V1) | 541,909 | 2010-12-01 08:26 to 2011-12-09 12:50 | `43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d` |
| `data/raw/online_retail_II.csv` (V2) | 1,067,371 | 2009-12-01 07:45 to 2011-12-09 12:50 | `32569a66f3842a82b0d8c4d63b263c5d98a76bde5d1f65c6c01bf457e541d3a9` |

The bounded script [COMMERCIAL_DS_002_ANALYSIS.py](COMMERCIAL_DS_002_ANALYSIS.py) reads the raw files, performs in-memory comparisons and emits JSON to stdout. It writes no datasets.

### 2.2 Comparison protocol

- V2 aliases were normalised using the repository mapping: `Invoice → InvoiceNo`, `Price → UnitPrice`, `Customer ID → CustomerID` (`src/data_loading.py:15-19`).
- Comparisons used the eight raw fields: invoice, stock code, description, quantity, timestamp, unit price, customer ID and country.
- Null strings were normalised to a sentinel; customer IDs were normalised numerically; timestamps and numeric values were compared exactly.
- Row multiplicities were compared, not just set membership. A separate sorted full-row assertion confirmed both 22,523-row overlap copies exactly equal the V1 overlap, including duplicate multiplicities.
- The V2 source boundary was detected from the only negative timestamp difference. The first block has 525,461 rows; the second has 541,910.
- Revenue definitions used the current flags in `src/cleaning.py:34-68`, plus a separate product-only view using the proposed P-09 code list.
- Customer histories used invoice-level orders grouped by customer and invoice, consistent with `src/customer_metrics.py:39-51`.

### 2.3 Scope controls

- Raw files were opened read-only and were not modified.
- No existing pipeline or notebook was executed into repository output paths.
- No derived dataset was retained. `/tmp/commercial_ds_002_evidence.json` was a temporary stdout capture only.
- The audit script is isolated from `src/`, dbt and Spark and does not alter their behaviour.

## 3. V1/V2 overlap analysis

### 3.1 Physical structure

V2 is a concatenation of two chronological source blocks:

| Block | Zero-based rows | Period | Rows |
| --- | --- | --- | ---: |
| First source-year block | 0–525,460 | 2009-12-01 to 2010-12-09 | 525,461 |
| Second source-year block | 525,461–1,067,370 | 2010-12-01 to 2011-12-09 | 541,910 |

The only chronological reset is at zero-based raw row 525,461 (one-based data row 525,462). This is independent evidence of two concatenated source-year blocks.

### 3.2 Exact overlap reconciliation

| Comparison for 2010-12-01 through 2010-12-09 | Rows | Current valid lines | Customers | Orders | Identifiable gross revenue |
| --- | ---: | ---: | ---: | ---: | ---: |
| V1 | 22,523 | 14,504 | 573 | 776 | GBP 311,878.00 |
| V2 first block | 22,523 | 14,504 | 573 | 776 | GBP 311,878.00 |
| V2 second block | 22,523 | 14,504 | 573 | 776 | GBP 311,878.00 |
| V2 combined | 45,046 | 29,008 | 573 | 776 | GBP 623,756.00 |

Both V2 block comparisons against V1 are exact full-row multiset matches. Every raw row and every multiplicity reconcile.

### 3.3 V1/V2 agreement outside the overlap

The full second V2 block has 541,910 rows; V1 has 541,909. Multiset comparison finds exactly one row only in V2 and none only in V1:

| Invoice | Stock code | Description | Quantity | Timestamp | Price | Customer | Country |
| --- | --- | --- | ---: | --- | ---: | ---: | --- |
| 581587 | POST | POSTAGE | 1 | 2011-12-09 12:50 | GBP 18.00 | 12680 | France |

Therefore:

- all V1 rows are contained in the second V2 block at the same multiplicity;
- the only difference outside 1–9 December 2010 is the additional GBP 18 postage row at the dataset end;
- product-only revenue and product customer metrics reconcile exactly to V1 over the V1 period;
- current identifiable revenue differs by GBP 18 because current logic includes `POST`.

## 4. Duplication analysis

### 4.1 Why `duplicated()` returns 22,844

Each individual overlap copy already contains 321 excess exact-repeat rows. When two identical multisets are concatenated, pandas marks:

- the 22,523 rows in the second copy as repeats of the first copy; plus
- 321 within-first-copy repeats.

The result is 22,844. It is a diagnostic count, not the number of rows that should be removed. The source-block correction removes exactly one 22,523-row copy and retains the 321 multiplicities present in V1.

### 4.2 Candidate duplicate keys

| Candidate | Assessment |
| --- | --- |
| Full eight-field row | Sufficient to prove the two overlap multisets are identical. Not a safe global deletion key because identical business lines can legitimately occur more than once and the sources have no line sequence. |
| Invoice + stock + quantity + timestamp + price + customer + country | Almost the same ambiguity; excluding description adds only two more excess repeats outside the overlap in corrected V2. It is not unique. |
| Invoice + stock | Not unique; the same product can appear on repeated invoice lines. |
| Invoice | Order-level key, not line-level key. |
| Source file + source row number | The only defensible raw-line identity. It preserves every source observation. |

Recommended raw primary key: `(source_sha256, source_row_number)`. Recommended canonical line ID: a deterministic encoding or hash of that raw key. Business-field hashes may be recorded for reconciliation, but must not replace source identity.

### 4.3 Repeated lines outside the overlap

| Dataset/view | Rows outside overlap | Excess exact repeats | Rows in repeat groups | Invoices containing repeats | Current-valid repeat revenue if one of each repeat were removed |
| --- | ---: | ---: | ---: | ---: | ---: |
| V1 | 519,386 | 4,947 | 9,530 | 1,849 | GBP 22,977.38 |
| Corrected V2 | 1,022,325 | 11,491 | 22,196 | 4,303 | GBP 55,525.28 |

Across all V1 dates, the existing audit's value is reproduced: 5,268 excess exact rows, including 5,192 current-valid rows and GBP 24,199.01 current identifiable revenue.

These repeats are confined to individual invoices, but there is no source line number or other field that distinguishes a duplicated export record from two genuinely repeated transaction lines. They must remain until a stronger source rule exists.

### 4.4 Recommended duplicate policy

1. Apply a **dataset-specific overlap correction only** for the known V2 SHA.
2. Preserve raw source-row identity and a source-block identifier.
3. Remove the first source block's rows dated 2010-12-01 through 2010-12-09 inclusive; retain the complete second block.
4. Add `is_exact_repeat` and `exact_repeat_group_size` flags after the overlap correction.
5. Do not globally call `drop_duplicates` on business fields.
6. Publish a sensitivity showing metrics with incidental repeats retained versus one-per-full-row, but keep the retained view canonical unless the owner approves otherwise.

This is a recommendation under P-01b/P-09, not an implemented or approved policy.

## 5. Candidate correction impact

| Candidate | Rows | Current valid lines | Customers | Orders | Gross positive, all | Net transactional, all | Identifiable gross | Identifiable gross product |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Raw V2 | 1,067,371 | 805,549 | 5,878 | 36,969 | GBP 20,972,594.57 | GBP 19,445,926.71 | GBP 17,743,429.18 | GBP 17,438,960.30 |
| Drop first-block overlap; keep second block | 1,044,848 | 791,045 | 5,878 | 36,969 | GBP 20,533,741.92 | GBP 19,068,438.26 | GBP 17,431,551.18 | GBP 17,129,436.55 |
| Drop second-block overlap; keep first block | 1,044,848 | 791,045 | 5,878 | 36,969 | GBP 20,533,741.92 | GBP 19,068,438.26 | GBP 17,431,551.18 | GBP 17,129,436.55 |
| V2 before 2010-12-01 + V1 | 1,044,847 | 791,044 | 5,878 | 36,969 | GBP 20,533,723.92 | GBP 19,068,420.26 | GBP 17,431,533.18 | GBP 17,129,436.55 |
| Global full-row dedupe | 1,033,036 | 779,425 | 5,878 | 36,969 | GBP 20,476,260.45 | GBP 19,014,209.84 | GBP 17,374,804.27 | GBP 17,073,078.29 |

The two source-block choices have identical aggregate values because the overlap copies are identical. Keeping the second block is preferable because it preserves the complete later source-year block and the one extra terminal postage row. The alternative “V2 before 2010-12-01 + V1” is scientifically equivalent for product metrics, but creates a composite source and drops a real V2 record.

A global full-row dedupe removes 11,812 additional rows and GBP 56,746.91 identifiable gross revenue relative to the narrow correction. There is no source evidence for that removal.

## 6. Customer-history analysis

### 6.1 V1 left-censoring

| Measure | Current valid-line logic | Proposed product-only logic |
| --- | ---: | ---: |
| Customers observed before V1 starts | 4,266 | 4,249 |
| Customers observed during the V1 period | 4,338 | 4,334 |
| V1-period customers with prior V2 history | 2,726 | 2,722 |
| Share with prior history | 62.84% | 62.81% |
| First observed during V1 | 1,612 | 1,612 |

The current V1 retention matrix assigns every customer to their first V1 month (`src/customer_metrics.py:145-163`). It therefore treats 2,726 known returning customers as first observed/new. The proposed product-only policy changes the numerator by four, not the conclusion.

Selected current-logic cohort contamination:

| V1 first-seen cohort | Customers | Known prior V2 history | Share |
| --- | ---: | ---: | ---: |
| 2010-12 | 885 | 809 | 91.41% |
| 2011-01 | 417 | 346 | 82.97% |
| 2011-06 | 242 | 134 | 55.37% |
| 2011-09 | 299 | 110 | 36.79% |
| 2011-12 | 41 | 13 | 31.71% |

V1 is unsuitable for first-purchase, acquisition, acquisition-cohort or first-to-second-purchase claims. V1 can still support legacy descriptive purchasing metrics when labelled as left-truncated.

### 6.2 Historical look-back available in V2

V2 begins on 2009-12-01 and V1 begins on 2010-12-01. It supplies 365 complete calendar days before the V1 boundary. For a customer first observed later in V1, the observable no-prior-purchase period is longer. This does not reveal purchases before 2009-12-01.

Required terminology:

| Term | Meaning |
| --- | --- |
| First-ever purchase | Not observable from these data. Must not be claimed. |
| First observed purchase | Earliest valid product order in the selected dataset. |
| First observed purchase after a qualifying look-back | First observed purchase occurring after at least L months of observable history with no earlier observed order. This is the recommended acquisition proxy. |
| Returning customer | At a boundary or order date, a customer with at least one earlier observed valid product order. |

### 6.3 Candidate look-back policies

The table uses corrected V2 and product-only orders. “Second purchase” means a second observed order before the half-open horizon end. Retention is a raw weighted share among customers whose whole target month is observable; it is not a Kaplan–Meier estimate.

| Look-back | Earliest cohort | Eligible customers | Cohort months | 60d mature / repeat rate | 90d mature / repeat rate | M1 mature / retention | M6 mature / retention | M12 mature / retention |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 3 months | 2010-03 | 4,152 | 22 | 3,792 / 33.86% | 3,556 / 41.51% | 3,933 / 20.72% | 3,209 / 17.39% | 2,540 / 18.27% |
| 6 months | 2010-06 | 3,166 | 19 | 2,806 / 34.68% | 2,570 / 41.75% | 2,947 / 21.55% | 2,223 / 14.17% | 1,554 / 19.05% |
| 9 months | 2010-09 | 2,552 | 16 | 2,192 / 35.08% | 1,956 / 41.00% | 2,333 / 22.59% | 1,609 / 15.16% | 940 / 22.13% |
| 12 months | 2010-12 | 1,612 | 13 | 1,252 / 34.98% | 1,016 / 42.32% | 1,393 / 22.83% | 669 / 17.94% | 0 / n.a. |

Interpretation:

- Shorter look-backs materially increase sample size but move the earliest cohorts closer to the left boundary and increase the risk that “first observed” is a returning customer after a long unobserved gap.
- The raw 60/90-day repeat rates are fairly stable across these policies, but the populations and calendar periods differ. The comparison is descriptive, not evidence that look-back length causes a rate change.
- A 12-month primary policy is conservative and aligns the acquisition-proxy population with the V1 period. It leaves no fully observed month-12 retention cohort because the dataset ends during December 2011.
- Second-purchase analyses must restrict to label-mature customers or use survival analysis for right-censoring. A raw rate over all 1,612 eligible customers would bias recent cohorts downward.
- Cohort tables must show recent or partial cells as null, not zero, and should disclose the partial final month.

### 6.4 Active-history look-back

On corrected V2 product orders, observed inter-order gaps have median 25.0 days, p75 62.1, p90 135.9 and p95 207.0; 1.07% exceed 365 days. A 365-day active look-back is therefore a defensible operational eligibility rule that excludes very long-inactive customers while covering 98.93% of observed repeat gaps. It remains a policy choice under P-17, not a discovered natural boundary.

## 7. Revenue-definition audit

### 7.1 Corrected V2 bridge

| Measure | Amount |
| --- | ---: |
| Gross positive revenue, all customers and codes | GBP 20,533,741.92 |
| Refund/cancellation revenue, all customers and codes | GBP -1,465,303.66 |
| Net transactional revenue, all customers and codes | GBP 19,068,438.26 |
| Identifiable gross revenue, current logic | GBP 17,431,551.18 |
| Identifiable non-product positive revenue | GBP 302,114.63 |
| Identifiable gross product revenue | GBP 17,129,436.55 |
| Identified product refund/cancellation revenue | GBP -714,532.55 |
| Identifiable net product revenue | GBP 16,414,904.00 |

The proposed non-product list is dominated by `M` manual entries (GBP 152,166.32 positive; GBP -337,491.80 identified negative), `POST` postage (GBP 124,648.04 positive; GBP -14,309.53 negative), `C2` carriage (GBP 12,546 positive) and `DOT` postage (GBP 11,906.36 positive). `D` discount and `CRUK` commission are predominantly negative. A single “exclude non-product” switch would lose these commercial distinctions.

### 7.2 Recommended revenue fields

- `gross_positive_revenue_all`: current gross-positive definition, all customers and line types.
- `net_transactional_revenue_all`: gross-positive plus signed refund/cancellation lines; preserve separate adjustment components.
- `identifiable_gross_product_revenue`: positive product lines with a customer ID; primary monetary feature for purchase behaviour.
- `identifiable_net_product_revenue`: gross product revenue plus identified product returns; use for realised customer value sensitivity.
- Separate `shipping_revenue`, `manual_adjustment_revenue`, `fee_revenue`, `discount_revenue` and `other_non_product_revenue` fields.
- Never publish an unqualified field named only `revenue` in a canonical dataset.

P-09 should approve the field family and the main study metric, not erase the other measures. Gross product revenue is recommended for RFM/frequency behaviour; R1/R4 must report net and bridge components separately.

## 8. Canonical-definition audit

“Approval” identifies whether owner action is required before implementation.

| Definition | Current and conflicting implementations | Proposed canonical definition | Evidence / impact | Required tests | Status / approval |
| --- | --- | --- | --- | --- | --- |
| Transaction-line identity | No raw line key. Proposed `C-LINE` hashes business fields plus occurrence index. | Raw key `(source_sha256, source_row_number)`; canonical `line_id` derived from it. Keep a business-field hash separately. | Business rows are not unique; an occurrence index after sorting is not stable provenance. | Raw-key uniqueness; deterministic IDs; source count reconciliation. | **RECOMMENDED; owner approval.** |
| Duplicate transaction | `src/cleaning.py:78-80` counts full-row repeats but retains them. No other policy. | Distinguish `duplicate_source_block` from `is_exact_repeat`. Remove only the verified V2 source-block copy; retain and flag incidental repeats. | Global dedupe removes a further GBP 56,746.91 identifiable gross revenue without source evidence. | Exact overlap multiset; 22,523 removal; outside repeats retained and flagged. | **RECOMMENDED / BLOCKED on P-01b, P-09.** |
| Order identity | pandas/dbt group customer × invoice (`src/customer_metrics.py:39-45`; `dbt/models/intermediate/int_customer_orders.sql:11-20`). Proposed text sometimes says invoice alone. | `order_id = InvoiceNo` string after validation that one invoice maps to one customer; physical key `(customer_id, order_id)` for aggregation. | Corrected V2 has zero identified invoices mapped to multiple customers and zero customer-invoice keys mapped to multiple countries. | One customer per invoice; non-null key; line-to-order revenue reconciliation. | **VERIFIED with continuing validation; no change required.** |
| Customer identity | Integer `CustomerID`; missing excluded from customer metrics. | Integer source `CustomerID`; missing is unidentified, never imputed or joined. | Current logic is consistent (`src/cleaning.py:46,62-68`). | Cast safety; missing exclusion; no fabricated IDs. | **VERIFIED; no change required.** |
| Valid purchase | Positive quantity and price, non-cancel invoice, customer present; non-product included. | Valid identified **product** purchase line: current rule plus approved `line_type=product`, after overlap correction. Keep broader positive commercial-line flags. | Current customer revenue includes GBP 302,114.63 proposed non-product positive revenue. | Boundary tests; code taxonomy; revenue bridge; anonymous handling. | **RECOMMENDED / BLOCKED on P-09 taxonomy.** |
| Returns and cancellations | Negative quantity or `C*`; excluded from customer revenue and added to company net (`src/cleaning.py:38-45,84-90`). | Preserve signed line and flags. Attribute to observed customer when ID exists; do not claim original-order linkage. Separate product returns from other adjustments. | Original invoice linkage is absent; identified product returns are GBP -714,532.55. | Signed bridge; customer attribution; no false original-order join. | **RECOMMENDED; owner approval for presentation fields.** |
| Non-product stock codes | No implementation; all included. Proposed list combines postage, manual, fees, discounts and other. | Versioned mapping table with `line_type` and code-specific category. Product metrics exclude non-product; total bridge retains every category. | `M`, `POST`, `C2`, `DOT`, `D`, `CRUK` have materially different economics. | Every observed code mapped/defaulted; mapping totals; unknown-code alert. | **BLOCKED on P-09.** |
| Gross revenue | Current gross is all positive, priced, non-cancel lines, regardless of customer (`src/cleaning.py:81-88`). | `gross_positive_revenue_all = Σ quantity×price` for positive non-cancel lines; disclose inclusion of non-product and unidentified lines. | Current measure is reproducible and useful for the top bridge. | Sum identity; line inclusion boundaries. | **VERIFIED; clarify name.** |
| Net revenue | Current gross plus negative/cancel line revenue; negative-price positive-quantity adjustments are outside both components. | Signed commercial bridge with explicit gross, returns/cancellations, discounts/fees/manual and other adjustments; `net_transactional_revenue_all` must list included components. | Current arithmetic reconciles but does not fully classify every signed economic line. | Component exhaustiveness; bridge sum; negative-price fixtures. | **RECOMMENDED; owner approval.** |
| Identifiable customer revenue | Current valid positive revenue with CustomerID, gross of returns and including non-product. | Publish both identifiable gross product and identifiable net product revenue; never use an unqualified label. | GBP 17.432m current vs GBP 17.129m gross product vs GBP 16.415m net product. | Orders-to-lines reconciliation; gross/net separation. | **RECOMMENDED / BLOCKED on P-09.** |
| Customer recency | Notebook relative to max order date; dbt relative to 2011-12-10 (`dbt_project.yml:16`; `mart_customer_metrics.sql:32-33`); snapshots relative to T. | Whole elapsed days from last valid product order strictly before anchor T to normalised T. Every output carries `anchor_date`. | Current implementations differ by anchor and sometimes one day. | T boundary; same-day; no future order; anchor normalisation. | **RECOMMENDED; owner approval.** |
| Purchase frequency | Lifetime distinct invoices in current customer metrics; 365d orders in dbt CLV mart. | Explicit fields: `orders_observed_to_date` and `orders_trailing_<L>d`, each distinct canonical order IDs before T. | Existing `total_orders` is left-truncated and ambiguous. | Distinct-order count; window boundaries; snapshot truncation. | **RECOMMENDED; owner approval.** |
| Monetary value | Current lifetime gross identifiable revenue including non-product; dbt has 365d revenue. | Explicit gross product lifetime-observed and trailing-window fields; parallel net product fields. Primary RFM monetary = trailing-365d gross product revenue at T. | Prevents mixing behaviour with returns and left-truncated “lifetime” value. | Line/order/customer reconciliation; trailing boundary; net sensitivity. | **RECOMMENDED / BLOCKED on P-09/P-17.** |
| Customer acquisition proxy | KPI document calls first valid purchase “acquired” (`reports/kpi_definitions.md:134-140`). Proposed `C-ACQ` sets `acquisition_known`. | `first_observed_order`; `qualifying_lookback_months`; `acquisition_proxy=true` when first observed after L; `first_ever_known=false` for all customers. | Even 12 months cannot rule out a purchase before V2. | Look-back cutoff; prior-order exclusion; terminology/schema tests. | **RECOMMENDED / BLOCKED on P-17.** |
| Cohort assignment | Current first observed month for every customer (`src/customer_metrics.py:145-163`; dbt equivalent). | Calendar month of first observed valid product order, only for customers satisfying the approved look-back; label `acquisition_proxy_cohort`. | V1 misclassifies 62.8% as new. | Eligibility; month boundary; no ineligible cohort rows. | **RECOMMENDED / BLOCKED on P-17.** |
| Retention | Current later-month activity divided by cohort month, with absent cells omitted in pivot; documents call it acquisition retention. | For eligible proxy cohort, share with ≥1 valid product order in calendar month offset k; month 0 = 1; not-fully-observed cells null. | Corrects left/right-censoring labels; final month is partial. | k=0; [0,1]; full-month maturity; null vs zero. | **RECOMMENDED; owner approval.** |
| Lapse | Current report: no purchase for 90+ days (`reports/kpi_definitions.md:199-203`). Model: no order in next 90 days, with inclusive endpoint (`src/churn_prediction.py:130-133,187-188`). | Separate `inactive_<d>d_at_T` status from predictive `no_purchase_next_<h>d`; if retaining `lapse_h`, define active population and half-open `[T,T+h)`. | Existing word describes two different constructs; current inclusive endpoint conflicts with proposed time convention. | Endpoint T/T+h; active eligibility; maturity; status-vs-label naming. | **RECOMMENDED; owner approval.** |
| Observation windows | Mixed implicit calendar and inclusive model windows. | All event windows half-open. Feature history `<T`; outcomes `[T,T+h)`; calendar retention needs a complete target month. | Prevents double counting boundary events. | Exact boundary fixtures; timezone/naive timestamp contract. | **RECOMMENDED; owner approval of C-TIME.** |
| Prediction horizons | Lapse 90d; propensity 60d; proposed value 90/180d. | Horizon is part of every field name and manifest. Primary lapse 90d, 60/120 sensitivity; value 90/180d subject to study preregistration. | Avoids silent reuse across horizons. | Parameter/field consistency; horizon-specific maturity. | **RECOMMENDED; P-16 can defer to R1/R3.** |
| Label maturity | Current lapse excludes late snapshots indirectly; experiment marts do not enforce complete windows. | Mature iff full half-open outcome window is observed. Store `label_mature`; immature labels are null and excluded from training/readout. | Fixes experiment censoring and prevents current scores carrying known labels. | At/one-before/one-after data-end boundaries; null immature label. | **RECOMMENDED; owner approval of C-TIME.** |
| Customer feature snapshot | Current lapse includes every historically observed customer and lifetime features; timestamp start can inherit 08:26. No canonical general snapshot. | One row per customer × normalised anchor T for customers active in `[T-365d,T)`. Features use only `<T`; explicit lifetime-observed and trailing fields; labels separate. | Supports R2–R5 and removes stale/labelled scoring confusion. | Truncation equality; uniqueness; active look-back; no feature leakage; current-anchor label null. | **RECOMMENDED / BLOCKED on P-17 active policy.** |

## 9. Data-contract decision matrix

| Issue | Classification | Recommendation | Owner approval |
| --- | --- | --- | --- |
| V2 overlap existence and magnitude | **VERIFIED** | Accept the measured defect and impact. | No factual choice. |
| P-01 canonical dataset | **RECOMMENDED** | Corrected V2 (`v2c`) becomes canonical; V1 remains legacy/golden comparison. | **Required.** |
| P-01b correction method | **RECOMMENDED** | Source-boundary rule tied to V2 SHA; remove first-block overlap and keep the complete second block. | **Required.** |
| Global exact duplicates | **RECOMMENDED** | Keep and flag outside the verified source overlap; sensitivity only. | **Required under P-09.** |
| Raw/canonical line identity | **RECOMMENDED** | Source SHA + row number; do not use business fields as identity. | Required before contract encoding. |
| Invoice as order ID | **VERIFIED** | Use invoice string with one-customer invariant; aggregate key remains customer × invoice. | No change, but approve contract wording. |
| P-09 non-product taxonomy | **BLOCKED** | Versioned categories; exclude from product metrics, retain in total bridge. Decide treatment of `M`, `D`, `CRUK`, `PADS`, `B`, `S`. | **Required.** |
| P-09 customer monetary metric | **RECOMMENDED** | Gross product revenue primary for behaviour; net product revenue separate and mandatory for value reporting. | **Required.** |
| P-17 acquisition look-back | **RECOMMENDED** | 12 months primary; 6/9 sensitivity; call it an acquisition proxy, never known first-ever. | **Required.** |
| P-17 active look-back | **RECOMMENDED** | 365 days; covers 98.93% of observed product-order gaps; retain as policy parameter. | **Required.** |
| Lapse terminology/status vs label | **UNRESOLVED** | Split inactive status from future non-purchase label; owner chooses published names. | Required before model contract. |
| Interim segmentation P-03/Q-C6 | **UNRESOLVED, safe to defer** | Decide in Phase 3/R2; not needed to approve transaction foundation. | Later. |
| Lapse horizon P-16 | **UNRESOLVED, safe to defer** | Keep 90d proposal; confirm in R1/R3 preregistration. | Later. |

## 10. Downstream research impact

| Workstream | Contracts required | Effect of corrections | Feasibility / invalid outputs |
| --- | --- | --- | --- |
| R1 commercial analytics | Line identity, overlap rule, line types, all revenue fields, orders, acquisition proxy, cohorts, retention, windows | December 2010 and any total containing it fall by the amounts in §5. V1 cohorts cannot be called acquisition cohorts. | Feasible after approvals. `reports/v2_year_over_year_comparison.md` (GBP 9.22m current-year identifiable revenue), `reports/dataset_comparison_summary.md`, notebook 08/09 outputs and V2 processed metrics require regeneration. |
| R2 segmentation | Product orders, recency/frequency/monetary at T, snapshot active policy | Monetary values and thresholds change when overlap/non-product are corrected; point-in-time fields replace full-period values. | Feasible after foundation and snapshots. Existing notebook/dbt segment counts are historical and incompatible; they cannot be carried forward. |
| R3 lapse prediction | Active customer, point-in-time snapshot, half-open label, maturity, horizon | V2 adds history and more anchors; product-only orders slightly change features. Status/label naming and current inclusive endpoint must be resolved. | Feasible with conditions. Existing V1 B0 remains a legacy baseline; model claims and CRM scores are not canonical and must eventually be regenerated, not in this task. |
| R4 customer value / forecasting | Gross/net product revenue, fixed horizons, maturity, weekly series | Corrected V2 totals and early weekly series change; “historical CLV” must be labelled left-truncated observed value. | Fixed-horizon and aggregate forecasting remain feasible; lifetime CLV remains unsupported. Existing V2 revenue series/results require regeneration. |
| R5 experiments | Acquisition proxy, eligibility, product/net outcomes, full observation, one assignment rule | V1 eligibility is contaminated; V2 12m policy gives 1,612 product-only acquisition-proxy customers before horizon maturity filters. | Framework feasible; real effects unsupported. Existing experiment marts remain invalid for causal readout and use censored populations. |
| R6 pandas/dbt/Spark parity | Every approved key, flag, window and tolerance | New line IDs, source-block correction, product mapping and revenue fields become parity targets. | pandas/dbt feasible after Phase 3. Spark remains unverified without Java. Existing parity claims cover only the old V1 core. |

## 11. Existing results affected

The following are not regenerated here and must be treated as legacy until rebuilt from approved contracts:

- all V2 outputs under `data/processed/v2_online_retail_ii/` that include December 2010;
- `reports/v2_year_over_year_comparison.md` and its GBP 9.22m current-year value;
- `reports/dataset_comparison_summary.md` totals, customer revenue and any model trained on raw V2;
- notebook 08/09 figures and any downstream V2 Tableau export;
- all V1 acquisition, cohort, first-to-second-purchase, second-purchase propensity and experiment-eligibility results;
- customer segment/value outputs if the owner approves product-only monetary value;
- existing lapse/CRM results for canonical presentation, because their snapshot and label contracts conflict with the proposed definitions.

V1 deterministic audit results remain valid as **legacy results under the old contract**. They are not valid evidence of acquisition.

## 12. Limitations and unresolved questions

1. Source-sheet names are absent from the CSV. The block boundary is inferred from row order and the only chronological reset, then validated by exact V1 reconciliation. A future different file hash needs revalidation.
2. The sources have no raw line identifier. Incidental exact repeats cannot be adjudicated as error or legitimate repeated order lines.
3. Customer ID is anonymised; cross-dataset identity is assumed to be stable because exact rows reconcile, but cannot be verified externally.
4. V2 is itself left-censored at 2009-12-01. No look-back proves first-ever purchase.
5. December 2011 is partial. Calendar-month cohorts and forecasts must treat it accordingly.
6. The non-product list is evidence-supported but not complete as a business taxonomy. `M` manual entries are especially material and require owner approval.
7. Returns cannot reliably be linked to the original invoice. Customer-level net attribution can only use the customer ID on the return line.
8. Raw retention rates in §6 are descriptive and right-censoring restricted. R1 should use Kaplan–Meier for time to second purchase.
9. No owner decisions were marked approved; no canonical YAML was created.

## 13. Exact commands

Run from the repository root:

```bash
git status --short --branch
shasum -a 256 data/raw/'Online Retail.xlsx' data/raw/online_retail_II.csv
.venv/bin/python docs/recovery/COMMERCIAL_DS_002_ANALYSIS.py > /tmp/commercial_ds_002_evidence.json
jq '.overlap, .candidate_corrections, .customer_history_product_only' /tmp/commercial_ds_002_evidence.json
```

Exact sorted overlap assertion:

```bash
.venv/bin/python - <<'PY'
import pandas as pd
from docs.recovery.COMMERCIAL_DS_002_ANALYSIS import (
    CANONICAL_COLUMNS, load_sources, normalise_for_exact_comparison,
)
v1, v2 = load_sources()
reset = v2.index[v2.InvoiceDate.diff() < pd.Timedelta(0)][0]
start = pd.Timestamp('2010-12-01')
end = pd.Timestamp('2010-12-09 23:59:59.999999')
def canon(frame):
    return normalise_for_exact_comparison(frame).sort_values(
        CANONICAL_COLUMNS, kind='mergesort'
    ).reset_index(drop=True)
expected = canon(v1[v1.InvoiceDate.between(start, end)])
for block in (v2.iloc[:reset], v2.iloc[reset:]):
    observed = canon(block[block.InvoiceDate.between(start, end)])
    pd.testing.assert_frame_equal(expected, observed, check_dtype=True, check_exact=True)
print('two exact 22,523-row full-field multiset matches')
PY
```

The review handover records the verification commands run after authoring.
