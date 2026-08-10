#!/usr/bin/env python3
"""Reduce unresolved 2026-2050 named commemorations to 366 Old-Calendar source slots."""
from __future__ import annotations
import json
from collections import defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CAL=ROOT/'canonical/internal_calendar_2026_2050.json'
OUT=ROOT/'canonical/jordan_jerusalem_commemoration_acquisition_queue.json'

def main():
    payload=json.loads(CAL.read_text(encoding='utf-8'))
    unresolved=defaultdict(list)
    for day in payload.get('days') or []:
        comm=day.get('commemoration') or {}
        if comm.get('source_kind')!='old_calendar_date_baseline': continue
        jul=str(day.get('julian_date') or '')
        if len(jul)>=10: unresolved[jul[5:10]].append(day['date_iso'])
    # Include every possible old-calendar day so Feb 29 can be verified once and reused.
    from datetime import date,timedelta
    slots=[]; cursor=date(2028,1,1); end=date(2028,12,31) # leap year gives all 366 month/day slots
    while cursor<=end:
        key=cursor.strftime('%m-%d'); civil=unresolved.get(key,[])
        slots.append({
          'old_calendar_month_day':key,
          'status':'PENDING_NATIVE_JORDAN_JERUSALEM_SHORT_METADATA' if civil else 'NO_UNRESOLVED_CIVIL_DAYS_IN_CURRENT_HORIZON',
          'unresolved_civil_day_count':len(civil),
          'sample_civil_dates':civil[:3],
          'promotion_contract':{
            'arabic':'native short commemoration title from Orthodox Jordan / Jerusalem Patriarchate source',
            'english':'independent native English ecclesiastical title; no machine translation from Arabic',
            'greek':'native Greek ecclesiastical title; no machine translation from Arabic/English',
            'jurisdiction':'Jerusalem/Jordan old-calendar fixed commemoration must match this MM-DD',
            'long_synaxarion_prose_copied':False,
          },
          'preferred_sources':[
            {'id':'orthodox_jordan_daily','url':'https://orthodoxjordan.org/','role':'Jordan-priority Arabic daily commemoration and fasting/service evidence'},
            {'id':'jerusalem_patriarchate_ar','url':'https://ar.jerusalem-patriarchate.info/','role':'Jerusalem fixed-feast/date cross-check'},
            {'id':'jerusalem_patriarchate_en','url':'https://en.jerusalem-patriarchate.info/','role':'native English title when published'},
            {'id':'jerusalem_patriarchate_el','url':'https://jerusalem-patriarchate.info/','role':'native Greek title when published'},
          ],
        })
        cursor+=timedelta(days=1)
    out={
      'schema_version':1,
      'jurisdiction':'Greek Orthodox Patriarchate of Jerusalem — Jordan priority',
      'calendar':'Julian Old Calendar',
      'purpose':'Resolve fixed daily named commemorations once per Old-Calendar MM-DD, then map safely across 2026-2050.',
      'machine_translation_allowed':False,
      'long_prose_republication':False,
      'slot_count':len(slots),
      'unresolved_civil_days':sum(x['unresolved_civil_day_count'] for x in slots),
      'slots':slots,
    }
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'R63_COMMEMORATION_QUEUE_OK slots={len(slots)} unresolved_civil_days={out["unresolved_civil_days"]}')
if __name__=='__main__': main()
