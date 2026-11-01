# COMMERCIAL-DS-002A-R — Independent Evidence and Taxonomy Review

**Reviewer:** Claude Code (independent of the implementation agent)<br>
**Review date:** 2026-10-31<br>
**Subject:** COMMERCIAL-DS-002A: [taxonomy inventory](COMMERCIAL_DS_002A_TAXONOMY_INVENTORY.md), [stock-code CSV](COMMERCIAL_DS_002A_STOCK_CODE_INVENTORY.csv), [evidence addendum](COMMERCIAL_DS_002A_EVIDENCE_ADDENDUM.md), [supersession note](COMMERCIAL_DS_002A_SUPERSESSION.md), [handover](COMMERCIAL_DS_002A_REVIEW_HANDOVER.md) and the hardened [evidence script](COMMERCIAL_DS_002_ANALYSIS.py), reviewed against the [DS-002 independent review](COMMERCIAL_DS_002_INDEPENDENT_REVIEW.md).<br>
**Status:** Review only. No production code, contract, raw data, existing script, report or decision record was modified. Nothing was committed or pushed.

---

## 1. Overall verdict: **PASS WITH CONDITIONS**

| Area | Verdict | Summary |
| --- | --- | --- |
| Numerical evidence | **PASS** | Every requested figure reproduces exactly. Checks used my own CSV/openpyxl parse with Decimal arithmetic, which shares no code with the script. The inventory CSV matches field by field across all 5,132 codes and both sources. |
| Fail-closed controls | **PASS WITH CONDITIONS** | SHA, block structure, overlap size, overlap multiset equality and the financial bridge all fail closed under perturbation. There are four gaps (§4): sentinel collisions, no customer-attribution invariant, pins that encode the *superseded* DS-002 code list, and no inventory-to-bridge reconciliation. |
| Taxonomy policy design (seed → `unclassified`) | **PASS WITH CONDITIONS** | The precedence and the fail-closed default are sound. Two conditions: the evidence classifier's heuristics must never enter production, and a row-context rule should replace both the 299-code description-exception review and most of the 351-code owner burden (§5, §7). |
| Evidence classifier (`classify_code`) as a production rule | **FAIL** | New codes that carry a description become `merchandise`, including `TEST003 "This is a test product."`, `POST2 "POSTAGE"` and numeric `"Next Day Carriage"`. `AMAZON FEE` becomes `inventory_adjustment`. Acceptable only as a discovery aid, which is how Codex labels it. |
| Ready for owner decisions | **Yes** | Recast as **nine transaction-type policy groups** (§7), not code-by-code approval. |

Five of my findings change what the owner is asked:

1. **The 351 unresolved codes have no commercial or customer impact.** All 357 corrected-V2 rows have zero price, no customer ID and no description. They are unattributed stock movements, with zero revenue and zero customers affected.
2. **The description exceptions on the 299 mixed codes have no revenue impact.** All 366 administrative-description rows on those codes are also zero-price and unattributed. A description-exception seed is not needed for any R1–R6 revenue or customer metric.
3. **About half of "refund/cancellation revenue" is not customer returns.** Of GBP −1,465,303.66, merchandise returns are GBP −719,677.94. The rest is:
   - manual adjustments: GBP −424,628.20;
   - Amazon and bank fees: GBP −277,989.79;
   - shipping: GBP −15,567.02;
   - discounts: GBP −13,277.52;
   - commission: GBP −7,933.43;
   - samples: GBP −6,137.70;
   - tests and vouchers: GBP −92.06.
4. **Non-merchandise-only invoices create purchase occasions under current logic.** 375 valid invoices have no merchandise line, and 26 customers exist only through such invoices.
5. **The same-day sensitivity in the addendum understates the occasion rate.** The correct later-calendar-day rate for the 12-month proxy at 90 days is **40.45%** (411 / 1,016), not 39.47%.

---

## 2. Independently reproduced results

### 2.1 Method

I re-used the DS-002 review's independent caches:

- V2 parsed with the stdlib `csv` module;
- V1 parsed with `openpyxl`;
- prices held as `Decimal` from source strings;
- multisets compared with Python `Counter`.

New verification scripts were written for this review. Codex's hardened script was run unchanged and exited 0 in 63 s. Projecting its JSON `stock_code_inventory` through `csv.DictWriter` reproduces the committed CSV **byte for byte**. File hashes match the handover: script `f4eb7940…b01f`, CSV `0d507be1…175b`, sources V1 `43465a06…676d` and V2 `32569a66…d3a9`.

### 2.2 Results

| Item | Codex | Independent | Verdict |
| --- | --- | --- | --- |
| Normalised stock-code union | 5,132 (V1 3,958; corrected V2 5,132) | 5,132 / 3,958 / 5,132; code sets identical | **PASS** |
| Inventory field accuracy | — | **0 mismatches** across row counts, +/−/0 value counts, identifiable positive revenue, negative revenue and the full description strings, for both sources | **PASS** |
| Inventory reconciliation | Rows 541,909 / 1,044,848 | Same. Identifiable positive revenue sums to V1 GBP 8,911,407.904 and corrected V2 GBP 17,431,551.178, which equals identifiable gross current exactly. Negative revenue sums to GBP −1,624,353.37 = refunds GBP −1,465,303.66 + bad-debt negative-price lines GBP −158,676.14 − GBP 373.57. The GBP 373.57 is positive-value lines that sit inside the refund mask and are netted into `refund_cancel_revenue_all`; see §3.4 | **PASS** |
| Category counts | 4,452 merch / 299 mixed / 351 unclassified / 30 other | Identical (13 categories) | **PASS** |
| 299 mixed-description codes | 299 | 299, all numeric codes, 110,567 corrected-V2 rows | **PASS** (design concern §5.3) |
| 351 unresolved codes / 357 rows | 351 / 357 | 351 / 357 corrected V2 (7 in V1) | **PASS** |
| V2 overlap correction | Reset 525,461; 22,523 × 2 exact; 1,044,848 | Same | **PASS** |
| Extra GBP 18 `POST` row | 581587 / POST / 2011-12-09 12:50 / 12680 / France | Same; it is the only element of `Counter(block2) − Counter(V1)` | **PASS** |
| Decimal bridge | 20,533,741.918 / −1,465,303.66 / 19,068,438.258 / 17,431,551.178 / 302,114.628 / 17,129,436.550 / −714,532.55 / 16,414,904.000 | Identical | **PASS** |
| Three-decimal prices | 18 rows; max 3 dp | 18 rows; max 3 dp | **PASS** |
| Acquisition-proxy contamination | 1,381/42, 1,031/88, 727/99, 1,872/260, 1,514/175 | Identical (3.04 / 8.54 / 13.62 / 13.89 / 11.56%) | **PASS** |
| Return by recency | 21,027 / 9,880 / 6,951 / 5,043 / 2,398 / 2,006 anchors; 54.08 → 6.43% | Identical counts, returners and rates | **PASS** |
| Ten complete and mature R3 anchors | 2010-12-01 … 2011-09-01 | Same ten anchors | **PASS** |
| Date-level maturity | 12m: 60d 1,258 / 441; 90d 1,016 / 430; 180d 713 / 371 | Same | **PASS** |
| Same-day repeat sensitivity | 12m 1,016 / 430 / 29 → 39.47%; 3m 3,556 / 1,476 / 154 → 37.18% | Inputs reproduce. The **correct later-day occasion rate is 40.45% (12m) and 38.98% (3m)**: subtraction drops 10 customers (12m) whose same-day split is followed by a genuine later purchase | **PASS with correction** |
| Returns-only / negative-net | 33 customers GBP −1,643.28; 37 negative-net; GBP −39,466.28 in first 3 months | Identical | **PASS** |
| Population bridge (DS-002 list) | 5,878 / 36,969 → 5,861 / 36,639 | Identical | **PASS** |
| Supersession note | No historical file changed | DS-001 and DS-002 file modification times all predate DS-002A (latest 2026-10-30 19:00). The supersession file only references, it does not edit. Cross-references checked against DS-001 R-18, the agent handover, P-01, `C-ACQ`, `transaction_lines`, the evaluation protocol and the research programme | **PASS** |

### 2.3 Bridge under the revised taxonomy (new; not in the addendum)

The addendum's bridge pins the **DS-002** code list. Applying the DS-002A proposed categories, with merchandise plus mixed counted as product:

| Measure | DS-002 list | DS-002A proposal | Change |
| --- | ---: | ---: | ---: |
| Identifiable gross product revenue | GBP 17,129,436.550 | **GBP 17,123,740.997** | −5,695.553 (`ADJUST*`, `TEST*` and `23444` removed; `PADS` +0.017 added) |
| Identified product returns | GBP −714,532.55 | **GBP −713,031.25** | +1,501.30 |
| Product customers / orders | 5,861 / 36,639 | **5,852 / 36,594** | −9 / −45 |

These figures must replace the DS-002 pins once the taxonomy is approved (§9, C-7).

---

## 3. Taxonomy and rule-design findings

### 3.1 Requested codes

| Code | Evidence (corrected V2) | Category assessment | Treatment issue |
| --- | --- | --- | --- |
| `23444` | 81 rows: 80 "Next Day Carriage", 1 null-description zero-value row. 79 valid lines (GBP 1,200, ~GBP 15 each). 79 of 81 invoices also contain merchandise | **Shipping, high confidence.** A whole-code mapping is safe because the only non-carriage row is zero-value. Proves numeric codes are not automatically merchandise. | Same as `POST` |
| `ADJUST` / `ADJUST2` | 70 rows; every invoice is standalone, with no merchandise; descriptions name staff and dates. `ADJUST` has 32 valid lines (GBP 3,538.52) and 31 cancellations | **Manual adjustment, high confidence** | Currently creates standalone "orders" for customers. It must not create purchase occasions. |
| `TEST001` / `TEST002` | 17 rows; standalone invoices; "This is a test product."; 10 valid lines (GBP 226) on 5 real customer IDs (12346, 14103, 14827, 16446, 16454), who also have 32 merchandise rows | **Test, high confidence** | Exclude the lines from **all** revenue, including commercial. Exclude lines, not customer accounts, unless the owner decides otherwise. |
| `M` | 1,403 rows, all "Manual". 691 valid lines worth GBP 152,166.32 across 438 customers. **196 lines on standalone `M`-only invoices carry GBP 146,663.08 (96%)**; 113 lines priced above GBP 100 carry GBP 142,647.42. 554 of 1,290 invoices also contain merchandise. Negatives GBP −422,939.08 | **Two populations under one code:** manual billing or adjustment invoices, and small manually priced lines inside merchandise invoices | Code-level mapping cannot separate them. Invoice context is required (§3.3). Genuine owner policy. |
| `D` | 173 rows; 168 cancellations; GBP −13,277.52; 5 positive lines GBP 397.89 | **Discount, high confidence** | Commercial net reduction; not behavioural |
| `CRUK` | 16 cancellation rows, all standalone, GBP −7,933.43 commission, identified customers | **Fee / commission, high confidence** | It is a cost, but it currently sits inside "refund/cancellation revenue" |
| `PADS` | 19 rows at GBP 0.001, always in merchandise invoices; GBP 0.017 | Merchandise accessory (Codex) is defensible; **immaterial** | Never creates a standalone valid order. Either choice is safe. |
| `B` | 6 unattributed rows: 5 with negative price (GBP −158,676.14, outside the current bridge) and **1 positive line of GBP 11,062.06 inside `gross_positive_revenue_all`** | **Bad debt, high confidence** | Current gross "sales" includes a bad-debt reversal. Must be a separate bridge line. |
| `S` | 102 unattributed rows; 99 cancellations GBP −6,137.70; 3 positive GBP 136.85 | **Sample credits, high confidence** | Non-sales |
| `AMAZONFEE`, `BANK CHARGES` | GBP −277,989.79 negative, almost all unattributed cancellations; GBP 20,987.04 positive | **Fee, high confidence** | GBP 278k of fees is labelled as refunds, and GBP 21k sits in gross positive revenue |
| Gift vouchers (`GIFT_0001_*`, `22016`) | 103 rows, all unattributed; GBP 1,839.50 gross positive; 0 customer-level exposure | **Gift voucher, high confidence** | Commercially a liability (stored value), not merchandise sales. No behavioural use. |
| `DCGS*` | 157 rows, all unattributed; GBP 1,154.72 gross positive | Merchandise from a marketplace channel (descriptions); **medium** | No customer exposure; R1 channel caveat only |
| `C3`, `GIFT` | 1 zero-value, null-description, unattributed row each | Covered by the row-context rule (§5.1) | — |

### 3.2 Is code-level classification sufficient?

**For every revenue-bearing row except `M`, yes.**

- All non-merchandise codes carrying valid revenue (`23444`, `ADJUST*`, `TEST*`, `POST`, `DOT`, `C2`, fees, `D`) have a single meaning across their revenue-bearing rows.
- Within the 4,751 merchandise and mixed codes, every administrative-looking description is on a non-valid row. The 1,645 valid rows on "plain merchandise" codes with non-uppercase descriptions carry ordinary product names, such as "BAG 250g SWIRLY MARBLES" (GBP 28,212.11). One exception, code `23702` "High Resolution Image" (3 valid rows), is a description glitch on a priced product line, so merchandise is correct.

### 3.3 Where invoice or transaction context is necessary

1. **Zero-value unattributed rows** (§5.1): classify by row context, not by code.
2. **`M` (Manual):** standalone `M`-only invoices versus `M` lines inside merchandise invoices.
3. **Purchase occasions:** an invoice creates a customer purchase occasion only if it contains at least one valid **merchandise** line. Under current logic, 375 valid invoices have no merchandise: 213 manual, 116 shipping-only, 30 fee, 10 test, 5 discount and 1 mixed. 26 customers exist only through such invoices. This is a contract rule, not a code mapping.

### 3.4 Determinism and precedence

The proposed production precedence is deterministic, provided the seed is complete and keys are unique: exact (code, description) exception → explicit code map → `unclassified` (fail). Three issues remain:

- **Normalisation mismatch.** The policy says "trim and uppercase", but the inventory key is uppercase only. Code `'47503J '` (trailing space, 1 row) is keyed separately from `'47503J'` (78 rows). After trimming they collide. The seed must be keyed on the same normalisation that production applies.
- **Description keys need normalisation too.** 42 (code, description) pairs collapse under trim and case-folding (e.g. `" Bank Charges"` / `"Bank Charges"`). An exact-string exception seed would be fragile.
- **Case variants.** 173 codes have lower-case variants, e.g. `15056bl` / `15056BL`. Merging them by upper-casing is consistent with the descriptions observed, but should be stated in the contract.

The GBP 373.57 difference between the inventory's negative-revenue column and the bridge (§2.2 table) comes from positive-value lines inside the refund/cancellation mask, which the bridge nets in. The inventory's negative-only column excludes them. It does not affect the bridge totals, but the contract-encoding reconciliation should itemise it.

### 3.5 Can legitimate merchandise be misclassified?

- **By the proposed seed: no material risk identified.** No revenue-bearing merchandise row maps to a non-merchandise category. The `CARRIAGE` lanterns and clocks (`23099`, `85168A/B`, `21347`) stay merchandise because shipping is assigned by code, not by description.
- **By description rules: yes.** A description regex for shipping would misclassify "FRENCH CARRIAGE LANTERN" and "BAROQUE CARRIAGE CLOCK". The administrative regex matches `"AMAZON"`, `"DOTCOM SETS"`, `"FOUND"` and `"MISSING"` as admin text (6 upper-case descriptions). It also misses "check", "?", "damaged", "thrown away", "smashed", "given away" and "Unsaleable, destroyed." on 2,660 rows of plain-merchandise codes. Every affected row is non-revenue-bearing, so the regex currently harms nothing, but it is unreliable in both directions and must stay out of production.

---

## 4. Fail-closed test results

All tests ran against an isolated copy of the script (`ROOT` repointed, otherwise unmodified), with perturbations made to in-memory DataFrames only. The real datasets and the original script were not touched; their hashes are unchanged.

| Test | Perturbation | Result |
| --- | --- | --- |
| T1a / T1b | Wrong expected V2 / V1 SHA | **Failed closed** before parsing ("V2 SHA-256 mismatch" / "V1 …") |
| T2 | `EXPECTED_OVERLAP_ROWS` 22,522; `EXPECTED_RESET_INDEX` 525,460; `EXPECTED_CORRECTED_ROWS` 1,044,849 | **All failed closed** |
| T3a | V1 overlap price +0.01 | **Failed closed** (multiset) |
| T3b | Trailing space on one block-1 description | **Failed closed** |
| T3c | Block-1 multiplicity swap with row count preserved | **Failed closed** |
| T3d | Block-1 price +1×10⁻⁹ | **Failed closed** (exact float comparison) |
| T3e | Block-1 NaN `CustomerID` replaced by −1.0 | **DID NOT FAIL**: sentinel collision (`fillna(-1.0)`) |
| T3f | Block-1 NaN `Description` replaced by literal `"<NA>"` | **DID NOT FAIL**: sentinel collision (`fillna("<NA>")`) |
| T3g | Block-2 non-overlap quantity +1 | **Failed closed** ("Second block must differ from V1 by one row") |
| T4a | Pre-V1 block-1 price +0.001 | Block evidence passes (no external oracle exists for 2009-12…2010-11), as expected; the SHA would catch it on real files |
| T4b | Same perturbation into the financial bridge | **Failed closed** (`gross_positive_revenue_all`) |
| T4c | Merchandise line relabelled `POST` | **Failed closed** (`identifiable_non_product_revenue`) |
| T4f | One valid line dropped | **Failed closed** (financial) |
| T4g | One non-repeat line dropped → repeat diagnostics | Not detected, which is correct: it only pins repeat counts |
| T4d | One valid line moved to a new customer ID | **Financial bridge DID NOT FAIL.** The population invariant did fail (customer count +1) |
| T4h | One invoice reassigned between two existing customers | **DID NOT FAIL** in any stage: financial, population, history, pseudo-boundary, active-window/recency |
| T5 | `classify_code` probes | `UNSEEN_FIXTURE` with no description → `unclassified` ✔. With a description, every unseen code → `merchandise`: `NEWCODE1`, `TEST003 "This is a test product."`, `POST2 "POSTAGE"`, `99999 "Next Day Carriage"`, `"check"`, `"?"`, `"thrown away"`. `FEE01 "AMAZON FEE"` → `inventory_adjustment`. |

Two of my first-pass probes (T4a, T4d) were built incorrectly and were rerun. The table reports the corrected runs.

**Missing, ineffective or misleading assertions:**

1. **Misleading fixture (medium).** `require(classify_code("UNSEEN_FIXTURE", []) == "unclassified")` only tests the description-less case. The function is fail-open for any unseen code that has a description, which is the realistic case. The fixture proves less than "Unknown code must fail closed" claims.
2. **No customer-attribution invariant (medium).** No assertion detects revenue moving between customers (T4h). Contract tests need a per-customer checksum, e.g. a hash of sorted `(customer_id, gross_product, orders)`.
3. **Pins encode the superseded taxonomy (medium).** The bridge, population and same-day invariants are pinned to the DS-002 list (`PADS` excluded; `ADJUST*`, `TEST*`, `23444` included). They are correct as regression pins for the reviewed baseline, but they must not be carried into the contract as-is (§2.3).
4. **No inventory-to-bridge reconciliation (low).** The script does not assert that inventory rows sum to 541,909 / 1,044,848, or that identifiable positive revenue sums to the bridge. These were checked outside the script (handover), and I reproduced them independently.
5. **Sentinel collisions (low, theoretical).** The −1.0 and `"<NA>"` sentinels cannot collide on the real sources, since IDs are positive and no description equals `"<NA>"`. Contract code should compare nulls with explicit `(is_null, value)` pairs.
6. **Circularity of pins (informational).** Several expected values are the DS-002 reviewer's own numbers. A passing pin shows agreement with that review, not independent correctness. Independence comes from this review's separate computation, which matches.
7. **Partial recency pin (low).** The return-by-recency assertion pins customer-anchor counts but not returner counts or rates. I reproduced both independently.

---

## 5. Proposed classification-policy groups

### 5.1 Strategy for the 351 unresolved codes

| Group | Codes / rows (corrected V2) | Revenue / customer exposure | Evidence | Proposed resolution |
| --- | --- | --- | --- | --- |
| **U1: Zero-value unattributed stock movements** (high confidence, by transaction context) | **All 351 codes / 357 rows** (7 rows in V1). 301 negative-quantity, 56 positive, 0 cancellations | **GBP 0; 0 customers; 0 orders** | Every row has price 0, null customer and null description. 345 codes appear once and 6 appear twice. 82 share a 5-digit stem with a known merchandise code (variant suffixes); the rest are numeric-shaped (`99999`, `99999A`) plus a few `DCGS` codes and `C3` / `GIFT` | Adopt a **row-level rule**: `price = 0 ∧ customer_id IS NULL ∧ description IS NULL` → `line_type = non_commercial_stock_movement`, excluded from every revenue and customer measure and kept for audit. The **codes stay unmapped**: any future row on these codes that carries value or a customer falls through to `unclassified` and fails. |
| U2: Ambiguous, needing investigation | None among the 351 once U1 is applied | — | — | — |
| U3: Owner policy | None among the 351 | — | — | — |

With U1, the owner does not need to classify any of the 351 codes. Only one row-context rule needs approval.

### 5.2 The 299 mixed-description codes

Whole-code exclusion would remove 110,567 rows and GBP 2,657,930.53 of identifiable revenue, so it is clearly unsafe, as Codex concluded. On those codes, all 366 administrative-description rows have price 0 and no customer: **GBP 0 exposure**. The U1-style context rule, broadened to `price = 0 ∧ customer_id IS NULL`, covers them without a description-exception seed.

**Recommendation:** drop the 299-code description-exception review from the owner gate. Map these codes as merchandise at code level. Keep a description-exception seed only if a future stock or inventory study needs it, which is outside R1–R6.

### 5.3 Revenue-bearing taxonomy: confidence groups

| Tier | Members | Exposure (corrected V2) |
| --- | --- | --- |
| **A. High confidence: steward sign-off, no policy needed** | Merchandise (4,452 + 299 codes) as the code-level seed. Shipping (`POST`, `DOT`, `C2`, `23444`). Test (`TEST001/002`). Manual adjustment (`ADJUST`, `ADJUST2`). Fee (`AMAZONFEE`, `BANK CHARGES`). Commission (`CRUK`). Bad debt (`B`). Sample (`S`). Discount (`D`). Gift voucher (`GIFT_0001_*`, `22016`). Stock movement (U1 rule). | All identifiable revenue except `M` |
| **B. Ambiguous: needs investigation** | `M` split by invoice context (standalone vs embedded). `PADS` (immaterial). `DCGS*` channel meaning (unattributed only). `23702` "High Resolution Image" (merchandise). `47503J` normalisation. | `M` GBP 152,166.32 identifiable positive (GBP 146,663.08 standalone); others under GBP 1.2k |
| **C. Owner policy** | **Treatment**, not category, of each transaction type (§7) | See §6 |

---

## 6. Downstream consequences: commercial vs behavioural representation

| Transaction type | R1 commercial bridge | R2–R4 behavioural product revenue | Creates purchase occasion? | Counts as a customer "return"? |
| --- | --- | --- | --- | --- |
| Merchandise | Gross sales | **Yes** | Yes | Merchandise returns only |
| Shipping / carriage | Separate "delivery income" line | No | **No** (116 shipping-only invoices) | No; separate line |
| Discount (`D`) | Net-sales deduction | No (net-value sensitivity only) | No | No |
| Manual adjustment (`ADJUST*`, embedded `M`) | Separate adjustments line | No | No | No |
| Standalone `M` invoices | **Owner policy:** separate "manual billing" line in all cases | **Owner policy:** excluded (recommended), with sensitivity | **Owner policy** (recommend no) | No |
| Fees (`AMAZONFEE`, `BANK CHARGES`), commission (`CRUK`) | **Below net sales as channel/finance costs**, not refunds | No | No | **No** (GBP −285,923.22 currently inside "refunds") |
| Bad debt (`B`) | Separate write-off line; remove the GBP 11,062.06 positive line from gross sales | No | No | No |
| Samples (`S`) | Separate line | No | No | No |
| Gift vouchers | Stored-value / liability line, not sales | No | No | No |
| Test | **Excluded from all reporting** | No | No | No |
| Zero-value stock movement | Excluded (audit only) | No | No | No |

**Workstream compatibility:**

- **R1 (revenue reconciliation): compatible only once the bridge is decomposed by category.** `refund_cancel_revenue_all` and `net_transactional_revenue_all` currently mix returns, fees, manual adjustments and discounts, and gross positive revenue includes fees and a bad-debt line. All-customer product revenue needs the same taxonomy. Gross positive revenue for anonymous customers includes GBP 2.58m of merchandise and GBP 0.30m of shipping.
- **R2 (RFM): compatible.** Needs the occasion rule (merchandise-bearing invoices on a later calendar day) and gross merchandise revenue. Excluding the 375 non-merchandise invoices changes frequency for affected customers and removes 26 customers.
- **R3 (lapse): compatible.** The label must use the same occasion definition. A shipping-only or manual-only invoice in `[T, T+90d)` must not count as a return. Ten complete, mature anchors confirmed.
- **R4 (value and forecasting): compatible.** Customer value uses gross merchandise revenue, with net merchandise as a sensitivity (returns-only and negative-net treatment still open). Aggregate forecasting should use merchandise sales plus a separately modelled or excluded delivery income, never a series mixing fees and adjustments.
- **R5 (experiments): compatible.** Eligibility and conversion use merchandise occasions on later calendar days. The correct 12-month 90-day baseline rate is 40.45%, not 39.47% or 42.32%.
- **R6 (parity): compatible if** one versioned seed (codes + row-context rules) is consumed by every engine; the normalisation key is identical (trim + upper); Spark/dbt do not re-implement the evidence heuristics; and the U1 rule is expressed on raw fields with explicit null handling.

---

## 7. Remaining owner decisions (grouped by transaction type)

| # | Decision | Recommendation |
| --- | --- | --- |
| **O-1** | Approve the precedence (row-context rules → explicit code seed → `unclassified` = fail) and the normalisation key (trim + uppercase) | Approve |
| **O-2** | Approve the U1 row-context rule for zero-value unattributed rows (resolves all 351 codes / 357 rows and the 366 admin rows) | Approve |
| **O-3** | Shipping and carriage: separate commercial line; excluded from behaviour; no purchase occasion | Approve |
| **O-4** | Manual adjustments (`ADJUST*`, embedded `M`): separate line; excluded from behaviour | Approve |
| **O-5** | Standalone `M` invoices (GBP 146,663.08 identifiable): commercial line "manual billing"; exclude from behaviour and occasions; report an inclusion sensitivity | **Genuine policy choice.** Recommendation as stated. |
| **O-6** | Fees and commission: move out of refunds into below-net-sales costs | Approve |
| **O-7** | Bad debt, samples and gift vouchers: separate non-sales lines | Approve |
| **O-8** | Tests: exclude lines from all reporting (not the customer accounts) | Approve |
| **O-9** | D-002-10 occasion rule: an order creates a purchase occasion only if it has ≥1 valid merchandise line, and a second purchase is the first such order on a **later calendar day** | Approve; invoice-level as sensitivity |

`PADS` (immaterial; accept merchandise) and `DCGS*` (merchandise, unattributed only) can be steward decisions. The open DS-002 decisions (D-002-01 … D-002-11) remain as previously reviewed. The supersession note is accurate and can be adopted when they are recorded.

---

## 8. Blocking and non-blocking defects

| ID | Severity | Defect | Blocks owner decisions | Blocks contract encoding |
| --- | --- | --- | --- | --- |
| A-01 | **High** | Evidence classifier is fail-open for unseen codes with descriptions and misroutes `AMAZON FEE` (T5) | No (it is labelled a discovery aid) | **Yes**: production must use a fully enumerated seed only |
| A-02 | **High** | Refund/cancellation and gross bridges mix fees, adjustments, discounts and a bad-debt line (§3.1, §6) | No | **Yes**, for R1 bridge fields |
| A-03 | **High** | Non-merchandise-only invoices create purchase occasions (375 invoices, 26 customers) | No (O-9) | **Yes** |
| A-04 | Medium | 351-code / 357-row gate framed as owner work; U1 context rule not proposed | No | Yes, until O-2 is decided |
| A-05 | Medium | `M` is two populations; code-level mapping cannot separate them | Requires O-5 | Yes |
| A-06 | Medium | Same-day sensitivity understates the occasion rate (39.47% vs correct 40.45%) | No | No (corrected definition in O-9) |
| A-07 | Medium | No customer-attribution invariant (T4h) | No | **Yes**: contract tests must include it |
| A-08 | Medium | Invariants pinned to the superseded DS-002 code list | No | **Yes**: re-pin to the approved taxonomy (§2.3) |
| A-09 | Medium | Misleading unseen-code fixture | No | Yes: replace with description-bearing fixtures |
| A-10 | Low | Normalisation key mismatch (`'47503J '`); 42 description pairs collapse | No | Yes (trivial) |
| A-11 | Low | Sentinel null collisions in tuple comparison | No | No (fix in contract code) |
| A-12 | Low | No in-script inventory-to-bridge reconciliation; partial recency pin | No | No |
| A-13 | Low | Admin regex over-inclusive (6 upper-case product-like strings) and under-inclusive (2,660 rows) | No | No, if excluded from production (A-01) |

---

## 9. Exact conditions for contract encoding

`contracts/business_definitions.yml` may be authored only when **all** of the following hold:

| # | Condition |
| --- | --- |
| C-1 | Owner decisions O-1 … O-9 and the open DS-002 decisions (D-002-01 … D-002-11) are recorded in `COMMERCIAL_DS_001_DECISION_LOG.md`, with the DS-002A supersession note referenced. |
| C-2 | The taxonomy is encoded as **one versioned seed**: every observed normalised code (trim + upper) is explicitly listed with its category, plus the row-context rules (U1, standalone-`M`). No regex or prefix heuristics are in the production path. `unclassified` rows > 0 fails validation. |
| C-3 | Revenue fields are category-decomposed so that `returns` contains merchandise returns only. Fees, commission, discounts, manual adjustments, shipping, bad debt, samples, vouchers and tests each have their own field. |
| C-4 | A purchase occasion is a customer × invoice with ≥1 valid merchandise line. Second purchase uses the later-calendar-day rule (O-9), and invoice-level repeat is kept as a sensitivity field. |
| C-5 | Contract tests include: description-bearing unseen-code fixtures (must → `unclassified`); a numeric-code shipping fixture; a test-product fixture; the U1 rule including a value-bearing row on a U1 code (must fail); a standalone-`M` fixture; a per-customer attribution checksum; null-safe tuple comparison; and inventory-to-bridge reconciliation. |
| C-6 | Exact decimal with ≥3 fractional places; all money comparisons in Decimal. |
| C-7 | Regression pins are regenerated under the approved taxonomy and independently re-verified. Expected baseline if the DS-002A proposal is approved unchanged: identifiable gross product GBP 17,123,740.997; identified product returns GBP −713,031.25; 5,852 product customers; 36,594 orders. These shift again if O-5 or O-9 differ. |
| C-8 | Existing source-integrity, overlap and bridge assertions are carried forward unchanged in substance (they passed T1–T4). |

Phase 3 remains unauthorised until the encoded contract passes its own independent review.

---

## 10. Git working-tree status

`git status --short --branch` at review end:

```text
## main...origin/main [ahead 1]
?? .vscode/
?? PROJECT_TECHNICAL_HANDOVER.md
?? docs/recovery/
```

- `git diff --stat` is empty, so no tracked file changed.
- The only file created in the repository by this review is `docs/recovery/COMMERCIAL_DS_002A_INDEPENDENT_REVIEW.md`.
- The evidence script, inventory CSV and raw sources have the same SHA-256 as at handover.
- The fail-closed harness, the isolated script copy and all verification scripts are in the session scratchpad, outside the repository.
- No `__pycache__` was created under `docs/recovery/`.
- Nothing was committed or pushed.

---

**HANDOVER FOR CHATGPT — COMMERCIAL-DS-002A DECISION GATE**

**Evidence: PASS.** Every DS-002A figure reproduces independently:

- the 5,132-code inventory, matching field for field with zero mismatches and reconciling exactly to 1,044,848 rows and GBP 17,431,551.178;
- the 299 mixed codes and the 351 codes / 357 rows;
- the overlap correction and the GBP 18 `POST` row;
- the Decimal bridge;
- contamination lower bounds (3.04–13.62%);
- return by recency;
- the ten complete, mature R3 anchors;
- returns-only and negative-net diagnostics.

The fail-closed controls work for source integrity, overlap and the financial bridge. They do not cover customer attribution, and their pins encode the superseded DS-002 code list.

**Safe to approve now:**

- the taxonomy precedence (row-context rules → explicit seed → `unclassified` = fail) with trim + uppercase normalisation;
- the U1 rule for zero-value, unattributed, description-less rows, which resolves all 351 unresolved codes with GBP 0 and 0-customer exposure;
- category assignments for shipping (including numeric `23444`), tests, `ADJUST*`, fees, commission, bad debt, samples, discounts and gift vouchers;
- treating the 299 mixed codes as merchandise at code level (their admin rows carry GBP 0);
- O-3, O-4 and O-6 to O-9 as recommended.

**Unresolved:**

- **O-5: standalone `M` invoices.** GBP 146.7k of the GBP 152.2k identifiable `M` revenue; a genuine policy choice.
- **R1 bridge redesign.** About half of current "refund/cancellation revenue" is fees, adjustments and discounts, not returns.
- **Occasion rule.** 375 non-merchandise invoices currently create orders. The correct 12-month 90-day repeat baseline is 40.45%.
- **Net-value treatment for R4.**

**Smallest next Codex task (COMMERCIAL-DS-002B, documentation and evidence only), after the owner records O-1 … O-9 and D-002-01 … D-002-11:**

1. Produce the fully enumerated seed as a reviewable CSV (trim + upper keys, including the U1 and standalone-`M` row-context rules), with no heuristics.
2. Extend the evidence script with:
   - category-decomposed bridge fields;
   - the merchandise-occasion and later-day rules;
   - a per-customer attribution checksum;
   - description-bearing unseen-code fixtures;
   - null-safe comparison;
   - re-pinned invariants under the approved taxonomy.
3. Submit for a light independent re-review.

Codex must not author `contracts/business_definitions.yml`, change pipelines or begin Phase 3 until that re-review passes.
