#!/usr/bin/env python3
"""Extract *candidates* for fixed Old-Calendar commemorations from R64 harvest.

Only pages that explicitly present an old-calendar/"شرقي" date next to a
commemoration are eligible.  This is intentionally conservative.  Candidates
are not promoted into the app merely because a saint name appears in a title.
"""
from __future__ import annotations
import argparse, json, re
from collections import defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
HARVEST=ROOT/'canonical/r64_official_source_harvest.json'
OUT=ROOT/'canonical/r64_commemoration_candidates.json'
AR_MONTHS={
 'كانون الثاني':1,'شباط':2,'آذار':3,'اذار':3,'نيسان':4,'أيار':5,'ايار':5,'حزيران':6,
 'تموز':7,'آب':8,'اب':8,'أيلول':9,'ايلول':9,'تشرين الأول':10,'تشرين الاول':10,'تشرين الثاني':11,'كانون الأول':12,'كانون الاول':12,
}
MONTH_RE='|'.join(sorted(map(re.escape,AR_MONTHS),key=len,reverse=True))
OLD_DATE=re.compile(rf'(?:شرقي|التقويم\s+الشرقي|قديم)[^\n]{{0,45}}?(?P<day>\d{{1,2}})\s+(?P<month>{MONTH_RE})(?:\s+(?P<year>\d{{4}}))?',re.I)
# Also catches the common "غربي ... | شرقي 18 تموز" layout.
OLD_DATE_AFTER=re.compile(rf'(?P<day>\d{{1,2}})\s+(?P<month>{MONTH_RE})(?:\s+(?P<year>\d{{4}}))?\s*(?:شرقي|حسب\s+التقويم\s+القديم)',re.I)
COMM=re.compile(r'(?:تذكار\s*:?|سنكسار\s*:?)(?P<title>[^\n]{5,900})',re.I)

def compact(v): return re.sub(r'\s+',' ',str(v or '')).strip(' :-|')

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--require-harvest',action='store_true'); a=ap.parse_args()
 if not HARVEST.is_file():
  if a.require_harvest: raise SystemExit('R64_COMMEMORATION_EXTRACT_FAIL harvest missing')
  print('R64_COMMEMORATION_EXTRACT_SOURCE_MODE harvest_not_present'); return
 h=json.loads(HARVEST.read_text(encoding='utf-8')); slots=defaultdict(list)
 for doc in h.get('documents') or []:
  cats=set(doc.get('categories') or [])
  if not cats.intersection({'daily','calendar','commemorations'}): continue
  text=compact((doc.get('title') or '')+'\n'+(doc.get('excerpt') or ''))
  dates=list(OLD_DATE.finditer(text))+list(OLD_DATE_AFTER.finditer(text))
  if not dates: continue
  comms=list(COMM.finditer(text))
  for dm in dates:
   day=int(dm.group('day')); month=AR_MONTHS[dm.group('month')]
   if not (1<=day<=31): continue
   # Pick the nearest explicit commemoration text. Never use a generic page title alone.
   title=''
   if comms:
    cm=min(comms,key=lambda m:abs(m.start()-dm.start()))
    title=compact(cm.group('title'))
   if len(title)<5: continue
   # Trim obvious next-section headings in compact excerpts.
   title=re.split(r'\b(?:اية اليوم|آية اليوم|رسالة اليوم|انجيل اليوم|إنجيل اليوم|مزمور اليوم|التاريخ)\s*:',title,maxsplit=1)[0].strip()
   key=f'{month:02d}-{day:02d}'
   slots[key].append({'language':'ar','title':title[:700],'url':doc.get('url'),'sha256':doc.get('sha256'),'evidence':'explicit_old_calendar_date_near_explicit_commemoration_heading'})
 out={'schema_version':1,'promotion_policy':'candidate_only; tri-language native evidence + same old-calendar MM-DD required before promotion','machine_translation_allowed':False,'slots':{}}
 for key,items in sorted(slots.items()):
  uniq=[]; seen=set()
  for x in items:
   sig=(x['title'],x['url'])
   if sig not in seen: seen.add(sig); uniq.append(x)
  titles={x['title'] for x in uniq}
  out['slots'][key]={'candidate_count':len(uniq),'conflict':len(titles)>1,'candidates':uniq}
 out['coverage']={'old_calendar_slots_with_arabic_candidate':len(out['slots']),'conflicting_slots':sum(1 for x in out['slots'].values() if x['conflict'])}
 OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print('R64_COMMEMORATION_CANDIDATES_OK ' + ' '.join(f'{k}={v}' for k,v in out['coverage'].items()))
if __name__=='__main__': main()
