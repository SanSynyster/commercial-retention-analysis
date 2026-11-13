"""P3-008A audit and private stratified split for the Hillstrom email experiment.

The input and row-level split assignments are kept under source_data, outside Git.
This module audits randomisation and defines a frozen split; it does not train models.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from scipy.stats import chisquare
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT.parent / "source_data/hillstrom/Kevin_Hillstrom_MineThatData_E-MailAnalytics_DataMiningChallenge_2008.03.20.csv"
DEFAULT_OUTPUT = ROOT.parent / "source_data/hillstrom/p3_008a_outputs"
ORIGINAL_SOURCE_URL = "https://blog.minethatdata.com/2008/03/minethatdata-e-mail-analytics-and-data.html"
ORIGINAL_CSV_URL = "http://www.minethatdata.com/Kevin_Hillstrom_MineThatData_E-MailAnalytics_DataMiningChallenge_2008.03.20.csv"
SEED = 20261114
ARMS = ("Mens E-Mail", "Womens E-Mail", "No E-Mail")
OUTCOMES = ("visit", "conversion", "spend")
FEATURES = ("recency", "history", "mens", "womens", "newbie",
            "history_segment", "zip_code", "channel")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def standardized_mean_differences(frame: pd.DataFrame) -> dict[str, dict[str, float]]:
    """Pairwise SMDs; categorical variables are represented by level indicators."""
    groups = {arm: frame.loc[frame.segment.eq(arm)] for arm in ARMS}
    expanded: dict[str, pd.Series] = {}
    for col in FEATURES:
        if pd.api.types.is_numeric_dtype(frame[col]):
            expanded[col] = frame[col].astype(float)
        else:
            for value in sorted(frame[col].dropna().astype(str).unique()):
                expanded[f"{col}={value}"] = frame[col].astype(str).eq(value).astype(float)
    results: dict[str, dict[str, float]] = {}
    for i, left in enumerate(ARMS):
        for right in ARMS[i + 1:]:
            values = {}
            for name, series in expanded.items():
                x, y = series.loc[groups[left].index], series.loc[groups[right].index]
                pooled = np.sqrt((x.var(ddof=1) + y.var(ddof=1)) / 2)
                values[name] = float((x.mean() - y.mean()) / pooled) if pooled > 0 else 0.0
            results[f"{left} vs {right}"] = values
    return results


def make_stratified_split(frame: pd.DataFrame, seed: int = SEED) -> pd.DataFrame:
    """Create fixed 60/20/20 row split, stratified by randomized assignment arm."""
    if "segment" not in frame or frame.segment.isna().any():
        raise ValueError("A complete randomized treatment assignment is required.")
    row_index = np.arange(len(frame))
    train_dev, test = train_test_split(row_index, test_size=0.20, random_state=seed,
                                       stratify=frame.segment)
    train, development = train_test_split(train_dev, test_size=0.25, random_state=seed,
                                          stratify=frame.iloc[train_dev].segment)
    out = pd.DataFrame({"row_index": row_index, "split": ""})
    out.loc[train, "split"] = "train"
    out.loc[development, "split"] = "development"
    out.loc[test, "split"] = "test"
    return out


def audit_dataset(path: Path, output_dir: Path, seed: int = SEED) -> dict:
    frame = pd.read_csv(path)
    expected = {"recency", "history_segment", "history", "mens", "womens",
                "zip_code", "newbie", "channel", "segment", "visit", "conversion", "spend"}
    if set(frame.columns) != expected:
        raise ValueError(f"Unexpected schema: {list(frame.columns)}")
    if frame.segment.isna().any() or set(frame.segment.unique()) != set(ARMS):
        raise ValueError("Unexpected treatment categories or missing assignments.")
    if not frame.visit.isin([0, 1]).all() or not frame.conversion.isin([0, 1]).all():
        raise ValueError("Binary outcomes have invalid values.")
    if not frame.mens.isin([0, 1]).all() or not frame.womens.isin([0, 1]).all():
        raise ValueError("Historical merchandise indicators must be binary.")
    if (frame.spend < 0).any() or not np.isfinite(frame.spend).all():
        raise ValueError("Spend must be finite and nonnegative.")
    if not frame.spend.gt(0).eq(frame.conversion.eq(1)).all():
        raise ValueError("Positive spend must correspond exactly to conversion.")
    if not frame.loc[frame.conversion.eq(1), "visit"].eq(1).all():
        raise ValueError("A conversion without a visit was observed.")

    split = make_stratified_split(frame, seed)
    output_dir.mkdir(parents=True, exist_ok=True)
    split_path = output_dir / "hillstrom_row_split_private.csv"
    split.to_csv(split_path, index=False)
    assignment_counts = pd.crosstab(frame.segment, split.split).reindex(index=ARMS)
    pooled = {outcome: {"mean": float(frame[outcome].mean()),
                        "positive_n": int(frame[outcome].gt(0).sum()),
                        "zero_n": int(frame[outcome].eq(0).sum()),
                        "zero_share": float(frame[outcome].eq(0).mean())}
              for outcome in OUTCOMES}
    # For the untouched test split, record only allocation counts, not outcomes.
    train_dev_stats = {}
    for split_name in ("train", "development"):
        block = frame.loc[split.split.eq(split_name)]
        train_dev_stats[split_name] = {"n": int(len(block)), "by_arm": {}}
        for arm in ARMS:
            arm_frame = block.loc[block.segment.eq(arm)]
            train_dev_stats[split_name]["by_arm"][arm] = {
                "n": int(len(arm_frame)),
                **{outcome: {"positive_n": int(arm_frame[outcome].gt(0).sum()),
                             "mean": float(arm_frame[outcome].mean())}
                   for outcome in OUTCOMES},
            }
    smd = standardized_mean_differences(frame)
    result = {
        "dataset": {"rows": int(len(frame)), "columns": int(frame.shape[1]),
                    "column_names": list(frame.columns), "missing_cells": int(frame.isna().sum().sum()),
                    "exact_duplicate_rows": int(frame.duplicated().sum()),
                    "customer_identifier_present": False,
                    "distinct_pre_treatment_feature_rows": int(frame[list(FEATURES)].drop_duplicates().shape[0]),
                    "raw_file": str(path), "raw_sha256": sha256(path),
                    "retrieval_source_page": ORIGINAL_SOURCE_URL,
                    "retrieval_file_url": ORIGINAL_CSV_URL,
                    "row_split_sha256": sha256(split_path)},
        "assignment": {"arm_counts": frame.segment.value_counts().reindex(ARMS).astype(int).to_dict(),
                       "allocation_chi_square": float(chisquare(
                           frame.segment.value_counts().reindex(ARMS).to_numpy()).statistic),
                       "allocation_chi_square_p": float(chisquare(
                           frame.segment.value_counts().reindex(ARMS).to_numpy()).pvalue),
                       "pre_treatment_pairwise_smd": smd,
                       "max_abs_smd_by_contrast": {k: max(map(abs, v.values())) for k, v in smd.items()}},
        "outcomes_pooled_full_sample_only": pooled,
        "split": {"seed": seed, "fractions": {"train": .60, "development": .20, "test": .20},
                  "allocation_by_arm": assignment_counts.astype(int).to_dict(),
                  "train_development_event_counts": train_dev_stats,
                  "test_outcomes_examined": False},
        "feature_types": {col: str(frame[col].dtype) for col in frame.columns},
        "outcome_checks": {"spend_without_conversion_n": int((frame.spend.gt(0) & frame.conversion.eq(0)).sum()),
                           "conversion_without_visit_n": int((frame.conversion.eq(1) & frame.visit.eq(0)).sum()),
                           "visit_without_conversion_n": int((frame.visit.eq(1) & frame.conversion.eq(0)).sum()),
                           "max_spend": float(frame.spend.max())},
    }
    (output_dir / "hillstrom_audit_aggregate_private.json").write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()
    if ROOT == args.output_dir.resolve() or ROOT in args.output_dir.resolve().parents:
        raise ValueError("Row-level split and audit outputs must remain outside the repository.")
    result = audit_dataset(args.dataset, args.output_dir, args.seed)
    print(json.dumps({"dataset": result["dataset"], "assignment": result["assignment"],
                      "split": result["split"]}, indent=2))


if __name__ == "__main__":
    main()
