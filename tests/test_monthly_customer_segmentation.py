from __future__ import annotations

from pathlib import Path
import sys
import unittest

import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_rand_score

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
import monthly_customer_segmentation as p3s


def sample_rows(months=("2011-03","2011-04"),n=12):
    rows=[]
    for month_index,month in enumerate(months):
        for i in range(n):
            rows.append({
                "customer_id":f"c{i}","snapshot_month":month,
                "decision_time":pd.Timestamp(month+"-01"),
                "days_since_last_qualifying_purchase":float(1+i+month_index),
                "qualifying_purchase_occasions_365d":float(2+i),
                "qualifying_purchase_dates_365d":float(2+i),
                "qualifying_gross_merchandise_365d":float(10+5*i),
                "average_qualifying_basket_value_365d":float(5+i),
                "qualifying_purchase_occasions_90d":float((i+month_index)%(2+i)),
                "outcome_label":int(i%2),"outcome_window_mature":True,
                "outcome_coverage_status":"complete",
            })
    return pd.DataFrame(rows)


class MonthlyCustomerSegmentationTests(unittest.TestCase):
    def test_monetary_outcome_selection_filters_30_day_horizon_before_join(self):
        dev=pd.DataFrame({
            "customer_id":["a","a","b"],"snapshot_month":["2011-04"]*3,
            "horizon_days":[30,60,30],"model":["HistGradientBoosting"]*3,
            "future_gross_30d":[12.5,999.0,0.0],
        })
        hold=pd.DataFrame({
            "customer_id":["c","c"],"snapshot_month":["2011-07"]*2,
            "horizon_days":[30,60],"model":["HistGradientBoosting"]*2,
            "future_gross_30d":[4.0,888.0],
        })
        selected=p3s.select_30_day_monetary_targets(dev,hold)
        self.assertEqual(set(selected.customer_id),{"a","b","c"})
        self.assertEqual(selected.set_index("customer_id").loc["a","future_gross_30d"],12.5)
        self.assertEqual(selected.set_index("customer_id").loc["c","future_gross_30d"],4.0)

    def test_point_in_time_feature_construction_excludes_outcomes_and_ids(self):
        data=sample_rows(("2011-03",),5)
        x=p3s.make_segmentation_features(data)
        self.assertEqual(tuple(x.columns),p3s.CLUSTER_FEATURES)
        self.assertNotIn("customer_id",x)
        self.assertNotIn("outcome_label",x)
        np.testing.assert_allclose(x[p3s.DERIVED_FEATURE],
            data.qualifying_purchase_occasions_90d/data.qualifying_purchase_occasions_365d)

    def test_reference_only_preprocessing_is_frozen_for_later_data(self):
        data=sample_rows(("2011-03","2011-04"),12)
        ref=data.loc[data.snapshot_month.eq("2011-03")]
        later=data.loc[data.snapshot_month.eq("2011-04")].copy()
        imputer,scaler,x_ref,meta=p3s.fit_reference_transform(ref)
        centers=scaler.mean_.copy();medians=imputer.statistics_.copy()
        later.loc[:,"qualifying_gross_merchandise_365d"]*=1e6
        x_later=p3s.transform_with_reference(later,imputer,scaler)
        np.testing.assert_array_equal(scaler.mean_,centers)
        np.testing.assert_array_equal(imputer.statistics_,medians)
        self.assertEqual(meta["reference_n"],len(ref))
        self.assertEqual(x_later.shape,(len(later),len(p3s.CLUSTER_FEATURES)))
        self.assertEqual(x_ref.shape,(len(ref),len(p3s.CLUSTER_FEATURES)))

    def test_rfm_thresholds_are_reference_fit_and_assignment_deterministic(self):
        data=sample_rows(("2011-03","2011-04"),20)
        ref=data.loc[data.snapshot_month.eq("2011-03")]
        rules=p3s.fit_rfm_rules(ref)
        before={k:list(v["thresholds_log1p"]) for k,v in rules["thresholds"].items()}
        assigned1=p3s.assign_rfm(data.loc[data.snapshot_month.eq("2011-04")],rules)
        assigned2=p3s.assign_rfm(data.loc[data.snapshot_month.eq("2011-04")],rules)
        self.assertEqual(before,{k:list(v["thresholds_log1p"]) for k,v in rules["thresholds"].items()})
        pd.testing.assert_frame_equal(assigned1,assigned2)
        self.assertTrue(set(assigned1.rfm_segment).issubset({"Champions","At risk","Hibernating","Loyal","Potential","Big spenders","Regular"}))

    def test_frozen_cluster_model_assigns_later_rows_without_refit(self):
        data=sample_rows(("2011-03","2011-04"),30)
        ref=data.loc[data.snapshot_month.eq("2011-03")]
        later=data.loc[data.snapshot_month.eq("2011-04")]
        imputer,scaler,x_ref,_=p3s.fit_reference_transform(ref)
        model=p3s.fit_cluster("KMeans",3,20261113).fit(x_ref)
        later_before=p3s.transform_with_reference(later,imputer,scaler)
        labels=p3s.predict_cluster(model,"KMeans",later_before)
        self.assertEqual(len(labels),len(later))
        np.testing.assert_array_equal(labels,model.predict(later_before))
        self.assertEqual(model.n_features_in_,len(p3s.CLUSTER_FEATURES))

    def test_deterministic_clustering_and_label_permutation_alignment(self):
        x=np.random.default_rng(123).normal(size=(120,4))
        a=p3s.fit_cluster("KMeans",4,20261113).fit_predict(x)
        b=p3s.fit_cluster("KMeans",4,20261113).fit_predict(x)
        np.testing.assert_array_equal(a,b)
        self.assertEqual(adjusted_rand_score(a,3-b),1.0)

    def test_transition_uses_matched_customers_and_tracks_entry_exit(self):
        frame=pd.DataFrame({"customer_id":["a","b","a","c"],
                            "snapshot_month":["2011-03","2011-03","2011-04","2011-04"]})
        labels=pd.Series([0,1,0,1])
        result=p3s.transition_summary(frame,labels,("2011-03","2011-04"),"ml_segment")
        row=result["adjacent_months"][0]
        self.assertEqual(row["matched_customers"],1)
        self.assertEqual(row["entrants"],1)
        self.assertEqual(row["leavers"],1)
        self.assertEqual(row["same_segment_share"],1.0)
        self.assertEqual(result["transition_matrices"]["2011-03_to_2011-04"]["counts"],[[1,0],[0,0]])

    def test_rfm_string_transition_labels_are_supported(self):
        frame=pd.DataFrame({"customer_id":["a","a","b","b"],
                            "snapshot_month":["2011-03","2011-04"]*2})
        labels=pd.Series(["Loyal","Loyal","Regular","At risk"])
        result=p3s.transition_summary(frame,labels,("2011-03","2011-04"),"rfm_segment")
        self.assertEqual(result["transition_matrices"]["2011-03_to_2011-04"]["labels"],
                         ["At risk","Loyal","Regular"])

    def test_cluster_quality_reports_size_imbalance_and_valid_metrics(self):
        rng=np.random.default_rng(77)
        x=np.r_[rng.normal(-2,.2,(30,2)),rng.normal(2,.2,(30,2))]
        labels=np.r_[np.zeros(30,dtype=int),np.ones(30,dtype=int)]
        metrics=p3s.cluster_quality(x,labels,sample_size=50)
        self.assertEqual(metrics["n_clusters"],2)
        self.assertEqual(metrics["cluster_sizes"],[30,30])
        self.assertGreater(metrics["silhouette_sampled"],.8)
        self.assertEqual(metrics["minimum_cluster_share"],.5)


if __name__=="__main__":unittest.main()
