# B2B-3 Outcome Private Finalisation — Offline CLI

## Scope and safeguards

This separate standard-library-only CLI finalises an already generated and independently reconstructed candidate. It does not import the outcome producer, the Stage A loader, or transaction-processing code. It never accesses source data. It validates the candidate and evidence against the reviewed identities pinned in the module, refuses an existing `final.json`, writes atomically with private permissions, preserves `candidate.json`, and marks the resulting artifact `NOT_APPROVED_FOR_PUBLICATION`. D-1 remains an unresolved release blocker.

The CLI is a future interface. This implementation milestone creates no owner receipt and does not run it against the real candidate.

## Owner privacy receipt

After explicitly approving private finalisation, the owner may have Codex transcribe the owner's confirmation into a canonical UTF-8 JSON file named `privacy_receipt.json` in the private run directory. Do not describe the receipt as owner-signed. It records owner statements and the confirmation date only; it must not invent a signature, timestamp, transcript digest, or network audit. File mode must be `0600`; the containing directory must be `0700`.

Schema ID: `B2B3_OUTCOME_PRIVACY_RECEIPT_V1`. The file must contain exactly the following keys (canonical JSON, sorted keys, compact separators, one trailing newline):

`receipt_id` must match `[A-Za-z0-9][A-Za-z0-9_-]{0,63}`: 1–64 ASCII letters, digits, underscores or hyphens, beginning with a letter or digit. This prevents whitespace, control characters, path separators, and multiline text from entering the artifact.

```json
{
  "schema_id": "B2B3_OUTCOME_PRIVACY_RECEIPT_V1",
  "receipt_id": "<unique receipt ID>",
  "run_id": "B2B3-OUTCOME-RUN-001-20261109",
  "candidate_sha256": "<exact candidate digest>",
  "operation_log_sha256": "<exact saved operation-log digest>",
  "authorization_sha256": "<exact saved authorisation-record digest>",
  "verification_report_path": "<absolute path to the saved Claude report>",
  "verification_report_sha256": "<report digest>",
  "verification_manifest_sha256": "<manifest digest>",
  "verification_results_sha256": "<results digest>",
  "decision": "APPROVED",
  "reviewer": "Project owner (ChatGPT confirmation; transcribed by Codex CLI)",
  "approval_scope": "B2B3_OUTCOME_RUN_001_PRIVATE_FINALISATION_ONLY_NO_PUBLICATION",
  "owner_confirmation_date": "2026-11-09",
  "owner_statement_source": "owner_confirmation_in_chatgpt",
  "owner_statements": {
    "complete_codex_execution_transcript_reviewed": true,
    "no_customer_level_disclosure_observed_by_owner": true,
    "codex_authorization_transcription_confirmed_by_owner": true,
    "scientific_and_operational_limitations_accepted_by_owner": true,
    "private_finalisation_approved_by_owner": true
  },
  "publication_status": "NOT_APPROVED_FOR_PUBLICATION"
}
```

The implementation enforces the exact schema, values, run/candidate/log/authorisation bindings, independent verification report and evidence identities, plus private file permissions. The owner statements must remain accurately attributed as owner confirmations, not facts independently observed by Codex.

## Invocation after separate approval

From the development checkout, only after a receipt exists and an owner has approved finalisation, use the module CLI with `--mode finalize-private`, the exact run ID, private run directory, receipt, verification directory, and all explicit reviewed hashes. For example:

Supply `--approved-finalizer-sha256` from the independent review decision for the exact reviewed finaliser bytes. This value is an external pin, not a value the executable can declare to approve itself. The CLI hashes its own file before processing the bundle, checks it again immediately before writing, and rechecks after saved-artifact validation. The final artifact records the verified digest. If the digest differs, the CLI refuses before finalisation; if it changes during the operation, any invocation-owned final artifact is removed only after its file identity is confirmed.

```sh
.venv/bin/python -I -B \
  docs/recovery/COMMERCIAL_DS_003_STAGE_B2B3_OUTCOME_FINALIZE.py \
  --mode finalize-private \
  --run-id B2B3-OUTCOME-RUN-001-20261109 \
  --private-output-directory .local/b2b3-outcome-output/B2B3-OUTCOME-RUN-001-20261109 \
  --receipt-file .local/b2b3-outcome-output/B2B3-OUTCOME-RUN-001-20261109/privacy_receipt.json \
  --verification-directory .local/b2b3-outcome-output/CLAUDE-OUTCOME-VERIFY-001-B2B3-OUTCOME-RUN-001-20261109 \
  --approved-finalizer-sha256 REPLACE_WITH_INDEPENDENTLY_PINNED_SHA256 \
  --candidate-sha256 c6374f3dee288fef8c2d152c6339372010290181c9a5eb4d9873d05a5fdd9c59 \
  --producer-sha256 48c1aa5badb3fec5dc920cb5346f333e3279d8d2314ad48bda5f7d8d46b77f44 \
  --counts-gate-sha256 20d2eea6a0dffb57430491cf2e3d995b229eefdfae3c4ecd11846024ec29f6d4 \
  --authorization-sha256 6ebc2159982fec5597bef5dbc10a355c5a2412355c02eb7a6083a3804fd40880 \
  --operation-log-sha256 680ec6ae67edabe07b798dce3a469da644abe715727266e5fc95d2d51dcf221a \
  --run-context-sha256 a88e56d0c3f9e529486282e175667319fa2adb10fcfff44c01ceaa775f333fe4 \
  --verification-report-sha256 9cbbcf657d6cca441f6c473a15b32e387cf7d4eda369008542d6dbcadd7f466b \
  --verification-manifest-sha256 5a141bad64994d187f3e5f68d833ee7f6e1058a646d4a49a0033211f96c9692e \
  --verification-results-sha256 3d5d99741d27e6eb3cce810177a3f1bf140963247ca1ffbf6e24677cf62ee87b \
  --reconstruction-sha256 b376ede371021fa0feb2c0572652cccdf03dd8e90cf893550503926156c886b6 \
  --reviewer-code-sha256 3fb0272e6f9c485adb5f08e10e3cef76201656940ee5cbc582d1be3fa1a4e373
```

The operation is one-shot: an existing final artifact is refused. On success, `final.json` contains the unchanged candidate under `candidate`, plus finalisation provenance and the publication block. Keep the final artifact, original candidate, receipt, run evidence and independent verification evidence private. Do not publish or push these outcomes; no disclosure-safe release is defined by this interface.
