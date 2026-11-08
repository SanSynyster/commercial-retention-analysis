"""B2B-3 counts-only feasibility gate (schema V1).

This module computes structural purchaser eligibility and calendar maturity only.
It deliberately contains no repeat/outcome computation. Real execution is disabled
until a separate owner authorization is recorded in code and operations policy.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile

import pandas as pd

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

from COMMERCIAL_DS_003_STAGE_B2B2 import derive_population_memberships
from COMMERCIAL_DS_003_PURCHASE_OCCASIONS import (
    _build_purchase_occasions_for_test, build_purchase_occasions,
    load_validated_purchase_input,
)

SCHEMA_ID = "B2B3_COUNTS_GATE_SCHEMA_V1"
PRODUCER_VERSION = "1.0.0"
REAL_DATA_EXECUTION_ENABLED = False
SOURCE_START = date(2009, 12, 1)
SOURCE_END = date(2011, 12, 9)
CUTOFF = date(2010, 12, 1)
HORIZONS = (30, 60, 90)
PRIMARY_POPULATIONS = ("left_censored", "proxy_1")
ALL_POPULATIONS = ("left_censored", "proxy_1", "proxy_2", "proxy_3")
PINNED = {
    "source_v1_sha256": "43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d",
    "source_v2_sha256": "32569a66f3842a82b0d8c4d63b263c5d98a76bde5d1f65c6c01bf457e541d3a9",
    "seed_sha256": "7b4611c78ca22d108c2616076c84b7c1db2efb8453ee9a32faceb027bb181e4e",
    "inventory_sha256": "0d507be1e2b062705ba9763507342db71a24663b0d76176b31a2b39e4f66175b",
    "stage_a_pins_sha256": "a96d2e9d5787dc1edd0e5c493e072ede4c342e845921e3242e90742625c8ba49",
    "occasion_pins_sha256": "4cf7b761a1b02cea853dbe577af7dddf8070fe65d0dcdfc7a71e2a064986f433",
    "bridge_pins_sha256": "765ff7a29530b4221ec3ab171fc2ed861fcb9247901ba84419d2ecf7e786e96d",
    "occasion_output_sha256": "402090a0eea8abd02d4d72b5c12301fa51334c925f19840c9a639282d61e2109",
    "b2b2_json_sha256": "5c46665535217a72234e2df13fd95e3f0ce4a0f67a3e6ddf905da43d95f2d345",
    "b2b2_summary_sha256": "5ec46c4d68d9969c0493da2266d1f002ba7ac1ef6b5b3e225d967bd00d609ed1",
}
TOP_KEYS = {"metadata", "calendar_coverage", "primary_monthly_counts", "quarter_thresholds", "proxy_feasibility_flags", "integrity"}
META_KEYS = {"schema_id", "producer_version", "producer_sha256", *PINNED, "source_start", "source_end", "source_end_partial_through", "occasion_contract_id", "population_codes", "horizons_days", "maturity_rule_id", "common_risk_set", "outcomes_computed", "deliverable_scope"}
CAL_KEYS = {"calendar_unit", "period_id", "period_start", "period_end", "source_start_truncated", "source_end_truncated", "final_source_day_partial", "population_cutoff_split_possible", "coverage_status"}
PRIMARY_KEYS = {"population", "month", "horizon_days", "eligible_customer_month_count", "h_mature_customer_month_count", "h_immature_customer_month_count", "common_90_mature_customer_month_count", "coverage_status", "possible_followup_start", "possible_followup_end", "followup_months_crossed", "followup_coverage_status"}
FLAG_KEYS = {"population", "quarter", "horizon_days", "count_basis", "threshold", "value"}
PROXY_KEYS = {"proxy_population", "calendar_unit", "period_id", "horizon_days", "count_basis", "threshold", "value"}
INTEGRITY_IDS = ("schema_allowlist", "count_arithmetic", "horizon_common_risk_set", "calendar_span_derivation", "b2b2_structural_regression", "independent_reconstruction", "c8_boundary_audit", "privacy_transcript_audit")
AUTO_CHECK_IDS = ("schema_allowlist", "count_arithmetic", "horizon_common_risk_set", "calendar_span_derivation", "c8_boundary_audit")
RECON_SECTIONS = ("metadata", "calendar_coverage", "primary_monthly_counts", "quarter_thresholds", "proxy_feasibility_flags")
RECON_EVIDENCE_KEYS = {"evidence_schema", "candidate_sha256", "operator_id", "reviewer_id", "reviewer_code_sha256", "reviewed_at_utc", "reconstructed_sections", "b2b2_structural_reference"}
PRIVACY_EVIDENCE_KEYS = {"evidence_schema", "candidate_sha256", "operator_id", "reviewer_id", "reviewed_at_utc", "generated_logs_sha256", "aggregate_only_confirmed", "generated_logs_reviewed", "agent_transcripts_reviewed", "no_customer_level_exposure_found"}
AUTH_KEYS = {"authorization_id", "approved_by", "approved_at_utc", "expires_at_utc", "action", "schema_id", "producer_sha256", "output_root"}
PRIVATE_SYNTHETIC_ROOT = REPO_ROOT / ".local" / "b2b3-gate-synthetic"
PRIVATE_REAL_ROOT = REPO_ROOT / ".local" / "b2b3-gate-output"
SAFE_LOG_LINES = {"B2B3 candidate generated", "B2B3 final artifact written", "B2B3 operation failed"}


def _month_start(y, m): return date(y, m, 1)
def _month_end(y, m):
    nxt = date(y + (m == 12), 1 if m == 12 else m + 1, 1)
    return nxt - timedelta(days=1)
def _add_month(y, m): return (y + (m == 12), 1 if m == 12 else m + 1)
def _month_id(d): return f"{d.year:04d}-{d.month:02d}"
def _quarter_id(d): return f"{d.year:04d}-Q{(d.month - 1)//3 + 1}"
def _periods():
    out=[]; y,m=2009,12
    while (y,m) <= (2011,12):
        s=_month_start(y,m); e=_month_end(y,m)
        out.append(("month",_month_id(s),s,e)); y,m=_add_month(y,m)
    for y in range(2009,2012):
        for q in range(1,5):
            s=date(y,(q-1)*3+1,1)
            e=_month_end(y,q*3)
            if e<SOURCE_START or s>SOURCE_END: continue
            out.append(("quarter",f"{y:04d}-Q{q}",s,e))
    return out


def _coverage(unit, pid, start, end):
    st = start < SOURCE_START
    en = end > SOURCE_END
    partial_day = start <= SOURCE_END <= end
    split = start < CUTOFF <= end
    status = "source_partial" if st or en else ("calendar_complete_population_cutoff_split_possible" if split else "source_complete")
    return {"calendar_unit":unit,"period_id":pid,"period_start":start.isoformat(),"period_end":end.isoformat(),"source_start_truncated":st,"source_end_truncated":en,"final_source_day_partial":partial_day,"population_cutoff_split_possible":split,"coverage_status":status}


def _calendar_coverage(): return [_coverage(*p) for p in _periods()]


def _followup_span(month, h):
    y,m=map(int,month.split("-")); ms=_month_start(y,m); me=_month_end(y,m)
    a_start=max(ms,SOURCE_START); a_end=min(me,SOURCE_END-timedelta(days=h))
    if a_start>a_end:
        return None,None,[],"no_calendar_eligible_anchor"
    fs=a_start+timedelta(days=1); fe=a_end+timedelta(days=h-1)
    months=[]; cur=date(fs.year,fs.month,1); last=date(fe.year,fe.month,1)
    while cur<=last:
        months.append(_month_id(cur)); yy,mm=_add_month(cur.year,cur.month); cur=date(yy,mm,1)
    return fs.isoformat(),fe.isoformat(),months,"calendar_span_defined"


def _threshold_from_exact_months(xs):
    if not xs: return "not_determined_at_gate"
    return True if max(xs)>=30 else (False if sum(xs)<30 else "not_determined_at_gate")


def _records_from_anchors(anchors, memberships):
    # anchors: (canonical customer id, date); identifiers stay local and are never serialized.
    by_month=defaultdict(set); first_by_customer_month={}
    for cid, day in anchors:
        key=(cid,_month_id(day))
        if key not in first_by_customer_month or day<first_by_customer_month[key]: first_by_customer_month[key]=day
        for pop in PRIMARY_POPULATIONS:
            if cid in memberships[pop]: by_month[(pop,_month_id(day))].add(cid)
    records=[]; raw_counts={}
    months=[p[1] for p in _periods() if p[0]=="month"]
    for pop in PRIMARY_POPULATIONS:
        for month in months:
            ids=by_month.get((pop,month),set()); n=len(ids)
            maturity_dates=[first_by_customer_month[(cid,month)] for cid in ids]
            mature={h:sum(1 for anchor in maturity_dates if anchor+timedelta(days=h)<=SOURCE_END) for h in HORIZONS}
            for h in HORIZONS:
                fs,fe,crossed,fstatus=_followup_span(month,h)
                row={"population":pop,"month":month,"horizon_days":h,"eligible_customer_month_count":n,"h_mature_customer_month_count":mature[h],"h_immature_customer_month_count":n-mature[h],"common_90_mature_customer_month_count":mature[90],"coverage_status":_month_coverage(month)["coverage_status"],"possible_followup_start":fs,"possible_followup_end":fe,"followup_months_crossed":crossed,"followup_coverage_status":fstatus}
                records.append(row); raw_counts[(pop,month,h,"eligible")]=n; raw_counts[(pop,month,h,"h_mature")]=mature[h]; raw_counts[(pop,month,h,"common_90_mature")]=mature[90]
    return records,raw_counts


def _month_coverage(month):
    y,m=map(int,month.split("-")); return _coverage("month",month,_month_start(y,m),_month_end(y,m))


def _quarter_thresholds(raw):
    rows=[]
    quarters=[p[1] for p in _periods() if p[0]=="quarter"]
    for pop in PRIMARY_POPULATIONS:
        for q in quarters:
            ms=[p[1] for p in _periods() if p[0]=="month" and _quarter_id(p[2])==q]
            for basis in ("eligible","h_mature","common_90_mature"):
                hs=(None,) if basis=="eligible" else HORIZONS
                for h in hs:
                    xs=[raw[(pop,m,90 if h is None else h,basis)] for m in ms]
                    rows.append({"population":pop,"quarter":q,"horizon_days":h,"count_basis":basis,"threshold":30,"value":_threshold_from_exact_months(xs)})
    return rows


def _proxy_flags(primary_rows):
    p1={(r["month"],r["horizon_days"]):r for r in primary_rows if r["population"]=="proxy_1"}
    out=[]
    for proxy,diff in (("proxy_2",11),("proxy_3",12)):
        for m in [p[1] for p in _periods() if p[0]=="month"]:
            for basis in ("eligible","h_mature","common_90_mature"):
                hs=(None,) if basis=="eligible" else HORIZONS
                for h in hs:
                    r=p1[(m,90 if h is None else h)]
                    n=r["eligible_customer_month_count"] if basis=="eligible" else (r["h_mature_customer_month_count"] if basis=="h_mature" else r["common_90_mature_customer_month_count"])
                    # Fixed global population deltas yield only conservative bounds per period.
                    value=True if n>=30+diff else (False if n<30 else "not_determined_at_gate")
                    out.append({"proxy_population":proxy,"calendar_unit":"month","period_id":m,"horizon_days":h,"count_basis":basis,"threshold":30,"value":value})
        for q in [p[1] for p in _periods() if p[0]=="quarter"]:
            ms=[p[1] for p in _periods() if p[0]=="month" and _quarter_id(p[2])==q]
            for basis in ("eligible","h_mature","common_90_mature"):
                hs=(None,) if basis=="eligible" else HORIZONS
                for h in hs:
                    vals=[]
                    for m in ms:
                        r=p1[(m,90 if h is None else h)]
                        vals.append(r["eligible_customer_month_count"] if basis=="eligible" else (r["h_mature_customer_month_count"] if basis=="h_mature" else r["common_90_mature_customer_month_count"]))
                    lower=max([max(0,x-diff) for x in vals],default=0); upper=sum(vals)
                    value=True if lower>=30 else (False if upper<30 else "not_determined_at_gate")
                    out.append({"proxy_population":proxy,"calendar_unit":"quarter","period_id":q,"horizon_days":h,"count_basis":basis,"threshold":30,"value":value})
    return out


def _customer_records(anchors):
    grouped=defaultdict(list)
    for cid,day in anchors: grouped[cid].append(day)
    return {cid:{"first_observed_date":min(days)} for cid,days in grouped.items()}


def _occasion_customer_id(value):
    # O-9 records carry the canonical numeric key as a decimal string. The
    # source-row canonicalizer intentionally rejects text and is not suitable
    # for this already-canonical internal representation.
    if not isinstance(value,str) or not re.fullmatch(r"[1-9][0-9]*",value):
        raise ValueError("occasion customer key is not canonical")
    return value


def _membership(anchors, classified_frame):
    return derive_population_memberships(_customer_records(anchors),classified_frame)


def _structural_regression_for_anchors(anchors, membership):
    expected_sizes={"left_censored":4239,"proxy_1":1613,"proxy_2":1602,"proxy_3":1601}
    expected_mature={"left_censored":4239,"proxy_1":1017,"proxy_2":1008,"proxy_3":1008}
    first=_customer_records(anchors)
    sizes={p:len(membership[p]) for p in expected_sizes}
    mature={p:sum(1 for cid in membership[p] if first[cid]["first_observed_date"]+timedelta(days=90)<=SOURCE_END) for p in expected_sizes}
    if sizes!=expected_sizes or mature!=expected_mature:
        raise ValueError("B2B-2 structural regression mismatch")
    return True


def _integrity(statuses=None):
    statuses=statuses or {}
    return [{"check_id":check,"passed":statuses.get(check,False)} for check in INTEGRITY_IDS]


def _metadata(producer_sha):
    return {"schema_id":SCHEMA_ID,"producer_version":PRODUCER_VERSION,"producer_sha256":producer_sha,**PINNED,"source_start":SOURCE_START.isoformat(),"source_end":SOURCE_END.isoformat(),"source_end_partial_through":"12:50","occasion_contract_id":"O-9","population_codes":list(ALL_POPULATIONS),"horizons_days":list(HORIZONS),"maturity_rule_id":"anchor_plus_H_calendar_days_lte_source_end_v1","common_risk_set":"h90_mature_primary_customer_month","outcomes_computed":False,"deliverable_scope":"aggregate_only"}


def _file_sha(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
    return h.hexdigest()


def _validate_payload(payload, strict_pins=True, require_pass=True, candidate=False):
    if set(payload)!=TOP_KEYS: raise ValueError("schema allowlist top-level mismatch")
    m=payload["metadata"]
    if set(m)!=META_KEYS: raise ValueError("metadata allowlist mismatch")
    if m["schema_id"]!=SCHEMA_ID or m["outcomes_computed"] is not False or m["deliverable_scope"]!="aggregate_only": raise ValueError("metadata boundary violation")
    if m["producer_version"]!=PRODUCER_VERSION or m["producer_sha256"]!=_file_sha(__file__): raise ValueError("producer provenance mismatch")
    fixed={"source_start":"2009-12-01","source_end":"2011-12-09","source_end_partial_through":"12:50","occasion_contract_id":"O-9","population_codes":list(ALL_POPULATIONS),"horizons_days":list(HORIZONS),"maturity_rule_id":"anchor_plus_H_calendar_days_lte_source_end_v1","common_risk_set":"h90_mature_primary_customer_month"}
    if any(m[k]!=v for k,v in fixed.items()): raise ValueError("frozen metadata value mismatch")
    if type(m["horizons_days"]) is not list or any(type(x) is not int for x in m["horizons_days"]): raise ValueError("horizon metadata type mismatch")
    if any(type(m[k]) is not str for k in ("schema_id","producer_version","producer_sha256","source_start","source_end","source_end_partial_through","occasion_contract_id","maturity_rule_id","common_risk_set","deliverable_scope")):
        raise ValueError("metadata string type mismatch")
    if m["population_codes"]!=list(ALL_POPULATIONS) or type(m["population_codes"]) is not list or any(type(x) is not str for x in m["population_codes"]): raise ValueError("population metadata type mismatch")
    if m["outcomes_computed"] is not False: raise ValueError("outcome boundary metadata mismatch")
    if not re.fullmatch(r"[0-9a-f]{64}",m["producer_sha256"]): raise ValueError("producer hash format invalid")
    if strict_pins and any(m[k]!=v for k,v in PINNED.items()): raise ValueError("frozen provenance pin mismatch")
    for rows,keyset,name in ((payload["calendar_coverage"],CAL_KEYS,"calendar"),(payload["primary_monthly_counts"],PRIMARY_KEYS,"primary"),(payload["quarter_thresholds"],FLAG_KEYS,"quarter flag"),(payload["proxy_feasibility_flags"],PROXY_KEYS,"proxy flag"),(payload["integrity"],{"check_id","passed"},"integrity")):
        if not isinstance(rows,list) or any(not isinstance(r,dict) or set(r)!=keyset for r in rows): raise ValueError(f"{name} schema allowlist mismatch")
    expected_cal=_calendar_coverage()
    for record in payload["calendar_coverage"]:
        if any(type(record[k]) is not bool for k in ("source_start_truncated","source_end_truncated","final_source_day_partial","population_cutoff_split_possible")):
            raise ValueError("calendar boolean type mismatch")
        if any(type(record[k]) is not str for k in ("calendar_unit","period_id","period_start","period_end","coverage_status")):
            raise ValueError("calendar string type mismatch")
    if payload["calendar_coverage"]!=expected_cal: raise ValueError("calendar coverage does not match fixed calendar")
    seen=set()
    expected_primary_order=[(pop,month,h) for pop in PRIMARY_POPULATIONS for month in [p[1] for p in _periods() if p[0]=="month"] for h in HORIZONS]
    actual_primary_order=[]
    for r in payload["primary_monthly_counts"]:
        if r["population"] not in PRIMARY_POPULATIONS or type(r["population"]) is not str or type(r["horizon_days"]) is not int or r["horizon_days"] not in HORIZONS: raise ValueError("primary row category violation")
        if type(r["month"]) is not str or type(r["coverage_status"]) is not str or type(r["followup_coverage_status"]) is not str: raise ValueError("primary string type mismatch")
        if type(r["followup_months_crossed"]) is not list or any(type(x) is not str for x in r["followup_months_crossed"]): raise ValueError("follow-up month list type mismatch")
        if any(r[k] is not None and type(r[k]) is not str for k in ("possible_followup_start","possible_followup_end")): raise ValueError("follow-up date type mismatch")
        key=(r["population"],r["month"],r["horizon_days"])
        if key in seen: raise ValueError("duplicate primary row")
        seen.add(key); actual_primary_order.append(key)
        n,mat,imm,common=(r[x] for x in ("eligible_customer_month_count","h_mature_customer_month_count","h_immature_customer_month_count","common_90_mature_customer_month_count"))
        if any(type(x) is not int or x<0 for x in (n,mat,imm,common)) or mat+imm!=n or mat>n or common>mat: raise ValueError("primary count arithmetic violation")
        fs,fe,months,status=_followup_span(r["month"],r["horizon_days"])
        if (r["possible_followup_start"],r["possible_followup_end"],r["followup_months_crossed"],r["followup_coverage_status"])!=(fs,fe,months,status): raise ValueError("calendar span mismatch")
        if r["coverage_status"]!=_month_coverage(r["month"])["coverage_status"]: raise ValueError("primary coverage mismatch")
    months=[p[1] for p in _periods() if p[0]=="month"]
    if len(seen)!=len(PRIMARY_POPULATIONS)*len(months)*len(HORIZONS): raise ValueError("primary row coverage incomplete")
    if actual_primary_order!=expected_primary_order: raise ValueError("primary row ordering mismatch")
    primary_lookup={(r["population"],r["month"],r["horizon_days"]):r for r in payload["primary_monthly_counts"]}
    raw={}
    for (pop,month,h),r in primary_lookup.items():
        raw[(pop,month,h,"eligible")]=r["eligible_customer_month_count"]
        raw[(pop,month,h,"h_mature")]=r["h_mature_customer_month_count"]
        raw[(pop,month,h,"common_90_mature")]=r["common_90_mature_customer_month_count"]
    if payload["quarter_thresholds"]!=_quarter_thresholds(raw): raise ValueError("quarter threshold derivation mismatch")
    if payload["proxy_feasibility_flags"]!=_proxy_flags(payload["primary_monthly_counts"]): raise ValueError("proxy threshold derivation mismatch")
    for pop in PRIMARY_POPULATIONS:
        for month in months:
            rows={r["horizon_days"]:r for r in payload["primary_monthly_counts"] if r["population"]==pop and r["month"]==month}
            if len(rows)!=3 or len({r["eligible_customer_month_count"] for r in rows.values()})!=1 or len({r["common_90_mature_customer_month_count"] for r in rows.values()})!=1:
                raise ValueError("cross-horizon common-risk-set mismatch")
            if any(rows[90]["common_90_mature_customer_month_count"]>r["h_mature_customer_month_count"] for r in rows.values()):
                raise ValueError("common 90-day risk set exceeds horizon maturity")
            if not (rows[30]["h_mature_customer_month_count"]>=rows[60]["h_mature_customer_month_count"]>=rows[90]["h_mature_customer_month_count"]==rows[90]["common_90_mature_customer_month_count"]):
                raise ValueError("horizon maturity nesting mismatch")
    for key in (("quarter_thresholds",FLAG_KEYS),("proxy_feasibility_flags",PROXY_KEYS)):
        for row in payload[key[0]]:
            if row["horizon_days"] is not None and type(row["horizon_days"]) is not int: raise ValueError("threshold horizon type mismatch")
            if (type(row["threshold"]) is not int or row["threshold"]!=30
                or not (type(row["value"]) is bool or row["value"]=="not_determined_at_gate")):
                raise ValueError("threshold flag invalid")
    if [r["check_id"] for r in payload["integrity"]]!=list(INTEGRITY_IDS) or any(type(r["check_id"]) is not str or type(r["passed"]) is not bool for r in payload["integrity"]): raise ValueError("integrity schema mismatch")
    status={r["check_id"]:r["passed"] for r in payload["integrity"]}
    if candidate and (status["independent_reconstruction"] or status["privacy_transcript_audit"]): raise ValueError("candidate cannot pre-attest human checks")
    if candidate and not all(status[k] for k in AUTO_CHECK_IDS): raise ValueError("candidate automated integrity check failed")
    if require_pass and not all(r["passed"] for r in payload["integrity"]): raise ValueError("integrity check failed")
    return True


def build_gate_payload(occasions, classified_frame, *, producer_path=None, enforce_b2b2_regression=False):
    """Build aggregate V1 from canonical occasion records and classified rows.

    Intended for synthetic fixtures. Production construction is separately gated.
    """
    anchors=[]
    seen_invoice=set()
    for row in occasions:
        cid=_occasion_customer_id(row.get("customer_id"))
        day=date.fromisoformat(row["transaction_date"])
        inv=row.get("invoice_id")
        if not cid or not isinstance(inv,str) or inv in seen_invoice or not SOURCE_START<=day<=SOURCE_END: raise ValueError("invalid canonical occasion input")
        seen_invoice.add(inv); anchors.append((cid,day))
    membership=_membership(anchors,classified_frame)
    regression=False
    try:
        _structural_regression_for_anchors(anchors,membership)
        regression=True
    except ValueError:
        if enforce_b2b2_regression: raise
    primary,raw=_records_from_anchors(anchors,membership)
    payload={"metadata":_metadata(_file_sha(producer_path or __file__)),"calendar_coverage":_calendar_coverage(),"primary_monthly_counts":primary,"quarter_thresholds":_quarter_thresholds(raw),"proxy_feasibility_flags":_proxy_flags(primary),"integrity":_integrity({})}
    _validate_payload(payload,strict_pins=True,require_pass=False)
    statuses={check:True for check in AUTO_CHECK_IDS}
    statuses["b2b2_structural_regression"]=regression
    # These can only be completed by a separate reviewer in the finalization stage.
    statuses["independent_reconstruction"]=False
    statuses["privacy_transcript_audit"]=False
    payload["integrity"]=_integrity(statuses)
    _validate_payload(payload,strict_pins=True,require_pass=False,candidate=True)
    return payload


def build_from_synthetic_rows(classified_frame):
    """Synthetic-only helper: rows are processed by the reviewed O-9 occasion builder."""
    occasions,_summary=_build_purchase_occasions_for_test(classified_frame)
    return build_gate_payload(occasions,classified_frame)


def build_from_validated_source(authorization):
    """Build a private candidate only after explicit CLI/env/owner authorization."""
    if not real_data_execution_enabled(authorization):
        raise RuntimeError("real-data B2B-3 gate execution is disabled; valid owner authorization required")
    try:
        validated=load_validated_purchase_input()
        occasions,_summary=build_purchase_occasions(validated)
        return build_gate_payload(occasions,validated._frame,producer_path=__file__,enforce_b2b2_regression=True)
    except Exception:
        raise RuntimeError("structural feasibility gate failed; diagnostic details suppressed") from None


def serialize_payload(payload):
    # Final artifacts can only be minted by finalize_candidate after evidence
    # comparison. A mapping with passed=True flags is not proof of execution.
    raise ValueError("final serialization requires candidate finalization evidence")


def _canonical_json(payload):
    return (json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False)+"\n").encode("utf-8")


def serialize_candidate_payload(payload):
    """Serialize a private, non-final candidate; never accept it as final output."""
    _validate_payload(payload,require_pass=False,candidate=True)
    return _canonical_json(payload)


def _pairs_no_duplicates(pairs):
    result={}
    for key,value in pairs:
        if key in result: raise ValueError("duplicate JSON key")
        result[key]=value
    return result


def _parse_json_bytes(raw):
    if not isinstance(raw,(bytes,bytearray)): raise TypeError("JSON input must be bytes")
    try:
        return json.loads(bytes(raw).decode("utf-8"),object_pairs_hook=_pairs_no_duplicates,
                          parse_constant=lambda _value: (_ for _ in ()).throw(ValueError("invalid JSON number")))
    except (UnicodeDecodeError,json.JSONDecodeError) as exc:
        raise ValueError("malformed JSON") from None


def load_candidate_bytes(raw):
    payload=_parse_json_bytes(raw)
    _validate_payload(payload,require_pass=False,candidate=True)
    if serialize_candidate_payload(payload)!=bytes(raw): raise ValueError("candidate JSON is not canonical")
    return payload


def load_and_validate_bytes(raw, *, candidate_bytes=None, run_context=None,
                            reconstruction=None, privacy=None, log_bytes=None):
    payload=_parse_json_bytes(raw)
    _validate_payload(payload,require_pass=True,candidate=False)
    if _canonical_json(payload)!=bytes(raw): raise ValueError("final JSON is not canonical")
    if any(x is None for x in (candidate_bytes,run_context,reconstruction,privacy,log_bytes)):
        raise ValueError("final artifact requires retained independent evidence")
    candidate=load_candidate_bytes(candidate_bytes)
    _verify_evidence(candidate,candidate_bytes,run_context,reconstruction,privacy,log_bytes)
    expected=dict(candidate); expected["integrity"]=_integrity({row["check_id"]:True for row in candidate["integrity"]})
    if _canonical_json(expected)!=bytes(raw): raise ValueError("final artifact does not match verified candidate")
    return payload


def load_candidate(path):
    path=Path(path)
    _check_private_file(path)
    return load_candidate_bytes(path.read_bytes())


def load_and_validate(path):
    path=Path(path)
    _check_private_file(path)
    if path.name!="final.json": raise ValueError("final artifact path invalid")
    run_dir=path.parent
    root=next((p for p in (PRIVATE_SYNTHETIC_ROOT,PRIVATE_REAL_ROOT) if p.resolve() in run_dir.resolve().parents),None)
    if root is None: raise ValueError("final artifact is outside approved private roots")
    _check_private_file(run_dir/"candidate.json")
    candidate_bytes=(run_dir/"candidate.json").read_bytes()
    context=_load_private_json(run_dir/"run_context.json",root)
    expected_mode="synthetic" if root==PRIVATE_SYNTHETIC_ROOT else "real"
    if context.get("run_id")!=run_dir.name or context.get("execution_mode")!=expected_mode: raise ValueError("artifact run context path mismatch")
    recon=_load_private_json(run_dir/"reconstruction.json",root)
    privacy=_load_private_json(run_dir/"privacy_review.json",root)
    log_path=run_dir/"operation.log"; _check_private_file(log_path); logs=log_path.read_bytes()
    return load_and_validate_bytes(path.read_bytes(),candidate_bytes=candidate_bytes,run_context=context,reconstruction=recon,privacy=privacy,log_bytes=logs)


def _check_private_file(path):
    if path.is_symlink() or not path.is_file(): raise ValueError("artifact file unavailable")
    if stat.S_IMODE(path.stat().st_mode)!=0o600: raise ValueError("artifact file permissions invalid")
    parent=path.parent
    if stat.S_IMODE(parent.stat().st_mode)!=0o700: raise ValueError("artifact directory permissions invalid")


def _utc_timestamp(value):
    if type(value) is not str: raise ValueError("timestamp type invalid")
    try: parsed=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError: raise ValueError("timestamp invalid") from None
    if parsed.tzinfo is None: raise ValueError("timestamp must include timezone")
    return parsed.astimezone(timezone.utc)


def _valid_authorization_record(record):
    if not isinstance(record,dict) or set(record)!=AUTH_KEYS: return False
    if any(type(record[k]) is not str or not record[k].strip() for k in AUTH_KEYS): return False
    if record["action"]!="candidate_real_data" or record["schema_id"]!=SCHEMA_ID: return False
    if record["producer_sha256"]!=_file_sha(__file__) or record["output_root"]!=str(PRIVATE_REAL_ROOT): return False
    try:
        now=datetime.now(timezone.utc)
        approved=_utc_timestamp(record["approved_at_utc"]); expires=_utc_timestamp(record["expires_at_utc"])
        if approved>now or expires<=now or expires<=approved: return False
    except ValueError:
        return False
    return True


def load_real_authorization(path):
    record=_parse_json_bytes(Path(path).read_bytes())
    if not _valid_authorization_record(record): raise ValueError("owner authorization record invalid or expired")
    return record


def _safe_run_id(run_id):
    if type(run_id) is not str or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}",run_id):
        raise ValueError("run id invalid")
    return run_id


def _ensure_private_directory(directory, allowed_root):
    directory=Path(directory); allowed_root=Path(allowed_root)
    if directory.is_symlink() or allowed_root.is_symlink(): raise ValueError("private output path cannot be a symlink")
    resolved_root=allowed_root.resolve(strict=False); resolved=directory.resolve(strict=False)
    if resolved!=resolved_root and resolved_root not in resolved.parents: raise ValueError("output path outside private root")
    if allowed_root.parent.is_symlink(): raise ValueError("private parent cannot be a symlink")
    directory.mkdir(parents=True,exist_ok=True,mode=0o700)
    if allowed_root.parent.exists() and stat.S_IMODE(allowed_root.parent.stat().st_mode)!=0o700:
        raise ValueError("private parent permissions invalid")
    os.chmod(directory,0o700)
    if allowed_root.exists() and stat.S_IMODE(allowed_root.stat().st_mode)!=0o700:
        raise ValueError("private output root permissions invalid")
    if stat.S_IMODE(directory.stat().st_mode)!=0o700: raise ValueError("private directory permissions invalid")
    return directory


def _atomic_private_write(path, data, allowed_root, *, overwrite=False):
    path=Path(path); root=Path(allowed_root)
    if path.name not in {"candidate.json","final.json","run_context.json","operation.log","reconstruction.json","privacy_review.json"}:
        raise ValueError("private output filename not allowed")
    parent=_ensure_private_directory(path.parent,root)
    if path.is_symlink() or (path.exists() and not overwrite): raise ValueError("private output already exists")
    if path.resolve(strict=False).parent!=parent.resolve(): raise ValueError("private output path invalid")
    old_umask=os.umask(0o077); temporary=None
    try:
        fd,temporary_name=tempfile.mkstemp(prefix=".b2b3-tmp-",dir=parent)
        temporary=Path(temporary_name)
        os.fchmod(fd,0o600)
        with os.fdopen(fd,"wb") as handle:
            handle.write(data); handle.flush(); os.fsync(handle.fileno())
        os.replace(temporary,path); temporary=None; os.chmod(path,0o600)
        dir_fd=os.open(parent,os.O_RDONLY)
        try: os.fsync(dir_fd)
        finally: os.close(dir_fd)
    finally:
        os.umask(old_umask)
        if temporary is not None:
            try: temporary.unlink()
            except FileNotFoundError: pass
    return path


def _safe_logs_bytes(lines):
    if any(line not in SAFE_LOG_LINES for line in lines): raise ValueError("generated log line not allowlisted")
    return ("\n".join(lines)+"\n").encode("ascii")


def _validate_generated_logs(raw):
    try: lines=raw.decode("ascii").splitlines()
    except (UnicodeDecodeError,AttributeError): raise ValueError("generated log encoding invalid") from None
    if not lines or _safe_logs_bytes(lines)!=raw: raise ValueError("generated logs failed automated privacy check")
    return True


def write_candidate(payload, run_id, operator_id, *, synthetic=False, authorization=None):
    run_id=_safe_run_id(run_id)
    if type(operator_id) is not str or not operator_id.strip(): raise ValueError("operator identity required")
    if not synthetic and not real_data_execution_enabled(authorization): raise ValueError("real candidate writing requires owner authorization")
    root=PRIVATE_SYNTHETIC_ROOT if synthetic else PRIVATE_REAL_ROOT
    _ensure_private_directory(root,root)
    run_dir=root/run_id
    if run_dir.exists() or run_dir.is_symlink(): raise ValueError("private run directory already exists")
    run_dir=_ensure_private_directory(run_dir,root)
    try:
        candidate_bytes=serialize_candidate_payload(payload)
        sha=hashlib.sha256(candidate_bytes).hexdigest()
        context={"context_schema":"B2B3_PRIVATE_RUN_CONTEXT_V1","run_id":run_id,"operator_id":operator_id,"schema_id":SCHEMA_ID,"producer_sha256":payload["metadata"]["producer_sha256"],"candidate_sha256":sha,"execution_mode":"synthetic" if synthetic else "real","authorization_id":None if synthetic else authorization["authorization_id"],"authorization_sha256":None if synthetic else hashlib.sha256(_canonical_json(authorization)).hexdigest()}
        log_bytes=_safe_logs_bytes(["B2B3 candidate generated"])
        _atomic_private_write(run_dir/"candidate.json",candidate_bytes,root)
        _atomic_private_write(run_dir/"run_context.json",_canonical_json(context),root)
        _atomic_private_write(run_dir/"operation.log",log_bytes,root)
        _validate_generated_logs((run_dir/"operation.log").read_bytes())
        return run_dir/"candidate.json"
    except Exception:
        for name in ("candidate.json","run_context.json","operation.log","final.json"):
            try: (run_dir/name).unlink()
            except FileNotFoundError: pass
        try: run_dir.rmdir()
        except OSError: pass
        raise RuntimeError("candidate staging failed; details suppressed") from None


def _load_private_json(path, root):
    path=Path(path)
    if path.is_symlink() or Path(root).resolve() not in path.resolve().parents: raise ValueError("evidence path outside private directory")
    if path.name not in {"run_context.json","reconstruction.json","privacy_review.json"}: raise ValueError("private evidence filename invalid")
    _check_private_file(path)
    raw=path.read_bytes(); obj=_parse_json_bytes(raw)
    if _canonical_json(obj)!=raw: raise ValueError("evidence JSON is not canonical")
    return obj


def _verify_evidence(candidate_payload, candidate_bytes, run_context, recon, privacy, log_bytes):
    candidate_hash=hashlib.sha256(candidate_bytes).hexdigest()
    candidate_status={row["check_id"]:row["passed"] for row in candidate_payload["integrity"]}
    if not all(candidate_status[k] for k in set(AUTO_CHECK_IDS)|{"b2b2_structural_regression"}):
        raise ValueError("candidate automated integrity checks incomplete")
    context_keys={"context_schema","run_id","operator_id","schema_id","producer_sha256","candidate_sha256","execution_mode","authorization_id","authorization_sha256"}
    if not isinstance(run_context,dict) or set(run_context)!=context_keys: raise ValueError("private run context invalid")
    operator=run_context["operator_id"]
    if (type(operator) is not str or not operator.strip() or run_context["candidate_sha256"]!=candidate_hash
        or run_context["context_schema"]!="B2B3_PRIVATE_RUN_CONTEXT_V1"
        or run_context["schema_id"]!=SCHEMA_ID
        or run_context["producer_sha256"]!=candidate_payload["metadata"]["producer_sha256"]):
        raise ValueError("candidate context mismatch")
    if run_context["execution_mode"] not in ("synthetic","real"): raise ValueError("candidate execution mode invalid")
    if _safe_run_id(run_context["run_id"])!=run_context["run_id"]: raise ValueError("candidate run id invalid")
    if run_context["execution_mode"]=="synthetic":
        if run_context["authorization_id"] is not None or run_context["authorization_sha256"] is not None: raise ValueError("synthetic context authorization invalid")
    elif (type(run_context["authorization_id"]) is not str or not run_context["authorization_id"]
          or type(run_context["authorization_sha256"]) is not str
          or not re.fullmatch(r"[0-9a-f]{64}",run_context["authorization_sha256"])):
        raise ValueError("real-run authorization record missing")
    if not isinstance(recon,dict) or set(recon)!=RECON_EVIDENCE_KEYS or recon.get("evidence_schema")!="B2B3_RECONSTRUCTION_EVIDENCE_V1": raise ValueError("reconstruction evidence missing or malformed")
    if recon["candidate_sha256"]!=candidate_hash or recon["operator_id"]!=operator: raise ValueError("reconstruction evidence candidate/operator mismatch")
    if type(recon["reviewer_id"]) is not str or not recon["reviewer_id"].strip() or recon["reviewer_id"]==operator: raise ValueError("independent reviewer identity invalid")
    if type(recon["reviewer_code_sha256"]) is not str or not re.fullmatch(r"[0-9a-f]{64}",recon["reviewer_code_sha256"]): raise ValueError("independent implementation hash invalid")
    if recon["reviewer_code_sha256"]==candidate_payload["metadata"]["producer_sha256"]: raise ValueError("reconstruction implementation is not independent")
    _utc_timestamp(recon["reviewed_at_utc"])
    sections=recon["reconstructed_sections"]
    if not isinstance(sections,dict) or set(sections)!=set(RECON_SECTIONS): raise ValueError("reconstruction sections incomplete")
    expected={key:candidate_payload[key] for key in RECON_SECTIONS}
    if _canonical_json(sections)!=_canonical_json(expected): raise ValueError("independent reconstruction mismatch")
    expected_reference={"population_sizes":{"left_censored":4239,"proxy_1":1613,"proxy_2":1602,"proxy_3":1601},"h90_mature_first_observed_customers":{"left_censored":4239,"proxy_1":1017,"proxy_2":1008,"proxy_3":1008}}
    if _canonical_json(recon["b2b2_structural_reference"])!=_canonical_json(expected_reference): raise ValueError("independent B2B-2 structural regression mismatch")
    if not isinstance(privacy,dict) or set(privacy)!=PRIVACY_EVIDENCE_KEYS or privacy.get("evidence_schema")!="B2B3_PRIVACY_REVIEW_V1": raise ValueError("privacy/transcript review evidence missing or malformed")
    if privacy["candidate_sha256"]!=candidate_hash or privacy["operator_id"]!=operator: raise ValueError("privacy review candidate/operator mismatch")
    if type(privacy["reviewer_id"]) is not str or not privacy["reviewer_id"].strip() or privacy["reviewer_id"]==operator: raise ValueError("privacy reviewer identity invalid")
    _utc_timestamp(privacy["reviewed_at_utc"])
    if any(privacy[k] is not True for k in ("aggregate_only_confirmed","generated_logs_reviewed","agent_transcripts_reviewed","no_customer_level_exposure_found")): raise ValueError("human privacy/transcript review incomplete")
    _validate_generated_logs(log_bytes)
    if (type(privacy["generated_logs_sha256"]) is not str
        or not re.fullmatch(r"[0-9a-f]{64}",privacy["generated_logs_sha256"])
        or privacy["generated_logs_sha256"]!=hashlib.sha256(log_bytes).hexdigest()):
        raise ValueError("reviewed log hash mismatch")
    return True


def finalize_candidate(candidate_path, reconstruction_path, privacy_path):
    candidate_path=Path(candidate_path)
    if candidate_path.name!="candidate.json": raise ValueError("candidate path invalid")
    run_dir=candidate_path.parent
    if Path(reconstruction_path).parent.resolve()!=run_dir.resolve() or Path(reconstruction_path).name!="reconstruction.json": raise ValueError("reconstruction evidence path invalid")
    if Path(privacy_path).parent.resolve()!=run_dir.resolve() or Path(privacy_path).name!="privacy_review.json": raise ValueError("privacy evidence path invalid")
    root=next((p for p in (PRIVATE_SYNTHETIC_ROOT,PRIVATE_REAL_ROOT) if p.resolve() in run_dir.resolve().parents),None)
    if root is None: raise ValueError("candidate is outside approved private output roots")
    _check_private_file(candidate_path)
    candidate_bytes=candidate_path.read_bytes(); candidate=load_candidate_bytes(candidate_bytes)
    context=_load_private_json(run_dir/"run_context.json",root)
    expected_mode="synthetic" if root==PRIVATE_SYNTHETIC_ROOT else "real"
    if context.get("run_id")!=run_dir.name or context.get("execution_mode")!=expected_mode: raise ValueError("candidate run context path mismatch")
    log_path=run_dir/"operation.log"; _check_private_file(log_path); logs=log_path.read_bytes()
    recon=_load_private_json(reconstruction_path,root)
    privacy=_load_private_json(privacy_path,root)
    _verify_evidence(candidate,candidate_bytes,context,recon,privacy,logs)
    candidate_status={row["check_id"]:row["passed"] for row in candidate["integrity"]}
    required_auto=set(AUTO_CHECK_IDS)|{"b2b2_structural_regression"}
    if not all(candidate_status[k] for k in required_auto): raise ValueError("candidate automated integrity checks incomplete")
    final=dict(candidate)
    final_status=dict(candidate_status)
    final_status["independent_reconstruction"]=True
    final_status["privacy_transcript_audit"]=True
    final["integrity"]=_integrity(final_status)
    _validate_payload(final,require_pass=True,candidate=False)
    final_bytes=_canonical_json(final)
    _atomic_private_write(run_dir/"final.json",final_bytes,root)
    return run_dir/"final.json"


def _validate_auth_file(path):
    record=_parse_json_bytes(Path(path).read_bytes())
    if not _valid_authorization_record(record): raise ValueError("owner authorization record invalid or expired")
    return record


def real_data_execution_enabled(authorization=None):
    return (REAL_DATA_EXECUTION_ENABLED is False
            and os.environ.get("B2B3_REAL_DATA_AUTHORIZED") == "1"
            and _valid_authorization_record(authorization))


def main(argv=None):
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode",choices=("synthetic-tests","candidate-real","finalize-real"),required=True)
    parser.add_argument("--authorization-file")
    parser.add_argument("--operator-id")
    parser.add_argument("--run-id")
    args=parser.parse_args(argv)
    if args.mode=="synthetic-tests":
        import unittest
        suite=unittest.defaultTestLoader.discover(str(HERE),pattern="test_COMMERCIAL_DS_003_STAGE_B2B3.py")
        result=unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1
    try:
        run_id=_safe_run_id(args.run_id)
        if args.mode=="candidate-real":
            if not args.authorization_file or not args.operator_id: raise ValueError("required authorization arguments missing")
            authorization=_validate_auth_file(args.authorization_file)
            if not real_data_execution_enabled(authorization): raise ValueError("real-data authorization gate is closed")
            candidate=build_from_validated_source(authorization)
            write_candidate(candidate,run_id,args.operator_id,synthetic=False,authorization=authorization)
            print("B2B3 candidate generated")
            return 0
        if args.mode=="finalize-real":
            run_dir=PRIVATE_REAL_ROOT/run_id
            finalize_candidate(run_dir/"candidate.json",run_dir/"reconstruction.json",run_dir/"privacy_review.json")
            print("B2B3 final artifact written")
            return 0
    except Exception:
        print("B2B3 operation failed",file=sys.stderr)
        return 2
    return 2

if __name__=="__main__": raise SystemExit(main())
