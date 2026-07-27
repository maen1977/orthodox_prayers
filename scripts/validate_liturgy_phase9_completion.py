#!/usr/bin/env python3
"""Validate phase-nine day-by-day coverage without interpretations."""
from __future__ import annotations
import argparse, importlib.util, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
YEAR_AUDIT=ROOT/"R21_PHASE9_YEAR_AUDIT_2026.json"
CONTRACT=ROOT/"canonical/liturgy_phase9_completion_contract.json"
def load_module(name,relative):
 p=ROOT/relative; spec=importlib.util.spec_from_file_location(name,p); m=importlib.util.module_from_spec(spec); assert spec and spec.loader; sys.modules[name]=m; spec.loader.exec_module(m); return m
def build_report():
 contract=json.loads(CONTRACT.read_text(encoding="utf-8")); phase8=load_module("phase9_phase8_gate","scripts/validate_liturgy_phase8_completion.py").build_report(); blockers=[f"phase8:{x}" for x in phase8.get("blockers") or []]
 year=json.loads(YEAR_AUDIT.read_text(encoding="utf-8")) if YEAR_AUDIT.is_file() else None; expected=int(contract["year_audit"]["expected_days"])
 if not year: blockers.append("phase9_year_audit_missing")
 else:
  days=year.get("days") if isinstance(year.get("days"),list) else []; dates=[str(x.get("date") or "") for x in days if isinstance(x,dict)]
  if len(days)!=expected or len(set(dates))!=expected: blockers.append("phase9_year_audit_day_integrity_failed")
  if year.get("network_fetch_used"): blockers.append("phase9_year_audit_used_network")
  if not year.get("annual_complete"): blockers.append("phase9_annual_daily_coverage_incomplete")
 return {"phase":"R21_PHASE9","pipeline_status":contract.get("status"),"complete_release_allowed":not blockers,"phase8_complete_release_allowed":bool(phase8.get("complete_release_allowed")),"year_audit_present":bool(year),"year_audit_days":int((year or {}).get("audited_days") or 0),"year_audit_complete_days":int((year or {}).get("complete_days") or 0),"year_audit_incomplete_days":int((year or {}).get("incomplete_days") or 0),"annual_daily_coverage_complete":bool((year or {}).get("annual_complete")),"interpretations_in_scope":False,"blockers":blockers,"fail_closed":True}
def main():
 ap=argparse.ArgumentParser(); ap.add_argument("--require-complete",action="store_true"); ap.add_argument("--json-output",type=Path); a=ap.parse_args(); r=build_report();
 if a.json_output: a.json_output.write_text(json.dumps(r,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 if a.require_complete and not r["complete_release_allowed"]: raise SystemExit("PHASE9_COMPLETE_RELEASE_BLOCKED "+",".join(r["blockers"]))
 print(f"PHASE9_DAILY_COVERAGE_GATE_OK complete={str(r['complete_release_allowed']).lower()} year_days={r['year_audit_days']} blockers={len(r['blockers'])} interpretations=false fail_closed=true")
if __name__=="__main__": main()
