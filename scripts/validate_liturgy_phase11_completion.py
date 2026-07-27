#!/usr/bin/env python3
"""Validate phase-eleven dated Sunday expansion while remaining fail-closed."""
from __future__ import annotations
import argparse, importlib.util, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CONTRACT=ROOT/"canonical/liturgy_phase11_completion_contract.json"
AUDIT=ROOT/"R21_PHASE11_YEAR_AUDIT_2026.json"
TARGET_DATES=("2026-07-05","2026-07-12")

def load(name,rel):
 p=ROOT/rel; spec=importlib.util.spec_from_file_location(name,p); m=importlib.util.module_from_spec(spec); assert spec and spec.loader; sys.modules[name]=m; spec.loader.exec_module(m); return m

def build_report():
 c=json.loads(CONTRACT.read_text(encoding="utf-8"))
 phase10=load("p11_phase10","scripts/validate_liturgy_phase10_completion.py").build_report()
 blockers=[f"phase10:{x}" for x in phase10.get("blockers") or [] if x != "phase10_annual_daily_coverage_incomplete"]
 audit=json.loads(AUDIT.read_text(encoding="utf-8")) if AUDIT.is_file() else None
 targets={d:False for d in TARGET_DATES}
 if not audit:
  blockers.append("phase11_year_audit_missing")
 else:
  if int(audit.get("audited_days") or 0)!=int(c["year_audit"]["expected_days"]): blockers.append("phase11_year_audit_day_integrity_failed")
  if audit.get("network_fetch_used"): blockers.append("phase11_year_audit_used_network")
  rows={str(x.get("date")):x for x in audit.get("days") or []}
  for d in TARGET_DATES:
   targets[d]=bool(rows.get(d,{}).get("complete_for_release"))
   if not targets[d]: blockers.append(f"phase11_target_date_incomplete:{d}")
  if int(audit.get("complete_days") or 0)<int(c["year_audit"]["minimum_complete_days"]): blockers.append("phase11_complete_day_target_not_met")
  if not audit.get("annual_complete"): blockers.append("phase11_annual_daily_coverage_incomplete")
 active=[ROOT/"scripts/update_liturgical_data.py",ROOT/"canonical/follow_along_liturgy_contract.json"]+list((ROOT/"data/services/native").glob("library_*.json"))+list((ROOT/"app/src/main/assets/data/native").glob("library_*.json"))
 token_files=[]
 for p in active:
  text=p.read_text(encoding="utf-8").lower()
  if "gospel_commentary" in text or "patristic_commentary" in text: token_files.append(str(p.relative_to(ROOT)))
 if token_files: blockers.append("phase11_interpretation_tokens_reintroduced")
 return {
  "phase":"R21_PHASE11","pipeline_status":c.get("status"),"complete_release_allowed":not blockers,
  "interpretations_removed":not token_files,"interpretation_token_files":token_files,
  "year_audit_present":bool(audit),"year_audit_days":int((audit or {}).get("audited_days") or 0),
  "year_audit_complete_days":int((audit or {}).get("complete_days") or 0),"year_audit_incomplete_days":int((audit or {}).get("incomplete_days") or 0),
  "target_dates_complete":targets,"blockers":blockers,"fail_closed":True
 }

def main():
 ap=argparse.ArgumentParser(); ap.add_argument("--require-complete",action="store_true"); ap.add_argument("--json-output",type=Path); a=ap.parse_args(); r=build_report()
 if a.json_output: a.json_output.write_text(json.dumps(r,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 if a.require_complete and not r["complete_release_allowed"]: raise SystemExit("PHASE11_COMPLETE_RELEASE_BLOCKED "+",".join(r["blockers"]))
 print(f"PHASE11_GATE_OK complete={str(r['complete_release_allowed']).lower()} complete_days={r['year_audit_complete_days']} targets={sum(r['target_dates_complete'].values())}/{len(TARGET_DATES)} blockers={len(r['blockers'])} fail_closed=true")
if __name__=="__main__": main()
