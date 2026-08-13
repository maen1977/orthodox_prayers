import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def read(rel): return (ROOT/rel).read_text(encoding='utf-8')
def load(rel): return json.loads(read(rel))

def test_church_service_builder_blocks_unconfirmed_redistribution_before_fetch():
    source=read('scripts/prepare_church_service_corpus.py')
    assert 'def redistribution_allowed(spec' in source
    assert 'not redistribution_allowed(spec)' in source
    assert 'OFFICIAL_SOURCE_LINK_ONLY_RIGHTS_PENDING' in source
    assert 'redistribution_permission_not_confirmed' in source

def test_arabic_church_service_manifest_uses_owner_confirmed_r64_permission():
    data=load('canonical/church_service_full_sources.json')
    services=data['languages']['ar']['services']
    assert services
    assert all(s.get('permission_confirmed') is True for s in services)
    assert all(s.get('redistribution_review_required') is False for s in services)
    assert all(s.get('rights_basis') == 'PROJECT_OWNER_CONFIRMED_R64_JERUSALEM_JORDAN_LICENSE' for s in services)
    assert all('2026-08-10' in s.get('authorization_record','') for s in services)
    assert all(s.get('allow_link_fallback', False) for s in services)

def test_official_daily_prayer_resources_are_reference_only_and_arabic_scoped():
    data=load('app/src/main/assets/data/official_prayer_resources.json')
    assert data['policy'] == 'SOURCE_REFERENCE_CATALOG_NOT_RENDERED_AS_EXTERNAL_PRAYER_CARDS'
    assert len(data['resources']) >= 4
    ids={x['id'] for x in data['resources']}
    assert {'official_before_confession_ar','official_guardian_angel_ar','official_beginning_day_optina_ar','official_study_prayer_ar'} <= ids
    for item in data['resources']:
        assert item['languages'] == ['ar']
        assert item['embedded_text'] is False
        assert item['url'].startswith('https://orthodoxjordan.org/')
        assert item['title']['ar'].strip()
        assert item['title']['en'] == '' and item['title']['el'] == ''

def test_daily_prayer_screen_never_opens_external_prayer_links():
    source=read('app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/ServiceListScreen.java')
    assert 'addOfficialDailyPrayerResources' not in source
    assert 'Intent.ACTION_VIEW' not in source
    assert 'openOfficialUrl' not in source

def test_church_service_reader_labels_catalog_only_and_uses_exact_catalog_source():
    source=read('app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/ReaderScreen.java')
    assert 'churchCatalogOnly' in source
    assert 'ui_church_service_catalog_only_r62' in source
    assert 'JSONObject catalogSource = service.optJSONObject("catalog_source")' in source
    assert 'catalogSource.optString("url"' in source


def test_rights_pending_source_is_never_prefetched(monkeypatch, tmp_path):
    import importlib.util
    spec=importlib.util.spec_from_file_location('r62_church_builder', ROOT/'scripts/prepare_church_service_corpus.py')
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    def forbidden_fetch(*args, **kwargs):
        raise AssertionError('rights-pending source must not be fetched')
    monkeypatch.setattr(mod, 'fetch_spec', forbidden_fetch)
    manifest={'languages':{'ar':{'services':[{'id':'x','url':'https://example.test/x','permission_confirmed':False,'redistribution_review_required':True}]}}}
    assert mod.prefetch_registered_sources(manifest, tmp_path) == {}
    assert mod.redistribution_allowed(manifest['languages']['ar']['services'][0]) is False
    assert mod.redistribution_allowed({'permission_confirmed':True,'redistribution_review_required':False}) is True
