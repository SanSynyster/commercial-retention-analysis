# Research Status

**As of 2026-11-01**

| Workstream | Status | Evidence / next gate |
|---|---|---|
| Historical V1 analytics and engineering code | Existing exploratory implementation | See `notebooks/`, `src/`, `dbt/`, `reports/`; not all outputs have been re-audited in the corrected-V2 workstream |
| COMMERCIAL-DS-001 scope and decisions | Recorded | See the research programme, roadmap, and decision log under `docs/recovery/` |
| COMMERCIAL-DS-002B taxonomy and corrected-V2 integration | Completed and reviewed | Taxonomy, row context, frozen source references, and verification reports are retained under `docs/recovery/` |
| COMMERCIAL-DS-003 Stage A / B1 | Completed with review conditions | Contract, purchase-occasion builder, temporal rules, and review handovers are retained under `docs/recovery/` |
| COMMERCIAL-DS-003 Stage B2A | Independently reviewed with conditions | Revenue bridge and occasion reference values reproduced independently; see Stage B2A review |
| COMMERCIAL-DS-003 B2B-1 integrity correction | **Implementation complete; independent re-review pending** | Codex ran 50 tests and two byte-identical producer passes; Claude Code must review the closure handover before the next stage |
| Stage B2B downstream analysis | **Not started** | No cohorts, segmentation, retention models, or downstream modeling have been started in this workstream |

The 50-test run is author-side verification, not independent review. The B2B-1 correction does not change scientific classifications or frozen taxonomy values. See the [latest handover](recovery/COMMERCIAL_DS_003_STAGE_B2A_INTEGRITY_CLOSURE_HANDOVER.md).

## Interpretation boundary

The corrected-V2 signed source total includes all observed signed line values and is not a profit-and-loss statement. Qualifying gross merchandise includes only eligible positive merchandise lines and is not net sales. Customer-level measures exclude unattributed rows. Descriptive repeat counts are not rates unless their eligible and mature denominators are explicitly defined. No causal effect or acquisition status is inferred from these records.
