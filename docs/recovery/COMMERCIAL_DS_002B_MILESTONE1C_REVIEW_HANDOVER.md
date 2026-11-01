# COMMERCIAL-DS-002B Milestone 1C — Independent Review Handover

**Result: COMPLETE.** The owner explicitly approved the exact O-5 amendment with “yes” in the ChatGPT coordination conversation before implementation. The amendment is recorded in `COMMERCIAL_DS_001_DECISION_LOG.md`. No Milestone 2, contract encoding or downstream model work has started.

## Six-blocker closure matrix

| Blocker | Status | Evidence |
| --- | --- | --- |
| B-1 — destructive seed test harness | **Closed** | Seed derivation occurs only in a temporary directory. Tests verify generated and authoritative seed hashes and assert the authoritative seed is unchanged after the suite. Corruption probes use temporary copies. |
| B-2 — category-sensitive integrity | **Closed** | The authoritative seed SHA/version and frozen category rows, positive/negative/signed amounts, and identifiable/unattributed Decimal amounts are validated. `85123A`→shipping and `85123A`/`POST` swaps fail. M split references are independently reconstructed and separately frozen. |
| B-3 — standalone M credit semantics | **Closed by owner approval and implementation** | Positive standalone M → `standalone_manual_billing`; negative → `standalone_manual_credit`; zero → `standalone_manual_zero_value`; embedded → `manual_adjustment` regardless of sign. No negative credit is paired with an earlier invoice or assigned an inferred economic cause. All manual categories are kept in source reconciliation and excluded from merchandise and behavioral metrics. |
| B-4 — report/document status | **Closed** | Correct identified/unattributed values and coverage are in the verification report. Decision log explicitly states the historical contract specification is planned and not created, and records the owner-approved O-5 amendment. |
| B-5 — row/customer integrity | **Closed** | Every line is keyed by pinned raw V2 SHA and zero-based source row number. Row fingerprint covers canonical source/category fields; customer fingerprint covers per-customer row membership/count and Decimal amounts. Mutation tests detect substitution, duplicate-for-deletion, customer reassignment, de-attribution and customer revenue reassignment. |
| B-6 — null and context typing | **Closed** | One type-aware missing predicate handles `None`, `pd.NA`, NumPy NaN and Python NaN. M requires an explicit Python/NumPy boolean context. Missing, string and numeric context flags fail. |

## Reconstructed M populations

Independent grouping of corrected V2 (not using `classify()`) by invoice merchandise context, exact Decimal quantity × price sign, and customer attribution gives:

| Population | Rows | Sign-specific invoices | Customers | Positive | Negative | Zero rows | Signed | Identifiable | Unattributed |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Standalone billing | 330 | 311 | 109 | 334,379.51 | 0 | 0 | 334,379.51 | 146,916.08 | 187,463.43 |
| Standalone credit | 470 | 443 | 191 | 0 | −421,770.38 | 0 | −421,770.38 | −336,332.43 | −85,437.95 |
| Standalone zero-value | 2 | 2 | 2 | 0 | 0 | 2 | 0 | 0 | 0 |
| Embedded M, in manual adjustment | 601 | 535 overall | 387 overall | 5,624.00 | −1,168.70 | 5 | 4,455.30 | 4,090.87 | 364.43 |
| All M | 1,403 | 1,290 overall | 582 overall | 340,003.51 | −422,939.08 | 7 | −82,935.57 | −185,325.48 | 102,389.91 |

Standalone positive/negative groups overlap by one invoice and multiple customers; sign-specific invoice/customer counts are not additive. Embedded sign-specific details, including identified and unattributed amounts, are in the integration JSON and verification report. Quantity/price signs were checked: negative M amounts are negative quantity at positive unit price; no negative unit-price M rows were observed.

Previous combined standalone category: 802 rows, GBP 334,379.51 positive, GBP −421,770.38 negative, signed GBP −87,390.87, identified −GBP 189,416.35, unattributed GBP 102,025.48. Revised categories transfer exactly those amounts into billing and credit plus two zero rows. Total rows and signed source value do not change.

## Full reconciliation and integrity hashes

- Corrected V2: **1,044,848 rows**, 1,042,714 seed-classified, 2,134 context-classified, 0 unclassified, 0 commercially relevant unclassified.
- Total signed source line value: **GBP 18,909,762.118**.
- Identifiable signed amount: **GBP 16,343,669.038**; unattributed: **GBP 2,566,093.08**.
- Identified customers: 5,942; identified rows: 809,561.
- Row fingerprint: **`80a6d26ec87d2cb1d9988c4fc7f28c2b611f64491caa611405da9f7d7c184022`**. This changes from M1B because category is part of the row fingerprint.
- Customer fingerprint: **`248f421fbcacfaf1e63b3a5a69da78ec3097ce0cfa73c50f1e6ed733e4736d51`**, unchanged.
- Seed SHA-256: **`7b4611c78ca22d108c2616076c84b7c1db2efb8453ee9a32faceb027bb181e4e`**, unchanged.
- V1 source SHA-256: `43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d`.
- V2 source SHA-256: `32569a66f3842a82b0d8c4d63b263c5d98a76bde5d1f65c6c01bf457e541d3a9`.
- Inventory SHA-256: `0d507be1e2b062705ba9763507342db71a24663b0d76176b31a2b39e4f66175b`.

## Tests and reproduction

Executed test command:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s docs/recovery -p 'test_COMMERCIAL_DS_002B_*.py' -v
```

**18 tests passed, 0 failed.** This includes positive, negative, zero and embedded M; invalid/missing context and Python/NumPy booleans; null customer variants; category flips/swaps; row/customer mutation tests; weak-code guards; and seed immutability.

Executed integration twice:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python docs/recovery/COMMERCIAL_DS_002B_INTEGRATION.py > /tmp/COMMERCIAL_DS_002B_M1C_run1.json
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python docs/recovery/COMMERCIAL_DS_002B_INTEGRATION.py > /tmp/COMMERCIAL_DS_002B_M1C_run2.json
cmp /tmp/COMMERCIAL_DS_002B_M1C_run1.json /tmp/COMMERCIAL_DS_002B_M1C_run2.json
shasum -a 256 /tmp/COMMERCIAL_DS_002B_M1C_run1.json /tmp/COMMERCIAL_DS_002B_M1C_run2.json
```

`cmp` passed. Both output SHA-256 hashes are **`1db45949690120c7bf7408473d0a24d52dc2e368943047d1120963d3562d4d04`**. The tests use `PYTHONDONTWRITEBYTECODE=1`; the seed remained unchanged. No raw data, production pipeline, or seed file was modified.

## Remaining scientific limitation

**SUPERSEDED count correction:** the 11 weak-note codes cover 20 corrected-V2 rows, not 22. All 20 are classified `merchandise` by the frozen seed, not context rules. Future rows with nonzero unit price or an identified customer fail closed. Notes such as “given away”, “damaged”, “lost”, “?” and “ebay” do not prove merchandise; a steward must provide evidence before enabling future commercial exposure.

## Changed files and working tree

Implementation/report/decision artifacts changed in the existing untracked `docs/recovery/` tree:

- `COMMERCIAL_DS_001_DECISION_LOG.md`
- `COMMERCIAL_DS_002B_TAXONOMY.py`
- `COMMERCIAL_DS_002B_INTEGRATION.py`
- `test_COMMERCIAL_DS_002B_TAXONOMY.py`
- `test_COMMERCIAL_DS_002B_INTEGRATION.py`
- `COMMERCIAL_DS_002B_MILESTONE1_VERIFICATION.md`
- `COMMERCIAL_DS_002B_MILESTONE1B_REVIEW_HANDOVER.md`
- `COMMERCIAL_DS_002B_MILESTONE1C_REVIEW_HANDOVER.md` (new)

Git status also contains the pre-existing untracked `.vscode/` and `PROJECT_TECHNICAL_HANDOVER.md`. No commit or push was made.

## Claude re-review instructions

Run the test and integration commands above with bytecode writing disabled. Verify the unchanged seed hash before/after the tests, compare the two JSON files, inspect the three revised standalone M categories against the independent grouped amounts, and confirm the row fingerprint changed while the customer fingerprint and source totals stayed fixed. Re-run category flip/swap and row/customer mutation fixtures from scratch. Do not start Milestone 2 as part of this review.

## Complete corrected-V2 category reference

Amounts are GBP signed quantity × unit price; customer attribution is based only on CustomerID presence.

| Category | Rows | Positive | Negative | Signed | Identifiable signed | Unattributed signed |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| bad_debt | 6 | 11,062.06 | −158,676.14 | −147,614.08 | 0 | −147,614.08 |
| commission | 16 | 0 | −7,933.43 | −7,933.43 | −7,933.43 | 0 |
| discount | 173 | 397.89 | −13,277.52 | −12,879.63 | −12,785.34 | −94.29 |
| fee | 136 | 20,987.041 | −277,989.79 | −257,002.749 | 330.001 | −257,332.75 |
| gift_voucher | 103 | 1,839.50 | −69.56 | 1,769.94 | 0 | 1,769.94 |
| manual_adjustment | 671 | 15,252.98 | −3,231.39 | 12,021.59 | 6,860.04 | 5,161.55 |
| merchandise | 1,038,222 | 19,699,671.127 | −719,677.94 | 18,979,993.187 | 16,410,709.747 | 2,569,283.44 |
| non_commercial_stock_movement | 731 | 0 | 0 | 0 | 0 | 0 |
| sample | 102 | 136.85 | −6,137.70 | −6,000.85 | 0 | −6,000.85 |
| shipping | 3,869 | 450,162.53 | −15,567.02 | 434,595.51 | 135,700.87 | 298,894.64 |
| standalone_manual_billing | 330 | 334,379.51 | 0 | 334,379.51 | 146,916.08 | 187,463.43 |
| standalone_manual_credit | 470 | 0 | −421,770.38 | −421,770.38 | −336,332.43 | −85,437.95 |
| standalone_manual_zero_value | 2 | 0 | 0 | 0 | 0 | 0 |
| test | 17 | 226.0 | −22.5 | 203.5 | 203.5 | 0 |
| **Total** | **1,044,848** | **20,534,115.488** | **−1,624,353.37** | **18,909,762.118** | **16,343,669.038** | **2,566,093.08** |
