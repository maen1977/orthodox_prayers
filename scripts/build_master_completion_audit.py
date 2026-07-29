#!/usr/bin/env python3
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
manifest=json.loads((ROOT/'canonical/religious_completeness_manifest.json').read_text(encoding='utf-8'))
required=manifest['required_services']
langs=('ar','en','el')
complete='complete_exact_native_edition'
rows=[]
for service in required:
    row={'service':service,'packaged_service_id':manifest['packaged_service_ids'].get(service),'languages':{}}
    for lang in langs:
        status=manifest['languages'][lang][service]
        row['languages'][lang]={'status':status,'release_ready':status==complete}
    row['all_languages_release_ready']=all(row['languages'][l]['release_ready'] for l in langs)
    rows.append(row)
summary={lang:{'complete':sum(manifest['languages'][lang][s]==complete for s in required),'required':len(required)} for lang in langs}
out={
 'schema_version':1,
 'generated_at_utc':datetime.now(timezone.utc).isoformat(),
 'release_allowed':all(summary[l]['complete']==len(required) for l in langs),
 'definition':manifest['definition'],
 'machine_translation_allowed':manifest['machine_translation_allowed'],
 'summary':summary,
 'services':rows,
 'blocking_rules':[
  'Every required service must be complete_exact_native_edition in ar, en, and el.',
  'A packaged fragment, abridgement, selection, or external link is not completeness.',
  'Machine translation cannot promote a service to release-ready.',
  'The signed release workflow must run validate_religious_completeness.py in production mode.'
 ]
}
path=ROOT/'MASTER_COMPLETION_AUDIT.json'
path.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(path)
print(json.dumps(summary,ensure_ascii=False))
print('release_allowed=',out['release_allowed'])
