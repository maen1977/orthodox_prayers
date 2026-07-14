#!/usr/bin/env python3
"""Validate the signed offline data and exact native-language contract shipped in the APK."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from native_text_contract import ROOT, LANGUAGES, sha256_text
CANONICAL_TODAY=ROOT/'data/calendar/today.json'
ASSET_TODAY=ROOT/'app/src/main/assets/data/today.json'
ASSET_LIBRARY=ROOT/'app/src/main/assets/data/library.json'
REQUIRED_SERVICES={'divine_liturgy','vespers','orthros','morning_prayer','evening_prayer','small_compline','next_sunday_full_liturgy'}

def fail(message):
    print(f'::error title=Embedded app data validation::{message}')
    raise SystemExit(message)
def read_object(path):
    try: value=json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc: fail(f'{path.relative_to(ROOT)} is not valid JSON: {exc}')
    if not isinstance(value,dict): fail(f'{path.relative_to(ROOT)} must contain an object')
    return value
def localized_ar(value:Any)->str: return str(value.get('ar') or '').strip() if isinstance(value,dict) else ''

def validate_today(data):
    required={'schema_version','date_iso','date_label','fast','fasting','readings','services','upcoming','next_sunday','integrity','language_content_mode','language_sources','native_text_contract'}
    missing=sorted(required-set(data))
    if missing: fail('today.json is missing: '+', '.join(missing))
    if int(data.get('schema_version') or 0)!=9: fail('today.json schema_version must be 9')
    if data.get('language_content_mode')!='THREE_STRICTLY_INDEPENDENT_OFFICIAL_NATIVE_LANGUAGE_LANES': fail('native language mode is invalid')
    if data.get('machine_translation_used') is not False or data.get('automatic_diacritization_used') is not False: fail('forbidden transformation flag')
    if data.get('translation_fallback_policy')!='DISABLED_NO_CROSS_LANGUAGE_FALLBACK': fail('cross-language fallback is not disabled')
    if not localized_ar(data.get('date_label')) or not localized_ar(data.get('fast')): fail('Arabic UI date/fast label missing')
    if not isinstance(data.get('upcoming'),list) or len(data['upcoming'])!=7: fail('today.json must contain seven upcoming days')
    integrity=data.get('integrity') or {}
    if integrity.get('status')!='VERIFIED_OFFICIAL_SOURCES': fail('top-level source integrity is not verified')
    if integrity.get('ai_scripture_translation_used') is not False or integrity.get('ai_liturgical_translation_used') is not False: fail('AI flags are invalid')
    readings=data.get('readings')
    if not isinstance(readings,list): fail('readings must be an array')
    by_kind={item.get('kind'):item for item in readings if isinstance(item,dict)}
    for kind in ('prokeimenon','epistle','gospel'):
        reading=by_kind.get(kind)
        if not reading: fail(f'missing {kind}')
        if reading.get('translation_locked') is not True: fail(f'{kind} is not locked')
        if (reading.get('integrity') or {}).get('status')!='NATIVE_LANGUAGE_LANES_ENFORCED': fail(f'{kind} native-lane integrity missing')
        verification=reading.get('native_source_verification') or {}
        if any(not isinstance(verification.get(lang),dict) for lang in LANGUAGES): fail(f'{kind} lacks three language evidence records')
        body=reading.get('body') or {}
        for lang in LANGUAGES:
            text=str(body.get(lang) or '')
            evidence=verification[lang]
            if text:
                if evidence.get('status') not in {'VERIFIED_EXACT_NATIVE_SOURCE','IMPORTED_EXACT_OFFICIAL_NATIVE_CORPUS'}: fail(f'{kind}.{lang} non-empty text is unverified')
                if evidence.get('text_sha256')!=sha256_text(text): fail(f'{kind}.{lang} text hash mismatch')
    services=data.get('services')
    if not isinstance(services,list): fail('services must be an array')
    ids={str(item.get('id')) for item in services if isinstance(item,dict)}
    missing_services=sorted(REQUIRED_SERVICES-ids)
    if missing_services: fail('missing services: '+', '.join(missing_services))
    for service in services:
        if not localized_ar(service.get('title')): fail(f"service {service.get('id')!r} has no Arabic UI title")
        if not isinstance(service.get('segments'),list) or not service['segments']: fail(f"service {service.get('id')!r} has no segments")

def validate_library(data):
    services=data.get('services')
    if not isinstance(services,list) or not services: fail('library services missing')
    ids=set()
    for service in services:
        sid=str(service.get('id') or '')
        if not sid or sid in ids: fail(f'invalid/duplicate library service id {sid!r}')
        ids.add(sid)
        if not localized_ar(service.get('title')): fail(f'library service {sid} has no Arabic title')

def main():
    if CANONICAL_TODAY.read_bytes()!=ASSET_TODAY.read_bytes(): fail('embedded today.json differs from canonical')
    today=read_object(ASSET_TODAY); library=read_object(ASSET_LIBRARY)
    validate_today(today); validate_library(library)
    dated=ROOT/'data/calendar'/f"{today['date_iso']}.json"
    if not dated.exists() or dated.read_bytes()!=CANONICAL_TODAY.read_bytes(): fail('dated JSON is missing or unsynchronized')
    print(f"Embedded app data validated: schema=9 date={today['date_iso']} services={len(today['services'])}")
if __name__=='__main__': main()
