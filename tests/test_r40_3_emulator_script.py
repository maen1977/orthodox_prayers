from pathlib import Path
import os
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run_android_emulator_ci.sh"


def test_android_emulator_ci_script_is_valid_bash():
    subprocess.run(["bash", "-n", str(SCRIPT)], check=True)


def test_android_emulator_runner_uses_one_shell_command():
    build = (ROOT / ".github/workflows/build.yml").read_text(encoding="utf-8")
    block = build.split(
        "Run instrumentation and capture Arabic, English, and Greek screens", 1
    )[1].split("Upload generated Play Store screenshots", 1)[0]
    assert 'script: bash scripts/run_android_emulator_ci.sh "${{ matrix.api_level }}"' in block
    assert "script: |" not in block
    assert "for attempt" not in block


def test_android_emulator_ci_script_runs_with_fake_adb(tmp_path: Path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "commands.log"

    adb = bin_dir / "adb"
    adb.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
printf 'adb %s\\n' "$*" >> "$FAKE_LOG"
if [[ "$1" == "shell" && "${2:-}" == "getprop" ]]; then
  printf '1\\r\\n'
fi
exit 0
""",
        encoding="utf-8",
    )
    adb.chmod(0o755)

    gradle = tmp_path / "gradlew"
    gradle.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
printf 'gradle %s\\n' "$*" >> "$FAKE_LOG"
""",
        encoding="utf-8",
    )
    gradle.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env['PATH']}"
    env["FAKE_LOG"] = str(log)
    subprocess.run(
        ["/bin/sh", "-c", f'bash "{SCRIPT}" 29'],
        cwd=tmp_path,
        env=env,
        check=True,
    )
    text = log.read_text(encoding="utf-8")
    assert "adb wait-for-device" in text
    assert "adb shell svc wifi disable" in text
    assert "adb shell svc data disable" in text
    assert "gradle --no-daemon connectedDebugAndroidTest --stacktrace" in text
    assert "adb shell svc wifi enable" in text
    assert "adb shell svc data enable" in text
