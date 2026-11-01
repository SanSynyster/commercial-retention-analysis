# COMMERCIAL-DS-003 Stage B1 — Independent Scientific and Engineering Review

**Reviewer:** Claude Code (independent of the implementation agent)<br>
**Review date:** 2026-11-01<br>
**Subject:** The Stage B1 production purchase-occasion builder, the temporal contract and the acquisition diagnostics:
- [handover](COMMERCIAL_DS_003_STAGE_B1_HANDOVER.md);
- [`COMMERCIAL_DS_003_PURCHASE_OCCASIONS.py`](COMMERCIAL_DS_003_PURCHASE_OCCASIONS.py) and [`test_COMMERCIAL_DS_003_STAGE_B1.py`](test_COMMERCIAL_DS_003_STAGE_B1.py);
- contract specification [§9–§11](COMMERCIAL_DS_002B_CONTRACT_SPECIFICATION.md);
- the refactored [integration runner](COMMERCIAL_DS_002B_INTEGRATION.py) and the [decision log](COMMERCIAL_DS_001_DECISION_LOG.md).

These were read against the [Stage A review](COMMERCIAL_DS_003_STAGE_A_INDEPENDENT_REVIEW.md).

**Status:** Read-only review. No production code, raw data, seed, pin or evidence file was modified. All probes ran on scratch copies or in-memory frames. Nothing was committed or pushed.

---

## 1. Executive verdict: **PASS WITH CONDITIONS**

| Dimension | Verdict |
| --- | --- |
| **Occasion reconstruction** | **Exact, occasion by occasion.** An independent stdlib-csv / Decimal rebuild reproduces all 36,594 customer × invoice occasions with identical keys, dates, exact gross, line counts and sorted source-row lineage. The four exclusion-reason counts also match. |
| **Eligibility and grouping** | **Strict and correct on real data.** All Stage A oracle gaps are closed. Residual strictness gaps exist only for synthetic inputs (§3.3) and do not affect corrected V2. |
| **Temporal contract** | **Correct and leakage-safe as written:** half-open windows, a strict `< T` feature cutoff, `[T, T+90)` outcomes, `d₁ < d₂ < d₁+90`, and date-level maturity. Two inconsistencies remain: the acquisition look-back wording vs its implementation, and validation inside the utilities (§4). |
| **Source integrity** | **Enforced on the production path.** Country, description, customer, date, stock-code, price and row-deletion mutations are all rejected before any occasion is built. **One bypass exists:** the public `build_purchase_occasions()` accepts any frame and does no integrity validation (§5). |
| **Acquisition diagnostics** | **Reproduced** (1,613 / 11 / 1,602). The exclusion is scientifically justified. The best-supported rule ("any identified activity before the first qualifying occasion") gives **12 / 1,601**. **Owner decision pending; not treated as approved.** |
| **Reproducibility** | 40/40 tests pass. Builder output is `96590720…` (byte-identical ×2). The Stage A integration output is still `2ffcbef7…` after the refactor. Seed and pins are unchanged. |

**Stage B2: GO** for non-acquisition temporal work (revenue bridge, occasion-based repeat measurement, snapshot scaffolding), subject to the conditions in §9. Any primary acquisition-proxy cohort remains **gated on the owner decision**.

---

## 2. Independent occasion reconstruction

Method:
- read raw `online_retail_II.csv` with the stdlib `csv` module, using string-to-`Decimal` prices and raw zero-based row IDs;
- remove raw rows 502,938–525,460;
- apply my own classification predicates with the frozen seed and inventory;
- apply the contract line predicate, then group by customer × invoice.

No Codex module was imported.

| Measure | Independent | Codex builder | Match |
| --- | ---: | ---: | :---: |
| Qualifying merchandise lines | 788,127 | 788,127 | ✔ |
| Purchase occasions | 36,594 | 36,594 | ✔ |
| Distinct customers | 5,852 | 5,852 | ✔ |
| Qualifying gross merchandise | GBP 17,123,740.997 | GBP 17,123,740.997 | ✔ |
| Excluded: non-merchandise category | 6,626 | 6,626 | ✔ |
| Excluded: missing / non-positive customer | 226,881 | 226,881 | ✔ |
| Excluded: non-positive quantity | 20,789 | 20,789 | ✔ |
| Excluded: non-positive unit price | 2,425 | 2,425 | ✔ |
| Excluded total + qualifying | 256,721 + 788,127 = 1,044,848 | same | ✔ |

**Occasion-level comparison.** Both sets have 36,594 keys: 0 only in mine and 0 only in Codex's. **0 occasions differ** in date, exact gross (compared numerically), eligible-line count or sorted `source_row_numbers`.

Lineage is disjoint and covers exactly the 788,127 qualifying source rows. Output is sorted by (customer, date, invoice). The cancellation, invalid-timestamp, invalid-invoice and outside-window exclusions are all zero on corrected V2. Every cancellation line already fails the quantity predicate first.

---

## 3. Eligibility and grouping audit

### 3.1 Stage A oracle gaps (S-1): closed

| Stage A gap | Builder behaviour |
| --- | --- |
| `pd.NaT`, `np.datetime64('NaT')`, `None` dates | Excluded (`invalid_or_missing_timestamp`) |
| Time-zone-aware timestamps (UTC, Europe/London) | Excluded |
| `" C500001"`, `"500001 "`, NBSP-padded IDs | **Build fails** (`invalid invoice identifier`) |
| `"c500001"` | Excluded as cancellation (case-insensitive) |
| Customer `" 12345 "`, `"1e3"`, `True`, `12345.0000001`, `inf` | **Build fails** (no string parsing; integer and finite required) |
| Customer `-5`, `0` | Treated as missing and excluded (see §3.3) |
| Quantity `1.5` | Excluded (`non_integral_quantity`) |
| Quantity `"2"`, NaN; price NaN | **Build fails** on merchandise rows |
| Multi-customer invoice where one customer's lines are ineligible | **Build fails.** The check now spans all identified rows, including non-merchandise rows. |

### 3.2 Grouping and exclusion semantics

| Case | Result |
| --- | --- |
| Several eligible lines on one invoice | One occasion; exact Decimal sum; sorted lineage ✔ |
| Mixed-sign invoice | Only positive eligible lines count ✔ |
| Same customer, several invoices on one day | Distinct invoice-level occasions ✔. Real data: **2,900** customer-days with more than one invoice. Date-level collapse is the consumer's job; see §4. |
| Numeric encodings of one ID (`12345`, `12345.0`, `np.int64(12345)`, `Decimal('12345')`) | One canonical key, `"12345"` ✔. These are the same number, not ambiguous IDs. |
| Distinct customers silently merged | **Not possible.** Strings are never parsed, and non-integral or non-finite values fail. |
| Shipping, fees, commission, discounts, bad debt, samples, vouchers, tests, stock movements, all four manual categories, `"Merchandise"`, missing category | Excluded (`non_merchandise_category`) ✔ |
| Returns / zero-value merchandise | Excluded by quantity or price ✔ |
| Source ID missing / duplicate / float (`10.0`) / negative / boolean | **Build fails** ✔. `np.int64` accepted ✔. |
| Observation boundaries | `2009-12-01 00:00` included; `2009-11-30 23:59` excluded; `2011-12-09 12:50:00` included; `12:50:01` excluded ✔ |

### 3.3 Residual strictness gaps (synthetic inputs only; 0 occurrences in corrected V2)

| Probe | Behaviour | Concern |
| --- | --- | --- |
| Customer `-5` with `12345` on the **same** invoice | `-5` is treated as missing and **excluded from the multi-customer check**; one occasion is built | Non-positive IDs are malformed and should fail the build, not be silently dropped |
| Eligible line on date A and ineligible line on date B, same invoice | Accepted; the date check covers eligible lines only | Specification §5 says "all rows in one invoice must agree on the calendar date" |
| `A`-prefixed invoice (`A563185`) labelled merchandise | Accepted | `A` = source adjustment invoices. Real `A` rows are bad debt and never merchandise, but the grammar is unspecified. |
| String or `datetime.date` timestamps | Silently **excluded** with a reason count | A wrong column type would yield zero occasions without failing. The production run does not pin occasion counts at run time (§5). |
| Customer `1e20` (float) | Accepted as `"100000000000000000000"` | Floats above 2⁵³ cannot be lossless. Add an upper bound or require integer dtype. |

---

## 4. Temporal-contract findings

### 4.1 Boundary probes (utilities in the builder module)

| Rule | Probe | Result |
| --- | --- | --- |
| Feature window `[T−L, T)` | `T−1` ✔ in; `T` ✗; `T−L` ✔ in; `T−L−1` ✗; `23:59` on `T−1` ✔ in; `00:00` on `T` ✗ | Correct; no anchor-day leakage |
| Repeat `d₁ < d₂ < d₁+90` | `d₁` ✗; `d₁+1` ✔; `d₁+89` ✔; `d₁+90` ✗ | Correct. The later-day opportunity is 89 calendar days; label it so. |
| Maturity `T+90 ≤ 2011-12-09` | 2011-09-10 mature; 2011-09-11 immature | Correct and conservative (the partial final day is never inside an outcome window) |
| Acquisition cutoff | 2010-12-01 inclusive | Correct |
| Invoice-level sensitivity | Same-day distinct invoices count | Correct, but **symmetric**: `invoice_level_repeat(B, A)` and `(A, B)` are both true. The caller must order by (date, invoice ID) or double counting is possible. |

**Leakage assessment.** Features (`< T`) and outcomes (`[T, T+90)`) are disjoint. Anchor-day transactions are outcomes, never features. The outcome window never includes the partial final day. The contract therefore **supports future cohort analysis and R3 modelling without outcome leakage**, provided Stage B2 producers also follow two rules:
- (a) cohort or proxy membership used as a feature at T is computed only from data `< T`;
- (b) date-level repeat collapses same-day invoices **before** the window test.

### 4.2 Inconsistencies and ambiguities

1. **Acquisition look-back: specification vs implementation.**
   - Specification §9 defines the look-back as `[first_observed_occasion − 12 calendar months, first_observed_occasion)`.
   - The diagnostic instead counts identified activity strictly before the **fixed cutoff** 2010-12-01.
   - These differ (§6). No 12-month or calendar-month utility exists.
2. **The utilities do not validate their inputs.** `primary_later_day_repeat` and the related helpers accept time-zone-aware timestamps and strings via `pd.Timestamp(...).date()`. For example, a Tokyo-zoned `00:30` resolves to that zone's local date. The builder already excludes such rows, but Stage B2 code must pass only validated naive dates.
3. **Wording of `D_end_exclusive`.** The phrase "full final observed date is included" applies to feature windows only. Outcome maturity correctly treats 2011-12-09 as not available as a complete outcome day. One clarifying sentence would prevent misreading.
4. **Taxonomy look-ahead (informational).** The seed was derived from full-period descriptions, so it is static metadata built with hindsight. This is acceptable for classification and does not leak outcomes.

---

## 5. Source-integrity enforcement

**Production path:** `build_real_data_report()` → `build_report_and_classified_rows()` → `load_sources()` (identity at ingestion) → `source_block_evidence()` → `classify_corrected_rows()` → full report → `validate_reference_pins()` → `build_purchase_occasions()`. No `src/` loader is used.

The refactor keeps the Stage A output byte-identical: `2ffcbef7…`, run independently.

| Real-data mutation through `build_real_data_report()` | Result |
| --- | --- |
| Country changed | **Rejected** (row fingerprint) |
| Description changed | **Rejected** (source-content fingerprint) |
| Invoice reassigned to another customer | **Rejected** (row fingerprint) |
| Date +1 day | **Rejected** (row fingerprint) |
| Stock code changed to another merchandise code (same category) | **Rejected** (row fingerprint) |
| Price +0.01 | **Rejected** (category Decimal reference) |
| One row dropped | **Rejected** (corrected row count) |
| Seed / pin corruption | Rejected by seed SHA and pin-file SHA. Inherited from Stage A and re-verified there; the code path is unchanged. |

**Bypass.** `build_purchase_occasions(frame)` is a public function with **no** integrity validation. In a probe I took the validated classified frame, relabelled every `shipping` row as `merchandise`, and called the builder directly. It accepted the frame and returned **36,711 occasions and GBP 17,274,041.397** without error. `classify_corrected_rows()` is similarly callable on an unvalidated frame; it checks the seed SHA but no fingerprints.

The production entry point is safe, but nothing prevents a Stage B2 producer from calling the unvalidated function. Condition B2-1 addresses this.

**No runtime occasion pin.** Expected occasion values (788,127 / 36,594 / 5,852 / 17,123,740.997) exist only in tests. Stage A condition S-4 asked for a frozen Stage B reference. `build_real_data_report()` does not check occasion outputs against frozen values at run time.

---

## 6. Acquisition-proxy diagnostics

Independent reconstruction:

| Rule | Candidates with prior identified activity | Adjusted count |
| --- | ---: | ---: |
| Merchandise-only first occasion ≥ 2010-12-01 (sensitivity) | — | **1,613** ✔ |
| Prior activity strictly before **2010-12-01** (Codex diagnostic) | **11** ✔ | **1,602** ✔ |
| Prior activity strictly before the customer's **first qualifying occasion** (any date) | **12** | **1,601** |
| Prior activity within `[first − 12 months, first)` (literal specification §9 wording) | 7 | (not recommended) |

**What the prior activity is.** Pre-cutoff rows for the 11 customers:

| Row type | Rows |
| --- | ---: |
| Merchandise returns / cancellations | 30 |
| Standalone manual credits (cancellation invoices) | 3 |
| Standalone manual billing | 2 |
| Embedded manual adjustment | 1 |
| Shipping-only line | 1 |
| Test cancellation | 1 |

The extra customer under the first-occasion rule has merchandise returns dated between the cutoff and their first qualifying purchase. **For 10 of the 12 customers, the first identified row is a return**, which strongly implies an earlier, unobserved purchase.

**Scientific assessment.**
- **The exclusion is justified.** A return, credit, manual billing or postage line by an identified customer is direct evidence of a prior commercial relationship. "No observed prior activity of any kind" is a strictly better proxy for observed acquisition than "no prior qualifying merchandise".
- **The recommended primary rule is "any identified source row, any category, before the customer's first qualifying occasion" (12 / 1,601).** The fixed-cutoff rule misses activity that falls between the cutoff and the first purchase. The literal 12-month-window rule misses 5 customers whose prior activity is older than 12 months, which contradicts the purpose of a look-back.
- **One edge case for the owner.** One customer's only prior row is a test-line cancellation. Test lines were excluded from all reporting under O-8, so the owner may choose whether test activity counts as evidence. Recommendation: count it, conservatively.
- **Unattributed pre-cutoff activity** cannot be linked to customers and cannot affect the definition. Neither can the left-censoring before 2009-12-01. The pseudo-boundary disclosure (lower bound 3–14% at a 12-month look-back) remains mandatory and dwarfs this 0.7% adjustment.

**Status:** **PENDING OWNER DECISION.** The builder correctly emits only diagnostics, with `primary_cohort_published: false`. This review does not treat the exclusion as approved.

---

## 7. Adversarial test results

### 7.1 Codex suite

There are 40 tests: 26 existing plus 14 Stage B1. The Stage B1 tests are substantive. They exercise the real builder function and include a real-data reconciliation. Two limitations:

- The real-data expected values are asserted in tests only, not at run time (§5).
- `test_temporal_boundaries` covers the utility functions, but nothing yet consumes them on real occasions. That is legitimately Stage B2 work.

### 7.2 Reviewer probes

| Probe group | Count | Rejected or correctly excluded | Gaps |
| --- | ---: | ---: | --- |
| Builder synthetic edge cases | 31 | 26 | Non-positive customer in the multi-customer check; ineligible-line date mismatch; `A` invoices; silent exclusion of string/date-type timestamps; float customer > 2⁵³ |
| Temporal utilities | 8 | 6 | Accepts tz-aware/string inputs; invoice-level repeat is symmetric |
| Real-data integrity mutations | 7 | 7 | — |
| Direct builder bypass | 1 | 0 | Unvalidated frame accepted |

The occasion-level reconstruction (§2) is the decisive correctness evidence. Aggregate matches alone were not relied on.

---

## 8. Reproducibility evidence

Commands run from the repository root:

| Step | Command | Result |
| --- | --- | --- |
| 1 | `shasum -a 256` of seed and Stage A pins | `7b4611c7…`, `a96d2e9d…` |
| 2 | `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s docs/recovery -p 'test_COMMERCIAL_DS_*.py' -v` | **Ran 40 tests in 133.1 s — OK** |
| 3 | `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python docs/recovery/COMMERCIAL_DS_003_PURCHASE_OCCASIONS.py > run{1,2}.json` | Both exit 0; **`965907203f40858168000fc045048e52229a1f754279ee6fc1f291acc826ff86`**; `cmp` identical |
| 4 | `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python docs/recovery/COMMERCIAL_DS_002B_INTEGRATION.py \| shasum -a 256` | `2ffcbef7…` (unchanged by refactor) |
| 5 | Seed and pin hashes after all runs | Unchanged |
| 6 | Independent rebuild and probes | Session scratchpad, outside the repository |

**Hygiene note.** `docs/recovery/__pycache__/` gained new `.pyc` files timestamped 23:32:43, including for the Stage B1 builder and test. Some Codex run therefore executed without `PYTHONDONTWRITEBYTECODE=1`, despite the handover's statement. This is harmless, but it should be cleaned up.

---

## 9. Remaining conditions

### Blocking defects for Stage B2

**None.**

### Conditions to implement in Stage B2

| ID | Condition |
| --- | --- |
| **B2-1** | **Close the builder bypass.** Every Stage B2 producer must obtain occasions only through the validated entry point. Either make the frame-level builder private, or have it check a fingerprint (row / customer pins) of the classified input before building. Add a test showing that a relabelled frame is rejected. |
| **B2-2** | **Runtime occasion reference.** Freeze an occasion-level fingerprint (customer, invoice, date, exact gross, sorted lineage) plus summary counts. Validate them in `build_real_data_report()` and in every downstream producer, not only in tests. |
| **B2-3** | **Date-level repeat construction.** Collapse same-day invoices into one purchase day **before** applying `d₁ < d₂ < d₁+h`. Order by (date, invoice ID) for the invoice-level sensitivity, so the symmetric utility cannot double count. Name metrics explicitly (date-level / invoice-level; 89-day later-day opportunity within a 90-day window). |
| **B2-4** | **Validated temporal inputs.** Temporal utilities must reject time-zone-aware timestamps, strings and NaT rather than coerce them. |
| **B2-5** | **Point-in-time membership.** Any cohort, proxy or tenure feature at anchor T is computed from data `< T` only. Add a truncation test. |
| **B2-6** | **Residual strictness.** Treat non-positive customer IDs as malformed (fail) and include them in the multi-customer check. Enforce single-date across **all** rows of an invoice, per specification §5. Decide the `A`-invoice grammar. Fail (do not exclude) on wrong-typed timestamp columns. Bound numeric customer IDs. |
| **B2-7** | **Specification consistency.** Align specification §9's acquisition look-back wording with the rule the owner approves (§6). Add the `D_end_exclusive` clarification (§4.2-3). |

### Non-blocking limitations

- Gross occasions include orders later cancelled; no linkage is possible (S-5 disclosure still applies).
- Left-censoring before 2009-12-01 and unattributed activity limit any acquisition proxy.
- 2,900 same-day multi-invoice customer-days make the date-level / invoice-level distinction material.
- Fingerprints are environment-coupled through pandas float parsing (fail closed). Raw-text Decimal parsing is advised for R6.
- Stale bytecode in `docs/recovery/__pycache__/`.

### Owner decisions pending

| Decision | Options | Recommendation |
| --- | --- | --- |
| **Acquisition-proxy primary rule** | (a) Merchandise-only first occasion (1,613); (b) exclude identified activity before the cutoff (1,602); **(c) exclude identified activity of any category before the customer's first qualifying occasion (1,601)** | **(c)**; record the merchandise-only figure as a sensitivity |
| Do test-line rows count as prior-relationship evidence? | count / ignore (affects 1 customer) | Count (conservative) |

---

## 10. Stage B2 go/no-go recommendation

**GO.** Stage B1 delivers a correct, strict and reproducible purchase-occasion builder. It is verified **occasion by occasion** against an independent reconstruction, protected on its production path by the Stage A runtime pins, and supported by a leakage-safe temporal contract.

Stage B2 may begin the revenue bridge, occasion-based repeat measurement and snapshot scaffolding, implementing B2-1 to B2-7 as it goes. **No primary acquisition-proxy cohort** may be published until the owner records the §6 decision. Any Stage B2 output requires its own independent review before acceptance. This recommendation does not authorise modelling or Phase 3.

---

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

**COMMERCIAL-DS-003 STAGE B1 — INDEPENDENT REVIEW VERDICT**

**PASS WITH CONDITIONS.**

- **Occasions are correct.** The production builder reproduces all 36,594 occasions **field by field** against an independent rebuild: keys, dates, exact gross, line counts and source-row lineage. Totals are 788,127 lines, 5,852 customers and GBP 17,123,740.997, with identical exclusion counts.
- **The production path is integrity-protected.** Every tested mutation is rejected.
- **The temporal contract is leakage-safe** at all tested boundaries.
- **The 1,613 / 11 / 1,602 acquisition diagnostics reproduce.** The best-supported primary rule gives 1,601, but this is an **owner decision still pending**.

**Stage B2 may begin**, under these conditions:

- close the unvalidated `build_purchase_occasions()` path and add a runtime occasion pin (B2-1 / B2-2);
- build date-level repeats by collapsing same-day invoices first (B2-3);
- validate inputs to the temporal utilities, and compute cohort membership from point-in-time data (B2-4 / B2-5);
- tighten the residual strictness gaps and align the specification (B2-6 / B2-7).

No acquisition-proxy cohort may be published before the owner's decision.
