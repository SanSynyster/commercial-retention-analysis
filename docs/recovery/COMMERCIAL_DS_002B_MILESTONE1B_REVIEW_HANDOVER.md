# COMMERCIAL-DS-002B Milestone 1B — Independent Re-review Handover

**Purpose:** light independent re-review of the six corrections raised by Claude Code. Milestone 2 has not started.

## Six-blocker closure matrix

| Blocker | Status | Correction and evidence |
| --- | --- | --- |
| B-1 — destructive test harness | **Closed** | The taxonomy suite derives a seed only into a `TemporaryDirectory`; it validates the frozen authoritative seed instead of regenerating it in place. Tests compare generated, initial, and post-suite seed SHA-256 to `7b4611c78ca22d108c2616076c84b7c1db2efb8453ee9a32faceb027bb181e4e`. A corrupted temporary copy is rejected. Run tests with `PYTHONDONTWRITEBYTECODE=1`; no test writes to the checked seed. |
| B-2 — category-sensitive integrity | **Closed** | Runner validates seed SHA and versioned content, then checks frozen expected rows, positive, negative, signed, identified, and unattributed Decimals per category. Tests flip `85123A` to shipping and swap `85123A`/`POST`, preserving global row count and aggregate signed revenue; both fail seed validation. Full reference values are in the verification report. |
| B-3 — standalone M credits | **Pending owner decision; blocker remains open** | No semantic split was implemented. The review found standalone M credits of GBP −421,770.38 and 127/191 credit customers without standalone billing history. Existing approved O-5 covers positive standalone manual billing, not credit-note economics. The current output retains the prior category and reports gross positive/negative separately. Explicit approval is required for positive `standalone_manual_billing`, negative `standalone_manual_credit`, zero-value standalone treatment, and behavioral exclusion. |
| B-4 — report and decision reference | **Closed** | Verification addendum supersedes the old transcribed totals with identified GBP 16,343,669.038, unattributed GBP 2,566,093.08, and 93.0617818% seed coverage. The decision log now explicitly notes that its historical contract-specification reference is planned and not created; the approved owner instruction remains the source. No specification was fabricated. |
| B-5 — source-row and customer integrity | **Closed** | Every corrected row receives its original zero-based raw V2 `source_row_number`; identity uses pinned V2 SHA plus row number. Canonical length-prefixed JSON fingerprints cover source row, code, invoice, customer/null status, quantity, unit price, date and category. Customer fingerprints include per-customer counts, amounts and source-row identities. Row substitution, duplicate-for-deletion, invoice/customer reassignment, identified-to-null, and customer revenue reassignment fixtures all fail. Pinned row hash: `2f9f13c59fcb333a6fe9f3555735ff4d481443cef8f1d672bdfcdd902a0c6ca9`; customer hash: `248f421fbcacfaf1e63b3a5a69da78ec3097ce0cfa73c50f1e6ed733e4736d51`. |
| B-6 — null/customer semantics | **Closed** | Shared type-aware missing predicate is used for taxonomy context, customer identification, M customer counts, and integrity records. Fixtures cover `None`, `pd.NA`, `numpy.nan`, and Python NaN. Literal text descriptions resembling null tokens are retained as text. `M` invoice context requires explicit Python `bool` or NumPy boolean; missing, string and numeric flags raise. |

## Validation outcome

- Corrected V2: 1,044,848 rows, 0 unclassified, exact category row reconciliation.
- Identifiable signed amount GBP 16,343,669.038; unattributed signed amount GBP 2,566,093.08; all-row signed amount GBP 18,909,762.118.
- Merchandise positive GBP 19,699,671.127 and negative/returns GBP −719,677.94.
- Seed remained unchanged at SHA-256 `7b4611c78ca22d108c2616076c84b7c1db2efb8453ee9a32faceb027bb181e4e`.
- Test command: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s docs/recovery -p 'test_COMMERCIAL_DS_002B_*.py' -v` — **17 tests passed**.
- Integration command: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python docs/recovery/COMMERCIAL_DS_002B_INTEGRATION.py`.
- Two outputs saved outside the repository as `/tmp/COMMERCIAL_DS_002B_M1B_run1.json` and `...run2.json`; `cmp` passed. Both SHA-256: `99bdb765036b1c2bca7c1502b01c75ce49e8feec7a89531eaf567b6214501105`.
- Raw V1 SHA-256 `43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d`; raw V2 SHA-256 `32569a66f3842a82b0d8c4d63b263c5d98a76bde5d1f65c6c01bf457e541d3a9`; inventory SHA-256 `0d507be1e2b062705ba9763507342db71a24663b0d76176b31a2b39e4f66175b`.

## Additional scientific caveat: 11 weak-note merchandise mappings

The seed remains unchanged. Codes `15002`, `20852`, `22126`, `23059`, `35643`, `35956`, `72038B`, `72732`, `72759`, `DCGS0067`, and `DCGS0073` have 22 source rows total, descriptions consisting only of administrative/ambiguous notes, zero positive and negative line values, and zero identified customers. Their current rows are not evidence that future priced rows are merchandise. The mapping is preserved as reviewed historical seed evidence, but remains an open scientific caveat; no alternative category is asserted without evidence. Exact code counts and descriptions are in the verification report.

## M policy decision request

The new semantic policy is not approved in the decision log. The owner must explicitly approve or decline:

1. Positive standalone `M` → `standalone_manual_billing`.
2. Negative standalone `M` → `standalone_manual_credit`.
3. Zero-value standalone `M` → explicit category/treatment.
4. All standalone and embedded `M` excluded from merchandise behavior, with all commercial values retained in reconciliation.

Until then, the new category is not implemented and B-3 remains open. The current review output preserves historical classification while reporting standalone positive GBP 334,379.51, negative GBP −421,770.38, signed GBP −87,390.87 after the positive-merchandise-line context rule. The broader O-5-referenced identified positive M-only amount remains as documented in the independent review.

## Re-review instructions

From repository root, run the test command and integration command above with bytecode writing disabled. Confirm the seed SHA before and after tests, compare the two `/tmp` output files, inspect the full category reference and both integrity hashes, then independently mutate scratch copies for the category and row/customer fixtures. Review B-3 separately as an owner decision; do not treat this handover as approval or as authorization to begin Milestone 2.

## Milestone 1C supersession note

The earlier B-3 pending status above was accurate at the time of the Milestone 1B handover. The owner subsequently approved the O-5 amendment explicitly (“yes”) in the ChatGPT coordination conversation. B-3 is now closed by the implementation and evidence in `COMMERCIAL_DS_002B_MILESTONE1C_REVIEW_HANDOVER.md`. The row fingerprint changed because classification category is included; the customer fingerprint and all source financial totals are unchanged. The authoritative seed remains unchanged.
