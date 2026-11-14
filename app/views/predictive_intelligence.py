"""Aggregate-only interactive view of completed Phase 3 predictive research."""
from __future__ import annotations

import os
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from p3_predictive_bundle import BundleError, DEFAULT_BUNDLE, load_bundle

BUNDLE_ENV = "P3_PREDICTIVE_BUNDLE"
MODEL_ORDER = ["Logistic C", "Frequency", "Random Forest", "HistGradientBoosting", "XGBoost", "LightGBM"]
LABELS = {
    "Logistic C": "Logistic Regression",
    "Frequency": "Frequency baseline",
    "Random Forest": "Random Forest",
    "HistGradientBoosting": "Histogram Gradient Boosting",
    "XGBoost": "XGBoost",
    "LightGBM": "LightGBM",
}
PAIRED_INTERVAL_FORMATS = {
    "Difference": "{:+.4f}",
    "95% lower": "{:+.4f}",
    "95% upper": "{:+.4f}",
}


@st.cache_data(show_spinner=False)
def _load(path: str) -> dict:
    return load_bundle(Path(path))


def _bundle_path() -> str:
    return os.environ.get(BUNDLE_ENV, str(DEFAULT_BUNDLE))


def render() -> None:
    st.title("Predictive Intelligence")
    try:
        bundle = _load(_bundle_path())
    except BundleError as exc:
        st.error(f"The aggregate predictive bundle could not be loaded, so no results are shown. {exc}")
        st.caption(f"Expected file: {Path(_bundle_path()).name}. Rebuild with `python -m src.p3_predictive_bundle --build` when reviewed private aggregates are available.")
        return

    st.caption("**Historical prediction.** This page summarizes the established-customer 30-day purchase task; it does not estimate the effect of marketing contact.")
    tab_models, tab_shap, tab_calibration = st.tabs(["Model comparison", "Global SHAP", "Calibration"])
    with tab_models:
        _render_model_comparison(bundle)
    with tab_shap:
        _render_shap(bundle)
    with tab_calibration:
        _render_calibration(bundle)
    with st.expander("Task, provenance and scientific limits"):
        task = bundle["task"]
        st.markdown(
            f"**Task:** {task['name']}. Outcome: {task['outcome']}. Features: {task['features']}. "
            f"Development uses {task['development_period']} ({task['development_snapshots']:,} snapshots; "
            f"{task['development_customers']:,} customers). The July–November 2011 period "
            f"({task['holdout_snapshots']:,} snapshots) was previously examined and is exploratory."
        )
        st.caption(bundle["selection"]["uncertainty_note"])
        st.caption("High purchase propensity is not treatment uplift. No per-customer scores or explanations are available in this application bundle.")
        for name, source in bundle["provenance"]["sources"].items():
            st.caption(f"{name}: {source['report']} · {Path(source['source_file']).name} · SHA-256 {source['sha256_raw_file'][:12]}…")


def _render_model_comparison(bundle: dict) -> None:
    st.subheader("M2 next-month purchase propensity")
    period_choice = st.radio(
        "Evaluation period",
        ["Development — model selection", "Previously examined holdout — exploratory"],
        horizontal=True,
        key="p3_predictive_period",
    )
    period = "development" if period_choice.startswith("Development") else "holdout"
    st.caption(
        "Pooled out-of-fold results over four March–June development origins. The selected settings were evaluated on the folds used for model selection."
        if period == "development" else
        "July–November 2011 results are an exploratory replay of a previously examined holdout, not independent confirmation."
    )
    st.caption("Model comparison pools March–June development folds (17,221 snapshots); calibration uses the matched April–June evaluation population (12,961 snapshots). The metrics therefore use different populations.")
    metric_label = st.selectbox("Chart metric", ["ROC-AUC", "Average precision"], key="p3_predictive_metric")
    metric = "roc_auc" if metric_label == "ROC-AUC" else "average_precision"
    rows = []
    for model in MODEL_ORDER:
        record = bundle["models"][model]
        performance = record[period]
        rows.append({
            "Model": LABELS[model],
            "ROC-AUC": performance["roc_auc"],
            "Average precision": performance["average_precision"],
            "Top-decile precision": performance["top_decile_precision"],
            "Status": record["selection_status"],
        })
    table = pd.DataFrame(rows)
    chart_data = table[["Model", metric_label]].copy()
    chart = alt.Chart(chart_data).mark_bar().encode(
        x=alt.X("Model:N", sort=None, axis=alt.Axis(labelAngle=-25, labelLimit=200), title=None),
        y=alt.Y(f"{metric_label}:Q", title=metric_label, scale=alt.Scale(domain=[0, 1])),
        color=alt.Color("Model:N", legend=None),
        tooltip=["Model", alt.Tooltip(f"{metric_label}:Q", format=".4f")],
    ).properties(height=260)
    st.altair_chart(chart, width="stretch")
    st.dataframe(table.style.format({"ROC-AUC": "{:.4f}", "Average precision": "{:.4f}", "Top-decile precision": "{:.1%}"}), hide_index=True, width="stretch")
    st.info("Random Forest remains the development reference. It led the four-fold mean AP selection; XGBoost and LightGBM did not meet the predeclared adoption criteria. Differences among the tree models are small and uncertain; these metrics do not establish future-period generalisation or causal CRM value.")
    with st.expander("Available paired ranking intervals"):
        comparisons = bundle["comparisons"]
        diff_rows = []
        for comparison, values in comparisons.items():
            is_holdout_comparison = comparison.lower().startswith("exploratory holdout:")
            if period == "holdout" and not is_holdout_comparison:
                continue
            if period == "development" and is_holdout_comparison:
                continue
            for metric_name, result in values.items():
                diff_rows.append({
                    "Comparison": comparison,
                    "Metric": "ROC-AUC" if metric_name == "roc_auc" else "Average precision",
                    "Difference": result["estimate"],
                    "95% lower": result["ci95"][0],
                    "95% upper": result["ci95"][1],
                })
        if diff_rows:
            st.dataframe(_format_paired_ranking_table(pd.DataFrame(diff_rows)), hide_index=True, width="stretch")
            st.caption("Paired customer-cluster bootstrap intervals condition on fitted predictions/configurations and the evaluated periods. They do not include model-selection or future-period uncertainty.")


def _format_paired_ranking_table(table: pd.DataFrame) -> pd.io.formats.style.Styler:
    """Format signed paired differences and confidence bounds for display."""
    return table.style.format(PAIRED_INTERVAL_FORMATS)


def _render_shap(bundle: dict) -> None:
    shap = bundle["shap"]
    st.subheader("Random Forest global feature attribution")
    st.caption("P3-004 SHAP decomposes class-1 purchase probability. Mean absolute SHAP is average attribution magnitude, not causal importance.")
    periods = ["Development overall", "March", "April", "May", "June", "Exploratory holdout months"]
    selected_period = st.selectbox("SHAP population", periods, key="p3_shap_period")
    importance = shap["overall_development"]
    if selected_period != "Development overall":
        series = shap["development_by_period"] if selected_period != "Exploratory holdout months" else shap["exploratory_holdout_by_month"]
        if selected_period == "Exploratory holdout months":
            month = st.selectbox("Exploratory month", [p["period"] for p in series], key="p3_shap_holdout_month")
            chosen = next(p for p in series if p["period"] == month)
        else:
            month = "2011-" + {"March": "03", "April": "04", "May": "05", "June": "06"}[selected_period]
            chosen = next(p for p in series if p["period"] == month)
        importance = chosen["features"]
    feature = st.selectbox("Feature", [r["feature"] for r in importance], key="p3_shap_feature")
    value_kind = st.radio("Attribution summary", ["Mean absolute contribution", "Mean signed contribution"], horizontal=True, key="p3_shap_value_kind")
    field = "mean_abs" if value_kind.startswith("Mean absolute") else "mean_signed"
    if field == "mean_signed" and "mean_signed" not in importance[0]:
        st.warning("Signed SHAP means are not available for this period-level aggregate.")
    else:
        plotted = sorted(importance, key=lambda x: x[field], reverse=(field == "mean_abs"))
        data = pd.DataFrame([{"Feature": r["feature"], "Contribution": r[field]} for r in plotted])
        chart = alt.Chart(data).mark_bar().encode(
            x=alt.X("Contribution:Q", title="Probability contribution"),
            y=alt.Y("Feature:N", sort="-x", title=None),
            color=alt.condition(alt.datum.Contribution >= 0, alt.value("#147D83"), alt.value("#C27B55")),
            tooltip=["Feature", alt.Tooltip("Contribution:Q", format=".4f")],
        ).properties(height=350)
        st.altair_chart(chart, width="stretch")
        focused = next((x for x in importance if x["feature"] == feature), None)
        if focused:
            st.metric(f"{value_kind}: {feature}", f"{focused[field]:.4f} probability units", help="0.01 probability units = 1 percentage point.")
    if selected_period == "Development overall":
        trend_rows = []
        for period_data in shap["development_by_period"]:
            item = next(x for x in period_data["features"] if x["feature"] == feature)
            trend_rows.append({"Period": period_data["period"], "Population": "Development", "Mean absolute SHAP": item["mean_abs"]})
        if st.checkbox("Include exploratory holdout months", value=False, key="p3_shap_include_holdout"):
            for period_data in shap["exploratory_holdout_by_month"]:
                item = next(x for x in period_data["features"] if x["feature"] == feature)
                trend_rows.append({"Period": period_data["period"], "Population": "Previously examined holdout", "Mean absolute SHAP": item["mean_abs"]})
        trend = pd.DataFrame(trend_rows)
        trend_chart = alt.Chart(trend).mark_line(point=True).encode(
            x=alt.X("Period:O", title="Explanation period", sort=None),
            y=alt.Y("Mean absolute SHAP:Q", title="Mean absolute attribution (probability units)"),
            color=alt.Color("Population:N", title=None),
            tooltip=["Period", "Population", alt.Tooltip("Mean absolute SHAP:Q", format=".4f")],
        ).properties(height=180)
        st.caption(f"Fold-wise mean absolute SHAP for the selected feature: {feature}. Fold models/backgrounds differ; the holdout option is exploratory.")
        st.altair_chart(trend_chart, width="stretch")
    stability = shap["rank_stability"]
    stability_df = pd.DataFrame([{"Fold pair": f"{x['period_a']} · {x['period_b']}", "Spearman rank correlation": x["spearman"]} for x in stability])
    st.caption(f"Development importance ranking correlations range {stability_df['Spearman rank correlation'].min():.3f}–{stability_df['Spearman rank correlation'].max():.3f}; April and May share an identical fitted model. Holdout summaries are exploratory.")
    with st.expander("Correlated features and interpretation"):
        st.markdown(shap["correlation_limit"])
        st.dataframe(pd.DataFrame(shap["correlated_groups"]), hide_index=True, width="stretch")
        st.caption("The SHAP summaries use sampled validation rows and training-only backgrounds. Correlated predictors can share attribution; the forest profiles do not identify a causal mechanism.")


def _render_calibration(bundle: dict) -> None:
    calibration = bundle["calibration"]
    st.subheader("Random Forest probability calibration")
    st.caption("Calibration uses the matched April–June evaluation population (12,961 snapshots), while model comparison pools March–June development folds (17,221 snapshots). These are different populations.")
    period = st.radio("Calibration evaluation", ["Development — April to June", "Previously examined holdout — July to November"], horizontal=True, key="p3_cal_period")
    if period.startswith("Development"):
        dev = calibration["development"]
        rows = []
        for label, key in (("Uncalibrated reference", "uncalibrated"), ("Intercept-only candidate", "intercept_only")):
            m = dev[key]
            rows.append({"Method": label, "Brier": m["brier"], "Log loss": m["log_loss"], "ROC-AUC": m["roc_auc"], "AP": m["average_precision"], "Mean predicted": m["mean_predicted"], "Observed prevalence": m["observed_prevalence"]})
        st.dataframe(pd.DataFrame(rows).style.format({"Brier": "{:.5f}", "Log loss": "{:.5f}", "ROC-AUC": "{:.4f}", "AP": "{:.4f}", "Mean predicted": "{:.2%}", "Observed prevalence": "{:.2%}"}), hide_index=True, width="stretch")
        metric = st.selectbox("Monthly calibration metric", ["Brier", "Log loss"], key="p3_cal_metric")
        stem = metric.lower().replace(" ", "_")
        monthly = pd.DataFrame(dev["monthly"]).melt(id_vars="month", value_vars=[f"uncalibrated_{stem}", f"intercept_only_{stem}"], var_name="Method", value_name="Score")
        monthly["Method"] = monthly["Method"].map({f"uncalibrated_{stem}": "Uncalibrated", f"intercept_only_{stem}": "Intercept-only"})
        chart = alt.Chart(monthly).mark_line(point=True).encode(
            x=alt.X("month:O", title="Evaluation month", sort=None),
            y=alt.Y("Score:Q", title=f"{metric}; lower is better"),
            color=alt.Color("Method:N", title=None),
            tooltip=["month", "Method", alt.Tooltip("Score:Q", format=".5f")],
        ).properties(height=240)
        st.altair_chart(chart, width="stretch")
        ci = dev["paired_difference_intercept_minus_uncalibrated"]
        st.markdown("**Paired customer-cluster intervals, intercept-only minus uncalibrated:**")
        st.write(f"Brier {ci['brier']['estimate']:+.5f} (95% CI {ci['brier']['ci95'][0]:+.5f}, {ci['brier']['ci95'][1]:+.5f}); log loss {ci['log_loss']['estimate']:+.5f} (95% CI {ci['log_loss']['ci95'][0]:+.5f}, {ci['log_loss']['ci95'][1]:+.5f}).")
        st.caption("April slightly worsens, while May and June improve. The pooled interval conditions on these three months and fitted calibration maps; it does not measure variation across future periods.")
        st.caption("April and May reuse the same RF fit and map from March; June is the only development map update.")
    else:
        hold = calibration["exploratory_holdout"]
        rows = []
        for label, key in (("Uncalibrated reference", "uncalibrated"), ("Intercept-only replay", "intercept_only")):
            m = hold[key]
            rows.append({"Method": label, "Brier": m["brier"], "Log loss": m["log_loss"], "ROC-AUC": m["roc_auc"], "AP": m["average_precision"], "Mean predicted": m["mean_predicted"], "Observed prevalence": m["observed_prevalence"]})
        st.dataframe(pd.DataFrame(rows).style.format({"Brier": "{:.5f}", "Log loss": "{:.5f}", "ROC-AUC": "{:.4f}", "AP": "{:.4f}", "Mean predicted": "{:.2%}", "Observed prevalence": "{:.2%}"}), hide_index=True, width="stretch")
        monthly = pd.DataFrame(hold["monthly"]).melt(id_vars="month", value_vars=["uncalibrated_brier", "intercept_only_brier"], var_name="Method", value_name="Brier")
        monthly["Method"] = monthly["Method"].map({"uncalibrated_brier": "Uncalibrated", "intercept_only_brier": "Intercept-only replay"})
        chart = alt.Chart(monthly).mark_line(point=True).encode(x=alt.X("month:O", title="Exploratory month", sort=None), y=alt.Y("Brier:Q", title="Brier; lower is better"), color="Method:N", tooltip=["month", "Method", alt.Tooltip("Brier:Q", format=".5f")]).properties(height=240)
        st.altair_chart(chart, width="stretch")
        st.caption("Exploratory replay only; July–November outcomes were previously examined and did not select the method.")
        st.caption("The earlier fold-model calibration map is transferred to full-training-model holdout scores; this is an additional assumption.")
    st.info(f"{calibration['deployment_status']}. A monotone intercept shift normally preserves ranking, so better probability loss does not automatically improve fixed-capacity targeting.")
