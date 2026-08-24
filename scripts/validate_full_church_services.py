#!/usr/bin/env python3
from pathlib import Path
import json, re, sys

ROOT = Path(__file__).resolve().parents[1]
errors=[]
manifest=json.loads((ROOT/'canonical/church_service_full_sources.json').read_text(encoding='utf-8'))
if manifest.get('policy')!='RIGHTS_AWARE_NATIVE_SOURCE_ONLY_NO_TRANSLATION': errors.append('policy')
if manifest.get('runtime_network_required') is not False: errors.append('runtime_network_required')
for lang,lane in manifest.get('languages',{}).items():
    ids=set()
    for svc in lane.get('services',[]):
        if svc.get('id') in ids: errors.append(f'duplicate:{lang}:{svc.get("id")}')
        ids.add(svc.get('id'))
        if not str(svc.get('url','')).startswith('https://'): errors.append(f'url:{lang}:{svc.get("id")}')


# 5.6.2 build resilience: official Arabic sources may be temporarily unreachable from hosted runners.
# Required services must fail soft only to their own official source link; another language is never substituted.
ar_lane=manifest.get('languages',{}).get('ar',{})
for svc in ar_lane.get('services',[]):
    if svc.get('required'):
        if svc.get('allow_link_fallback') is not True:
            errors.append(f'ar_required_network_fallback:{svc.get("id")}')
        if svc.get('fallback_policy') != 'OFFICIAL_SOURCE_LINK_ONLY_WHEN_BUILD_SOURCE_UNAVAILABLE':
            errors.append(f'ar_fallback_policy:{svc.get("id")}')
    if int(svc.get('max_chars',80000)) > 120000:
        errors.append(f'ar_max_chars:{svc.get("id")}')

gradle=(ROOT/'app/build.gradle.kts').read_text(encoding='utf-8')
for token in ['versionCode = 50605','versionName = "5.6.5"','prepareChurchServiceCorpus','generated/churchServiceAssets']:
    if token not in gradle: errors.append('gradle:'+token)
repo=(ROOT/'app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java').read_text(encoding='utf-8')
for token in ['data/church/full_services_','machine_translation_used','composeBuiltInChurchService']:
    if token not in repo: errors.append('runtime:'+token)


# 5.6.2 rights/source hardening: protected GOARCH pages are not scraped into the APK.
for lang in ('en','el'):
    lane=manifest.get('languages',{}).get(lang,{})
    for svc in lane.get('services',[]):
        transport=svc.get('source_transport')
        if transport not in {'public_domain_plain_text','cc_by_pdf_text','official_link_only'}:
            errors.append(f'open_transport:{lang}:{svc.get("id")}:{transport}')
        if transport in {'public_domain_plain_text','cc_by_pdf_text'}:
            if svc.get('permission_confirmed') is not True:
                errors.append(f'rights_not_confirmed:{lang}:{svc.get("id")}')
            if svc.get('redistribution_review_required') is not False:
                errors.append(f'rights_review_flag:{lang}:{svc.get("id")}')
            if not svc.get('rights_basis'):
                errors.append(f'rights_basis:{lang}:{svc.get("id")}')
        if 'www.goarch.org' in str(svc.get('url','')) and transport != 'official_link_only':
            errors.append(f'protected_goarch_bundling:{lang}:{svc.get("id")}')

importer=(ROOT/'scripts/prepare_church_service_corpus.py').read_text(encoding='utf-8')
for token in ['public_domain_plain_text','cc_by_pdf_text','CHURCH_SERVICE_RIGHTS_LINK_ONLY','rights_basis','permission_confirmed','service_too_large','fallbacks','OFFICIAL_SOURCE_LINK_ONLY_BUILD_FALLBACK']:
    if token not in importer: errors.append('importer:'+token)
for forbidden in ['r.jina.ai','cross_language_fallback = True','permission_confirmed": True']:
    if forbidden in importer: errors.append('forbidden_importer:'+forbidden)

out=ROOT/'app/build/generated/churchServiceAssets/data/church'
materialized=[]
if out.exists():
    for lang in ['ar','en','el']:
        p=out/f'full_services_{lang}.json'
        if not p.exists(): errors.append(f'missing_generated:{lang}'); continue
        d=json.loads(p.read_text(encoding='utf-8'))
        if d.get('language')!=lang or d.get('machine_translation_used') is not False or d.get('cross_language_fallback') is not False:
            errors.append(f'generated_policy:{lang}')
        for fb in d.get('fallbacks',[]):
            if fb.get('full_service') is not False or fb.get('machine_translation_used') is not False or fb.get('cross_language_fallback') is not False:
                errors.append(f'generated_fallback_policy:{lang}:{fb.get("id")}')
            if not str(fb.get('official_source_url','')).startswith('https://'):
                errors.append(f'generated_fallback_url:{lang}:{fb.get("id")}')
        materialized.append(f'{lang}:{len(d.get("services",[]))}/fallback:{len(d.get("fallbacks",[]))}')
if errors:
    print('FULL_CHURCH_SERVICES_FAIL', *errors, sep='\n')
    sys.exit(1)
print('FULL_CHURCH_SERVICES_OK version=5.6.5 policy=rights_aware_no_translation generated=' + (','.join(materialized) if materialized else 'not_materialized_in_source_checkout'))
