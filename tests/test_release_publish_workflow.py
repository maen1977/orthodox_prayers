from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_manual_publish_release_path_is_available_and_signed():
    workflow = (ROOT / '.github/workflows/church-prayers.yml').read_text(encoding='utf-8')
    assert 'publish_release:' in workflow
    assert "inputs.publish_release" in workflow
    assert 'IS_RELEASE_BUILD:' in workflow
    assert 'Release tags require the production signing secrets' in workflow
    assert 'RELEASE_TAG=$release_tag' in workflow
    assert 'gh api --method POST' in workflow
    assert 'refs/tags/$release_tag' in workflow
    assert 'gh release create "$release_tag"' in workflow


def test_local_signing_setup_is_never_committed():
    script = (ROOT / 'scripts/setup_release_signing.ps1').read_text(encoding='utf-8')
    ignore = (ROOT / '.gitignore').read_text(encoding='utf-8')
    assert 'ANDROID_KEYSTORE_B64' in script
    assert 'ANDROID_KEYSTORE_PASSWORD' in script
    assert 'ANDROID_KEY_ALIAS' in script
    assert 'ANDROID_KEY_PASSWORD' in script
    assert 'release-signing.dpapi.json' in script
    assert '.release-signing/' in ignore
