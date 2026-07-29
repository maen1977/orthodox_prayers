#!/usr/bin/env python3
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
manifest=json.loads((ROOT/'canonical/religious_completeness_manifest.json').read_text(encoding='utf-8'))
langs=('ar','en','el'); complete='complete_exact_native_edition'
known={
 ('chrysostom_liturgy','ar'):[
  'Current Arabic package is materially shorter than the complete English/Greek editions.',
  'Missing separately structured catechumen dismissal and first/second prayers of the faithful.',
  'Several priestly prayers and rubrics are condensed; exact single-edition completeness is not proven.'
 ],
 ('pre_communion','en'):['Current package is a prayer-book selection, not the complete appointed office.'],
 ('pre_communion','el'):['Current package is a prayer-book selection, not the complete appointed office.'],
 ('post_communion','en'):['Current package is a prayer-book selection, not the complete thanksgiving office.'],
 ('post_communion','el'):['Current package is a prayer-book selection, not the complete thanksgiving office.'],
}
rows=[]
for service in manifest['required_services']:
 row={'service':service,'packaged_service_id':manifest['packaged_service_ids'][service],'languages':{}}
 for lang in langs:
  status=manifest['languages'][lang][service]
  blockers=[] if status==complete else known.get((service,lang),[])
  if status=='missing': blockers=['No packaged native service exists.']
  elif status=='abridged': blockers=['Packaged text is an abridgement and cannot be promoted by field coverage or source URL alone.']
  elif status=='unproven_complete' and not blockers: blockers=['A complete single-edition source comparison and structural proof are missing.']
  elif status=='complete_authorized_native_selection' and not blockers: blockers=['The imported selection is complete for its scope but not the complete required office.']
  row['languages'][lang]={'status':status,'release_ready':status==complete,'blockers':blockers}
 rows.append(row)
out={'schema_version':1,'generated_at_utc':datetime.now(timezone.utc).isoformat(),'summary':{l:{'complete':sum(manifest['languages'][l][s]==complete for s in manifest['required_services']),'required':15} for l in langs},'services':rows,'source_acquisition_plan':'canonical/service_source_acquisition_plan.json'}
(ROOT/'CONTENT_GAP_MATRIX.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(ROOT/'CONTENT_GAP_MATRIX.json')
