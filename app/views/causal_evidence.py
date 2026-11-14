"""Historical randomised-study evidence and exploratory uplift comparisons."""
from __future__ import annotations

import os
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from causal_evidence_bundle import BundleError, DEFAULT_BUNDLE, load_bundle

BUNDLE_ENV = "P3_CAUSAL_BUNDLE"


@st.cache_data(show_spinner=False)
def _load(path: str) -> dict:
    return load_bundle(Path(path))


def render() -> None:
    st.title("Causal Evidence & Experimentation")
    try:
        bundle_path = Path(os.environ.get(BUNDLE_ENV, str(DEFAULT_BUNDLE)))
        bundle = _load(str(bundle_path))
    except BundleError as exc:
        st.error(f"The aggregate causal evidence bundle could not be loaded, so no results are shown. {exc}")
        st.caption(f"Expected file: {Path(os.environ.get(BUNDLE_ENV, str(DEFAULT_BUNDLE))).name}. Rebuild with `.venv/bin/python -m src.causal_evidence_bundle --build` when verified P3-008 aggregate sources are available.")
        return
    data = bundle["data"]
    _design_overview(data)
    tab_primary, tab_secondary, tab_development, tab_interpretation = st.tabs([
        "Locked test · primary", "Secondary randomised comparisons", "Development · uplift policy", "Interpretation",
    ])
    with tab_primary:
        _primary_result(data)
    with tab_secondary:
        _secondary_results(data)
    with tab_development:
        _development_results(data)
    with tab_interpretation:
        _interpretation(data)
    with st.expander("Sources, methods and limitations"):
        _source_panel(data, bundle["content_sha256"])


def _design_overview(data: dict) -> None:
    design = data["design"]
    st.caption("**Historical description.** Hillstrom is a separate randomised email experiment, distinct from the observational UCI Online Retail II customer history used on other pages.")
    st.subheader("Three-arm randomised design")
    a, b, c, d = st.columns(4)
    a.metric("Observations", f"{design['observations']:,}")
    b.metric("Men's email", f"{design['arms'][0]['assigned']:,}")
    c.metric("Women's email", f"{design['arms'][1]['assigned']:,}")
    d.metric("No email", f"{design['arms'][2]['assigned']:,}")
    arm_table = pd.DataFrame(design["arms"])
    arm_chart = alt.Chart(arm_table).mark_bar().encode(
        x=alt.X("assigned:Q", title="Randomised observations", axis=alt.Axis(format=",")),
        y=alt.Y("label:N", title=None, sort=None),
        color=alt.Color("label:N", legend=None, scale=alt.Scale(range=["#147D83", "#67A6A0", "#9DB7B5"])),
        tooltip=[alt.Tooltip("label:N", title="Assignment"), alt.Tooltip("assigned:Q", title="Rows", format=",")],
    ).properties(height=100)
    st.altair_chart(arm_chart, width="stretch")
    partition = pd.DataFrame([{"Partition": label, "Rows": n} for label, n in design["partition_sizes"].items()])
    st.dataframe(partition, hide_index=True, width="stretch")
    pairwise = design["primary_pairwise_partition_sizes"]
    st.caption(f"Outcome: website visit during the original two-week window. Interpretation is intent-to-treat by assignment; email receipt, opening and reading were not measured. The frozen split is 60/20/20: {design['partition_sizes']['Training']:,} training, {design['partition_sizes']['Development']:,} development and {design['partition_sizes']['Locked test']:,} locked-test observations. Men's/no-email pairwise rows: {pairwise['Training']:,} train, {pairwise['Development']:,} development and {pairwise['Locked test']:,} test.")


def _primary_result(data: dict) -> None:
    result = data["primary"]
    st.subheader("Men's email assignment vs no email · website visit")
    st.success("Confirmatory randomised evidence — locked test")
    st.caption("Assignment-based intent-to-treat effect on visiting the website during the original two weeks.")
    first, second = st.columns(2)
    first.metric("Men's email", f"{result['events_treated']:,} / {result['n_treated']:,}", f"{result['rate_treated']:.3%} visited")
    second.metric("No email", f"{result['events_control']:,} / {result['n_control']:,}", f"{result['rate_control']:.3%} visited")
    st.metric("Risk difference", f"{result['risk_difference_pp']:+.4f} percentage points", f"{result['additional_visits_per_1000']:.2f} additional visits per 1,000 assigned")
    st.caption(f"95% Newcombe/Wilson CI [{result['ci95_low_pp']:+.4f}, {result['ci95_high_pp']:+.4f}] percentage points · exact two-sided randomisation p = {_format_p(result['exact_two_sided_randomization_p'])}.")
    plot = pd.DataFrame([{"Contrast": "Men's email assignment vs no email", "Estimate": result["risk_difference_pp"], "Lower": result["ci95_low_pp"], "Upper": result["ci95_high_pp"]}])
    zero = alt.Chart(pd.DataFrame({"x": [0]})).mark_rule(color="#687780", strokeDash=[5, 4]).encode(x="x:Q")
    interval = alt.Chart(plot).mark_errorbar(ticks=True, color="#147D83", thickness=3).encode(
        x=alt.X("Lower:Q", title="Risk difference (percentage points)", scale=alt.Scale(domain=[-1, 12])),
        x2="Upper:Q", y=alt.Y("Contrast:N", title=None),
        tooltip=["Contrast", alt.Tooltip("Lower:Q", format="+.4f"), alt.Tooltip("Upper:Q", format="+.4f")],
    )
    point = alt.Chart(plot).mark_point(filled=True, size=110, color="#147D83").encode(
        x=alt.X("Estimate:Q"), y=alt.Y("Contrast:N"),
        tooltip=["Contrast", alt.Tooltip("Estimate:Q", title="Difference (pp)", format="+.4f")],
    )
    st.altair_chart((zero + interval + point).properties(height=100), width="stretch")
    st.caption("The interval excludes zero. This estimates assignment to the historical email offer, not opening or reading it, and does not establish transportability to the UCI customer population.")


def _secondary_results(data: dict) -> None:
    st.subheader("Predeclared secondary website-visit contrasts")
    st.caption("Secondary randomised — Holm-adjusted comparisons across the eight prespecified contrast/outcome tests.")
    choices = {row["contrast"]: row for row in data["secondary_visits"]}
    selected = st.selectbox("Visit contrast", list(choices), key="causal_secondary_contrast")
    row = choices[selected]
    first_arm, second_arm = selected.split(" vs ", 1)
    cols = st.columns(2)
    cols[0].metric("Risk difference", f"{row['risk_difference_pp']:+.4f} percentage points")
    cols[1].metric("Holm-adjusted p-value", _format_p(row["holm_adjusted_p"]))
    st.caption(f"{first_arm}: {row['events_treated']:,}/{row['n_treated']:,} ({row['rate_treated']:.3%}); {second_arm}: {row['events_control']:,}/{row['n_control']:,} ({row['rate_control']:.3%}). Difference is first arm minus second arm. 95% Newcombe/Wilson interval [{row['ci95_low_pp']:+.4f}, {row['ci95_high_pp']:+.4f}] percentage points.")
    selected_frame = pd.DataFrame([{"Contrast": selected, "Estimate": row["risk_difference_pp"], "Lower": row["ci95_low_pp"], "Upper": row["ci95_high_pp"]}])
    zero = alt.Chart(pd.DataFrame({"x": [0]})).mark_rule(color="#687780", strokeDash=[5, 4]).encode(x="x:Q")
    error = alt.Chart(selected_frame).mark_errorbar(ticks=True, color="#D18A38", thickness=3).encode(
        x=alt.X("Lower:Q", title="Risk difference (percentage points)"), x2="Upper:Q", y=alt.Y("Contrast:N", title=None),
    )
    point = alt.Chart(selected_frame).mark_point(filled=True, size=100, color="#D18A38").encode(x="Estimate:Q", y="Contrast:N")
    st.altair_chart((zero + error + point).properties(height=90), width="stretch")
    table = pd.DataFrame(choices.values())
    table = table[["contrast", "n_treated", "events_treated", "rate_treated", "n_control", "events_control", "rate_control", "risk_difference_pp", "ci95_low_pp", "ci95_high_pp", "holm_adjusted_p"]]
    st.dataframe(table, hide_index=True, width="stretch", column_config={
        "rate_treated": st.column_config.NumberColumn("First-arm visit rate", format="percent"),
        "rate_control": st.column_config.NumberColumn("Second-arm visit rate", format="percent"),
        "risk_difference_pp": st.column_config.NumberColumn("Difference (pp)", format="%+.4f"),
        "ci95_low_pp": st.column_config.NumberColumn("95% lower (pp)", format="%+.4f"),
        "ci95_high_pp": st.column_config.NumberColumn("95% upper (pp)", format="%+.4f"),
        "holm_adjusted_p": st.column_config.NumberColumn("Holm-adjusted p", format="%.3g"),
    })
    st.caption("These are secondary contrasts, not additional primary confirmations. The secondary conversion and spend contrasts were inconclusive after Holm adjustment; this does not establish zero effect.")


def _development_results(data: dict) -> None:
    development = data["development"]
    st.subheader("20% targeting policy vs expected random targeting")
    st.caption("Exploratory development — CATE and targeting-policy evaluation. Policy differences are incremental website visits per 1,000 eligible experiment rows; intervals include zero.")
    st.metric("Eligible development rows", f"{development['eligible_rows']:,}", f"{development['selected_rows_at_budget']:,} selected at 20% budget")
    st.caption(f"Expected random targeting reference: {development['expected_random_visits_per_1000']:.2f} incremental website visits per 1,000 eligible experiment rows at 20%. Values below are candidate policy minus this expected-random reference.")
    families = ["All formal learners and benchmark", "Logistic", "HistGradientBoosting", "Historical benchmark", "Reference baseline", "Supplementary XGBoost"]
    selected_family = st.selectbox("Model family", families, key="causal_dev_family")
    rows = development["comparisons"]
    if selected_family == "All formal learners and benchmark":
        shown = [r for r in rows if r["family"] not in ("Reference baseline", "Supplementary XGBoost")]
    elif selected_family == "Logistic":
        shown = [r for r in rows if r["family"] == "Logistic"]
    elif selected_family == "HistGradientBoosting":
        shown = [r for r in rows if r["family"] == "HistGradientBoosting"]
    elif selected_family == "Historical benchmark":
        shown = [r for r in rows if r["family"] == "Historical benchmark"]
    elif selected_family == "Reference baseline":
        shown = [r for r in rows if r["family"] == "Reference baseline"]
    else:
        shown = [r for r in rows if r["family"] == "Supplementary XGBoost"]
    chart_data = pd.DataFrame([{"Policy": row["label"], "Estimate": row["delta_visits_per_1000"], "Lower": row["ci95_low"], "Upper": row["ci95_high"]} for row in shown])
    zero = alt.Chart(pd.DataFrame({"x": [0]})).mark_rule(color="#687780", strokeDash=[5, 4]).encode(x="x:Q")
    error = alt.Chart(chart_data).mark_errorbar(ticks=True, color="#147D83", thickness=2).encode(
        x=alt.X("Lower:Q", title="Difference vs expected random (incremental website visits per 1,000 eligible experiment rows)"), x2="Upper:Q",
        y=alt.Y("Policy:N", title=None, sort=[r["label"] for r in shown]),
        tooltip=["Policy", alt.Tooltip("Lower:Q", format="+.2f"), alt.Tooltip("Upper:Q", format="+.2f")],
    )
    point = alt.Chart(chart_data).mark_point(filled=True, size=90, color="#147D83").encode(
        x="Estimate:Q", y=alt.Y("Policy:N", sort=[r["label"] for r in shown]),
        tooltip=["Policy", alt.Tooltip("Estimate:Q", format="+.2f")],
    )
    st.altair_chart((zero + error + point).properties(height=max(150, 36 * len(shown))), width="stretch")
    table = pd.DataFrame(shown)[["label", "delta_visits_per_1000", "ci95_low", "ci95_high", "formal_promotion_candidate"]]
    st.dataframe(table, hide_index=True, width="stretch", column_config={
        "label": "Policy / learner",
        "delta_visits_per_1000": st.column_config.NumberColumn("Δ visits / 1,000", format="%+.2f"),
        "ci95_low": st.column_config.NumberColumn("95% lower", format="%+.2f"),
        "ci95_high": st.column_config.NumberColumn("95% upper", format="%+.2f"),
        "formal_promotion_candidate": "Formal learner",
    })
    st.info("No personalised model established reliable superiority over expected random targeting; constant ATE / expected random allocation remained the research reference. This does not prove treatment effects are homogeneous.")
    st.caption("The locked test was not used to evaluate or promote personalized models. The P3-008C aggregate records zero model fits and no candidate test diagnostics. XGBoost T-learner is supplementary and not promotion-eligible.")


def _interpretation(data: dict) -> None:
    meaning = data["interpretation"]
    st.subheader("What this evidence answers")
    left, middle, right = st.columns(3)
    left.markdown("**1 · Average assignment effect**")
    left.write(meaning["average_assignment_effect"])
    middle.markdown("**2 · Individual response**")
    middle.write(meaning["individual_response"])
    right.markdown("**3 · 20% policy value**")
    right.write(meaning["targeting_policy"])
    st.warning("Do not apply Hillstrom treatment effects or uplift scores directly to UCI Online Retail II segments. Purchase/visit propensity and treatment uplift answer different questions.")
    policy = data["test_policy"]
    locked_n = data["design"]["primary_pairwise_partition_sizes"]["Locked test"]
    st.caption(f"Locked-test expected random allocation at 20%, estimated from {locked_n:,} Men's/no-email locked-test eligible experiment rows: {policy['increment_visits_per_1000']:.2f} incremental website visits per 1,000 locked-test eligible experiment rows (95% scaled interval [{policy['ci95_low_per_1000']:.2f}, {policy['ci95_high_per_1000']:.2f}]). This is the expected average value of random allocation under the estimated test ATE, not evidence of a personalized gain.")


def _source_panel(data: dict, bundle_hash: str) -> None:
    provenance = data["provenance"]
    st.markdown(f"Application bundle content SHA-256: `{bundle_hash}`. Frozen data SHA-256: `{provenance['dataset_sha256']}`. Split SHA-256: `{provenance['split_sha256']}`.")
    for name, source in provenance["sources"].items():
        st.caption(f"{name}: {source.get('source_file', source.get('report'))} · SHA-256 {source.get('sha256_raw_file', source.get('sha256_report'))}")
    st.caption("Source aggregates were extracted by fixed paths and raw-file hashes. No raw Hillstrom rows, row-level outcomes, prediction Parquet, test-row Parquet or split assignments are included in the application bundle.")
    st.caption("This is one historical randomised experiment with no observed delivery/open/engagement and no contact cost or margin. Conversion/spend evidence was inconclusive. Effects are not established to transport to current campaigns or the UCI customer population.")


def _format_p(value: float) -> str:
    return f"{value:.3g}"
