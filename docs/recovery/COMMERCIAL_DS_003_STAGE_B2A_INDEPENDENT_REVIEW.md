# COMMERCIAL-DS-003 Stage B2A — Independent Scientific and Engineering Review

**Reviewer:** Claude Code (independent of the implementation agent)<br>
**Review date:** 2026-11-01<br>
**Subject:** The Stage B2A production integrity boundary, revenue bridge and repeat-purchase diagnostics:
- [handover](COMMERCIAL_DS_003_STAGE_B2A_HANDOVER.md);
- [`COMMERCIAL_DS_003_PURCHASE_OCCASIONS.py`](COMMERCIAL_DS_003_PURCHASE_OCCASIONS.py) and [`COMMERCIAL_DS_003_REVENUE_BRIDGE.py`](COMMERCIAL_DS_003_REVENUE_BRIDGE.py);
- [B2A reference pins](COMMERCIAL_DS_003_STAGE_B2A_REFERENCE_PINS.json);
- contract specification [§9–§12](COMMERCIAL_DS_002B_CONTRACT_SPECIFICATION.md);
- the [decision log](COMMERCIAL_DS_001_DECISION_LOG.md) and `test_COMMERCIAL_DS_003_STAGE_B1.py`, which now also carries the B2A tests.

These were read against the [Stage B1 review](COMMERCIAL_DS_003_STAGE_B1_INDEPENDENT_REVIEW.md).

**Status:** Read-only review. No production code, raw data, seed, pin or evidence file was modified. All probes ran on scratch copies or in-memory objects. Nothing was committed or pushed.

---

## 1. Executive verdict: **PASS WITH CONDITIONS**

| Dimension | Verdict |
| --- | --- |
| **Revenue bridge** | **Exact.** An independent stdlib-csv / Decimal rebuild reproduces all **16 leaves**, matching every row count, positive / negative / signed / identifiable / unattributed amount and the full sorted source-row lineage. The leaves are disjoint and exhaustive (1,044,848 rows). Totals are GBP 18,909,762.118 = 16,343,669.038 + 2,566,093.08. |
| **Occasions** | Identical to the independent reconstruction (all 36,594, field by field) and pinned at run time by frozen occasion and lineage fingerprints. |
| **Repeat diagnostics** | **2,532 / 2,673 reproduced.** Same-day collapse, the `d₁+90` exclusion, order invariance and typed-timestamp rejection are all correct. The **denominator is all 5,852 customers with no maturity filter**, so these are descriptive counts, not rates (§4). |
| **Production boundary** | **Closed against accidental misuse.** Arbitrary DataFrames, in-place mutation, `dataclasses.replace` with a stale digest, report mutation, corrupted pins, and source mutations before load (customer, source ID, date, price, stock code) all fail before output. **Not closed against deliberate forgery through private names.** A frame altered in ways that leave qualifying occasions unchanged passes into the bridge and produces **wrong leaves** (§2). |
| **Acquisition proxy** | Diagnostics only (1,613 / 1,602 / 1,601); `primary_cohort_published: false`. Owner decision pending. |
| **Reproducibility** | 47/47 tests pass. Occasions `402090a0…`, bridge `016cf7a1…`, Stage A integration `2ffcbef7…`, each byte-identical across runs. Seed, Stage A pins and B2A pins are unchanged. |

**Stage B2B: GO**, provided condition **B2B-1** (bind the sealed frame to the frozen Stage A fingerprints, and pin the bridge leaves) is implemented **before any B2B producer consumes bridge leaves**. The other conditions can be met within B2B.

---

## 2. Production-boundary assessment

### 2.1 Design

The supported API is `load_validated_purchase_input()`. It runs the approved loader, then the overlap correction, frozen taxonomy and full Stage A pin validation, and mints a frozen `_ValidatedPurchaseInput`. That object holds the frame, the integrity report, a content digest (`hash_pandas_object`) and a module-private token.

`build_purchase_occasions()`, `build_real_data_report()` and `build_revenue_bridge()` accept only this object. Before use they re-check the token, revalidate the report against the Stage A pins and recompute the digest. Occasions are then checked against the B2A frozen summary and the occasion and lineage fingerprints.

`_build_purchase_occasions_for_test()` is the row-level core. Despite the name, production uses it internally, behind the boundary.

### 2.2 Probe results

| Attempt | Result |
| --- | --- |
| Arbitrary DataFrame into the occasion builder, real-data report or bridge | **Rejected** (`TypeError`) |
| In-place mutation of the sealed `_frame` (shipping → merchandise) | **Rejected** (digest mismatch) |
| `dataclasses.replace(_frame=…)` keeping the old digest | **Rejected** |
| Object minted with a foreign token | **Rejected** |
| `_integrity_report` mutated (row fingerprint) | **Rejected** (Stage A pin) |
| B2A pin file corrupted | **Rejected** (pin-file SHA) |
| Before load: customer ID, source-row swap, invoice date +1 day, price +0.01, `POST` row recoded as `85123A` | **All rejected** (Stage A row fingerprint / category references) |
| **Forged** object: shipping → merchandise, digest recomputed with private `_frame_content_digest` | Rejected, but only **downstream**, by the frozen occasion summary (790,273 ≠ 788,127 qualifying lines) |
| **Forged** object: every **fee** row relabelled **discount**, digest recomputed | **ACCEPTED by `build_revenue_bridge`.** The fees leaf disappears and discounts become GBP −269,882.379. |
| **Forged** object: 100 unattributed positive merchandise rows relabelled **shipping** | **ACCEPTED.** Shipping becomes GBP 435,314.23 and other positive merchandise GBP 2,575,211.41. |
| `object.__setattr__` on the frozen dataclass, same fee → discount change | **ACCEPTED** |
| Object constructed with the module's `_VALIDATION_TOKEN` | **ACCEPTED** |

**Root cause.** The content digest binds the sealed frame **only to itself**. `_validate_purchase_input` revalidates the *report* against the Stage A pins, but it never recomputes the Stage A row fingerprint (which includes category) from the *frame*. The bridge checks only global totals, and recategorisation preserves those. Occasion pins catch any change to qualifying lines; nothing catches changes confined to non-qualifying rows.

Every forgery needed deliberate use of underscore-private names (`_frame_content_digest`, `_VALIDATION_TOKEN`, `object.__setattr__`). Python cannot fully prevent that, so this is **not an accidental-misuse defect**. Still, the trusted bridge output can be silently wrong, which a frozen reference should prevent (§9, B2B-1).

---

## 3. Independent bridge reconstruction

Method:
- read raw `online_retail_II.csv` with the stdlib `csv` module, using string-to-`Decimal` amounts and raw row IDs;
- apply the 22,523-row overlap removal;
- apply my own taxonomy predicates with the frozen seed and inventory;
- apply my own leaf rules: zero amount → zero leaf; merchandise: negative → returns, eligible positive → qualifying, other positive → other; manual split by `M` vs other codes; one leaf per remaining category.

No Codex module was imported.

| Leaf | Rows | Signed (GBP) | Independent vs Codex (all 8 measures + lineage) |
| --- | ---: | ---: | :---: |
| Qualifying gross merchandise purchases | 788,127 | 17,123,740.997 | ✔ |
| Other positive merchandise activity | 226,881 | 2,575,930.13 | ✔ |
| Merchandise returns / cancellations | 17,973 | −719,677.94 | ✔ |
| Shipping / delivery income (non-zero) | 3,851 | 434,595.51 | ✔ |
| Standalone manual billing | 330 | 334,379.51 | ✔ |
| Standalone manual credits | 470 | −421,770.38 | ✔ |
| Embedded manual adjustments (`M`) | 596 | 4,455.30 | ✔ |
| Other manual adjustment codes | 70 | 7,566.29 | ✔ |
| Fees | 136 | −257,002.749 | ✔ |
| Commissions | 16 | −7,933.43 | ✔ |
| Bad debt | 6 | −147,614.08 | ✔ |
| Discounts | 173 | −12,879.63 | ✔ |
| Samples | 102 | −6,000.85 | ✔ |
| Gift vouchers (non-zero) | 79 | 1,769.94 | ✔ |
| Test entries (non-zero) | 14 | 203.5 | ✔ |
| Zero-value entries | 6,024 | 0 | ✔ |
| **Total** | **1,044,848** | **18,909,762.118** | ✔ (identifiable 16,343,669.038; unattributed 2,566,093.08) |

Further checks:

- **Zero-value subcategories:** merchandise 5,241; non-commercial stock movement 731; gift voucher 24; shipping 18; manual adjustment 5; test 3; standalone zero-value manual 2. All match.
- **Positive merchandise reconciliation:** GBP 19,699,671.127 total = 17,123,740.997 qualifying + 2,575,930.130 other. All **226,881** "other positive merchandise" rows are **unattributed**. None is excluded for any other reason, such as a cancellation or `A` invoice.
- **No misrepresentation:** 0 qualifying rows come from a non-merchandise category, have a non-positive amount, lack a customer, or sit on a `C` or `A` invoice. Returns, cancellations, shipping, standalone billing and credits, adjustments and fees each have their own leaf.
- **No double counting or dropped rows:** source-row lineage is disjoint and exhaustive, and every per-leaf identifiable + unattributed amount equals its signed amount.
- **Invoice grammar:** 0 violations in corrected V2 (1,025,677 numeric, 19,165 `C`, 6 `A`).
- **Not a profit-and-loss statement.** The bridge is observed signed transaction-line value only, with no cost, margin, cash or refund linkage. The code and specification §12 say so.

---

## 4. Repeat-purchase validation

### 4.1 Reproduction

Built from independently reconstructed occasions. These are identical to Codex's occasions: the 36,594-entry set matched exactly.

| Population | Denominator | Date-level repeat (primary) | Invoice-level (sensitivity) |
| --- | ---: | ---: | ---: |
| **All customers with ≥ 1 occasion (Codex diagnostic)** | **5,852** | **2,532** ✔ | **2,673** ✔ |
| Mature subset (`d₁ + 90 ≤ 2011-12-09`) | 5,256 | 2,312 | 2,444 |

Rule as implemented and reproduced: `d₁` is the customer's **first observed** occasion date. A date-level repeat requires a distinct later date `d₂` with `d₁ < d₂ < d₁ + 90`. An invoice-level repeat requires any other invoice dated in `[d₁, d₁ + 90)`, measured from the lowest invoice ID on `d₁`.

### 4.2 Semantics verified

| Property | Result |
| --- | --- |
| Same-day multiple invoices are not a date-level repeat | ✔. 141 customers repeat **only** at invoice level, through same-day invoices. 0 repeat at date level but not invoice level. |
| Same-day later invoice counts only in the sensitivity | ✔ (synthetic: two same-day invoices → date 0, invoice 1) |
| Exactly `d₁ + 90` | ✔ excluded at both levels (synthetic). Real data: **52** customers have an occasion exactly on `d₁ + 90`, so the boundary is material. |
| Input order | ✔ invariant (Codex reversed-input test and my independent rebuild agree) |
| Missing, string or time-zone-aware timestamps | ✔ rejected by `summarize_repeat_purchases` |
| Feature leakage | Not applicable. The repeat summary is a full-window descriptive and feeds no features. `rows_before_anchor` uses strict `< T` and rejects non-midnight anchors ✔. |

### 4.3 Interpretation constraints (must accompany any use)

- **These are not rates and not cohort retention.** The 5,852-customer denominator includes **596 customers whose 90-day window is not fully observed**. Treating them as non-repeaters biases any ratio downwards.
- **4,239 of the 5,852 customers were first observed before 2010-12-01.** For them, `d₁` is the first observed occasion, not a first purchase. Their "repeat within 90 days of d₁" is a left-censored quantity.
- **Ordering caveat.** Invoice-level ordering uses **string** comparison of invoice IDs (`"100" < "99"`). That is harmless here, because every corrected-V2 invoice is six characters, but it should be numeric-aware or asserted fixed-width.

---

## 5. Adversarial test results

| Group | Probes | Outcome |
| --- | --- | --- |
| Production boundary (§2.2) | 14 | 10 rejected before output. **4 forgeries accepted**, all requiring private names. |
| Synthetic eligibility (Codex suite, re-verified by inspection) | Invalid customers (−5, 0, strings, exponent, fractional, > 2⁵³); duplicate or missing source IDs; mixed-sign invoices; invalid, NaT, tz-aware or string timestamps; `A` invoices; ineligible-row date conflicts; multi-customer invoices across categories | All **fail closed or are excluded with a reason**, as specified. Malformed records **fail** rather than disappear: missing timestamps and invoice IDs now raise. |
| Real-data mutations before load | Customer, source ID, invoice date, price, stock-code recode | All rejected |
| Category reassignment / row substitution / customer and invoice reassignment | Via the load path | All rejected (Stage A fingerprints) |
| Negative merchandise quantity; zero-value rows | — | Routed to the returns / zero leaves; never qualifying ✔ |
| Same-day invoices; exactly 90-day separation | Synthetic and real | ✔ (§4.2) |
| Temporal helpers | tz-aware, missing, string, non-midnight anchor | All rejected ✔ |

---

## 6. Reproducibility evidence

Commands run from the repository root:

| Step | Command | Result |
| --- | --- | --- |
| 1 | `shasum -a 256` of seed, Stage A pins and B2A pins | `7b4611c7…`, `a96d2e9d…`, `4cf7b761…` |
| 2 | `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s docs/recovery -p 'test_COMMERCIAL_DS_*.py' -v` | **Ran 47 tests in 167.7 s — OK** |
| 3 | `… COMMERCIAL_DS_003_PURCHASE_OCCASIONS.py > occ{1,2}.json` | Both **`402090a0eea8abd02d4d72b5c12301fa51334c925f19840c9a639282d61e2109`**; `cmp` identical |
| 4 | `… COMMERCIAL_DS_003_REVENUE_BRIDGE.py > br{1,2}.json` | Both **`016cf7a18dbea9c8018ddd4c85e2b2b5ce4a049580decf533d198fbad8d1fa1a`**; `cmp` identical |
| 5 | `… COMMERCIAL_DS_002B_INTEGRATION.py \| shasum -a 256` | `2ffcbef73482a05572983019c535c12384fc2fcbf935bbc0a2581f7be695dd6b` |
| 6 | All three pin and seed hashes after runs | Unchanged |

Matching hashes were not treated as evidence of correctness. Correctness rests on the leaf-by-leaf, lineage-level and occasion-level independent reconstruction.

---

## 7. Scientific limitations

- **The bridge is a signed line-value reconciliation**, not a P&L. There is no cost, margin, cash or refund linkage.
- **Gross occasions are never linked** to later cancellations.
- **GBP 2.58m of positive merchandise (226,881 lines) is unattributed** and cannot enter any customer-level metric. Customer-value descriptives cover identifiable revenue only.
- **Repeat diagnostics** are left-censored for 4,239 customers and right-censored for 596 (§4.3).
- **The taxonomy is static full-period metadata**, and the fingerprints are coupled to the environment through pandas parsing. They fail closed under drift.
- **The boundary is a convention-level seal**, not a security boundary. Forgery through private names is possible (§2).

---

## 8. Remaining owner decisions

| Decision | Options (diagnostic counts) | Reviewer assessment |
| --- | --- | --- |
| **Primary acquisition-proxy rule** | Merchandise-only 1,613; exclude identified activity before 2010-12-01: 1,602; **exclude identified activity of any category before the customer's first qualifying occasion: 1,601** | The conservative rule (1,601) is **scientifically defensible**. Any identified row, including a return, credit, manual billing, postage line or test-line cancellation on that customer's account, is evidence of a pre-existing relationship. Counting the single test-line cancellation errs towards excluding a possibly returning customer, which is the safer error for an acquisition proxy. **Not approved; owner decision required.** |
| Test-line activity as evidence | Count (affects 1 customer) or ignore | Recommend count |

No other owner decision is pending for Stage B2B. The decision log §3B item 8 records the open acquisition choice.

---

## 9. Stage B2B go/no-go recommendation

**GO**, with these conditions:

| ID | Condition | Timing |
| --- | --- | --- |
| **B2B-1** | **Bind the sealed frame to the frozen references.** In `_validate_purchase_input`, recompute the Stage A row (category-sensitive) and source-content fingerprints from the frame, or freeze the frame digest in the B2A pin file. Also add **frozen per-leaf bridge references** (rows; positive / negative / signed / identifiable / unattributed; lineage fingerprint) checked at run time. Add tests in which forged objects (recomputed digest, `object.__setattr__`) are rejected. | **Before any B2B producer consumes bridge leaves** |
| **B2B-2** | **Repeat metrics.** Report the population, the denominator and maturity explicitly. Use the mature-subset denominator (5,256) for any rate. Flag left-censored first-observed customers. Never present the full-window counts as retention or cohort rates. | Within B2B |
| **B2B-3** | **Calendar cohorts.** Build on the point-in-time helpers. Cohort membership and features use only `< T`. Cells beyond maturity are null, not zero. Cohorts are labelled "first observed", never "acquired", until the owner decides §8. | Within B2B |
| **B2B-4** | **Segmentation and customer value.** Use identifiable qualifying gross (primary) with net sensitivity. Disclose the unattributed GBP 2.58m and the gross-not-net-of-cancellations limitation. | Within B2B |
| **B2B-5** | **Invoice-ordering hygiene.** Make the comparison numeric-aware or assert fixed-width IDs. Rename `_build_purchase_occasions_for_test`, which is the production core, to avoid misleading future readers. | Within B2B |

Stage B2B may implement:
- customer repeat-purchase summaries;
- calendar-day retention cohorts on the **first-observed** basis;
- non-acquisition commercial segmentation;
- revenue and customer-value descriptives.

No primary acquisition-proxy cohort and no modelling are authorised. Each B2B output requires its own independent review.

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

**COMMERCIAL-DS-003 STAGE B2A — INDEPENDENT REVIEW VERDICT**

**PASS WITH CONDITIONS.**

- **The revenue bridge is exact.** All 16 leaves reproduce independently, including full source-row lineage. They are disjoint and exhaustive over 1,044,848 rows, with totals GBP 18,909,762.118 = 16,343,669.038 + 2,566,093.08. Qualifying purchases (GBP 17,123,740.997) plus other unattributed positive merchandise (GBP 2,575,930.130) equal total positive merchandise (GBP 19,699,671.127).
- **Occasions and repeat diagnostics reproduce.** There are 36,594 occasions; date-level repeats are 2,532 and invoice-level 2,673, over **all 5,852 customers with no maturity filter**. Same-day handling, the `d₁+90` exclusion, order invariance and timestamp validation are correct.
- **The production boundary rejects all accidental misuse** and every source mutation before output. It does **not** bind the sealed frame to the frozen Stage A fingerprints. Deliberate forgeries through private names that leave qualifying occasions unchanged therefore yield **wrong but accepted bridge leaves**.
- **Owner decision:** the acquisition proxy remains diagnostic (1,613 / 1,602 / 1,601) and unapproved.

**Stage B2B may begin.** B2B-1 (frame-to-fingerprint binding plus frozen bridge-leaf references) must be implemented before any B2B producer consumes bridge leaves.
