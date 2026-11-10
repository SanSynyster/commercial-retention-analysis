from __future__ import annotations

from dataclasses import replace
import gzip
import json
from pathlib import Path
import shutil
import unittest
import uuid
from unittest.mock import patch
import time

import src.exp_sim.campaign as campaign_module
from src.exp_sim.campaign import (
    FULL_CAMPAIGN_SEED, MIN_CAMPAIGN_CUSTOMERS, SCENARIO_NAMES,
    run_campaign, scenario_matrix, scenario_truth, validate_scenario_matrix,
)
from src.exp_sim.core import ExperimentConfig, SensitivityRange, generate_trial, monte_carlo


class ScenarioCampaignTests(unittest.TestCase):
    def test_matrix_contains_eight_valid_hypothetical_scenarios(self):
        configs=scenario_matrix(n_customers=600,seed=781)
        self.assertEqual(tuple(configs),SCENARIO_NAMES)
        self.assertEqual(len(configs),8)
        self.assertEqual(len({c.seed for c in configs.values()}),1)  # shared ID seed; MC streams vary by family
        for config in configs.values():
            config.validate()
            if config.outcome_missingness != "complete":
                self.assertTrue(config.margin_resolution_follows_outcome)

    def test_campaign_defaults_use_assurance_sample_and_fresh_seed(self):
        self.assertGreaterEqual(MIN_CAMPAIGN_CUSTOMERS, 25_000)
        self.assertNotIn(FULL_CAMPAIGN_SEED, (20261109, 20261110))
        np=__import__("numpy")
        scenario_seeds=np.random.SeedSequence(FULL_CAMPAIGN_SEED).spawn(len(SCENARIO_NAMES))
        identities={(int(child.entropy),child.spawn_key+(replicate_id,))
                    for child in scenario_seeds for replicate_id in range(10_000)}
        self.assertEqual(len(identities),80_000)
        prior={(int(child.entropy),child.spawn_key+(replicate_id,))
               for child in np.random.SeedSequence(20261109).spawn(len(SCENARIO_NAMES))
               for replicate_id in range(10_000)}
        self.assertTrue(identities.isdisjoint(prior))

    def test_scenario_truth_and_recalibration(self):
        configs=scenario_matrix(n_customers=25_000,seed=20261110)
        truth={name:scenario_truth(config,name) for name,config in configs.items()}
        self.assertEqual(configs["C_random_missingness"].missing_rate_control,.015)
        self.assertEqual(configs["C_random_missingness"].missing_rate_treatment,.015)
        self.assertGreater(truth["C_random_missingness"]["expected_missing_fraction_by_arm"]["control"],0)
        self.assertLess(truth["C_random_missingness"]["expected_missing_fraction_by_arm"]["control"],.02)
        d=configs["D_outcome_dependent_missingness"]
        self.assertEqual(d.missing_rate_control,d.missing_rate_treatment)
        self.assertEqual(d.outcome_missingness,"outcome_dependent")
        dt=truth["D_outcome_dependent_missingness"]["expected_missing_fraction_by_arm"]
        self.assertLess(abs(dt["treatment"]-dt["control"]),.01)
        # Equal base rates make diagnostics more likely to pass; the truth
        # calculation does not assert that realized diagnostics must pass.
        e=truth["E_rare_experience_harm"]
        self.assertGreater(e["complaint_itt_risk_difference"],.002)
        self.assertGreater(e["optout_itt_risk_difference"],.005)
        self.assertFalse(e["day90_adoption_scientifically_plausible"])
        b,g=configs["B_positive_persistent_effect"],configs["G_purchase_acceleration"]
        self.assertEqual([k for k in b.__dict__ if b.__dict__[k]!=g.__dict__[k]], ["effect_180_eligible"])
        self.assertGreater(truth["B_positive_persistent_effect"]["population_incremental_margin_90"],.5)
        self.assertGreater(truth["B_positive_persistent_effect"]["population_incremental_margin_180"],0)
        self.assertTrue(truth["B_positive_persistent_effect"]["day90_adoption_scientifically_plausible"])
        self.assertTrue(truth["B_positive_persistent_effect"]["day180_confirmation_scientifically_plausible"])

    def test_h_false_commercial_adoption_truth_masking_and_diagnostics(self):
        configs=scenario_matrix(n_customers=25_000,seed=20261111)
        h=configs["H_mnar_below_commercial_hurdle"]
        truth=scenario_truth(h,"H_mnar_below_commercial_hurdle")
        self.assertEqual(h.eligible_effect,.04)
        self.assertEqual(h.effect_180_eligible,.04)
        self.assertEqual(h.missing_rate_control,.012)
        self.assertEqual(h.missing_rate_treatment,.008)
        self.assertEqual(h.missing_effect_if_repeat,2.0)
        self.assertTrue(h.margin_resolution_follows_outcome)
        self.assertAlmostEqual(truth["population_itt_rd_90"],.722*.04,places=12)
        self.assertAlmostEqual(truth["population_itt_rd_180"],.722*.04,places=12)
        self.assertAlmostEqual(truth["population_incremental_margin_90"],.722*(.04*20-.35),places=12)
        self.assertAlmostEqual(truth["population_incremental_margin_180"],.722*(.04*20-.35),places=12)
        self.assertFalse(truth["day90_adoption_scientifically_plausible"])
        self.assertTrue(truth["day180_confirmation_scientifically_plausible"])
        self.assertTrue(truth["expected_observable_outcome_diagnostics_pass_at_truth_rates"])
        self.assertFalse(truth["expected_margin_completeness_gate_pass_at_truth_rates"])
        self.assertAlmostEqual(truth["expected_resolved_risk_difference_bias_vs_population_itt"],.0017334677673784445,places=10)
        trial=generate_trial(h)
        unresolved=~trial.records["resolved_90"]
        self.assertGreater(int(unresolved.sum()),0)
        self.assertTrue(trial.records.loc[unresolved,"outcome_90"].isna().all())
        self.assertTrue(trial.records.loc[unresolved,"margin_90"].isna().all())

    def test_h_rows_expose_commercial_decisions_without_reconstructing_metrics_from_truth(self):
        config=scenario_matrix(n_customers=2500,seed=777)["H_mnar_below_commercial_hurdle"]
        result=monte_carlo(config,replicates=3,seed=778,
                           sensitivity_range=SensitivityRange(-.1,.1,True,"test"),
                           margin_bootstrap_reps=10)
        rows=result["replicate_results"]
        for row in rows:
            for key in ("estimated_incremental_margin_90","incremental_margin_90_ci95",
                        "margin_gate_90","margin_completeness_gate_90",
                        "estimated_incremental_margin_180","incremental_margin_180_ci95",
                        "margin_gate_180","margin_completeness_gate_180",
                        "day90_non_adoption_reasons","day180_decision_reason",
                        "day180_decision_action"):
                self.assertIn(key,row)
        estimated=[r["estimated_incremental_margin_90"] for r in rows if r["estimated_incremental_margin_90"] is not None]
        self.assertAlmostEqual(result["continuous_metrics"]["estimated_incremental_margin_90"]["mean"],sum(estimated)/len(estimated))
        adoption=result["probability_metrics"]["day90_provisional_adoption"]
        rollback=result["probability_metrics"]["rollback_given_provisional_adoption"]
        self.assertEqual(rollback["denominator"],adoption["numerator"])
        self.assertEqual(rollback,result["probability_metrics"]["day180_rollback_given_90_provisional"])
        for horizon in ("90","180"):
            status_field=f"margin_gate_{horizon}"
            for state in ("PASS","FAIL","INCONCLUSIVE"):
                key=f"margin_{horizon}_gate_{state.lower()}"
                self.assertEqual(result["probability_metrics"][key]["numerator"],
                                 sum(r[status_field]==state for r in rows))
        self.assertEqual(result["probability_metrics"]["false_provisional_adoption_when_true_margin_below_threshold"]["denominator"],3)
        self.assertEqual(result["probability_metrics"]["false_statistical_rejection_under_known_truth"]["denominator"],3)
        self.assertEqual(result["probability_metrics"]["false_day180_confirmation_when_true_margin_below_threshold"]["denominator"],0)

    def test_zero_provisional_adoptions_gives_undefined_conditional_rollback(self):
        configs=scenario_matrix(n_customers=500,seed=779)
        result=monte_carlo(configs["A_clean_null"],replicates=3,seed=780,
                           sensitivity_range=SensitivityRange(-.1,.1,True,"test"),margin_bootstrap_reps=5)
        metric=result["probability_metrics"]["rollback_given_provisional_adoption"]
        self.assertEqual(metric["denominator"],0)
        self.assertIsNone(metric["estimate"])
        self.assertIsNone(metric["mcse"])

    def test_matrix_rejects_missing_financial_mask_for_unresolved_outcomes(self):
        configs=scenario_matrix(n_customers=600,seed=782)
        configs["C_random_missingness"]=replace(configs["C_random_missingness"],margin_resolution_follows_outcome=False)
        with self.assertRaisesRegex(ValueError,"linked financial masking"):
            validate_scenario_matrix(configs)

    def test_unresolved_purchase_outcomes_mask_all_linked_financial_fields(self):
        configs=scenario_matrix(n_customers=5000,seed=787)
        for name in ("C_random_missingness", "D_outcome_dependent_missingness"):
            trial=generate_trial(configs[name])
            unresolved=~trial.records["resolved_90"]
            self.assertGreater(int(unresolved.sum()),0)
            self.assertTrue(trial.records.loc[unresolved,"outcome_90"].isna().all())
            self.assertTrue(trial.records.loc[unresolved,"margin_90"].isna().all())
            self.assertTrue(trial.records.loc[unresolved,"margin_180"].isna().all())
            self.assertFalse(any("truth" in column or "hidden" in column for column in trial.records.columns))

    def test_ground_truth_distinguishes_persistent_effect_from_acceleration(self):
        configs=scenario_matrix(n_customers=1000,seed=783)
        persistent=scenario_truth(configs["B_positive_persistent_effect"])
        accelerated=scenario_truth(configs["G_purchase_acceleration"])
        self.assertGreater(persistent["population_itt_rd_90"],0)
        self.assertGreater(persistent["population_itt_rd_180"],0)
        self.assertGreater(accelerated["population_itt_rd_90"],0)
        self.assertEqual(accelerated["population_itt_rd_180"],0)
        self.assertFalse(accelerated["day180_independent_replication"])

    def test_generator_exhibits_catch_up_in_acceleration_scenario(self):
        config=scenario_matrix(n_customers=120000,seed=784)["G_purchase_acceleration"]
        truth=generate_trial(config).truth
        self.assertGreater(truth.population_itt_rd,0)
        self.assertEqual(truth.population_itt_rd_180,0)
        self.assertGreater(truth.finite_population_sate,0)
        self.assertEqual(truth.finite_population_sate_180,0)
        self.assertTrue((truth.potential_treatment_90 <= truth.potential_treatment_180).all())

    def test_mc_reports_estimands_denominators_and_day180_nonindependence(self):
        configs=scenario_matrix(n_customers=400,seed=785)
        sensitivity=SensitivityRange(-.10,.10,True,"HYPOTHETICAL TEST RANGE")
        config=configs["A_clean_null"]
        result=monte_carlo(config,replicates=3,seed=9001,sensitivity_range=sensitivity,margin_bootstrap_reps=5)
        self.assertEqual(result["data_generating_parameters"],config.__dict__)
        self.assertEqual(result["simulator_evaluation_only"]["population_itt_rd_90"],0)
        self.assertEqual(result["simulator_evaluation_only"]["population_itt_rd_180"],0)
        self.assertFalse(result["longitudinal_interpretation"]["day180_is_independent_replication"])
        metrics=result["probability_metrics"]
        for key in ("type_i_error_unconditional","power_unconditional","ci_coverage_conditional_on_defined",
                    "day90_inconclusive","any_guardrail_inconclusive","day90_provisional_adoption",
                    "primary_statistical_inconclusive_rate","primary_statistical_fail_rate",
                    "outcome_ascertainment_diagnostics_pass",
                    "complaint_guardrail_fail","optout_guardrail_fail",
                    "day180_confirm_marginal","day180_rollback_marginal",
                    "joint_90_provisional_and_180_confirm",
                    "false_adoption_day180_confirm_given_false_adoption",
                    "false_day180_confirmation_when_true_margin_below_threshold"):
            self.assertIn(key,metrics)
            self.assertIsNotNone(metrics[key]["denominator"])
        self.assertEqual(metrics["type_i_error_unconditional"]["denominator"],3)
        self.assertEqual(result["effective_denominators"]["all_replicates"],3)
        self.assertEqual(result["replicate_results"][0]["replicate_id"],0)
        self.assertEqual(metrics["false_day180_confirmation_when_true_margin_below_threshold"]["denominator"],3)
        self.assertIn("primary_arm_counts",result["replicate_results"][0])
        rows=result["replicate_results"]
        self.assertEqual(sum(r["primary_statistical_status"]=="INCONCLUSIVE" for r in rows),
                         metrics["primary_statistical_inconclusive_rate"]["numerator"])
        self.assertEqual(sum(r["complaint_state"]=="FAIL" for r in rows),
                         metrics["complaint_guardrail_fail"]["numerator"])
        self.assertEqual(sum(r["optout_state"]=="FAIL" for r in rows),
                         metrics["optout_guardrail_fail"]["numerator"])

    def test_replicate_streams_are_stable_across_block_boundaries(self):
        cfg=scenario_matrix(n_customers=180,seed=788)["A_clean_null"]
        root=__import__("numpy").random.SeedSequence(123456).spawn(8)[2]
        kwargs=dict(seed_sequence=root,sensitivity_range=SensitivityRange(-.1,.1,True,"test"),margin_bootstrap_reps=2)
        whole=monte_carlo(cfg,replicates=5,**kwargs)["replicate_results"]
        first=monte_carlo(cfg,replicates=2,replicate_start=0,**kwargs)["replicate_results"]
        second=monte_carlo(cfg,replicates=3,replicate_start=2,**kwargs)["replicate_results"]
        self.assertEqual(whole,first+second)

    def test_checkpoint_resume_and_output_rows_are_deterministic(self):
        root=Path(__file__).resolve().parents[1]/".local"/"exp-sim-output"/"tests"
        path=root/uuid.uuid4().hex
        comparison_path=root/uuid.uuid4().hex
        try:
            kwargs=dict(replicates=4,n_customers=120,seed=54321,margin_bootstrap_reps=2,
                        max_seconds=120,scenario_timeout_seconds=60,memory_limit_mib=1536,
                        allow_small_sample=True)
            first=run_campaign(block_size=2,output_dir=path,**kwargs)
            # Simulate interruption after the first A block; resume with a
            # different block size must fill only missing replicate IDs.
            (path/"A_clean_null"/"block-00000002-00000004.jsonl.gz").unlink()
            second=run_campaign(block_size=3,output_dir=path,resume=True,**kwargs)
            comparison=run_campaign(block_size=3,output_dir=comparison_path,**kwargs)
            self.assertEqual(first["status"],"COMPLETE")
            self.assertEqual(second["status"],"COMPLETE")
            self.assertEqual(comparison["status"],"COMPLETE")
            self.assertEqual(len(second["scenarios"]),8)
            self.assertEqual(tuple(second["scenarios"]),SCENARIO_NAMES)
            for scenario_name in SCENARIO_NAMES:
                scenario_summary=json.loads((path/scenario_name/"summary.json").read_text())
                reference_scenario=json.loads((comparison_path/scenario_name/"summary.json").read_text())
                self.assertEqual(scenario_summary["probability_metrics"],reference_scenario["probability_metrics"])
                self.assertEqual(scenario_summary["continuous_metrics"],reference_scenario["continuous_metrics"])
                def read_scenario_rows(summary):
                    rows=[]
                    for item in summary["replicate_record_blocks"]:
                        with gzip.open(Path(__file__).resolve().parents[1]/item["path"],"rt",encoding="utf-8") as stream:
                            next(stream)
                            rows.extend(json.loads(line) for line in stream)
                    return rows
                self.assertEqual(read_scenario_rows(scenario_summary),read_scenario_rows(reference_scenario))
            summary=json.loads((path/"A_clean_null"/"summary.json").read_text())
            reference=json.loads((comparison_path/"A_clean_null"/"summary.json").read_text())
            self.assertEqual(summary["effective_denominators"]["all_replicates"],4)
            self.assertIn("replicate_record_blocks",summary)
            self.assertEqual(len(summary["replicate_record_blocks"]),3)
            self.assertEqual(summary["probability_metrics"],reference["probability_metrics"])
            rows=[]
            for item in summary["replicate_record_blocks"]:
                with gzip.open(Path(__file__).resolve().parents[1]/item["path"],"rt",encoding="utf-8") as stream:
                    next(stream)
                    rows.extend(json.loads(line) for line in stream)
            self.assertEqual([row["replicate_id"] for row in rows],[0,1,2,3])
            reference_rows=[]
            for item in reference["replicate_record_blocks"]:
                with gzip.open(Path(__file__).resolve().parents[1]/item["path"],"rt",encoding="utf-8") as stream:
                    next(stream)
                    reference_rows.extend(json.loads(line) for line in stream)
            self.assertEqual(rows,reference_rows)
            self.assertEqual(summary["probability_metrics"]["primary_statistical_inconclusive_rate"]["denominator"],4)
        finally:
            shutil.rmtree(path,ignore_errors=True)
            shutil.rmtree(comparison_path,ignore_errors=True)

    def test_resume_refuses_corrupt_or_incompatible_checkpoints(self):
        root=Path(__file__).resolve().parents[1]/".local"/"exp-sim-output"/"tests"
        path=root/uuid.uuid4().hex
        kwargs=dict(replicates=2,n_customers=100,seed=54322,margin_bootstrap_reps=1,
                    max_seconds=120,scenario_timeout_seconds=60,memory_limit_mib=1536,
                    allow_small_sample=True)
        try:
            run_campaign(block_size=1,output_dir=path,**kwargs)
            with self.assertRaisesRegex(ValueError,"incompatible"):
                run_campaign(block_size=1,output_dir=path,resume=True,**{**kwargs,"seed":54323})
            block=next((path/"A_clean_null").glob("block-*.jsonl.gz"))
            block.write_bytes(b"corrupt")
            with self.assertRaisesRegex(ValueError,"Corrupt checkpoint"):
                run_campaign(block_size=1,output_dir=path,resume=True,**kwargs)
        finally:
            shutil.rmtree(path,ignore_errors=True)

    def test_campaign_requires_assurance_sample_unless_smoke_override(self):
        root=Path(__file__).resolve().parents[1]/".local"/"exp-sim-output"/"tests"/uuid.uuid4().hex
        with self.assertRaisesRegex(ValueError,">=25,000"):
            run_campaign(replicates=1,n_customers=100,output_dir=root)

    def test_wall_clock_timeout_saves_incomplete_manifest(self):
        root=Path(__file__).resolve().parents[1]/".local"/"exp-sim-output"/"tests"/uuid.uuid4().hex
        try:
            with patch("src.exp_sim.campaign.monte_carlo",side_effect=lambda *a,**k: time.sleep(2)):
                result=run_campaign(replicates=1,n_customers=25_000,seed=54324,
                                    margin_bootstrap_reps=1,block_size=1,max_seconds=5,
                                    scenario_timeout_seconds=1,memory_limit_mib=1536,
                                    output_dir=root)
            self.assertEqual(result["status"],"INCOMPLETE_TIME_LIMIT")
            self.assertEqual(result["scenarios"]["A_clean_null"]["status"],"TIME_LIMIT")
            self.assertTrue((root/"campaign-manifest.json").exists())
            self.assertFalse(list(root.rglob("block-*.jsonl.gz")))
        finally:
            shutil.rmtree(root,ignore_errors=True)

    def test_memory_stop_status_and_unsafe_output_refusal(self):
        root=Path(__file__).resolve().parents[1]/".local"/"exp-sim-output"/"tests"/uuid.uuid4().hex
        try:
            with patch("src.exp_sim.campaign.monte_carlo",side_effect=MemoryError("test stop")):
                result=run_campaign(replicates=1,n_customers=25_000,seed=54325,
                                    margin_bootstrap_reps=1,block_size=1,max_seconds=10,
                                    scenario_timeout_seconds=5,memory_limit_mib=1536,
                                    output_dir=root)
            self.assertEqual(result["status"],"INCOMPLETE_MEMORY_LIMIT")
            self.assertEqual(result["scenarios"]["A_clean_null"]["status"],"MEMORY_LIMIT")
        finally:
            shutil.rmtree(root,ignore_errors=True)
        with self.assertRaisesRegex(ValueError,"under .local/exp-sim-output"):
            campaign_module._campaign_root("/tmp/exp-sim-outside")

    def test_longitudinal_followup_uses_same_customers_and_seeded_campaign_repeats(self):
        config=scenario_matrix(n_customers=300,seed=786)["G_purchase_acceleration"]
        kwargs=dict(replicates=2,seed=9002,sensitivity_range=SensitivityRange(-.1,.1,True,"test"),margin_bootstrap_reps=5)
        a=monte_carlo(config,**kwargs)
        b=monte_carlo(config,**kwargs)
        self.assertEqual(a,b)
        self.assertTrue(a["longitudinal_interpretation"]["same_synthetic_customers_at_day90_and_day180"])
        self.assertTrue(a["longitudinal_interpretation"]["shared_purchase_latent_draw"])


if __name__ == "__main__":
    unittest.main()
