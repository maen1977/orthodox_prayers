from pathlib import Path
import importlib.util
import json

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/'scripts/prepare_church_service_corpus.py'


def load_module():
    spec=importlib.util.spec_from_file_location('church_service_builder_v552',SCRIPT)
    module=importlib.util.module_from_spec(spec); assert spec.loader
    spec.loader.exec_module(module)
    return module


def test_version_is_552():
    text=(ROOT/'app/build.gradle.kts').read_text(encoding='utf-8')
    assert 'versionCode = 50604' in text
    assert 'versionName = "5.6.4"' in text


def test_manifest_uses_open_redistributable_sources_for_en_el():
    data=json.loads((ROOT/'canonical/church_service_full_sources.json').read_text(encoding='utf-8'))
    assert data['policy']=='RIGHTS_AWARE_NATIVE_SOURCE_ONLY_NO_TRANSLATION'
    assert data['runtime_network_required'] is False
    for svc in data['languages']['en']['services']:
        assert svc['source_transport']=='public_domain_plain_text'
        assert svc['permission_confirmed'] is True
        assert svc['rights_basis']=='PUBLIC_DOMAIN_1922_HAPGOOD'
        assert 'archive.org' in svc['url']
        assert svc['allow_link_fallback'] is True
    for svc in data['languages']['el']['services']:
        assert svc['source_transport']=='cc_by_pdf_text'
        assert svc['permission_confirmed'] is True
        assert svc['rights_basis'].startswith('CC_BY_4_0')
        assert 'olympias.lib.uoi.gr' in svc['url']
        assert svc['license_url']=='https://creativecommons.org/licenses/by/4.0/'
        assert svc['allow_link_fallback'] is True


def test_no_protected_goarch_page_is_required_for_bundle():
    data=json.loads((ROOT/'canonical/church_service_full_sources.json').read_text(encoding='utf-8'))
    for lang in ('en','el'):
        for svc in data['languages'][lang]['services']:
            assert 'www.goarch.org' not in svc['url']


def test_plain_text_section_extraction_ignores_toc_first_hit():
    m=load_module()
    raw=b'''CONTENTS\nBETROTHAL\nCROWNING\n\nOTHER\n\nTHE OFFICE OF BETROTHAL\nPRIEST\n''' + b'Complete service line.\n'*100 + b'''\nTHE OFFICE OF CROWNING\nPRIEST\nNext service\n'''
    spec={'id':'church_betrothal','title':'Service of Betrothal','source_transport':'public_domain_plain_text',
          'start_marker':['THE OFFICE OF BETROTHAL','BETROTHAL'],'end_marker':['THE OFFICE OF CROWNING'],
          'marker_occurrence':'last'}
    blocks=m.normalize_blocks(raw,'en',spec)
    text=' '.join(blocks)
    assert 'Complete service line' in text
    assert 'Next service' not in text


def test_cc_pdf_text_is_cached_after_single_conversion(monkeypatch,tmp_path):
    m=load_module(); calls={'download':0,'convert':0}
    monkeypatch.setattr(m,'_fetch_open_source',lambda url,cache,suffix: calls.__setitem__('download',calls['download']+1) or b'%PDF fake source bytes'*100)
    monkeypatch.setattr(m,'_pdf_to_text',lambda raw: calls.__setitem__('convert',calls['convert']+1) or (b'GREEK SERVICE TEXT\n'*100))
    a=m._fetch_cc_pdf_text('https://example.test/euchologion.pdf',tmp_path)
    b=m._fetch_cc_pdf_text('https://example.test/euchologion.pdf',tmp_path)
    assert a==b
    assert calls=={'download':1,'convert':1}


def test_build_service_does_not_hardcode_permission_true():
    text=SCRIPT.read_text(encoding='utf-8')
    assert 'bool(spec.get("permission_confirmed", False))' in text
    assert '"rights_basis": spec.get("rights_basis"' in text


def test_workflow_installs_pdf_text_tool_before_import():
    text=(ROOT/'.github/workflows/church-prayers.yml').read_text(encoding='utf-8')
    assert 'Prepare open liturgical source tools' in text
    assert 'poppler-utils' in text
    assert text.index('Prepare open liturgical source tools') < text.index('Prepare complete native church services')
