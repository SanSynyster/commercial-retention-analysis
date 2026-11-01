# COMMERCIAL-DS-001 — Decision Log

Part of the [recovery index](README.md). This file is the **source of truth for decisions**. Agents must not act on a proposed decision until it is moved to "Confirmed" by the project owner.

## 1. Confirmed decisions

Recorded from the COMMERCIAL-DS-001 brief issued by the project owner on 2026-10-30.

**Editorial note (2026-11-01):** The original owner-confirmed CD-01 wording used a term excluded from current public-facing project materials. This log renders that terminology as “research programme.” The approved multi-study structure and project title are unchanged; this editorial wording does not alter the decision.

| ID | Decision | Source |
| --- | --- | --- |
| CD-01 | The project is restructured as a multi-study Commercial Data Science research programme, titled *Commercial Data Science & Customer Intelligence* (title stated as "proposed" in the brief; see P-00) | Owner brief §2 |
| CD-02 | Six workstreams R1–R6 as defined in the brief | Owner brief §3 |
| CD-03 | Spark is retained for technical coverage, without claiming it is needed for the dataset size | Owner brief §3 R6 |
| CD-04 | Databricks remains optional until deployment can be verified | Owner brief §3 R6 |
| CD-05 | No historical customer split is presented as a real A/B test; no invented uplift drives recommendations | Owner brief §3 R5 |
| CD-06 | The existing lapse model is preserved as a historical baseline | Owner brief §3 R3 |
| CD-07 | Nothing existing is deleted in this phase. Archiving requires a documented proposal first | Owner brief §6, §11 |
| CD-08 | Tools are retained only with a documented purpose, a verification strategy and a research link | Owner brief §2 |
| CD-09 | Phase 1 is documentation-only: no code, data, model, README or dependency changes; no commits | Owner brief §11 |
| CD-10 | Later phases are never authorised automatically | Owner brief §8 |

## 2. Proposed decisions (require owner approval)

| ID | Proposal | Rationale | Alternatives | Needed before |
| --- | --- | --- | --- | --- |
| P-00 | Confirm the final project title | The brief marks the title as proposed | Keep "commercial-retention-analysis" as the repo name, with the new title in docs | Phase 10 |
| **P-01** | **Make V2 (deduplicated) the canonical dataset.** V1 becomes the legacy baseline | V1 is 62.8% left-censored (R-19); V2 gives a 12-month burn-in for acquisition and two seasonal cycles | Keep V1 canonical and mark all acquisition/cohort/first-purchase analyses NOT SUPPORTED | Phase 2 |
| **P-01b** | Approve the V2 overlap dedupe approach (`C-DQ-1`), subject to reconciliation evidence | R-18 | Truncate V2 to before 2010-12-01 and append V1 instead (equivalent if V2 ⊇ V1 holds) | Phase 2 |
| P-02 | `src/` pandas is the reference implementation; dbt and Spark are parity mirrors | Ends 5-way divergence | dbt as reference (would push ML features into SQL) | Phase 3 |
| P-03 | Single canonical segmentation `C-SEG`. Interim RFM quintiles until R2 decides. Notebook P1–P7 and dbt P1–P5 become historical | R-06 | Adopt one of the existing schemes now | Phase 3 |
| P-04 | Reclassify the dbt experiment marts as an A/A design frame (rename or add `evidence_class`, remove decision flags); rebuild per `C-EXP` in Phase 8 | R-07–R-09 | Delete them (conflicts with CD-07); leave them unchanged (misleading) | Phase 8 |
| P-05 | All README/report numbers are generated from a results registry with CI consistency checks | R-01 | Manual updates with a checklist | Phase 3 |
| P-06 | Owner installs JDK 17 locally (and CI uses an explicit JDK) so Spark can be verified | R-40 | Leave Spark "unverified"; demote it in the research programme | Phase 9 |
| P-07 | Freeze `src/churn_prediction.py` at `1b293c2` behaviour as baseline B0 (no edits; successor in `src/models/lapse.py`) | Preserves a reproducible reference | Fix it in place (loses the historical reference) | Phase 3 |
| P-08 | Notebooks become presentation-only and import `src` | R-02 | Keep notebooks as an independent implementation | Phase 3 |
| P-09 | Data-quality policies: keep and flag exact duplicates outside the overlap (`C-DQ-2`); classify non-product codes and exclude them from customer product revenue (`C-DQ-3`); customer metrics on gross product revenue, with net as a separate field (`C-DQ-4`) | R-14 | Remove duplicates; keep non-product codes | Phase 2 |
| P-10 | Dependency additions, pinned: `statsmodels` (forecasting/ETS); one CLV approach (PyMC-Marketing, or an in-house scipy BG/NBD); optional `shap` | R-42 | Avoid new libraries; restrict R4 to ML regression and simple forecast baselines | Phases 5, 7 |
| P-11 | Archival plan per [architecture](COMMERCIAL_DS_001_ARCHITECTURE.md) §3 (reversible `git mv` into `archive/`) | Reduces confusion without deletion | Keep everything in place with "legacy" banners only | Phase 10 |
| P-12 | Pin CI dependencies (lock file or fully pinned minimal requirements) | R-15 | Accept drift | Phase 3 |
| P-13 | Commit `PROJECT_TECHNICAL_HANDOVER.md` together with `docs/recovery/` (links depend on it) | R-21 | Move the handover into `docs/recovery/` and update links | Owner's next commit |
| P-14 | Reverse phases 5/6 (lapse before segmentation); run R5 in parallel after Phase 3 | [Roadmap](COMMERCIAL_DS_001_ROADMAP.md) rationale | Keep the brief's original order | Phase 4 end |
| P-15 | Retire the second-purchase propensity model from CRM scoring. Report it as a negative finding; revisit only on V2 with `C-ACQ` | R-11, R-19 | Re-tune it on V1 (not recommended) | Phase 5 |
| P-16 | Lapse horizon: h = 90 days primary, 60/120 sensitivity, confirmed by the R1 interval analysis | Interval quantiles | 120 days primary (closer to V2 p90) | Phase 5 pre-registration |
| P-17 | Look-back windows: `C-ACQ` L = 12 months; `C-ACTIVE` = 365 days | Data contracts | 6 or 9 months (larger acquisition sample, more contamination) | Phase 2 |

## 3. Open questions for the owner

## 3A. Approved COMMERCIAL-DS-002 / 002A decisions

Approved by the project owner explicitly in the COMMERCIAL-DS-002B task following the COMMERCIAL-DS-002A independent review. Conditions below are part of each approval. Historical proposals above are retained verbatim as decision history; this section supersedes their conflicting wording. See [002A supersession](COMMERCIAL_DS_002A_SUPERSESSION.md).

| Established ID | Approved decision and conditions | Approval source |
| --- | --- | --- |
| P-01 | Canonical candidate is overlap-corrected V2 (`v2c`). | Owner explicit approval following 002A independent review; 002B brief |
| P-01b | Remove only the verified 22,523-row source overlap; assert source hashes, block structure, exact null-safe multiset equality, and corrected row count. | Same |
| P-09a | Retain and flag incidental exact repeats; report deduplication sensitivity. | Same |
| D-002-04 | Assign source-row line IDs once at ingestion; preserve source hash plus zero-based row number as materialised identity. | Same |
| P-09 / D-002-05 | Use the approved transaction taxonomy and fail-closed precedence in O-1/O-2. Gross merchandise revenue is the primary behavioural metric. | Same |
| P-09 / D-002-06 | Preserve category-specific commercial revenue fields and net merchandise sensitivity; use exact decimal precision ≥3 places. | Same |
| P-17 / D-002-07 | Use a 12-month acquisition proxy, never a known first-ever acquisition claim. Carry observed-look-back metadata, pseudo-boundary disclosure and late-cohort sensitivity. | Same |
| P-17 / D-002-08 | A 365-day active window is eligible for canonical snapshots only when complete. Redesign R3 temporal evaluation before modelling. | Same |
| D-002-09 | Separate historical inactivity from future non-purchase labels; use half-open windows and date-level maturity. | Same |
| D-002-10 | Apply O-9 purchase-occasion definition; preserve invoice-level repeat as sensitivity. | Same |
| D-002-11 | Use date-level label maturity consistently. | Same |
| D-002-12 | Preserve returns-only and negative-net customers in reconciliation; define treatment in R4 rather than silently dropping them. | Same |
| O-1 … O-9 | Approve transaction-type policies exactly as described in the 002B owner instruction and detailed in `COMMERCIAL_DS_002B_CONTRACT_SPECIFICATION.md`. | Same |

These approvals do not approve unrelated deferred decisions P-00, P-02–P-08, P-10–P-16, or authorise production contract encoding or Phase 3. The identifier D-002-12 is added only for the approved returns reconciliation policy; established P-IDs above are retained rather than duplicated.

**Reference status note (2026-10-31):** the `COMMERCIAL_DS_002B_CONTRACT_SPECIFICATION.md` named in the historical O-1…O-9 row above does not yet exist. It is a planned artifact, not a completed approval record. O-1…O-9 approval is recorded here as sourced to the owner's explicit COMMERCIAL-DS-002B instruction and the approved decisions in this section. No contract has been encoded by this note.

**Reference status update (2026-10-31, Stage A):** the historical status note above was accurate when entered. The formal `COMMERCIAL_DS_002B_CONTRACT_SPECIFICATION.md` has now been authored as the Stage A purchase-occasion and taxonomy contract foundation. It documents approved semantics and invariants; it is not production contract encoding, does not supersede owner decisions, and does not authorize downstream modelling.

**O-5 owner-approved amendment (2026-10-31; owner response: “yes” in the ChatGPT coordination conversation):** classify positive standalone `M` line amounts as `standalone_manual_billing`, negative standalone amounts as `standalone_manual_credit`, zero-value standalone rows as `standalone_manual_zero_value`, and embedded `M` rows as `manual_adjustment` regardless of sign. All four categories remain in source-value reconciliation and are excluded from merchandise sales, returns, purchase occasions, retention/repeat events and behavioural customer-value features. A negative manual credit is not paired with or attributed to an earlier invoice without separate evidence; its economic cause remains unknown. This owner approval covers the category split and stated limitations only; it does not attribute the later cancellation-invoice interpretation to the owner, replace other decisions, or authorise downstream modelling.

**O-5 invoice-context technical clarification (2026-10-31; based on the independent review, not a new owner approval):** M standalone/embedded context is distinct from purchase-occasion eligibility. A non-cancellation invoice has merchandise context when it contains a non-row-context merchandise line with positive value; a cancellation invoice has merchandise context when it contains a non-row-context merchandise return with nonzero value. This preserves 64 negative M rows (GBP −1,168.70; 52 invoices; 47 customers) as embedded `manual_adjustment`. They remain so classified; the context does not assert that an M amount refunds or links to a merchandise return. No further owner decision is required for those observed rows under this reviewed interpretation; any future change to this context definition requires owner review.

## 3B. Open questions for the owner

1. What role(s) and seniority is the research programme targeting? This decides the depth of R4/R6 relative to R3/R5.
2. Is there a deadline? It decides whether Phases 7–9 are in scope.
3. Is installing a JDK acceptable (P-06)? If not, Spark is presented as code-reviewed but unverified.
4. Should legacy reports remain visible at their current paths with banners, or be moved to `archive/` (P-11)?
5. Push the unpushed commit `1b293c2`? Rewrite history to remove the raw data blobs? (The rewrite is destructive and needs explicit approval.)
6. Should `.vscode/` be ignored or committed?
7. Is the Tableau workbook available, so BI exports can be verified end-to-end?
8. For the observed-acquisition proxy, select a primary rule. Diagnostics: 1,613 merchandise-only candidates; excluding prior identified activity before the fixed 2010-12-01 cutoff leaves 1,602; excluding any prior identified activity before each customer's first qualifying occasion leaves 1,601. These are alternatives/sensitivities, not owner-approved policy. Until explicitly decided, report all as diagnostics only and do not publish a primary proxy cohort.

## 4. Gate approvals

| Gate | Date | Approved by | Notes |
| --- | --- | --- | --- |
| Phase 1 | — | — | Awaiting owner review |
