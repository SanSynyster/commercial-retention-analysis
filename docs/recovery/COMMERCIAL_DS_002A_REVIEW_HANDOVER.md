# COMMERCIAL-DS-002A — Independent review handover

## Scope performed

This bounded task investigated the full V1/corrected-V2 stock-code inventory, closed numerical evidence gaps from the COMMERCIAL-DS-002 independent review, hardened the existing read-only evidence script, and documented DS-001 supersessions. It did not change application or pipeline code, production contracts, raw data, dependencies, models, reports, or the decision log. No owner approval is represented.

## Files inspected

Required, in order:

1. `docs/recovery/COMMERCIAL_DS_002_INDEPENDENT_REVIEW.md`
2. `docs/recovery/COMMERCIAL_DS_002_DATA_AUDIT.md`
3. `docs/recovery/COMMERCIAL_DS_002_DECISION_PROPOSAL.md`
4. `docs/recovery/COMMERCIAL_DS_002_ANALYSIS.py`
5. `docs/recovery/COMMERCIAL_DS_001_DATA_CONTRACTS.md`
6. `docs/recovery/COMMERCIAL_DS_001_DECISION_LOG.md`

Selectively inspected: DS-001 evaluation protocol, research programme, architecture, risk register, roadmap and agent handover; `Makefile`, CI workflow, existing tests and validation entry points; raw V1/V2 only through read-only parsers.

## Files changed or created

- Updated `docs/recovery/COMMERCIAL_DS_002_ANALYSIS.py` (existing evidence script only).
- Created `docs/recovery/COMMERCIAL_DS_002A_STOCK_CODE_INVENTORY.csv` (5,132 data rows plus header; no derived transaction dataset).
- Created `docs/recovery/COMMERCIAL_DS_002A_TAXONOMY_INVENTORY.md`.
- Created `docs/recovery/COMMERCIAL_DS_002A_EVIDENCE_ADDENDUM.md`.
- Created `docs/recovery/COMMERCIAL_DS_002A_SUPERSESSION.md`.
- Created this handover.

SHA-256 at handover: script `f4eb79406492c89fa9c64de57a22823df63b1166b7047f50aafd254f73adb01f`; inventory CSV `0d507be1e2b062705ba9763507342db71a24663b0d76176b31a2b39e4f66175b`.

## Reproduction commands

Run from the repository root:

```bash
git status --short --branch
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python docs/recovery/COMMERCIAL_DS_002_ANALYSIS.py > /tmp/commercial_ds_002a_evidence.json
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python docs/recovery/COMMERCIAL_DS_002_ANALYSIS.py > /tmp/commercial_ds_002a_evidence_rerun.json
cmp /tmp/commercial_ds_002a_evidence.json /tmp/commercial_ds_002a_evidence_rerun.json
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m src.docs_validation
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m src.synthetic_validation
```

The committed/reviewable CSV was mechanically projected from `stock_code_inventory` in the first JSON using Python `csv.DictWriter`, preserving JSON field order. Validation assertions: 5,132 rows and unique codes; source row-count sums 1,044,848 corrected V2 and 541,909 V1; 357 corrected-V2 rows proposed `unclassified`.

## Evidence and reproducibility notes

- Source SHA-256 is asserted before parsing: V1 `43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d`; V2 `32569a66f3842a82b0d8c4d63b263c5d98a76bde5d1f65c6c01bf457e541d3a9`.
- V2 physical data lines, exact block sizes/boundaries, one reset at zero-based row 525,461, overlap counts and corrected row count all fail closed.
- Overlap comparison uses `Counter` over full normalized source tuples, not 64-bit row hashes. Both 22,523-row copies equal V1 exactly; the full second block is V1 plus the asserted `POST` row.
- Financial bridges and per-code inventory revenue use `Decimal` created from source-number string representations. The 18 three-decimal-price rows and exact totals are asserted.
- Acquisition pseudo-boundary, active completeness, return-recency, same-day invoice, population and return-truncation results are generated and asserted.
- JSON is byte-identical across two complete runs. The script writes only stdout; repository output creation was a separate documented projection.

## Verification results

- Evidence script: PASS, twice; outputs byte-identical.
- CSV structural/reconciliation assertions: PASS.
- Unit tests: 14 run, 13 passed, 1 existing skip.
- Markdown link validation: PASS.
- Synthetic validation: PASS.
- Arrow emitted sandbox `sysctlbyname` cache-detection warnings; commands exited zero and results were unaffected.
- No `__pycache__` exists under `docs/recovery/`.

## Findings requiring independent verification

1. Recompute full-row multisets independently and confirm the source boundary, 22,523-row removal and exact extra `POST` row.
2. Recompute exact Decimal revenue bridges, especially the three-decimal `BANK CHARGES` contribution.
3. Independently sample the inventory’s 299 mixed-description codes. Confirm that whole-code exclusion would be unsafe and assess whether the description screen is over-inclusive.
4. Confirm that 351 codes / 357 corrected-V2 rows lack enough evidence and remain `unclassified`; do not silently resolve them.
5. Reproduce pseudo-boundary populations/rates, recency bands, active-window counts and ten complete/mature anchors.
6. Reproduce same-day figures and review the caveat that simple subtraction is a sensitivity, not the final later-calendar-day occasion algorithm.
7. Confirm product/current population bridge and exact returns-only/negative-net figures.
8. Verify the supersession cross-references and that no historical file or decision status was silently changed.

## Known uncertainties and owner gates

- The administrative-description regex is an evidence discovery aid. Its 299 mixed-description proposals are not an approved exception seed and may include false positives.
- `C3`, `GIFT`, 349 other unsupported codes and their 357 corrected-V2 rows remain unclassified.
- Category treatment for adjustments, tests, samples, discounts, gift vouchers, shipping, fees, bad debt and `PADS` needs owner approval.
- D-002-10 must choose invoice repeat versus later-calendar-day purchase occasion. The recommended primary is later-day occasion.
- The 12-month acquisition proxy needs mandatory lower-bound disclosure and late-cohort sensitivity; it never establishes first-ever acquisition.
- R3 needs a new evaluation split before pre-registration. No redesign was attempted here.
- Net-value treatment for returns-only and negative-net customers remains an R4 policy decision.

## Git status

At the pre-handover check:

```text
## main...origin/main [ahead 1]
?? .vscode/
?? PROJECT_TECHNICAL_HANDOVER.md
?? docs/recovery/
```

`git diff --stat` is empty because the recovery tree was already untracked. Existing uncommitted files were preserved. Nothing was committed or pushed.

## Reviewer completion criterion

Claude Code should issue a bounded PASS / PASS WITH CONDITIONS / FAIL for: (a) inventory completeness and financial columns; (b) fail-closed script controls; (c) all addendum figures; (d) the explicit supersessions; and (e) whether owner gates are complete enough to proceed to decision recording. Do not implement `contracts/business_definitions.yml`, change pipelines, or begin Phase 3 during this re-review.
