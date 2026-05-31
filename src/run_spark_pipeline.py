from __future__ import annotations

import argparse

from src.config import DATASETS, get_dataset_config
from src.spark_pipeline import run_spark_pipeline


def run_dataset_spark_pipeline(dataset: str, processed_dir: str | None = None) -> None:
    config = get_dataset_config(dataset, processed_dir=processed_dir)
    print(f"Running Spark metrics for {config.name}: {config.description}")
    print(f"Processed input directory: {config.processed_dir}")
    parity = run_spark_pipeline(config.processed_dir)
    print(parity.to_string(index=False))
    print("Spark pipeline completed successfully.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Spark metric pipeline and parity checks.")
    parser.add_argument("--dataset", choices=sorted(DATASETS), required=True, help="Dataset version to process.")
    parser.add_argument(
        "--processed-dir",
        default=None,
        help="Optional override for the processed output directory.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        run_dataset_spark_pipeline(dataset=args.dataset, processed_dir=args.processed_dir)
    except RuntimeError as exc:
        raise SystemExit(f"Spark pipeline could not start: {exc}") from exc


if __name__ == "__main__":
    main()
