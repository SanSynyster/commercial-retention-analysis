# B2B-3 Counts Gate: Lightweight Operational Policy

The owner replaced the earlier encrypted-volume and exhaustive backup/synchronisation proposals with proportionate local safeguards. This does not change the prior UNKNOWN backup/sync findings.

- Synthetic candidates use `.local/b2b3-gate-synthetic/`; real-data candidates, if separately authorized, use `.local/b2b3-gate-output/`. Both are Git-ignored and enforced as mode `0700`; files and temporary files use `0600` and atomic replacement.
- Real-data source loading requires an owner authorization record bound to the frozen schema, current producer SHA-256, approved local output root and expiry; the operator must also set `B2B3_REAL_DATA_AUTHORIZED=1` and explicitly choose `candidate-real` mode. The default is disabled.
- Candidate generation never marks independent reconstruction or privacy/transcript review complete. Finalization requires candidate-bound reconstruction sections, B2B-2 structural references, and a distinct human privacy review of generated logs and relevant agent transcripts.
- Automated checks validate only output schema/derivations and the program's fixed generic log lines. They cannot certify every terminal transcript or external agent session. The human review receipt is mandatory for finalization.
- Python bytecode is redirected to a fresh private temporary cache for tests; no existing cache directory is read or modified in this work.
- Logs and terminal output use fixed generic messages only. Exceptions are suppressed at the command boundary. Never expose customer-level records, identifiers, histories, raw rows, or data-bearing diagnostics in logs, prompts, tool output, reports, or transcripts.
- On suspected exposure, stop immediately, restrict access, do not copy or further inspect exposed material, preserve a minimal incident note without the data, and notify the owner. Do not continue until the owner directs containment.

These safeguards are proportionate to a local research implementation. Real-data execution was not authorized or performed here. Git ignore does not establish backup or synchronization exclusion. No commit, push, publication, or real-data run is authorized by this document.
