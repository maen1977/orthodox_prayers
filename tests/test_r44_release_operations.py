from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def create_zip(path: Path, entries: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)


def test_release_artifact_verifier_accepts_structural_apk_and_aab(tmp_path: Path) -> None:
    apk = tmp_path / "Church-Prayers-5.2.0.apk"
    aab = tmp_path / "Church-Prayers-5.2.0.aab"
    create_zip(apk, {
        "AndroidManifest.xml": b"binary-manifest",
        "classes.dex": b"dex\n035\0" + b"a" * 64,
        "assets/data/calendar/today.json": b"{}",
    })
    create_zip(aab, {
        "BundleConfig.pb": b"bundle",
        "base/manifest/AndroidManifest.xml": b"binary-manifest",
        "base/dex/classes.dex": b"dex\n035\0" + b"b" * 64,
    })
    report = tmp_path / "report.json"
    subprocess.run([
        sys.executable,
        "scripts/verify_release_artifacts.py",
        "--apk", str(apk),
        "--aab", str(aab),
        "--report", str(report),
    ], cwd=ROOT, check=True)
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["status"] == "PASS"
    assert payload["apk_metadata"]["status"] == "DEFERRED"
    assert payload["apk_signature"]["status"] == "DEFERRED"
    assert payload["application"]["min_sdk"] == 26


def test_release_artifact_verifier_rejects_secret_like_entry(tmp_path: Path) -> None:
    apk = tmp_path / "bad.apk"
    aab = tmp_path / "app.aab"
    create_zip(apk, {
        "AndroidManifest.xml": b"manifest",
        "classes.dex": b"dex",
        "assets/release.keystore": b"secret",
    })
    create_zip(aab, {
        "BundleConfig.pb": b"bundle",
        "base/manifest/AndroidManifest.xml": b"manifest",
        "base/dex/classes.dex": b"dex",
    })
    result = subprocess.run([
        sys.executable,
        "scripts/verify_release_artifacts.py",
        "--apk", str(apk),
        "--aab", str(aab),
        "--report", str(tmp_path / "bad.json"),
    ], cwd=ROOT, text=True, capture_output=True)
    assert result.returncode != 0
    assert "forbidden secret-like files" in (result.stderr + result.stdout)


def test_release_attestation_round_trip_and_calendar_lock(tmp_path: Path) -> None:
    artifacts = []
    for name, data in (
        ("Church-Prayers-5.2.0.apk", b"apk"),
        ("Church-Prayers-5.2.0.aab", b"aab"),
        ("Church-Prayers-5.2.0-source.zip", b"source"),
        ("Church-Prayers-5.2.0-sbom.cdx.json", b"{}"),
    ):
        path = tmp_path / name
        path.write_bytes(data)
        artifacts.append(path)
    report = tmp_path / "artifact.json"; report.write_text('{"status":"PASS"}\n', encoding="utf-8")
    size = tmp_path / "size.json"; size.write_text('{"status":"PASS"}\n', encoding="utf-8")
    attestation = tmp_path / "attestation.json"
    subprocess.run([
        sys.executable,
        "scripts/generate_release_attestation.py",
        "--apk", str(artifacts[0]),
        "--aab", str(artifacts[1]),
        "--source-zip", str(artifacts[2]),
        "--sbom", str(artifacts[3]),
        "--artifact-report", str(report),
        "--size-report", str(size),
        "--output", str(attestation),
    ], cwd=ROOT, check=True)
    subprocess.run([
        sys.executable,
        "scripts/validate_release_attestation.py",
        str(attestation),
        *sum((["--artifact", str(path)] for path in artifacts), []),
    ], cwd=ROOT, check=True)
    payload = json.loads(attestation.read_text(encoding="utf-8"))
    lock = payload["predicate"]["calendar_lock"]
    assert lock["end"] == "2050-12-31"
    assert lock["day_count"] == 9131
    canonical_lock = json.loads((ROOT / "canonical/calendar_2026_2050_lock.json").read_text(encoding="utf-8"))
    assert lock["aggregate_sha256"] == canonical_lock["aggregate_sha256"]


def test_release_handoff_bundle_is_deterministic_and_secret_free(tmp_path: Path) -> None:
    release = tmp_path / "release"; release.mkdir()
    required = {
        "Church-Prayers-5.2.0.apk": b"apk",
        "Church-Prayers-5.2.0.aab": b"aab",
        "Church-Prayers-5.2.0-source.zip": b"source",
        "Church-Prayers-5.2.0-sbom.cdx.json": b"{}",
        "RELEASE_ARTIFACT_REPORT.json": b"{}",
        "RELEASE_ATTESTATION.json": b"{}",
        "RELEASE_SIZE_REPORT.json": b"{}",
        "RELEASE_PERMISSIONS.txt": b"INTERNET\n",
    }
    for name, data in required.items():
        (release / name).write_bytes(data)
    first = tmp_path / "first.zip"; second = tmp_path / "second.zip"
    for output in (first, second):
        subprocess.run([
            sys.executable,
            "scripts/create_release_handoff_bundle.py",
            "--release-dir", str(release),
            "--version", "5.2.0",
            "--output", str(output),
        ], cwd=ROOT, check=True)
    assert hashlib.sha256(first.read_bytes()).digest() == hashlib.sha256(second.read_bytes()).digest()
    with zipfile.ZipFile(first) as archive:
        assert "RELEASE_HANDOFF_MANIFEST.json" in archive.namelist()


def test_r44_release_qualification_tools_remain_available_after_fast_workflow_refactor() -> None:
    workflow = (ROOT / ".github/workflows/church-prayers.yml").read_text(encoding="utf-8")
    for script in (
        "scripts/verify_release_artifacts.py",
        "scripts/generate_release_attestation.py",
        "scripts/validate_release_attestation.py",
        "scripts/create_release_handoff_bundle.py",
    ):
        assert (ROOT / script).is_file()
    assert "Prepare release signing" in workflow
    assert "Validate release identity and signature requirements" in workflow
    assert "Publish GitHub Release for the updater" in workflow
    assert not (ROOT / ".github/workflows/build.yml").exists()
