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


def test_default_gate_blocks_production_while_arabic_orthros_is_unreadable():
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.returncode != 0
    assert "language=ar verified_complete=14/15" in result.stdout
    assert "production completeness is 14/15" in result.stderr
