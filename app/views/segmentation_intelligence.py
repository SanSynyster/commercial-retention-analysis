"""Aggregate-only RFM and exploratory K-Means segmentation view."""
from __future__ import annotations

import os
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from segmentation_bundle import BundleError, DEFAULT_BUNDLE, load_bundle

BUNDLE_ENV = "P3_SEGMENTATION_BUNDLE"


@st.cache_data(show_spinner=False)
def _load(path: str) -> dict:
    from pathlib import Path
    return load_bundle(Path(path))


def render() -> None:
    st.title("Segmentation Intelligence")
    try:
        bundle_path = Path(os.environ.get(BUNDLE_ENV, str(DEFAULT_BUNDLE)))
        bundle = _load(str(bundle_path))
    except BundleError as exc:
        st.error(f"The aggregate segmentation bundle could not be loaded, so no results are shown. {exc}")
        st.caption(f"Expected file: {Path(os.environ.get(BUNDLE_ENV, str(DEFAULT_BUNDLE))).name}. Rebuild with `.venv/bin/python -m src.segmentation_bundle --build` when verified P3-007 aggregate sources are available.")
        return

    data = bundle["data"]
    cohort = data["cohort"]
    st.caption(
        f"**Historical description.** RFM rules and the supplementary K-Means profiles describe the March 2011 reference population ({cohort['reference_customers']:,} customers). These are historical states, not current CRM segments."
    )
    tabs = st.tabs(["RFM · primary", "K-Means · exploratory", "Comparison and stability"])
    with tabs[0]:
        _render_rfm(data)
    with tabs[1]:
        _render_kmeans(data)
    with tabs[2]:
        _render_comparison(data)

    from page_registry import TARGETING_EXPLORER_PAGE
    st.page_link(TARGETING_EXPLORER_PAGE, label="Continue to retrospective CRM targeting comparisons")
    st.caption("Segment purchase rates describe subsequent historical purchasing. They are not calibrated future probabilities and do not estimate response to marketing contact.")
    with st.expander("Bundle provenance and evidence limits"):
        provenance = data["provenance"]
        st.markdown(
            f"Source report: `{provenance['report']}`. Exact aggregate: `{provenance['source_file']}` "
            f"(SHA-256 `{provenance['sha256_raw_file']}`). Source manifest SHA-256: `{provenance['sha256_manifest']}`. "
            f"Application bundle content SHA-256: `{bundle['content_sha256']}`."
        )
        st.caption("The March-fitted thresholds and clustering transforms were held fixed when later snapshots were assigned. April–June is descriptive retrospective evaluation; July–November was previously examined and is exploratory. No individual assignments are present in this application.")


def _render_rfm(data: dict) -> None:
    rfm = data["rfm"]
    cohort = data["cohort"]
    st.subheader("March reference RFM groups")
    st.caption(f"Historical description · {cohort['reference_month']} · {cohort['reference_customers']:,} eligible customers. RFM scores use March reference quintile cutpoints on log1p values; ties are assigned deterministically. The segment rules use the precedence shown below.")
    table = _rfm_table(data)
    selected = st.selectbox("RFM segment", table["Segment"].tolist(), key="p3c_rfm_segment")
    row = table.loc[table["Segment"] == selected].iloc[0]
    a, b, c = st.columns(3)
    a.metric("March customers", f"{int(row['Customers']):,}", f"{row['Share']:.1%} of reference")
    b.metric("Median recency", f"{row['Median recency (days)']:.1f} days")
    c.metric("Median qualifying gross", f"£{row['Median gross (GBP)']:,.2f}")
    st.caption("March defines the 4,260-customer reference cohort; April–June rates use segment membership re-derived at each month's snapshot under the same frozen rules.")
    st.dataframe(table, hide_index=True, width="stretch", column_config={
        "Share": st.column_config.NumberColumn("Share", format="percent"),
        "Purchase rate": st.column_config.NumberColumn("Apr–Jun next-30-day purchase rate", format="percent"),
        "Median recency (days)": st.column_config.NumberColumn("Median recency (days)", format="%.1f"),
        "Median frequency (365d)": st.column_config.NumberColumn("Median occasions (365d)", format="%.1f"),
        "Median gross (GBP)": st.column_config.NumberColumn("Median gross (GBP)", format="£%.2f"),
        "Mean subsequent gross (GBP)": st.column_config.NumberColumn("Apr–Jun mean subsequent gross (GBP)", format="£%.2f"),
    })
    chart = alt.Chart(table).mark_bar().encode(
        x=alt.X("Purchase rate:Q", title="Subsequent purchase rate", axis=alt.Axis(format="%"), scale=alt.Scale(domain=[0, 0.5])),
        y=alt.Y("Segment:N", sort=table["Segment"].tolist(), title=None),
        color=alt.condition(alt.datum.Segment == selected, alt.value("#147D83"), alt.value("#9DB7B5")),
        tooltip=["Segment", alt.Tooltip("Snapshots:Q", format=","), alt.Tooltip("Purchase rate:Q", format=".1%")],
    ).properties(height=260)
    st.altair_chart(chart, width="stretch")
    _rfm_cutpoints(rfm)
    st.caption("**Retrospective evaluation · April–June 2011.** Purchase rates use 12,961 matched mature snapshots pooled across months; repeated customers may appear in multiple snapshots. These are descriptive outcomes, not future probabilities or marketing effects.")


def _render_kmeans(data: dict) -> None:
    km = data["kmeans"]
    quality = km["quality"]
    st.subheader("Frozen three-cluster K-Means solution")
    st.caption("Exploratory · March-fitted K-Means; evaluation snapshots were assigned with the frozen March preprocessing and centroids.")
    a, b, c = st.columns(3)
    a.metric("Selected solution", "k = 3", "Frozen selection criteria")
    b.metric("Silhouette", f"{quality['silhouette_sampled']:.3f}", "2,000-row deterministic sample")
    c.metric("Seed stability ARI", f"{quality['mean_seed_ari']:.3f}")
    st.metric("Customer-bootstrap stability ARI", f"{quality['customer_bootstrap_ari_mean']:.3f}", "12 March-row resamples")
    st.caption("Bootstrap p10–p90: " + "–".join(f"{v:.3f}" for v in quality["customer_bootstrap_ari_p10_p90"]) + ". The original analysis reported the mean; its small number of replicates makes it a noisy stability summary.")

    profiles = km["reference_profiles"]
    centroid_profiles = km["standardized_centroid_profiles"]
    outcomes = data["outcomes"]["development_apr_jun"]["ml_segment"]
    rows = []
    for cluster, profile in profiles.items():
        medians = profile["feature_medians"]
        future = outcomes[cluster]
        rows.append({
            "Cluster": f"Cluster {cluster}", "Customers": profile["n"], "Share": profile["share"],
            "Median recency (days)": medians["days_since_last_qualifying_purchase"],
            "Median occasions (365d)": medians["qualifying_purchase_occasions_365d"],
            "Median gross (GBP)": medians["qualifying_gross_merchandise_365d"],
            "Median basket (GBP)": medians["average_qualifying_basket_value_365d"],
            "Recent occasion share": profile["recent_purchase_share_90d_median"],
            "Apr–Jun purchase rate": future["purchase_rate"],
            "Apr–Jun snapshots": future["n"],
        })
    table = pd.DataFrame(rows)
    selected = st.selectbox("Cluster", table["Cluster"].tolist(), key="p3c_kmeans_cluster")
    chosen = table.loc[table["Cluster"] == selected].iloc[0]
    st.markdown(f"**{selected}:** {_cluster_description(str(chosen['Cluster']))}")
    m1, m2 = st.columns(2)
    m1.metric("March cluster size", f"{int(chosen['Customers']):,}", f"{chosen['Share']:.1%} of reference")
    m2.metric("Apr–Jun subsequent purchase rate", f"{chosen['Apr–Jun purchase rate']:.1%}", f"{int(chosen['Apr–Jun snapshots']):,} snapshots")
    feature_labels = {
        "days_since_last_qualifying_purchase": "Log recency (higher = less recent)",
        "qualifying_purchase_occasions_365d": "Log purchase occasions",
        "qualifying_gross_merchandise_365d": "Log qualifying gross",
        "average_qualifying_basket_value_365d": "Log average basket",
        "purchase_occasion_share_90d": "Purchase occasion share (90d)",
    }
    heat = pd.DataFrame([{"Cluster": f"Cluster {cluster}", "Feature": feature_labels[feature], "Standard deviations from March": value}
                         for cluster, values in centroid_profiles.items() for feature, value in values.items()])
    heat_chart = alt.Chart(heat).mark_rect().encode(
        x=alt.X("Feature:N", title=None, axis=alt.Axis(labelAngle=-25, labelLimit=180)),
        y=alt.Y("Cluster:N", title=None, sort=["Cluster 0", "Cluster 1", "Cluster 2"]),
        color=alt.Color("Standard deviations from March:Q", title="Standard deviations", scale=alt.Scale(scheme="redblue", domainMid=0)),
        tooltip=["Cluster", "Feature", alt.Tooltip("Standard deviations from March:Q", format=".2f")],
    ).properties(height=140)
    st.altair_chart(heat_chart, width="stretch")
    st.caption("Median profiles below show original feature scales; the chart shows standardized cluster centroids. Recency and recent occasion share are related by design.")
    st.dataframe(table, hide_index=True, width="stretch", column_config={
        "Share": st.column_config.NumberColumn("March share", format="percent"),
        "Apr–Jun purchase rate": st.column_config.NumberColumn("Apr–Jun next-30-day purchase rate", format="percent"),
        "Recent occasion share": st.column_config.NumberColumn("Median recent occasion share", format="percent"),
        "Median gross (GBP)": st.column_config.NumberColumn("Median gross (GBP)", format="£%.2f"),
        "Median basket (GBP)": st.column_config.NumberColumn("Median basket (GBP)", format="£%.2f"),
    })
    st.caption("Cluster IDs are model labels, not an ordered score. RFM remains the primary CRM-facing framework; these clusters are supplementary behavioural summaries.")


def _render_comparison(data: dict) -> None:
    comparison = data["comparison"]
    st.subheader("How the groupings relate")
    st.caption("Historical comparison · RFM and clusters use different numbers of groups (seven versus three), so agreement metrics describe partition overlap, not commercial quality.")
    a, b = st.columns(2)
    a.metric("March ARI: K-Means vs RFM", f"{comparison['reference_ari']:.3f}")
    a.metric("March NMI: K-Means vs RFM", f"{comparison['reference_nmi']:.3f}")
    monthly = comparison["rfm_vs_kmeans_by_month"]
    overlap = pd.DataFrame([{"Month": month, "ARI": values["adjusted_rand_ml_vs_rfm"], "NMI": values["normalized_mutual_information_ml_vs_rfm"]} for month, values in monthly.items()])
    agreement = overlap.melt(id_vars="Month", var_name="Metric", value_name="Agreement")
    agreement_chart = alt.Chart(agreement).mark_line(point=True).encode(
        x=alt.X("Month:O", title="Snapshot month", sort=None),
        y=alt.Y("Agreement:Q", scale=alt.Scale(domain=[0, 1]), title="Agreement with RFM"),
        color="Metric:N", tooltip=["Month", "Metric", alt.Tooltip("Agreement:Q", format=".3f")],
    ).properties(height=220)
    a.altair_chart(agreement_chart, width="stretch")
    st.caption("March–June are reference/development snapshots; July–November values are the previously examined exploratory replay.")

    selected_month = st.selectbox("Transition period", ["Development only", "Through exploratory replay"], key="p3c_transition_period")
    kmeans_rows = comparison["kmeans_transitions"]
    rfm_rows = comparison["rfm_transitions"]
    kmeans_by_pair = {(r["from_month"], r["to_month"]): r for r in kmeans_rows}
    rfm_by_pair = {(r["from_month"], r["to_month"]): r for r in rfm_rows}
    pairs = [(a, b) for a, b in kmeans_by_pair if selected_month == "Through exploratory replay" or b <= "2011-06"]
    if selected_month == "Through exploratory replay":
        st.caption("**Exploratory · Previously examined July–November 2011 replay.**")
    else:
        st.caption("**Development · March–June 2011 adjacent snapshots.**")
    transition = pd.DataFrame([
        {"Transition": f"{a[5:]} → {b[5:]}", "Month": b,
         "K-Means ARI": kmeans_by_pair[(a, b)]["adjusted_rand_index"],
         "RFM ARI": rfm_by_pair[(a, b)]["adjusted_rand_index"],
         "K-Means same group": kmeans_by_pair[(a, b)]["same_segment_share"],
         "RFM same group": rfm_by_pair[(a, b)]["same_segment_share"],
         "Matched customers": kmeans_by_pair[(a, b)]["matched_customers"]}
        for a, b in pairs
    ])
    b.altair_chart(alt.Chart(transition.melt(id_vars=["Transition", "Month"], value_vars=["K-Means ARI", "RFM ARI"], var_name="Grouping", value_name="ARI")).mark_line(point=True).encode(
        x=alt.X("Transition:O", title="Adjacent matched snapshots", sort=None), y=alt.Y("ARI:Q", scale=alt.Scale(domain=[0, 1]), title="Transition ARI"), color="Grouping:N", tooltip=["Transition", "Grouping", alt.Tooltip("ARI:Q", format=".3f")],
    ).properties(height=220), width="stretch")
    st.dataframe(transition, hide_index=True, width="stretch")
    st.caption("Adjacent snapshots share roughly 11 of 12 months of the rolling 365-day history window, so high persistence is partly expected mechanically. RFM and K-Means have unequal group counts, and their persistence should not be compared from raw same-group shares alone.")

    conclusion = comparison["incremental_value_conclusion"]
    st.info(conclusion)
    within = data["within_rfm_cluster_variation"]
    left, right = st.columns(2)
    left.metric("Median within-RFM purchase-rate range", f"{within['median_purchase_rate_range']:.1%}", "among groups with ≥2 cluster cells of n≥50")
    right.metric("Median within-RFM mean-gross range", f"£{within['median_mean_value_range_gbp']:,.0f}", "per snapshot; dimensions already in RFM")
    st.caption("Cluster splits show some within-group variation, but these dimensions already appear in the full RFM scores; this does not establish meaningful incremental purchase discrimination.")
    st.caption("The report includes reviewer-derived April–June AUC diagnostics, but those figures are absent from the exact verified aggregate source, so this app does not display them. Verified aggregate outcome profiles remain descriptive and do not establish incremental campaign value.")


def _rfm_table(data: dict) -> pd.DataFrame:
    profiles = data["rfm"]["reference_profiles"]
    outcomes = data["outcomes"]["development_apr_jun"]["rfm_segment"]
    rows = []
    for segment in data["rfm"]["assignment_precedence"]:
        profile, future = profiles[segment], outcomes[segment]
        rows.append({
            "Segment": segment,
            "Definition": data["rfm"]["segment_descriptions"][segment],
            "Customers": profile["n"], "Share": profile["share"],
            "Median recency (days)": profile["recency_median_days"],
            "Median frequency (365d)": profile["frequency_median_365d"],
            "Median gross (GBP)": profile["monetary_median_365d_gbp"],
            "Purchase rate": future["purchase_rate"], "Snapshots": future["n"],
            "Mean subsequent gross (GBP)": future["mean_future_gross_gbp"],
        })
    return pd.DataFrame(rows)


def _rfm_cutpoints(rfm: dict) -> None:
    c = rfm["cutpoints"]
    labels = {
        "recency": ("Recency in days, ascending cutpoint; lower values earn higher R score", "days"),
        "frequency": ("Qualifying purchase occasions in prior 365 days", "occasions"),
        "monetary": ("Qualifying gross merchandise in prior 365 days", "GBP"),
    }
    dimension_order = ("recency", "frequency", "monetary")
    rows = [{"Dimension": labels[name][0], "March cutpoints": ", ".join(f"£{x:,.2f}" if labels[name][1] == "GBP" else f"{x:.2f} {labels[name][1]}" for x in c[name]["original_scale"])} for name in dimension_order]
    with st.expander("How RFM scores and groups are assigned"):
        st.markdown("Scores use five nominal ordinal bands from March reference-period quintile cutpoints (ties assigned deterministically). Segment rules are applied in this order:")
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        definitions = rfm["segment_descriptions"]
        st.markdown("\n".join(f"- **{name}:** {definitions[name]}" for name in rfm["assignment_precedence"]))
        st.caption("Eligibility requires at least one qualifying purchase in the trailing 365-day window; there is no never-purchased segment. Discrete frequency ties yield four non-empty March F bands; one occasion maps to F=2. These historical rules are not thresholds fitted to outcomes.")


def _cluster_description(cluster: str) -> str:
    return {
        "Cluster 0": "recently active with low-to-moderate historical purchase frequency.",
        "Cluster 1": "predominantly inactive over the recent window and single-occasion.",
        "Cluster 2": "frequent and higher-spend in the historical window.",
    }[cluster]
