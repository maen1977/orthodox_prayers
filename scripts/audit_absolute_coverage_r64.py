#!/usr/bin/env python3
"""Absolute 2026-2050 coverage gate for R64.

Source archives can be audited without the network-derived R63/R64 artifacts.
GitHub invokes --require-complete after harvesting/bootstrap/rebuild.  In strict
mode every civil date must be structurally present, have a resolved reading-day
state, complete fasting metadata, a selected service, and a non-empty three-
language commemoration.  --require-named-commemorations additionally rejects the
safe Old-Calendar-date generic label so a green build truly means named daily
commemorations were sourced for the entire horizon.
"""
from __future__ import annotations
import argparse, json
from datetime import date, timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CAL=ROOT/'canonical/internal_calendar_2026_2050.json'
BASE=ROOT/'canonical/perpetual_lectionary_2026_2050.json'
HARVEST=ROOT/'canonical/r64_official_source_harvest.json'
CANDIDATES=ROOT/'canonical/r64_commemoration_candidates.json'
NETWORK=ROOT/'canonical/r64_official_source_network.json'
OUT=ROOT/'canonical/r64_absolute_coverage_audit.json'
START=date(2026,1,1); END=date(2050,12,31); EXPECTED=9131
LANGS=('ar','en','el')

def load(p): return json.loads(p.read_text(encoding='utf-8'))
def filled_langs(obj): return isinstance(obj,dict) and all(str(obj.get(x) or '').strip() for x in LANGS)

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--require-complete',action='store_true'); ap.add_argument('--require-named-commemorations',action='store_true'); a=ap.parse_args()
 cal=load(CAL); days=cal.get('days') or []; by={str(d.get('date_iso') or ''):d for d in days}
 expected=[]; cur=START
 while cur<=END: expected.append(cur.isoformat()); cur+=timedelta(days=1)
 errors=[]; missing_dates=[x for x in expected if x not in by]; extra_dates=sorted(set(by)-set(expected))
 if len(days)!=EXPECTED or len(by)!=EXPECTED or missing_dates or extra_dates: errors.append('calendar civil horizon is not exactly 9131 unique days')
 problems={'reading_unresolved':[],'fasting_incomplete':[],'service_incomplete':[],'commemoration_incomplete':[],'generic_commemoration':[]}
 for iso in expected:
  d=by.get(iso)
  if not d: continue
  rr=d.get('reading_day_resolution') or {}
  if str(rr.get('status') or '') in {'','UNRESOLVED'}: problems['reading_unresolved'].append(iso)
  f=d.get('fasting') or {}
  if not str(f.get('code') or '').strip() or not filled_langs(f.get('title')) or not filled_langs(f.get('detail')): problems['fasting_incomplete'].append(iso)
  s=d.get('liturgy_service_selection') or {}
  if not str(s.get('service_type') or '').strip() or not str(s.get('rule_id') or '').strip() or not filled_langs(s.get('label')): problems['service_incomplete'].append(iso)
  c=d.get('commemoration') or {}
  if not filled_langs(c.get('name')): problems['commemoration_incomplete'].append(iso)
  if c.get('source_kind') in {'old_calendar_date_baseline','comparative_english_lane','mixed_native_and_comparative_lanes'}:
   problems['generic_commemoration'].append(iso)
 baseline={}
 if BASE.is_file(): baseline=load(BASE)
 harvest={}
 if HARVEST.is_file(): harvest=load(HARVEST)
 candidates={}
 if CANDIDATES.is_file(): candidates=load(CANDIDATES)
 network={}
 if NETWORK.is_file(): network=load(NETWORK)
 direct_documents=network.get('direct_documents') or []
 report={
  'schema_version':1,'civil_range':{'start':START.isoformat(),'end':END.isoformat(),'expected_days':EXPECTED,'actual_days':len(by)},
  'strict_flags':{'require_complete':a.require_complete,'require_named_commemorations':a.require_named_commemorations},
  'coverage':{
   'calendar_days':len(by),
   'reading_resolved_days':EXPECTED-len(problems['reading_unresolved']),
   'fasting_complete_days':EXPECTED-len(problems['fasting_incomplete']),
   'service_selected_days':EXPECTED-len(problems['service_incomplete']),
   'commemoration_display_complete_days':EXPECTED-len(problems['commemoration_incomplete']),
   'named_commemoration_days':EXPECTED-len(problems['generic_commemoration']),
   'generic_commemoration_days':len(problems['generic_commemoration']),
   'perpetual_baseline_dates':len((baseline.get('dates') or {})) if baseline else 0,
   'official_harvest_documents':int((harvest.get('coverage') or {}).get('documents') or 0) if harvest else 0,
   'official_direct_documents_configured':len(direct_documents),
   'official_direct_document_ids':[str(x.get('id') or '') for x in direct_documents if str(x.get('id') or '').strip()],
   'old_calendar_slots_with_arabic_candidate':int((candidates.get('coverage') or {}).get('old_calendar_slots_with_arabic_candidate') or 0) if candidates else 0,
  },
  'commemoration_policy':{
   'required_native_languages':list(LANGS),
   'generic_old_calendar_date_label_is_not_named':True,
   'status':'INCOMPLETE' if problems['generic_commemoration'] else 'COMPLETE',
     'note':'Comparative native-English evidence may be displayed in the English lane but never satisfies the Jerusalem/Jordan local-language named gate; local Arabic, English, and Greek evidence are still required.'
,
  },
  'missing_dates':missing_dates,'extra_dates':extra_dates,
  'problem_counts':{k:len(v) for k,v in problems.items()},
  'problem_samples':{k:v[:50] for k,v in problems.items()},
 }
 OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 if a.require_complete:
  for key in ('reading_unresolved','fasting_incomplete','service_incomplete','commemoration_incomplete'):
   if problems[key]: errors.append(f'{key}={len(problems[key])}')
  if not BASE.is_file() or len((baseline.get('dates') or {}))!=EXPECTED: errors.append('perpetual baseline is not bootstrapped for all 9131 dates')
  if not HARVEST.is_file(): errors.append('official Jerusalem/Jordan network harvest is missing')
 if a.require_named_commemorations and problems['generic_commemoration']:
  errors.append(f'named commemoration coverage incomplete: generic={len(problems["generic_commemoration"])}')
 if errors:
  for e in errors: print('R64_ABSOLUTE_COVERAGE_FAIL',e)
  print('R64_ABSOLUTE_COVERAGE_REPORT',OUT.relative_to(ROOT))
  raise SystemExit(1)
 c=report['coverage']
 mode='STRICT' if a.require_complete else 'SOURCE'
 print(f"R64_ABSOLUTE_COVERAGE_OK mode={mode} calendar={c['calendar_days']}/{EXPECTED} readings={c['reading_resolved_days']}/{EXPECTED} fasting={c['fasting_complete_days']}/{EXPECTED} services={c['service_selected_days']}/{EXPECTED} commemoration_display={c['commemoration_display_complete_days']}/{EXPECTED} named={c['named_commemoration_days']}/{EXPECTED} generic={c['generic_commemoration_days']}")
if __name__=='__main__': main()
