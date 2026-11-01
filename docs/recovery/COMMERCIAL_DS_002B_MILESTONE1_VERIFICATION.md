# COMMERCIAL-DS-002B Milestone 1 Verification

**Milestone 1B corrected-V2 integration: PASS. Milestone 1C owner-approved O-5 correction: PASS.** The addenda below supersede earlier session snapshots. Corrected-V2 classification, invoice-context checks, category-sensitive and source/customer integrity tests, exact reconciliation, and two-run reproducibility have executed successfully.

## Reviewed historical evidence and newly executed checks

**Historical status note:** statements in the original Milestone 1 snapshot below that say corrected-V2 classification was not executed, describe pre-M1C category totals, or say owner approval / purchase-occasion contract remains pending are historical and superseded by the final Stage A addendum below. They are retained for audit chronology.

The independent 002A review records the approved O-1–O-9 policies, the 22,523-row overlap evidence, 1,044,848 expected corrected rows, and the 351-code/357-row U1 and 366-row administrative-description findings. Newly executed in this session: the existing read-only `COMMERCIAL_DS_002_ANALYSIS.py` completed using `.venv/bin/python`; its pinned source SHA checks and overlap checks passed. The five existing taxonomy unit tests passed (5 tests, 0 failures).

Raw source hashes match the review: V1 `43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d`; V2 `32569a66f3842a82b0d8c4d63b263c5d98a76bde5d1f65c6c01bf457e541d3a9`. Inventory SHA-256: `0d507be1e2b062705ba9763507342db71a24663b0d76176b31a2b39e4f66175b`. Taxonomy seed SHA-256: `7b4611c78ca22d108c2616076c84b7c1db2efb8453ee9a32faceb027bb181e4e`.

The analysis reports V2 blocks of 525,461 and 541,910 rows, overlap multiplicities equal to V1 at exactly 22,523 rows, and 1,044,848 corrected rows (remove the first block overlap; preserve the second block, including its extra `POST` row). The existing taxonomy summary reports 5,132 raw code keys and 357 U1 rows, but this is inventory evidence and is not classifier execution or full row classification.

## Five-key reconciliation

After trim-plus-uppercase normalization, the 5,131-key inventory has 4,775 seed keys, leaving 356 absent keys. The 351 U1 codes are expected to stay unmapped. The remaining five canonical keys are:

| Key | Raw variant | Corrected-V2 rows | Description(s) | Proposed category | Exposure / approved context |
| --- | --- | ---: | --- | --- | --- |
| 23595 | 23595 | 2 | adjustment; re-adjustment | inventory adjustment | Inventory evidence reports zero identifiable positive and negative amount; approved zero-price, unattributed row context applies if actual source fields confirm it. |
| 35600A | 35600A | 1 | Found by jackie | inventory adjustment | Same context and zero reported identifiable exposure. |
| 35605A | 35605A | 1 | damages | inventory adjustment | Same context and zero reported identifiable exposure. |
| 35978 | 35978 | 3 | damages | inventory adjustment | Same context and zero reported identifiable exposure. |
| 84641 | 84641 | 1 | damages | inventory adjustment | Same context and zero reported identifiable exposure. |

These are not the formatting collision (`47503J` / `47503J `), which accounts for the separate 5,132-to-5,131 normalization reduction. The row-context policy is approved by O-2: zero-value and unattributed rows are classified as non-commercial stock movement, while codes remain unmapped. Actual per-row price/customer confirmation and classifier application remain outstanding in this session; thus the rule-based resolution is supported by reviewed inventory evidence but has not passed integration verification.

## Coverage and category reconciliation

The executed historical inventory analysis reports 5,132 corrected-V2 code keys, 4,452 merchandise, 299 merchandise-with-description-exceptions, 357 unclassified U1 rows, plus 30 keys in other categories. It does not report a row-by-row category breakdown. Corrected-V2 total rows are independently pinned to 1,044,848 by the overlap analysis. Seed-classified/context-classified/unclassified row counts, signed amounts by category, identifiable/unattributed category amounts, and exact Decimal classification reconciliation remain **not executed**.

The independent review reports 351 U1 codes / 357 rows, all zero price, no customer and no description (zero revenue and customer exposure). It also reports 366 administrative-description rows on mixed merchandise codes, zero value and unattributed. O-2's narrow zero-price/unattributed row rule is the approved handling. The current classifier's exception is narrower (U1 plus null description, or an injected flag) and therefore does not implement the approved broader context for those 366 rows. No broad description regex was added.

## Invoice-context validation

**SUPERSEDED:** Not executed against corrected-V2 groups. Standalone and embedded `M`, merchandise plus shipping, shipping-only, fee-only, manual-only, test-only, and merchandise plus discount exact counts and amounts are therefore not asserted here. Historical review evidence identifies 375 valid invoices without merchandise (213 manual, 116 shipping, 30 fee, 10 test, 5 discount, 1 mixed) and 26 customers present only through such invoices. O-9 requires purchase occasions to contain merchandise and be on a later calendar day for repeat behavior.

## Tests and reproducibility

Executed command:

```sh
.venv/bin/python -m unittest discover -s docs/recovery -p 'test_COMMERCIAL_DS_002B_TAXONOMY.py' -v
```

Result: 5/5 existing synthetic tests passed. No new integration or negative tests were added. The read-only evidence script was run once:

```sh
.venv/bin/python docs/recovery/COMMERCIAL_DS_002_ANALYSIS.py > /tmp/comm_ds002.json
```

It completed successfully and validated source hashes, overlap, and historical reconciliations. Its output file SHA-256 was not captured; a second run and byte-identity comparison were not performed. Integration output hashes: none. Seed modification: none intended; generator test rewrote the seed to its deterministic generated contents, whose SHA-256 remains the reviewed value above.

## Remaining blockers / next action

Extend the evidence classifier to implement the approved zero-value/unattributed context using raw fields (robust null handling), derive invoice merchandise context independent of row order, and apply it to each corrected-V2 row while retaining `(source_sha256, source_row_number)` identity and customer IDs. Then add and execute the requested integration and negative tests, reconcile exact Decimal amounts and invoice groups, run twice, compare output hashes, and update this report with measured results. Until then the scientific final gate remains PARTIAL.

## Corrected-V2 integration execution (follow-up)

The follow-up integration runner and tests completed. The runner uses `load_sources()` and `source_block_evidence()` from the historical evidence script, applying its source SHA checks, exact 22,523-row overlap correction, incidental-repeat preservation, and 1,044,848-row invariant before classification. Category amounts use Decimal from source numeric values; JSON category keys are sorted.

### Coverage and context results

| Measure | Executed result |
| --- | ---: |
| Corrected-V2 rows | 1,044,848 |
| Seed-classified rows | 1,042,714 |
| Context-classified rows | 2,134 |
| Unclassified rows | 0 |
| Unclassified commercially relevant rows | 0 |
| Observed canonical stock-code keys | 5,131 |
| Seed-mapped canonical keys | 4,775 (92.0618%) — **SUPERSEDED: corrected to 93.0618% in the M1B addendum below** |
| U1 population | 351 codes / 357 rows |
| Administrative-description context rows on mixed merchandise codes | 366 |
| Five inventory-adjustment keys | 8 rows total, all zero value and unattributed |

The five codes resolved from actual corrected-V2 records are `23595` (2 rows), `35600A` (1), `35605A` (1), `35978` (3), and `84641` (1). All have zero signed exposure and no customer attribution. Their row context is limited to those inventory-evidenced code/description pairs (including the blank description on one `35978` row); future commercial value/customer exposure on these unmapped keys still fails closed. The 366 administrative rows are matched by reviewed inventory code/description exception pairs and the row constraints price = 0 and customer missing. Ordinary zero-price merchandise outside those reviewed pairs remains merchandise.

Invoice context is computed as an invoice-level set before row classification, so input order does not affect it. A qualifying merchandise line must use a seed merchandise code and must not be one of the administrative-context rows. Corrected V2 contains 554 embedded-`M` invoices (620 rows, 387 customers, signed amount GBP 18,127.19) and 736 standalone-`M` invoices (783 rows, 236 customers, signed amount GBP −101,062.76). The standalone/embedded test and row-reordering fixture pass. **SUPERSEDED in M1C**: the approved O-5 split and invoice context are documented in the M1C addendum.

### Category row and signed-amount reconciliation

Amounts below are signed quantity × unit price in GBP. Identifiable means CustomerID is present; unattributed means absent.

| Category | Rows | Signed total | Identifiable | Unattributed |
| --- | ---: | ---: | ---: | ---: |
| bad_debt | 6 | −147,614.08 | 0 | −147,614.08 |
| commission | 16 | −7,933.43 | −7,933.43 | 0 |
| discount | 173 | −12,879.63 | −12,785.34 | −94.29 |
| fee | 136 | −257,002.749 | 330.001 | −257,332.75 |
| gift_voucher | 103 | 1,769.94 | 0 | 1,769.94 |
| manual_adjustment | 690 | 25,693.48 | 6,860.04 | 18,833.44 |
| manual_billing | 783 | −101,062.76 | −189,416.35 | 88,353.59 — **SUPERSEDED in M1C by three standalone M categories** |
| merchandise | 1,038,222 | 18,979,993.187 | 16,410,709.747 | 2,569,283.44 |
| non_commercial_stock_movement | 731 | 0.0 | 0 | 0.0 |
| sample | 102 | −6,000.85 | 0 | −6,000.85 |
| shipping | 3,869 | 434,595.51 | 135,700.87 | 298,894.64 |
| test | 17 | 203.5 | 203.5 | 0.0 |
| **Total** | **1,044,848** | **18,909,762.118** | **16,353,668.068 — SUPERSEDED** | **2,556,094.05 — SUPERSEDED** |

Category row counts sum exactly to 1,044,848. Identifiable plus unattributed signed amounts reconcile to the category total; monetary values were not rounded before serialization. This all-row signed amount is a taxonomy line-value total, not the DS-002 gross/current revenue bridge measure, whose line eligibility masks differ.

### Tests and reproducibility

Executed:

```sh
.venv/bin/python -m unittest discover -s docs/recovery -p 'test_COMMERCIAL_DS_002B_*.py' -v
.venv/bin/python docs/recovery/COMMERCIAL_DS_002B_INTEGRATION.py > /tmp/COMMERCIAL_DS_002B_INTEGRATION_run1.json
.venv/bin/python docs/recovery/COMMERCIAL_DS_002B_INTEGRATION.py > /tmp/COMMERCIAL_DS_002B_INTEGRATION_run2.json
cmp /tmp/COMMERCIAL_DS_002B_INTEGRATION_run1.json /tmp/COMMERCIAL_DS_002B_INTEGRATION_run2.json
```

**Tests: 11 passed, 0 failed.** The five original synthetic tests remain; six integration tests cover corrected-V2 row/category reconciliation, absence of unclassified rows, U1 and five-code populations, administrative context and merchandise preservation, standalone/embedded M and ordering invariance, and unknown described-code rejection.

Both JSON output hashes are `3940d2b0c32394e49d16c574f612dd6a41a0fe57c8838bdc1b591b1c8273f1df`; `cmp` confirmed byte identity. Source hashes remain V1 `43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d`, V2 `32569a66f3842a82b0d8c4d63b263c5d98a76bde5d1f65c6c01bf457e541d3a9`, inventory `0d507be1e2b062705ba9763507342db71a24663b0d76176b31a2b39e4f66175b`, and seed `7b4611c78ca22d108c2616076c84b7c1db2efb8453ee9a32faceb027bb181e4e`. The seed was not modified. Outputs are in `/tmp`, outside the repository.

Runner command: `.venv/bin/python docs/recovery/COMMERCIAL_DS_002B_INTEGRATION.py`.

## Milestone 1B correction addendum

This addendum supersedes the earlier hand-transcribed identifiable/unattributed figures and the earlier M context counts above. Historical measurements are retained above as a record; the figures below are generated and checked by the current runner.

- Correct signed identified amount: **GBP 16,343,669.038**; unattributed amount: **GBP 2,566,093.08**; signed all-row total: **GBP 18,909,762.118**.
- Seed coverage: **4,775 / 5,131 = 93.0617818%**. This corrects the earlier 92.0618% figure marked SUPERSEDED above.
- Total positive line value is GBP 20,534,115.488; total negative line value is GBP −1,624,353.37. Merchandise gross positive is GBP 19,699,671.127; merchandise returns are GBP −719,677.94 (GBP −713,031.25 identified and GBP −6,646.69 unattributed). These are taxonomy signed line values, not a revenue bridge.

The suite no longer writes the authoritative seed. It derives to a temporary path; both the generated and checked seed hash must equal `7b4611c78ca22d108c2616076c84b7c1db2efb8453ee9a32faceb027bb181e4e`. Tests assert the seed hash after the suite. A seed category flip (`85123A` merchandise→shipping) and a two-key category swap preserving global rows/revenue are both rejected by the seed integrity pin. Full expected per-category rows, positive, negative, signed, identifiable and unattributed Decimal amounts are also frozen in the integration implementation.

Missing customer values use a shared type-aware predicate for `None`, `pd.NA`, NumPy NaN and Python NaN. Literal description text such as `"nan"`, `"None"`, and `"<NA>"` is not treated as null. `M` classification now rejects absent, string and numeric context flags; it accepts explicit Python and NumPy booleans. For non-cancellation invoices, merchandise context requires a positive merchandise line amount. Nonzero merchandise returns qualify on cancellation invoices. This N-2 refinement moves 19 `M` rows (GBP 13,671.89 positive, mostly unattributed) from embedded to standalone; see current M counts below.

### Current category reference

| Category | Rows | Positive | Negative | Signed | Identifiable signed | Unattributed signed |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| merchandise | 1,038,222 | 19,699,671.127 | −719,677.94 | 18,979,993.187 | 16,410,709.747 | 2,569,283.44 |
| shipping | 3,869 | 450,162.53 | −15,567.02 | 434,595.51 | 135,700.87 | 298,894.64 |
| manual_billing (current O-5 implementation, standalone M) | 802 | 334,379.51 | −421,770.38 | −87,390.87 | −189,416.35 | 102,025.48 |
| manual_adjustment (ADJUST* and embedded M) | 671 | 15,252.98 | −3,231.39 | 12,021.59 | 6,860.04 | 5,161.55 |
| fee | 136 | 20,987.041 | −277,989.79 | −257,002.749 | 330.001 | −257,332.75 |
| bad_debt | 6 | 11,062.06 | −158,676.14 | −147,614.08 | 0 | −147,614.08 |
| discount | 173 | 397.89 | −13,277.52 | −12,879.63 | −12,785.34 | −94.29 |
| commission | 16 | 0 | −7,933.43 | −7,933.43 | −7,933.43 | 0 |
| sample | 102 | 136.85 | −6,137.70 | −6,000.85 | 0 | −6,000.85 |
| gift_voucher | 103 | 1,839.50 | −69.56 | 1,769.94 | 0 | 1,769.94 |
| test | 17 | 226.0 | −22.5 | 203.5 | 203.5 | 0 |
| non_commercial_stock_movement | 731 | 0 | 0 | 0 | 0 | 0 |
| **Total** | **1,044,848** | **20,534,115.488** | **−1,624,353.37** | **18,909,762.118** | **16,343,669.038** | **2,566,093.08** |

## COMMERCIAL-DS-003 Stage A — source integrity and contract verification (2026-10-31)

This addendum supersedes historical status notes above. It records newly executed Stage A checks; it does not implement purchase-occasion production outputs or downstream analytics.

### Source identity, overlap and frozen fingerprints

Raw V2 row IDs are assigned as zero-based data-row positions immediately after CSV load, before renaming, overlap removal, sorting or filtering. The correction removed exactly raw IDs 502,938–525,460 inclusive (22,523 rows); all other source IDs are unique and retained. Corrected V2 has 1,044,848 rows spanning source IDs 0–1,067,370. Incidental duplicate business rows remain distinct by source-row ID. The integration reports and validates these facts.

The legacy reviewed row fingerprint remains bit-identical: `80a6d26ec87d2cb1d9988c4fc7f28c2b611f64491caa611405da9f7d7c184022`. The country-sensitive classification fingerprint is `d76696efc5d02069d1180c84286e813973f810ca8fbf2b356ebc03f45bca1a04`. The separate source-content fingerprint, including raw code, description and country, is `59970949b45bf75263217525fa9f437c672d39503c7b2c605275601546299c6d`. Customer fingerprint remains `248f421fbcacfaf1e63b3a5a69da78ec3097ce0cfa73c50f1e6ed733e4736d51`. The independent Stage A pin file is SHA-256 `a96d2e9d5787dc1edd0e5c493e072ede4c342e845921e3242e90742625c8ba49`; normal integration runs verify its own external file hash and each pinned value rather than regenerating it.

Mutation tests detect country, category, date, source-row, stock-code and customer changes; source-content fingerprint detects description mutations. Reordering records without altering identities/content leaves canonical fingerprints unchanged. Runtime references are frozen in `COMMERCIAL_DS_003_STAGE_A_REFERENCE_PINS.json`.

### Corrected-V2 coverage and reconciliation

Executed corrected-V2 totals: 1,044,848 rows; 1,042,714 seed-classified rows; 2,134 context-classified rows; zero unclassified and zero commercially relevant unclassified rows. Canonical coverage is 4,775 / 5,131 = 93.0617813292%; 356 keys are unmapped after normalization (351 U1 keys plus five inventory-adjustment codes). U1 remains 351 codes / 357 rows. The five inventory-adjustment keys and observed populations are `23595` (2 rows), `35600A` (1), `35605A` (1), `35978` (3), and `84641` (1); all eight observed rows are zero-value and unattributed under their approved row context. The narrow administrative-description exception classifies 366 rows as `non_commercial_stock_movement`; ordinary merchandise on mixed codes remains merchandise.

| Category | Rows | Positive GBP | Negative GBP | Signed GBP | Identifiable GBP | Unattributed GBP |
|---|---:|---:|---:|---:|---:|---:|
| merchandise | 1,038,222 | 19,699,671.127 | −719,677.94 | 18,979,993.187 | 16,410,709.747 | 2,569,283.44 |
| shipping | 3,869 | 450,162.53 | −15,567.02 | 434,595.51 | 135,700.87 | 298,894.64 |
| standalone_manual_billing | 330 | 334,379.51 | 0 | 334,379.51 | 146,916.08 | 187,463.43 |
| standalone_manual_credit | 470 | 0 | −421,770.38 | −421,770.38 | −336,332.43 | −85,437.95 |
| standalone_manual_zero_value | 2 | 0 | 0 | 0 | 0 | 0 |
| manual_adjustment | 671 | 15,252.98 | −3,231.39 | 12,021.59 | 6,860.04 | 5,161.55 |
| fee | 136 | 20,987.041 | −277,989.79 | −257,002.749 | 330.001 | −257,332.75 |
| bad_debt | 6 | 11,062.06 | −158,676.14 | −147,614.08 | 0 | −147,614.08 |
| discount | 173 | 397.89 | −13,277.52 | −12,879.63 | −12,785.34 | −94.29 |
| commission | 16 | 0 | −7,933.43 | −7,933.43 | −7,933.43 | 0 |
| sample | 102 | 136.85 | −6,137.70 | −6,000.85 | 0 | −6,000.85 |
| gift_voucher | 103 | 1,839.50 | −69.56 | 1,769.94 | 0 | 1,769.94 |
| test | 17 | 226.0 | −22.5 | 203.5 | 203.5 | 0 |
| non_commercial_stock_movement | 731 | 0 | 0 | 0 | 0 | 0 |
| **Total** | **1,044,848** | **20,534,115.488** | **−1,624,353.37** | **18,909,762.118** | **16,343,669.038** | **2,566,093.08** |

Category row counts sum exactly to corrected V2; signed categories sum to GBP 18,909,762.118. Identifiable plus unattributed is exactly the same total. The seed hash is unchanged. Historical weak-code count 22 is superseded: 11 weak-note codes cover 20 observed zero-value, unattributed rows, all currently classified merchandise by the seed, not context. The existing future-exposure guard remains fail-closed.

### O-5 cancellation-invoice semantics

The reviewed context predicate remains exact: a non-cancellation invoice is merchandise-bearing when it has a non-row-context seed-merchandise line with positive value; a cancellation invoice is merchandise-bearing when it has a non-row-context merchandise line with nonzero return value. The cancellation clause retains embedded classification for 64 negative `M` rows, GBP −1,168.70 across 52 invoices and 47 customers. They remain `manual_adjustment`; no causal linkage to merchandise returns is inferred. Purchase occasions have the stricter independent predicate in `COMMERCIAL_DS_002B_CONTRACT_SPECIFICATION.md` and do not use the `M` context set.

### Tests and reproducibility

Executed: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s docs/recovery -p 'test_COMMERCIAL_DS_00*.py' -v` — 26 tests passed. The suite covers taxonomy, null semantics, strict context flags, corruption and mutation detection, source-ID ingestion, invoice-order invariance and the test-only C-1/O-9 contract oracle, including invalid date, multi-customer invoice and inconsistent invoice-date failures.

Executed twice: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python docs/recovery/COMMERCIAL_DS_002B_INTEGRATION.py`, writing respectively to `/tmp/COMMERCIAL_DS_003_STAGE_A_RUN1.json` and `/tmp/COMMERCIAL_DS_003_STAGE_A_RUN2.json`. `cmp -s` succeeded. Both output SHA-256 hashes are `2ffcbef73482a05572983019c535c12384fc2fcbf935bbc0a2581f7be695dd6b`. Source V1 SHA-256 `43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d`; V2 `32569a66f3842a82b0d8c4d63b263c5d98a76bde5d1f65c6c01bf457e541d3a9`; inventory `0d507be1e2b062705ba9763507342db71a24663b0d76176b31a2b39e4f66175b`; seed `7b4611c78ca22d108c2616076c84b7c1db2efb8453ee9a32faceb027bb181e4e`.

### Current M context and unresolved owner policy

**SUPERSEDED by owner-approved O-5 amendment:** After the positive-merchandise-line context refinement, corrected V2 has 755 standalone-M invoices (802 rows, 236 customers; positive GBP 334,379.51, negative GBP −421,770.38, signed GBP −87,390.87) and 535 embedded-M invoices (601 rows, 387 customers; positive GBP 5,624.00, negative GBP −1,168.70, signed GBP 4,455.30). Standalone M credits are **not** assigned a new category: absent explicit owner approval, the current O-5 classifier still places all standalone M rows in `manual_billing`. This leaves the scientific issue identified in the independent review open: 127 of 191 customers with standalone M credits have no standalone billing history, and the economic meaning of those credits is unresolved. Positive standalone billing / negative standalone credit / zero-value standalone treatment is pending owner decision. No R1/R4 interpretation or Milestone 2 work is authorised by this result.

### Row and customer integrity

**SUPERSEDED source-ID implementation note:** Each corrected line carries raw V2 `source_row_number` (zero-based), derived from the preserved block order: corrected positions `[0, 502,938)` map directly; later positions map to raw position +22,523. The row checksum uses canonical sorted JSON records with explicit null status and length-prefixed serialization. It includes source hash, source row, canonical code, invoice, customer, quantity, unit price, date and category. The corrected rows cover unique raw source positions 0–1,067,370 excluding the verified 22,523-row removed block. Stage A assigns these IDs at raw ingestion and fingerprints country as well.

- **SUPERSEDED historical row identity SHA-256:** `2f9f13c59fcb333a6fe9f3555735ff4d481443cef8f1d672bdfcdd902a0c6ca9` (1,044,848 rows).
- Customer fingerprint SHA-256: `248f421fbcacfaf1e63b3a5a69da78ec3097ce0cfa73c50f1e6ed733e4736d51` (5,942 identified customers, 809,561 rows, signed GBP 16,343,669.038). Each customer summary includes row count, signed amount and source row identities.
- Adversarial tests prove failure for row substitution, duplicate-for-deletion, invoice/customer reassignment, identified-to-null mutation and customer revenue reassignment, including cases preserving total rows or signed revenue.

### Weakly supported merchandise notes

The 11 inventory descriptions are administrative/ambiguous rather than product names. Their current source populations are all zero-price, unattributed, and have zero positive/negative line value; total exposure is GBP 0 and zero identified customers. The current mapping is retained pending better evidence, not silently changed:

| Code | Rows | Description | Positive / negative value | Customer exposure | Assessment |
| --- | ---: | --- | ---: | ---: | --- |
| 15002 | 1 | rex use | 0 / 0 | 0 | Unsupported as a future commercial merchandise mapping |
| 20852 | 5 | Given away | 0 / 0 | 0 | Unsupported as a future commercial merchandise mapping |
| 22126 | 3 | given away | 0 / 0 | 0 | Unsupported as a future commercial merchandise mapping |
| 23059 | 1 | Thrown away-rusty | 0 / 0 | 0 | Unsupported as a future commercial merchandise mapping |
| 35643 | 2 | ? | 0 / 0 | 0 | Ambiguous; no commercial evidence |
| 35956 | 1 | lost | 0 / 0 | 0 | Unsupported as a future commercial merchandise mapping |
| 72038B | 1 | damaged | 0 / 0 | 0 | Unsupported as a future commercial merchandise mapping |
| 72732 | 2 | thrown away-can't sell | 0 / 0 | 0 | Unsupported as a future commercial merchandise mapping |
| 72759 | 2 | thrown away-can't sell. | 0 / 0 | 0 | Unsupported as a future commercial merchandise mapping |
| DCGS0067 | 1 | ebay | 0 / 0 | 0 | Ambiguous channel note; no commercial evidence |
| DCGS0073 | 1 | ebay | 0 / 0 | 0 | Ambiguous channel note; no commercial evidence |

**SUPERSEDED:** this earlier count of 22 was incorrect. The independent M2 Stage A recheck confirms **20** observed rows; they receive `merchandise` from the frozen seed, not context classification. The mapping is weak for future commercial exposure. No revenue-bearing classification was inferred from these notes.

### Executed commands and reproducibility

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s docs/recovery -p 'test_COMMERCIAL_DS_002B_*.py' -v
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python docs/recovery/COMMERCIAL_DS_002B_INTEGRATION.py > /tmp/COMMERCIAL_DS_002B_M1B_run1.json
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python docs/recovery/COMMERCIAL_DS_002B_INTEGRATION.py > /tmp/COMMERCIAL_DS_002B_M1B_run2.json
cmp /tmp/COMMERCIAL_DS_002B_M1B_run1.json /tmp/COMMERCIAL_DS_002B_M1B_run2.json
```

The corrected suite completed **17 tests, 0 failures**. Seed SHA before/after tests remains `7b4611c78ca22d108c2616076c84b7c1db2efb8453ee9a32faceb027bb181e4e`. Both output files are byte-identical (`cmp` exit 0); their SHA-256 is `99bdb765036b1c2bca7c1502b01c75ce49e8feec7a89531eaf567b6214501105`.

## Milestone 1C — owner-approved O-5 amendment

The owner explicitly approved the O-5 amendment with the response “yes” in the ChatGPT coordination conversation before this implementation turn. The matching amendment is recorded in `COMMERCIAL_DS_001_DECISION_LOG.md`. This addendum supersedes the Milestone 1B statement that B-3 was pending.

Standalone `M` is defined by the frozen invoice context: the invoice contains no qualifying positive merchandise line. A standalone `M` row is classified by exact Decimal `Quantity × UnitPrice`: positive → `standalone_manual_billing`; negative → `standalone_manual_credit`; zero → `standalone_manual_zero_value`. Embedded `M` remains `manual_adjustment` regardless of sign. Manual credits are retained in source-value reconciliation but are not attributed to prior invoices or described as merchandise refunds. All manual categories are excluded from merchandise sales/returns and behavioural purchase, retention, repeat and customer-value measures.

### Independently reconstructed M split

An independent corrected-V2 grouping, without using `classify()`, joined `M` to the invoice-level qualifying-merchandise set and grouped exact Decimal quantity × price by sign and customer nullness. Results:

| Category/population | Rows | Sign-specific invoices* | Customers* | Positive | Negative | Zero rows | Signed | Identifiable signed | Unattributed signed |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Standalone manual billing | 330 | 311 | 109 | 334,379.51 | 0 | 0 | 334,379.51 | 146,916.08 | 187,463.43 |
| Standalone manual credit | 470 | 443 | 191 | 0 | −421,770.38 | 0 | −421,770.38 | −336,332.43 | −85,437.95 |
| Standalone manual zero value | 2 | 2 | 2 | 0 | 0 | 2 | 0 | 0 | 0 |
| Embedded M (manual adjustment component) | 601 | 535 overall | 387 overall | 5,624.00 | −1,168.70 | 5 | 4,455.30 | 4,090.87 | 364.43 |
| **All M** | **1,403** | **1,290 overall** | **582 overall** | **340,003.51** | **−422,939.08** | **7** | **−82,935.57** | **−185,325.48** | **102,389.91** |

For embedded M, the 532 positive rows are on 478 sign-specific invoices / 347 customers; 64 negative rows are on 52 invoices / 47 customers; 5 zero rows are on 5 invoices / 5 customers. Embedded amounts by attribution are: positive GBP 5,250.24 identified / GBP 373.76 unattributed; negative GBP −1,159.37 identified / GBP −9.33 unattributed; zero GBP 0. The 601 embedded M rows are part of the `manual_adjustment` total together with `ADJUST*` rows.

For standalone M, sign-specific invoice/customer counts overlap: one invoice contains both positive and negative M rows, and customer groups overlap. The overall standalone totals are 802 rows, 755 invoices, 236 customers, positive GBP 334,379.51, negative GBP −421,770.38, signed GBP −87,390.87. The sign split exactly reconciles to that prior combined standalone category. The all-row source total, identified/unattributed totals, and customer fingerprint are unchanged.

Quantity/price sign audit: standalone negative M consists of 470 rows with negative quantity and positive unit price; standalone positive consists of 330 rows with positive quantity and positive unit price; two zero rows have positive quantity and zero unit price. Embedded negative M consists of 64 negative-quantity/positive-price rows, positive M of 532 positive-quantity/positive-price rows, and five zero-quantity rows have zero amount. No negative-price quantity pattern was observed in M.

### Frozen category changes and reconciliations

The former `manual_billing` reference (802 rows; positive GBP 334,379.51; negative GBP −421,770.38; signed GBP −87,390.87; identified −GBP 189,416.35; unattributed GBP 102,025.48) was replaced with the three independently reconstructed standalone categories above. Exact transfers:

- GBP 334,379.51 positive signed value → `standalone_manual_billing` (330 rows).
- GBP −421,770.38 negative signed value → `standalone_manual_credit` (470 rows).
- 2 zero-value rows → `standalone_manual_zero_value` (GBP 0).
- 802 total rows remain 802; global signed source total remains GBP 18,909,762.118.
- `manual_adjustment` remains 671 rows, signed GBP 12,021.59 (embedded M plus adjustments).

All other frozen category references remain unchanged. Corrected V2 still reconciles 1,044,848 rows, with zero unclassified commercially relevant rows. Identifiable signed value remains GBP 16,343,669.038 and unattributed signed value GBP 2,566,093.08. The row fingerprint changes from the Milestone 1B value because it intentionally includes classification category; the new value is recorded in the M1C handover. The customer fingerprint remains unchanged because it fingerprints source-row membership and amounts per customer, not category labels.

### 11 weak-note merchandise codes

The mapping stays as observed. The classifier fails closed if any of the 11 codes has nonzero unit price or an identified customer. **Corrected count: 20 observed zero-price/unattributed rows, all classified merchandise by the frozen seed (not context-classified).** The evidence limitation remains: descriptions (“rex use”, “given away”, “thrown away”, “?”, “lost”, “damaged”, “ebay”) do not prove merchandise. No future revenue classification is inferred.

### Validation execution

Full test suite: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s docs/recovery -p 'test_COMMERCIAL_DS_002B_*.py' -v` — **18 passed, 0 failed**. Tests cover all four M cases, invalid/missing and Python/NumPy boolean contexts, null customer forms, frozen category values, category corruption/swaps, source/customer mutations, weak-code future exposure, and seed immutability.

Two final integration runs use `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python docs/recovery/COMMERCIAL_DS_002B_INTEGRATION.py`, write to `/tmp/COMMERCIAL_DS_002B_M1C_run1.json` and `...run2.json`, and compare byte-identically. Both output SHA-256 values are `1db45949690120c7bf7408473d0a24d52dc2e368943047d1120963d3562d4d04`. New row fingerprint is `80a6d26ec87d2cb1d9988c4fc7f28c2b611f64491caa611405da9f7d7c184022`; customer fingerprint remains `248f421fbcacfaf1e63b3a5a69da78ec3097ce0cfa73c50f1e6ed733e4736d51`; seed SHA remains `7b4611c78ca22d108c2616076c84b7c1db2efb8453ee9a32faceb027bb181e4e`. No raw source or seed mapping was changed.

### Complete current category reference after O-5 split

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
