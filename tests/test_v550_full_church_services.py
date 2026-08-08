from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]


def test_version_is_552():
    text = (ROOT / 'app/build.gradle.kts').read_text(encoding='utf-8')
    assert 'versionCode = 50602' in text
    assert 'versionName = "5.6.2"' in text


def test_native_source_manifest_forbids_translation():
    data = json.loads((ROOT / 'canonical/church_service_full_sources.json').read_text(encoding='utf-8'))
    assert data['policy'] == 'RIGHTS_AWARE_NATIVE_SOURCE_ONLY_NO_TRANSLATION'
    assert data['runtime_network_required'] is False
    assert set(data['languages']) == {'ar', 'en', 'el'}
    assert len(data['languages']['ar']['services']) >= 10
    for lang, lane in data['languages'].items():
        assert lane['services']
        for svc in lane['services']:
            assert svc['id'].startswith('church_')
            assert svc['title'].strip()
            assert svc['url'].startswith('https://')


def test_gradle_builds_and_bundles_church_service_assets():
    text = (ROOT / 'app/build.gradle.kts').read_text(encoding='utf-8')
    assert 'prepareChurchServiceCorpus' in text
    assert 'scripts/prepare_church_service_corpus.py' in text
    assert 'generated/churchServiceAssets' in text
    assert 'assets.srcDir(generatedChurchServiceAssets' in text
    assert 'dependsOn(prepareBibleCorpus, prepareChurchServiceCorpus)' in text


def test_workflow_prepares_church_services_before_gradle():
    text = (ROOT / '.github/workflows/church-prayers.yml').read_text(encoding='utf-8')
    pos_service = text.index('Prepare complete native church services')
    pos_gradle = text.index('Test and build the app')
    assert pos_service < pos_gradle
    assert '--output-dir app/build/generated/churchServiceAssets/data/church' in text


def test_runtime_overlays_only_same_language_offline_pack():
    text = (ROOT / 'app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java').read_text(encoding='utf-8')
    assert 'data/church/full_services_' in text
    assert 'language.equals(pack.optString("language", ""))' in text
    assert 'pack.optBoolean("machine_translation_used", true)' in text
    assert 'loadOptionalJsonAsset' in text


def test_existing_complete_local_church_services_are_composed_not_translated():
    text = (ROOT / 'app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java').read_text(encoding='utf-8')
    assert '"church_eucharist".equals(id)' in text
    assert '"church_hours".equals(id)' in text
    assert 'FULL_NATIVE_SERVICE_COMPOSED_FROM_AUDITED_LOCAL_ASSETS' in text
    assert '"first_hour", "third_hour", "sixth_hour", "ninth_hour"' in text


def test_importer_is_build_time_only_and_no_translation():
    text = (ROOT / 'scripts/prepare_church_service_corpus.py').read_text(encoding='utf-8')
    assert 'BUILD-TIME ONLY' in text
    assert 'machine_translation_used' in text
    assert 'cross_language_fallback' in text
    assert 'urllib.request' in text
    runtime = (ROOT / 'app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java').read_text(encoding='utf-8')
    assert 'orthodoxjordan.org' not in runtime
    assert 'goarch.org' not in runtime
