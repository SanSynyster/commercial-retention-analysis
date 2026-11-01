VENV := .venv
VENV_PYTHON ?= python3.11
PYTHON := $(VENV)/bin/python
PIP := $(PYTHON) -m pip

.PHONY: help venv install install-full test validate-ci validate pipeline-v1 pipeline-v2 churn-v1 churn-v2 spark-v1 spark-v2 databricks-validate dbt-debug dbt-run dbt-test dbt-build dbt-docs

help:
	@printf "Available commands:\n"
	@printf "  make install       Create .venv and install lean runtime dependencies\n"
	@printf "  make install-full  Create .venv and install full notebook environment\n"
	@printf "  make test          Run lightweight unit tests\n"
	@printf "  make validate-ci   Run CI-safe validation without raw data\n"
	@printf "  make validate      Run full local validation path\n"
	@printf "  make pipeline-v1   Run core pipeline for one-year baseline dataset\n"
	@printf "  make pipeline-v2   Run core pipeline for expanded two-year dataset\n"
	@printf "  make churn-v1      Train and score lapse-risk model for baseline dataset\n"
	@printf "  make churn-v2      Train and score lapse-risk model for expanded dataset\n"
	@printf "  make spark-v1      Run Spark metric pipeline for baseline dataset\n"
	@printf "  make spark-v2      Run Spark metric pipeline for expanded dataset\n"
	@printf "  make databricks-validate  Validate Databricks bundle if CLI is installed\n"
	@printf "  make dbt-debug     Validate dbt DuckDB profile configuration\n"
	@printf "  make dbt-run       Build dbt SQL analytics models\n"
	@printf "  make dbt-test      Run dbt schema and reconciliation tests\n"
	@printf "  make dbt-build     Run and test the dbt analytics project\n"
	@printf "  make dbt-docs      Generate dbt documentation site artifacts\n"

venv:
	$(VENV_PYTHON) -m venv $(VENV)

install: venv
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements-minimal.txt

install-full: venv
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

test:
	$(PYTHON) -m unittest discover -s tests

validate-ci: test
	$(PYTHON) -m src.docs_validation
	$(PYTHON) -m src.synthetic_validation

validate: test pipeline-v1 churn-v1 dbt-build

pipeline-v1:
	$(PYTHON) -m src.run_pipeline --dataset v1

pipeline-v2:
	$(PYTHON) -m src.run_pipeline --dataset v2

churn-v1:
	$(PYTHON) -m src.run_churn_prediction --dataset v1

churn-v2:
	$(PYTHON) -m src.run_churn_prediction --dataset v2

spark-v1:
	$(PYTHON) -m src.run_spark_pipeline --dataset v1

spark-v2:
	$(PYTHON) -m src.run_spark_pipeline --dataset v2

databricks-validate:
	@if command -v databricks >/dev/null 2>&1; then \
		databricks bundle validate -t dev --config-file databricks/databricks.yml; \
	else \
		printf "Databricks CLI is not installed. Install it before bundle validation.\n"; \
	fi

dbt-debug:
	mkdir -p data/warehouse
	DBT_TARGET_PATH=dbt/target $(VENV)/bin/dbt debug --profiles-dir profiles

dbt-run:
	mkdir -p data/warehouse
	DBT_TARGET_PATH=dbt/target $(VENV)/bin/dbt run --profiles-dir profiles

dbt-test:
	mkdir -p data/warehouse
	DBT_TARGET_PATH=dbt/target $(VENV)/bin/dbt test --profiles-dir profiles

dbt-build:
	mkdir -p data/warehouse
	DBT_TARGET_PATH=dbt/target $(VENV)/bin/dbt build --profiles-dir profiles

dbt-docs:
	mkdir -p data/warehouse
	DBT_TARGET_PATH=dbt/target $(VENV)/bin/dbt docs generate --profiles-dir profiles
