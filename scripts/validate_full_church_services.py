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
for token in ['versionCode = 50500','versionName = "5.5.0"','prepareChurchServiceCorpus','generated/churchServiceAssets']:
    if token not in gradle: errors.append('gradle:'+token)
repo=(ROOT/'app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java').read_text(encoding='utf-8')
for token in ['data/church/full_services_','machine_translation_used','composeBuiltInChurchService']:
    if token not in repo: errors.append('runtime:'+token)

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
print('FULL_CHURCH_SERVICES_OK version=5.5.0 policy=no_translation generated=' + (','.join(materialized) if materialized else 'not_materialized_in_source_checkout'))
