#!/usr/bin/env python3
import argparse, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def fail(msg): raise SystemExit(msg)
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--expected-date',required=True); a=ap.parse_args()
    p=json.loads((ROOT/'data/calendar/today.json').read_text(encoding='utf-8'))
    if p.get('date_iso') != a.expected_date: fail('daily date mismatch')
    if p.get('machine_translation_used') is not False: fail('machine translation flag invalid')
    if p.get('translation_fallback_policy') != 'DISABLED_NO_CROSS_LANGUAGE_FALLBACK': fail('cross-language fallback enabled')
    services=p.get('services')
    if not isinstance(services,list) or len(services)<7: fail('daily services missing')
    readings=p.get('readings')
    if not isinstance(readings,list): fail('readings missing')
    kinds={r.get('kind') for r in readings if isinstance(r,dict)}
    if not {'epistle','gospel'}.issubset(kinds): fail('epistle or gospel reference missing')
    for r in readings:
        if not isinstance(r,dict): continue
        if r.get('kind') not in {'epistle','gospel','prokeimenon'}: continue
        if r.get('translation_locked') is not True: fail('reading not translation locked')
        bodies=r.get('body') or {}
        evidence=r.get('native_source_verification') or {}
        for lang in ('ar','en','el'):
            text=str(bodies.get(lang,'')).strip()
            if text:
                ev=evidence.get(lang) or {}
                if ev.get('status') not in {'VERIFIED_EXACT_NATIVE_SOURCE','IMPORTED_EXACT_OFFICIAL_NATIVE_CORPUS'}:
                    fail(f'unverified published text: {r.get("kind")}/{lang}')
    status=(p.get('publication') or {}).get('daily_availability')
    if status not in {'FULL','PARTIAL_VERIFIED'}: fail('daily availability status missing')
    print(f'Useful signed daily data validated for {a.expected_date}: {status}')
if __name__=='__main__': main()
