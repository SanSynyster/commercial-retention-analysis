# Reproducibility

## Supported environment

The verified local environment is Python 3.11.14. CI targets Python 3.11 and runs without private or downloaded datasets. The dependency list in `requirements-minimal.txt` supports the lightweight pipeline tests; `requirements.txt` includes the broader notebook, dbt, Spark, and visualization environment.

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements-minimal.txt
make validate-ci
```

`make validate-ci` runs unit tests, local Markdown link validation, and deterministic synthetic data checks. It does not execute corrected-V2 integration tests. Those tests require both raw data files in `data/raw/` and can take several minutes.

## Corrected-V2 reproduction

After obtaining the exact files described in [Data Provenance](DATA_PROVENANCE.md), verify source hashes and run:

```bash
shasum -a 256 data/raw/Online\ Retail.xlsx data/raw/online_retail_II.csv
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python docs/recovery/COMMERCIAL_DS_002B_INTEGRATION.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s docs/recovery -p 'test_COMMERCIAL_DS_*.py' -v
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python docs/recovery/COMMERCIAL_DS_003_PURCHASE_OCCASIONS.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python docs/recovery/COMMERCIAL_DS_003_REVENUE_BRIDGE.py
```

The integration verifies source bytes against frozen references, applies the reviewed overlap correction, validates the taxonomy, and checks row, category, source-content, and customer integrity. Production occasion and bridge entry points repeat checks against actual consumed rows. Frozen pins live beside the recovery scripts and are verified against hard-coded SHA-256 values.

For deterministic output comparisons, capture each command's stdout in a temporary file and compare SHA-256 hashes. Do not put real-data output files in the repository. The most recent Codex-run output hashes and commands are recorded in `docs/recovery/COMMERCIAL_DS_003_STAGE_B2A_INTEGRITY_CLOSURE_HANDOVER.md`; independent B2B-1 review is pending.

## Earlier analytics and optional tooling

- `make pipeline-v1` and `make pipeline-v2` run the earlier reusable pandas workflows; they need their corresponding raw inputs.
- `make churn-v1` and `make churn-v2` train/score the earlier lapse-risk models; outputs are generated under ignored `data/processed/`.
- `make dbt-build` requires the dbt DuckDB dependency and creates a local ignored warehouse.
- `make spark-v1` and `make spark-v2` require a Java runtime. CI skips the local Spark execution when Java is unavailable.
- Databricks validation requires its CLI and an applicable configuration; no cloud deployment is claimed.

The repository keeps old analytic artifacts for traceability. Reproducing an old report may require its notebook-specific environment and should not be mistaken for current corrected-V2 evidence.
