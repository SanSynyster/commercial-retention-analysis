# COMMERCIAL-DS-001 — Data Contracts and Canonical Business Definitions

Part of the [recovery index](README.md). Used by the [research programme](COMMERCIAL_DS_001_RESEARCH_PROGRAMME.md), [architecture](COMMERCIAL_DS_001_ARCHITECTURE.md) and [evaluation protocol](COMMERCIAL_DS_001_EVALUATION_PROTOCOL.md).

**Status:** [PROPOSED]. These contracts do not yet exist in code. Current executable definitions (described in §1) remain in force until Phase 2/3 changes are approved and implemented. Contract IDs (`C-…`) are referenced across all recovery documents.

---

## 1. Current executable definitions (as-is) [VERIFIED]

| Concept | Current definition | Location |
| --- | --- | --- |
| Valid order line | `Quantity > 0 AND UnitPrice > 0 AND InvoiceNo NOT LIKE 'C%' AND CustomerID IS NOT NULL` | `src/cleaning.py:41-69`, notebook 01, `dbt/models/staging/stg_clean_transactions.sql` (consumes flag) |
| Order | customer × invoice, `sum(analytical_revenue) > 0`, `order_date = min(line timestamp)` | `src/customer_metrics.py` `build_customer_orders`; dbt `int_customer_orders`; Spark |
| Duplicates | Counted in the audit, **not removed** | `src/cleaning.py` `build_audit_summary` |
| Non-product codes | Included in revenue | none (no filter) |
| Refunds | Subtract from net transactional revenue; excluded from customer revenue | `src/cleaning.py` |
| Recency anchor | Notebook 04: max order date; dbt: var `analysis_as_of_date = 2011-12-10` | — |
| Lapse | No valid order in `[snapshot, snapshot + 90d]` (inclusive end) | `src/churn_prediction.py:187-188` |
| High value | Top 10% by revenue (rank-based in pandas; `quantile_cont ≥` in dbt) | notebook 04 / `mart_customer_segments.sql` |
| Segments / priority | Two incompatible schemes (notebook P1–P7, dbt P1–P5) | notebooks 04/07, dbt |

These are recorded so that every change in Phase 3 is an explicit, reviewable diff against the as-is behaviour.

---

## 2. Global conventions (proposed)

| ID | Convention |
| --- | --- |
| `C-TIME-1` | All timestamps are naive local times as provided by the source (UK). No timezone conversion. |
| `C-TIME-2` | **Dataset end** `D_end` = max(InvoiceDate) of the canonical dataset = 2011-12-09 12:50 [VERIFIED]. **Dataset start** `D_start` = 2009-12-01 (V2) / 2010-12-01 (V1). |
| `C-TIME-3` | Anchor dates are **midnight** (`normalize()`) on the stated day (fixes audit D-5). |
| `C-TIME-4` | Windows are half-open: history `[−∞, T)`, outcome `[T, T + h)`. |
| `C-TIME-5` | A label with horizon *h* at anchor *T* is **mature** iff `T + h ≤ D_end` (date-level comparison). Immature labels are never used for training or evaluation. |
| `C-KEY-1` | `customer_id` = integer CustomerID. Missing → unidentified (never imputed). |
| `C-KEY-2` | `order_id` = `InvoiceNo` as string. One order belongs to one customer (verify; flag violations). |
| `C-CUR-1` | Currency GBP. Revenue = `Quantity × UnitPrice`. No margin exists in the data; any margin is an assumption parameter. |
| `C-VER-1` | Each canonical dataset is written with a run manifest: git SHA, dirty flag, source file SHA-256, contract version, parameters, row counts, command, timestamp. |

---

## 3. Data-quality decisions

| ID | Topic | Proposed decision | Rationale | Status |
| --- | --- | --- | --- | --- |
| `C-DQ-1` | **V2 overlap duplication (1–9 Dec 2010)** | Remove the second copy of the overlapping sheet window. The method (row-multiplicity reconciliation against V1, or a source-sheet boundary rule) must be validated: after dedupe, V2 for 2010-12-01…2010-12-09 must reconcile to V1 within tolerance | [VERIFIED] V2 has exactly 2× V1 rows/revenue in that window | [PROPOSED] — owner approval (decision P-01b) |
| `C-DQ-2` | Exact duplicate lines elsewhere | Keep (the source system may legitimately repeat lines); flag `is_exact_duplicate`; report sensitivity (V1: 5,192 valid duplicate lines, GBP 24,199, 0.27%) | Can't distinguish error from legitimate repeat | [OPEN] P-09 |
| `C-DQ-3` | Non-product stock codes (`POST`, `DOT`, `M`, `C2`, `BANK CHARGES`, `AMAZONFEE`, `PADS`, `D`, `S`, `B`, `CRUK`) | Add `line_type ∈ {product, shipping, manual_adjustment, fee, discount, other}`. **Product revenue** excludes non-product. **Total revenue** includes all. Customer value metrics use product revenue | V1 ≈ GBP 150k (~1.7%) of customer revenue is non-product [VERIFIED] | [OPEN] P-09 |
| `C-DQ-4` | Refund attribution | Keep the line-level refund flag. Add `refund_revenue` per customer (returns linked by customer, not to the original invoice, since no invoice link exists). Customer "net revenue" = product revenue + refunds (negative) — a separate field, never mixed with gross | Original-invoice linkage not available | [PROPOSED] |
| `C-DQ-5` | Unidentified customers | Excluded from customer-level datasets; included in the company revenue bridge | — | Confirmed (as-is) |
| `C-DQ-6` | Negative / zero price lines, `A`-prefixed adjustments | Excluded from purchase revenue; reported in the bridge as "adjustments" | 2 negative-price rows, 3 `A`-invoices in V1 [VERIFIED] | [PROPOSED] |
| `C-DQ-7` | Customer with multiple countries | `country` = mode over history ≤ T (point-in-time); ties broken by most recent | Current code uses first/mode inconsistently | [PROPOSED] |

---

## 4. Canonical business definitions

| ID | Term | Definition |
| --- | --- | --- |
| `C-LINE` | Valid purchase line | As-is valid line **and** `line_type = product`, after `C-DQ-1` |
| `C-ORDER` | Order | customer × invoice with ≥1 valid purchase line; `order_date` = min line timestamp; `order_revenue` = sum product revenue > 0 |
| `C-ACQ` | Acquisition-eligible customer | First observed order ≥ `D_start + L` where look-back `L` = 12 months ([PROPOSED]; sensitivity 6/9 months). Customers first observed earlier have **unknown acquisition date** (`acquisition_known = false`). V1 alone cannot satisfy `C-ACQ` meaningfully |
| `C-FIRST` | First observed order | Earliest order in the dataset. **Never** called "first purchase" unless `acquisition_known` |
| `C-REPEAT` | Repeat order | Order rank ≥ 2 **among observed orders** |
| `C-T2` | Time to second purchase | Days from first to second order for `C-ACQ` customers; right-censored at `D_end` (Kaplan–Meier, not a raw median of completers) |
| `C-ACTIVE` | Active customer at T | ≥1 order in `[T − 365d, T)` ([PROPOSED] look-back) |
| `C-SNAP` | Point-in-time customer snapshot | One row per `C-ACTIVE` customer per anchor T (month starts, normalised per `C-TIME-3`). Features use only orders with `order_date < T`. Each label column carries its horizon *h* and a maturity flag per `C-TIME-5`. A snapshot built on data truncated at T must be identical to one built on full data (truncation test) |
| `C-LAPSE` | Lapsed (h) at T | `C-ACTIVE` at T, and no order in `[T, T + h)`; primary h = 90 days; mature per `C-TIME-5` |
| `C-HV` | High value at T | Top 10% of `C-ACTIVE` customers by trailing-365d product revenue at T (point-in-time; rank-based; ties by customer_id) |
| `C-SEG` | Canonical segment | One scheme, chosen by R2, defined only from data < T. Until R2 completes, the **interim** canonical scheme is RFM quintiles at T ([PROPOSED]) |
| `C-COHORT` | Acquisition cohort | Calendar month of first observed order **for `C-ACQ` customers only** |
| `C-RET` | Cohort retention (month k) | Share of cohort with ≥1 order in month k after acquisition; cells beyond `D_end` are null, not zero |
| `C-VALUE-H` | Historical value | Product revenue to date (left-truncated; labelled as observed) |
| `C-VALUE-F` | Fixed-horizon future revenue | Product revenue in `[T, T + h)`, h ∈ {90, 180}; mature per `C-TIME-5` |
| `C-EXP` | Experiment record | See §6 |

---

## 5. Canonical datasets

| Dataset | Grain | Primary key | Date semantics | Producer (reference) | Depends on | Validation |
| --- | --- | --- | --- | --- | --- | --- |
| `raw_transactions` | Source line | (file, row_number) | As provided | `src/data_loading.py` | Raw files | 8 canonical columns; SHA-256 of source recorded |
| `transaction_lines` | Line (post-dedupe) | `line_id` (deterministic hash of source fields + occurrence index) | `invoice_ts` | `src/cleaning.py` (extended) | raw | Revenue bridge identities; `C-DQ-1` reconciliation; flag completeness; no null keys where required |
| `orders` | customer × invoice | `order_id` | `order_date` = min line ts | `src/customer_metrics.py` | lines | Sum(order_revenue) = sum(valid product line revenue); 1 customer per order |
| `customers` | customer | `customer_id` | first/last observed order; `acquisition_known` | `src/customer_metrics.py` | orders | Counts and revenue reconcile to orders; no non-positive revenue |
| `customer_snapshots` | customer × anchor T | (`customer_id`, `anchor_date`) | features < T; labels `[T, T+h)` + maturity flags | new `src` module (Phase 3) | orders | **Point-in-time test:** recomputing features with data truncated at T gives identical values; label maturity correct |
| `cohorts` | cohort month × k | (`cohort_month`, `k`) | `C-COHORT`, `C-RET` | `src` + dbt | customers, orders | Retention ∈ [0,1]; k=0 = 1; censored cells null |
| `segments` | customer × anchor T | (`customer_id`, `anchor_date`, `scheme_version`) | uses data < T | R2 module | snapshots | One scheme version is canonical; every customer gets exactly one segment |
| `training_sets` | customer × anchor (study-specific) | + `split` ∈ {train, validation, holdout} | mature labels only | study modules | snapshots | No holdout anchor overlaps training label windows (purge check) |
| `predictions` | customer × anchor × model_version | (`customer_id`, `anchor_date`, `model_id`) | `scored_at`; `label_available` | study modules | model + snapshots | Scores ∈ [0,1]; `model_id` resolves to a manifest; current-anchor predictions carry no label |
| `experiment_eligibility` | customer × experiment | (`experiment_id`, `customer_id`) | `eligibility_date`; `observation_end`; `fully_observed` | R5 module | customers, orders | Eligibility uses data ≤ eligibility date; `fully_observed` true for every analysed unit |
| `experiment_assignment` | customer × experiment | same | `assigned_at` | R5 module (single hash rule) | eligibility | Allocation within binomial tolerance; one rule, one place; salt recorded |
| `experiment_exposure` (future) | customer × message | (`experiment_id`, `customer_id`, `sent_at`) | from CRM | external | — | Schema only; empty in this dataset |
| `bi_exports` | Varies (documented per file) | — | — | reporting module | results registry | Every exported number traceable to a manifest |
| `results_registry` | metric × study × run | (`study`, `metric`, `run_id`) | `run_at` | reporting module | all | README/report tables generated only from here |

**Ownership.** Each dataset has exactly one producing module. dbt and Spark produce **mirrors** for the parity study, never alternative canonical versions.

---

## 6. Experiment record contract (`C-EXP`)

| Field | Type | Notes |
| --- | --- | --- |
| `experiment_id` | string | Registered in a pre-registration file |
| `evidence_class` | enum {`observational`, `aa`, `synthetic`, `causal`} | `causal` only with real exposure data |
| `unit` | enum {customer} | |
| `eligibility_rule_version` | string | |
| `eligibility_date` | date | |
| `assignment` | enum {control, treatment} | Single salted hash: `hash(salt ‖ experiment_id ‖ customer_id) mod 10000 < control_bp` ([PROPOSED]) |
| `observation_end` | date | `eligibility_date + max_window` |
| `fully_observed` | bool | `observation_end ≤ D_end` |
| `synthetic_effect` | float, nullable | Injected effect for `synthetic` class only |
| outcome fields | per window | conversion flags and revenue, computed only if `fully_observed` |

---

## 7. Cross-engine parity tolerances

| Quantity | Tolerance |
| --- | --- |
| Row counts, distinct keys | Exact |
| Sums of revenue | Relative ≤ 1e-9 (DuckDB/pandas), ≤ 1e-6 (Spark) |
| Rates / shares | Absolute ≤ 1e-9 / 1e-6 |
| Rank-based assignments (deciles, top-10%) | Exact, given a documented tie-break (`revenue desc, customer_id asc`) |

---

## 8. Unresolved contract questions

| # | Question | Blocking |
| --- | --- | --- |
| Q-C1 | Exact dedupe rule for V2 overlap: drop the window from one sheet, or multiplicity-reconcile against V1? | Phase 2 |
| Q-C2 | Look-back `L` for `C-ACQ` (12 months proposed) and `C-ACTIVE` (365 days proposed) | Phase 2 |
| Q-C3 | Keep or flag exact duplicates elsewhere (`C-DQ-2`) | Phase 2 |
| Q-C4 | Non-product code taxonomy (`C-DQ-3`), including whether `M` (manual) is product revenue | Phase 2 |
| Q-C5 | Should customer metrics be gross product revenue (current) or net of refunds? | Phase 2 |
| Q-C6 | Interim segmentation before R2 completes (RFM quintiles proposed) | Phase 3 |
| Q-C7 | Does any `InvoiceNo` map to more than one `CustomerID`? (to be checked in Phase 2) | Phase 2 |
