"""Synthetic-only contract and regression tests for the B2B-3 feasibility gate."""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import calendar
import hashlib
import io
import json
import os
import shutil
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from contextlib import redirect_stderr

import pandas as pd

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import COMMERCIAL_DS_003_STAGE_B2B3 as gate


def synthetic_inputs():
    # Independently specified fixture: 50 proxy-1 customers; 11 have earlier
    # pre-cutoff activity and one has post-cutoff, pre-first-qualifying activity.
    occasions=[]; classified=[]; seq=1
    def activity(cid, day):
        nonlocal seq
        classified.append({"CustomerID":cid,"InvoiceDate":pd.Timestamp(day)})
        seq+=1
    for cid in range(1,51):
        day=date(2011,1,1)
        if cid<=11: activity(cid,date(2010,11,30))
        if cid==12: activity(cid,date(2010,12,15))
        activity(cid,day)
        occasions.append({"customer_id":str(cid),"invoice_id":f"{1000+cid}","transaction_date":day.isoformat()})
    activity(59,date(2010,11,30))
    occasions.append({"customer_id":"59","invoice_id":"2059","transaction_date":"2010-11-30"})
    # One customer has another purchase date in January and a February anchor;
    # primary eligibility remains one row per month, from the earliest date.
    for cid,day,inv in ((1,date(2011,1,20),"2001"),(1,date(2011,2,1),"2002")):
        activity(cid,day); occasions.append({"customer_id":"1","invoice_id":inv,"transaction_date":day.isoformat()})
    # Exact maturity boundary pairs: H-day anchor matures, H+1 does not.
    for cid,day,inv in ((60,date(2011,9,10),"2060"),(61,date(2011,9,11),"2061"),
                        (62,date(2011,10,10),"2062"),(63,date(2011,10,11),"2063"),
                        (64,date(2011,11,9),"2064"),(65,date(2011,11,10),"2065")):
        activity(cid,day); occasions.append({"customer_id":str(cid),"invoice_id":inv,"transaction_date":day.isoformat()})
    return occasions,pd.DataFrame(classified)


def structural_reference_inputs():
    """Synthetic fixture matching the accepted B2B-2 structural totals only."""
    occasions=[]; classified=[]; invoice=3000000
    def add_customer(cid, day, earlier=()):
        nonlocal invoice
        for prior in earlier: classified.append({"CustomerID":cid,"InvoiceDate":pd.Timestamp(prior)})
        classified.append({"CustomerID":cid,"InvoiceDate":pd.Timestamp(day)})
        occasions.append({"customer_id":str(cid),"invoice_id":str(invoice),"transaction_date":day.isoformat()})
        invoice+=1
    for cid in range(1,4240): add_customer(cid,date(2010,1,1))
    for offset in range(1,1614):
        cid=10000+offset
        day=date(2011,1,1) if offset<=1017 else date(2011,11,1)
        prior=()
        if offset<=9 or offset in (1018,1019): prior=(date(2010,11,30),)
        elif offset==1020: prior=(date(2010,12,15),)
        add_customer(cid,day,prior)
    return occasions,pd.DataFrame(classified)


def independent_reference_sections(occasions, frame, metadata):
    """Small test-only reconstruction; deliberately does not call gate aggregators."""
    start=date(2009,12,1); end=date(2011,12,9); cutoff=date(2010,12,1); horizons=(30,60,90)
    def month_id(d): return f"{d.year:04d}-{d.month:02d}"
    def quarter_id(d): return f"{d.year:04d}-Q{(d.month-1)//3+1}"
    months=[]; y,m=2009,12
    while (y,m)<=(2011,12):
        s=date(y,m,1); last=calendar.monthrange(y,m)[1]; e=date(y,m,last)
        months.append((month_id(s),s,e)); y,m=(y+(m==12),1 if m==12 else m+1)
    quarters=[]
    for year in range(2009,2012):
        for q in range(1,5):
            s=date(year,(q-1)*3+1,1); e=date(year,q*3,calendar.monthrange(year,q*3)[1])
            if e>=start and s<=end: quarters.append((f"{year:04d}-Q{q}",s,e))
    periods=[("month",pid,s,e) for pid,s,e in months]+[("quarter",pid,s,e) for pid,s,e in quarters]
    calendar_rows=[]
    for unit,pid,s,e in periods:
        st=s<start; en=e>end; partial=s<=end<=e; split=s<cutoff<=e
        coverage="source_partial" if st or en else ("calendar_complete_population_cutoff_split_possible" if split else "source_complete")
        calendar_rows.append({"calendar_unit":unit,"period_id":pid,"period_start":s.isoformat(),"period_end":e.isoformat(),"source_start_truncated":st,"source_end_truncated":en,"final_source_day_partial":partial,"population_cutoff_split_possible":split,"coverage_status":coverage})
    first={}; by_customer_month={}
    for row in occasions:
        cid=row["customer_id"]; day=date.fromisoformat(row["transaction_date"])
        first[cid]=min(first.get(cid,day),day)
        key=(cid,month_id(day)); by_customer_month[key]=min(by_customer_month.get(key,day),day)
    before_cutoff=set(); before_first=set()
    for row in frame.itertuples(index=False):
        if pd.isna(row.CustomerID): continue
        cid=str(int(row.CustomerID)); day=pd.Timestamp(row.InvoiceDate).date()
        if day<cutoff: before_cutoff.add(cid)
        if cid in first and day<first[cid]: before_first.add(cid)
    all_ids=set(first); left={cid for cid,day in first.items() if day<cutoff}; p1=all_ids-left
    populations={"left_censored":left,"proxy_1":p1,"proxy_2":p1-before_cutoff,"proxy_3":p1-before_first}
    monthly={}; primary=[]
    for population in ("left_censored","proxy_1"):
        for mid,ms,me in months:
            ids={cid for cid in populations[population] if (cid,mid) in by_customer_month}
            mature={h:sum(by_customer_month[(cid,mid)]+timedelta(days=h)<=end for cid in ids) for h in horizons}
            cal=next(c for c in calendar_rows if c["calendar_unit"]=="month" and c["period_id"]==mid)
            for h in horizons:
                a=max(ms,start); b=min(me,end-timedelta(days=h))
                if a>b: fs=fe=None; crossed=[]; fstatus="no_calendar_eligible_anchor"
                else:
                    fs=a+timedelta(days=1); fe=b+timedelta(days=h-1)
                    crossed=[]; cursor=date(fs.year,fs.month,1); last=date(fe.year,fe.month,1)
                    while cursor<=last:
                        crossed.append(month_id(cursor)); cursor=date(cursor.year+(cursor.month==12),1 if cursor.month==12 else cursor.month+1,1)
                    fs=fs.isoformat(); fe=fe.isoformat(); fstatus="calendar_span_defined"
                n=len(ids); row={"population":population,"month":mid,"horizon_days":h,"eligible_customer_month_count":n,"h_mature_customer_month_count":int(mature[h]),"h_immature_customer_month_count":n-int(mature[h]),"common_90_mature_customer_month_count":int(mature[90]),"coverage_status":cal["coverage_status"],"possible_followup_start":fs,"possible_followup_end":fe,"followup_months_crossed":crossed,"followup_coverage_status":fstatus}
                primary.append(row); monthly[(population,mid,h,"eligible")]=n; monthly[(population,mid,h,"h_mature")]=int(mature[h]); monthly[(population,mid,h,"common_90_mature")]=int(mature[90])
    def threshold(xs): return True if max(xs)>=30 else (False if sum(xs)<30 else "not_determined_at_gate")
    quarter_rows=[]
    for pop in ("left_censored","proxy_1"):
        for q,_,_ in quarters:
            mids=[mid for mid,_,_ in months if quarter_id(date.fromisoformat(mid+"-01"))==q]
            for basis in ("eligible","h_mature","common_90_mature"):
                for h in ((None,) if basis=="eligible" else horizons):
                    xs=[monthly[(pop,mid,90 if h is None else h,basis)] for mid in mids]
                    quarter_rows.append({"population":pop,"quarter":q,"horizon_days":h,"count_basis":basis,"threshold":30,"value":threshold(xs)})
    proxy_rows=[]
    for proxy,diff in (("proxy_2",11),("proxy_3",12)):
        for mid,_,_ in months:
            for basis in ("eligible","h_mature","common_90_mature"):
                for h in ((None,) if basis=="eligible" else horizons):
                    n=monthly[("proxy_1",mid,90 if h is None else h,basis)]
                    value=True if n>=30+diff else (False if n<30 else "not_determined_at_gate")
                    proxy_rows.append({"proxy_population":proxy,"calendar_unit":"month","period_id":mid,"horizon_days":h,"count_basis":basis,"threshold":30,"value":value})
        for q,_,_ in quarters:
            mids=[mid for mid,_,_ in months if quarter_id(date.fromisoformat(mid+"-01"))==q]
            for basis in ("eligible","h_mature","common_90_mature"):
                for h in ((None,) if basis=="eligible" else horizons):
                    xs=[monthly[("proxy_1",mid,90 if h is None else h,basis)] for mid in mids]
                    lower=max(max(0,n-diff) for n in xs); upper=sum(xs)
                    value=True if lower>=30 else (False if upper<30 else "not_determined_at_gate")
                    proxy_rows.append({"proxy_population":proxy,"calendar_unit":"quarter","period_id":q,"horizon_days":h,"count_basis":basis,"threshold":30,"value":value})
    return {"metadata":dict(metadata),"calendar_coverage":calendar_rows,"primary_monthly_counts":primary,"quarter_thresholds":quarter_rows,"proxy_feasibility_flags":proxy_rows}


class B2B3SyntheticContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.occasions,cls.frame=synthetic_inputs()
        cls.payload=gate.build_gate_payload(cls.occasions,cls.frame)

    def row(self,pop,month,h):
        return next(r for r in self.payload["primary_monthly_counts"] if (r["population"],r["month"],r["horizon_days"])==(pop,month,h))

    def test_frozen_top_level_and_allowlists(self):
        self.assertEqual(set(self.payload),gate.TOP_KEYS)
        self.assertTrue(all(set(x)==gate.PRIMARY_KEYS for x in self.payload["primary_monthly_counts"]))
        self.assertTrue(all(set(x)==gate.CAL_KEYS for x in self.payload["calendar_coverage"]))
        self.assertFalse(self.payload["metadata"]["outcomes_computed"])
        self.assertFalse(next(x for x in self.payload["integrity"] if x["check_id"]=="b2b2_structural_regression")["passed"])
        with self.assertRaises(ValueError): gate.serialize_payload(self.payload)

    def test_primary_customer_month_anchor_and_repeat_months(self):
        jan=self.row("proxy_1","2011-01",90)
        feb=self.row("proxy_1","2011-02",90)
        # 50 distinct customers in Jan despite two January occasions for customer 1.
        self.assertEqual(jan["eligible_customer_month_count"],50)
        self.assertEqual(feb["eligible_customer_month_count"],1)
        self.assertEqual(jan["h_mature_customer_month_count"],50)

    def test_population_separation_and_nested_proxy_flags(self):
        self.assertEqual(self.row("left_censored","2010-11",90)["eligible_customer_month_count"],1)
        p2=next(x for x in self.payload["proxy_feasibility_flags"] if (x["proxy_population"],x["period_id"],x["count_basis"])==("proxy_2","2011-01","eligible"))
        p3=next(x for x in self.payload["proxy_feasibility_flags"] if (x["proxy_population"],x["period_id"],x["count_basis"])==("proxy_3","2011-01","eligible"))
        self.assertIs(p2["value"],True)  # 50 >= 30+11
        self.assertIs(p3["value"],True)  # 50 >= 30+12

    def test_exact_horizon_maturity_boundaries(self):
        # At H days from anchor to source end is mature; H+1 is immature.
        self.assertEqual((self.row("proxy_1","2011-09",90)["h_mature_customer_month_count"],
                          self.row("proxy_1","2011-09",90)["h_immature_customer_month_count"]),(1,1))
        self.assertEqual((self.row("proxy_1","2011-10",60)["h_mature_customer_month_count"],
                          self.row("proxy_1","2011-10",60)["h_immature_customer_month_count"]),(1,1))
        self.assertEqual((self.row("proxy_1","2011-11",30)["h_mature_customer_month_count"],
                          self.row("proxy_1","2011-11",30)["h_immature_customer_month_count"]),(1,1))
        for h in gate.HORIZONS:
            self.assertEqual(self.row("proxy_1","2011-09",h)["common_90_mature_customer_month_count"],1)

    def test_empty_and_partial_periods_are_explicit(self):
        self.assertEqual(self.row("proxy_1","2011-12",90)["eligible_customer_month_count"],0)
        self.assertEqual(self.row("proxy_1","2011-12",90)["followup_coverage_status"],"no_calendar_eligible_anchor")
        self.assertEqual(self.row("proxy_1","2011-09",90)["possible_followup_start"],"2011-09-02")
        self.assertEqual(self.row("proxy_1","2011-09",90)["possible_followup_end"],"2011-12-08")
        q4=next(x for x in self.payload["calendar_coverage"] if x["period_id"]=="2011-Q4")
        self.assertTrue(q4["source_end_truncated"] and q4["final_source_day_partial"])

    def test_empty_synthetic_population_has_zero_structural_counts(self):
        empty=gate.build_gate_payload([],pd.DataFrame(columns=["CustomerID","InvoiceDate"]))
        self.assertTrue(all(r["eligible_customer_month_count"]==0 for r in empty["primary_monthly_counts"]))
        self.assertTrue(all(r["h_mature_customer_month_count"]==0 for r in empty["primary_monthly_counts"]))

    def test_quarter_bounds_threshold_and_reconciliation(self):
        # Exact monthly vector [30,41],[0,29],[0,29] implies threshold true.
        self.assertIs(gate._threshold_from_exact_months([30,0,0]),True)
        self.assertIs(gate._threshold_from_exact_months([29,0,0]),False)
        self.assertEqual(gate._threshold_from_exact_months([29,1,0]),"not_determined_at_gate")
        rec=next(x for x in self.payload["quarter_thresholds"] if (x["population"],x["quarter"],x["horizon_days"],x["count_basis"])==("proxy_1","2011-Q1",None,"eligible"))
        self.assertIs(rec["value"],True)
        jan=self.row("proxy_1","2011-01",90)["eligible_customer_month_count"]
        feb=self.row("proxy_1","2011-02",90)["eligible_customer_month_count"]
        mar=self.row("proxy_1","2011-03",90)["eligible_customer_month_count"]
        self.assertEqual(jan+feb+mar,51)  # customer-month records, not quarter-unique customers.

    def test_deterministic_input_order_invariance(self):
        reversed_payload=gate.build_gate_payload(list(reversed(self.occasions)),self.frame.iloc[::-1].reset_index(drop=True))
        self.assertEqual(self.payload,reversed_payload)

    def test_same_day_invoices_and_next_day_are_occasions_not_outcomes(self):
        rows=[]
        for i,(invoice,stamp) in enumerate((("9001","2011-01-01 09:00:00"),("9002","2011-01-01 15:00:00"),("9003","2011-01-02 10:00:00")),1):
            rows.append({"source_row_number":i,"category":"merchandise","CustomerID":900,"InvoiceNo":invoice,"InvoiceDate":pd.Timestamp(stamp),"Quantity":1,"UnitPrice":2.0})
        frame=pd.DataFrame(rows)
        occasions,_=gate._build_purchase_occasions_for_test(frame)
        self.assertEqual(len(occasions),3)  # invoice occasions; this test computes no repeat label.
        payload=gate.build_gate_payload(occasions,frame)
        # Three occasions for one customer still produce one customer-month record.
        self.assertEqual(next(r for r in payload["primary_monthly_counts"] if r["population"]=="proxy_1" and r["month"]=="2011-01" and r["horizon_days"]==90)["eligible_customer_month_count"],1)

    def test_duplicate_invoice_input_fails_closed(self):
        rows=deepcopy(self.occasions)
        rows.append(dict(rows[0]))
        with self.assertRaises(ValueError): gate.build_gate_payload(rows,self.frame)

    def test_schema_drift_and_customer_fields_rejected(self):
        bad=deepcopy(self.payload); bad["primary_monthly_counts"][0]["repeat_numerator"]=0
        with self.assertRaises(ValueError): gate._validate_payload(bad)
        bad=deepcopy(self.payload); bad["primary_monthly_counts"][0]["customer_id"]="123"
        with self.assertRaises(ValueError): gate._validate_payload(bad)

    def test_calendar_spans_use_calendar_not_purchase_dates(self):
        a=gate._followup_span("2011-09",90)
        self.assertEqual(a,("2011-09-02","2011-12-08",["2011-09","2011-10","2011-11","2011-12"],"calendar_span_defined"))
        self.assertEqual(gate._followup_span("2011-12",90),(None,None,[],"no_calendar_eligible_anchor"))


class B2B3IntegrityWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.structural_occasions,cls.structural_frame=structural_reference_inputs()
        cls.candidate=gate.build_gate_payload(cls.structural_occasions,cls.structural_frame,enforce_b2b2_regression=True)
        cls.reference=independent_reference_sections(cls.structural_occasions,cls.structural_frame,cls.candidate["metadata"])

    def create_run(self, name, *, small=False):
        run_id="t_"+hashlib.sha256(name.encode()).hexdigest()[:12]
        if small:
            payload=gate.build_gate_payload(*synthetic_inputs())
        else: payload=self.candidate
        candidate_path=gate.write_candidate(payload,run_id,"synthetic-operator",synthetic=True)
        self.addCleanup(lambda: shutil.rmtree(candidate_path.parent,ignore_errors=True))
        candidate_bytes=candidate_path.read_bytes(); candidate_hash=hashlib.sha256(candidate_bytes).hexdigest()
        log_bytes=(candidate_path.parent/"operation.log").read_bytes()
        reconstruction={"evidence_schema":"B2B3_RECONSTRUCTION_EVIDENCE_V1","candidate_sha256":candidate_hash,"operator_id":"synthetic-operator","reviewer_id":"independent-synthetic-reviewer","reviewer_code_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),"reviewed_at_utc":"2026-11-08T12:00:00Z","reconstructed_sections":deepcopy(self.reference),"b2b2_structural_reference":{"population_sizes":{"left_censored":4239,"proxy_1":1613,"proxy_2":1602,"proxy_3":1601},"h90_mature_first_observed_customers":{"left_censored":4239,"proxy_1":1017,"proxy_2":1008,"proxy_3":1008}}}
        privacy={"evidence_schema":"B2B3_PRIVACY_REVIEW_V1","candidate_sha256":candidate_hash,"operator_id":"synthetic-operator","reviewer_id":"synthetic-privacy-reviewer","reviewed_at_utc":"2026-11-08T12:00:00Z","generated_logs_sha256":hashlib.sha256(log_bytes).hexdigest(),"aggregate_only_confirmed":True,"generated_logs_reviewed":True,"agent_transcripts_reviewed":True,"no_customer_level_exposure_found":True}
        root=gate.PRIVATE_SYNTHETIC_ROOT
        if not small:
            gate._atomic_private_write(candidate_path.parent/"reconstruction.json",gate._canonical_json(reconstruction),root)
            gate._atomic_private_write(candidate_path.parent/"privacy_review.json",gate._canonical_json(privacy),root)
        return candidate_path,reconstruction,privacy,candidate_bytes

    def test_b2b2_population_and_mature_regressions(self):
        self.assertTrue(next(x for x in self.candidate["integrity"] if x["check_id"]=="b2b2_structural_regression")["passed"])
        first={}
        for row in self.structural_occasions:
            cid=row["customer_id"]; day=date.fromisoformat(row["transaction_date"])
            first[cid]=min(first.get(cid,day),day)
        activities={}
        for row in self.structural_frame.itertuples(index=False):
            if pd.isna(row.CustomerID): continue
            activities.setdefault(str(int(row.CustomerID)),[]).append(pd.Timestamp(row.InvoiceDate).date())
        counts={p:0 for p in ("left_censored","proxy_1","proxy_2","proxy_3")}
        mature={p:0 for p in counts}
        for cid,day in first.items():
            pop="left_censored" if day<date(2010,12,1) else "proxy_1"
            if pop=="proxy_1":
                activity=activities[cid]
                p2=not any(d<date(2010,12,1) for d in activity)
                p3=not any(d<day for d in activity)
                counts["proxy_2"]+=p2; counts["proxy_3"]+=p3
                mature["proxy_2"]+=p2 and day+timedelta(days=90)<=date(2011,12,9)
                mature["proxy_3"]+=p3 and day+timedelta(days=90)<=date(2011,12,9)
            counts[pop]+=1
            if day+timedelta(days=90)<=date(2011,12,9): mature[pop]+=1
        self.assertEqual(counts,{"left_censored":4239,"proxy_1":1613,"proxy_2":1602,"proxy_3":1601})
        self.assertEqual(mature,{"left_censored":4239,"proxy_1":1017,"proxy_2":1008,"proxy_3":1008})

    def test_candidate_is_private_and_keeps_human_checks_pending(self):
        path,_,_,raw=self.create_run("candidate",small=True)
        candidate=gate.load_candidate(path)
        flags={x["check_id"]:x["passed"] for x in candidate["integrity"]}
        self.assertTrue(flags["c8_boundary_audit"])
        self.assertFalse(flags["independent_reconstruction"])
        self.assertFalse(flags["privacy_transcript_audit"])
        with self.assertRaises(ValueError): gate._validate_payload(candidate,require_pass=True)
        forged=deepcopy(candidate)
        next(row for row in forged["integrity"] if row["check_id"]=="independent_reconstruction")["passed"]=True
        with self.assertRaises(ValueError): gate._validate_payload(forged,require_pass=False,candidate=True)
        self.assertEqual(path.stat().st_mode & 0o777,0o600)
        self.assertEqual(path.parent.stat().st_mode & 0o777,0o700)
        with self.assertRaises(ValueError): gate.serialize_payload({**candidate,"integrity":[{"check_id":k,"passed":True} for k in gate.INTEGRITY_IDS]})
        with self.assertRaises(ValueError): gate.finalize_candidate(path,path.parent/"reconstruction.json",path.parent/"privacy_review.json")
        self.assertFalse((path.parent/"final.json").exists())

    def test_independent_reconstruction_mismatch_blocks_finalization(self):
        path,recon,privacy,_=self.create_run("mismatch")
        recon["reconstructed_sections"]["primary_monthly_counts"][0]["eligible_customer_month_count"]+=1
        gate._atomic_private_write(path.parent/"reconstruction.json",gate._canonical_json(recon),gate.PRIVATE_SYNTHETIC_ROOT,overwrite=True)
        with self.assertRaisesRegex(ValueError,"independent reconstruction mismatch"):
            gate.finalize_candidate(path,path.parent/"reconstruction.json",path.parent/"privacy_review.json")
        self.assertFalse((path.parent/"final.json").exists())

    def test_reconstruction_cannot_be_self_certified_or_reused_by_operator(self):
        path,recon,privacy,_=self.create_run("selfcert")
        recon["reviewer_id"]="synthetic-operator"
        gate._atomic_private_write(path.parent/"reconstruction.json",gate._canonical_json(recon),gate.PRIVATE_SYNTHETIC_ROOT,overwrite=True)
        with self.assertRaisesRegex(ValueError,"reviewer identity"):
            gate.finalize_candidate(path,path.parent/"reconstruction.json",path.parent/"privacy_review.json")
        with self.assertRaises(TypeError): gate.build_gate_payload(self.structural_occasions,self.structural_frame,independent_reconstruction_passed=True)

    def test_unperformed_privacy_and_transcript_audit_blocks_finalization(self):
        path,recon,privacy,_=self.create_run("privacy")
        privacy["agent_transcripts_reviewed"]=False
        gate._atomic_private_write(path.parent/"privacy_review.json",gate._canonical_json(privacy),gate.PRIVATE_SYNTHETIC_ROOT,overwrite=True)
        with self.assertRaisesRegex(ValueError,"review incomplete"):
            gate.finalize_candidate(path,path.parent/"reconstruction.json",path.parent/"privacy_review.json")
        self.assertFalse((path.parent/"final.json").exists())

    def test_successful_synthetic_two_stage_finalization_and_saved_revalidation(self):
        path,_,_,candidate_bytes=self.create_run("finalize")
        final_path=gate.finalize_candidate(path,path.parent/"reconstruction.json",path.parent/"privacy_review.json")
        result=gate.load_and_validate(final_path)
        self.assertTrue(all(row["passed"] for row in result["integrity"]))
        self.assertEqual(final_path.read_bytes(),gate._canonical_json(result))
        self.assertTrue(next(x for x in result["integrity"] if x["check_id"]=="independent_reconstruction")["passed"])
        self.assertTrue(gate.load_and_validate_bytes(final_path.read_bytes(),candidate_bytes=candidate_bytes,run_context=gate._load_private_json(path.parent/"run_context.json",gate.PRIVATE_SYNTHETIC_ROOT),reconstruction=gate._load_private_json(path.parent/"reconstruction.json",gate.PRIVATE_SYNTHETIC_ROOT),privacy=gate._load_private_json(path.parent/"privacy_review.json",gate.PRIVATE_SYNTHETIC_ROOT),log_bytes=(path.parent/"operation.log").read_bytes()))

    def test_duplicate_json_keys_malformed_json_and_missing_evidence_rejected(self):
        candidate=gate.serialize_candidate_payload(self.candidate)
        duplicated=candidate.replace(b'"schema_id":"B2B3_COUNTS_GATE_SCHEMA_V1"',b'"schema_id":"B2B3_COUNTS_GATE_SCHEMA_V1","schema_id":"B2B3_COUNTS_GATE_SCHEMA_V1"',1)
        with self.assertRaisesRegex(ValueError,"duplicate JSON key"): gate.load_candidate_bytes(duplicated)
        with self.assertRaises(ValueError): gate.load_candidate_bytes(b'{bad json')
        with self.assertRaises(ValueError): gate.load_and_validate_bytes(b'{}')

    def test_strict_types_duplicate_integrity_and_required_order(self):
        for mutate in (
            lambda x:x["primary_monthly_counts"][0].__setitem__("horizon_days",30.0),
            lambda x:x["metadata"]["horizons_days"].__setitem__(0,30.0),
            lambda x:x["calendar_coverage"][0].__setitem__("source_start_truncated",0),
            lambda x:x["integrity"].append(dict(x["integrity"][0])),
            lambda x:x["integrity"].pop(),
            lambda x:x["primary_monthly_counts"].reverse(),
            lambda x:x["quarter_thresholds"].reverse(),
            lambda x:x["primary_monthly_counts"][0].pop("possible_followup_end"),
            lambda x:x["metadata"].__setitem__("unapproved_metadata",1),
        ):
            bad=deepcopy(self.candidate); mutate(bad)
            with self.assertRaises(ValueError): gate._validate_payload(bad,require_pass=False,candidate=True)

    def test_c9_purchase_date_injection_and_c12_log_leakage_rejected(self):
        bad=deepcopy(self.candidate); bad["primary_monthly_counts"][0]["first_purchase_date"]="2011-01-01"
        with self.assertRaises(ValueError): gate._validate_payload(bad,require_pass=False,candidate=True)
        for log in (b"customer_id=123\n",b"invoice history omitted\n",b"B2B3 candidate generated\ncustomer_id=123\n"):
            with self.assertRaises(ValueError): gate._validate_generated_logs(log)

    def test_c8_symbolic_lower_bounds_are_acknowledged_but_never_emitted(self):
        # Contract-only algebra over synthetic N/F counts; no purchase history or project outcomes.
        n={"2011-01":20,"2011-02":30,"2011-03":40,"2011-04":50}
        f={"2011-01":10,"2011-02":10,"2011-03":10,"2011-04":10}
        def lower(lag):
            month="2011-04"; prior="2011-"+f"{4-lag:02d}"
            cumulative=sum(f[x] for x in n if x<month)
            residual=n[month]-f[month]
            return max(0,residual-(cumulative-n[prior]))
        bounds={lag:lower(lag) for lag in (1,2,3)}
        immature={1:0,2:5,3:35}
        maturity_adjusted={lag:max(0,bounds[lag]-immature[lag]) for lag in (1,2,3)}
        self.assertEqual(bounds,{1:50,2:40,3:30})
        self.assertEqual(maturity_adjusted,{1:50,2:35,3:0})
        output_keys=set(self.candidate)
        self.assertNotIn("repeat_numerators",output_keys)
        self.assertNotIn("c8_lower_bounds",output_keys)
        self.assertTrue(all(set(row)==gate.PRIMARY_KEYS for row in self.candidate["primary_monthly_counts"]))

    def test_proxy_40_41_42_monthly_boundaries(self):
        rows=deepcopy(self.candidate["primary_monthly_counts"])
        for n in (29,30,40,41,42):
            trial=deepcopy(rows)
            for row in trial:
                if row["population"]=="proxy_1" and row["month"]=="2011-01":
                    row["eligible_customer_month_count"]=n
                    row["h_mature_customer_month_count"]=n
                    row["h_immature_customer_month_count"]=0
                    row["common_90_mature_customer_month_count"]=n
            flags=gate._proxy_flags(trial)
            p2=next(x["value"] for x in flags if x["proxy_population"]=="proxy_2" and x["period_id"]=="2011-01" and x["count_basis"]=="eligible")
            p3=next(x["value"] for x in flags if x["proxy_population"]=="proxy_3" and x["period_id"]=="2011-01" and x["count_basis"]=="eligible")
            self.assertEqual(p2,False if n<30 else (True if n>=41 else "not_determined_at_gate"))
            self.assertEqual(p3,False if n<30 else (True if n>=42 else "not_determined_at_gate"))

    def test_real_mode_refuses_before_source_loading(self):
        with patch.dict(os.environ,{"B2B3_REAL_DATA_AUTHORIZED":"0"}), patch.object(gate,"load_validated_purchase_input",side_effect=AssertionError("source loader must not run")):
            self.assertFalse(gate.real_data_execution_enabled())
            with self.assertRaises(RuntimeError): gate.build_from_validated_source(None)
            with redirect_stderr(io.StringIO()):
                self.assertEqual(gate.main(["--mode","candidate-real","--authorization-file","/private/tmp/no-owner-auth.json","--operator-id","synthetic-operator","--run-id","noauth"]),2)

    def test_authorized_entrypoint_smoke_test_uses_only_mocked_synthetic_pipeline(self):
        now=datetime.now(timezone.utc)
        authorization={"authorization_id":"synthetic-approval","approved_by":"synthetic-owner","approved_at_utc":(now-timedelta(minutes=1)).isoformat(),"expires_at_utc":(now+timedelta(hours=1)).isoformat(),"action":"candidate_real_data","schema_id":gate.SCHEMA_ID,"producer_sha256":gate._file_sha(gate.__file__),"output_root":str(gate.PRIVATE_REAL_ROOT)}
        with patch.dict(os.environ,{"B2B3_REAL_DATA_AUTHORIZED":"1"}), \
             patch.object(gate,"load_validated_purchase_input",return_value=SimpleNamespace(_frame=self.structural_frame)) as loader, \
             patch.object(gate,"build_purchase_occasions",return_value=(self.structural_occasions,{"synthetic_only":True})):
            self.assertTrue(gate.real_data_execution_enabled(authorization))
            candidate=gate.build_from_validated_source(authorization)
            loader.assert_called_once_with()
        status={row["check_id"]:row["passed"] for row in candidate["integrity"]}
        self.assertTrue(status["b2b2_structural_regression"])
        self.assertFalse(status["independent_reconstruction"])
        self.assertFalse(status["privacy_transcript_audit"])


if __name__=="__main__": unittest.main(verbosity=2)
