# Databricks notebook source
# COMMAND ----------

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def add_repo_root_to_path() -> None:
    current_path = Path.cwd()
    for candidate in [current_path, *current_path.parents]:
        if (candidate / "src" / "spark_pipeline.py").exists():
            sys.path.insert(0, str(candidate))
            return


add_repo_root_to_path()

from src.run_databricks_pipeline import run_databricks_pipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Databricks wrapper for commercial retention gold marts.")
    parser.add_argument("--clean-transactions-path", required=True)
    parser.add_argument("--target-schema", required=True)
    parser.add_argument("--catalog", default="")
    parser.add_argument("--write-mode", default="overwrite")
    return parser.parse_args()


args = parse_args()
run_databricks_pipeline(
    clean_transactions_path=args.clean_transactions_path,
    target_schema=args.target_schema,
    catalog=args.catalog or None,
    write_mode=args.write_mode,
)
