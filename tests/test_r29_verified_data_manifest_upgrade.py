from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _prepare_fixture(root: Path, manifest_minimum: int, contract_minimum: int) -> str:
    date_iso = json.loads((ROOT / "data/calendar/today.json").read_text(encoding="utf-8"))["date_iso"]
    shutil.copytree(ROOT / "data", root / "data")
    (root / "canonical/signing").mkdir(parents=True)
    (root / "scripts").mkdir()
    for name in ("build_update_manifest.py", "sign_update_manifest.py", "verify_update_manifest.py"):
        shutil.copy2(ROOT / "scripts" / name, root / "scripts" / name)
    (root / "canonical/update_contract.json").write_text(
        json.dumps(
            {
                "manifest_schema_version": 1,
                "minimum_app_version_code": contract_minimum,
                "policy": "test",
            }
        ),
        encoding="utf-8",
    )
    private_key = root / "private.pem"
    public_key = root / "canonical/signing/data_signing_public_key.pub"
    subprocess.run(
        ["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(private_key)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    subprocess.run(
        ["openssl", "pkey", "-in", str(private_key), "-pubout", "-out", str(public_key)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    subprocess.run(
        [
            sys.executable,
            "scripts/build_update_manifest.py",
            "--date",
            date_iso,
            "--revision",
            "29",
            "--minimum-app-version-code",
            str(manifest_minimum),
            "--published-at-utc",
            f"{date_iso}T00:00:00Z",
        ],
        cwd=root,
        check=True,
        stdout=subprocess.DEVNULL,
    )
    subprocess.run(
        [sys.executable, "scripts/sign_update_manifest.py", "--private-key", str(private_key)],
        cwd=root,
        check=True,
        stdout=subprocess.DEVNULL,
    )
    return date_iso


def test_older_signed_manifest_is_accepted_only_in_import_compatibility_mode() -> None:
    with tempfile.TemporaryDirectory(prefix="orthodox-r29-") as directory:
        root = Path(directory)
        date_iso = _prepare_fixture(root, manifest_minimum=50013, contract_minimum=50023)
        strict = subprocess.run(
            [sys.executable, "scripts/verify_update_manifest.py", "--expected-date", date_iso],
            cwd=root,
            text=True,
            capture_output=True,
        )
        assert strict.returncode != 0
        assert "manifest minimum app version differs" in strict.stderr + strict.stdout
        compatible = subprocess.run(
            [
                sys.executable,
                "scripts/verify_update_manifest.py",
                "--expected-date",
                date_iso,
                "--allow-compatible-minimum-version",
            ],
            cwd=root,
            text=True,
            capture_output=True,
        )
        assert compatible.returncode == 0, compatible.stderr + compatible.stdout
        assert "UPDATE_MANIFEST_COMPATIBLE_MINIMUM manifest=50013 app=50023" in compatible.stdout


def test_manifest_requiring_newer_app_is_rejected_even_in_compatibility_mode() -> None:
    with tempfile.TemporaryDirectory(prefix="orthodox-r29-newer-") as directory:
        root = Path(directory)
        date_iso = _prepare_fixture(root, manifest_minimum=50024, contract_minimum=50023)
        result = subprocess.run(
            [
                sys.executable,
                "scripts/verify_update_manifest.py",
                "--expected-date",
                date_iso,
                "--allow-compatible-minimum-version",
            ],
            cwd=root,
            text=True,
            capture_output=True,
        )
        assert result.returncode != 0
        assert "manifest requires a newer app" in result.stderr + result.stdout


def test_debug_build_uses_compatible_manifest_import_but_update_publish_stays_strict() -> None:
    build = (ROOT / ".github/workflows/build.yml").read_text(encoding="utf-8")
    update = (ROOT / ".github/workflows/update.yml").read_text(encoding="utf-8")
    assert "--allow-compatible-manifest-version" in build
    assert "--allow-compatible-minimum-version" not in update
