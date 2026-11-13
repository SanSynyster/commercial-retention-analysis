from __future__ import annotations

from pathlib import Path
import sys
import unittest
import importlib

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
import monthly_purchase_value_timing as p3v


class MonthlyPurchaseValueTimingTests(unittest.TestCase):
    def test_point_in_time_targets_keep_zero_customers_and_half_open_end(self):
        rows=pd.DataFrame({"customer_id":["a","b","a"],"snapshot_month":["m1","m1","m2"],
                           "decision_time":pd.to_datetime(["2011-01-01","2011-01-01","2011-02-01"])})
        events=[{"customer_id":"a","transaction_date":"2011-01-30","qualifying_gross_merchandise":"10.00","invoice_id":"i1"},
                {"customer_id":"a","transaction_date":"2011-01-31","qualifying_gross_merchandise":"20.00","invoice_id":"i2"},
                {"customer_id":"a","transaction_date":"2011-02-01","qualifying_gross_merchandise":"40.00","invoice_id":"i3"}]
        got=p3v.build_future_targets(rows,events,data_end=pd.Timestamp("2011-04-01"),horizons=(30,))
        self.assertEqual(len(got),3)
        self.assertEqual(got.loc[0,"future_gross_30d"],10.0)
        self.assertEqual(got.loc[0,"future_occasion_count_30d"],1)
        self.assertEqual(got.loc[1,"future_gross_30d"],0.0)
        self.assertEqual(got.loc[1,"future_occasion_count_30d"],0)
        # The second snapshot has Feb 1 on its left boundary and includes it.
        self.assertEqual(got.loc[2,"future_gross_30d"],40.0)

    def test_maturity_marks_censored_spend_unknown_not_zero(self):
        rows=pd.DataFrame({"customer_id":["a","b"],"snapshot_month":["m","m"],
                           "decision_time":pd.to_datetime(["2011-01-01","2011-02-01"])})
        got=p3v.build_future_targets(rows,[],data_end=pd.Timestamp("2011-02-15"),horizons=(30,))
        self.assertTrue(bool(got.loc[0,"value_mature_30d"]))
        self.assertEqual(got.loc[0,"future_gross_30d"],0.0)
        self.assertFalse(bool(got.loc[1,"value_mature_30d"]))
        self.assertTrue(pd.isna(got.loc[1,"future_gross_30d"]))

    def test_predeclared_horizon_feasibility_counts_months(self):
        months=pd.date_range("2011-01-01","2011-12-01",freq="MS")
        frame=pd.DataFrame({"decision_time":months,"snapshot_month":months.strftime("%Y-%m")})
        result=p3v.horizon_feasibility(frame,pd.Timestamp("2011-12-09 12:50"))
        self.assertEqual(len(result["30"]["mature_months"]),11)
        self.assertEqual(result["30"]["latest_decision_month"],"2011-11")
        self.assertEqual(result["60"]["latest_decision_month"],"2011-10")
        self.assertEqual(result["90"]["latest_decision_month"],"2011-09")

    def test_value_fold_training_is_chronological_and_mature(self):
        months=pd.date_range("2011-01-01","2011-06-01",freq="MS")
        data=[]
        for month in months:
            for i in range(1000):
                t=month+pd.Timedelta(days=0)
                data.append({"customer_id":f"{month:%m}-{i}","snapshot_month":month.strftime("%Y-%m"),
                             "decision_time":t,"value_mature_30d":True,"value_end_30d":t+pd.Timedelta(days=30),
                             "future_gross_30d":float(i%7)})
        folds=p3v.make_value_folds(pd.DataFrame(data),30)
        self.assertEqual([x["month"] for x in folds],list(p3v.DEV_MONTH_CANDIDATES))
        for fold in folds:
            self.assertTrue((fold["train"].decision_time<fold["boundary"]).all())
            self.assertTrue((fold["train"].value_end_30d<fold["boundary"]).all())

    def test_survival_outcomes_keep_nonpurchasers_as_censored(self):
        frame=pd.DataFrame({"customer_id":["a","b"],"snapshot_month":["m","m"],
                            "decision_time":pd.to_datetime(["2011-01-01","2011-01-01"])})
        events=[{"customer_id":"a","transaction_date":"2011-01-10","invoice_id":"i"}]
        got=p3v.build_survival_outcomes(frame,events,observation_end=pd.Timestamp("2011-02-01"))
        self.assertTrue(bool(got.loc[0,"event_observed"]))
        self.assertAlmostEqual(got.loc[0,"duration_days"],9)
        self.assertFalse(bool(got.loc[1,"event_observed"]))
        self.assertAlmostEqual(got.loc[1,"duration_days"],31)

    def test_training_survival_labels_are_censored_at_cutoff(self):
        frame=pd.DataFrame({"customer_id":["a"],"snapshot_month":["2011-01"],
                            "decision_time":pd.to_datetime(["2011-01-01"])})
        events=[{"customer_id":"a","transaction_date":"2011-03-01","invoice_id":"i"}]
        got=p3v.build_survival_outcomes(frame,events,censor_at=pd.Timestamp("2011-02-01"))
        self.assertFalse(bool(got.loc[0,"event_observed"]))
        self.assertAlmostEqual(got.loc[0,"duration_days"],31)

    def test_harrell_concordance_and_monetary_metrics(self):
        c=p3v.harrell_c_index(np.asarray([1,2,3]),np.asarray([1,1,0]),np.asarray([3.,2.,1.]))
        self.assertEqual(c["harrell_c"],1.0)
        frame=pd.DataFrame({"customer_id":["a","b","c"],"future_gross_30d":[0.,10.,20.]})
        m=p3v.amount_metrics(frame,np.asarray([0.,12.,18.]),"future_gross_30d")
        self.assertAlmostEqual(m["mae"],4/3)
        self.assertAlmostEqual(m["mean_bias_prediction_minus_actual"],0.0)

    def test_harrell_concordance_truncates_events_and_earlier_censoring(self):
        times,events=p3v.truncate_survival_followup(
            np.asarray([10.,30.,45.,20.]),np.asarray([True,True,True,False]),30)
        np.testing.assert_array_equal(times,np.asarray([10.,30.,30.,20.]))
        np.testing.assert_array_equal(events,np.asarray([True,False,False,False]))
        c=p3v.harrell_c_index(times,events,np.asarray([4.,3.,1.,2.]))
        self.assertEqual(c["harrell_c"],1.0)

    def test_outcome_window_scope_marks_post_june_outcomes_exploratory(self):
        self.assertEqual(p3v._survival_window_scope("2011-04",90)["outcome_scope"],
                         "strict_pre_holdout_outcome_window")
        self.assertEqual(p3v._survival_window_scope("2011-05",90)["outcome_scope"],
                         "exploratory_outcomes_extend_beyond_2011-07-01")
        self.assertEqual(p3v._survival_window_scope("2011-06",60)["outcome_scope"],
                         "exploratory_outcomes_extend_beyond_2011-07-01")

    def test_runner_resolves_recovery_module_from_repository_layout(self):
        load_input,build_occasions=p3v.load_purchase_occasion_api()
        module=importlib.import_module("COMMERCIAL_DS_003_PURCHASE_OCCASIONS")
        self.assertIs(load_input,module.load_validated_purchase_input)
        self.assertIs(build_occasions,module.build_purchase_occasions)
        self.assertTrue(callable(module.load_validated_purchase_input))

    def test_regressor_prediction_alignment_and_determinism(self):
        x=pd.DataFrame({c:np.asarray([1.,2.,3.,4.,5.,6.]) for c in p3v.FEATURES})
        y=np.asarray([0.,1.,0.,4.,0.,9.])
        model1=p3v.make_regressor("Random Forest");model1.fit(x,y)
        p1=model1.predict(x)
        model2=p3v.make_regressor("Random Forest");model2.fit(x,y)
        p2=model2.predict(x)
        self.assertEqual(len(p1),len(x))
        np.testing.assert_array_equal(p1,p2)


if __name__=="__main__":unittest.main()
