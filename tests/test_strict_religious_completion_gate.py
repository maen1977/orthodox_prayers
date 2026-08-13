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


def test_default_gate_accepts_all_forty_five_completed_native_lanes():
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "language=ar verified_complete=15/15" in result.stdout
    assert "language=en verified_complete=15/15" in result.stdout
    assert "language=el verified_complete=15/15" in result.stdout
    assert "RELIGIOUS_COMPLETENESS_OK mode=production" in result.stdout
