# COMMERCIAL-DS-002 — Independent Review Handover

**Reviewer:** Claude Code<br>
**Task boundary:** Evidence and decision gate only. Do not implement contracts, change pipelines, regenerate published results or begin Phase 3 during this review.

## 1. Scope performed

- Read the eight required context documents in the requested order.
- Consulted the research programme, architecture and risk register where relevant.
- Inspected the current pandas, dbt and documented KPI implementations for keys, orders, revenue, cohorts, retention, lapse and snapshots.
- Independently loaded both raw sources and verified their hashes, row counts and periods.
- Located the physical V2 source-block boundary and reconciled both overlap copies to V1 by full-row multiplicity.
- Compared four candidate correction policies on rows, revenues, customers and orders.
- Quantified incidental exact repeats outside the overlap and tested candidate line/order identities.
- Quantified V1 left-censoring under current and proposed product-only rules.
- Evaluated 3-, 6-, 9- and 12-month qualifying look-backs, second-purchase horizon maturity and cohort-retention observability.
- Audited the requested canonical business definitions and classified decisions as VERIFIED, RECOMMENDED, BLOCKED or UNRESOLVED.
- Assessed dependencies and invalidation risk for workstreams R1–R6.
- Ran the existing unit suite and documentation validator.
- Did not modify raw data, application code, business logic, models, dependencies, the main README or existing reports.

## 2. Files created

| File | Purpose |
| --- | --- |
| [COMMERCIAL_DS_002_ANALYSIS.py](COMMERCIAL_DS_002_ANALYSIS.py) | Isolated read-only evidence generator; stdout only |
| [COMMERCIAL_DS_002_DATA_AUDIT.md](COMMERCIAL_DS_002_DATA_AUDIT.md) | Full evidence, definition audit, decision matrix and research impact |
| [COMMERCIAL_DS_002_DECISION_PROPOSAL.md](COMMERCIAL_DS_002_DECISION_PROPOSAL.md) | Owner choices, alternatives, trade-offs and Phase 3 blockers |
| [COMMERCIAL_DS_002_REVIEW_HANDOVER.md](COMMERCIAL_DS_002_REVIEW_HANDOVER.md) | This independent-review guide |

The analysis script is the only additional file beyond the three requested reports. It was necessary to make the 1.07-million-row multiset and look-back calculations reproducible without altering existing pipelines or retaining a derived dataset.

## 3. Files inspected

### Required context, in order

1. `docs/recovery/README.md`
2. `docs/recovery/COMMERCIAL_DS_001_AGENT_HANDOVER.md`
3. `docs/recovery/COMMERCIAL_DS_001_EXECUTIVE_BLUEPRINT.md`
4. `docs/recovery/COMMERCIAL_DS_001_DECISION_LOG.md`
5. `docs/recovery/COMMERCIAL_DS_001_DATA_CONTRACTS.md`
6. `docs/recovery/COMMERCIAL_DS_001_EVALUATION_PROTOCOL.md`
7. `docs/recovery/COMMERCIAL_DS_001_ROADMAP.md`
8. `PROJECT_TECHNICAL_HANDOVER.md`

### Selective design/risk context

- `docs/recovery/COMMERCIAL_DS_001_RESEARCH_PROGRAMME.md`
- `docs/recovery/COMMERCIAL_DS_001_ARCHITECTURE.md`
- `docs/recovery/COMMERCIAL_DS_001_RISK_REGISTER.md`

### Executable and reporting evidence

- `src/data_loading.py`
- `src/cleaning.py`
- `src/customer_metrics.py`
- `src/churn_prediction.py`
- `src/validation.py`
- `dbt_project.yml`
- `dbt/models/staging/stg_clean_transactions.sql`
- `dbt/models/intermediate/int_customer_orders.sql`
- `dbt/models/intermediate/int_customer_order_features.sql`
- `dbt/models/intermediate/int_second_purchase_experiment_customers.sql`
- `dbt/models/marts/mart_customer_metrics.sql`
- `dbt/models/marts/mart_retention_cohorts.sql`
- `dbt/models/marts/mart_customer_segments.sql`
- `dbt/models/marts/mart_customer_churn_clv.sql`
- `dbt/models/marts/mart_experiment_eligibility.sql`
- `reports/kpi_definitions.md`
- `reports/dataset_comparison_summary.md`
- `reports/v2_year_over_year_comparison.md`
- relevant code cells in notebooks 05–09 found through bounded text search
- `data/raw/Online Retail.xlsx`
- `data/raw/online_retail_II.csv`

## 4. Commands executed

All commands were run from the repository root unless stated otherwise.

### Repository and source inspection

```bash
git status --short --branch
rg --files
wc -l <required recovery documents>
sed -n <bounded ranges> <required recovery documents and source files>
rg -n <bounded definition/risk patterns> docs/recovery src dbt notebooks reports sql
ls -lh data/raw
shasum -a 256 data/raw/'Online Retail.xlsx' data/raw/online_retail_II.csv
```

Initial Git status:

```text
## main...origin/main [ahead 1]
?? .vscode/
?? PROJECT_TECHNICAL_HANDOVER.md
?? docs/recovery/
```

The supplied outer directory was not a Git repository. The actual repository root is `commercial-retention-analysis/` one level below it.

### Reproducible evidence

```bash
.venv/bin/python docs/recovery/COMMERCIAL_DS_002_ANALYSIS.py > /tmp/commercial_ds_002_evidence.json
jq '{sources,overlap,candidate_corrections,duplicate_evidence_v1,duplicate_evidence_corrected_v2,order_identity_corrected_v2,customer_history_current_valid_lines,customer_history_product_only,non_product_codes_corrected_v2}' /tmp/commercial_ds_002_evidence.json
```

Additional bounded Python checks:

- inspected the V2 chronological reset and boundary rows;
- asserted sorted full-row exact equality for V1 overlap versus each V2 block;
- identified the one V2-only row in the full second block;
- reproduced V1 valid exact-repeat count and revenue;
- calculated product/current inter-order quantiles and the share above 365 days.

### Verification

```bash
.venv/bin/python -m py_compile docs/recovery/COMMERCIAL_DS_002_ANALYSIS.py
.venv/bin/python docs/recovery/COMMERCIAL_DS_002_ANALYSIS.py > /tmp/commercial_ds_002_evidence_verify.json
shasum -a 256 /tmp/commercial_ds_002_evidence.json /tmp/commercial_ds_002_evidence_verify.json
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m src.docs_validation
```

Results:

- Evidence JSON SHA-256 was identical across two runs: `821340995a747ccf4bea3fabc6bfb0212a19a82dc91f54a3c22801eac877cd84`.
- Unit tests: 14 run, 13 passed, 1 skipped because no Java runtime was available for Spark.
- Markdown link validation passed.
- The temporary bytecode file created by `py_compile` was removed; no generated evidence file was retained in the repository.

## 5. Evidence summary for independent verification

| Finding | Primary value |
| --- | --- |
| V2 raw rows | 1,067,371 |
| V2 source-block reset | zero-based row 525,461 |
| V1 overlap rows | 22,523 |
| Each V2 block overlap rows | 22,523, exact full-field multiset match |
| Raw V2 combined overlap | 45,046 rows; GBP 623,756 identifiable gross revenue |
| Narrow corrected V2 | 1,044,848 rows; GBP 17,431,551.18 identifiable gross revenue |
| Identifiable overlap inflation | GBP 311,878.00 |
| Customer/order count impact | none: 5,878 / 36,969 before and after |
| Only V2-vs-V1 second-block difference | one GBP 18 `POST` line, invoice 581587, 2011-12-09 12:50 |
| Corrected-V2 exact repeats outside overlap | 11,491 excess rows; 4,303 invoices |
| Unsupported global-dedupe impact vs narrow correction | -11,812 rows; -GBP 56,746.91 identifiable gross revenue |
| V1 current customers with prior V2 history | 2,726 / 4,338 = 62.84% |
| V1 product-only customers with prior V2 history | 2,722 / 4,334 = 62.81% |
| 12m product-only acquisition-proxy population | 1,612 customers across 13 cohort months |
| Corrected-V2 identifiable gross product revenue | GBP 17,129,436.55 |
| Corrected-V2 identifiable net product revenue | GBP 16,414,904.00 |

## 6. Findings requiring independent verification

Claude Code should independently verify, without trusting the derived JSON:

1. The raw file hashes and the single chronological reset position.
2. Exact sorted eight-field equality, including multiplicity, between V1's 1–9 December window and each V2 block's window.
3. That the correct source-block removal is 22,523 rows and why `duplicated().sum()` returns 22,844.
4. That the second V2 block equals V1 plus exactly the GBP 18 `POST` row.
5. Candidate correction row, revenue, customer and order totals.
6. The global-dedupe sensitivity and the absence of a defensible source key for incidental repeats.
7. The current and product-only V1 left-censoring counts, including selected monthly cohort contamination.
8. The 3/6/9/12-month eligible populations, horizon maturity and retention observability.
9. The non-product mapping amounts, especially the mixed-sign `M` manual entries.
10. Every current-implementation citation and proposed canonical definition in the audit matrix.
11. The list of existing reports/results requiring regeneration.

## 7. Known uncertainties

- The CSV contains no source-sheet name; source blocks are inferred from row order and the only timestamp reset.
- Exact repeats outside the overlap cannot be classified as erroneous or legitimate from available fields.
- V2 cannot establish true first-ever purchase because history before 2009-12-01 is unavailable.
- The non-product taxonomy needs business-owner confirmation, especially `M`, `D`, `CRUK`, `PADS`, `B` and `S`.
- The final month is partial, limiting recent cohort and horizon maturity.
- Customer returns cannot be linked to original invoices reliably.
- The 365-day active rule is empirically reasonable but still a policy choice.
- No owner decision has been approved or written to the COMMERCIAL-DS-001 decision log.

## 8. Git status and preservation note

At handover, the branch remains `main`, one commit ahead of `origin/main`. Pre-existing untracked `.vscode/`, `PROJECT_TECHNICAL_HANDOVER.md` and `docs/recovery/` remain untracked. Because the requested COMMERCIAL-DS-002 files were added inside the already-untracked `docs/recovery/` directory, short Git status does not distinguish them individually.

No tracked file was modified. No commit or push was performed. Raw datasets and existing uncommitted files were preserved.

Reviewer command:

```bash
git status --short --branch
git ls-files --others --exclude-standard docs/recovery | sort
```

## 9. Reviewer instructions

1. Run the analysis script and independently reproduce at least the eleven checks in §6.
2. Review the correction recommendation for scientific validity, not only arithmetic correctness.
3. Challenge the proposed acquisition-proxy terminology; reject any implication of known first-ever purchase.
4. Review the P-09 taxonomy and gross/net revenue choices as business decisions, not facts inferred by code.
5. Confirm that the decision proposal does not mark any owner policy as approved.
6. Report discrepancies against exact file/section references.
7. If the evidence passes, recommend that the owner decide P-01, P-01b, P-09, P-17, line identity and lapse terminology.
8. Do not author the canonical YAML or begin Phase 3 until those decisions are recorded and contract encoding is separately authorised.

## 10. Exact next step after review

The owner reviews Claude Code's independent findings and records decisions in `COMMERCIAL_DS_001_DECISION_LOG.md`. If, and only if, contract encoding is then authorised, the next bounded task is to create versioned `contracts/business_definitions.yml` plus synthetic and real-data contract tests that implement the approved definitions. Phase 3 remains unauthorised until that artifact passes independent review.
