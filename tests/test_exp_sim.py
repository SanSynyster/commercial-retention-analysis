from __future__ import annotations

import ast
from dataclasses import replace
from math import sqrt
from pathlib import Path
from statistics import NormalDist
import unittest

import numpy as np
import pandas as pd

from src.exp_sim import (
    DecisionConfig, ExperimentConfig, SensitivityRange, analyze_trial,
    decide_adoption, generate_trial, monte_carlo, newcombe_interval,
    write_simulation_result,
)
from src.exp_sim.core import _probability_metric, assess_180_day

REPO = Path(__file__).resolve().parents[1]
SENS = SensitivityRange(-0.01, 0.01, True, "HYPOTHETICAL TEST RANGE")


class SyntheticExperimentTests(unittest.TestCase):
    def analysis(self, trial, **kwargs):
        return analyze_trial(trial.records, sensitivity_range=kwargs.pop("sensitivity_range", SENS),
                             bootstrap_seed_sequence=trial.bootstrap_seed_sequence,
                             margin_bootstrap_reps=kwargs.pop("margin_bootstrap_reps", 25),
                             missingness_assumptions_approved=kwargs.pop("missingness_assumptions_approved", True), **kwargs)

    def test_published_newcombe_reference_values(self):
        references = [
            (56,70,48,80,0.2000,0.0524,0.3339), (9,10,3,10,0.6000,0.1705,0.8090),
            (6,7,2,7,0.5714,0.0582,0.8062), (5,56,0,29,0.0893,-0.0381,0.1926),
            (0,10,0,20,0.0,-0.1611,0.2775), (0,10,0,10,0.0,-0.2775,0.2775),
            (10,10,0,20,1.0,0.6791,1.0), (10,10,0,10,1.0,0.6075,1.0),
        ]
        for xt,nt,xc,nc,rd,lo,hi in references:
            actual = newcombe_interval(xt,nt,xc,nc)
            np.testing.assert_allclose(actual, (rd,lo,hi), atol=0.000051)

    def test_newcombe_boundary_and_validation(self):
        for x,n in [(0,10),(10,10)]:
            _,lo,hi = newcombe_interval(x,n,x,n)
            self.assertLessEqual(lo, 0); self.assertGreaterEqual(hi, 0)
        with self.assertRaises(ValueError): newcombe_interval(0,0,0,3)

    def test_reproducibility_truth_split_and_ground_truth(self):
        cfg = ExperimentConfig(n_customers=5000, seed=72, eligible_effect=0.06)
        a, b = generate_trial(cfg), generate_trial(cfg)
        pd.testing.assert_frame_equal(a.records, b.records)
        self.assertEqual(a.truth.finite_population_sate, b.truth.finite_population_sate)
        self.assertAlmostEqual(a.truth.population_itt_rd, (1-cfg.p_early_repeat)*(1-cfg.p_optout_pre_day21)*cfg.p_operationally_contactable*cfg.eligible_effect)
        self.assertAlmostEqual(a.truth.finite_population_sate, a.truth.sample_eligible_fraction*cfg.eligible_effect, delta=0.02)
        self.assertTrue(set(a.records.columns).isdisjoint({"resolution_scenario", "true_itt_rd", "true_outcome_90", "hidden_outcome"}))

    def test_exact_randomization_and_symmetric_eligibility(self):
        trial = generate_trial(ExperimentConfig(n_customers=10000, seed=91))
        f = trial.records
        self.assertEqual(int((f.assignment == "treatment").sum()), 5000)
        self.assertLess(abs(f.groupby("assignment").eligible_day21.mean().diff().dropna().iloc[0]), 0.025)
        self.assertEqual(f.customer_id.nunique(), len(f))

    def test_null_effect_and_primary_itt_method(self):
        t = generate_trial(ExperimentConfig(n_customers=1000, eligible_effect=0))
        self.assertEqual(t.truth.population_itt_rd, 0)
        a = self.analysis(t)
        self.assertEqual(a["primary"]["estimand"], "all_randomized_itt_rd")
        self.assertEqual(a["primary"]["method"], "newcombe_hybrid_score_resolved_itt")

    def test_truth_labels_cannot_change_analyst_decision(self):
        t = generate_trial(ExperimentConfig(n_customers=5000, seed=23, eligible_effect=0.08, outcome_missingness="outcome_dependent", missing_rate_control=0.01, missing_rate_treatment=0.01, missing_effect_if_repeat=8, margin_resolution_follows_outcome=True))
        a1 = self.analysis(t)
        changed_truth = replace(t.truth, missingness_mechanism="complete", population_itt_rd=-0.9, finite_population_sate=0.9)
        a2 = self.analysis(replace(t, truth=changed_truth))
        d1 = decide_adoption(a1, sensitivity_range=SENS)
        d2 = decide_adoption(a2, sensitivity_range=SENS)
        self.assertEqual(a1, a2)
        self.assertEqual(d1, d2)
        self.assertEqual(a1["missingness_assumptions"]["assumptions_pass"], a1["diagnostics_pass"])

    def test_financial_truth_is_private_and_masked_when_purchase_unresolved(self):
        cfg=ExperimentConfig(n_customers=5000,seed=232,outcome_missingness="outcome_dependent",
                             missing_rate_control=.04,missing_rate_treatment=.04,
                             missing_effect_if_repeat=2,margin_resolution_follows_outcome=True)
        t=generate_trial(cfg); f=t.records
        unresolved=~f.resolved_90.astype(bool)
        self.assertGreater(int(unresolved.sum()),0)
        for value_col,status_col in (("margin_90","margin_resolved_90"),("margin_180","margin_resolved_180")):
            self.assertTrue(f.loc[unresolved,value_col].isna().all())
            self.assertFalse(f.loc[unresolved,status_col].any())
            self.assertTrue(f[value_col].notna().equals(f[status_col]))
        self.assertTrue(np.isfinite(t.truth.margin_90_truth).all())
        self.assertTrue(np.isfinite(t.truth.margin_180_truth).all())
        expected_margin=(1-cfg.p_early_repeat)*(1-cfg.p_optout_pre_day21)*cfg.p_operationally_contactable*(cfg.eligible_effect*cfg.contribution_per_repeat-cfg.intervention_cost_per_sent)
        self.assertAlmostEqual(t.truth.population_itt_margin_90,expected_margin)
        self.assertAlmostEqual(t.truth.finite_population_sate_margin_90,float(np.mean(t.truth.potential_margin_treatment_90-t.truth.potential_margin_control_90)))
        self.assertTrue(set(t.records.columns).isdisjoint({"margin_90_truth","margin_180_truth","true_outcome_90"}))
        a1=self.analysis(t)
        hidden=replace(t.truth,margin_90_truth=np.full(cfg.n_customers,1e9),margin_180_truth=np.full(cfg.n_customers,-1e9))
        t2=replace(t,truth=hidden)
        a2=self.analysis(t2)
        self.assertEqual(a1,a2)
        self.assertEqual(decide_adoption(a1,sensitivity_range=SENS),decide_adoption(a2,sensitivity_range=SENS))

    def test_outcome_dependent_scenario_rejects_unmasked_financial_policy(self):
        with self.assertRaisesRegex(ValueError,"requires margin_resolution_follows_outcome=True"):
            generate_trial(ExperimentConfig(n_customers=100,outcome_missingness="outcome_dependent"))

    def test_financial_masking_is_arm_symmetric_and_clean_default_is_preserved(self):
        cfg=ExperimentConfig(n_customers=2000,seed=233,outcome_missingness="balanced_random",
                             missing_rate_control=.15,missing_rate_treatment=.15,
                             margin_resolution_follows_outcome=True)
        t=generate_trial(cfg); f=t.records
        for arm in ("control","treatment"):
            rows=f.assignment.eq(arm)
            expected=f.loc[rows,"resolved_90"].astype(bool).to_numpy()
            rows_array=rows.to_numpy()
            np.testing.assert_array_equal(f.loc[rows,"margin_resolved_90"].to_numpy(),expected & t.truth.margin_capture_90[rows_array])
            np.testing.assert_array_equal(f.loc[rows,"margin_resolved_180"].to_numpy(),expected & t.truth.margin_capture_180[rows_array])
        clean=generate_trial(ExperimentConfig(n_customers=1000,seed=234))
        self.assertTrue(clean.records.margin_resolved_90.all())
        self.assertTrue(clean.records.margin_resolved_180.all())

    def test_zero_margin_is_observed_not_missing(self):
        t=generate_trial(ExperimentConfig(n_customers=1000,seed=235,contribution_per_repeat=0,
                                          intervention_cost_per_sent=0,margin_noise_sd=0,
                                          margin_missing_rate=.25))
        f=t.records
        observed=f.margin_90.notna()
        self.assertTrue((f.loc[observed,"margin_90"]==0).all())
        self.assertGreater(int(observed.sum()),0)
        self.assertLess(int(observed.sum()),len(f))
        a=self.analysis(t)
        self.assertEqual(a["commercial"]["90"]["arms"]["treatment"]["complete"],int(f.loc[f.assignment.eq("treatment"),"margin_90"].notna().sum()))

    def test_outcome_dependent_scenario_can_apparently_adopt(self):
        # The hidden departure is deliberately larger than this frozen illustrative range.
        cfg = ExperimentConfig(n_customers=30000, seed=991, eligible_effect=0.20, p_late_repeat=0.20,
                               outcome_missingness="outcome_dependent", missing_rate_control=0.002,
                               missing_rate_treatment=0.002, missing_effect_if_repeat=1.0,
                               margin_resolution_follows_outcome=True,
                               contribution_per_repeat=100, intervention_cost_per_sent=0,
                               p_repeat_180_control=0.45, effect_180_eligible=0.20, margin_noise_sd=0)
        trial = generate_trial(cfg)
        narrow = SensitivityRange(-0.001, 0.001, True, "PRECONFIGURED HYPOTHETICAL RANGE")
        a = self.analysis(trial, sensitivity_range=narrow, margin_bootstrap_reps=100)
        d = decide_adoption(a, sensitivity_range=narrow)
        self.assertEqual(a["missingness_assumptions"]["assumptions_pass"], True)
        self.assertEqual(d["day_90"]["status"], "PROVISIONAL ADOPT WITH HOLDOUT")

    def test_null_outcome_dependent_false_adoption_remains_possible_without_oracle(self):
        # A fixed null randomization draw checks possibility, not frequency.
        cfg=ExperimentConfig(n_customers=4000,seed=54,eligible_effect=0,p_late_repeat=.18,
                            p_repeat_180_control=.35,effect_180_eligible=0,
                            p_complaint_control=0,p_optout_control=0,
                            contribution_per_repeat=30,intervention_cost_per_sent=0,margin_noise_sd=0,
                            outcome_missingness="outcome_dependent",missing_rate_control=.001,
                            missing_rate_treatment=.001,missing_effect_if_repeat=2,
                            margin_resolution_follows_outcome=True)
        t=generate_trial(cfg)
        sensitivity=SensitivityRange(-.001,.001,True,"HYPOTHETICAL SYNTHETIC RANGE")
        a=self.analysis(t,sensitivity_range=sensitivity,margin_bootstrap_reps=1000)
        d=decide_adoption(a,sensitivity_range=sensitivity)
        self.assertEqual(t.truth.population_itt_rd,0)
        self.assertEqual(t.truth.population_itt_margin_90,0)
        self.assertEqual(int((~t.records.resolved_90).sum()),int(t.records.margin_90.isna().sum()))
        self.assertEqual(a["missingness_assumptions"]["assumptions_pass"],True)
        self.assertEqual(a["primary"]["statistical_status"],"PASS")
        self.assertEqual(d["day_90"]["gates"]["margin_90"],"PASS")
        self.assertEqual(d["day_90"]["status"],"PROVISIONAL ADOPT WITH HOLDOUT")

    def test_tipping_mapping_and_extreme_bounds(self):
        cfg = ExperimentConfig(n_customers=1000, seed=44, outcome_missingness="differential", missing_rate_control=.02, missing_rate_treatment=.03)
        t = generate_trial(cfg); a = self.analysis(t)
        p = a["primary"]["arms"]
        r_t = p["treatment"]["n_resolved"]/p["treatment"]["n_randomized"]
        r_c = p["control"]["n_resolved"]/p["control"]["n_randomized"]
        mapped = p["treatment"]["risk_resolved"]+(1-r_t)*.04 - p["control"]["risk_resolved"]-(1-r_c)*(-.03)
        self.assertAlmostEqual(mapped, a["primary"]["rd_resolved"]+(1-r_t)*.04-(1-r_c)*(-.03))
        self.assertIn("adverse_rd", a["extreme_bounds_descriptive_only"])
        self.assertEqual(a["sensitivity"]["outside_range_distance_search_steps"],200)
        self.assertGreaterEqual(a["sensitivity"]["outside_range_distance_resolution_linf"],0)

    def test_guardrail_baselines_and_rare_rates_calibrate(self):
        n = 150000
        cfg = ExperimentConfig(n_customers=n, seed=17, eligible_effect=0, p_complaint_control=.003,
                               p_optout_control=.02, p_optout_pre_day21=.40, complaint_effect=0, optout_effect=0)
        f = generate_trial(cfg).records
        for col,p in (("complaint",.003),("optout_post_randomization",.02)):
            se=sqrt(p*(1-p)/n)
            self.assertLess(abs(f[col].mean()-p), 4*se)
        rare=generate_trial(replace(cfg,p_complaint_control=.001,p_optout_control=.01,seed=18)).records
        self.assertLess(abs(rare.complaint.mean()-.001),4*sqrt(.001*.999/n))
        self.assertLess(abs(rare.optout_post_randomization.mean()-.01),4*sqrt(.01*.99/n))

    def test_guardrail_harm_only_on_delivered_and_itt_by_assignment(self):
        base = ExperimentConfig(n_customers=100000, seed=31, eligible_effect=0, p_early_repeat=0,
                                p_optout_pre_day21=0, p_operationally_contactable=1,
                                p_complaint_control=.01,p_optout_control=.02,complaint_effect=.10,optout_effect=.08)
        none=generate_trial(replace(base,p_delivery=0)).records
        all_del=generate_trial(replace(base,p_delivery=1)).records
        part=generate_trial(replace(base,p_delivery=.5)).records
        for f in (none,all_del,part):
            rates=f.groupby("assignment")[["complaint","optout_post_randomization"]].mean()
            # Control is baseline; treatment RD tracks delivered fraction times configured conditional harm.
            tr=f.assignment.eq("treatment")
            expected_delivery=f.loc[tr,"delivered"].mean()
            self.assertAlmostEqual(rates.loc["treatment","complaint"]-rates.loc["control","complaint"],expected_delivery*.10,delta=.006)
            self.assertAlmostEqual(rates.loc["treatment","optout_post_randomization"]-rates.loc["control","optout_post_randomization"],expected_delivery*.08,delta=.006)
        self.assertFalse(none.loc[none.assignment.eq("treatment"),"delivered"].any())
        self.assertTrue(all_del.loc[all_del.assignment.eq("treatment") & all_del.eligible_day21,"delivered"].all())
        self.assertLess(part.loc[part.assignment.eq("treatment"),"delivered"].mean(),1)

    def test_pre_day21_optouts_are_not_postrandomization_guardrails(self):
        f=generate_trial(ExperimentConfig(n_customers=100000,seed=6,p_optout_pre_day21=.7,p_optout_control=.02,eligible_effect=0)).records
        self.assertGreater(f.optout_pre_day21.mean(),.65)
        self.assertLess(abs(f.optout_post_randomization.mean()-.02),.002)

    def test_guardrail_statuses_and_no_adoption_when_mandatory_gate_fails(self):
        t=generate_trial(ExperimentConfig(n_customers=100,seed=7))
        a=self.analysis(t)
        d=decide_adoption(a,sensitivity_range=SENS,config=DecisionConfig(complaint_margin=-1))
        self.assertEqual(d["day_90"]["gates"]["complaint"],"FAIL")
        self.assertNotEqual(d["day_90"]["status"],"PROVISIONAL ADOPT WITH HOLDOUT")
        no_event={"rd":0,"lower_95":-0.1,"upper_95":0.1}
        self.assertEqual(__import__("src.exp_sim.core",fromlist=["_guardrail_status"])._guardrail_status(no_event,.002),"INCONCLUSIVE")

    def test_zero_events_both_arms_primary_inconclusive_and_missing_diagnostics(self):
        t=generate_trial(ExperimentConfig(n_customers=200,seed=41))
        # Complete ascertainment but no qualifying outcomes in either arm.
        f=t.records.copy(); f["outcome_90"]=0.; f["resolved_90"]=True
        a0=analyze_trial(f,sensitivity_range=SENS,margin_bootstrap_reps=5,missingness_assumptions_approved=True,bootstrap_seed_sequence=t.bootstrap_seed_sequence)
        d0=decide_adoption(a0,sensitivity_range=SENS)
        self.assertEqual(a0["primary"]["statistical_status"],"INCONCLUSIVE")
        self.assertEqual(d0["day_90"]["gates"]["statistical_conversion"],"INCONCLUSIVE")
        # Fully unresolved outcome data have no primary interval and remain inconclusive.
        f["outcome_90"]=np.nan; f["resolved_90"]=False
        a=analyze_trial(f,sensitivity_range=SENS,margin_bootstrap_reps=5,missingness_assumptions_approved=True,bootstrap_seed_sequence=t.bootstrap_seed_sequence)
        self.assertEqual(a["primary"]["statistical_status"],"INCONCLUSIVE")
        self.assertEqual(a["primary"]["ci95"],[None,None])

    def test_all_events_versus_none_decision_cannot_upgrade_degenerate_analysis(self):
        t=generate_trial(ExperimentConfig(n_customers=400,seed=412))
        f=t.records.copy(); f["resolved_90"]=True; f["outcome_90"]=0.0
        f.loc[f.assignment.eq("treatment"),"outcome_90"]=1.0
        a=analyze_trial(f,sensitivity_range=SENS,margin_bootstrap_reps=5,missingness_assumptions_approved=True,bootstrap_seed_sequence=t.bootstrap_seed_sequence)
        self.assertTrue(a["primary"]["degenerate"])
        self.assertEqual(a["primary"]["statistical_status"],"INCONCLUSIVE")
        d=decide_adoption(a,sensitivity_range=SENS)
        self.assertEqual(d["day_90"]["gates"]["statistical_conversion"],"INCONCLUSIVE")
        self.assertNotEqual(d["day_90"]["status"],"PROVISIONAL ADOPT WITH HOLDOUT")

    def test_missing_financial_records_180_triggers_rollback_without_rewriting_day90(self):
        t=generate_trial(ExperimentConfig(n_customers=1000,seed=3))
        a=self.analysis(t)
        d90={"status":"PROVISIONAL ADOPT WITH HOLDOUT"}
        a["commercial"]["180"]["completeness"]=.90
        later=assess_180_day(a,d90)
        self.assertEqual(later["status"],"ROLLBACK")
        self.assertEqual(later["action"],"STOP EXPANSION / ROLLBACK TO BAU")
        self.assertEqual(d90["status"],"PROVISIONAL ADOPT WITH HOLDOUT")
        d_no=decide_adoption(a,sensitivity_range=SENS)
        self.assertEqual(d_no["day_180"]["status"],"NOT APPLICABLE")

    def test_unapproved_range_fails_closed(self):
        t=generate_trial(ExperimentConfig(n_customers=500,seed=30))
        a=self.analysis(t,sensitivity_range=None)
        d=decide_adoption(a,sensitivity_range=None)
        self.assertEqual(d["day_90"]["status"],"INCONCLUSIVE / NOT AUTHORISED")

    def test_seedsequence_spawn_keys_unique_and_reproducible(self):
        cfg=ExperimentConfig(n_customers=120,seed=50)
        reusable=np.random.SeedSequence(99)
        again_a=generate_trial(cfg,seed_sequence=reusable)
        again_b=generate_trial(cfg,seed_sequence=reusable)
        pd.testing.assert_frame_equal(again_a.records,again_b.records)
        replicate_roots=np.random.SeedSequence(98).spawn(2)
        rep_a=generate_trial(cfg,seed_sequence=replicate_roots[0])
        rep_b=generate_trial(cfg,seed_sequence=replicate_roots[1])
        self.assertFalse(rep_a.records.assignment.equals(rep_b.records.assignment))
        a=monte_carlo(cfg,replicates=20,seed=100,sensitivity_range=SENS,margin_bootstrap_reps=5)
        b=monte_carlo(cfg,replicates=20,seed=100,sensitivity_range=SENS,margin_bootstrap_reps=5)
        self.assertEqual(a,b)
        keys=[tuple(x["spawn_key"]) for x in a["replicate_seed_streams"]]
        self.assertEqual(len(keys),len(set(keys)))
        self.assertEqual(len(keys),20)
        many=np.random.SeedSequence(777).spawn(10000)
        many_keys=[tuple(s.spawn_key) for s in many]
        self.assertEqual(len(many_keys),len(set(many_keys)))
        component_roots=np.random.SeedSequence(778).spawn(2)
        component_boot=[generate_trial(cfg,seed_sequence=s).bootstrap_seed_sequence.spawn_key for s in component_roots]
        self.assertNotEqual(component_boot[0],component_boot[1])

    def test_mcse_and_effective_denominator(self):
        m=_probability_metric([True,False,True,True],denominator_mask=[True,True,True,False])
        self.assertEqual((m["numerator"],m["denominator"]),(2,3))
        self.assertAlmostEqual(m["estimate"],2/3)
        self.assertAlmostEqual(m["mcse"],sqrt((2/3)*(1/3)/3))
        zero=_probability_metric([False]*10)
        one=_probability_metric([True]*10)
        self.assertEqual(zero["mcse"],0)
        self.assertGreater(zero["ci95_wilson"][1],0)
        self.assertLess(one["ci95_wilson"][0],1)
        t=generate_trial(ExperimentConfig(n_customers=250,seed=12))
        mc=monte_carlo(ExperimentConfig(n_customers=250,seed=12),replicates=6,seed=13,sensitivity_range=SENS,margin_bootstrap_reps=5)
        metric=mc["probability_metrics"]["ci_coverage_conditional_on_defined"]
        self.assertLessEqual(metric["denominator"],6)
        self.assertEqual(mc["effective_denominators"]["all_replicates"],6)
        self.assertIn("false_statistical_positive_when_population_itt_nonpositive",mc["probability_metrics"])
        self.assertIn("false_provisional_adoption_when_true_margin_below_threshold",mc["probability_metrics"])

    def test_same_day_sensitivity_resolved_only_and_order_status_retains_itt(self):
        t=generate_trial(ExperimentConfig(n_customers=2000,seed=4,same_day_ambiguous_rate=.3,p_first_order_status_error=.1,p_first_order_later_cancelled=.2))
        a=self.analysis(t)
        f=t.records
        self.assertGreater(a["ascertainment"]["same_day_ambiguous_count"],0)
        self.assertEqual(sum(x["n_randomized"] for x in a["primary"]["arms"].values()),len(f))
        self.assertEqual(a["ascertainment"]["completeness"],1)
        self.assertEqual(a["same_day_sensitivity"]["primary_ambiguous_candidates_counted_as_non_events"],True)

    def test_private_path_guard_and_no_readers(self):
        with self.assertRaises(ValueError): write_simulation_result({},REPO/".local"/"b2b3-outcome-output"/"bad.json")
        for path in (REPO/"src"/"exp_sim").glob("*.py"):
            tree=ast.parse(path.read_text())
            attrs={n.func.attr for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)}
            self.assertFalse(attrs & {"read_csv","read_parquet","read_excel","read_pickle"})
            self.assertNotIn("read_csv(\"",path.read_text())

    def test_no_scipy_dependency(self):
        tree=ast.parse(Path(__file__).read_text())
        imports=[n for n in ast.walk(tree) if isinstance(n,(ast.Import,ast.ImportFrom))]
        self.assertFalse(any((n.module or "").startswith("scipy") for n in imports if isinstance(n,ast.ImportFrom)))
        self.assertFalse(any(alias.name.startswith("scipy") for n in imports if isinstance(n,ast.Import) for alias in n.names))


if __name__ == "__main__":
    unittest.main()
