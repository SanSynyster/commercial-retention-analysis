import unittest
from collections import defaultdict
from datetime import date, datetime, timedelta

import pandas as pd

import COMMERCIAL_DS_003_STAGE_B2B2 as producer
from COMMERCIAL_DS_003_PURCHASE_OCCASIONS import build_purchase_occasions, load_validated_purchase_input


def occasion(customer, day, invoice, row_number):
    return {"customer_id":str(customer), "transaction_date":day.isoformat(),
            "invoice_id":invoice, "source_row_numbers":[row_number]}


class B2B2OutcomeUnitTests(unittest.TestCase):
    def test_date_and_invoice_90_day_boundaries(self):
        anchor=date(2011,1,1)
        same_day=producer.calculate_customer_outcome([
            occasion(1,anchor,"000001",1), occasion(1,anchor,"000002",2)],
            data_end_date=date(2012,1,1))
        self.assertFalse(same_day["date_level_repeat"])
        self.assertTrue(same_day["invoice_level_repeat"])

        day_89=anchor+timedelta(days=89)
        before_edge=producer.calculate_customer_outcome([
            occasion(1,anchor,"000001",1), occasion(1,day_89,"000002",2)],
            data_end_date=date(2012,1,1))
        self.assertTrue(before_edge["date_level_repeat"])
        self.assertTrue(before_edge["invoice_level_repeat"])

        day_90=anchor+timedelta(days=90)
        on_edge=producer.calculate_customer_outcome([
            occasion(1,anchor,"000001",1), occasion(1,day_90,"000002",2)],
            data_end_date=date(2012,1,1))
        self.assertFalse(on_edge["date_level_repeat"])
        self.assertFalse(on_edge["invoice_level_repeat"])

        next_day=producer.calculate_customer_outcome([
            occasion(1,anchor,"000001",1), occasion(1,anchor+timedelta(days=1),"000002",2)],
            data_end_date=date(2012,1,1))
        self.assertTrue(next_day["date_level_repeat"])
        self.assertTrue(next_day["invoice_level_repeat"])

        day_10=producer.calculate_customer_outcome([
            occasion(1,anchor,"000001",1), occasion(1,anchor+timedelta(days=10),"000002",2)],
            data_end_date=date(2012,1,1))
        self.assertTrue(day_10["date_level_repeat"])
        self.assertTrue(day_10["invoice_level_repeat"])

    def test_outcomes_are_input_order_invariant(self):
        rows=[occasion(1,date(2011,1,1),"000002",2),
              occasion(1,date(2011,1,1),"000001",1),
              occasion(1,date(2011,1,2),"000003",3)]
        expected=producer.calculate_customer_outcome(rows,data_end_date=date(2012,1,1))
        self.assertEqual(producer.calculate_customer_outcome(list(reversed(rows)),data_end_date=date(2012,1,1)),expected)

    def test_maturity_boundary_and_immature_nulls(self):
        sep10=producer.calculate_customer_outcome([
            occasion(1,date(2011,9,10),"000001",1)], data_end_date=date(2011,12,9))
        sep11=producer.calculate_customer_outcome([
            occasion(1,date(2011,9,11),"000001",1)], data_end_date=date(2011,12,9))
        self.assertTrue(sep10["mature"])
        self.assertFalse(sep11["mature"])
        self.assertIsNone(sep11["date_level_repeat"])
        self.assertIsNone(sep11["invoice_level_repeat"])

    def test_cutoff_partition_and_nested_proxy_memberships(self):
        first_dates={"1":date(2010,11,30), "2":date(2010,12,1),
                     "3":date(2011,1,1), "4":date(2011,1,2)}
        records={cid:{"first_observed_date":day} for cid,day in first_dates.items()}
        activity=pd.DataFrame({"CustomerID":[1.,2.,3.,4.],
            "InvoiceDate":pd.to_datetime(["2010-10-01","2010-11-30","2010-12-15","2011-01-02"])})
        sets=producer.derive_population_memberships(records,activity)
        self.assertEqual(sets["left_censored"],{"1"})
        self.assertEqual(sets["proxy_1"],{"2","3","4"})
        self.assertEqual(sets["proxy_2"],{"4","3"})
        self.assertEqual(sets["proxy_3"],{"4"})
        self.assertFalse(sets["left_censored"] & sets["proxy_1"])
        self.assertEqual(sets["left_censored"] | sets["proxy_1"],set(first_dates))


class B2B2RealSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validated=load_validated_purchase_input()
        cls.occasions,_=build_purchase_occasions(cls.validated)
        cls.analysis=producer._assemble_analysis(cls.validated,cls.occasions)

    def test_real_source_population_maturity_and_reviewed_monthly_counts(self):
        populations=self.analysis["populations"]
        self.assertEqual({k:v["customer_count"] for k,v in populations.items()},
            {"all_observed":5852,"left_censored":4239,"proxy_1":1613,"proxy_2":1602,"proxy_3":1601})
        self.assertEqual(populations["left_censored"]["customer_count"]+
                         populations["proxy_1"]["customer_count"],5852)
        for month,expected in {"2011-10":(221,221,220), "2011-11":(191,191,191),
                               "2011-12":(28,28,28)}.items():
            got=tuple(self._cell(f"proxy_{idx}","month",month)["eligible_customers"] for idx in (1,2,3))
            self.assertEqual(got,expected)
            for idx in (1,2,3):
                cell=self._cell(f"proxy_{idx}","month",month)
                self.assertEqual(cell["mature_customers"],0)
                self.assertIsNone(cell["date_level_repeat_numerator"])
                self.assertIsNone(cell["invoice_level_repeat_numerator"])
                self.assertIsNone(cell["observed_repeat_share"])

        self.assertEqual(self._cell("proxy_1","month","2010-12")["eligible_customers"],76)
        self.assertEqual(self._cell("proxy_1","month","2010-12")["date_level_repeat_numerator"],12)
        self.assertEqual(self._cell("proxy_1","month","2010-12")["period_coverage"],"full")

    def test_coverage_flags_nulls_and_month_quarter_reconciliation(self):
        self.assertEqual(self._cell("left_censored","quarter","2009-Q4")["period_coverage"],"data_start_truncated")
        self.assertEqual(self._cell("left_censored","quarter","2010-Q4")["period_coverage"],"cutoff_split")
        self.assertEqual(self._cell("proxy_1","quarter","2010-Q4")["period_coverage"],"cutoff_split")
        self.assertEqual(self._cell("proxy_1","quarter","2011-Q3")["period_coverage"],"maturity_truncated")
        self.assertEqual(self._cell("proxy_1","month","2011-09")["period_coverage"],"maturity_truncated")
        self.assertEqual(self._cell("proxy_1","quarter","2011-Q4")["period_coverage"],"none_mature")
        self.assertEqual(self._cell("proxy_1","month","2011-09")["mature_customers"],32)
        self.assertEqual(self._cell("proxy_1","month","2011-09")["mature_anchor_date_min"],"2011-09-01")
        self.assertEqual(self._cell("proxy_1","month","2011-09")["mature_anchor_date_max"],"2011-09-09")
        self.assertIn("December 2011 source coverage ends on December 9",producer.render_summary(self.analysis))

        rows=self.analysis["records"]
        for population in producer.POPULATION_ORDER:
            for grain in ("month","quarter"):
                for level in producer.OUTCOME_LEVELS:
                    cells=[row for row in rows if row["population_id"]==population
                           and row["period_grain"]==grain and row["outcome_level"]==level]
                    self.assertEqual(sum(row["eligible_customers"] for row in cells),
                        self.analysis["populations"][population]["customer_count"])
                    for row in cells:
                        self.assertEqual(row["mature_customers"]+row["immature_customers"],row["eligible_customers"])
                        if population != "all_observed" and row["denominator_mature_eligible_customers"]:
                            self.assertLessEqual(row["date_level_repeat_numerator"],row["invoice_level_repeat_numerator"])

        for population in producer.POPULATION_ORDER:
            for quarter in producer._periods("quarter"):
                year=int(quarter[:4]); qnum=int(quarter[-1])
                months=[f"{year:04d}-{month:02d}" for month in range((qnum-1)*3+1,qnum*3+1)
                        if f"{year:04d}-{month:02d}" in producer._periods("month")]
                monthly=[self._cell(population,"month",month) for month in months]
                quarterly=self._cell(population,"quarter",quarter)
                for field in ("eligible_customers","mature_customers","immature_customers"):
                    self.assertEqual(sum(cell[field] for cell in monthly),quarterly[field],(population,quarter,field))
                for field in ("date_level_repeat_numerator","invoice_level_repeat_numerator"):
                    month_sum=sum(cell[field] or 0 for cell in monthly)
                    self.assertEqual(month_sum,quarterly[field] or 0,(population,quarter,field))

        for row in rows:
            self.assertNotEqual(row["first_observed_period"],"all")
            if row["population_id"]=="all_observed":
                for field in ("date_level_repeat_numerator","invoice_level_repeat_numerator",
                              "numerator_repeat_customers","denominator_mature_eligible_customers",
                              "observed_repeat_share","interval_low","interval_high"):
                    self.assertIsNone(row[field])
        self.assertEqual(len(rows),5*(25+9)*2)

    def test_cell_reconstruction_regression_from_frozen_occasions(self):
        # This is a downstream regression check from frozen occasion output,
        # not an independent raw-source scientific reconstruction.
        first={}
        by_customer=defaultdict(list)
        for item in self.occasions:
            cid=str(item["customer_id"])
            day=date.fromisoformat(item["transaction_date"])
            first[cid]=min(day,first.get(cid,day))
            by_customer[cid].append((day,item["invoice_id"]))
        members={"all_observed":set(first),
                 "left_censored":{cid for cid,day in first.items() if day < date(2010,12,1)}}
        members["proxy_1"]=members["all_observed"]-members["left_censored"]
        before_cutoff=set();before_first=set()
        for row in self.validated._frame.itertuples(index=False):
            if pd.isna(row.CustomerID):
                continue
            cid=str(int(row.CustomerID)); day=pd.Timestamp(row.InvoiceDate).date()
            if cid in first and day < date(2010,12,1): before_cutoff.add(cid)
            if cid in first and day < first[cid]: before_first.add(cid)
        members["proxy_2"]=members["proxy_1"]-before_cutoff
        members["proxy_3"]=members["proxy_1"]-before_first

        independent={}
        for cid,items in by_customer.items():
            ordered=sorted(items,key=lambda x:(x[0],x[1]))
            d1=ordered[0][0]
            mature=d1+timedelta(days=90) <= date(2011,12,9)
            date_repeat=None
            invoice_repeat=None
            if mature:
                date_repeat=any(d1 < day < d1+timedelta(days=90) for day,_ in ordered[1:])
                first_day,first_invoice=ordered[0]
                invoice_repeat=any((first_day,first_invoice)<(day,invoice)
                                   and first_day <= day < first_day+timedelta(days=90)
                                   for day,invoice in ordered[1:])
            independent[cid]=(d1,mature,date_repeat,invoice_repeat)

        for population in ("left_censored","proxy_1","proxy_2","proxy_3"):
            for grain, periods in (("month",producer._periods("month")),
                                   ("quarter",producer._periods("quarter"))):
                for period in periods:
                    selected=[cid for cid in members[population]
                              if (f"{independent[cid][0].year:04d}-{independent[cid][0].month:02d}" if grain=="month"
                                  else f"{independent[cid][0].year:04d}-Q{(independent[cid][0].month-1)//3+1}")==period]
                    mature=[cid for cid in selected if independent[cid][1]]
                    expected_date=sum(independent[cid][2] is True for cid in mature) if mature else None
                    expected_invoice=sum(independent[cid][3] is True for cid in mature) if mature else None
                    cell=self._cell(population,grain,period)
                    self.assertEqual(cell["eligible_customers"],len(selected))
                    self.assertEqual(cell["mature_customers"],len(mature))
                    self.assertEqual(cell["date_level_repeat_numerator"],expected_date)
                    self.assertEqual(cell["invoice_level_repeat_numerator"],expected_invoice)

    def test_serialization_is_deterministic_and_has_no_customer_rows(self):
        first=producer.serialize_output(self.analysis)
        second=producer.serialize_output(self.analysis)
        self.assertEqual(first,second)
        self.assertNotIn(b'"customer_id"',first)
        self.assertEqual(producer.CONTRACT_VERSION,self.analysis["contract_version"])

    def test_zero_mature_denominator_numerator_is_null_and_mature_zero_is_zero(self):
        immature={"first_observed_date":date(2011,10,5),"first_observed_month":"2011-10",
                  "first_observed_quarter":"2011-Q4","mature":False,
                  "date_level_repeat":None,"invoice_level_repeat":None}
        empty=producer._cell_row("proxy_1",set(),{},"month","2011-10","date_level_primary")
        no_maturity=producer._cell_row("proxy_1",{"i"},{"i":immature},"month","2011-10","date_level_primary")
        self.assertIsNone(empty["numerator_repeat_customers"])
        self.assertIsNone(no_maturity["numerator_repeat_customers"])
        mature={**immature,"first_observed_date":date(2011,1,1),"first_observed_month":"2011-01",
                "first_observed_quarter":"2011-Q1","mature":True,
                "date_level_repeat":False,"invoice_level_repeat":False}
        mature_zero=producer._cell_row("proxy_1",{"m"},{"m":mature},"month","2011-01","date_level_primary")
        self.assertEqual(mature_zero["denominator_mature_eligible_customers"],1)
        self.assertEqual(mature_zero["numerator_repeat_customers"],0)
        affected=[r for r in self.analysis["records"] if not r["population_reconciliation_only"]
                  and r["denominator_mature_eligible_customers"]==0]
        self.assertEqual(len(affected),154)
        self.assertTrue(all(r["numerator_repeat_customers"] is None for r in affected))

    def _cell(self,population,grain,period):
        return next(row for row in self.analysis["records"] if row["population_id"]==population
                    and row["period_grain"]==grain and row["first_observed_period"]==period
                    and row["outcome_level"]=="date_level_primary")


if __name__ == "__main__":
    unittest.main()
