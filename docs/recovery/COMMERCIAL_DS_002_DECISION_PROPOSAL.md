# COMMERCIAL-DS-002 — Data-Contract Decision Proposal

**Status:** Recommendations for owner review. Nothing in this document is approved or implemented.

Evidence and calculations are in [COMMERCIAL_DS_002_DATA_AUDIT.md](COMMERCIAL_DS_002_DATA_AUDIT.md). The existing source of truth for approvals remains [COMMERCIAL_DS_001_DECISION_LOG.md](COMMERCIAL_DS_001_DECISION_LOG.md).

## 1. Decisions required before Phase 3

### D-002-01 / P-01 — Canonical dataset

**Recommendation:** Approve corrected V2 (`v2c`) as the canonical research dataset. Keep V1 unchanged as the legacy/golden comparison dataset.

**Why:** V2 provides 365 days before V1, while 62.8% of V1 customers are known returning customers. Corrected V2 retains 1,044,848 source rows, 5,878 current-valid customers and 36,969 orders.

**Alternatives and trade-offs:**

| Option | Benefit | Cost / consequence |
| --- | --- | --- |
| Corrected V2 canonical (**recommended**) | Longest available history; supports a 12-month acquisition proxy and two seasonal cycles | Requires approved overlap and revenue contracts; still left-censored before 2009-12-01 |
| V1 canonical | Preserves existing outputs with least change | Acquisition/cohort/first-to-second-purchase studies are not supported; only one seasonal cycle |
| V2 before 2010-12-01 + V1 | Exact V1-period legacy reconciliation | Composite source; drops the extra real GBP 18 V2 postage line; unnecessary for product metrics |

**Approval requested:** approve / reject / request further evidence.

### D-002-02 / P-01b — V2 overlap correction

**Recommendation:** For the V2 file with SHA-256 `32569a66f3842a82b0d8c4d63b263c5d98a76bde5d1f65c6c01bf457e541d3a9`, preserve raw row identity, identify the source-block reset at zero-based row 525,461, remove the first block's 22,523 rows dated 2010-12-01 through 2010-12-09 inclusive, and retain the complete second block.

**Evidence:** Both block windows are exact 22,523-row full-field multiset matches to V1. The correction removes one copy and reconciles rows and every revenue field. The second full block differs from V1 by only a GBP 18 `POST` row on 2011-12-09.

**Alternatives and trade-offs:**

| Option | Benefit | Cost / consequence |
| --- | --- | --- |
| Drop first-block overlap; retain second block (**recommended**) | Keeps the complete later source-year block; reproducible from source row order; retains GBP 18 terminal postage | Dataset-specific rule tied to file hash |
| Drop second-block overlap; retain first block | Same aggregate overlap result | Splices the first block into the later block and is less natural for lineage |
| Multiplicity-cap overlap to V1 | Works without source-block fields and reconciles exactly | Uses V1 as an external oracle; ambiguous if future source version differs |
| Global `drop_duplicates` | Simple | Unsupported removal of 11,812 additional rows and GBP 56,746.91 identifiable gross revenue |
| Keep raw V2 | No transformation | Known GBP 311,878 identifiable revenue inflation remains |

**Approval requested:** approve the recommended source-boundary rule. Do not approve global row deduplication.

### D-002-03 / P-09a — Incidental exact repeats

**Recommendation:** Retain exact-repeat lines outside the verified overlap and add `is_exact_repeat`, `exact_repeat_group_size` and a business-field fingerprint. Report a one-per-full-row sensitivity, but do not make it canonical.

**Why:** Corrected V2 has 11,491 excess exact rows outside the overlap across 4,303 invoices. No source line ID distinguishes an export duplicate from a genuine repeated invoice line.

**Alternative:** remove all exact repeats. This lowers corrected-V2 identifiable gross revenue by GBP 56,746.91 and product gross revenue by GBP 56,358.26. The change is not defensible from available source evidence.

**Approval requested:** approve retain-and-flag.

### D-002-04 — Transaction-line identity

**Recommendation:** Define raw transaction identity as `(source_sha256, source_row_number)` and derive canonical `line_id` from that tuple. Preserve `source_block_id`. Do not use the eight business fields or a hash-plus-occurrence index as identity.

**Why:** Business fields are non-unique. Source identity must survive legitimate identical lines and cross-engine ordering differences.

**Alternatives:**

- Business-field hash alone: collapses repeats and is rejected.
- Business-field hash plus occurrence index: can change when ordering or dedupe changes and is unsuitable as raw provenance.

**Approval requested:** approve before contract YAML is authored.

### D-002-05 / P-09b — Non-product taxonomy

**Recommendation:** Approve a versioned mapping with at least:

| Category | Initial codes | Recommended treatment |
| --- | --- | --- |
| Product | All normal merchandise codes | Product and customer product revenue |
| Shipping/carriage | `POST`, `DOT`, `C2` | Exclude from product revenue; retain in commercial bridge |
| Manual adjustment | `M` | Exclude from product revenue; report separately |
| Fee/commission/bad debt | `BANK CHARGES`, `AMAZONFEE`, `CRUK`, `B` | Exclude from product revenue; report separately |
| Discount | `D` | Exclude from gross product sales; retain as a negative net-revenue component |
| Samples/other | `S`, `PADS` | Exclude pending owner confirmation; report separately |

**Why:** Corrected V2 has GBP 302,114.63 identifiable positive revenue on the proposed list. `M` is material and has both positive and negative entries; `D` and `CRUK` are mainly negative. A single binary exclusion would obscure the revenue bridge.

**Alternatives and consequences:**

- Keep all codes as product: preserves legacy outputs but overstates merchandise value and makes the GBP 18 V1/V2 difference appear in product revenue.
- Exclude all listed codes without categories: improves product revenue but loses shipping/discount/manual visibility.
- Treat `M` as product: adds GBP 152,166.32 positive identifiable revenue but mixes manual adjustments with merchandise.

**Approval requested:** approve category mapping and specifically decide `M`, `D`, `CRUK`, `PADS`, `B` and `S`.

### D-002-06 / P-09c — Revenue fields and primary customer monetary value

**Recommendation:**

1. Preserve `gross_positive_revenue_all` and an explicit signed total-revenue bridge.
2. Use identifiable **gross product revenue** as the primary behavioural/RFM monetary measure.
3. Publish identifiable **net product revenue** as a separate mandatory value outcome and sensitivity.
4. Keep shipping, discounts, fees and manual adjustments in separate fields.
5. Prohibit an unqualified canonical field named only `revenue`.

**Consequences on corrected V2:**

| Field | Amount |
| --- | ---: |
| Current identifiable gross, including non-product | GBP 17,431,551.18 |
| Identifiable gross product | GBP 17,129,436.55 |
| Identifiable net product | GBP 16,414,904.00 |

**Alternatives:**

- Net product as the only customer metric: closer to realised value, but negative returns can obscure purchasing intensity and require return-attribution caveats.
- Current gross including non-product: easiest legacy continuity, but mixes merchandise, postage and manual adjustments.

**Approval requested:** approve the field family and gross-product primary metric.

### D-002-07 / P-17a — Acquisition-proxy look-back and terminology

**Recommendation:** Use 12 months as the primary qualifying look-back, with 6- and 9-month sensitivity analyses. Replace `acquisition_known` with fields that do not claim first-ever purchase:

- `first_observed_order_ts`
- `qualifying_lookback_months`
- `qualifying_lookback_observed`
- `acquisition_proxy`
- `first_ever_purchase_known = false`

Use the public term **acquisition-proxy cohort** or **first-observed cohort after 12-month look-back**, not “acquired customer” without qualification.

**Evidence:** Product-only corrected V2 produces:

| Look-back | Eligible customers | Cohort months | Mature 90d customers | 90d second-purchase rate |
| ---: | ---: | ---: | ---: | ---: |
| 3m | 4,152 | 22 | 3,556 | 41.51% |
| 6m | 3,166 | 19 | 2,570 | 41.75% |
| 9m | 2,552 | 16 | 1,956 | 41.00% |
| 12m | 1,612 | 13 | 1,016 | 42.32% |

**Alternatives and trade-offs:**

- 6 months: nearly doubles the 12-month population but offers weaker protection against long-returning customers.
- 9 months: compromise sample of 2,552.
- 12 months: strongest supported look-back and aligns with V1-era cohorts, but no fully observed month-12 retention cell remains.
- “First-ever acquisition”: unsupported under every option and must not be approved.

**Approval requested:** approve 12 months and the revised terminology.

### D-002-08 / P-17b — Active-customer look-back

**Recommendation:** Define active at T as at least one valid product order in `[T-365d,T)`. Keep 365 as a versioned parameter.

**Evidence:** Product-order gaps have p95 207.0 days and 98.93% are at most 365 days. The rule excludes long-dead customers from snapshot populations while retaining nearly all observed repeat gaps.

**Alternatives:**

- No maximum look-back: includes customers inactive for nearly two years and can create easy lapse negatives.
- 180 days: tighter current-customer definition but excludes more plausible long-cycle repeaters.
- 270 days: intermediate policy without a strong observed breakpoint.

**Approval requested:** approve 365 days as operational policy, not as a natural law.

### D-002-09 — Lapse status and predictive label

**Recommendation:** Approve two distinct concepts:

- `inactive_90d_at_T`: no product order in `[T-90d,T)`; a current status.
- `no_purchase_next_90d`: no product order in `[T,T+90d)` for an active customer; a mature predictive outcome.

If the name `lapse` is retained, it must include direction and horizon in the field name. All windows should be half-open.

**Why:** Current documentation defines lapse as 90+ days since the last order, while the model defines it as no order in the next 90 days and includes the endpoint. These are not the same variable.

**Alternative:** retain one overloaded “lapse” term. This is rejected because it prevents reliable reporting and parity testing.

**Approval requested:** approve names before snapshot/model contracts are encoded.

## 2. Decisions that can safely be deferred

| Decision | Deferral point | Why safe to defer |
| --- | --- | --- |
| P-16 primary lapse horizon 90 vs 120 days | R1 interval analysis / R3 preregistration | Foundation can parameterise horizons; no model is trained in Phase 2. |
| P-03 interim/final segmentation | Phase 3/R2 | Foundation needs RFM inputs, not a final segment scheme. |
| R2 clustering method | R2 preregistration | Does not alter source lines, orders or revenue definitions. |
| R4 model/library choices | Phase 7 | Fixed-horizon outcome contracts can be approved independently. |
| R5 assignment hash details | Phase 8 | Eligibility and maturity contracts are the only immediate foundation dependency. |
| Spark/Databricks execution | Phase 9 | Does not change pandas canonical definitions; parity waits for approved contracts. |

## 3. Explicit blockers for the next phase

Phase 3 must not start until the owner records decisions for:

1. P-01: corrected V2 versus V1 canonical.
2. P-01b: source-boundary overlap correction.
3. P-09: retain-and-flag incidental repeats, non-product taxonomy and gross/net customer revenue fields.
4. P-17: 12-month acquisition-proxy and 365-day active look-back.
5. Raw/canonical line identity.
6. Acquisition-proxy terminology, removing any implication that first-ever purchase is known.
7. Distinct names for current inactivity and future non-purchase labels.

After those choices, Phase 2 still requires an approved, versioned `contracts/business_definitions.yml` and associated tests. This task intentionally did not create that implementation artifact because no owner approval has been recorded.

## 4. Proposed owner decision record

```text
Gate: COMMERCIAL-DS-002 data-contract decisions
Date:
Evidence reviewed:
  - docs/recovery/COMMERCIAL_DS_002_DATA_AUDIT.md
  - docs/recovery/COMMERCIAL_DS_002_ANALYSIS.py
P-01 decision:
P-01b decision:
P-09 duplicate policy:
P-09 line-type taxonomy:
P-09 revenue metric policy:
P-17 acquisition-proxy look-back and terminology:
P-17 active look-back:
Line identity decision:
Lapse status/label terminology:
Approved by:
Phase 2 contract encoding authorised: yes/no
Phase 3 authorised: no (requires completed and independently reviewed contract encoding)
```
