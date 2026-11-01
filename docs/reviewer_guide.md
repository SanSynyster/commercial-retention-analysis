# Review Guide

## Five-Minute Review

- [README](../README.md): scope, verified corrected-V2 results, status, and limitations.
- [Research status](RESEARCH_STATUS.md): completed work and pending review gates.
- [Data provenance](DATA_PROVENANCE.md): official dataset sources, licensing, checksums, and local-data warnings.
- [Recovery evidence index](recovery/README.md): research decisions, audits, contracts, and independent reviews.
- [Latest integrity handover](recovery/COMMERCIAL_DS_003_STAGE_B2A_INTEGRITY_CLOSURE_HANDOVER.md): B2B-1 correction; independent re-review pending.

## Validation Paths

Data-free tests and synthetic validation:

```bash
make validate-ci
```

Corrected-V2 source, taxonomy, occasion, and bridge checks require the exact raw inputs described in [Data Provenance](DATA_PROVENANCE.md):

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s docs/recovery -p 'test_COMMERCIAL_DS_*.py' -v
```

## Existing Engineering Areas

| Area | Evidence |
|---|---|
| Python analytics | `src/`, `tests/` |
| SQL and dbt | `sql/`, `dbt/models/`, `dbt/tests/` |
| Notebooks | `notebooks/` |
| Dashboards | `dashboards/`, dashboard definitions in `docs/` |
| Optional Spark | `src/spark_pipeline.py`, `docs/spark_pipeline.md` |
| Databricks scaffolding | `databricks/`, `docs/databricks_support.md` |

Older outputs are retained for traceability and have not all been re-audited under the current corrected-V2 definitions. A code path or architecture document does not by itself establish production use.
