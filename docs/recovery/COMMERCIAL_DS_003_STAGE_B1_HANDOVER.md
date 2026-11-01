# COMMERCIAL-DS-003 Stage B1 — Purchase-Occasion Contract Handover

**Status: COMPLETE for Stage B1.** The production purchase-occasion builder is implemented, tested and reconciled to Claude's independent reference. The authoritative taxonomy seed and Stage A source/fingerprint pins are unchanged. No revenue bridge, cohort output, retention model or machine learning was implemented.

## 1. S-1 through S-7 disposition

| Condition | Disposition | Evidence |
|---|---|---|
| S-1 — strict eligibility | Closed. | Production builder is separate from the test-only Stage A oracle. It validates customer, invoice, source identity, timestamp, integral quantity, price and cancellation semantics; malformed identities fail closed and invalid/noneligible rows are excluded with reason counts. Tests cover the review's edge cases. |
| S-2 — temporal contract | Closed for contract foundation and boundary utilities. | Contract specifies observation bounds, half-open windows, strict `< T` feature cutoff, `[T,T+90)` outcomes, `d1 < d2 < d1+90`, date-level maturity and same-day invoice sensitivity. Boundary tests pass. No labels or cohorts are built. |
| S-3 — acquisition proxy policy | Infrastructure and diagnostics complete; proposed primary-population change remains **pending owner approval**. | 1,613 merchandise-only observed-acquisition sensitivity customers; 11 have prior identified transaction activity; hypothetical adjusted count is 1,602. The run marks the primary cohort unpublished. Absence of observed prior activity is not called true acquisition. |
| S-6 — decision attribution | Closed. | Decision log separates the owner-approved O-5 category split from the dated technical clarification of cancellation-invoice context. The 64 rows / GBP −1,168.70 / 52 invoices / 47 customers remain embedded manual adjustments; no classification changed. |
| S-7 — approved source loader | Closed. | Real-data construction calls `build_report_and_classified_rows()`, which uses `COMMERCIAL_DS_002_ANALYSIS.load_sources()` and the reviewed overlap correction. The builder rejects missing, duplicate, negative, boolean, or non-integral source-row identities. |
| S-4/S-5 — downstream analyses | Not in this batch. | No full revenue bridge, cohorts, retention modelling, or prediction work was started. These remain outside Stage B1 scope. |

## 2. Strict purchase eligibility

An occasion line must be classified `merchandise`, have strictly positive integral numeric quantity and positive finite numeric unit price, a positive canonical numeric customer ID, a valid invoice ID, a non-cancellation invoice, a valid timezone-naive transaction timestamp, and a timestamp within the observed source interval. Customer strings are rejected rather than parsed, including whitespace-padded and exponent-form values. Boolean, fractional and non-finite numeric identifiers/values are rejected. Missing or non-positive customer identifiers, missing invoice/date, invalid timestamps, non-positive/fractional quantities, non-positive prices, and cancellation invoices are excluded with deterministic reason counts. Invoice identifiers with leading/trailing whitespace are rejected; lowercase `c` cancellation prefixes are recognized case-insensitively.

All identified rows participate in invoice-to-customer consistency validation, including non-merchandise rows. Duplicate or absent source-row identities stop the build. Multiple eligible lines on one invoice form one customer × invoice occasion, with exact Decimal gross, eligible line count, transaction date and sorted raw source-row lineage. Source reordering leaves output unchanged. A non-merchandise line cannot contribute to eligibility, gross, or lineage. Mixed-sign invoices retain only positive eligible merchandise lines.

## 3. Real-data occasion reconciliation

The builder independently reproduced Claude's values; these expected figures are in tests and the handover, not forced into the builder:

| Measure | Result |
|---|---:|
| Corrected-V2 rows integrity-checked | 1,044,848 |
| Qualifying merchandise lines | 788,127 |
| Customer × invoice purchase occasions | 36,594 |
| Customers with at least one occasion | 5,852 |
| Qualifying gross merchandise | GBP 17,123,740.997 |

Excluded-row counts by disjoint first-failure reason: non-merchandise category 6,626; missing/non-positive customer 226,881; non-positive quantity 20,789; non-positive unit price 2,425. Total excluded rows: 256,721; this plus 788,127 qualifying lines reconciles to 1,044,848 source rows. Missing/invalid timestamps, invalid invoice IDs and outside-observation rows are zero in corrected V2. The full Stage A source/category/customer fingerprints are validated before occasions are built.

## 4. Temporal definitions

The formal definitions and test boundaries are recorded in §9 of [the contract specification](COMMERCIAL_DS_002B_CONTRACT_SPECIFICATION.md):

- Observation starts 2009-12-01; maximum source timestamp is 2011-12-09 12:50; the final observed calendar date is 2011-12-09 and date windows end exclusively at 2011-12-10.
- Source timestamps are accepted only from 2009-12-01 00:00 inclusive through the maximum observed timestamp inclusive; timezone-aware timestamps are excluded.
- Feature windows are half-open `[T-L,T)` and historical features use dates strictly before normalized anchor date `T`.
- The 90-day outcome is `[T,T+90 days)`; exactly `T+90` is excluded. An anchor is mature only when `T+90 <= 2011-12-09` at date grain.
- The repeat boundary is `d1 < d2 < d1+90 days`. Date-level primary repeat collapses same-day invoices; invoice-level sensitivity retains them separately.
- The twelve-calendar-month acquisition cutoff is 2010-12-01. A proxy is observed acquisition only, with left-censoring disclosure, never proof of a true first purchase.

Boundary tests pass at feature start/anchor, `d1+89`/`d1+90`, mature/immature cutoffs, and source observation-end timestamps.

## 5. Acquisition-proxy diagnostics and approval

The merchandise-only sensitivity has 1,613 customers whose first qualifying occasion is on/after 2010-12-01. Eleven also have earlier identified transaction activity of any category. Excluding those 11 would leave 1,602. The production report records these diagnostic counts, sets `primary_cohort_published: false`, and status `PENDING_OWNER_APPROVAL`.

The owner's decision is still required before adopting that exclusion for any primary acquisition-proxy population. The already approved 12-month lookback principle and the merchandise-only sensitivity remain distinct. The pipeline does not emit an acquisition cohort or customer membership list.

## 6. Source loader, integrity and reproducibility

Real-data path: `build_report_and_classified_rows()` → `COMMERCIAL_DS_002_ANALYSIS.load_sources()` → `source_block_evidence()` → taxonomy classification → `build_purchase_occasions()`. No legacy `src/` loader is used. Corrected-V2 removes raw source IDs 502,938–525,460 inclusive; 1,044,848 remaining IDs are unique. Stage A runtime pins validate source, seed, category, row, source-content and customer references.

The authoritative seed remains SHA-256 `7b4611c78ca22d108c2616076c84b7c1db2efb8453ee9a32faceb027bb181e4e`. Stage A frozen reference file remains `a96d2e9d5787dc1edd0e5c493e072ede4c342e845921e3242e90742625c8ba49`. Source hashes remain V1 `43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d` and V2 `32569a66f3842a82b0d8c4d63b263c5d98a76bde5d1f65c6c01bf457e541d3a9`.

Executed twice:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python docs/recovery/COMMERCIAL_DS_003_PURCHASE_OCCASIONS.py > /tmp/COMMERCIAL_DS_003_STAGE_B1_RUN1.json
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python docs/recovery/COMMERCIAL_DS_003_PURCHASE_OCCASIONS.py > /tmp/COMMERCIAL_DS_003_STAGE_B1_RUN2.json
cmp -s /tmp/COMMERCIAL_DS_003_STAGE_B1_RUN1.json /tmp/COMMERCIAL_DS_003_STAGE_B1_RUN2.json
shasum -a 256 /tmp/COMMERCIAL_DS_003_STAGE_B1_RUN1.json /tmp/COMMERCIAL_DS_003_STAGE_B1_RUN2.json
```

`cmp` succeeded. Both builder output SHA-256 values: `965907203f40858168000fc045048e52229a1f754279ee6fc1f291acc826ff86`.

## 7. Tests and commands

Full suite command:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s docs/recovery -p 'test_COMMERCIAL_DS_*.py' -v
```

Result: **40 passed, 0 failed**. This includes all existing taxonomy, Stage A integration and contract tests, Stage B1 adversarial fixtures, and real corrected-V2 comparison with the independent occasion baseline. Stage B1 tests cover missing/NaT/timezone-aware timestamps, observation-end boundaries, uppercase/lowercase cancellation and whitespace IDs, customer IDs −5/0/whitespace/exponent/fractional, fractional quantities, mixed-sign invoice lines, missing/invalid invoice IDs, duplicate/missing source identities, all-identified-row invoice/customer consistency, same customer/multiple invoices on one day, lineage, ordering invariance and temporal boundaries.

Seed and reference hashes were rechecked after tests and both runs. No raw data, production pipeline or seed changed. Commands used `PYTHONDONTWRITEBYTECODE=1`; no bytecode cleanup was performed.

## 8. Remaining uncertainties and Stage B2 readiness

The 11-customer acquisition exclusion is pending explicit owner approval; the proposed primary cohort must remain unpublished until that decision is recorded. Observed absence is not true acquisition. Stage B1 does not resolve subsequent cancellations of gross purchase occasions; source records cannot reliably link cancellations to original invoices. The valid invoice rule currently follows source identifiers (non-empty trimmed strings; `C` prefix denotes cancellation) without inventing a broader invoice grammar.

**Stage B2 readiness: READY for non-acquisition temporal work.** Any primary acquisition-proxy cohort remains gated on owner approval. Any downstream cohort or label producer must implement the temporal contract, validate the frozen integrity references, and preserve the explicit date-level versus invoice-level distinction.
