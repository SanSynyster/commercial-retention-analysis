# COMMERCIAL-DS-003 Stage A — Independent Scientific and Engineering Review

**Reviewer:** Claude Code (independent of the implementation agent)<br>
**Review date:** 2026-10-31<br>
**Subject:** The COMMERCIAL-DS-003 Stage A contract foundation:
- [Stage A handover](COMMERCIAL_DS_003_STAGE_A_HANDOVER.md);
- [contract specification](COMMERCIAL_DS_002B_CONTRACT_SPECIFICATION.md);
- [frozen reference pins](COMMERCIAL_DS_003_STAGE_A_REFERENCE_PINS.json);
- the revised [evidence script](COMMERCIAL_DS_002_ANALYSIS.py) loader and [integration runner](COMMERCIAL_DS_002B_INTEGRATION.py);
- [`test_COMMERCIAL_DS_003_CONTRACT.py`](test_COMMERCIAL_DS_003_CONTRACT.py) and the updated integration and taxonomy tests;
- the [decision log](COMMERCIAL_DS_001_DECISION_LOG.md), read against the [Milestone 1C review](COMMERCIAL_DS_002B_MILESTONE1C_INDEPENDENT_REVIEW.md).

**Status:** Read-only review. No seed, raw source, implementation, test, pin or evidence file was modified. All probes ran on scratch copies or in-memory frames. Nothing was committed or pushed.

---

## 1. Executive verdict: **PASS WITH CONDITIONS**

| Dimension | Verdict |
| --- | --- |
| **Source identity** | **Correct.** Zero-based identity is assigned at raw CSV ingestion, before any transformation. Exactly raw rows 502,938–525,460 (22,523) are removed, and the remaining 1,044,848 identities are unique, stable under shuffling and pinned. Reproduced from the raw file with the stdlib `csv` module. |
| **Fingerprint enforcement** | **Correct and runtime-enforced.** All four fingerprints reproduce bit for bit from an independent stdlib-csv clean room. `build_report()` fails on any mismatch. Country, description, raw code, customer, date, price, category, source-row substitution and both forms of duplicate-for-deletion were all rejected on real data. |
| **Financial and classification reconciliation** | **Exact.** 1,044,848 / 1,042,714 / 2,134 / 0. GBP 16,343,669.038 + 2,566,093.08 = 18,909,762.118. The O-5 cancellation context is 64 rows, −1,168.70, 52 invoices and 47 customers. |
| **Purchase-occasion contract (written specification)** | **Scientifically sound.** It is strict, separate from the `M` context set, keeps lineage, uses later-calendar-day as primary repeat and keeps invoice repeat as a sensitivity. Under it, independently: 788,127 qualifying lines, 36,594 occasions, 5,852 customers, GBP 17,123,740.997. |
| **Contract test oracle** | **Weaker than the written contract.** It accepts `pd.NaT`, `" C…"` / `"c…"` cancellation IDs, negative, zero and exponent-form customer IDs, and fractional quantities. None occurs in the real data, but the oracle must not become the reference implementation. |
| **Temporal contract** | **Not yet specified, by design.** Horizons, windows, acquisition cutoff and anchors are deferred. Two definitions must be fixed before Stage B builds cohorts or labels (§5). |
| **Reproducibility** | 26/26 tests pass. Seed `7b4611c7…` and pin file `a96d2e9d…` are unchanged. Integration `2ffcbef7…` is byte-identical across two runs. |

**Stage B: GO.** No defect blocks the start of Stage B. The conditions in §9 must be met *inside* Stage B before the corresponding producers are accepted.

---

## 2. Source identity findings

Independently reconstructed from `data/raw/online_retail_II.csv` with the stdlib `csv` module, sharing no code with Codex:

| Check | Result |
| --- | --- |
| Raw data rows / single chronological reset | 1,067,371 / zero-based index 525,461 |
| Removed rows | Exactly **502,938–525,460** inclusive, contiguous, **22,523** rows (the first block's 1–9 Dec 2010 copy) |
| Corrected rows | **1,044,848**; source identities unique; equal to raw positions minus that interval |
| Incidental exact repeats retained | 11,812 excess repeats, each with its own identity |
| Identity assigned before transformation | Yes. `assign_source_row_numbers()` is called immediately after `read_csv` and before renaming, slicing, sorting or correction. It refuses to reassign if the column exists, and `load_sources` asserts contiguity `0…1,067,370`. |
| Lineage asserted after correction | Yes. `source_block_evidence` requires the column and asserts uniqueness. The full corrected ID list must equal `range(0, 502,938) ∪ range(525,461, 1,067,371)`. |
| Sorting / filtering | Real-data shuffle of all rows: the report is **identical**, because identity travels with the row. The synthetic slice and sort test also passes. |
| Missing identity | A frame without `source_row_number` is rejected, but as an `AttributeError` crash rather than an explicit error (§9 N-2). |
| Ingestion bypass | Within the Stage A evidence path, none: `load_sources` is the only loader, and V1 is used only for overlap evidence. **Outside it**, `src/data_loading.py`, `src/validation.py` and `src/spark_pipeline.py` read raw files **without** identity. A Stage B producer built on them would violate the contract (§9 S-7). |

---

## 3. Fingerprint enforcement findings

### 3.1 Provenance and enforcement

- The pins live in `COMMERCIAL_DS_003_STAGE_A_REFERENCE_PINS.json`. The runner checks that file's SHA-256 against a constant in code (`a96d2e9d…`) and then compares source hashes, seed hash, corrected rows, the overlap interval and all four fingerprints. No code path writes the pin file or the seed, and both hashes were identical before and after the full suite.
- **The pins are independently verified, not merely self-consistent.** Codex generated them, but I reproduced every value from a clean room using stdlib `csv` parsing, my own classification predicates and my own serializer:

| Pin | Value | Independent |
| --- | --- | :---: |
| Row (country-sensitive) | `d76696efc5d02069d1180c84286e813973f810ca8fbf2b356ebc03f45bca1a04` | ✔ |
| Legacy row | `80a6d26ec87d2cb1d9988c4fc7f28c2b611f64491caa611405da9f7d7c184022` | ✔ |
| Source content (raw code, description, country) | `59970949b45bf75263217525fa9f437c672d39503c7b2c605275601546299c6d` | ✔ |
| Customer | `248f421fbcacfaf1e63b3a5a69da78ec3097ce0cfa73c50f1e6ed733e4736d51` | ✔ |

### 3.2 Mutation results (real corrected V2, through `build_report`)

| Mutation | Result |
| --- | --- |
| Country changed on one row | **Rejected** (row fingerprint) |
| Description changed, category unchanged | **Rejected** (source-content fingerprint) |
| Raw stock-code case changed | **Rejected** (source-content fingerprint) |
| One invoice reassigned to another customer | **Rejected** (row fingerprint) |
| Date +1 day | **Rejected** (row fingerprint) |
| Unit price +1×10⁻¹² | **Rejected** (category Decimal reference) |
| Source-row IDs swapped between two rows | **Rejected** (row fingerprint) |
| Duplicate-for-deletion, copy keeps its own ID | **Rejected** (`duplicate source row identity`) |
| Duplicate-for-deletion, copy relabelled with the deleted ID | **Rejected** (row fingerprint) |
| Seed category flip, SHA enforced / SHA bypassed | **Rejected** by the seed SHA / by the category references |
| Pin file tampered | **Rejected** (pin-file SHA) |
| Pin file tampered **and** its SHA constant updated | **Rejected** (actual fingerprint ≠ tampered pin) |
| All rows shuffled, identities carried | Accepted, **identical report** (correct) |

### 3.3 Serialization and environment

- Records are canonical compact JSON with sorted keys and an 8-byte length prefix. Records are ordered by `source_row_number` and customers by ID string. Nulls are explicit (`customer_missing` plus `None`). Integers stay integers. Unit prices are `str(Decimal(str(float)))`.
- **Environment dependence.** Prices pass through pandas' float parser. In this environment, all 1,044,848 parsed prices equal the source text exactly, which is why a stdlib/Decimal clean room reproduces the pins. A different pandas version or engine (for example pyarrow) could in principle parse differently. The pins would then **fail closed** rather than pass silently. Fingerprints are therefore meaningful within a pinned environment. For cross-engine work (R6), derive Decimals from the raw text (§9 S-8).
- **Weakness.** CSV empty strings become NaN, so empty and missing descriptions are indistinguishable. The source itself carries no such distinction, so this is acceptable.

---

## 4. Purchase-occasion contract assessment

### 4.1 Edge-case coverage (written specification §3–§6)

| Case | Specification handling | Assessment |
| --- | --- | --- |
| Positive merchandise on invoices also containing fees or adjustments | Only qualifying merchandise lines contribute eligibility, revenue and lineage | ✔. Real data has 2,028 occasion invoices that also carry shipping and 446 that carry embedded manual adjustments. |
| Merchandise returns | Excluded (quantity ≤ 0, and every return is on a cancellation invoice) | ✔. 0 occasion invoices contain any negative line. |
| Cancellation invoices | Excluded by the `C` prefix | ✔ in the specification. The oracle can be bypassed by `" C…"` or `"c…"` (§7). The real data has neither. |
| Zero-value merchandise rows | Excluded (price > 0 required) | ✔ |
| Missing customers | Excluded; never imputed | ✔ |
| Mixed-sign invoices | Only positive qualifying lines count | ✔ (none in real non-cancellation invoices) |
| Multiple merchandise lines per invoice | One occasion per customer × invoice; revenue is the exact sum; lineage is the sorted IDs | ✔ |
| Several invoices, one customer, same date | Primary: one occasion-day. Sensitivity: distinct invoices | ✔. Material: **2,900 customer-days** have more than one qualifying invoice. |
| Later-calendar-day repeat | Strictly later calendar date | ✔ |
| Invoice-level repeat sensitivity | Separately computed; never substituted | ✔ |
| Invalid dates / invoice IDs | Fail closed | ✔ in the specification. The oracle accepts `pd.NaT` and time-zone-aware dates (§7). |
| Multi-customer invoices | Integrity failure | ✔ in the specification; 0 in real data. The oracle checks eligible lines only (§7). |
| Inconsistent invoice dates | Fail closed | ✔; 0 in real data. 64 invoices have several timestamps on the same date, which is allowed. |

### 4.2 Separation from the `M` context set

**Confirmed.** The specification (§1, §4, §7) and the decision log forbid reuse, and no occasion code reads `merch_invoices`. The populations differ materially: the `M` context set has **46,921** invoices, and **10,327** of them are not purchase occasions (7,405 cancellation invoices, the rest unattributed-only).

Shipping, fees, commission, discounts, bad debt, samples, vouchers, tests, stock movements, all four manual categories and returns are each excluded by the category or sign predicate. The oracle test asserts this for every non-merchandise category.

### 4.3 Independent occasion baseline (a Stage B reference, not a Codex claim)

| Measure | Value |
| --- | ---: |
| Qualifying merchandise lines | 788,127 |
| Purchase occasions (customer × invoice) | **36,594** |
| Customers with ≥ 1 occasion | **5,852** |
| Gross occasion merchandise revenue | **GBP 17,123,740.997** |
| Identified customers with no occasion | 90 |
| Customers with a later-day repeat (any horizon) | 4,179 |
| Customers with an invoice-level repeat (any horizon) | 4,234 |

These match the revised-taxonomy predictions in the 002A review (5,852 / 36,594 / 17,123,740.997). Stage B should pin them.

### 4.4 Business definitions still open

1. **Acquisition-proxy look-back evidence (needs a contract decision; owner confirmation advised).** With the qualifying-occasion definition, 1,613 customers are first observed on or after 2010-12-01. **11 of them have identified, non-qualifying activity before that date** (returns, manual lines, postage and the like). They are known prior relationships, yet an occasion-only look-back would label them acquisition proxies. Recommendation: exclude any customer with **any identified source row** before the cutoff.
2. **Cancelled orders.** Occasions are gross and remain occasions even if later cancelled, because cancellations cannot be linked to their originals. This is defensible, but it must be documented as a limitation, with a customer-level net sensitivity where relevant.

---

## 5. Temporal-validity assessment

The specification §6 explicitly defers horizons, censoring, acquisition eligibility, cohorts, labels and models. The decision log approves the principles (D-002-07…11: 12-month proxy, half-open windows, date-level maturity, later-day occasions). The contract supports correct ordering (date, then invoice ID) and calendar-day occasion dates. These definitions are **not yet written as contract formulas** and must be fixed before Stage B produces cohorts or labels:

| Item | Required precision | Risk if left ambiguous |
| --- | --- | --- |
| `D_end` | Source maximum, 2011-12-09 12:50. Maturity is date-level: `occasion_date + h ≤ 2011-12-09`. | Partial final day counted as observed |
| 90-day repeat window | Date-level half-open: second occasion date `d₂` with `d₁ < d₂ < d₁ + 90`. The earlier evidence script used timestamps. | ±1-day boundary differences between engines. With my provisional rule, the 12-month proxy gives 1,017 mature, 411 repeaters (40.41%). |
| Acquisition cutoff | First qualifying occasion date ≥ 2010-12-01 (= `D_start` + 12 months), plus §4.4 item 1 | Inconsistent cohorts and contamination |
| Observed vs true first purchase | The specification correctly says "first observed occasion". The proxy must carry `observed_lookback_days` and the pseudo-boundary disclosure. | False acquisition claims |
| Anchors and leakage | Anchor T normalised to midnight. Features use occasion dates **strictly before** T; labels use `[T, T + h)`. `active_window_complete` holds for T ≥ 2010-12-01. | Feature leakage; R3 splits incomparable |
| Customer vs invoice sensitivity | Defined for repeats; must be carried through every outcome field name | Silent substitution |

These are legitimately Stage B work. They do not invalidate Stage A, but **no cohort, label or model output may be accepted until they are written and tested** (§9 S-2).

---

## 6. Independent financial reconciliation

From raw CSV text with Decimal arithmetic, using my own predicates:

| Measure | Independent | Codex | Match |
| --- | ---: | ---: | :---: |
| Corrected-V2 rows | 1,044,848 | 1,044,848 | ✔ |
| Seed-classified rows | 1,042,714 | 1,042,714 | ✔ |
| Context-classified rows (731 row-context + 1,403 `M`) | 2,134 | 2,134 | ✔ |
| Unclassified rows | 0 | 0 | ✔ |
| Identifiable signed | 16,343,669.038 | 16,343,669.038 | ✔ |
| Unattributed signed | 2,566,093.08 | 2,566,093.08 | ✔ |
| Overall signed | 18,909,762.118 | 18,909,762.118 | ✔ |
| O-5 cancellation-context `M` | 64 rows, −1,168.70, 52 invoices, 47 customers → `manual_adjustment` | Same | ✔ |

The full 14-category table matched exactly in the Milestone 1C review. The integration's frozen references are unchanged and still pass. No refund linkage or economic cause is inferred anywhere in code or specification.

---

## 7. Adversarial test results

### 7.1 Codex suite: what it does and does not establish

- **26 tests pass.** The integration and taxonomy tests are now strong: runtime pins, mutation fixtures, seed immutability and null semantics.
- **The contract tests (5) are weak.**
  - They exercise a test-only oracle only on synthetic rows. They never touch real data.
  - `test_primary_later_day_and_invoice_sensitivity` sorts an inline list inside the test rather than testing any function, so it checks no implementation.
  - The oracle diverges from the written contract (§7.2).

### 7.2 Oracle probes (`eligible_line` / `contract_occasion_rows`)

| Input | Contract requires | Oracle |
| --- | --- | --- |
| `InvoiceDate = pd.NaT` | reject | **accepted** (`isinstance(NaT, datetime)` is true) |
| `InvoiceDate = np.datetime64('NaT')`, `'2011-02-30'` | reject | rejected |
| Time-zone-aware date `…T23:30+05:00` | undefined | accepted; the date is taken from the string |
| `InvoiceNo = ' C500001'` / `'c500001'` | reject (cancellation) | **accepted** |
| `InvoiceNo = 'A563185'` | undefined (A = bad-debt adjustment) | accepted if categorised merchandise |
| `CustomerID = -5`, `0` | "canonical integer" (undefined) | accepted |
| `CustomerID = '1e3'`, `' 12345 '` | lossless canonical | **accepted**; `'1e3'` and `1000` collapse to one key |
| `CustomerID = True`, `pd.NA`, `NaN`, `'123.5'` | reject | rejected |
| `Quantity = 1.5` | source quantities are integers | **accepted** |
| `Quantity = True`; price `inf` / `NaN` | reject | rejected |
| Category `' merchandise'` / `'Merchandise'` | reject | rejected |
| Invoice with a second customer on **ineligible** lines | integrity failure | **not detected** (the check covers eligible lines only) |

None of these inputs occurs in the real data. I checked for lower-case or whitespace invoice IDs (0), non-integer customers (0), multi-customer invoices (0) and NaT (0). These are therefore **not data defects**. They are requirements for the Stage B producer, which must be stricter than this oracle.

---

## 8. Remaining scientific and engineering risks

| ID | Risk | Severity | Blocks Stage B start? |
| --- | --- | --- | --- |
| R-1 | Temporal formulas (windows, maturity, cutoff, anchors) not yet in the contract | High for cohorts and labels | No; must precede them |
| R-2 | Acquisition look-back ignores non-qualifying prior activity (11 / 1,613) | Medium | No; decide before the eligibility producer |
| R-3 | The test oracle is weaker than the specification (NaT, cancellation-prefix normalisation, customer canonicality, fractional quantity, multi-customer scope) | Medium | No; the producer must close it |
| R-4 | Fingerprints depend on pandas float parsing; they fail closed under environment drift | Low–medium (R6) | No |
| R-5 | Legacy `src/` loaders lack source identity | Medium if reused | No; prohibit reuse |
| R-6 | Gross occasions include orders later cancelled (no linkage) | Low; disclosure | No |
| R-7 | **Governance:** the decision-log O-5 paragraph, attributed to the owner's "yes", now contains Codex's later cancellation-context clarification, with no marker separating the two | Low–medium | No |
| R-8 | Weak-note codes: correctly reported as **20** rows, merchandise by seed, guard fails closed, not overstated; superseded values now carry inline **SUPERSEDED** markers | Closed | — |
| R-9 | Standalone manual credits: no cause or linkage asserted anywhere | Closed | — |
| R-10 | Stale `docs/recovery/__pycache__/` (21:27–21:33) | Cosmetic | No |

---

## 9. Required corrections

**None block the start of Stage B.** The following must be met within Stage B.

### Conditions for Stage B producers

| ID | Condition |
| --- | --- |
| **S-1** | The occasion producer's validation must implement the written contract exactly, with fixtures for every §7.2 case. Reject NaT and time-zone-aware timestamps. Apply the cancellation test after defined normalisation (reject leading or trailing whitespace and lower-case `c`). Customer IDs must be positive integers from a numeric source value: reject exponent and whitespace strings. Quantity must be an integer. The multi-customer check covers all identified rows of an invoice. The oracle must not be promoted to reference status. |
| **S-2** | Before any cohort, label or model output, add a temporal section to the contract: `D_end`; date-level half-open windows; the exact repeat boundary (`d₁ < d₂ < d₁ + h`); maturity (`d₁ + h ≤ 2011-12-09`); acquisition cutoff; anchor normalisation and the `< T` feature rule; `active_window_complete`. Provide boundary fixtures for each. |
| **S-3** | Decide and record the acquisition look-back evidence rule. Recommended: exclude customers with any identified source row before the cutoff. Report the 11-customer effect. Owner confirmation is advised. |
| **S-4** | Pin the independent occasion baseline (§4.3) as a Stage B frozen reference once the producer reproduces it. |
| **S-5** | Document that occasions are gross and unlinked to later cancellations. Provide a customer-level net-of-returns sensitivity where outcomes are value-based. |
| **S-6** | Mark the cancellation-context sentences in the O-5 decision-log entry as a dated clarification, separate from the owner-approved wording, or obtain explicit owner confirmation of the expanded text. |
| **S-7** | Stage B producers must ingest only through the identity-assigning loader (or an equivalent that passes the same assertions). `src/` loaders must not be reused for contract outputs. |
| **S-8** | For cross-engine (R6) work, derive Decimal prices from raw CSV text rather than floats, or pin the environment and record it in the run manifest. |

### Non-blocking improvements

- **N-1:** Replace the inline-list repeat test with a real function under test.
- **N-2:** Raise an explicit error when `source_row_number` is absent.
- **N-3:** Remove the stale `__pycache__`.
- **N-4:** The contract specification lives under the `002B` file name but governs DS-003. Consider a pointer from a DS-003 file name for discoverability.

---

## 10. Stage B go/no-go recommendation

**GO.** Stage A delivers what it claims:

- identity materialised at ingestion, with the exact overlap removal;
- runtime-enforced, independently reproduced fingerprints covering country, description, customer, date, category and lineage;
- exact financial and classification reconciliation;
- O-5 semantics recorded and preserved;
- a sound, strict purchase-occasion specification kept separate from the `M` context set.

Stage B may begin. Its occasion producer must meet S-1, S-4, S-5 and S-7. Its cohort, label and acquisition work must first satisfy S-2 and S-3. S-6 and S-8 should be completed alongside. This recommendation does not authorise models, Phase 3, or acceptance of any Stage B output before its own independent review.

---

## Reproduction record

Commands run from the repository root:

| Step | Command | Result |
| --- | --- | --- |
| 1 | `shasum -a 256 docs/recovery/COMMERCIAL_DS_002B_TAXONOMY_SEED.csv docs/recovery/COMMERCIAL_DS_003_STAGE_A_REFERENCE_PINS.json` | `7b4611c7…1e4e`; `a96d2e9d…ba49` |
| 2 | `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s docs/recovery -p 'test_COMMERCIAL_DS_00*.py' -v` | **Ran 26 tests — OK** |
| 3 | Hashes again | Both unchanged |
| 4 | `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python docs/recovery/COMMERCIAL_DS_002B_INTEGRATION.py > run{1,2}.json` | Both exit 0; **`2ffcbef73482a05572983019c535c12384fc2fcbf935bbc0a2581f7be695dd6b`**; `cmp` identical |
| 5 | Independent stdlib-csv reconstruction, oracle probes, real-data mutation probes | Session scratchpad, outside the repository |

**Working tree at review end:**

```text
## main...origin/main [ahead 1]
?? .vscode/
?? PROJECT_TECHNICAL_HANDOVER.md
?? docs/recovery/
```

- This review created exactly one repository file: this document.
- The seed, pins, raw sources and all Codex files have their pre-review hashes.
- Nothing was committed or pushed.

---

**COMMERCIAL-DS-003 STAGE A — INDEPENDENT REVIEW VERDICT**

**PASS WITH CONDITIONS.**

- **Source identity is correct.** It is assigned at ingestion. Exactly raw rows 502,938–525,460 are removed, leaving 1,044,848 unique and stable identities.
- **All four frozen fingerprints are correct.** They reproduce bit for bit from an independent stdlib-csv clean room, and they are enforced at run time against every mutation class tested.
- **Financial and classification totals reconcile exactly:** 16,343,669.038 / 2,566,093.08 / 18,909,762.118, and the 64-row O-5 cancellation context.
- **The purchase-occasion specification is scientifically sound.** It is strict, separate from the `M` context set, and independently yields 36,594 occasions and 5,852 customers.

**Stage B may begin.** Conditions, none of which blocks the start:

- The test oracle accepts NaT, normalisation-bypassed cancellation IDs, non-canonical customers and fractional quantities, so the Stage B producer must be stricter (S-1).
- The temporal formulas and the acquisition look-back rule must be written and tested before any cohort, label or model output (S-2 / S-3).
- The O-5 decision-log entry needs its owner-approved wording separated from the later clarification (S-6).
