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
    assert 'versionCode = 50607' in text
    assert 'versionName = "5.6.7"' in text


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
        assert svc['permission_confirmed'] is True
        assert svc['allow_link_fallback'] is True
        transport = svc['source_transport']
        if transport == 'official_html_user_permission':
            assert svc['source_id'] == 'goarch_glt_greek_euchologion_pages'
            assert svc['source_name']
            assert svc['rights_basis'].startswith('USER_CONFIRMED_REPUBLICATION_PERMISSION_')
            assert 'glt.goarch.org' in svc['url']
        elif transport == 'local_native_text':
            assert svc['id']=='church_memorial'
            assert svc['local_path']=='canonical/sources/greek_dcs_memorial/church_memorial.txt'
            assert svc['source_id']=='goarch_dcs_greek_memorial_2026_07_19'
            assert svc['source_name']
            assert svc['rights_basis'].startswith('USER_CONFIRMED_REPUBLICATION_PERMISSION_')
            assert svc['extraction_method']=='EXACT_GREEK_ONLY_FROM_REGISTERED_DCS_PAGE_NO_TRANSLATION'
            assert 'dcs.goarch.org' in svc['url']
        else:
            assert svc['rights_basis'].startswith('CC_BY_4_0')
            assert 'olympias.lib.uoi.gr' in svc['url']
            assert svc['license_url']=='https://creativecommons.org/licenses/by/4.0/'
            if transport == 'local_native_ocr_text':
                assert svc['local_path'].startswith('canonical/sources/greek_uoi_ocr/')
                assert svc['ocr_page_ranges']
                assert svc['extraction_method']=='OCR_FROM_REGISTERED_NATIVE_GREEK_SCAN_NO_TRANSLATION'
            else:
                assert transport=='cc_by_pdf_text'


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
    assert 'tesseract-ocr-ell' in text
    assert text.index('Prepare open liturgical source tools') < text.index('Prepare offline Bible and church-service assets once')


def test_local_native_source_key_is_distinct_per_excerpt():
    m=load_module()
    a={'source_transport':'local_native_ocr_text','url':'https://example.test/uoi.pdf','local_path':'canonical/sources/greek_uoi_ocr/church_confession.txt','ocr_page_ranges':[[271,287]]}
    b={'source_transport':'local_native_ocr_text','url':'https://example.test/uoi.pdf','local_path':'canonical/sources/greek_uoi_ocr/church_priesthood.txt','ocr_page_ranges':[[213,237]]}
    assert m._source_key('el', a) != m._source_key('el', b)


def test_local_native_text_reads_registered_repo_file(tmp_path):
    m=load_module()
    spec={'local_path':'canonical/sources/greek_uoi_ocr/church_confession.txt'}
    data=m._fetch_local_native_text(spec)
    assert 'ΑΚΟΛΟΥΘΙΑ'.encode('utf-8') in data


def test_dcs_memorial_excerpt_is_greek_only_and_bounded():
    path=ROOT/'canonical/sources/greek_dcs_memorial/church_memorial.txt'
    text=path.read_text(encoding='utf-8')
    assert len(text) > 2500
    assert 'Ὁ Θεὸς τῶν πνευμάτων' in text
    assert 'Αἰωνία' in text
    assert not any(('A' <= ch <= 'Z') or ('a' <= ch <= 'z') for ch in text)
