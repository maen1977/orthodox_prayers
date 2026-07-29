from __future__ import annotations
import importlib.util
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

spec=importlib.util.spec_from_file_location('edition_evidence',ROOT/'scripts/validate_service_edition_evidence.py')
assert spec and spec.loader
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)

def test_source_backed_evidence_gate_passes():
    assert mod.collect_errors()==[]

def test_all_production_complete_statuses_have_evidence_records():
    manifest=json.loads((ROOT/'canonical/religious_completeness_manifest.json').read_text(encoding='utf-8'))
    evidence=json.loads((ROOT/'canonical/service_edition_evidence.json').read_text(encoding='utf-8'))['services']
    for lang in ('ar','en','el'):
        for service,status in manifest['languages'][lang].items():
            if status in set(manifest['production_complete_statuses']):
                assert f'{service}:{lang}' in evidence
                assert evidence[f'{service}:{lang}']['status'] == status

def test_chrysostom_distinguishes_native_compilation_from_exact_editions():
    manifest=json.loads((ROOT/'canonical/religious_completeness_manifest.json').read_text(encoding='utf-8'))
    assert manifest['languages']['ar']['chrysostom_liturgy']=='complete_native_source_compilation'
    assert manifest['languages']['en']['chrysostom_liturgy']=='complete_exact_native_edition'
    assert manifest['languages']['el']['chrysostom_liturgy']=='complete_exact_native_edition'
