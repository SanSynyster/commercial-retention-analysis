from __future__ import annotations

import argparse

from src.spark_pipeline import get_active_or_local_spark, run_delta_pipeline


def run_databricks_pipeline(
    clean_transactions_path: str,
    target_schema: str,
    catalog: str | None = None,
    write_mode: str = "overwrite",
) -> None:
    """Run Databricks Delta gold-table build using the shared Spark transformations."""

    spark = get_active_or_local_spark("commercial-retention-databricks")
    print(f"Source clean transactions: {clean_transactions_path}")
    print(f"Target schema: {target_schema}")
    if catalog:
        print(f"Target catalog: {catalog}")
    validation = run_delta_pipeline(
        spark,
        clean_transactions_path=clean_transactions_path,
        target_schema=target_schema,
        catalog=catalog,
        write_mode=write_mode,
    )
    print(validation.to_string(index=False))
    print("Databricks Delta pipeline completed successfully.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Databricks Delta gold-table pipeline.")
    parser.add_argument("--clean-transactions-path", required=True, help="Path or table-readable location for clean transaction parquet.")
    parser.add_argument("--target-schema", required=True, help="Schema/database for gold Delta outputs.")
    parser.add_argument("--catalog", default=None, help="Optional Unity Catalog name.")
    parser.add_argument("--write-mode", default="overwrite", choices=["overwrite", "append"], help="Delta write mode.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        run_databricks_pipeline(
            clean_transactions_path=args.clean_transactions_path,
            target_schema=args.target_schema,
            catalog=args.catalog,
            write_mode=args.write_mode,
        )
    except RuntimeError as exc:
        raise SystemExit(f"Databricks pipeline could not start: {exc}") from exc


if __name__ == "__main__":
    main()
