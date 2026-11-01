# COMMERCIAL-DS-002A — Supersession addendum

**Status:** documentary clarification based on verified evidence. It does not edit historical COMMERCIAL-DS-001 records and does not record owner approval.

COMMERCIAL-DS-001 remains useful design history, but the following wording must not be implemented as the current contract. Approval remains with the owner and should be recorded in the decision log after independent re-review.

| Historical location / assumption | Superseding evidence and proposed interpretation | Status |
| --- | --- | --- |
| `COMMERCIAL_DS_001_RISK_REGISTER.md` R-18 and `COMMERCIAL_DS_001_AGENT_HANDOVER.md`: “22,844 exact duplicates” | **22,844 is a diagnostic duplicate count in raw V2, not the source defect removal count.** The physical defect is one exactly repeated **22,523-row** source block for 1–9 Dec 2010. | Verified evidence; wording superseded |
| `COMMERCIAL_DS_001_DECISION_LOG.md` P-01 and architecture: “V2 (deduplicated)” | Canonical candidate is **overlap-corrected V2 (`v2c`)**, constructed by excluding the first physical overlap copy and retaining the second source block. Do not globally call `drop_duplicates`; corrected V2 still contains 11,812 diagnostic repeats that may be legitimate. | Recommended; owner approval outstanding |
| `COMMERCIAL_DS_001_DATA_CONTRACTS.md` `transaction_lines`: hash of source fields plus occurrence index | Proposed identity is `(source_sha256, source_row_number)`, where row number is zero-based data-row position excluding the header, assigned once at raw ingestion and materialised. V1 is a separate identity space; cross-source comparison is by full-row multiset. A byte-level re-export intentionally changes the identity namespace. | Recommended; owner approval outstanding |
| `C-ACQ`, `C-FIRST`, `customers.acquisition_known` and statements allowing “first purchase” when the flag is true | The source can establish **first observed purchase** and **first observed purchase after a qualifying observed look-back**, never first-ever purchase. Replace `acquisition_known` with explicit proxy fields such as `acquisition_proxy_eligible`, `observed_lookback_days` and policy version. Do not label a customer genuinely acquired. | Verified limitation; field naming superseded |
| P-17 / `C-ACTIVE`: 365-day window without completeness condition | Retain `[T−365d,T)` only with `active_window_complete = (T ≥ 2010-12-01)` for this source. Canonical snapshots use complete windows unless a study pre-registers a truncation sensitivity. Forward-return evidence, not observed-gap coverage, is the justification. | Recommended condition; owner approval outstanding |
| `COMMERCIAL_DS_001_RESEARCH_PROGRAMME.md`: 16 monthly R3 anchors from 2010-06; `COMMERCIAL_DS_001_EVALUATION_PROTOCOL.md`: development 2010-06-01…2011-04-01 | Six development anchors have truncated 365-day histories. Only ten month-start anchors are both history-complete and 90-day mature (2010-12-01…2011-09-01). **The reference R3 evaluation split is superseded and must be redesigned at pre-registration.** | Verified conflict; redesign required |
| Implicit timestamp-level maturity used by the original evidence script | Use date-level maturity: `date(anchor or first_observed)+h ≤ date(D_end)`. For the 12-month acquisition proxy and h=60, the mature count is 1,258 rather than 1,252. | Recommended D-002-11; approval outstanding |
| Product/non-product list in DS-002 proposal, itself based on DS-001 structure | The list is incomplete and fail-open. Use the COMMERCIAL-DS-002A full inventory, exact description exceptions, explicit mapping and `unclassified` default that fails validation. | Revised evidence; mapping blocked on owner/steward review |

## Implementation guardrails for the future contract task

- A corrected source block is not a globally deduplicated transaction table.
- Full-row equality is an evidence comparison, not line identity.
- `source_row_number` must never be recomputed from Spark partition order or a downstream sort.
- No canonical field may be named `acquisition_known`; no report may claim first-ever acquisition from these sources.
- Snapshot completeness and label maturity are separate fields and both must be true for canonical R3 anchors.
- Repeat invoice and repeat purchase occasion are separate concepts pending D-002-10.
- Historical documents are not silently rewritten. This addendum is the reviewable bridge until decisions are explicitly recorded.

## Approval boundary

This addendum establishes what the evidence contradicts. It does not mark P-01/P-01b, P-09, P-17, D-002-10, D-002-11, the taxonomy mapping, or the revised R3 split as approved. Phase 3 and production contract encoding remain unauthorised.
