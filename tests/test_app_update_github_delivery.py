from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_android_updater_is_securely_wired():
    manifest = read("app/src/main/AndroidManifest.xml")
    manager = read("app/src/main/java/com/orthodoxprayers/privateapp/appupdate/AppUpdateManager.java")
    client = read("app/src/main/java/com/orthodoxprayers/privateapp/appupdate/AppUpdateClient.java")
    verifier = read("app/src/main/java/com/orthodoxprayers/privateapp/appupdate/AppUpdateVerifier.java")
    worker = read("app/src/main/java/com/orthodoxprayers/privateapp/work/AppUpdateWorker.java")

    assert "android.permission.REQUEST_INSTALL_PACKAGES" in manifest
    assert "androidx.core.content.FileProvider" in manifest
    assert "@xml/file_paths" in manifest
    assert "releases/latest" in client
    assert "https" in client and "ALLOWED_HOSTS" in client
    assert "checksum_mismatch" in verifier
    assert "certificate_mismatch" in verifier
    assert "package_mismatch" in verifier
    assert "PeriodicWorkRequest" in manager
    assert "canRequestPackageInstalls" in manager
    assert "AppUpdateManager" in worker


def test_release_workflow_publishes_updater_contract_assets():
    workflow = read(".github/workflows/church-prayers.yml")
    assert 'tags: ["v*"]' in workflow
    assert "generate_app_update_manifest.py" in workflow
    assert "Church-Prayers.apk.sha256" in workflow
    assert "app-update.json" in workflow
    assert "gh release create" in workflow
    assert "gh release upload" in workflow
    assert "ANDROID_KEYSTORE_B64" in workflow
    assert "Release tags require the production signing secrets" in workflow


def test_release_version_is_bumped_for_updater_delivery():
    build = read("app/build.gradle.kts")
    assert 'versionName = "5.5.2"' in build
    assert "versionCode = 50502" in build
