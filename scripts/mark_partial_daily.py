#!/usr/bin/env python3
import argparse, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = [ROOT/'data/calendar/today.json']

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--date', required=True)
    ap.add_argument('--mode', choices=['full','partial'], required=True)
    a=ap.parse_args()
    for path in FILES:
        data=json.loads(path.read_text(encoding='utf-8'))
        pub=data.setdefault('publication',{})
        pub['daily_availability']='FULL' if a.mode=='full' else 'PARTIAL_VERIFIED'
        pub['date_published']=a.date
        pub['usable_when_partial']=True
        pub['partial_policy']='publish_verified_sections_and_references; leave_only_unverified_exact_text_empty'
        data['daily_update_status']={
            'mode': a.mode,
            'date': a.date,
            'message': {
                'ar': 'بيانات اليوم متاحة؛ قد تبقى بعض النصوص غير المنشورة فارغة حتى ورودها من مصدر رسمي مطابق.',
                'en': 'Today data is available; unavailable exact texts remain empty until a matching official source is available.',
                'el': 'Τὰ σημερινὰ δεδομένα εἶναι διαθέσιμα· τὰ μὴ ἐπαληθευμένα κείμενα παραμένουν κενά.'
            }
        }
        path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        dated=ROOT/'data/calendar'/f'{a.date}.json'
        dated.write_text(path.read_text(encoding='utf-8'),encoding='utf-8')

if __name__=='__main__': main()
