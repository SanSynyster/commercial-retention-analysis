# Commercial Data Science & Customer Intelligence

A reproducible research-engineering repository for retail transaction analysis, customer purchase measurement, and commercial data validation. It combines earlier exploratory analytics code with a newer, evidence-led corrected-data workstream. The two workstreams have different data definitions and should not be read as one interchangeable set of results.

## Current status

**COMMERCIAL-DS-003 B2B-1 implementation is complete; independent re-review is pending.** Stage B2A source integrity, taxonomy, revenue reconciliation, and purchase occasions were independently reviewed. The subsequent B2B-1 trust-boundary correction has been self-verified by Codex and is awaiting Claude Code re-review. Stage B2B downstream analytics have not started.

## Research and engineering objectives

- Establish source lineage and reproducible transaction corrections.
- Separate merchandise, returns, shipping, manual entries, fees, and administrative activity.
- Define customer purchase occasions with explicit eligibility and temporal rules.
- Reconcile signed transaction-line amounts exactly and preserve customer attribution.
- Keep exploratory modelling and simulated experiments distinct from causal evidence.

## Data provenance and scope

The analyses use the UCI **Online Retail** and **Online Retail II** transaction datasets, donated by Daqing Chen. The UCI pages identify both datasets as **Creative Commons Attribution 4.0 International (CC BY 4.0)** and provide the recommended citations: [Online Retail](https://archive.ics.uci.edu/dataset/352/online+retail), DOI [10.24432/C5BW33](https://doi.org/10.24432/C5BW33); [Online Retail II](https://archive.ics.uci.edu/dataset/502/online+retail+ii), DOI [10.24432/C5CG6D](https://doi.org/10.24432/C5CG6D). See [data provenance and attribution](docs/DATA_PROVENANCE.md).

The raw files are not tracked in Git. Local reproduction expects `data/raw/Online Retail.xlsx` and `data/raw/online_retail_II.csv`; SHA-256 values and the CSV conversion provenance limitation are documented in the data guide. The UCI source includes pseudonymous customer identifiers and transaction details. Avoid adding row-level customer outputs, raw extracts, model artifacts, or local databases to Git.

## Verified corrected-V2 findings

These results describe the corrected V2 definition documented in the [contract specification](docs/recovery/COMMERCIAL_DS_002B_CONTRACT_SPECIFICATION.md), not the earlier V1 notebooks.

| Measure | Verified value | Definition |
|---|---:|---|
| Raw V2 rows | 1,067,371 | Source CSV data rows |
| Overlap rows removed | 22,523 | The reviewed V1/V2 duplicate block only |
| Corrected-V2 rows | 1,044,848 | Corrected source rows, retaining incidental exact repeats |
| Qualifying purchase occasions | 36,594 | Customer-by-invoice groups with qualifying positive merchandise lines |
| Customers with qualifying occasions | 5,852 | Distinct identified customers in those occasions |
| Qualifying gross merchandise | GBP 17,123,740.997 | Exact Decimal sum of qualifying positive merchandise line values |
| Full signed transaction-line value | GBP 18,909,762.118 | Signed quantity × unit price across all 16 bridge categories |
| Identifiable signed amount | GBP 16,343,669.038 | Signed value on rows with a customer identifier |
| Unattributed signed amount | GBP 2,566,093.08 | Signed value on rows without a customer identifier |
| Positive unattributed merchandise activity | GBP 2,575,930.13 | Positive merchandise rows that cannot enter customer-level purchase occasions |

Signed transaction-line value is an exact line reconciliation, not recognised accounting revenue or profit. Qualifying gross merchandise is a narrower measure: it excludes returns and non-merchandise categories and requires positive quantity, positive unit price, an identified customer, a valid timestamp and invoice, and a non-cancellation invoice. Unattributed commercial activity remains in the full reconciliation but cannot be assigned to customer behaviour.

A **purchase occasion** groups eligible merchandise lines by customer and invoice. It is distinct from a transaction line, invoice count across all categories, or a customer-day repeat count.

The Stage B2A review reproduced 2,532 customers with a later-day repeat and 2,673 under invoice-level sensitivity. These are descriptive counts over 5,852 occasion customers without a maturity-filtered denominator; they are **not retention rates**. Acquisition-proxy diagnostics (1,613, 1,602, and 1,601 customers under alternative screens) remain unapproved diagnostics, not a published acquisition cohort.

## Implemented capabilities

- Earlier V1/V2 cleaning, cohort, segmentation, CRM prioritisation, model, SQL/dbt, Spark, and dashboard code is present. Those artifacts are historical exploratory work; no legacy model-performance result is adopted as corrected-V2 evidence, and the current work has not independently validated every older output or operational recommendation.
- The corrected-V2 workstream has a pinned source correction, reviewed taxonomy, 16-category signed bridge, purchase-occasion builder, frozen integrity references, and adversarial validation tests.
- The current B2B-1 correction recomputes source, classification, and customer fingerprints from consumed rows, then checks frozen category values and source-row membership.

## Reproduction

Use Python 3.11. A lightweight, data-free validation path is:

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements-minimal.txt
make validate-ci
```

The local corrected-V2 evidence path requires the two raw files named above and verifies their hashes before analysis:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python docs/recovery/COMMERCIAL_DS_002B_INTEGRATION.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s docs/recovery -p 'test_COMMERCIAL_DS_*.py' -v
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python docs/recovery/COMMERCIAL_DS_003_PURCHASE_OCCASIONS.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python docs/recovery/COMMERCIAL_DS_003_REVENUE_BRIDGE.py
```

The recovery suite exercises real data and takes several minutes. `make validate-ci` runs lightweight tests, local Markdown link checks, and synthetic end-to-end checks; it does not claim the real-data recovery suite passed. See [reproduction instructions](docs/REPRODUCIBILITY.md).

## Repository map

| Path | Contents |
|---|---|
| `src/`, `tests/` | Earlier reusable analytics code and lightweight regression tests |
| `notebooks/` | Exploratory analysis and model notebooks |
| `dbt/`, `sql/` | SQL transformations, marts, and data-quality tests |
| `dashboards/`, `reports/` | Historical V1 reports, simulation scenarios, CRM proposals, and dashboard views are labeled exploratory and not deployment evidence |
| `data/bi_exports/` | Historical aggregate exports are excluded from the proposed release tree; regenerate only under a reviewed analysis contract |
| `docs/` | User-facing technical, methodology, and reproduction documentation |
| `docs/recovery/` | Source audits, decisions, contract, frozen references, verification, and independent reviews |
| `data/raw/`, `data/processed/`, `data/warehouse/` | Local inputs and generated data; ignored by Git |

## Scientific limitations and interpretation

- The source is left-censored; no observed first purchase proves true acquisition.
- The data does not include margin, campaign exposure, channel, or demographic features. It cannot establish causal marketing impact.
- Cancellation and return values are reconciled as observed lines; credits are not linked to specific original invoices.
- Earlier model and experiment outputs are not evidence of deployment or causal effect. The simulated experiment is not a randomized trial.
- Current B2B-1 integrity checks have not yet received the pending independent re-review.
- Original project code is licensed under MIT; see [LICENSE](LICENSE). The MIT license does not apply to UCI datasets or third-party dependencies, which retain their own terms.

## Documentation

- [Research status](docs/RESEARCH_STATUS.md)
- [Documentation index](docs/index.md)
- [Data provenance](docs/DATA_PROVENANCE.md)
- [Reproducibility](docs/REPRODUCIBILITY.md)
- [B2B-1 integrity closure handover](docs/recovery/COMMERCIAL_DS_003_STAGE_B2A_INTEGRITY_CLOSURE_HANDOVER.md)
- [Full recovery evidence index](docs/recovery/README.md)
