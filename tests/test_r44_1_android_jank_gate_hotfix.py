from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _write_inputs(tmp_path: Path, jank_percent: float, total_frames: int = 120) -> dict[str, Path]:
    values = {
        "cold": "Status: ok\nTotalTime: 1098\nWaitTime: 1200\n",
        "warm": "Status: ok\nTotalTime: 149\nWaitTime: 180\n",
        "home": "TOTAL PSS: 79038\n",
        "reader": "TOTAL PSS: 64211\n",
        "search": "TOTAL PSS: 64015\n",
        "gfx": f"Total frames rendered: {total_frames}\nJanky frames: 119 ({jank_percent}%)\n",
    }
    result: dict[str, Path] = {}
    for name, content in values.items():
        path = tmp_path / f"{name}.txt"
        path.write_text(content, encoding="utf-8")
        result[name] = path
    return result


def _run_parser(tmp_path: Path, mode: str, jank_percent: float, check: bool) -> tuple[subprocess.CompletedProcess[str], dict]:
    files = _write_inputs(tmp_path, jank_percent)
    output = tmp_path / f"metrics-{mode}.json"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/parse_android_runtime_metrics.py",
            "--api-level", "29",
            "--enforcement-mode", mode,
            "--start-output", str(files["cold"]),
            "--warm-start-output", str(files["warm"]),
            "--meminfo-output", str(files["home"]),
            "--reader-meminfo-output", str(files["reader"]),
            "--search-meminfo-output", str(files["search"]),
            "--gfxinfo-output", str(files["gfx"]),
            "--output", str(output),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=check,
    )
    return result, json.loads(output.read_text(encoding="utf-8"))


def test_compatibility_emulator_records_extreme_jank_without_false_release_failure(tmp_path: Path) -> None:
    result, payload = _run_parser(tmp_path, "compatibility", 99.34, check=True)
    assert result.returncode == 0
    assert payload["status"] == "PASS"
    assert payload["jank_enforced"] is False
    assert payload["janky_frames_percent"] == 99.34
    assert payload["total_frames_rendered"] == 120
    assert any("exceeds" in warning for warning in payload["warnings"])


def test_strict_api35_style_gate_still_fails_real_jank_regression(tmp_path: Path) -> None:
    result, payload = _run_parser(tmp_path, "strict", 99.34, check=False)
    assert result.returncode != 0
    assert payload["status"] == "FAIL"
    assert payload["jank_enforced"] is True
    assert any("janky frames" in failure for failure in payload["failures"])


def test_emulator_runner_uses_strict_full_and_diagnostic_compatibility_modes() -> None:
    runner = (ROOT / "scripts/run_android_emulator_ci.sh").read_text(encoding="utf-8")
    collector = (ROOT / "scripts/collect_android_runtime_metrics.sh").read_text(encoding="utf-8")
    reader = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/ReaderScreen.java").read_text(encoding="utf-8")
    assert 'if [[ "$SUITE_MODE" == "full" ]]; then METRICS_MODE="strict"; else METRICS_MODE="compatibility"; fi' in runner
    assert 'ENFORCEMENT_MODE="${3:-${ANDROID_METRICS_MODE:-strict}}"' in collector
    assert "postOnAnimation" in reader
    assert "lastDisplayedProgressPercent" in reader
    subprocess.run(["bash", "-n", str(ROOT / "scripts/run_android_emulator_ci.sh")], check=True)
    subprocess.run(["bash", "-n", str(ROOT / "scripts/collect_android_runtime_metrics.sh")], check=True)
