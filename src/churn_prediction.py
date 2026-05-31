from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, precision_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from src.customer_metrics import standardize_processed_columns


TARGET_COLUMN = "lapsed_next_90_days"
FEATURE_COLUMNS = [
    "recency_days",
    "customer_age_days",
    "active_days",
    "avg_days_between_orders",
    "orders_per_active_day",
    "total_orders",
    "log_revenue",
    "log_avg_order_value",
    "avg_order_quantity",
    "avg_order_lines",
    "days_to_second_purchase",
    "is_repeat_customer",
    "is_high_value",
    "country_group",
    "snapshot_month",
]
CATEGORICAL_FEATURES = ["country_group", "snapshot_month"]
NUMERIC_FEATURES = [column for column in FEATURE_COLUMNS if column not in CATEGORICAL_FEATURES]
RISK_DECILE_LABELS = [
    "Top 10%",
    "10-20%",
    "20-30%",
    "30-40%",
    "40-50%",
    "50-60%",
    "60-70%",
    "70-80%",
    "80-90%",
    "Bottom 10%",
]


@dataclass(frozen=True)
class ChurnModelConfig:
    """Configuration for rolling-snapshot lapse-risk modelling."""

    target_window_days: int = 90
    min_history_months: int = 3
    test_snapshot_pct: float = 0.30
    random_state: int = 42
    permutation_sample_size: int = 2000


def build_order_features(clean_transactions: pd.DataFrame) -> pd.DataFrame:
    """Build customer invoice-level order features from clean transaction lines."""

    transactions = standardize_processed_columns(clean_transactions)
    required_columns = {
        "customer_id",
        "invoice_no",
        "invoice_date",
        "quantity",
        "country",
        "is_valid_order_line",
        "analytical_revenue",
    }
    missing_columns = sorted(required_columns - set(transactions.columns))
    if missing_columns:
        raise ValueError(f"Processed transaction data is missing columns: {missing_columns}")

    transactions["invoice_date"] = pd.to_datetime(transactions["invoice_date"])
    valid_lines = transactions[transactions["is_valid_order_line"]].copy()
    orders = (
        valid_lines.groupby(["customer_id", "invoice_no"], as_index=False)
        .agg(
            order_date=("invoice_date", "min"),
            order_revenue=("analytical_revenue", "sum"),
            order_quantity=("quantity", "sum"),
            order_lines=("invoice_no", "size"),
            country=("country", first_non_null),
        )
    )
    orders = orders[orders["order_revenue"] > 0].copy()
    orders = orders.sort_values(["customer_id", "order_date", "invoice_no"]).reset_index(drop=True)
    orders["order_rank"] = orders.groupby("customer_id").cumcount() + 1
    return orders


def first_non_null(values: pd.Series) -> object:
    non_null_values = values.dropna()
    if non_null_values.empty:
        return pd.NA
    return non_null_values.iloc[0]


def build_lapse_snapshot_features(
    orders: pd.DataFrame,
    config: ChurnModelConfig | None = None,
) -> pd.DataFrame:
    """Create monthly customer snapshots using only pre-snapshot behavior."""

    model_config = config or ChurnModelConfig()
    order_data = orders.copy()
    order_data["order_date"] = pd.to_datetime(order_data["order_date"])
    min_date = order_data["order_date"].min()
    max_date = order_data["order_date"].max()
    snapshot_dates = pd.date_range(
        min_date + pd.DateOffset(months=model_config.min_history_months),
        max_date - pd.Timedelta(days=model_config.target_window_days),
        freq="MS",
    )
    if len(snapshot_dates) == 0:
        raise ValueError("Not enough order history to build full-observation lapse snapshots.")

    rows = []
    for snapshot_date in snapshot_dates:
        history = order_data[order_data["order_date"] < snapshot_date].copy()
        future = order_data[
            (order_data["order_date"] >= snapshot_date)
            & (order_data["order_date"] <= snapshot_date + pd.Timedelta(days=model_config.target_window_days))
        ]
        if history.empty:
            continue

        customer_features = (
            history.groupby("customer_id", as_index=False)
            .agg(
                total_orders=("invoice_no", "nunique"),
                revenue=("order_revenue", "sum"),
                avg_order_value=("order_revenue", "mean"),
                avg_order_quantity=("order_quantity", "mean"),
                avg_order_lines=("order_lines", "mean"),
                first_purchase=("order_date", "min"),
                last_purchase=("order_date", "max"),
                country=("country", first_non_null),
            )
        )
        customer_features["snapshot_date"] = snapshot_date
        customer_features["recency_days"] = (snapshot_date - customer_features["last_purchase"]).dt.days
        customer_features["customer_age_days"] = (
            snapshot_date - customer_features["first_purchase"]
        ).dt.days
        customer_features["active_days"] = (
            customer_features["last_purchase"] - customer_features["first_purchase"]
        ).dt.days
        customer_features["avg_days_between_orders"] = np.where(
            customer_features["total_orders"] > 1,
            customer_features["active_days"] / (customer_features["total_orders"] - 1),
            np.nan,
        )
        customer_features["orders_per_active_day"] = (
            customer_features["total_orders"] / customer_features["customer_age_days"].clip(lower=1)
        )
        customer_features["is_repeat_customer"] = customer_features["total_orders"].gt(1).astype(int)

        second_orders = history[history["order_rank"] == 2][
            ["customer_id", "order_date"]
        ].rename(columns={"order_date": "second_purchase"})
        first_orders = history[history["order_rank"] == 1][
            ["customer_id", "order_date"]
        ].rename(columns={"order_date": "first_purchase_for_second"})
        days_to_second = first_orders.merge(second_orders, on="customer_id", how="inner")
        days_to_second["days_to_second_purchase"] = (
            days_to_second["second_purchase"] - days_to_second["first_purchase_for_second"]
        ).dt.days
        customer_features = customer_features.merge(
            days_to_second[["customer_id", "days_to_second_purchase"]],
            on="customer_id",
            how="left",
        )

        customer_features = customer_features.sort_values("revenue", ascending=False).reset_index(drop=True)
        customer_features["revenue_rank_pct"] = (customer_features.index + 1) / len(customer_features)
        customer_features["is_high_value"] = customer_features["revenue_rank_pct"].le(0.10).astype(int)
        future_customers = set(future["customer_id"].unique())
        customer_features[TARGET_COLUMN] = (~customer_features["customer_id"].isin(future_customers)).astype(int)
        rows.append(customer_features)

    if not rows:
        raise ValueError("No lapse snapshots were created from the available order history.")

    snapshot_data = pd.concat(rows, ignore_index=True)
    snapshot_data["log_revenue"] = np.log1p(snapshot_data["revenue"])
    snapshot_data["log_avg_order_value"] = np.log1p(snapshot_data["avg_order_value"])
    snapshot_data["snapshot_month"] = snapshot_data["snapshot_date"].dt.month.astype(str)
    snapshot_data["country_group"] = np.where(
        snapshot_data["country"].eq("United Kingdom"), "United Kingdom", "International"
    )
    return snapshot_data


def split_snapshots(snapshot_data: pd.DataFrame, test_snapshot_pct: float = 0.30) -> tuple[pd.DataFrame, pd.DataFrame, pd.Timestamp]:
    """Split snapshots by time so later snapshots simulate future scoring."""

    unique_snapshots = sorted(pd.to_datetime(snapshot_data["snapshot_date"]).unique())
    if len(unique_snapshots) < 2:
        raise ValueError("At least two snapshot dates are required for a time-based train/test split.")
    split_index = max(1, int(len(unique_snapshots) * (1 - test_snapshot_pct)))
    split_snapshot = pd.Timestamp(unique_snapshots[min(split_index, len(unique_snapshots) - 1)])
    train_data = snapshot_data[snapshot_data["snapshot_date"] < split_snapshot].copy()
    test_data = snapshot_data[snapshot_data["snapshot_date"] >= split_snapshot].copy()
    if train_data.empty or test_data.empty:
        raise ValueError("Time-based split produced an empty train or test set.")
    return train_data, test_data, split_snapshot


def build_model_candidates(random_state: int = 42) -> dict[str, Pipeline]:
    """Return production-style sklearn pipelines for lapse-risk modelling."""

    numeric_preprocess = Pipeline(
        steps=[("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler())]
    )
    categorical_preprocess = Pipeline(
        steps=[("imputer", SimpleImputer(strategy="most_frequent")), ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False))]
    )
    preprocess = ColumnTransformer(
        transformers=[
            ("numeric", numeric_preprocess, NUMERIC_FEATURES),
            ("categorical", categorical_preprocess, CATEGORICAL_FEATURES),
        ]
    )
    return {
        "Logistic Regression": Pipeline(
            steps=[
                ("preprocess", preprocess),
                ("model", LogisticRegression(max_iter=1000, class_weight="balanced", random_state=random_state)),
            ]
        ),
        "Random Forest": Pipeline(
            steps=[
                ("preprocess", preprocess),
                (
                    "model",
                    RandomForestClassifier(
                        n_estimators=120,
                        min_samples_leaf=10,
                        class_weight="balanced_subsample",
                        random_state=random_state,
                        n_jobs=-1,
                    ),
                ),
            ]
        ),
        "Histogram Gradient Boosting": Pipeline(
            steps=[
                ("preprocess", preprocess),
                ("model", HistGradientBoostingClassifier(max_iter=120, random_state=random_state)),
            ]
        ),
    }


def precision_at_top_pct(y_true: pd.Series, scores: np.ndarray, top_pct: float) -> float:
    scored = pd.DataFrame({"target": y_true.to_numpy(), "score": scores}).sort_values(
        "score", ascending=False
    )
    top_n = max(1, int(np.ceil(len(scored) * top_pct)))
    return precision_score(scored.head(top_n)["target"], np.ones(top_n), zero_division=0)


def train_lapse_risk_models(
    snapshot_data: pd.DataFrame,
    config: ChurnModelConfig | None = None,
) -> dict[str, object]:
    """Train candidate models, select the strongest CRM prioritization model, and score snapshots."""

    model_config = config or ChurnModelConfig()
    train_data, test_data, split_snapshot = split_snapshots(snapshot_data, model_config.test_snapshot_pct)
    x_train = train_data[FEATURE_COLUMNS]
    y_train = train_data[TARGET_COLUMN]
    x_test = test_data[FEATURE_COLUMNS]
    y_test = test_data[TARGET_COLUMN]

    metrics = []
    fitted_models = {}
    for model_name, model in build_model_candidates(model_config.random_state).items():
        model.fit(x_train, y_train)
        scores = model.predict_proba(x_test)[:, 1]
        metrics.append(
            {
                "model": model_name,
                "train_rows": len(train_data),
                "test_rows": len(test_data),
                "split_snapshot": split_snapshot,
                "test_target_rate": y_test.mean(),
                "roc_auc": roc_auc_score(y_test, scores),
                "pr_auc": average_precision_score(y_test, scores),
                "precision_top_10pct": precision_at_top_pct(y_test, scores, 0.10),
                "precision_top_20pct": precision_at_top_pct(y_test, scores, 0.20),
                "brier_score": brier_score_loss(y_test, scores),
            }
        )
        fitted_models[model_name] = model

    model_metrics = pd.DataFrame(metrics).sort_values(
        ["precision_top_20pct", "roc_auc"], ascending=False
    ).reset_index(drop=True)
    selected_model_name = str(model_metrics.loc[0, "model"])
    selected_model = fitted_models[selected_model_name]

    scored_snapshots = snapshot_data.copy()
    scored_snapshots["lapse_risk_score"] = selected_model.predict_proba(
        scored_snapshots[FEATURE_COLUMNS]
    )[:, 1]
    scored_snapshots["data_split"] = np.where(
        scored_snapshots["snapshot_date"] < split_snapshot, "train", "test"
    )
    lift = build_lapse_risk_lift(scored_snapshots)
    scores = build_latest_scores(scored_snapshots)
    feature_importance = build_feature_importance(
        selected_model,
        test_data,
        model_config.permutation_sample_size,
        model_config.random_state,
    )

    return {
        "model_metrics": model_metrics,
        "selected_model_name": selected_model_name,
        "selected_model": selected_model,
        "scored_snapshots": scored_snapshots,
        "lapse_risk_lift": lift,
        "lapse_risk_scores": scores,
        "lapse_risk_feature_importance": feature_importance,
        "split_snapshot": split_snapshot,
    }


def build_lapse_risk_lift(scored_snapshots: pd.DataFrame) -> pd.DataFrame:
    """Build test-set lift by predicted risk decile."""

    test_scored = scored_snapshots[scored_snapshots["data_split"] == "test"].copy()
    test_scored = test_scored.sort_values("lapse_risk_score", ascending=False).reset_index(drop=True)
    if len(test_scored) < 10:
        test_scored["risk_decile"] = "Top 10%"
    else:
        test_scored["risk_decile"] = pd.qcut(
            test_scored.index + 1,
            10,
            labels=RISK_DECILE_LABELS,
        )
    overall_test_lapse_rate = test_scored[TARGET_COLUMN].mean()
    lift = (
        test_scored.groupby("risk_decile", observed=False)
        .agg(
            customers=("customer_id", "count"),
            observed_lapse_rate=(TARGET_COLUMN, "mean"),
            avg_risk_score=("lapse_risk_score", "mean"),
            high_value_customers=("is_high_value", "sum"),
        )
        .reset_index()
    )
    lift["lift_vs_test_average"] = lift["observed_lapse_rate"] / overall_test_lapse_rate
    return lift


def build_latest_scores(scored_snapshots: pd.DataFrame) -> pd.DataFrame:
    """Return latest full-observation snapshot scores for CRM consumption."""

    latest_snapshot = scored_snapshots["snapshot_date"].max()
    scores = scored_snapshots[scored_snapshots["snapshot_date"] == latest_snapshot].copy()
    scores = scores.sort_values("lapse_risk_score", ascending=False).reset_index(drop=True)
    if len(scores) < 3:
        scores["risk_band"] = "High risk"
    else:
        scores["risk_band"] = pd.qcut(
            scores["lapse_risk_score"].rank(method="first"),
            q=[0, 0.5, 0.8, 1.0],
            labels=["Low risk", "Medium risk", "High risk"],
        )
    return scores[
        [
            "customer_id",
            "snapshot_date",
            "lapse_risk_score",
            "risk_band",
            TARGET_COLUMN,
            "recency_days",
            "total_orders",
            "revenue",
            "is_high_value",
            "data_split",
        ]
    ]


def build_feature_importance(
    selected_model: Pipeline,
    test_data: pd.DataFrame,
    sample_size: int,
    random_state: int,
) -> pd.DataFrame:
    """Estimate raw feature importance using permutation importance on test data."""

    sample = test_data.sample(n=min(sample_size, len(test_data)), random_state=random_state)
    importance = permutation_importance(
        selected_model,
        sample[FEATURE_COLUMNS],
        sample[TARGET_COLUMN],
        n_repeats=5,
        random_state=random_state,
        scoring="roc_auc",
    )
    return pd.DataFrame(
        {
            "feature": FEATURE_COLUMNS,
            "importance": importance.importances_mean,
            "importance_std": importance.importances_std,
        }
    ).sort_values("importance", ascending=False)


def write_lapse_risk_outputs(results: dict[str, object], processed_dir: str | Path) -> None:
    """Persist churn prediction outputs using the existing notebook-compatible names."""

    output_dir = Path(processed_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(results["model_metrics"]).to_csv(output_dir / "lapse_risk_model_metrics.csv", index=False)
    pd.DataFrame(results["lapse_risk_scores"]).to_csv(output_dir / "lapse_risk_scores.csv", index=False)
    pd.DataFrame(results["lapse_risk_lift"]).to_csv(output_dir / "lapse_risk_lift.csv", index=False)
    pd.DataFrame(results["lapse_risk_feature_importance"]).to_csv(
        output_dir / "lapse_risk_feature_importance.csv", index=False
    )
    joblib.dump(results["selected_model"], output_dir / "lapse_risk_model.joblib")


def run_lapse_risk_pipeline(
    clean_transactions: pd.DataFrame,
    processed_dir: str | Path,
    config: ChurnModelConfig | None = None,
) -> dict[str, object]:
    """Build features, train, score, and persist the lapse-risk model layer."""

    orders = build_order_features(clean_transactions)
    snapshots = build_lapse_snapshot_features(orders, config)
    results = train_lapse_risk_models(snapshots, config)
    write_lapse_risk_outputs(results, processed_dir)
    return results
