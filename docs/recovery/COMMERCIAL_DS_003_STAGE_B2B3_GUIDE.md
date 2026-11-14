# B2B-3 Counts-Only Feasibility Gate

## Scope and frozen contract

The gate computes structural purchaser eligibility and fixed-calendar maturity under `B2B3_COUNTS_GATE_SCHEMA_V1`. It does not search for later purchases, calculate repeat outcomes, or support acquisition, lifecycle, causal, or predictive claims. Customer identifiers stay in local memory for approved population assignment and distinct-customer-month counting. No customer-level row, identifier, history, purchase-derived date bound, or outcome value is permitted in the V1 payload.

The producer reuses the validated corrected-V2/O-9 pipeline and the B2B-2 population membership utility. Primary anchors are the first qualifying date per customer-month. H=30/60/90 maturity is evaluated against 2011-12-09, and the three horizon rows share the 90-day-mature risk set. The exact allowlist and owner-approved C-8 disclosure scope remain in the frozen external DESIGN-005 documents. Schema changes require a new review and explicit owner approval.

## Synthetic tests

The verified pinned environment is Python 3.11.14 with pandas 3.0.2 and numpy 2.4.4 in the project virtual environment:

`.venv/bin/python`

This interpreter is used read-only; no files in the original checkout are changed. From the development repository root, run:

```sh
cache_dir="$(mktemp -d)"
chmod 700 "$cache_dir"
PYTHONPYCACHEPREFIX="$cache_dir" .venv/bin/python -B -m unittest -v docs.recovery.test_COMMERCIAL_DS_003_STAGE_B2B3
result=$?
python3 -B -c 'import pathlib, shutil, sys; shutil.rmtree(pathlib.Path(sys.argv[1]))' "$cache_dir"
exit "$result"
```

The suite is synthetic only. It does not call the raw-source loader. Tests write transient candidates only under `.local/b2b3-gate-synthetic/`, mode `0700`, and remove their run folders afterward. Python bytecode is redirected to a new private temporary cache and that cache is removed after the run.

The equivalent test CLI is:

`.venv/bin/python -B docs/recovery/COMMERCIAL_DS_003_STAGE_B2B3.py --mode synthetic-tests`

## Integrity and artifact lifecycle

Candidate generation writes the frozen V1 fields only. Its `independent_reconstruction` and `privacy_transcript_audit` checks are `false`, so a candidate is not a releasable result. The automated C-8 check verifies the allowlist and all encoded derivations; it does not claim to prove the absence of every conceivable inference. The owner-approved C-8 review defines which aggregate implications are acknowledged.

A separate reviewer must provide a reconstruction evidence sidecar containing the exact independently reconstructed metadata, calendar coverage, monthly counts and threshold-flag sections, plus the frozen B2B-2 population and 90-day maturity references. The finalizer compares those sections with the candidate bytes. A mismatch, missing section, same reviewer/operator identity, or implementation hash equal to the producer blocks finalization.

A separate human privacy reviewer must provide a privacy sidecar tied to the candidate hash and generated-log hash. It records review of generated logs and applicable agent transcripts, and confirms no customer-level exposure. Code verifies the sidecar structure, identities, hashes, and fixed log allowlist; it cannot inspect or certify every external terminal/agent transcript. Until that human evidence is present, `privacy_transcript_audit` remains false. The frozen V1 output contains no evidence fields; reviewer evidence and run context remain private sidecars beside the artifact.

`serialize_payload` intentionally refuses direct caller serialization. Only `finalize_candidate` can write `final.json`, after the evidence comparisons and all required automated checks pass. `load_and_validate(path)` revalidates a saved final artifact against its candidate and retained private evidence. The final JSON uses the exact frozen allowlist and deterministic canonical encoding; duplicate keys and noncanonical encodings are rejected.

## Proposed real-data invocation (not run)

Real-data execution is disabled by default. It requires all of the following:

- a separate owner approval JSON with exact action `candidate_real_data`, schema ID, current producer SHA-256, approved output root, approval ID, approving owner, and expiry;
- `B2B3_REAL_DATA_AUTHORIZED=1` in the invocation environment;
- explicit `candidate-real` mode, operator ID, and run ID.

Example only; do not run without separate owner authorization:

```sh
B2B3_REAL_DATA_AUTHORIZED=1 .venv/bin/python -B docs/recovery/COMMERCIAL_DS_003_STAGE_B2B3.py \
  --mode candidate-real --authorization-file path/to/owner-authorization.json \
  --operator-id OWNER_ID --run-id RUN_ID
```

The candidate is written beneath `.local/b2b3-gate-output/RUN_ID/` with directory mode `0700`, files mode `0600`, atomic writes and restrictive temporary files. The location is Git-ignored. A separate reviewer then places canonical `reconstruction.json` and `privacy_review.json` sidecars in that same private run directory. Only after those independent checks can the finalizer be invoked:

```sh
.venv/bin/python -B docs/recovery/COMMERCIAL_DS_003_STAGE_B2B3.py \
  --mode finalize-real --run-id RUN_ID
```

The finalizer writes only `final.json` in the frozen V1 schema. Candidate output, reviewer sidecars, and private generic logs are separate local evidence files, not public deliverables. The code emits only fixed generic log messages and suppresses exception details.

An owner approval for implementation or this execution pathway is not authorization to run it. Real-data execution and output release remain separately unauthorized in this implementation stage.

## Operational policy and limitations

The owner replaced the earlier encrypted-volume and exhaustive backup/synchronisation verification proposals with proportionate local safeguards for this research project. The synthetic and aggregate output directories are Git-ignored and permission-restricted; Git ignore is not protection against other sync or publication routes. Earlier OPS-001 backup/synchronisation findings remain UNKNOWN and are not reclassified as verified exclusions.

Do not print customer records, identifiers, histories, raw rows, or data-bearing exceptions to stdout, stderr, logs, prompts, tool output, reports, or agent transcripts. Debug only with synthetic examples. On suspected exposure, stop, restrict access, preserve only a minimal note without exposed data, and notify the owner for containment guidance. Do not copy outputs into the public repository.

Outcome methods, intervals, secondary-anchor analyses, proxy outcome comparisons, and quarterly outcome aggregation remain deferred. No real-data run occurred in this implementation stage.
