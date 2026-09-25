from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]


def test_remote_payload_ceiling_is_shared_by_manifest_downloader_and_store():
    contract = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/DataContract.java").read_text(encoding="utf-8")
    repository = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java").read_text(encoding="utf-8")
    store = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/DailyDataStore.java").read_text(encoding="utf-8")
    manifest = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/UpdateManifest.java").read_text(encoding="utf-8")
    assert "MAX_SIGNED_PAYLOAD_BYTES = 12_000_000" in contract
    assert "MAX_JSON_BYTES = DataContract.MAX_SIGNED_PAYLOAD_BYTES" in repository
    assert "MAX_JSON_BYTES = DataContract.MAX_SIGNED_PAYLOAD_BYTES" in store
    assert "size > DataContract.MAX_SIGNED_PAYLOAD_BYTES" in manifest
    assert "MAX_JSON_BYTES = 6_000_000" not in store


def test_5023_is_required_before_publishing_large_moving_window_payloads():
    build = (ROOT / "app/build.gradle.kts").read_text(encoding="utf-8")
    update_contract = json.loads((ROOT / "canonical/update_contract.json").read_text(encoding="utf-8"))
    assert 'versionName = "5.6.7"' in build
    assert "versionCode = 50607" in build
    assert update_contract["minimum_app_version_code"] == 50023


def test_manual_failure_surfaces_and_persists_the_real_diagnostic_code():
    activity = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/MainActivity.java").read_text(encoding="utf-8")
    repository = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java").read_text(encoding="utf-8")
    assert "preferences.setAdvancedDiagnosticsExpanded(true)" in activity
    assert "repository.refreshDiagnosticCode()" in activity
    assert "invalid_json_size" in repository
    assert "response_too_large" in repository
