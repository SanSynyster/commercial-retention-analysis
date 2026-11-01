# Commercial Data Science Research Evidence

This directory preserves source audits, owner decisions, taxonomy evidence, contracts, test suites, frozen references, verification results, and independent reviews. Historical reports retain their original conclusions and are not overwritten by later corrections; later handovers identify superseded values where applicable.

## Current status

**COMMERCIAL-DS-003 B2B-1 implementation complete; independent re-review pending.** Stage B2B downstream analysis has not started. The latest correction closes a validated-object integrity gap and adds frozen bridge category references.

## Reading path

| Order | Evidence | Purpose |
|---:|---|---|
| 1 | [COMMERCIAL-DS-001 decision log](COMMERCIAL_DS_001_DECISION_LOG.md) | Approved policies, open owner choices, and decision provenance |
| 2 | [COMMERCIAL-DS-002 source audit](COMMERCIAL_DS_002_DATA_AUDIT.md) and [independent review](COMMERCIAL_DS_002_INDEPENDENT_REVIEW.md) | Initial data investigation and review findings |
| 3 | [COMMERCIAL-DS-002A inventory](COMMERCIAL_DS_002A_STOCK_CODE_INVENTORY.csv), [audit addendum](COMMERCIAL_DS_002A_EVIDENCE_ADDENDUM.md), and [independent review](COMMERCIAL_DS_002A_INDEPENDENT_REVIEW.md) | Stock-code evidence and row-context findings |
| 4 | [COMMERCIAL-DS-002B verification](COMMERCIAL_DS_002B_MILESTONE1_VERIFICATION.md), [contract](COMMERCIAL_DS_002B_CONTRACT_SPECIFICATION.md), and [independent reviews](COMMERCIAL_DS_002B_MILESTONE1_INDEPENDENT_REVIEW.md) | Taxonomy, owner decisions, source integrity, and category corrections |
| 5 | [COMMERCIAL-DS-003 Stage A handover](COMMERCIAL_DS_003_STAGE_A_HANDOVER.md) and [contract specification](COMMERCIAL_DS_002B_CONTRACT_SPECIFICATION.md) | Source-row identity and purchase-occasion contract |
| 6 | [Stage B1 handover](COMMERCIAL_DS_003_STAGE_B1_HANDOVER.md) and [independent review](COMMERCIAL_DS_003_STAGE_B1_INDEPENDENT_REVIEW.md) | Occasion builder, temporal rules, and reviewed reference values |
| 7 | [Stage B2A handover](COMMERCIAL_DS_003_STAGE_B2A_HANDOVER.md) and [independent review](COMMERCIAL_DS_003_STAGE_B2A_INDEPENDENT_REVIEW.md) | Revenue bridge and independent scientific review |
| 8 | [B2B-1 integrity closure handover](COMMERCIAL_DS_003_STAGE_B2A_INTEGRITY_CLOSURE_HANDOVER.md) and [frozen bridge references](COMMERCIAL_DS_003_STAGE_B2A_BRIDGE_REFERENCE_PINS.json) | Latest correction, adversarial validation, category pins, and pending review |

## Evidence interpretation

- Independent reviews are attributed to the reviewer and preserve their original verdicts.
- Codex execution reports describe implementation-side verification and are not independent approval.
- `*_REFERENCE_PINS.json` files are frozen inputs to runtime checks. Normal validation does not regenerate them.
- Some early audit values were superseded by later source corrections or taxonomy decisions. Use the latest handover for current accepted values and retain the earlier reports for audit history.

## Historical model interpretation

- [Legacy model metric note](COMMERCIAL_DS_001_LEGACY_MODEL_METRIC_NOTE.md): records the unresolved V1 lapse metric discrepancy and the negative propensity finding; neither is corrected-V2 performance evidence.
