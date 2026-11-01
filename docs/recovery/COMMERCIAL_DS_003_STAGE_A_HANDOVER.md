# COMMERCIAL-DS-003 Stage A — Contract Foundation Handover

**Status: COMPLETE. Stage B may begin.** The approved taxonomy and O-5 semantics are preserved. Stage A closes the independent review conditions C-1 through C-6, verifies source identity and frozen integrity references, and defines/tests the purchase-occasion contract. It does not implement a revenue bridge, occasion production pipeline, retention cohorts, labels or models.

## 1. C-1 through C-6 disposition

| Condition | Disposition | Evidence |
|---|---|---|
| C-1 — binding occasion eligibility | Closed as a formal/tested specification. | [Contract specification](COMMERCIAL_DS_002B_CONTRACT_SPECIFICATION.md) defines the strict qualifying merchandise line and customer × invoice grain; test-only oracle verifies eligibility and edge cases. The integration `M` invoice set is explicitly excluded. No production occasion builder was created. |
| C-2 — source-row identity | Closed. | Raw zero-based `source_row_number` is assigned in `load_sources()` at CSV ingestion before transformations. Exactly 22,523 source IDs 502,938–525,460 are removed. Corrected rows retain every other original ID, unique and stable under filtering/sorting. |
| C-3 — integrity coverage/runtime pins | Closed. | Country is in the category-sensitive row fingerprint; description and raw code are included in a separate source-content fingerprint. `build_report()` validates externally frozen references and the pin file hash on every run. Legacy reviewed row and customer fingerprints reproduce unchanged. Country, description, date, source ID and category mutation tests fail as expected; row reorder with identities preserved is invariant. |
| C-4 — O-5 cancellation context | Closed. | Decision log states non-cancellation merchandise context requires positive value; cancellation context requires a nonzero merchandise return. The 64 negative `M` rows (GBP −1,168.70; 52 invoices; 47 customers) remain embedded `manual_adjustment`. No return linkage or cause is inferred; no further owner decision is required under the reviewed interpretation. |
| C-5 — weak-code and historical documentation | Closed. | The 11 weak-note codes cover 20 rows, not 22. They are classified as merchandise by the frozen seed, not row context; all are zero-value and unattributed. Future priced or identified rows fail closed. Verification report marks stale values/status statements SUPERSEDED and adds current measurements. |
| C-6 — owner approval source | Closed per independent review. | Decision log retains the explicit owner approval (“yes” in the ChatGPT coordination conversation) for the O-5 split. Approval scope and limits remain documented; no broader semantic approval is inferred. |

## 2. Source identity and overlap verification

The V2 loader materialises IDs `0..1,067,370` before renaming, sorting, slicing or overlap correction. The only removed block is zero-based source row 502,938 through 525,460 inclusive (22,523 rows), the approved first V1-overlap copy. Corrected V2 contains 1,044,848 rows and retains unique source IDs from 0 through 1,067,370 with precisely that interval absent. Incidental exact repeats remain with their separate IDs. A synthetic loader test verifies filtering and sorting retain their initial IDs and refuses reassignment.

The legacy row fingerprint is unchanged (`80a6d26ec87d2cb1d9988c4fc7f28c2b611f64491caa611405da9f7d7c184022`). New country-sensitive category fingerprint: `d76696efc5d02069d1180c84286e813973f810ca8fbf2b356ebc03f45bca1a04`. Separate source-content fingerprint, including description/raw code/country: `59970949b45bf75263217525fa9f437c672d39503c7b2c605275601546299c6d`. Customer fingerprint unchanged: `248f421fbcacfaf1e63b3a5a69da78ec3097ce0cfa73c50f1e6ed733e4736d51`. The production evidence runner loads frozen values from `COMMERCIAL_DS_003_STAGE_A_REFERENCE_PINS.json`, verifies that file's pinned SHA-256, and compares each value; it cannot silently regenerate expected references.

Adversarial checks detect country, description (in source-content integrity), date, category, source-row substitution, stock-code substitution, duplicate-for-deletion, customer reassignment and de-attribution. Sorting/reordering rows while preserving source IDs/content produces the same canonical fingerprints.

## 3. Corrected-V2 coverage and financial reconciliation

| Coverage measure | Result |
|---|---:|
| Corrected-V2 source rows | 1,044,848 |
| Seed-classified rows | 1,042,714 |
| Context-classified rows | 2,134 |
| Unclassified rows | 0 |
| Commercially relevant unclassified rows | 0 |
| Canonical keys | 5,131 |
| Seed-mapped keys | 4,775 (93.0617813292%) |
| Unmapped keys | 356 = 351 U1 + 5 inventory-adjustment |
| U1 rows | 357 across 351 codes |
| Administrative-description exception rows | 366 |

The complete category breakdown, including rows, positive/negative/signed amounts and identifiable/unattributed components, is in the Stage A addendum to [the verification report](COMMERCIAL_DS_002B_MILESTONE1_VERIFICATION.md). Reconciliation is exact: categories sum to 1,044,848 rows and GBP 18,909,762.118 signed; identifiable GBP 16,343,669.038 plus unattributed GBP 2,566,093.08 equals that total.

The five non-U1 unmapped keys have observed populations `23595` (2), `35600A` (1), `35605A` (1), `35978` (3), `84641` (1), all eight zero-value and unattributed under the existing explicit inventory context. The 20 weak-note rows remain seed-classified merchandise; their current zero-value/no-customer state and future exposure guard are retained without claiming scientific proof of merchandise.

## 4. Purchase-occasion eligibility specification

A qualifying source line must have category exactly `merchandise`, finite exact Decimal quantity > 0, finite exact Decimal unit price > 0, valid losslessly canonical integer customer ID, non-empty invoice ID not beginning with cancellation prefix `C`, and valid invoice date. Group qualifying rows at `(customer_id, invoice_id)`, require an invoice to map to at most one customer and require a single calendar date within the invoice. Occasion revenue sums qualifying merchandise lines only; lineage is the sorted source-row IDs of those lines. Non-merchandise lines on the same invoice remain in reconciliation but contribute no eligibility, amount or lineage.

Primary repeat definition is a qualifying occasion on a strictly later calendar date; multiple invoices on one day are not a second primary occasion. Invoice-level repeat is a separate sensitivity where same-day distinct invoices may count. O-5 M-context is separate and must not be reused for occasions. The contract document defines failure behavior and invariants. `test_COMMERCIAL_DS_003_CONTRACT.py` exercises a test-only eligibility oracle, not a production analytics implementation.

## 5. O-5 cancellation-invoice interpretation

On ordinary invoices, positive merchandise line value establishes context; on cancellation invoices, nonzero merchandise return value establishes context. This preserves 64 negative M adjustments on 52 cancellation invoices (47 customers), amount GBP −1,168.70. They remain manual adjustments, stay in full source reconciliation, and are excluded from merchandise purchase occasions and behavioural measures. Nothing states that a manual credit refunds a specific merchandise return. The owner-approved positive/negative/zero standalone split and this limitation remain in the decision log.

## 6. Tests, hashes and reproduction

Executed command:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s docs/recovery -p 'test_COMMERCIAL_DS_00*.py' -v
```

Result: **26 tests passed, 0 failed**. Coverage includes existing synthetic taxonomy tests, full-data coverage/category references, seed corruption and immutability, context and null semantics, all specified source/customer mutations, row-ID ingestion, administrative-description and weak-code safeguards, M categories/order invariance, and test-only contract eligibility/repeat sensitivity. The contract oracle also rejects invalid dates, multi-customer invoices and inconsistent invoice dates.

Run integration twice:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python docs/recovery/COMMERCIAL_DS_002B_INTEGRATION.py > /tmp/COMMERCIAL_DS_003_STAGE_A_RUN1.json
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python docs/recovery/COMMERCIAL_DS_002B_INTEGRATION.py > /tmp/COMMERCIAL_DS_003_STAGE_A_RUN2.json
cmp -s /tmp/COMMERCIAL_DS_003_STAGE_A_RUN1.json /tmp/COMMERCIAL_DS_003_STAGE_A_RUN2.json
shasum -a 256 /tmp/COMMERCIAL_DS_003_STAGE_A_RUN1.json /tmp/COMMERCIAL_DS_003_STAGE_A_RUN2.json
```

`cmp` succeeded. Both output hashes: `2ffcbef73482a05572983019c535c12384fc2fcbf935bbc0a2581f7be695dd6b`.

| Input/reference | SHA-256 |
|---|---|
| V1 source | `43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d` |
| V2 source | `32569a66f3842a82b0d8c4d63b263c5d98a76bde5d1f65c6c01bf457e541d3a9` |
| Inventory | `0d507be1e2b062705ba9763507342db71a24663b0d76176b31a2b39e4f66175b` |
| Authoritative taxonomy seed (unchanged) | `7b4611c78ca22d108c2616076c84b7c1db2efb8453ee9a32faceb027bb181e4e` |
| Frozen Stage A reference file | `a96d2e9d5787dc1edd0e5c493e072ede4c342e845921e3242e90742625c8ba49` |

No raw data, production pipeline or seed was modified. Tests ran with bytecode writes disabled; no generated repository outputs were used.

## 7. Remaining uncertainties and readiness

The weak-note evidence does not prove the 11 mappings are merchandise; the guard safely blocks future commercially exposed rows until evidence supports them. The economic cause of standalone manual credits remains unknown by design. Stage A did not execute purchase-occasion analytics, so no occasion counts, retention outcomes or revenue bridge are claimed here. The written and test-oracle contract is ready to guide Stage B implementation; downstream work must retain the frozen source, taxonomy, row lineage, eligibility and failure invariants.

**Stage B readiness: READY.**
