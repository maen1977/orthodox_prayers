import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_religious_completeness.py"


def test_declaration_audit_remains_available():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--declaration-only"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "mode=declaration" in result.stdout


def test_default_gate_allows_complete_production_release():
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    for language in ("ar", "en", "el"):
        assert f"language={language} verified_complete=15/15" in result.stdout
