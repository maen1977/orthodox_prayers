#!/usr/bin/env python3
"""Validate phase-ten interpretation removal and expanded dated coverage."""
from __future__ import annotations
import argparse, importlib.util, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; CONTRACT=ROOT/"canonical/liturgy_phase10_completion_contract.json"; AUDIT=ROOT/"R21_PHASE10_YEAR_AUDIT_2026.json"
FORBIDDEN=[ROOT/"canonical/patristic_commentary_registry.json",ROOT/"canonical/patristic_commentary_sources.json",ROOT/"scripts/patristic_commentary.py",ROOT/"scripts/import_patristic_commentary.py",ROOT/"scripts/validate_patristic_commentary.py",ROOT/"R21_PHASE9_CANDIDATE_2026-07-26.json",ROOT/"R21_PHASE9_PATRISTIC_VALIDATION.json"]
def load(name,rel):
 p=ROOT/rel; spec=importlib.util.spec_from_file_location(name,p); m=importlib.util.module_from_spec(spec); assert spec and spec.loader; sys.modules[name]=m; spec.loader.exec_module(m); return m
def build_report():
 c=json.loads(CONTRACT.read_text(encoding="utf-8")); phase8=load("p10_phase8","scripts/validate_liturgy_phase8_completion.py").build_report(); blockers=[f"phase8:{x}" for x in phase8.get("blockers") or []]
 leftovers=[str(p.relative_to(ROOT)) for p in FORBIDDEN if p.exists()]
 active=[ROOT/"scripts/update_liturgical_data.py",ROOT/"scripts/build_native_service_packs.py",ROOT/"canonical/follow_along_liturgy_contract.json"]+list((ROOT/"data/services/native").glob("library_*.json"))+list((ROOT/"app/src/main/assets/data/native").glob("library_*.json"))
 tokens=[]
 for p in active:
  s=p.read_text(encoding="utf-8").lower()
  if "gospel_commentary" in s or "patristic_commentary" in s: tokens.append(str(p.relative_to(ROOT)))
 if leftovers or tokens: blockers.append("phase10_interpretation_subsystem_not_fully_removed")
 audit=json.loads(AUDIT.read_text(encoding="utf-8")) if AUDIT.is_file() else None
 if not audit: blockers.append("phase10_year_audit_missing")
 else:
  if int(audit.get("audited_days") or 0)!=int(c["year_audit"]["expected_days"]): blockers.append("phase10_year_audit_day_integrity_failed")
  if audit.get("network_fetch_used"): blockers.append("phase10_year_audit_used_network")
  if not audit.get("annual_complete"): blockers.append("phase10_annual_daily_coverage_incomplete")
  day=next((x for x in audit.get("days") or [] if x.get("date")=="2026-07-19"),{})
  if not day.get("complete_for_release"): blockers.append("phase10_reference_sunday_2026_07_19_incomplete")
 return {"phase":"R21_PHASE10","pipeline_status":c.get("status"),"complete_release_allowed":not blockers,"interpretations_removed":not leftovers and not tokens,"interpretation_leftover_files":leftovers,"interpretation_active_token_files":tokens,"year_audit_present":bool(audit),"year_audit_days":int((audit or {}).get("audited_days") or 0),"year_audit_complete_days":int((audit or {}).get("complete_days") or 0),"year_audit_incomplete_days":int((audit or {}).get("incomplete_days") or 0),"reference_sunday_complete":bool(next((x for x in (audit or {}).get("days") or [] if x.get("date")=="2026-07-19"),{}).get("complete_for_release")),"blockers":blockers,"fail_closed":True}
def main():
 ap=argparse.ArgumentParser(); ap.add_argument("--require-complete",action="store_true"); ap.add_argument("--json-output",type=Path); a=ap.parse_args(); r=build_report();
 if a.json_output: a.json_output.write_text(json.dumps(r,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 if a.require_complete and not r["complete_release_allowed"]: raise SystemExit("PHASE10_COMPLETE_RELEASE_BLOCKED "+",".join(r["blockers"]))
 print(f"PHASE10_GATE_OK complete={str(r['complete_release_allowed']).lower()} interpretations_removed={str(r['interpretations_removed']).lower()} complete_days={r['year_audit_complete_days']} blockers={len(r['blockers'])} fail_closed=true")
if __name__=="__main__": main()
