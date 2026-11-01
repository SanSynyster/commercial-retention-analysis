import unittest
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

import numpy as np
import pandas as pd

import COMMERCIAL_DS_003_PURCHASE_OCCASIONS as purchase_module
import COMMERCIAL_DS_003_REVENUE_BRIDGE as bridge_module
from COMMERCIAL_DS_003_PURCHASE_OCCASIONS import (
    ACQUISITION_CUTOFF, DATA_END_DATE, PRIMARY_REPEAT_DAYS,
    _build_purchase_occasions_for_test, build_purchase_occasions, build_real_data_report,
    feature_window_contains, load_validated_purchase_input,
    invoice_level_repeat, label_is_mature, primary_later_day_repeat,
    rows_before_anchor, summarize_repeat_purchases,
)
from COMMERCIAL_DS_003_REVENUE_BRIDGE import build_revenue_bridge


class PurchaseOccasionBuilderTests(unittest.TestCase):
    def row(self, **changes):
        value={"source_row_number":10,"category":"merchandise","CustomerID":12345,
            "InvoiceNo":"500001","InvoiceDate":pd.Timestamp("2011-01-01 10:00:00"),
            "Quantity":2,"UnitPrice":3.25}
        value.update(changes)
        return value

    def build(self, *rows):
        return _build_purchase_occasions_for_test(pd.DataFrame(list(rows)))

    def test_positive_merchandise_group_and_exact_gross(self):
        occasions,summary=self.build(self.row(),self.row(source_row_number=11,Quantity=1,UnitPrice=0.125))
        self.assertEqual(len(occasions),1)
        self.assertEqual(occasions[0]["source_row_numbers"],[10,11])
        self.assertEqual(occasions[0]["qualifying_gross_merchandise"],"6.625")
        self.assertEqual(summary["eligible_line_count"] if "eligible_line_count" in summary else summary["qualifying_line_count"],2)

    def test_non_merchandise_and_nonpositive_rows_are_excluded(self):
        rows=[self.row(source_row_number=1,category="shipping"),self.row(source_row_number=2,Quantity=-1),
            self.row(source_row_number=3,Quantity=0),self.row(source_row_number=4,UnitPrice=0),
            self.row(source_row_number=5,category="standalone_manual_credit")]
        occasions,summary=_build_purchase_occasions_for_test(pd.DataFrame(rows))
        self.assertEqual(occasions,[])
        self.assertEqual(summary["qualifying_gross_merchandise"],"0")

    def test_missing_and_invalid_timestamps_fail_closed(self):
        for value in (None,pd.NaT,np.datetime64("NaT"),datetime(2011,1,1,tzinfo=timezone.utc)):
            with self.assertRaises((ValueError,TypeError),msg=repr(value)):
                self.build(self.row(InvoiceDate=value))
        for value in ("2011-01-01",date(2011,1,1)):
            with self.assertRaises(TypeError,msg=repr(value)):
                self.build(self.row(InvoiceDate=value))

    def test_observation_end_timestamp_boundary(self):
        occasions,_=self.build(self.row(InvoiceDate=pd.Timestamp("2011-12-09 12:50:00")))
        self.assertEqual(len(occasions),1)
        for value in (pd.Timestamp("2011-12-09 12:50:01"),pd.Timestamp("2011-12-10 00:00:00")):
            occasions,summary=self.build(self.row(InvoiceDate=value))
            self.assertEqual(occasions,[])
            self.assertEqual(summary["excluded_rows_by_reason"]["outside_observation_window"],1)

    def test_cancellation_normalisation_and_invoice_whitespace(self):
        for invoice in ("C500001","c500001"):
            occasions,_=self.build(self.row(InvoiceNo=invoice))
            self.assertEqual(occasions,[])
        with self.assertRaisesRegex(ValueError,"invoice identifier"):
            self.build(self.row(InvoiceNo=" C500001"))
        with self.assertRaisesRegex(ValueError,"invoice identifier"):
            self.build(self.row(InvoiceNo="500001 "))

    def test_customer_ids_fail_closed_without_string_coercion(self):
        for cid in (-5,0):
            with self.assertRaisesRegex(ValueError,"must be positive"):
                self.build(self.row(CustomerID=cid))
        for cid in (" 12345 ","1e3"):
            with self.assertRaisesRegex(ValueError,"customer identifier"):
                self.build(self.row(CustomerID=cid))
        with self.assertRaisesRegex(ValueError,"not an integer"):
            self.build(self.row(CustomerID=12345.5))
        with self.assertRaisesRegex(ValueError,"lossless numeric bound"):
            self.build(self.row(CustomerID=1e20))

    def test_fractional_quantity_excluded_and_mixed_sign_invoice(self):
        occasions,summary=self.build(self.row(Quantity=1.5),self.row(source_row_number=11,Quantity=-1),
            self.row(source_row_number=12,Quantity=2),
            self.row(source_row_number=13,InvoiceNo="500002",InvoiceDate=pd.Timestamp("2011-01-01 12:00"),Quantity=2))
        self.assertEqual(len(occasions),2)
        self.assertEqual(summary["excluded_rows_by_reason"]["non_integral_quantity"],1)
        self.assertEqual([o["invoice_id"] for o in occasions],["500001","500002"])
        self.assertTrue(all(o["qualifying_gross_merchandise"]=="6.50" for o in occasions))

    def test_invalid_and_missing_invoice_ids(self):
        with self.assertRaisesRegex(ValueError,"missing invoice identifier"):
            self.build(self.row(InvoiceNo=None))
        with self.assertRaisesRegex(ValueError,"invalid invoice identifier"):
            self.build(self.row(InvoiceNo=""))

    def test_source_identity_required_unique_and_order_invariant(self):
        with self.assertRaisesRegex(ValueError,"source_row_number is required"):
            _build_purchase_occasions_for_test(pd.DataFrame([self.row()]).drop(columns="source_row_number"))
        with self.assertRaisesRegex(TypeError,"requires load_validated_purchase_input"):
            build_purchase_occasions(pd.DataFrame([self.row()]).drop(columns="source_row_number"))
        with self.assertRaisesRegex(ValueError,"duplicate source_row_number"):
            self.build(self.row(),self.row())
        rows=[self.row(source_row_number=12,InvoiceNo="500002"),self.row(source_row_number=10),self.row(source_row_number=11)]
        a,_=_build_purchase_occasions_for_test(pd.DataFrame(rows));b,_=_build_purchase_occasions_for_test(pd.DataFrame(list(reversed(rows))))
        self.assertEqual(a,b)
        self.assertEqual(a[0]["source_row_numbers"],[10,11])

    def test_invoice_customer_validation_spans_categories(self):
        rows=[self.row(source_row_number=1),self.row(source_row_number=2,CustomerID=67890,category="shipping")]
        with self.assertRaisesRegex(ValueError,"multiple identified customers"):
            _build_purchase_occasions_for_test(pd.DataFrame(rows))

    def test_same_day_invoices_remain_distinct_occasions(self):
        rows=[self.row(source_row_number=1,InvoiceNo="500001"),self.row(source_row_number=2,InvoiceNo="500002")]
        occasions,summary=_build_purchase_occasions_for_test(pd.DataFrame(rows))
        self.assertEqual((summary["occasion_count"],summary["customer_count"]),(2,1))
        self.assertEqual({x["transaction_date"] for x in occasions},{"2011-01-01"})

    def test_temporal_boundaries(self):
        anchor=datetime(2020,1,1)
        self.assertTrue(feature_window_contains(anchor-timedelta(days=90),anchor,90))
        self.assertFalse(feature_window_contains(anchor,anchor,90))
        self.assertFalse(feature_window_contains(anchor+timedelta(days=1),anchor,90))
        self.assertTrue(primary_later_day_repeat(anchor,anchor+timedelta(days=1)))
        self.assertTrue(primary_later_day_repeat(anchor,anchor+timedelta(days=89)))
        self.assertFalse(primary_later_day_repeat(anchor,anchor))
        self.assertFalse(primary_later_day_repeat(anchor,anchor+timedelta(days=90)))
        first_day=datetime(2020,1,1,10)
        same_day=datetime(2020,1,1,15)
        at_boundary=datetime(2020,3,31)
        self.assertFalse(primary_later_day_repeat(anchor,anchor))
        self.assertTrue(invoice_level_repeat(first_day,"I1",same_day,"I2"))
        self.assertTrue(invoice_level_repeat(same_day,"I2",first_day,"I1"))
        self.assertFalse(invoice_level_repeat(first_day,"I1",at_boundary,"I3"))
        self.assertTrue(label_is_mature(datetime.combine(DATA_END_DATE-timedelta(days=PRIMARY_REPEAT_DAYS),datetime.min.time())))
        self.assertFalse(label_is_mature(datetime.combine(DATA_END_DATE-timedelta(days=PRIMARY_REPEAT_DAYS)+timedelta(days=1),datetime.min.time())))
        self.assertEqual(ACQUISITION_CUTOFF,date(2010,12,1))
        for invalid in ("2020-01-01",date(2020,1,1),pd.NaT,np.datetime64("2020-01-01"),datetime(2020,1,1,tzinfo=timezone.utc)):
            with self.assertRaises((ValueError,TypeError)):
                primary_later_day_repeat(invalid,anchor)
        with self.assertRaises(ValueError):label_is_mature(datetime(2020,1,1,1))
        with self.assertRaises(TypeError):feature_window_contains("2019-12-31",anchor,90)
        with self.assertRaises(TypeError):label_is_mature("2020-01-01")

    def test_repeat_summary_is_order_invariant_and_collapses_customer_days(self):
        d=datetime(2020,1,1)
        records=[
            {"customer_id":"1","invoice_id":"B","transaction_timestamp":d,"source_row_numbers":[2]},
            {"customer_id":"1","invoice_id":"A","transaction_timestamp":d,"source_row_numbers":[1]},
            {"customer_id":"1","invoice_id":"C","transaction_timestamp":d+timedelta(days=89),"source_row_numbers":[3]},
            {"customer_id":"1","invoice_id":"D","transaction_timestamp":d+timedelta(days=90),"source_row_numbers":[4]},
            {"customer_id":"2","invoice_id":"F","transaction_timestamp":d,"source_row_numbers":[6]},
            {"customer_id":"2","invoice_id":"E","transaction_timestamp":d,"source_row_numbers":[5]},
            {"customer_id":"3","invoice_id":"G","transaction_timestamp":d,"source_row_numbers":[7]},
            {"customer_id":"3","invoice_id":"H","transaction_timestamp":d+timedelta(days=90),"source_row_numbers":[8]},
        ]
        forward=summarize_repeat_purchases(records)
        backward=summarize_repeat_purchases(list(reversed(records)))
        self.assertEqual(forward,backward)
        self.assertEqual(forward["date_level_repeat_customers"],1)
        self.assertEqual(forward["invoice_level_sensitivity_repeat_customers"],2)

    def test_nonqualifying_invoice_rows_still_require_one_calendar_date(self):
        rows=[self.row(source_row_number=1),self.row(source_row_number=2,category="shipping",InvoiceDate=pd.Timestamp("2011-01-02"))]
        with self.assertRaisesRegex(ValueError,"inconsistent calendar dates"):
            self.build(*rows)

    def test_A_adjustment_invoice_grammar_is_non_purchase(self):
        occasions,summary=self.build(self.row(InvoiceNo="A563185"))
        self.assertEqual(occasions,[])
        self.assertEqual(summary["excluded_rows_by_reason"]["administrative_invoice_id"],1)

    def test_point_in_time_truncation_uses_only_rows_before_anchor(self):
        anchor=datetime(2011,1,1)
        frame=pd.DataFrame({"InvoiceDate":[pd.Timestamp("2010-12-31 23:59"),pd.Timestamp("2011-01-01"),pd.Timestamp("2011-02-01")],"value":[1,2,3]})
        before=rows_before_anchor(frame,anchor)
        mutated=frame.copy();mutated.loc[2,"value"]=999
        self.assertEqual(rows_before_anchor(mutated,anchor).to_dict("records"),before.to_dict("records"))
        with self.assertRaises(TypeError):rows_before_anchor(frame.assign(InvoiceDate=frame.InvoiceDate.astype(str)),anchor)


class RealCorrectedV2OccasionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validated=load_validated_purchase_input()
        cls.report=build_real_data_report(cls.validated)
        cls.bridge=build_revenue_bridge(cls.validated)

    def test_independent_occasion_reference_reconciliation(self):
        summary=self.report["purchase_occasion_summary"]
        self.assertEqual(summary["qualifying_line_count"],788127)
        self.assertEqual(summary["occasion_count"],36594)
        self.assertEqual(summary["customer_count"],5852)
        self.assertEqual(summary["qualifying_gross_merchandise"],"17123740.997")
        self.assertEqual(self.report["corrected_v2_rows"],1044848)
        self.assertEqual(self.report["purchase_occasion_integrity"],{
            "occasion_fingerprint_sha256":"9ad56e57c7bc40a967ad23a8f0e9038ac09cef926b628a36adcd7296117797e8",
            "lineage_fingerprint_sha256":"b172093cd3701f22faaf2fc63b5db125c5ecc87b505061438c545c4e1dcad8de",
            "lineage_rows":788127})

    def test_acquisition_proxy_is_diagnostic_and_unpublished(self):
        diagnostic=self.report["acquisition_proxy_diagnostic"]
        self.assertEqual(diagnostic["merchandise_only_lookback_sensitivity_customers"],1613)
        self.assertEqual(diagnostic["fixed_cutoff_prior_identified_activity_customers"],11)
        self.assertEqual(diagnostic["fixed_cutoff_adjusted_diagnostic_customers"],1602)
        self.assertEqual(diagnostic["before_first_occasion_prior_identified_activity_customers"],12)
        self.assertEqual(diagnostic["before_first_occasion_adjusted_diagnostic_customers"],1601)
        self.assertFalse(diagnostic["primary_cohort_published"])

    def test_production_entry_rejects_arbitrary_and_reclassified_rows(self):
        arbitrary=self.validated._frame.copy(deep=True)
        with self.assertRaisesRegex(TypeError,"requires load_validated_purchase_input"):
            build_purchase_occasions(arbitrary)
        with self.assertRaisesRegex(TypeError,"requires load_validated_purchase_input"):
            build_real_data_report(arbitrary)
        with self.assertRaisesRegex(TypeError,"requires load_validated_purchase_input"):
            build_revenue_bridge(arbitrary)
        changed=arbitrary.copy(deep=True)
        changed.loc[changed.category=="shipping","category"]="merchandise"
        tampered=replace(self.validated,_frame=changed)
        with self.assertRaisesRegex(AssertionError,"frame changed after validation"):
            build_purchase_occasions(tampered)
        with self.assertRaisesRegex(AssertionError,"frame changed after validation"):
            build_real_data_report(tampered)
        with self.assertRaisesRegex(AssertionError,"frame changed after validation"):
            build_revenue_bridge(tampered)

    def test_recomputed_forged_wrapper_cannot_bypass_actual_frame_pins(self):
        # Recompute every caller-controlled seal field to reproduce Claude's
        # deliberate private-name forgery. The consumed rows still have to
        # match the external Stage A pins.
        changed=self.validated._frame.copy(deep=True)
        changed.loc[changed.category=="fee","category"]="discount"
        candidates=changed.index[(changed.category=="merchandise") & changed.CustomerID.isna()][:100]
        changed.loc[candidates,"category"]="shipping"
        digest=purchase_module._frame_content_digest(changed)
        forged=replace(self.validated,_frame=changed,_content_digest=digest,
            _integrity_report=dict(self.validated._integrity_report),_token=purchase_module._VALIDATION_TOKEN)
        with self.assertRaisesRegex(AssertionError,"actual classified frame row fingerprint mismatch"):
            build_revenue_bridge(forged)

    def test_frozen_leaf_refs_reject_category_swaps_and_membership_changes(self):
        leaves={name:dict(item) for name,item in self.bridge["bridge_leaves"].items()}
        # A value-preserving transfer between leaves keeps the grand total.
        old_fee=Decimal(leaves["fees"]["signed_amount"])
        old_discount=Decimal(leaves["discounts"]["signed_amount"])
        leaves["fees"]["signed_amount"]=str(old_fee+Decimal("1.00"))
        leaves["discounts"]["signed_amount"]=str(old_discount-Decimal("1.00"))
        self.assertEqual(Decimal(leaves["fees"]["signed_amount"])+Decimal(leaves["discounts"]["signed_amount"]),old_fee+old_discount)
        with self.assertRaisesRegex(AssertionError,"bridge category reference mismatch for discounts.signed_amount"):
            bridge_module._validate_bridge_against_frozen_references(leaves,self.bridge["source_reconciliation"])

        leaves={name:dict(item) for name,item in self.bridge["bridge_leaves"].items()}
        leaves["fees"]["source_row_membership_sha256"]="0"*64
        with self.assertRaisesRegex(AssertionError,"source_row_membership_sha256"):
            bridge_module._validate_bridge_against_frozen_references(leaves,self.bridge["source_reconciliation"])

    def test_frozen_leaf_refs_reject_unattributed_merchandise_to_shipping(self):
        leaves={name:dict(item) for name,item in self.bridge["bridge_leaves"].items()}
        moved=Decimal("100.00")
        merch=leaves["other_positive_merchandise_activity"]
        ship=leaves["shipping_delivery_income"]
        merch["rows"]-=1;merch["positive_rows"]-=1;merch["positive_amount"]=str(Decimal(merch["positive_amount"])-moved)
        merch["signed_amount"]=str(Decimal(merch["signed_amount"])-moved);merch["unattributed_amount"]=str(Decimal(merch["unattributed_amount"])-moved)
        ship["rows"]+=1;ship["positive_rows"]+=1;ship["positive_amount"]=str(Decimal(ship["positive_amount"])+moved)
        ship["signed_amount"]=str(Decimal(ship["signed_amount"])+moved);ship["unattributed_amount"]=str(Decimal(ship["unattributed_amount"])+moved)
        with self.assertRaisesRegex(AssertionError,"bridge category reference mismatch for other_positive_merchandise_activity"):
            bridge_module._validate_bridge_against_frozen_references(leaves,self.bridge["source_reconciliation"])

    def test_revenue_bridge_exact_decimal_reconciliation(self):
        bridge=self.bridge
        rec=bridge["source_reconciliation"]
        self.assertTrue(rec["rows_reconcile"])
        self.assertTrue(rec["all_source_row_ids_unique"])
        self.assertEqual(rec["leaf_rows"],1044848)
        self.assertEqual(Decimal(rec["signed_total"]),Decimal("18909762.118"))
        self.assertEqual(Decimal(rec["identifiable_signed"]),Decimal("16343669.038"))
        self.assertEqual(Decimal(rec["unattributed_signed"]),Decimal("2566093.08"))
        self.assertEqual(Decimal(rec["leaf_signed_amount"]),Decimal("18909762.118"))
        merch=bridge["merchandise_positive_reconciliation"]
        self.assertEqual(Decimal(merch["all_positive_merchandise"]),Decimal("19699671.127"))
        self.assertEqual(Decimal(merch["qualifying_gross_purchases"]),Decimal("17123740.997"))
        self.assertEqual(Decimal(merch["other_positive_nonqualifying_merchandise"]),Decimal("2575930.13"))
        self.assertEqual(Decimal(merch["difference"]),Decimal("2575930.130"))
        leaves=bridge["bridge_leaves"]
        self.assertEqual((leaves["qualifying_gross_merchandise_purchases"]["rows"],leaves["other_positive_merchandise_activity"]["rows"]),(788127,226881))
        self.assertEqual(Decimal(leaves["merchandise_returns_cancellations"]["signed_amount"]),Decimal("-719677.94"))
        self.assertEqual(Decimal(leaves["shipping_delivery_income"]["signed_amount"]),Decimal("434595.51"))
        self.assertEqual(Decimal(leaves["standalone_manual_billing"]["signed_amount"]),Decimal("334379.51"))
        self.assertEqual(Decimal(leaves["standalone_manual_credits"]["signed_amount"]),Decimal("-421770.38"))
        self.assertEqual(Decimal(leaves["embedded_manual_adjustments"]["signed_amount"]),Decimal("4455.30"))
        self.assertEqual(leaves["zero_value_entries"]["rows"],6024)

    def test_occasion_reference_fails_on_lineage_mutation(self):
        import COMMERCIAL_DS_003_PURCHASE_OCCASIONS as occasions_module
        _validate_occasions_against_frozen_reference=occasions_module._validate_occasions_against_frozen_reference
        altered=[dict(x) for x in self.report["occasions"]]
        altered[0]=dict(altered[0]);altered[0]["source_row_numbers"]=list(altered[0]["source_row_numbers"])
        altered[0]["source_row_numbers"][-1]+=10000000
        with self.assertRaisesRegex(AssertionError,"occasion fingerprint"):
            _validate_occasions_against_frozen_reference(altered,self.report["purchase_occasion_summary"],self.validated._integrity_report)
        with tempfile.TemporaryDirectory() as temp_dir:
            altered_pin=Path(temp_dir)/"pins.json"
            pins=json.loads(occasions_module.OCCASION_REFERENCE_FILE.read_text())
            pins["summary"]["occasion_count"]+=1
            altered_pin.write_text(json.dumps(pins))
            with patch.object(occasions_module,"OCCASION_REFERENCE_FILE",altered_pin):
                with self.assertRaisesRegex(AssertionError,"pin file SHA-256 mismatch"):
                    _validate_occasions_against_frozen_reference(self.report["occasions"],self.report["purchase_occasion_summary"],self.validated._integrity_report)


if __name__=="__main__": unittest.main()
