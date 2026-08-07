#!/usr/bin/env python3
from pathlib import Path
import json, re, sys

ROOT = Path(__file__).resolve().parents[1]
errors=[]
manifest=json.loads((ROOT/'canonical/church_service_full_sources.json').read_text(encoding='utf-8'))
if manifest.get('policy')!='AUTHORIZED_NATIVE_SOURCE_ONLY_NO_TRANSLATION': errors.append('policy')
if manifest.get('runtime_network_required') is not False: errors.append('runtime_network_required')
for lang,lane in manifest.get('languages',{}).items():
    ids=set()
    for svc in lane.get('services',[]):
        if svc.get('id') in ids: errors.append(f'duplicate:{lang}:{svc.get("id")}')
        ids.add(svc.get('id'))
        if not str(svc.get('url','')).startswith('https://'): errors.append(f'url:{lang}:{svc.get("id")}')

gradle=(ROOT/'app/build.gradle.kts').read_text(encoding='utf-8')
for token in ['versionCode = 50501','versionName = "5.5.1"','prepareChurchServiceCorpus','generated/churchServiceAssets']:
    if token not in gradle: errors.append('gradle:'+token)
repo=(ROOT/'app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java').read_text(encoding='utf-8')
for token in ['data/church/full_services_','machine_translation_used','composeBuiltInChurchService']:
    if token not in repo: errors.append('runtime:'+token)


# 5.5.1 transport hardening: prefer stable DCS pages when known and keep GOARCH
# fallbacks same-origin without weakening required content.
for lang in ('en','el'):
    by_id={svc.get('id'):svc for svc in manifest.get('languages',{}).get(lang,{}).get('services',[])}
    for service_id in ('church_baptism','church_memorial'):
        svc=by_id.get(service_id,{})
        if not str(svc.get('url','')).startswith('https://dcs.goarch.org/'):
            errors.append(f'dcs_preference:{lang}:{service_id}')
        if svc.get('source_transport')!='dcs_static':
            errors.append(f'dcs_transport:{lang}:{service_id}')
    for service_id,svc in by_id.items():
        if 'goarch.org' in str(svc.get('url','')) and 'dcs.goarch.org' not in str(svc.get('url','')):
            if svc.get('source_transport')!='goarch_browser_fallback':
                errors.append(f'goarch_transport:{lang}:{service_id}')

importer=(ROOT/'scripts/prepare_church_service_corpus.py').read_text(encoding='utf-8')
for token in ['_fetch_with_curl','_fetch_with_headless_browser','CHURCH_SERVICE_CURL_FALLBACK_OK','CHURCH_SERVICE_BROWSER_FALLBACK_OK','Referer']:
    if token not in importer: errors.append('importer:'+token)
for forbidden in ['r.jina.ai','cross_language_fallback = True']:
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
        materialized.append(f'{lang}:{len(d.get("services",[]))}')
if errors:
    print('FULL_CHURCH_SERVICES_FAIL', *errors, sep='\n')
    sys.exit(1)
print('FULL_CHURCH_SERVICES_OK version=5.5.1 policy=no_translation generated=' + (','.join(materialized) if materialized else 'not_materialized_in_source_checkout'))
