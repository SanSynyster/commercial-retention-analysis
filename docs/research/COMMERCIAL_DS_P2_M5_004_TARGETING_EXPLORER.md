# M5-004 — CRM Targeting Explorer

## Result

Replaced the Targeting Explorer placeholder with a functional aggregate-only view of the four frozen M3 policies at exactly 5%, 10% and 20% capacity. The app loads `app_data/targeting_v1.json`; no customer-level predictions, selections or outcomes are present. No model was trained and no M3 result was changed.

## Approved M3 content and provenance

The bundle is derived from the final M3-002 aggregate JSON, whose SHA-256 is `5e9558f7d26a144587325d6465164bed7f6ce1718facc35f0e7a6cd6c15b509d`. Its manifest records frozen upstream hashes for the M2 dataset, dataset manifest, predictions and baseline run manifest. The approved research sources are `COMMERCIAL_DS_P2_M3_002_TARGETING_COMPARISON.md` and independent review `COMMERCIAL_DS_P2_M3_003_INDEPENDENT_TARGETING_REVIEW.md`. The bundle content SHA-256 is `44bcf66762056a8746333239e731e6d79809d2a0a29904924dd9b8c858a7c6f9`, independently pinned in `src/targeting_bundle.py`.

The frozen holdout contains 21,672 mature customer-month snapshots, 5,092 positive outcomes and 4,999 distinct customers across July–November 2011. At 10%, pooled precision was 69.35% Model C, 68.80% frequency, 67.24% RFM and 23.50% analytical random expectation. The bundle includes pooled selected snapshot counts, precision, capture and lift at all three capacities, Model C paired customer-cluster differences versus each alternative, overlap with Model C, available repeat-selection aggregates, and the reported tie sensitivity. Random selection is an analytical expectation; no random list was drawn.

The frozen aggregate does not provide standalone policy confidence intervals; the UI leaves those unavailable rather than estimating them. Pairwise 95% percentile intervals are shown as reported, with their conditional/exploratory limitations. They are not formal hypothesis tests, and a difference interval crossing zero does not establish equivalence.

## Explorer behavior

- The radio selector has exactly 5%, 10% and 20% choices and updates the comparison, pairwise differences, overlap, tie sensitivity and repeated-selection table.
- The page shows a policy table and precision chart, with exact policy labels, snapshot denominator and selected customer-month counts.
- Model C versus RFM, frequency and random includes frozen precision and capture differences and paired 95% customer-cluster intervals.
- Overlap is reported as share of Model C selections in common and Jaccard overlap. The tie table reports key-ascending frozen results and alternatives from the independent review.
- Repeat-selection statistics describe list membership across monthly decisions, not actual contact.
- The scientific caveat is visible: this is retrospective future-purchase capture, not causal CRM response or commercial value. Eligibility, consent, contact policy and economics are not established by M3.

For future prospective evaluation, the research recommends a prespecified pseudorandom hash tie-break. This does not alter the frozen historical selections.

## Validation and operating notes

The loader enforces an exact top-level schema, approved capacities and policies, frozen holdout counts, source aggregate hash, content hash and independent application pin. It rejects identifier/selection/prediction fields and returns controlled errors for missing or malformed files. Runtime data are served only from the tracked bundle, so a clean checkout requires no private source data.

Run the page from the repository root with `streamlit run app/streamlit_app.py`. Build the tracked bundle only from the frozen aggregate via `python3 src/targeting_bundle.py <path-to-frozen-m3-aggregate.json>`; the builder checks its approved source hash before emitting content.
