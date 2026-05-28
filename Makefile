VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(PYTHON) -m pip

.PHONY: help venv install install-full test pipeline-v1 pipeline-v2

help:
	@printf "Available commands:\n"
	@printf "  make install       Create .venv and install lean runtime dependencies\n"
	@printf "  make install-full  Create .venv and install full notebook environment\n"
	@printf "  make test          Run lightweight unit tests\n"
	@printf "  make pipeline-v1   Run core pipeline for one-year baseline dataset\n"
	@printf "  make pipeline-v2   Run core pipeline for expanded two-year dataset\n"

venv:
	python3 -m venv $(VENV)

install: venv
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements-minimal.txt

install-full: venv
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

test:
	$(PYTHON) -m unittest discover -s tests

pipeline-v1:
	$(PYTHON) -m src.run_pipeline --dataset v1

pipeline-v2:
	$(PYTHON) -m src.run_pipeline --dataset v2
