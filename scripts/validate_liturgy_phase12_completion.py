#!/usr/bin/env python3
"""Validate phase-twelve dated Sunday expansion while remaining fail-closed."""
from __future__ import annotations
import argparse, importlib.util, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CONTRACT=ROOT/"canonical/liturgy_phase12_completion_contract.json"
AUDIT=ROOT/"R21_PHASE12_YEAR_AUDIT_2026.json"
TARGET_DATES=("2026-06-21","2026-06-28")

def load(name,rel):
 p=ROOT/rel; spec=importlib.util.spec_from_file_location(name,p); m=importlib.util.module_from_spec(spec); assert spec and spec.loader; sys.modules[name]=m; spec.loader.exec_module(m); return m

def build_report():
 c=json.loads(CONTRACT.read_text(encoding="utf-8"))
 phase11=load("p12_phase11","scripts/validate_liturgy_phase11_completion.py").build_report()
 blockers=[f"phase11:{x}" for x in phase11.get("blockers") or [] if x != "phase11_annual_daily_coverage_incomplete"]
 audit=json.loads(AUDIT.read_text(encoding="utf-8")) if AUDIT.is_file() else None
 targets={d:False for d in TARGET_DATES}
 if not audit:
  blockers.append("phase12_year_audit_missing")
 else:
  if str(audit.get("phase"))!="R21_PHASE12": blockers.append("phase12_year_audit_phase_mismatch")
  if int(audit.get("audited_days") or 0)!=int(c["year_audit"]["expected_days"]): blockers.append("phase12_year_audit_day_integrity_failed")
  if audit.get("network_fetch_used"): blockers.append("phase12_year_audit_used_network")
  rows={str(x.get("date")):x for x in audit.get("days") or []}
  for d in TARGET_DATES:
   targets[d]=bool(rows.get(d,{}).get("complete_for_release"))
   if not targets[d]: blockers.append(f"phase12_target_date_incomplete:{d}")
  if int(audit.get("complete_days") or 0)<int(c["year_audit"]["minimum_complete_days"]): blockers.append("phase12_complete_day_target_not_met")
  if not audit.get("annual_complete"): blockers.append("phase12_annual_daily_coverage_incomplete")
 active=[ROOT/"scripts/update_liturgical_data.py",ROOT/"canonical/follow_along_liturgy_contract.json"]+list((ROOT/"data/services/native").glob("library_*.json"))+list((ROOT/"app/src/main/assets/data/native").glob("library_*.json"))
 token_files=[]
 for p in active:
  text=p.read_text(encoding="utf-8").lower()
  if "gospel_commentary" in text or "patristic_commentary" in text: token_files.append(str(p.relative_to(ROOT)))
 if token_files: blockers.append("phase12_interpretation_tokens_reintroduced")
 return {
  "phase":"R21_PHASE12","pipeline_status":c.get("status"),"complete_release_allowed":not blockers,
  "interpretations_removed":not token_files,"interpretation_token_files":token_files,
  "year_audit_present":bool(audit),"year_audit_days":int((audit or {}).get("audited_days") or 0),
  "year_audit_complete_days":int((audit or {}).get("complete_days") or 0),"year_audit_incomplete_days":int((audit or {}).get("incomplete_days") or 0),
  "target_dates_complete":targets,"blockers":blockers,"fail_closed":True
 }

def main():
 ap=argparse.ArgumentParser(); ap.add_argument("--require-complete",action="store_true"); ap.add_argument("--json-output",type=Path); a=ap.parse_args(); r=build_report()
 if a.json_output: a.json_output.write_text(json.dumps(r,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 if a.require_complete and not r["complete_release_allowed"]: raise SystemExit("PHASE12_COMPLETE_RELEASE_BLOCKED "+",".join(r["blockers"]))
 print(f"PHASE12_GATE_OK complete={str(r['complete_release_allowed']).lower()} complete_days={r['year_audit_complete_days']} targets={sum(r['target_dates_complete'].values())}/{len(TARGET_DATES)} blockers={len(r['blockers'])} fail_closed=true")
if __name__=="__main__": main()
