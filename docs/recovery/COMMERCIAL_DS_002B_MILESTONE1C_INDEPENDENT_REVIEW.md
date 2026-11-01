# COMMERCIAL-DS-002B — Milestone 1C Final Independent Re-Review

**Reviewer:** Claude Code (independent of the implementation agent)<br>
**Review date:** 2026-10-31<br>
**Subject:** Codex's closure of blockers B-1 … B-6 from the [Milestone 1 independent review](COMMERCIAL_DS_002B_MILESTONE1_INDEPENDENT_REVIEW.md). Evidence reviewed:
- the [1B handover](COMMERCIAL_DS_002B_MILESTONE1B_REVIEW_HANDOVER.md) and [1C handover](COMMERCIAL_DS_002B_MILESTONE1C_REVIEW_HANDOVER.md);
- the [decision log](COMMERCIAL_DS_001_DECISION_LOG.md);
- [`COMMERCIAL_DS_002B_TAXONOMY.py`](COMMERCIAL_DS_002B_TAXONOMY.py), the [seed](COMMERCIAL_DS_002B_TAXONOMY_SEED.csv) and [`COMMERCIAL_DS_002B_INTEGRATION.py`](COMMERCIAL_DS_002B_INTEGRATION.py);
- both test files and the [verification report](COMMERCIAL_DS_002B_MILESTONE1_VERIFICATION.md).

**Status:** Read-only review. No Codex file, seed, raw source, pipeline or evidence file was modified. All corruption and mutation probes ran on scratch copies or in-memory frames. Nothing was committed or pushed.

---

## 1. Executive verdict: **PASS WITH CONDITIONS**

| Dimension | Verdict |
| --- | --- |
| **Implementation correctness** | **Correct.** Every category row count and all six Decimal components per category reproduce exactly from my independent code, including the four `M` categories. Both integrity fingerprints (`80a6d26e…` row, `248f421f…` customer) reproduce **bit for bit** from a clean-room reimplementation, so every row's source identity, content and category agrees. |
| **Blocker closure** | **All six closed.** B-1, B-2, B-3, B-4 and B-6 are fully closed. B-5 is closed for every mutation class the Milestone 1 review specified, with two residual gaps (country and description are not fingerprinted; source-row numbers are derived from position) that are non-blocking for Milestone 2. |
| **Engineering safeguards** | **Adequate for Milestone 2.** The seed is immutable under tests. Category corruption is rejected twice: by the SHA pin, and, with the pin bypassed, by the frozen per-category references. Row and customer corruption is rejected by pinned fingerprints. |
| **Scientific validity** | **Sound for the purposes of Milestone 2**, subject to the conditions in §9. The O-5 categories are mechanically correct, carry no inferred linkage or cause, and are separate from merchandise. |
| **Documentation** | **Minor residual defects.** The weak-code row count is stated as 22 (actual 20). Superseded figures remain in place without inline markers. The O-5 wording is ambiguous for cancellation invoices. None changes a reported financial total. |

**Milestone 2: GO, subject to the conditions in §9 and §10.**

---

## 2. Six-blocker closure matrix

| Blocker | Codex claim | Independent verification | Status |
| --- | --- | --- | --- |
| **B-1** Seed overwritten by tests | Derives only into a temp directory; asserts the seed hash before and after | Seed SHA `7b4611c7…1e4e` before the suite, after the suite (18/18 OK), and after two integration runs. `generate_seed` is called only with a temp `output=`. **Failing-test case:** in a scratch copy with `85123A` corrupted to shipping, the suite fails loudly (`authoritative seed SHA-256 mismatch: 90693c87…`; 2 setUpClass errors) and **the corrupted file is left untouched**, with no silent regeneration. | **CLOSED** |
| **B-2** Category-insensitive validation | Seed SHA/version pin plus frozen per-category references | The `EXPECTED` table is a code literal with no generator path. It equals my classifier-independent reconstruction exactly (§3), so it is genuinely independent. Mutations: `85123A`→shipping, the `85123A`/`POST` swap, `22016` gift voucher→merchandise and `23702` merchandise→test (low volume) are all **rejected by the SHA pin**, and also **rejected by the frozen category references when the pin is bypassed**. A stock-code swap between two merchandise rows preserves every category total and the global rows and revenue; it is **rejected by the pinned row fingerprint**. | **CLOSED** |
| **B-3** Standalone `M` credits | Owner-approved O-5 amendment implemented | The amendment is recorded verbatim in the decision log §3A. All four categories reproduce exactly from raw rows and invoice context (§5). Classification depends only on the row's sign and its invoice's merchandise context; there is no pairing logic or cause attribution. | **CLOSED** (owner approval cited to an external conversation; see §9 C-6) |
| **B-4** Documentation / numbers | Corrected totals; specification flagged as planned | Identifiable **16,343,669.038**, unattributed **2,566,093.08** and total **18,909,762.118** are asserted in tests and in the JSON. Coverage is **4,775 / 5,131 = 0.930617813…**. The decision log now states the contract specification "does not yet exist … a planned artifact", which is not a false claim. Residual: superseded figures without inline markers, and a 22-vs-20 weak-row error (§9). | **CLOSED** (minor residuals) |
| **B-5** Source-row and customer integrity | Source-row identity and length-prefixed fingerprints | `source_row_number` is correct for all 1,044,848 rows (tuple-equal to raw V2 at that index). Both fingerprints reproduce independently. Every mutation class in the Milestone 1 review is detected (§4, §6). Residuals: country, description and raw code case are not fingerprinted; numbering is positional. | **CLOSED** (residuals non-blocking) |
| **B-6** Missing-customer / context semantics | Shared type-aware null predicate; strict boolean flag | NumPy NaN, Python NaN, `None` and `pd.NA` give **identical** category and attribution reports through the full integration path. The `M` flag accepts only Python and NumPy booleans; `None`, `"True"`, `1`, `0`, `np.int64(1)` and `1.0` are all rejected. Literal `"nan"` descriptions are kept as text. Residual: an empty-string customer crashes with a non-descriptive `int()` error (fails closed). | **CLOSED** |

---

## 3. Independently reproduced numerical findings

Method: the DS-002 review caches (stdlib `csv` / `openpyxl` parse, `Decimal` prices), the frozen seed and the 002A inventory. My own context predicates, invoice-context rule and category assignment were used, with no Codex imports.

| Category | Rows | Positive | Negative | Signed | Identifiable | Unattributed | Match |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | :---: |
| merchandise | 1,038,222 | 19,699,671.127 | −719,677.94 | 18,979,993.187 | 16,410,709.747 | 2,569,283.44 | ✔ |
| shipping | 3,869 | 450,162.53 | −15,567.02 | 434,595.51 | 135,700.87 | 298,894.64 | ✔ |
| standalone_manual_billing | 330 | 334,379.51 | 0 | 334,379.51 | 146,916.08 | 187,463.43 | ✔ |
| standalone_manual_credit | 470 | 0 | −421,770.38 | −421,770.38 | −336,332.43 | −85,437.95 | ✔ |
| standalone_manual_zero_value | 2 | 0 | 0 | 0 | 0 | 0 | ✔ |
| manual_adjustment | 671 | 15,252.98 | −3,231.39 | 12,021.59 | 6,860.04 | 5,161.55 | ✔ |
| fee | 136 | 20,987.041 | −277,989.79 | −257,002.749 | 330.001 | −257,332.75 | ✔ |
| bad_debt | 6 | 11,062.06 | −158,676.14 | −147,614.08 | 0 | −147,614.08 | ✔ |
| discount | 173 | 397.89 | −13,277.52 | −12,879.63 | −12,785.34 | −94.29 | ✔ |
| commission | 16 | 0 | −7,933.43 | −7,933.43 | −7,933.43 | 0 | ✔ |
| sample | 102 | 136.85 | −6,137.70 | −6,000.85 | 0 | −6,000.85 | ✔ |
| gift_voucher | 103 | 1,839.50 | −69.56 | 1,769.94 | 0 | 1,769.94 | ✔ |
| test | 17 | 226.0 | −22.5 | 203.5 | 203.5 | 0 | ✔ |
| non_commercial_stock_movement | 731 | 0 | 0 | 0 | 0 | 0 | ✔ |
| **Total** | **1,044,848** | **20,534,115.488** | **−1,624,353.37** | **18,909,762.118** | **16,343,669.038** | **2,566,093.08** | ✔ |

Other reproduced values:

- Seed coverage: 4,775 of 5,131 canonical keys = **93.0618%**.
- Row context: 731 rows.
- Identified customers: 5,942, on 809,561 rows.
- `manual_adjustment` = 70 `ADJUST*` rows + 601 embedded `M` rows (signed 7,566.29 + 4,455.30 = 12,021.59).

**Gross, signed and net.** These are all-row taxonomy line values. Total positive (20,534,115.488) differs from DS-002 gross positive revenue (20,533,741.918) by the GBP 373.57 of positive lines inside the refund mask. Net merchandise for customers is not yet defined; that is Milestone 2 work.

---

## 4. Adversarial-test results

Every probe ran against a scratch copy of the current modules. "Pinned fingerprints" means the row and customer hashes asserted in Codex's integration test. `build_report` itself asserts category references but not fingerprints.

| # | Mutation (real corrected V2 unless noted) | Result |
| --- | --- | --- |
| 1 | Seed `85123A` → shipping | Rejected by SHA pin. With the pin bypassed: rejected by category references (merchandise rows 1,038,222 → 1,032,413) |
| 2 | Seed `85123A` ↔ `POST` swap (global rows and revenue preserved) | Rejected by SHA pin; with the pin bypassed, rejected by category references |
| 3 | Seed `22016` gift voucher → merchandise | Rejected by SHA pin; with the pin bypassed, rejected by category references |
| 4 | Seed `23702` merchandise → test (4 rows) | Rejected by SHA pin; with the pin bypassed, rejected by category references |
| 5 | Stock codes swapped between two merchandise rows (every category total preserved) | **Detected by the row fingerprint**; customer fingerprint unchanged, as it should be |
| 6 | One row deleted, one equal-amount row of another customer duplicated | Detected (row and customer fingerprints) |
| 7 | Invoice reassigned to another identified customer | Detected (row and customer fingerprints) |
| 8 | Invoice de-attributed (customer → null) | Rejected by `build_report` (identifiable reference mismatch) |
| 9 | Customer revenue reassignment (customers swapped on two unequal lines) | Detected (row and customer fingerprints) |
| 10 | Invoice date shifted by one day | Detected (row fingerprint) |
| 11 | Rows shuffled, content identical | Detected (fingerprints change, because `source_row_number` is derived from position; §6) |
| 12 | **Description changed** on a merchandise row | **Not detected** (not a fingerprint input; category unaffected) |
| 13 | **Country changed** on an identified row | **Not detected** (not a fingerprint input) |
| 14 | Raw code case changed (`85123A` → `85123a`) | Not detected (by design: the normalised code is fingerprinted) |
| 15 | Null forms NumPy NaN / Python NaN / `None` / `pd.NA` (synthetic invoices through `build_report`) | **Identical** category and attribution output |
| 16 | Empty-string customer | Raises `ValueError: invalid literal for int()` (fails closed; message unhelpful) |
| 17 | `M` flag `True` / `False` / `np.True_` / `np.False_` | Accepted, giving `manual_adjustment` / `standalone_manual_billing` |
| 18 | `M` flag `None`, `"True"`, `1`, `0`, `np.int64(1)`, `1.0` | All rejected |
| 19 | Synthetic `M` invoice set, forward vs reversed order | Identical categories |
| 20 | Weak code priced; identified at zero price; string price `"0.50"`; padded lower-case `' dcgs0067 '`; empty-string customer | All rejected (`commercial exposure`) |
| 21 | Weak code, zero value, unattributed, with a new product description | Accepted as merchandise (zero exposure; consistent with the guard's stated scope) |
| 22 | Unknown numeric, described, postage and zero-value codes; U1 or inventory-adjustment codes gaining value, customer or description | All rejected (re-confirmed from the Milestone 1 harness; the logic is unchanged) |

**Codex suite:** 18 tests, all pass, on the authoritative files. With a corrupted scratch seed, 0 tests run and 2 setUpClass errors are raised, and the corrupted seed is preserved.

---

## 5. O-5 semantic verification

### 5.1 Reconstruction from raw rows and invoice context

Invoice context, as implemented and reproduced: an invoice is merchandise-bearing if it has a seed-merchandise row that is not row-context and has value **> 0 on a non-cancellation invoice**, or value **≠ 0 on a cancellation invoice**.

| Category | Rows | Invoices | Customers | Signed | Identifiable | Unattributed | Row pattern |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| standalone_manual_billing | **330** | 311 | 109 | **334,379.51** | 146,916.08 | 187,463.43 | quantity > 0, price > 0 (1 row on a cancellation invoice) |
| standalone_manual_credit | **470** | 443 | 191 | **−421,770.38** | −336,332.43 | −85,437.95 | all 470 on cancellation invoices; quantity < 0, price > 0 |
| standalone_manual_zero_value | **2** | 2 | 2 | **0** | 0 | 0 | — |
| manual_adjustment (embedded `M`) | **601** | 535 | 387 | **4,455.30** | 4,090.87 | 364.43 | 64 rows are negative on cancellation invoices (−1,168.70) |

All four reproduce Codex and the expected table exactly. No `M` row has a negative unit price. No standalone invoice contains both billing and credit rows.

### 5.2 No inferred linkage or cause

`classify()` uses only the row's own `Quantity × UnitPrice` sign and its invoice's boolean context. Nothing in the taxonomy or integration modules pairs credits with earlier invoices, references customer history or labels economic cause. The decision log states that cause is unknown. **Verified.**

### 5.3 Exclusion from merchandise and behavioural metrics

At Milestone 1, all four `M` categories are distinct labels and never `merchandise`, so any consumer that selects `category == "merchandise"` excludes them. **No purchase-occasion or customer-value builder exists yet**, so their exclusion from occasions and behavioural metrics is a requirement for Milestone 2, not something already proven (§9 C-1).

### 5.4 Wording ambiguity (non-blocking)

The decision-log amendment defines standalone as "the invoice has no qualifying **positive** merchandise line". Read literally, the 64 embedded `M` credits on cancellation invoices that also return merchandise (−GBP 1,168.70; 52 invoices; 47 customers) would become `standalone_manual_credit`. The implementation, the expected table in this review's brief and the referenced Milestone 1 recommendation (N-2) all treat a non-zero merchandise return on a cancellation invoice as qualifying context. The implementation is defensible, but the decision-log text should state the cancellation-invoice rule explicitly (§9 C-4).

---

## 6. Row and customer integrity assessment

| Aspect | Finding |
| --- | --- |
| Source-row identity | `source_row_number = pos` for `pos < 502,938`, else `pos + 22,523`. **Verified correct for all 1,044,848 rows** against the raw V2 tuples. Identity is `(V2 SHA-256, source_row_number)`, and duplicate identities raise. |
| How identity is obtained | **Derived from row position in the corrected frame, using hardcoded offsets.** It is not carried from ingestion. It is correct because the evidence script asserts block structure and order. A reordered loader would produce wrong numbers, which the pinned fingerprint would detect (test 11) but not explain. D-002-04 requires assignment once at ingestion (§9 C-2). |
| Row fingerprint inputs | source SHA, source row, normalised code, invoice, customer-missing flag, customer ID, quantity, unit price, date, category. **Omitted: description, country, raw code variant.** |
| Customer fingerprint inputs | Per customer: row count, exact signed amount, list of source rows. Covers attribution completely. |
| Serialization | Canonical compact JSON (`sort_keys`), 8-byte length prefix per record. Records sorted by `source_row_number`, customers by customer-ID string. Collision-safe and order-stable. **Reproduced bit for bit independently.** |
| Where pins are enforced | Fingerprint pins are asserted **only in the integration test**. `build_report` asserts the category references, not the fingerprints. That is acceptable for an evidence runner, but Milestone 2 producers should call `assert_integrity` themselves (§9 C-3). |
| Expected values | Row `80a6d26ec87d2cb1d9988c4fc7f28c2b611f64491caa611405da9f7d7c184022` and customer `248f421fbcacfaf1e63b3a5a69da78ec3097ce0cfa73c50f1e6ed733e4736d51`: **reproduced**. |

---

## 7. Weak-code limitation assessment

| Code | Corrected-V2 rows | V1 rows | Value | Identified | Description |
| --- | ---: | ---: | ---: | ---: | --- |
| 15002 | 1 | 0 | 0 | 0 | rex use |
| 20852 | 5 | 0 | 0 | 0 | Given away / given away |
| 22126 | 3 | 0 | 0 | 0 | given away |
| 23059 | 1 | 1 | 0 | 0 | Thrown away-rusty |
| 35643 | 2 | 0 | 0 | 0 | ? |
| 35956 | 1 | 0 | 0 | 0 | lost |
| 72038B | 1 | 0 | 0 | 0 | damaged |
| 72732 | 2 | 1 | 0 | 0 | thrown away-can't sell |
| 72759 | 2 | 1 | 0 | 0 | thrown away-can't sell. |
| DCGS0067 | 1 | 1 | 0 | 0 | ebay |
| DCGS0073 | 1 | 1 | 0 | 0 | ebay |
| **Total** | **20** | 5 | **0** | **0** | |

- **Row-count discrepancy.** The handovers and verification report say **22** rows. The correct corrected-V2 figure is **20**, which is also what Codex's own test asserts. The V1 rows are a subset of corrected V2.
- **Wording discrepancy.** The verification report says these rows "retain their prior context classification". They are classified **`merchandise`** (seed), not row-context.
- **Future exposure fails closed.** A non-zero price (including string or unparseable prices), an identified customer (including `""`) and padded or lower-case code variants are all rejected (tests 20, 21).
- **No other key escapes with similarly weak evidence.** I scanned every other seed-merchandise key across V1 ∪ corrected V2. **None** has only administrative-style descriptions. Only two keys (`23001` "TRAVEL CARD WALLET DOTCOMGIFTSHOP" and `49031B` "CHROME EURO HOOK 20cm") have no priced and no identified row, and both are product-named.
- **Observed vs future.** The historical classification of these 20 rows is immaterial (GBP 0). Their descriptions are **not** evidence that would justify classifying a future priced row as merchandise, and the guard correctly blocks that case.

---

## 8. Reproducibility evidence

Commands run from the repository root:

| Step | Command | Result |
| --- | --- | --- |
| 1 | `shasum -a 256 docs/recovery/COMMERCIAL_DS_002B_TAXONOMY_SEED.csv` | `7b4611c78ca22d108c2616076c84b7c1db2efb8453ee9a32faceb027bb181e4e` |
| 2 | `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s docs/recovery -p 'test_COMMERCIAL_DS_002B_*.py' -v` | **Ran 18 tests in 49.5 s — OK** |
| 3 | Seed hash again | `7b4611c7…1e4e` (unchanged) |
| 4 | `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python docs/recovery/COMMERCIAL_DS_002B_INTEGRATION.py > run{1,2}.json` | Both exit 0 |
| 5 | `shasum -a 256 run1.json run2.json; cmp` | Both **`1db45949690120c7bf7408473d0a24d52dc2e368943047d1120963d3562d4d04`**; byte-identical |
| 6 | Independent reconstruction (§3) | All 14 categories × 6 components match; totals match |
| 7 | Category counts and row reconciliation | 14 categories sum to **1,044,848**; 0 unclassified; 0 commercially relevant unclassified |
| — | Raw sources | V1 `43465a06…676d`, V2 `32569a66…d3a9` (unchanged) |

Matching hashes were not treated as proof of correctness. Correctness rests on the independent reconstruction (§3, §5) and the clean-room fingerprint match (§6).

---

## 9. Remaining blockers and caveats

**There are no blocking scientific or implementation defects for starting Milestone 2.**

### Conditions for Milestone 2 work

| ID | Type | Condition |
| --- | --- | --- |
| **C-1** | Scientific, binding | The purchase-occasion builder must select `category == "merchandise"` **and** the valid-line predicate: quantity > 0, price > 0, non-cancellation invoice, customer present. It must **not** reuse the integration's `merch_invoices` set, which is an `M`-context device that includes unattributed lines and cancellation invoices. Tests must show that all four manual categories, shipping, fees, tests and vouchers can never create an occasion. |
| **C-2** | Implementation, before contract encoding | Materialise `source_row_number` at ingestion (in the loader), rather than reconstructing it from position with hardcoded offsets. Carry it through every Milestone 2 table. |
| **C-3** | Implementation | Milestone 2 producers should call `assert_integrity` (or equivalent) at run time, not only in tests. Add `country` (an R1/R3 business field) to the row fingerprint before contract encoding; description is optional. |
| **C-4** | Documentation | Amend the O-5 decision-log text to state the cancellation-invoice context rule explicitly (§5.4). |
| **C-5** | Documentation | Correct "22 rows" to **20** and "retain their prior context classification" to "classified merchandise by the frozen seed". Add inline `SUPERSEDED` markers to the earlier verification tables (16,353,668.068 / 2,556,094.05; 92.0618%; `manual_billing` −101,062.76), which are currently superseded only by later addenda and a header line. |
| **C-6** | Governance | O-5 owner approval is sourced to an external ChatGPT conversation ("yes"), which this review cannot inspect. The decision log records it explicitly, and that record is accepted as the source of truth under the log's own rules. The owner should confirm the entry when convenient. |

### Non-blocking limitations

- An empty-string customer raises an unhelpful `int()` error. It should be an explicit null/format rejection.
- The `build_report(validate_reference=False)` bypass exists. Restrict it to tests, or log loudly when it is used.
- `generate_seed()` still defaults `output=` to the authoritative seed. Remove the default.
- A stale `docs/recovery/__pycache__/` from 21:27–21:33 remains (Milestone 1 N-11). Its bytecode is out of date, so Python ignores it; it should still be removed.

### Future-work notes for Milestone 2 tasks (carried from DS-002 / 002A)

| Milestone 2 task | Foundation sufficient? | Note |
| --- | --- | --- |
| Category-level revenue reconciliation | **Yes** | Use positive / negative / signed per category. Bad debt includes 5 negative-price lines outside the DS-002 refund mask. |
| Merchandise purchase-occasion construction | **Yes**, with C-1 | Apply O-9 (later calendar day) for repeat purchases, with invoice-level repeat as a sensitivity. |
| Repeat-purchase measurement | **Yes** | The expected 12-month-proxy 90-day later-day rate was 40.45% under the DS-002 list. Re-pin it under the approved taxonomy. |
| Acquisition-proxy eligibility | **Yes** | Lower-bound contamination 3.0–13.6% and per-cohort observed look-back must be disclosed (P-17 / D-002-07). |
| Formal business-contract specification | **Yes, as a document to author** | `COMMERCIAL_DS_002B_CONTRACT_SPECIFICATION.md` does not exist yet. It should be written from the decision log §3A, this review's conditions and the frozen references. Encoding still requires separate authorisation. |

---

## 10. Milestone 2 go/no-go recommendation

**GO.** COMMERCIAL-DS-002B Milestone 2 may begin. The foundation is correct, reproducible and adequately protected:

- exact category reconciliation;
- O-5 implemented as approved, with no inferred linkage;
- an immutable seed;
- category, row and customer corruption all detected;
- consistent null semantics.

Conditions C-1 (binding for occasion construction) and C-2 / C-3 (before contract encoding) must be honoured inside Milestone 2. C-4 and C-5 are documentation fixes that Codex can complete at the start of Milestone 2. Milestone 2 approval does **not** authorise production contract encoding, Phase 3 or downstream modelling.

---

**Working tree at review end:**

```text
## main...origin/main [ahead 1]
?? .vscode/
?? PROJECT_TECHNICAL_HANDOVER.md
?? docs/recovery/
```

- This review created exactly one repository file: this document.
- The seed, raw sources and every Codex file have their pre-review hashes.
- Reviewer scripts, scratch module copies and outputs are in the session scratchpad.
- Nothing was committed or pushed.

---

**COMMERCIAL-DS-002B MILESTONE 1C — INDEPENDENT RE-REVIEW VERDICT**

**PASS WITH CONDITIONS.**

All six Milestone 1 blockers are closed and independently verified:

- **B-1:** the seed is immutable, including when tests fail.
- **B-2:** category mutations are rejected by the SHA pin and, independently, by frozen references.
- **B-3:** the owner-approved O-5 split reproduces exactly (330 / 334,379.51; 470 / −421,770.38; 2 / 0; 601 / 4,455.30) with no inferred linkage.
- **B-4:** the corrected totals 16,343,669.038 / 2,566,093.08 / 18,909,762.118 and coverage of 93.0618% are verified.
- **B-5:** both fingerprints reproduce bit for bit, and every specified mutation class is detected.
- **B-6:** all four null forms behave identically, and ambiguous `M` flags are rejected.

The integration output `1db45949…` and the seed `7b4611c7…` reproduce. **Milestone 2 may begin**, with these conditions:

- occasions use only valid merchandise lines (C-1);
- source-row identity is materialised at ingestion, and country is added to the fingerprint, before contract encoding (C-2 / C-3);
- the documentation corrections in C-4 and C-5 are made.
