from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_android_resource_contract_passes() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/validate_android_resources.py"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    assert "ANDROID_RESOURCES_OK" in completed.stdout


def test_android_13_monochrome_launcher_is_present() -> None:
    icon = ROOT / "app/src/main/res/mipmap-anydpi-v33/ic_launcher.xml"
    text = icon.read_text(encoding="utf-8")
    assert "<monochrome" in text
    assert "@drawable/ic_launcher_monochrome" in text
