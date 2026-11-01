# COMMERCIAL-DS-002B — Milestone 1 Independent Scientific and Engineering Review

**Reviewer:** Claude Code (independent of the implementation agent)<br>
**Review date:** 2026-10-31<br>
**Subject:** [`COMMERCIAL_DS_002B_TAXONOMY.py`](COMMERCIAL_DS_002B_TAXONOMY.py), [`COMMERCIAL_DS_002B_TAXONOMY_SEED.csv`](COMMERCIAL_DS_002B_TAXONOMY_SEED.csv), [`COMMERCIAL_DS_002B_INTEGRATION.py`](COMMERCIAL_DS_002B_INTEGRATION.py), [`test_COMMERCIAL_DS_002B_TAXONOMY.py`](test_COMMERCIAL_DS_002B_TAXONOMY.py), [`test_COMMERCIAL_DS_002B_INTEGRATION.py`](test_COMMERCIAL_DS_002B_INTEGRATION.py), [`COMMERCIAL_DS_002B_MILESTONE1_VERIFICATION.md`](COMMERCIAL_DS_002B_MILESTONE1_VERIFICATION.md). These were compared against the [decision log](COMMERCIAL_DS_001_DECISION_LOG.md), the [DS-002 review](COMMERCIAL_DS_002_INDEPENDENT_REVIEW.md), the [DS-002A review](COMMERCIAL_DS_002A_INDEPENDENT_REVIEW.md), the [002A inventory](COMMERCIAL_DS_002A_STOCK_CODE_INVENTORY.csv) and the [evidence script](COMMERCIAL_DS_002_ANALYSIS.py).<br>
**Status:** Review only. No Codex file, seed, raw source, pipeline or decision record was modified. Every adversarial test ran against isolated scratch copies. Nothing was committed or pushed.

---

## 1. Executive verdict: **CONDITIONAL PASS**

| Dimension | Verdict |
| --- | --- |
| **Implementation correctness of the classification run** | **Correct.** Every row count, category amount, context population, `M` split and output hash reproduces exactly from my independent code. The classifier fails closed on every unknown-code probe I constructed. |
| **Engineering safeguards (tests, pins, null handling)** | **Inadequate.** The test suite overwrites the seed it is meant to check. No assertion detects category corruption, row substitution or customer reassignment. The integration's null test diverges from the classifier's. |
| **Documentation accuracy** | **Defective.** The verification report's headline identifiable/unattributed split is wrong by **GBP 9,999.03**, and its coverage percentage is mistyped (92.06% vs the actual 93.06%). The decision log cites a contract specification that does not exist. |
| **Scientific validity** | **Conditional.** The category structure is sound. The implementation of O-5 classifies **standalone `M` credit notes (GBP −421,770.38) as "manual billing"**, outside the evidence O-5 was approved on. As a result the "manual billing" category has negative signed revenue. |

The Milestone 1 classification output is accepted as **correct evidence**. Milestone 2 may begin only after the engineering corrections and the `M`-credit decision in §10.

---

## 2. Independently reproduced findings

### 2.1 Method

| Aspect | Codex | This review |
| --- | --- | --- |
| Parsing | pandas `read_csv` / `read_excel` via the 002 evidence script | stdlib `csv` + `openpyxl` caches from the DS-002 review; `Decimal` from source strings |
| Seed / inventory | `generate_seed()` projection | Re-derived projection from the inventory CSV by my own code |
| Context rows | `classify()` predicates | Own predicates: zero price ∧ null customer ∧ {U1 code ∧ null description; inventory-adjustment code; mixed code ∧ admin-regex description} |
| `M` invoice context | Integration's merchandise-invoice set | Own invoice set, plus the 002A "M-only" definition for comparison |
| Adversarial tests | Codex unit tests | Reviewer-owned harness against a scratch copy of the modules, using in-memory perturbations and scratch seed copies |

### 2.2 Source integrity

| Check | Result |
| --- | --- |
| Pinned source hashes | V1 `43465a06…676d`, V2 `32569a66…d3a9`: **match** |
| Corrected-V2 rows | **1,044,848** |
| Removed block | Source rows **502,938–525,460** (contiguous, 22,523 rows), the first block's 1–9 Dec 2010 copy. Corrected V2 equals raw V2 minus exactly that block, with order preserved (tuple-by-tuple comparison) |
| Incidental exact repeats retained | **11,812** excess repeats present, as expected |
| Source-row identity | Recoverable: `source_row_number = pos` for `pos < 502,938`, else `pos + 22,523`. **The integration does not materialise this identity.** Its failure-record `"row"` field is the corrected-frame position, not the source row (§8, B-5). |
| Customer attribution | My own fingerprint over 5,942 identified customers (row count + exact signed amount) is `b239ce31…`. Codex has no equivalent invariant (§6). |

### 2.3 Seed completeness

| Item | Codex | Independent | Verdict |
| --- | --- | --- | --- |
| Raw inventory keys | 5,132 | 5,132 | **PASS** |
| Canonical keys (trim + upper) | 5,131 | 5,131; the only collision is `47503J` / `'47503J '`, both merchandise | **PASS** |
| Seed keys | 4,775 | 4,775, all unique and canonical. The seed **equals** my independent projection of the inventory (merchandise 4,750; gift voucher 10; shipping 4; manual adjustment 3; fee 2; test 2; bad debt, commission, discount, sample 1 each) | **PASS** |
| Unmapped canonical keys | 356 | 356 = 351 U1 + 5 inventory adjustment | **PASS** |
| Five inventory-adjustment codes | `23595` (2), `35600A` (1), `35605A` (1), `35978` (3), `84641` (1) | Same; all zero value, no customer | **PASS** |
| Observed codes absent from the inventory | — | **None** (V1 ∪ corrected V2) | **PASS** |
| Commercially relevant unmapped rows | 0 | **0**. Every unmapped-code row has zero value and no customer | **PASS** |
| Seed SHA-256 | `7b4611c7…1e4e` | `7b4611c7…1e4e` | **PASS** |

**Evidence quality of merchandise mappings.** The seed is an enumerated freeze of the 002A evidence classifier, so no runtime default remains. Of the 4,750 merchandise keys, 4,620 carry valid revenue and are product-named. However:

- **130 merchandise keys have no valid revenue** in corrected V2. Their mapping rests on description alone.
- **11 merchandise keys rest only on administrative notes:** `15002` "rex use", `20852`/`22126` "given away", `23059` "Thrown away-rusty", `35643` "?", `35956` "lost", `72038B` "damaged", `72732`/`72759` "thrown away-can't sell", `DCGS0067`/`DCGS0073` "ebay".

All 11 are zero-value and unattributed today, so exposure is GBP 0. But a future priced row on any of them would be accepted as merchandise without evidence (§9, N-3).

---

## 3. Numerical reconciliation

### 3.1 Category totals (corrected V2, exact Decimal)

Every Codex category row count and signed / identifiable / unattributed amount reproduces **exactly**. The table adds gross positive and gross negative components, which the Codex report does not separate.

| Category | Rows | Positive | Negative | Signed | Identifiable | Unattributed |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| merchandise | 1,038,222 | 19,699,671.127 | −719,677.94 | 18,979,993.187 | 16,410,709.747 | 2,569,283.44 |
| shipping | 3,869 | 450,162.53 | −15,567.02 | 434,595.51 | 135,700.87 | 298,894.64 |
| manual_billing (standalone `M`) | 783 | 320,707.62 | −421,770.38 | −101,062.76 | −189,416.35 | 88,353.59 |
| manual_adjustment (`ADJUST*` + embedded `M`) | 690 | 28,924.87 | −3,231.39 | 25,693.48 | 6,860.04 | 18,833.44 |
| fee | 136 | 20,987.041 | −277,989.79 | −257,002.749 | 330.001 | −257,332.75 |
| bad_debt | 6 | 11,062.06 | −158,676.14 | −147,614.08 | 0 | −147,614.08 |
| discount | 173 | 397.89 | −13,277.52 | −12,879.63 | −12,785.34 | −94.29 |
| commission | 16 | 0 | −7,933.43 | −7,933.43 | −7,933.43 | 0 |
| sample | 102 | 136.85 | −6,137.70 | −6,000.85 | 0 | −6,000.85 |
| gift_voucher | 103 | 1,839.50 | −69.56 | 1,769.94 | 0 | 1,769.94 |
| test | 17 | 226.0 | −22.5 | 203.5 | 203.5 | 0 |
| non_commercial_stock_movement | 731 | 0 | 0 | 0 | 0 | 0 |
| **Total** | **1,044,848** | **20,534,115.488** | **−1,624,353.37** | **18,909,762.118** | **16,343,669.038** | **2,566,093.08** |

### 3.2 Discrepancies

| # | Item | Codex report | Correct value | Severity |
| --- | --- | --- | --- | --- |
| D-1 | Total identifiable signed amount | GBP 16,353,668.068 | **GBP 16,343,669.038** (sum of Codex's own table and of the integration JSON) | **High (documentary)**: the headline overstates identifiable revenue by **GBP 9,999.03** |
| D-2 | Total unattributed signed amount | GBP 2,556,094.05 | **GBP 2,566,093.08** | **High (documentary)**: understated by GBP 9,999.03 |
| D-3 | Seed-mapped key coverage | "4,775 (92.0618%)" | **93.0618%** (JSON: `0.9306178…`) | Low (typo) |
| D-4 | Total signed amount | GBP 18,909,762.118 | Same | — |

D-1 and D-2 sum to the correct total, so the error lies only in the split between them. Neither figure appears in the integration JSON, so they were hand-transcribed.

### 3.3 Required properties

| Requirement | Finding |
| --- | --- |
| Merchandise returns exclude fees and adjustments | **Yes.** All 17,973 negative merchandise rows are on cancellation invoices (−719,677.94 total; −713,031.25 identified; −6,646.69 across 332 unattributed rows). There are no non-cancellation negative merchandise rows. Fees, manual lines, discounts and commission are separate categories. |
| Shipping separate | Yes (`POST`, `DOT`, `C2`, `23444`). |
| Discounts separate | Yes. |
| Bad debt and commission separate | Yes. Bad debt includes one positive GBP 11,062.06 line and five negative-price lines (−158,676.14). |
| Test rows excluded from commercial KPIs | **Separable but not yet enforced.** No KPI layer exists at Milestone 1. |
| Standalone manual billing not merchandise | Yes. However, "manual_billing" also absorbs standalone credit notes (§5). |
| No invented customer identities | **Yes on the real data** (pandas NaN). **No under alternative null representations:** `None` / `pd.NA` customers are counted as identifiable (§6, B-6). |
| Gross vs signed vs net | The Codex report gives signed values only. "Signed" here is the all-row line-value total, which includes non-sales categories and bad-debt negative-price lines. It is neither DS-002 gross positive revenue (20,533,741.918) nor net transactional revenue (19,068,438.258). The GBP 373.57 difference between 20,534,115.488 and 20,533,741.918 is positive-value lines inside the refund mask (as noted in 002A). |

---

## 4. Taxonomy and context-rule audit

### 4.1 The 2,134 context-classified rows

| Population | Rows | Predicate (as implemented) | Independent count | Justification |
| --- | ---: | --- | ---: | --- |
| U1 stock movements | 357 | price = 0 ∧ customer null ∧ code ∈ U1 ∧ description null | 357 | O-2: zero-value unattributed movements on undescribed codes |
| Inventory-adjustment codes | 8 | price = 0 ∧ customer null ∧ code ∈ five codes ∧ description ∈ {"", "adjustment", "re-adjustment", "found by jackie", "damages"} | 8 | Same; enumerated descriptions |
| Administrative descriptions on merchandise codes | 366 | price = 0 ∧ customer null ∧ (code, normalised description) ∈ reviewed inventory exception pairs | 366 | O-2 broadened to admin notes; zero value |
| **Row-context subtotal** | **731** | | **731** | |
| `M` invoice context | 1,403 | code `M`, split by whether the invoice contains a seed-merchandise row that is not an admin-context row | 1,403 | O-4 / O-5 |
| **Total "context-classified"** | **2,134** | | **2,134** | |

The label "context-classified" combines two different mechanisms: zero-value row context (731) and invoice context for `M` (1,403). Reports should keep them separate.

### 4.2 Can context rules swallow future commercial rows?

**No, on the evidence tested.** Every row-context branch requires price = 0 and a null customer, so a context row is zero-value by construction. Each of these probes was rejected with `unclassified commercial code`:

- unknown numeric codes;
- unknown described merchandise;
- unknown postage and dotcom-postage codes;
- a U1 code gaining a customer, a value, or a description;
- an inventory-adjustment code gaining a new description or a value;
- an unknown zero-value undescribed code.

### 4.3 Residual rule-design issues

- **Zero-value unattributed merchandise rows stay merchandise.** There are 5,180 such rows outside the reviewed exception pairs, plus 18 shipping, 24 gift voucher and 1 test. This is harmless monetarily, but merchandise line counts include stock movements.
- **`ADMIN_CONTEXT` is derived mechanically** from the 002A `description_exception_examples` column. It therefore includes `("23444", "next day carriage")`. This is harmless because the rule requires zero price, but the pair has no administrative meaning.
- **`_is_null` treats literal descriptions** `"nan"`, `"None"` and `"<NA>"` as null. None occur in the sources. It is a latent misclassification path.
- **Import-time coupling.** `U1_CODES` and `ADMIN_CONTEXT` are loaded from the 002A inventory at import time, so the classifier depends on two files, but only the seed carries a version.

---

## 5. `M` invoice-context audit

### 5.1 Reconstruction (corrected V2, exact Decimal)

| Population | Rows | Invoices | Customers | Positive | Negative | Signed | Identifiable signed | Unattributed signed | Cancellation-invoice rows (signed) | Valid identified positive |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| All `M` | 1,403 | 1,290 | 582 | 340,003.51 | −422,939.08 | −82,935.57 | −185,325.48 | 102,389.91 | 535 (−422,565.51) | 152,166.32 |
| Embedded (Codex) | 620 | 554 | 387 | 19,295.89 | −1,168.70 | **18,127.19** | 4,090.87 | 14,036.32 | 64 (−1,168.70) | 5,250.24 |
| Standalone (Codex) | 783 | 736 | 236 | **320,707.62** | **−421,770.38** | **−101,062.76** | −189,416.35 | 88,353.59 | 471 (−421,396.81) | **146,916.08** |
| — of which `M`-only invoices (002A definition) | 751 | 705 | 235 | 320,454.62 | −412,892.62 | −92,438.00 | −188,581.07 | 96,143.07 | 440 | **146,663.08** |
| — of which `M` + other non-merchandise (27 `M`+`POST`, 3 `D`+`M`, 2 with bank charges) | 32 | 31 | 3 | 253.00 | −8,877.76 | −8,624.76 | −835.28 | −7,789.48 | 31 | 253.00 |

### 5.2 Reconciliation with historical evidence

There is **no numerical disagreement**. The 002A figure of GBP 146,663.08 is the valid identified positive value on **`M`-only** invoices. Codex's −GBP 101,062.76 is the **signed all-row** value under a broader standalone definition (no merchandise line). That definition adds 31 `M`+non-merchandise invoices and includes unattributed rows and **all credit notes**. Under Codex's definition the valid identified positive value is GBP 146,916.08, which is GBP 146,663.08 + 253.00.

### 5.3 Does the implementation apply O-5 correctly?

**For positive standalone billing, yes. For credit notes, the policy is applied beyond its evidence base.**

- O-5 was approved on the evidence of **positive** standalone manual billing (GBP 146,663.08 identifiable). The implementation routes every standalone `M` row into `manual_billing`, including **471 cancellation-invoice rows (−GBP 421,396.81)**. This gives the "manual billing" category a negative signed total (−GBP 101,062.76) and negative identifiable value (−GBP 189,416.35), which is not interpretable as billing revenue.
- These credits are mostly **not reversals of standalone billing:**
  - 127 of the 191 customers with standalone `M` credits have **no** standalone `M` billing at all, accounting for −GBP 155,534.99.
  - Only 16 of those customers have an embedded `M` positive line.
  - Only 7 of 336 identified credit rows match an embedded `M` positive amount exactly.

  The economic meaning of these credits (goodwill, price corrections, or manual merchandise refunds) is **not determinable** from the data. Classifying them as billing, as merchandise returns, or as anything else is an owner decision. It is not implied by O-5.
- **Embedded via zero-value lines.** "Embedded" is defined by *any* seed-merchandise row, whatever its value or sign. 71 invoices (83 `M` rows) are embedded with **no positive merchandise line**. Most are credit notes containing merchandise returns, which is reasonable. 19 non-cancellation rows (+GBP 13,671.89, almost entirely unattributed) are embedded only through zero-value merchandise lines. A real-data probe confirms the effect: adding one **zero-quantity** merchandise line to a standalone-`M` invoice moved it from billing to adjustment.
- **Order independence: verified.** A shuffle of all 1,044,848 rows produced an identical report. Codex's own "order independence" test does not exercise invoice-context derivation: it re-classifies two dicts with a pre-set flag.
- **The flag is fragile.** `classify()` returns `manual_billing` when `invoice_has_merchandise` is missing, is the string `"True"`, or is `numpy.bool_(True)`, because the check is `is True`. A vectorised re-implementation in another engine could therefore silently reclassify all embedded `M` rows as billing.

---

## 6. Adversarial-test results

All tests ran against a scratch copy of the Codex modules, with the evidence script's `ROOT` repointed to the read-only sources. "Codex checks" means the assertions in Codex's integration tests, plus `test_approved_codes` where relevant.

| # | Fixture | Expected | Result | Detected by Codex tests? |
| --- | --- | --- | --- | --- |
| 1 | Unknown numeric code `123456`, priced, identified | Reject | Rejected | Partly: one described-code test exists |
| 2 | Unknown described merchandise `NEWMUG1 "RED SPOTTY MUG"` | Reject | Rejected | Yes (`UNKNOWN-X`) |
| 3 | Unknown postage `POST3 "POSTAGE"`; `DOT2 "DOTCOM POSTAGE"` unattributed | Reject | Both rejected | `POST2` yes; unattributed case no |
| 4 | U1 code gains customer | Reject | Rejected | Yes (value case only) |
| 5 | U1 code gains value / gains description | Reject | Both rejected | Value yes; description no |
| 6 | Inventory-adjustment code gains description / value | Reject | Both rejected | No |
| 7 | Unknown zero-value undescribed code | Reject | Rejected | No |
| 8 | `M` flag missing / `"True"` / `numpy.bool_(True)` | Error or adjustment | **Silently `manual_billing`** | No |
| 9 | Synthetic `M` invoices (merch / alone / zero-price merch / admin merch / credit+merch / credit alone / +`POST`) | — | Embedded: merch, zero-price merch, credit+merch. Standalone: alone, admin merch, credit alone, +`POST`. Matches the implementation's definition; the zero-price case is questionable (§5.3) | No |
| 10 | Synthetic invoices in reversed order | Identical | Identical | — |
| 11 | All 1,044,848 real rows shuffled | Identical | **Identical** | No (Codex test is trivial) |
| 12 | Zero-quantity merchandise line added to a standalone-`M` invoice (real data) | Should not change economics | **Flips one invoice to embedded** (735 / 555) | No (any change in `M` invoice counts would fail, but the semantics are untested) |
| 13 | Normalisation collision with conflicting categories | Reject | Rejected by `generate_seed` | No |
| 14 | Collision with equivalent categories | Merge | Merged | — |
| 15 | Seed: duplicate key / non-canonical key / invalid category | Reject | All rejected by `load_seed` | No |
| 16 | Seed: `85123A` merchandise → shipping | Detect | **Accepted.** 5,809 rows moved; all Codex checks pass | **No** |
| 17 | Seed: `22016` gift voucher → merchandise | Detect | **Accepted.** All Codex checks pass | **No** |
| 18 | Seed: `D` discount → merchandise | Detect | Detected (`test_approved_codes`, `M` counts) | Yes |
| 19 | Seed: `POST` row deleted | Detect | **Accepted** by `load_seed`; the integration would then raise on `POST` rows | Indirectly |
| 20 | **Codex's full suite run against a corrupted seed (`85123A` → shipping)** | Fail | **11/11 pass, and `setUpClass` → `generate_seed()` rewrote the seed file**, restoring hash `7b4611c7…` and erasing the evidence | **No; the corruption is masked** |
| 21 | One row deleted and another of equal amount duplicated (different customer) | Detect | **Not detected**; my attribution fingerprint changed | No |
| 22 | Invoice reassigned between identified customers | Detect | **Not detected** | No |
| 23 | Invoice de-attributed (customer → null) | Detect | **Not detected**; identifiable total silently falls to 16,343,378.318 | No |
| 24 | Unattributed customers supplied as `None` or `pd.NA` | Remain unattributed | **Counted identifiable.** The admin-context row also stopped matching, so `M` flipped to embedded. The integration tests nulls with `str(x) == "nan"`; the classifier uses `_is_null` | No |
| 25 | Literal descriptions `"nan"` / `"None"` / `"<NA>"` on U1 zero-value rows | Reject (real text) | Treated as null → stock movement | No |

Fixture note: in test 9 my fixture code added a cancellation prefix to the "C1" invoice by mistake, so it ran as `CC1`. The zero-price-line effect it was meant to show is confirmed independently on real data (test 12).

**Codex tests reproduced:** in a scratch copy, the full suite gives `Ran 11 tests … OK` (41.6 s), and also passes with the corrupted seed (tests 16 and 20).

---

## 7. Scientific validity assessment

| Workstream | Suitable now? | Remaining under-specification |
| --- | --- | --- |
| **R1 commercial revenue / customer reporting** | **Partly.** Categories separate returns, fees, shipping, discounts, bad debt, commission and tests correctly. | (a) Standalone `M` credit notes need a defined category and treatment. (b) Reports must carry gross positive, returns and signed fields per category, not signed only. (c) A KPI layer that excludes tests is not built. (d) "Identifiable" must be defined as customer present on the row; it is unrelated to valid-purchase status. |
| **R2 behavioural segmentation** | **Not yet assessable.** No customer-level output exists. | The O-9 purchase-occasion rule (≥1 valid merchandise line; later calendar day) is not implemented. "Merchandise-bearing invoice" for `M` currently counts zero-value and negative lines. |
| **R3 occasion / lapse labels** | **Not yet assessable.** | Same as R2. Labels must use merchandise occasions, not invoice presence. |
| **R4 customer value** | **Not yet.** | Customer-level net value depends on the treatment of standalone `M` credits: −GBP 189,416.35 identifiable, concentrated in 191 customers. Returns-only and negative-net handling is still R4 policy. |
| **R5 experimentation simulations** | **Not yet.** | Eligibility and outcomes depend on the occasion rule and the `M` credit treatment. |
| **R6 cross-engine contracts** | **Not yet.** | Null semantics (B-6), boolean flag typing, seed version/hash pinning, the "merchandise-bearing invoice" definition and materialised source-row identity all need specifying before a second engine can reproduce the results. |

Coverage of 100% (0 unclassified rows) establishes **completeness**, not **correctness**. Category correctness is currently protected only by 15 spot-checked codes and the `M` invoice counts.

---

## 8. Blocking defects

| ID | Severity | Defect | Evidence | Correction | Blocks Milestone 2 | Blocks contract encoding |
| --- | --- | --- | --- | --- | --- | --- |
| **B-1** | **High** | The test suite mutates the artifact under test. `TaxonomyTests.setUpClass` calls `generate_seed()`, which rewrites `COMMERCIAL_DS_002B_TAXONOMY_SEED.csv` in place. | Test 20: corruption erased, suite green | Tests must write the generated seed to a temporary path and compare its bytes or hash with the committed seed. | **Yes** | Yes |
| **B-2** | **High** | No seed integrity pin, and integration assertions are invariant to category assignment (the signed total does not depend on category). | Tests 16, 17, 19 | Pin the seed SHA-256 and version. Pin per-category row counts and positive / negative / identifiable / unattributed amounts for the approved seed. Pin per-key category for every non-merchandise key. | **Yes** | Yes |
| **B-3** | **High (scientific)** | Standalone `M` credit notes are classified as `manual_billing`, beyond the evidence O-5 was approved on. | §5.3: −GBP 421,770.38; 127 of 191 credit customers have no standalone billing | Split them into `manual_billing` (non-cancellation) and a separate `manual_credit` (cancellation) category, pending an owner decision on treatment. Report both. | **Yes, for any R1/R4 use**; the owner may decide in parallel | Yes |
| **B-4** | **High (documentary)** | Wrong identifiable/unattributed headline (±GBP 9,999.03). Coverage typo. Decision log cites a non-existent `COMMERCIAL_DS_002B_CONTRACT_SPECIFICATION.md` as the definition of the approved O-1…O-9. | §3.2; the file is absent | Correct the report from the JSON (no hand transcription). Create the referenced specification or repoint the decision log to an existing record of the approved O-1…O-9 wording. | **Yes** (approval traceability) | Yes |
| **B-5** | **Medium–High** | No row-identity or customer-attribution invariant. `(source_sha256, source_row_number)` is not materialised, contrary to the approved D-002-04. | Tests 21–23; §2.2 | Emit `source_row_number` per row. Add a per-customer fingerprint and a row multiset or identity checksum to the integration report, and pin them. | **Yes** | Yes |
| **B-6** | **Medium** | Null handling in the integration (`str(x) == "nan"`) diverges from the classifier (`_is_null`). `None` / `pd.NA` customers become identifiable and change `M` context. | Test 24 | One shared null predicate, used for identification, admin context and invoice context, with fixtures for NaN / None / `pd.NA`. | No (real data uses NaN) | **Yes** (R6) |

---

## 9. Non-blocking improvements

| ID | Improvement |
| --- | --- |
| N-1 | `classify()` should raise when `M` context is missing or is not a real boolean, instead of defaulting to `manual_billing` (test 8). |
| N-2 | For non-cancellation invoices, define "merchandise-bearing" as having ≥1 merchandise line with positive value, so zero-value lines cannot flip `M` context (19 rows, +GBP 13,671.89 in total, almost all unattributed). |
| N-3 | Move the 11 admin-note-only merchandise keys out of the seed into context-only handling. Add an `evidence_strength` column (revenue-bearing / description-only) for the 130 zero-revenue merchandise keys. |
| N-4 | Stop treating the literal strings `"nan"`, `"None"` and `"<NA>"` as null descriptions. Use real nulls only. |
| N-5 | Remove the mechanically inherited `("23444", "next day carriage")` admin pair. Version the admin-pair and U1 lists alongside the seed. |
| N-6 | Replace the constants `"unclassified_rows": 0` and `"unclassified_commercially_relevant_rows": 0` with measured counts, and remove the tautological test. |
| N-7 | Replace the trivial order-independence test with a shuffled-input integration comparison. |
| N-8 | Report row-context (731) and invoice-context (1,403) populations separately. |
| N-9 | Add gross positive / gross negative / signed columns per category to the report (as in §3.1). |
| N-10 | Carry per-key rationale and evidence references into the seed instead of a single generic `evidence` file name. |
| N-11 | `docs/recovery/__pycache__/` (five `.pyc` files, timestamped 21:27–21:33 on 2026-10-31) was left by the Codex session, contrary to earlier hygiene notes. This review neither created nor removed it. Codex should remove it and run tests with `PYTHONDONTWRITEBYTECODE=1`. |

---

## 10. Exact corrections required from Codex

1. **Test isolation (B-1).** `generate_seed()` must write only to a temporary path in tests. Add a test asserting `sha256(generated) == sha256(committed) == 7b4611c7…1e4e`, or the re-approved hash.
2. **Pins (B-2).** Add to the integration tests:
   - seed SHA and version;
   - the full §3.1 table (rows; positive, negative, signed, identifiable and unattributed amounts per category), as exact Decimals;
   - the category of every non-merchandise seed key;
   - a negative test showing that a flipped merchandise key, e.g. `85123A`, fails.
3. **`M` credits (B-3).** Implement the split into `manual_billing` (non-cancellation standalone) and `manual_credit` (cancellation standalone), without choosing an economic treatment. Report both with the §5.1 breakdown. Record the open owner decision.
4. **Documentation (B-4).** Regenerate every figure in the verification report from the integration JSON programmatically, correcting the identifiable and unattributed totals (16,343,669.038 / 2,566,093.08) and the coverage figure (93.06%). Resolve the missing `COMMERCIAL_DS_002B_CONTRACT_SPECIFICATION.md` reference.
5. **Identity and attribution (B-5).** Emit and pin `source_row_number` (zero-based raw V2 data row), a per-customer fingerprint, and a row-identity checksum. Add tests for deletion + duplication, customer reassignment and de-attribution (tests 21–23 here).
6. **Null semantics (B-6).** Use one null predicate everywhere, with NaN / None / `pd.NA` fixtures.
7. Address N-1 and N-2 before contract encoding. N-3 to N-10 may be scheduled.
8. Re-run twice, publish the new output SHA-256, and submit for a light re-review.

---

## 11. Recommendation on whether Milestone 2 may begin

**Not yet. Milestone 2 may begin once corrections 1–6 are complete and re-reviewed.** The classification itself is correct and reproducible and needs no rework. The blockers are:

- safeguards that would not catch a future regression (B-1, B-2, B-5);
- documentation that misstates the identifiable/unattributed split and cites a missing approval record (B-4);
- a manual-credit population that needs its own category before any revenue or customer-value use (B-3).

The owner may decide the economic treatment of standalone `M` credits in parallel. Milestone 2 work on R1 or R4 revenue must not proceed until that decision is recorded.

---

## Reproducibility record

| Command (repository root unless noted) | Result |
| --- | --- |
| `shasum -a 256 data/raw/* docs/recovery/*002B*` | Sources and seed match the pinned values; script and test hashes recorded at review start |
| `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python docs/recovery/COMMERCIAL_DS_002B_INTEGRATION.py > run1.json` (×2) | Both exit 0; **SHA-256 `3940d2b0c32394e49d16c574f612dd6a41a0fe57c8838bdc1b591b1c8273f1df`** for both; `cmp` identical |
| Seed SHA-256 | **`7b4611c78ca22d108c2616076c84b7c1db2efb8453ee9a32faceb027bb181e4e`**, unchanged after review |
| `python -m unittest discover -s <scratch copy> -p 'test_COMMERCIAL_DS_002B_*.py'` | 11 tests OK (run in a scratch copy because the suite rewrites the seed) |
| Same suite with corrupted scratch seed | 11 tests OK; seed rewritten (B-1) |
| Reviewer independent reconstruction and adversarial harness | In the session scratchpad, outside the repository |

**Working tree at review end:**

```text
## main...origin/main [ahead 1]
?? .vscode/
?? PROJECT_TECHNICAL_HANDOVER.md
?? docs/recovery/
```

- The only file this review created in the repository is this document.
- A pre-existing `docs/recovery/__pycache__/` from the Codex session was left untouched (N-11).
- No tracked file changed.
- Unrelated untracked files were preserved.
- Nothing was committed or pushed.

---

**COMMERCIAL-DS-002B MILESTONE 1 — INDEPENDENT REVIEW VERDICT**

**CONDITIONAL PASS.**

The implementation is **correct**. All 1,044,848 corrected-V2 rows are classified, with 0 unclassified. Category rows and amounts, the 731 row-context and 1,403 `M` invoice-context populations, and the output SHA `3940d2b0…` reproduce exactly from independent code. The classifier fails closed on every unknown-code probe tested.

The milestone is **not yet scientifically or operationally sound**, for four reasons:

- The tests overwrite the seed they verify, and they cannot detect category, row or customer-attribution corruption.
- The verification report misstates the identifiable/unattributed split by GBP 9,999.03, and the decision log cites a missing specification.
- Standalone `M` credit notes (−GBP 421.8k) are classified as "manual billing" beyond the approved evidence.
- Null handling would invent customer identities under non-NaN nulls.

**Milestone 2 may not begin** until Codex completes corrections 1–6 in §10 and they pass a light independent re-review. The owner decides the treatment of standalone `M` credits.
