# COMMERCIAL-DS-003 Stage B2A — Integrity and Revenue Bridge Handover

**Status: COMPLETE.** The Stage B1 conditions are closed and the first exact corrected-V2 commercial line bridge is implemented. The independent occasion baseline and all Stage A pins remain unchanged. Acquisition cohorts, retention modelling, a full profit-and-loss bridge, and machine learning were not implemented.

## 1. Independent-review condition closure

| Condition | Status | Evidence |
|---|---|---|
| B2-1 — validated construction boundary | **Closed** | Production functions accept only `_ValidatedPurchaseInput` objects minted by `load_validated_purchase_input()` after full Stage A runtime pin validation. The object is frozen and its private frame is content-digested; changed data/category is rejected. Arbitrary DataFrames are rejected by every production entry point. A test relabels every shipping row as merchandise and verifies rejection by the occasion builder, real-data report and bridge. The row-level constructor is explicitly named `_build_purchase_occasions_for_test`. |
| B2-2 — production occasion references | **Closed** | `COMMERCIAL_DS_003_STAGE_B2A_REFERENCE_PINS.json` externally freezes the independently reviewed summary, occasion fingerprint, lineage fingerprint, source V2 hash, seed and source-row fingerprint. Runtime checks file SHA and each pin; it never generates expected values during validation. Tests reject occasion-lineage mutation and pin-file corruption. |
| B2-3 — deterministic repeats | **Closed** | Primary repeat sorts by customer/date/invoice/lineage, collapses customer-days, and applies the half-open 90-day rule. Invoice-level sensitivity preserves distinct invoices; a later invoice on the same day counts, with ordering by invoice identifier. Shuffled fixtures produce identical results. |
| B2-4 — typed temporal helpers | **Closed** | Repeat, maturity, feature-window and point-in-time helpers reject strings, missing values, unsupported date types, timezone-aware timestamps and non-midnight anchors. Local source calendar dates govern day boundaries. Boundary tests cover anchor, +89/+90 days, maturity, observation end and cutoff. |
| B2-5 — point-in-time membership | **Closed as infrastructure** | `rows_before_anchor()` uses only source dates strictly before normalized anchor `T`. A truncation test mutates a future row and verifies historical membership/output is unchanged. No cohort or model was created. |
| B2-6 — source and identifier strictness | **Closed** | Customer IDs must be positive, integral, numeric, finite and within 2⁵³; strings are never parsed. Missing IDs are legitimate unattributed rows and are excluded from occasions; zero/negative IDs fail. All rows require a valid typed timestamp and valid invoice ID. Customer and calendar-date consistency are checked across all invoice rows, including non-merchandise. Invoice grammar is explicit: digits, `C` + digits for cancellation (case-insensitive), `A` + digits for adjustment; A invoices cannot create purchase occasions. |
| B2-7 — specification consistency | **Closed** | Temporal contract clarifies that 2011-12-09 is only partially observed through 12:50, aligns the 12-month cutoff with the implemented fixed-date diagnostics, records all three acquisition comparison populations, and leaves selection pending the owner. |

## 2. Validated construction and frozen occasion references

The only production input path is `load_validated_purchase_input()` → approved `COMMERCIAL_DS_002_ANALYSIS.load_sources()` → overlap correction → frozen taxonomy classification and Stage A references. The validated object stores the integrity report and a content digest; production construction checks its validation token, revalidates Stage A references and recomputes the digest before building. `build_purchase_occasions()` rejects a DataFrame. `build_real_data_report()` and `build_revenue_bridge()` accept only a validated object (or load one themselves). No legacy `src/` loader is used.

Frozen production references, independently reproduced during Stage B1:

| Measure | Frozen result |
|---|---:|
| Qualifying merchandise lines | 788,127 |
| Customer × invoice occasions | 36,594 |
| Distinct customers | 5,852 |
| Qualifying gross merchandise | GBP 17,123,740.997 |
| Occasion fingerprint | `9ad56e57c7bc40a967ad23a8f0e9038ac09cef926b628a36adcd7296117797e8` |
| Lineage fingerprint | `b172093cd3701f22faaf2fc63b5db125c5ecc87b505061438c545c4e1dcad8de` |
| Unique qualifying source-row IDs | 788,127 |

The occasion fingerprint covers customer, invoice, local transaction date, Decimal gross, eligible-line count and sorted source-row IDs. The separate lineage fingerprint binds every qualifying source ID to its customer/invoice/date. Each source row appears in at most one occasion. The runtime also requires the expected source V2, taxonomy seed and Stage A source-row fingerprint.

## 3. Repeat semantics and temporal boundaries

For the first 90-day outcome, date-level primary repeats collapse all invoices on each customer-day before testing `d1 < d2 < d1 + 90 days`. Thus there are 89 later-calendar-day opportunities; the boundary date exactly `d1 + 90` is excluded. Invoice-level sensitivity counts distinct invoices; a subsequent same-day invoice counts, and invoice identifiers provide deterministic within-day ordering. Source-row lineage is the stable final tie-breaker.

The production full-window diagnostic reports **2,532** customers with a date-level repeat within the 90-day window and **2,673** with an invoice-level sensitivity repeat. These are repeat-semantics diagnostics, not cohorts or model labels. Repeat utilities accept typed timezone-naive timestamps only. Local source dates are used for date-level comparisons; feature membership is strictly `< T`, with date windows half-open. Maturity remains `T + 90 days <= 2011-12-09`.

## 4. Acquisition-proxy diagnostics and gate

No primary acquisition-proxy cohort was published. Diagnostics are:

| Candidate rule | Customers | Status |
|---|---:|---|
| Merchandise-only first occasion on/after 2010-12-01 | 1,613 | Sensitivity only |
| Exclude identified activity before fixed cutoff | 1,602 | Diagnostic only |
| Exclude identified activity before customer's first qualifying occasion | 1,601 | Diagnostic only |

The owner has not selected a primary rule. No rule is treated as approved. Absence of observed activity does not establish true acquisition because V2 is left-censored. The decision log records this pending choice.

## 5. Commercial line revenue bridge

Each corrected source row belongs to exactly one bridge leaf and retains its zero-based raw V2 source-row ID. The rows below form a disjoint partition. Amounts are signed GBP using Decimal arithmetic; positive and negative columns are signed components. Identifiable and unattributed columns partition each signed leaf total.

| Bridge leaf | Rows | Positive | Negative | Signed | Identifiable | Unattributed |
|---|---:|---:|---:|---:|---:|---:|
| Qualifying gross merchandise purchases | 788,127 | 17,123,740.997 | 0 | 17,123,740.997 | 17,123,740.997 | 0 |
| Other positive merchandise activity | 226,881 | 2,575,930.13 | 0 | 2,575,930.13 | 0 | 2,575,930.13 |
| Merchandise returns/cancellations | 17,973 | 0 | −719,677.94 | −719,677.94 | −713,031.25 | −6,646.69 |
| Shipping/delivery income (nonzero rows) | 3,851 | 450,162.53 | −15,567.02 | 434,595.51 | 135,700.87 | 298,894.64 |
| Standalone manual billing | 330 | 334,379.51 | 0 | 334,379.51 | 146,916.08 | 187,463.43 |
| Standalone manual credits | 470 | 0 | −421,770.38 | −421,770.38 | −336,332.43 | −85,437.95 |
| Embedded manual adjustments (`M`, nonzero) | 596 | 5,624.00 | −1,168.70 | 4,455.30 | 4,090.87 | 364.43 |
| Other manual adjustment codes | 70 | 9,628.98 | −2,062.69 | 7,566.29 | 2,769.17 | 4,797.12 |
| Fees | 136 | 20,987.041 | −277,989.79 | −257,002.749 | 330.001 | −257,332.75 |
| Commissions | 16 | 0 | −7,933.43 | −7,933.43 | −7,933.43 | 0 |
| Bad debt | 6 | 11,062.06 | −158,676.14 | −147,614.08 | 0 | −147,614.08 |
| Discounts | 173 | 397.89 | −13,277.52 | −12,879.63 | −12,785.34 | −94.29 |
| Samples | 102 | 136.85 | −6,137.70 | −6,000.85 | 0 | −6,000.85 |
| Gift vouchers (nonzero rows) | 79 | 1,839.50 | −69.56 | 1,769.94 | 0 | 1,769.94 |
| Test entries (nonzero rows) | 14 | 226.0 | −22.5 | 203.5 | 203.5 | 0 |
| Non-commercial stock movements (nonzero rows) | 0 | 0 | 0 | 0 | 0 | 0 |
| Zero-value entries (all taxonomy categories) | 6,024 | 0 | 0 | 0 | 0 | 0 |
| **Total** | **1,044,848** | **20,534,115.488** | **−1,624,353.37** | **18,909,762.118** | **16,343,669.038** | **2,566,093.08** |

The 6,024 zero-value rows retain taxonomy subcategory and source lineage: merchandise 5,241; shipping 18; manual adjustment 5; standalone zero-value manual 2; gift voucher 24; test 3; non-commercial stock movement 731. There are 70 identified and 5,954 unattributed zero rows.

Positive merchandise reconciliation: total positive merchandise is GBP 19,699,671.127. Qualifying purchases are GBP 17,123,740.997. The difference, GBP 2,575,930.130, equals other positive merchandise activity; its 226,881 lines are all unattributed and do not qualify as customer purchases. Decimal trailing-zero scale may differ in JSON (`2575930.13` versus `2575930.130`); the exact Decimal values are equal.

The complete bridge retains source-row IDs by leaf and reports `all_source_row_ids_unique: true`; all leaf row counts sum to 1,044,848, and signed values sum to GBP 18,909,762.118. Manual credits are not merchandise returns. This line reconciliation is **not** a complete profit-and-loss statement and makes no margin, cost, cash, refund-linkage or profitability claim.

## 6. Execution, tests and hashes

Executed full test suite:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s docs/recovery -p 'test_COMMERCIAL_DS_*.py' -v
```

Result: **47 passed, 0 failed**. It includes all taxonomy and Stage A integration tests, contract tests, typed eligibility/date validation, source and invoice integrity probes, production boundary mutation tests, frozen occasion-reference checks, repeat ordering/boundaries, acquisition diagnostic gating, exact Decimal bridge reconciliation and source-row lineage checks.

Production outputs were run twice each:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python docs/recovery/COMMERCIAL_DS_003_PURCHASE_OCCASIONS.py > /tmp/COMMERCIAL_DS_003_STAGE_B2A_OCCASIONS_RUN1.json
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python docs/recovery/COMMERCIAL_DS_003_PURCHASE_OCCASIONS.py > /tmp/COMMERCIAL_DS_003_STAGE_B2A_OCCASIONS_RUN2.json
cmp -s /tmp/COMMERCIAL_DS_003_STAGE_B2A_OCCASIONS_RUN1.json /tmp/COMMERCIAL_DS_003_STAGE_B2A_OCCASIONS_RUN2.json
shasum -a 256 /tmp/COMMERCIAL_DS_003_STAGE_B2A_OCCASIONS_RUN1.json /tmp/COMMERCIAL_DS_003_STAGE_B2A_OCCASIONS_RUN2.json

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python docs/recovery/COMMERCIAL_DS_003_REVENUE_BRIDGE.py > /tmp/COMMERCIAL_DS_003_STAGE_B2A_BRIDGE_RUN1.json
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python docs/recovery/COMMERCIAL_DS_003_REVENUE_BRIDGE.py > /tmp/COMMERCIAL_DS_003_STAGE_B2A_BRIDGE_RUN2.json
cmp -s /tmp/COMMERCIAL_DS_003_STAGE_B2A_BRIDGE_RUN1.json /tmp/COMMERCIAL_DS_003_STAGE_B2A_BRIDGE_RUN2.json
shasum -a 256 /tmp/COMMERCIAL_DS_003_STAGE_B2A_BRIDGE_RUN1.json /tmp/COMMERCIAL_DS_003_STAGE_B2A_BRIDGE_RUN2.json
```

Both comparisons succeeded. Occasion output SHA-256 (both runs): `402090a0eea8abd02d4d72b5c12301fa51334c925f19840c9a639282d61e2109`. Revenue bridge output SHA-256 (both runs): `016cf7a18dbea9c8018ddd4c85e2b2b5ce4a049580decf533d198fbad8d1fa1a`.

The Stage A integration output was rerun and remains byte-identical to the independently reviewed value: `2ffcbef73482a05572983019c535c12384fc2fcbf935bbc0a2581f7be695dd6b`.

| Artifact | SHA-256 |
|---|---|
| V1 source | `43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d` |
| V2 source | `32569a66f3842a82b0d8c4d63b263c5d98a76bde5d1f65c6c01bf457e541d3a9` |
| Inventory | `0d507be1e2b062705ba9763507342db71a24663b0d76176b31a2b39e4f66175b` |
| Authoritative taxonomy seed (unchanged) | `7b4611c78ca22d108c2616076c84b7c1db2efb8453ee9a32faceb027bb181e4e` |
| Stage A frozen reference pins (unchanged) | `a96d2e9d5787dc1edd0e5c493e072ede4c342e845921e3242e90742625c8ba49` |
| Stage B2A occasion reference pins | `4cf7b761a1b02cea853dbe577af7dddf8070fe65d0dcdfc7a71e2a064986f433` |
| Stage A classification/source-row fingerprint | `d76696efc5d02069d1180c84286e813973f810ca8fbf2b356ebc03f45bca1a04` |
| Occasion fingerprint | `9ad56e57c7bc40a967ad23a8f0e9038ac09cef926b628a36adcd7296117797e8` |
| Occasion lineage fingerprint | `b172093cd3701f22faaf2fc63b5db125c5ecc87b505061438c545c4e1dcad8de` |

No raw data or taxonomy seed changed. Commands disabled bytecode writing; no cache files were removed.

## 7. Remaining limitations and Stage B2B readiness

Acquisition-proxy rule selection remains with the owner; all three populations above are diagnostic only and no primary cohort is available. V2 is left-censored, so observed inactivity is not true acquisition. Gross occasions are not linked to later cancellations. The source has no cost, margin or complete accounting fields; the bridge is only observed signed transaction-line value. Static taxonomy descriptions remain full-period metadata. The source parser/fingerprint pins remain environment-coupled and fail closed under drift.

**Stage B2B readiness: READY for non-acquisition repeat and commercial research.** Any primary acquisition analysis remains gated. Downstream producers must use the sealed validated input, frozen occasion/reference checks, strict temporal helpers, point-in-time cutoff and the disjoint Decimal bridge. No full P&L, cohort, retention, or ML work was included here.
