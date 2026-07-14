#!/usr/bin/env python3
from __future__ import annotations
import json, os, sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo
from native_text_contract import ROOT, LANGUAGES, sha256_text
TZ=ZoneInfo('Asia/Amman')
BAD_MARKERS=['موضع قراءة','تُحدّث يومياً','Updated daily','must be fetched','Daily reading text was not returned','[فصل','[البروكيمنن]','[طروبارية','[القنداق]','[آية المناولة]','...']

def fail(msg):
    print(f'::error title=Daily data quality check failed::{msg}'); print(f'QUALITY CHECK FAILED: {msg}'); raise SystemExit(1)
def read_json(path):
    try: return json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc: fail(f'cannot read valid JSON from {path}: {exc}')
def expected_date(): return os.getenv('ORTHODOX_DATE','').strip() or datetime.now(TZ).strftime('%Y-%m-%d')
def text_of_loc(obj): return ' '.join(str((obj or {}).get(k,'')) for k in LANGUAGES) if isinstance(obj,dict) else ''

def check_synced(data,path,date_iso):
    canonical=ROOT/'data/calendar/today.json'
    if path.resolve()!=canonical.resolve(): return
    for other in (ROOT/f'data/calendar/{date_iso}.json',ROOT/'app/src/main/assets/data/today.json'):
        if not other.exists() or read_json(other)!=data: fail(f'{other.relative_to(ROOT)} is not synchronized')
    manifest=read_json(ROOT/'data/manifest.json')
    if not str(manifest.get('updated_at') or '').startswith(date_iso): fail('data manifest date mismatch')

def validate_reading(reading,pointer):
    if reading.get('translation_locked') is not True: fail(f'{pointer} is not locked')
    if (reading.get('integrity') or {}).get('status')!='NATIVE_LANGUAGE_LANES_ENFORCED': fail(f'{pointer} has old/invalid integrity mode')
    verification=reading.get('native_source_verification') or {}
    refs=reading.get('reference') or {}; bodies=reading.get('body') or {}
    for lang in LANGUAGES:
        evidence=verification.get(lang)
        if not isinstance(evidence,dict): fail(f'{pointer}.{lang} evidence missing')
        if evidence.get('ai_translation_used') is not False or evidence.get('automatic_diacritization_used') is not False: fail(f'{pointer}.{lang} forbidden transformation flag')
        text=str(bodies.get(lang) or '')
        ref=str(refs.get(lang) or '')
        if text:
            if evidence.get('status') not in {'VERIFIED_EXACT_NATIVE_SOURCE','IMPORTED_EXACT_OFFICIAL_NATIVE_CORPUS'}: fail(f'{pointer}.{lang} text is not exact native-source text')
            if evidence.get('text_sha256')!=sha256_text(text): fail(f'{pointer}.{lang} text hash mismatch')
        if ref and evidence.get('reference_available') is not True: fail(f'{pointer}.{lang} reference lacks provenance')
    combined=text_of_loc(refs)+' '+text_of_loc(bodies)
    for bad in BAD_MARKERS:
        if bad in combined: fail(f'{pointer} contains placeholder marker: {bad}')

def main():
    args=[a for a in sys.argv[1:] if a!='--allow-stale']
    allow_stale='--allow-stale' in sys.argv[1:]
    path=Path(args[0]) if args else ROOT/'data/calendar/today.json'
    if not path.is_absolute(): path=ROOT/path
    data=read_json(path)
    date_iso=str(data.get('date_iso') or '')
    if not allow_stale and date_iso!=expected_date(): fail(f'daily file date is {date_iso}, expected {expected_date()} in Asia/Amman')
    required=['schema_version','date_label','fast','fasting','readings','upcoming','next_sunday','recommended_services','services']
    for key in required:
        if key not in data: fail(f'missing {key}')
    if data.get('schema_version')!=9: fail('schema_version must be 9')
    if (data.get('integrity') or {}).get('status')!='VERIFIED_OFFICIAL_SOURCES': fail('top-level source integrity invalid')
    if data.get('language_content_mode')!='THREE_STRICTLY_INDEPENDENT_OFFICIAL_NATIVE_LANGUAGE_LANES': fail('strict independent language mode missing')
    if data.get('machine_translation_used') is not False or data.get('automatic_diacritization_used') is not False: fail('forbidden transformation flag')
    if data.get('translation_fallback_policy')!='DISABLED_NO_CROSS_LANGUAGE_FALLBACK': fail('cross-language fallback is enabled')
    lanes=data.get('language_sources') or {}
    for lang in LANGUAGES:
        if not isinstance(lanes.get(lang),dict) or lanes[lang].get('same_language_fallback_only') is not True: fail(f'{lang} source lane missing')
    if not str((data.get('date_label') or {}).get('ar') or '').strip(): fail('Arabic date UI label missing')
    if not str((data.get('fast') or {}).get('ar') or '').strip(): fail('Arabic fasting UI label missing')
    readings=data.get('readings') or []
    kinds={r.get('kind') for r in readings if isinstance(r,dict)}
    if not {'prokeimenon','epistle','gospel'}.issubset(kinds): fail('daily reading kinds incomplete')
    for i,reading in enumerate(readings):
        if not isinstance(reading,dict): fail(f'reading {i} invalid')
        if not str((reading.get('title') or {}).get('ar') or '').strip(): fail(f'reading {i} Arabic UI title missing')
        validate_reading(reading,f'readings[{i}]')
    next_readings=((data.get('integrity_inputs') or {}).get('next_sunday') or {}).get('readings')
    if not isinstance(next_readings,list): fail('next Sunday readings missing')
    for i,reading in enumerate(next_readings):
        if isinstance(reading,dict) and reading.get('kind') in {'prokeimenon','epistle','gospel'}: validate_reading(reading,f'next_sunday[{i}]')
    from validate_reader_services import compose_overlay, validate_payload
    library_map=validate_payload(ROOT/'app/src/main/assets/data/library.json')
    services=data.get('services') or []
    service_map={s.get('id'):s for s in services if isinstance(s,dict)}
    required_services={'divine_liturgy','vespers','orthros','morning_prayer','evening_prayer','small_compline','next_sunday_full_liturgy'}
    if not required_services.issubset(service_map): fail('daily-aware services incomplete')
    composed=[compose_overlay(service,library_map,path) for service in services]
    for service in composed:
        if service.get('id') in {'divine_liturgy','next_sunday_full_liturgy'}:
            if len(service.get('segments') or [])<200: fail(f"{service.get('id')} is too short")
            rendered=json.dumps(service,ensure_ascii=False)
            for bad in BAD_MARKERS:
                if bad in rendered: fail(f"{service.get('id')} contains placeholder {bad}")
    for sid in required_services:
        if not str(service_map[sid].get('dynamic_date') or ''): fail(f'{sid} missing dynamic_date')
    from validate_liturgical_schedule import validate as validate_schedule
    errors=validate_schedule(data)
    if errors: fail('liturgical schedule invalid: '+' | '.join(errors))
    check_synced(data,path,date_iso)
    print(f'Quality check passed for {date_iso}: strict native lanes, safe unavailable states, services, schedule, and synchronized signed outputs')
if __name__=='__main__': main()
