#!/usr/bin/env python3
"""Collect short daily commemorations from the Jordan/Jerusalem official sites.

Facts only: short names, civil/old-style date evidence, URLs, retrieval time and
SHA-256. Long articles, images and Synaxarion prose are never copied. Publication
is fail-closed and preserves the last verified local record during outages.
"""
from __future__ import annotations
import argparse, hashlib, json, re, urllib.parse, urllib.request
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'canonical/local_commemorations.json'
UA='ChurchPrayersLocalCalendar/5.5.1 (+https://github.com/maen1977/orthodox_prayers)'
JORDAN='https://orthodoxjordan.org/%D8%B5%D9%84%D8%A7%D8%A9-%D8%A7%D9%84%D9%8A%D9%88%D9%85/'
JERUSALEM_SEARCH='https://en.jerusalem-patriarchate.info/wp-json/wp/v2/search'

class Text(HTMLParser):
    def __init__(self): super().__init__(convert_charrefs=True); self.parts=[]; self.skip=0
    def handle_starttag(self,t,a):
        if t in {'script','style','noscript','svg'}: self.skip+=1
        elif not self.skip and t in {'p','div','br','li','h1','h2','h3','h4'}: self.parts.append('\n')
    def handle_endtag(self,t):
        if t in {'script','style','noscript','svg'} and self.skip: self.skip-=1
    def handle_data(self,d):
        if not self.skip: self.parts.append(d)
    def text(self): return re.sub(r'[ \t]+',' ',re.sub(r'\n\s*\n+','\n',' '.join(self.parts))).strip()

def fetch(url,max_bytes=2_000_000):
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept-Language':'ar,en;q=0.8'})
    with urllib.request.urlopen(req,timeout=25) as r:
        data=r.read(max_bytes+1)
        if len(data)>max_bytes: raise ValueError('response_too_large')
        return data,r.geturl()

def old_style(day): return day-timedelta(days=13)
def date_proven(text, day):
    old=old_style(day)
    normalized=text.translate(str.maketrans('٠١٢٣٤٥٦٧٨٩','0123456789'))
    tokens={day.isoformat(),f'{day.day}/{day.month}/{day.year}',f'{day.day:02d}/{day.month:02d}/{day.year}',
            old.isoformat(),f'{old.day}/{old.month}/{old.year}',f'{old.day:02d}/{old.month:02d}/{old.year}'}
    return any(t in normalized for t in tokens)

def short_arabic_commemorations(text):
    candidates=[]
    patterns=[r'(?:تذكار(?:ات)? اليوم|تذكار|القديسون|القديسين)\s*[:：-]?\s*([^\n]{4,280})',
              r'(?:عيد|ذكرى)\s+([^\n]{4,220})']
    for pat in patterns:
        for m in re.finditer(pat,text,re.I):
            value=re.sub(r'\s+',' ',m.group(1)).strip(' .،؛:-')
            if value and not any(x in value for x in ('المزيد','اقرأ','الرئيسية')) and value not in candidates:
                candidates.append(value)
    return candidates[:4]

def jordan_observation(day):
    raw,url=fetch(JORDAN)
    parser=Text(); parser.feed(raw.decode('utf-8','replace')); text=parser.text()
    names=short_arabic_commemorations(text)
    proven=date_proven(text,day)
    return {'url':url,'sha256':hashlib.sha256(raw).hexdigest(),'date_proven':proven,'names':names}

def jerusalem_confirmation(day):
    old=old_style(day)
    query=f'{old.day} {day.day} {day.year}'
    url=JERUSALEM_SEARCH+'?'+urllib.parse.urlencode({'search':query,'per_page':10})
    raw,final=fetch(url,1_000_000)
    rows=json.loads(raw.decode('utf-8'))
    titles=[re.sub(r'<[^>]+>','',str(x.get('title') or '')).strip() for x in rows if isinstance(x,dict)]
    return {'url':final,'sha256':hashlib.sha256(raw).hexdigest(),'matched':bool(titles),'titles':titles[:3]}

def load_previous():
    try: return json.loads(OUT.read_text(encoding='utf-8'))
    except Exception: return {'records':{}}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--start-date',required=True); ap.add_argument('--days',type=int,default=9); ap.add_argument('--offline',action='store_true'); args=ap.parse_args()
    start=date.fromisoformat(args.start_date); previous=load_previous(); old_records=previous.get('records') or {}; records={}
    checked=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
    for offset in range(args.days):
        day=start+timedelta(days=offset); key=day.isoformat(); prior=old_records.get(key)
        if args.offline:
            if isinstance(prior,dict) and prior.get('verification_status') in {'LOCAL_OFFICIAL_SOURCE_VERIFIED','LAST_VERIFIED_LOCAL_RECORD'}:
                prior=dict(prior); prior['verification_status']='LAST_VERIFIED_LOCAL_RECORD'; records[key]=prior
            continue
        try: jordan=jordan_observation(day)
        except Exception as e: jordan={'error':type(e).__name__}
        try: jerusalem=jerusalem_confirmation(day)
        except Exception as e: jerusalem={'error':type(e).__name__}
        if jordan.get('date_proven') and jordan.get('names'):
            ar='؛ '.join(jordan['names'])
            records[key]={
              'civil_date':key,'church_date':old_style(day).isoformat(),'calendar_style':'julian_old_calendar',
              'jurisdiction':'jerusalem_jordan','commemorations':{'ar':ar,'en':ar,'el':ar},
              'verification_status':'LOCAL_OFFICIAL_SOURCE_VERIFIED','retrieved_at_utc':checked,
              'sources':[{'authority':'Orthodox Jordan','url':jordan['url'],'sha256':jordan['sha256'],'role':'local_primary'},
                         {'authority':'Jerusalem Patriarchate','url':jerusalem.get('url',''),'sha256':jerusalem.get('sha256',''),'role':'jurisdiction_confirmation','matched':bool(jerusalem.get('matched'))}]
            }
        elif isinstance(prior,dict) and prior.get('verification_status') in {'LOCAL_OFFICIAL_SOURCE_VERIFIED','LAST_VERIFIED_LOCAL_RECORD'}:
            prior=dict(prior); prior['verification_status']='LAST_VERIFIED_LOCAL_RECORD'; records[key]=prior
        print(f"LOCAL_COMMEMORATION date={key} jordan={'verified' if key in records and records[key]['verification_status']=='LOCAL_OFFICIAL_SOURCE_VERIFIED' else 'unavailable'} jerusalem={'matched' if jerusalem.get('matched') else 'unavailable'}")
    payload={'schema_version':1,'generated_at_utc':checked,'jurisdiction':'Greek Orthodox Patriarchate of Jerusalem — Jordan priority',
             'rights_policy':'short factual metadata and official links only; no long Synaxarion prose or images copied',
             'records':records}
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'LOCAL_COMMEMORATIONS_OK start={start.isoformat()} days={args.days} verified={len(records)}')
if __name__=='__main__': main()
