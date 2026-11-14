# B2B-3 Primary Outcome Candidate — Controlled Local CLI

## Scope

The CLI creates one private candidate for primary monthly 30/60/90-day date-level repeat outcomes. It does not publish, finalize, push, or automatically retry. Real data loading is reachable only through `--mode candidate-real`, an unexpired run-specific owner authorization file, and the one-command environment opt-in `B2B3_OUTCOME_REAL_DATA_AUTHORIZED=1`.

The authorization must be separately created by the owner after focused review. Codex must not create it on the owner's behalf. The record is bound to the exact outcome producer bytes, run ID, verified final counts-gate SHA-256, approved scope, and private output root. The same run ID is consumed before source loading begins; a failed or completed run cannot be retried. Candidate metadata and the private run context also capture the frozen source-pin hashes and the actual Python and pandas versions used.

## Owner authorization JSON

The file must be canonical UTF-8 JSON with exactly these fields (no additions or omissions), mode `0600`, inside a directory of mode `0700`:

```json
{"action":"b2b3_primary_outcome_candidate","approved_at_utc":"<timezone-aware UTC timestamp>","approved_by":"<owner identity>","approved_scope":"B2B3_PRIMARY_REPEAT_OUTCOMES_V1_PRIVATE_CANDIDATE_ONLY","authorization_id":"<unique approval ID>","counts_gate_sha256":"<verified final.json SHA-256>","decision":"APPROVED","expires_at_utc":"<timezone-aware UTC timestamp>","output_root":"<absolute .local/b2b3-outcome-output path>","producer_sha256":"<SHA-256 of this exact outcome implementation>","run_id":"<one unique run ID>","schema_id":"B2B3_PRIMARY_REPEAT_OUTCOMES_V1"}
```

The interface checks the action, decision, exact schema and scope, dates, output root, producer digest, run ID, and final counts-gate digest before loading customer-level data.

## Invocation after separate approval

From the development checkout, with the approved record already in place:

```sh
B2B3_OUTCOME_REAL_DATA_AUTHORIZED=1 .venv/bin/python -B docs/recovery/COMMERCIAL_DS_003_STAGE_B2B3_OUTCOMES.py \
  --mode candidate-real \
  --authorization-file path/to/owner-outcome-authorization.json \
  --run-id <owner-approved-run-id>
```

Set the environment flag only for this command. The CLI writes to `.local/b2b3-outcome-output/<run-id>/` with `0700` directories and `0600` files. It records a generic operation log, run context, and `candidate.json`; no IDs, raw rows, or data-bearing exceptions are logged. Duplicate run IDs are refused.

No invocation was made as part of OUTCOME-FIX-001.

## Statistical and release conventions

An outcome is 1 if a later qualifying date occurs strictly after the anchor and strictly before `anchor + H`. Maturity and denominators use the common 90-day-mature customer-month anchors. Wilson bounds use binary64 arithmetic and `z = 1.959963984540054`, clamped to [0, 1]; the proportions and interval bounds are rounded with Python `round(value, 12)` (binary64, ties-to-even behavior). These numerical conventions remain subject to owner approval and do not amend DESIGN-005.

Every real outcome candidate is marked `NOT_APPROVED_FOR_PUBLICATION`. The proxy-1 January/February 2011 cross-artifact inference identified as D-1 remains a release blocker. The 30-customer cell threshold is not a public-release guarantee. Any future disclosure method requires a separate owner decision.
