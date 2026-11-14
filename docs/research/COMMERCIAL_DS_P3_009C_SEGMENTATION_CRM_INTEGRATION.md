# COMMERCIAL_DS_P3_009C — Segmentation and CRM Decision Support Integration

**Status:** implemented locally for independent scientific and engineering review; no new modelling experiment or campaign workflow.
**Base:** P3-009B commit `d9c4c9847578c2c957c23cf53d35001612d844ba`.

## Implemented functionality

Added **Segmentation Intelligence** to the existing Streamlit navigation. The view gives RFM priority and presents the March 2011 reference groups with rule definitions, sizes and shares, median recency/frequency/gross characteristics, and April–June subsequent purchase rates. An analyst can select an RFM segment or K-Means cluster. The cluster view shows selected-cluster size/rate, original-scale profiles, standardized centroid feature chart, selection and stability metrics, and relationship to RFM. The comparison view shows March ARI/NMI, monthly partition agreement, adjacent-month persistence comparisons, matched customer counts, and the report-supported within-RFM cluster variation and scientific conclusion.

Customer Overview and CRM Targeting Explorer link to segmentation context. Segmentation Intelligence links onward to the existing fixed-capacity CRM Targeting Explorer, which remains responsible for the retrospective targeting comparison. The app does not connect a selected RFM segment or cluster to a customer list, change the targeting policies, or execute a campaign.

## Bundle provenance and privacy

`src/segmentation_bundle.py` reads only these explicit P3-007 sources from the sibling `source_data` tree:

| Source | Relative path | Raw file SHA-256 |
|---|---|---|
| Aggregate results | `uci_online_retail_ii/p3_007_outputs/p3_007_aggregate_results.json` | `53a7636b839e97cfc489cfa5688076edef3337abaf76b3bb326316b1a5ecf209` |
| Manifest | `uci_online_retail_ii/p3_007_outputs/p3_007_manifest.json` | `35bb459509ab58d4d41f519fa3374339b7717d0206412bdd75295aeedc94dea6` |

The report-cited aggregate path and the manifest’s `aggregate_sha256`, dataset digest, reference month, and selected algorithm/k are checked before extraction. The builder selects allowlisted aggregate fields, serializes deterministically, validates segment-count/rate consistency, and pins the application bundle content SHA-256. Missing or changed source files fail clearly. Rebuild-dependent tests skip if the exact private aggregate/manifest are unavailable; committed bundle checks always run.

The bundle includes no customer rows, identifiers, predictions, assignment file contents, or private absolute paths. Small-cell RFM-by-cluster cross-tabs are excluded from the projection. The private `private/p3_007_customer_month_assignments.parquet` source was not read by the builder and is not staged. Bundle content SHA-256: `590328678dcb144d94d5d8c54a79d767f0590a22554e9e4bd9dabbbad3f522a8`.

## Scientific evidence shown

### RFM primary segmentation

The reference is March 2011 (4,260 eligible customers). R, F and M are assigned from March reference-period quintile cutpoints on log1p values; recency is reversed so fewer days since purchase yields a higher R score. Ties are handled deterministically. The original-scale cutpoints are about 32.49, 90.49, 124.35, 190.39 days; 1, 2, 3 and 6 occasions; and £246.50, £489.60, £948.16 and £2,040.80 gross merchandise. Eligibility requires qualifying activity in the preceding 365-day window.

The fixed precedence is Champions (R≥4, F≥4, M≥4), At risk (R≤2, F≥3), Hibernating (R≤2, F≤2), Loyal (R≥4, F≥3), Potential (R≥4, F≤2), Big spenders (M≥4 after preceding rules), then Regular. March counts are Champions 1,023 (24.0%), Hibernating 967 (22.7%), At risk 737 (17.3%), Regular 543 (12.7%), Loyal 422 (9.9%), Big spenders 309 (7.3%), and Potential 259 (6.1%). Profiles use the aggregate’s median point-in-time characteristics.

April–June retrospective outcomes cover 12,961 mature snapshots: Champions had a 44.0% next-30-day purchase rate, Hibernating 5.2%, At risk 12.1%, Loyal 19.4%, Potential 12.9%, Big spenders 27.9%, and Regular 10.4%. The page labels these as retrospective outcome rates. They are not calibrated future probabilities and say nothing about response to contact.

### Supplementary K-Means and comparison

K-Means k=3 was selected under the frozen stability criteria without future outcomes. The March reference sizes are cluster 0: 567 (13.3%); cluster 1: 2,310 (54.2%); cluster 2: 1,383 (32.5%). Cluster 0 is recently active with low-to-moderate frequency; cluster 1 is predominantly less recently active and single-occasion; cluster 2 is frequent and higher-spend. April–June descriptive purchase rates are 17.9%, 8.3%, and 39.2%, respectively.

The displayed selection and stability evidence is silhouette 0.384, mean seed ARI 0.993, and original-analysis customer-bootstrap mean ARI 0.974 (12 resamples; p10–p90 0.943–0.991). These are reference-population stability summaries. The independent reviewer’s approximately 0.972 bootstrap mean is not included because the verified source aggregate supports 0.974 from the original analysis. K-Means group IDs are nominal, not an ordered score.

March RFM/cluster agreement is ARI 0.357 and NMI 0.493; April–November ARI ranges 0.414–0.495 and NMI 0.534–0.577. These describe partition agreement across seven RFM groups and three clusters, not commercial quality. Adjacent-month K-Means ARIs range 0.563–0.692 in March–November, compared with 0.512–0.669 for RFM; their same-group shares have different chance baselines because group counts differ. Approximately 11 of 12 months overlap in adjacent rolling 365-day windows, which mechanically contributes to persistence.

The report’s April–June ROC-AUC values (K-Means 0.721; RFM segments 0.748; RFM×clusters 0.751; full RFM code 0.753; RFM code×clusters 0.751) are explicitly reviewer-derived diagnostics. They are absent from the exact manifest-verified P3-007 aggregate JSON, so the application does not display them as verified bundle results. Instead it shows aggregate-supported segment outcomes and within-RFM cluster ranges, alongside the research conclusion: **available evidence does not demonstrate meaningful incremental purchase discrimination beyond RFM.** This is a bounded finding in the evaluated data, not a claim that clustering could never add value.

RFM is labeled **Historical description**; April–June rates are **Retrospective evaluation**; K-Means is **Exploratory**; July–November transitions are **Previously examined holdout — exploratory**; the existing targeting page remains **Retrospective targeting**. UCI segmentation has no confirmatory randomized evidence.

## CRM analyst workflow

1. Review historical customer context in Customer Overview.
2. Open Segmentation Intelligence to inspect March RFM group definitions/profiles and April–June outcomes.
3. Inspect K-Means as a supplementary exploratory behavioural summary and review its stability and RFM overlap.
4. Continue to CRM Targeting Explorer to compare existing retrospective targeting policies at their supported capacities.

Observed segment purchase rates remain separate from causal intervention effects. The underlying observations are from 2009–2011; displayed March 2011 states are not current customer states. No customer drill-down, list export, live assignment or campaign execution is introduced.

## Tests and limitations

Added focused tests for bundle schema/content pin, explicit aggregate/manifest provenance, deterministic rebuild, missing and mismatched sources, aggregate-only privacy, RFM counts/rates, K-Means/stability values, evidence labels, reviewer-AUC exclusion, scientific conclusion, page rendering and segment/cluster/transition interactions. The existing app navigation test now verifies six registered pages. The focused app suite passed **70 tests, with 1 existing `LOCAL_DATA_DIR`-dependent rebuild test skipped**. Python compilation/import, source/bundle checksum, privacy and `git diff --check` verification also passed.

Limitations follow P3-007: the reference fit is one March period; cluster bootstrap stability uses only 12 resamples; repeated customers appear across monthly evaluations; eligibility/composition changes over time; and adjacent snapshots share most of their rolling history. Outcome profiles are descriptive, not causal. The research does not establish CRM eligibility, contact rules, costs, incremental revenue, or prospective generalization.
