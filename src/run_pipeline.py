from __future__ import annotations

import argparse

from src.cleaning import build_clean_transactions, write_clean_outputs
from src.config import DATASETS, get_dataset_config
from src.customer_metrics import build_customer_metric_outputs, write_customer_metric_outputs
from src.data_loading import load_raw_transactions
from src.validation import validate_pipeline_outputs


def run_pipeline(dataset: str, validate: bool = True, processed_dir: str | None = None) -> None:
    """Run the reusable cleaning and customer metric pipeline for a dataset."""

    config = get_dataset_config(dataset, processed_dir=processed_dir)
    print(f"Running pipeline for {config.name}: {config.description}")
    print(f"Raw input: {config.raw_path}")
    print(f"Processed output: {config.processed_dir}")

    raw_transactions = load_raw_transactions(config.raw_path)
    clean_transactions, audit_summary = build_clean_transactions(raw_transactions)
    write_clean_outputs(clean_transactions, audit_summary, config.processed_dir)

    metric_outputs = build_customer_metric_outputs(clean_transactions)
    write_customer_metric_outputs(metric_outputs, config.processed_dir)

    if validate:
        validate_pipeline_outputs(config.processed_dir)

    print("Pipeline completed successfully.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the commercial retention analytics core pipeline.")
    parser.add_argument(
        "--dataset",
        choices=sorted(DATASETS),
        required=True,
        help="Dataset version to process.",
    )
    parser.add_argument(
        "--processed-dir",
        default=None,
        help="Optional override for the processed output directory.",
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip output validation checks.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_pipeline(
        dataset=args.dataset,
        validate=not args.skip_validation,
        processed_dir=args.processed_dir,
    )


if __name__ == "__main__":
    main()
