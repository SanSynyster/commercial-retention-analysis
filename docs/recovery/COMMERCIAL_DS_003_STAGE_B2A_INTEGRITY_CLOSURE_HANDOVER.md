# COMMERCIAL-DS-003 Stage B2A Integrity Closure — B2B-1

## Disposition

**Implementation is ready for Claude Code's focused independent re-review. Stage B2B analytics have not begun.**

B2B-1's defect was a mismatch between the trusted object and the trusted rows. `_validate_purchase_input()` checked a stored report against Stage A pins and compared the frame with a digest stored beside that same frame. A caller using private Python names could alter a non-occasion row, recompute that digest, and retain the original report. Because the bridge checked only grand totals, category reassignment could pass while corrupting leaf results.

## Corrected trust boundary

Every supported production consumer (`build_purchase_occasions`, `build_real_data_report`, and `build_revenue_bridge`) calls `_validate_purchase_input`. It now:

1. Retains the frame digest as an accidental-mutation guard.
2. Recomputes the Stage A row/classification, legacy row, source-content, and customer fingerprints from the actual frame being consumed. Reconstructed records include source row ID, customer/null status, transaction date, canonical and raw stock code, invoice, country, description, quantity, unit price, and category.
3. Compares the computed fingerprints with the separately frozen Stage A reference file after verifying its hard-coded SHA-256, and verifies the raw source and authoritative seed hashes against that pin.
4. Recomputes all Stage A category row and signed attribution/amount totals from those same rows.
5. Only then allows the occasion or bridge producer to continue.

Cached reports, cached digests, and the module token are not evidence for the frame's actual content. A forged wrapper with a recomputed digest therefore fails the data-derived reference checks. The source loader and source-row identity assignment are unchanged. Synthetic occasion construction remains explicitly internal/test-only; it cannot enter production consumers.

The bridge independently checks all 16 leaf references and the complete reconciliation before returning a result. Checks include row and sign counts, exact signed/identified/unattributed Decimal totals, and a collision-safe fingerprint of sorted source-row membership. Reference values are stored separately in `COMMERCIAL_DS_003_STAGE_B2A_BRIDGE_REFERENCE_PINS.json`; runtime code verifies its frozen SHA and never regenerates expected values.

## Frozen reference provenance

Claude Code's Stage B2A review §3 records an independent stdlib CSV + Decimal reconstruction, verifies all 16 categories across the eight reported measures and confirms the full sorted source-row lineage is disjoint and exhaustive. The pins capture those independently reviewed category values and membership; the membership hash encoding is SHA-256 over length-prefixed canonical JSON source-row IDs in sorted order. The complete pin reconciles to the reviewed signed total GBP 18,909,762.118, identifiable GBP 16,343,669.038 and unattributed GBP 2,566,093.08.

The pin file SHA-256 is `765ff7a29530b4221ec3ab171fc2ed861fcb9247901ba84419d2ecf7e786e96d`. Stage A and taxonomy reference pins were not changed.

## Full 16-category reconciliation

Amounts are GBP. Positive and negative fields are signed components; zero rows are separately counted. Category rows partition all corrected-V2 rows.

| Category | Rows | Positive | Negative | Signed | Identifiable | Unattributed | ID rows | Unattr. rows |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Bad debt | 6 | 11,062.06 | -158,676.14 | -147,614.08 | 0 | -147,614.08 | 0 | 6 |
| Commissions | 16 | 0 | -7,933.43 | -7,933.43 | -7,933.43 | 0 | 16 | 0 |
| Discounts | 173 | 397.89 | -13,277.52 | -12,879.63 | -12,785.34 | -94.29 | 170 | 3 |
| Embedded manual adjustments | 596 | 5,624.00 | -1,168.70 | 4,455.30 | 4,090.87 | 364.43 | 556 | 40 |
| Fees | 136 | 20,987.041 | -277,989.79 | -257,002.749 | 330.001 | -257,332.75 | 37 | 99 |
| Gift vouchers | 79 | 1,839.50 | -69.56 | 1,769.94 | 0 | 1,769.94 | 0 | 79 |
| Merchandise returns / cancellations | 17,973 | 0 | -719,677.94 | -719,677.94 | -713,031.25 | -6,646.69 | 17,641 | 332 |
| Other manual adjustment codes | 70 | 9,628.98 | -2,062.69 | 7,566.29 | 2,769.17 | 4,797.12 | 64 | 6 |
| Other positive merchandise activity | 226,881 | 2,575,930.13 | 0 | 2,575,930.13 | 0 | 2,575,930.13 | 0 | 226,881 |
| Qualifying gross merchandise purchases | 788,127 | 17,123,740.997 | 0 | 17,123,740.997 | 17,123,740.997 | 0 | 788,127 | 0 |
| Samples | 102 | 136.85 | -6,137.70 | -6,000.85 | 0 | -6,000.85 | 0 | 102 |
| Shipping / delivery income | 3,851 | 450,162.53 | -15,567.02 | 434,595.51 | 135,700.87 | 298,894.64 | 2,333 | 1,518 |
| Standalone manual billing | 330 | 334,379.51 | 0 | 334,379.51 | 146,916.08 | 187,463.43 | 197 | 133 |
| Standalone manual credits | 470 | 0 | -421,770.38 | -421,770.38 | -336,332.43 | -85,437.95 | 336 | 134 |
| Test entries | 14 | 226.00 | -22.50 | 203.50 | 203.50 | 0 | 14 | 0 |
| Zero-value entries | 6,024 | 0 | 0 | 0 | 0 | 0 | 70 | 5,954 |
| **Total** | **1,044,848** | **20,534,115.488** | **-1,624,353.37** | **18,909,762.118** | **16,343,669.038** | **2,566,093.08** |  |  |

The occasion reference remains 788,127 eligible lines, 36,594 occasions, 5,852 customers, and GBP 17,123,740.997 qualifying gross. The revenue bridge is an observed signed line-value reconciliation, not a complete profit-and-loss statement.

## Adversarial coverage

The revised tests:

- Forge a validated wrapper after changing every fee to discount and moving 100 unattributed merchandise rows to shipping, while recomputing the private frame digest and using the module token. Production validation must reject it using the actual-frame Stage A fingerprint.
- Change category amounts in opposite directions while preserving the two-category and grand total; frozen per-category checks reject it.
- Move an amount and row count between other positive merchandise and shipping; frozen category references reject it.
- Change a leaf's source-row membership fingerprint; the leaf reference rejects it.
- Retain existing synthetic checks for duplicate/substituted source identities, customer changes, date, country, description, category mutation, and input order invariance.

`build_revenue_bridge()` is the supported injected production bridge API and validates the wrapper before processing. `build_real_data_bridge()` obtains its input through the approved loader and delegates to that same production gate. Occasion/report production APIs share `_validate_purchase_input`, so a forged object is rejected before either output as well.

## Verification record

The full recovery suite passed **50 tests in 214.786 seconds**. This includes the forged-wrapper test and category-sensitive bridge-reference tests. The Stage B1 occasion references reproduced at **788,127 eligible lines, 36,594 occasions, 5,852 customers, GBP 17,123,740.997**. The bridge reconciled **1,044,848 rows** to signed GBP **18,909,762.118**, identifiable GBP **16,343,669.038**, and unattributed GBP **2,566,093.08**.

Two production passes used one unchanged, loader-validated corrected-V2 object. The serialized JSON files were written outside the repository under `/tmp/commercial_ds003_b2b1_outputs/` and compared by SHA-256:

| Producer output | Run 1 SHA-256 | Run 2 SHA-256 | Result |
|---|---|---|---|
| Purchase occasions | `402090a0eea8abd02d4d72b5c12301fa51334c925f19840c9a639282d61e2109` | same | byte-identical |
| Revenue bridge | `0cc8d5f1af9ccc88b11888e018102a2377c0a2c87db98762a3abe820202e781d` | same | byte-identical |

The occasion hash is unchanged from Stage B2A. The bridge output hash intentionally changed from the prior `016cf7a18dbea9c8018ddd4c85e2b2b5ce4a049580decf533d198fbad8d1fa1a`, because bridge leaves now include sign-row counts and frozen source-row membership fingerprints.

Commands executed:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s docs/recovery -p 'test_COMMERCIAL_DS_*.py' -v
cat > /tmp/run_b2b1_producers.py <<'PY'
import hashlib, json, sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / "docs/recovery"))
from COMMERCIAL_DS_003_PURCHASE_OCCASIONS import load_validated_purchase_input, build_real_data_report
from COMMERCIAL_DS_003_REVENUE_BRIDGE import build_revenue_bridge
out = Path('/tmp/commercial_ds003_b2b1_outputs')
out.mkdir(exist_ok=True)
validated = load_validated_purchase_input()
for run in (1, 2):
    occasion = build_real_data_report(validated)
    bridge = build_revenue_bridge(validated)
    for name, payload in (("occasions", occasion), ("bridge", bridge)):
        data = (json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2,
                           separators=(",", ": ")) + "\n").encode()
        (out / f"{name}_{run}.json").write_bytes(data)
        print(name, run, len(data), hashlib.sha256(data).hexdigest(), flush=True)
PY
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python /tmp/run_b2b1_producers.py
shasum -a 256 /tmp/commercial_ds003_b2b1_outputs/occasions_1.json /tmp/commercial_ds003_b2b1_outputs/occasions_2.json /tmp/commercial_ds003_b2b1_outputs/bridge_1.json /tmp/commercial_ds003_b2b1_outputs/bridge_2.json
shasum -a 256 data/raw/Online\ Retail.xlsx data/raw/online_retail_II.csv docs/recovery/COMMERCIAL_DS_002A_STOCK_CODE_INVENTORY.csv docs/recovery/COMMERCIAL_DS_002B_TAXONOMY_SEED.csv docs/recovery/COMMERCIAL_DS_003_STAGE_A_REFERENCE_PINS.json docs/recovery/COMMERCIAL_DS_003_STAGE_B2A_REFERENCE_PINS.json docs/recovery/COMMERCIAL_DS_003_STAGE_B2A_BRIDGE_REFERENCE_PINS.json
```

Verified source and foundation hashes:

| Artifact | SHA-256 |
|---|---|
| Raw V1 | `43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d` |
| Raw V2 | `32569a66f3842a82b0d8c4d63b263c5d98a76bde5d1f65c6c01bf457e541d3a9` |
| Stock-code inventory | `0d507be1e2b062705ba9763507342db71a24663b0d76176b31a2b39e4f66175b` |
| Authoritative taxonomy seed | `7b4611c78ca22d108c2616076c84b7c1db2efb8453ee9a32faceb027bb181e4e` |
| Stage A pins | `a96d2e9d5787dc1edd0e5c493e072ede4c342e845921e3242e90742625c8ba49` |
| B2A occasion pins | `4cf7b761a1b02cea853dbe577af7dddf8070fe65d0dcdfc7a71e2a064986f433` |
| New B2A bridge pins | `765ff7a29530b4221ec3ab171fc2ed861fcb9247901ba84419d2ecf7e786e96d` |

The Stage A classification/source row fingerprint remains `d76696efc5d02069d1180c84286e813973f810ca8fbf2b356ebc03f45bca1a04`; source-content fingerprint remains `59970949b45bf75263217525fa9f437c672d39503c7b2c605275601546299c6d`; customer fingerprint remains `248f421fbcacfaf1e63b3a5a69da78ec3097ce0cfa73c50f1e6ed733e4736d51`. The seed and Stage A/B2A pins are unchanged. `git diff --check` is clean. The repository already had `.vscode/`, `PROJECT_TECHNICAL_HANDOVER.md`, and `docs/recovery/` as untracked content; these files were preserved. No commit or push was made.

## Remaining conditions

No B2B analysis has started. Claude should focus re-review on the actual-frame fingerprint reconstruction, the immutable pin comparison, the 16 bridge leaf memberships and totals, and the forged-wrapper adversarial tests. The source parser remains dependent on the pinned pandas/CSV behavior documented by Stage A; this correction does not change that limitation.
