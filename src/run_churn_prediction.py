from __future__ import annotations

import argparse

import pandas as pd

from src.churn_prediction import ChurnModelConfig, run_lapse_risk_pipeline
from src.config import DATASETS, get_dataset_config
from src.validation import validate_lapse_risk_outputs


def run_churn_prediction(dataset: str, processed_dir: str | None = None) -> None:
    """Train and score the lapse-risk model for a processed dataset."""

    config = get_dataset_config(dataset, processed_dir=processed_dir)
    clean_path = config.processed_dir / "clean_transactions.parquet"
    if not clean_path.exists():
        raise FileNotFoundError(
            f"Processed clean transactions not found: {clean_path}. Run the core pipeline first."
        )

    print(f"Running lapse-risk model for {config.name}: {config.description}")
    print(f"Processed input: {clean_path}")
    clean_transactions = pd.read_parquet(clean_path)
    results = run_lapse_risk_pipeline(
        clean_transactions,
        config.processed_dir,
        ChurnModelConfig(),
    )
    validate_lapse_risk_outputs(config.processed_dir)
    selected_model = results["selected_model_name"]
    metrics = results["model_metrics"]
    print(f"Selected model: {selected_model}")
    print(
        "Top-20% precision: "
        f"{float(metrics.loc[0, 'precision_top_20pct']):.3f}; "
        f"ROC-AUC: {float(metrics.loc[0, 'roc_auc']):.3f}"
    )
    print("Lapse-risk pipeline completed successfully.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train and score the lapse-risk churn model.")
    parser.add_argument("--dataset", choices=sorted(DATASETS), required=True, help="Dataset version to score.")
    parser.add_argument(
        "--processed-dir",
        default=None,
        help="Optional override for the processed output directory.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_churn_prediction(dataset=args.dataset, processed_dir=args.processed_dir)


if __name__ == "__main__":
    main()
