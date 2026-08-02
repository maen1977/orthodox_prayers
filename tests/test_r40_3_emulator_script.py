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
if [[ "$1" == "shell" && "${2:-}" == "getprop" && "${3:-}" == "sys.boot_completed" ]]; then
  printf '1\\r\\n'
elif [[ "$1" == "shell" && "${2:-}" == "getprop" && "${3:-}" == "ro.build.version.sdk" ]]; then
  printf '29\\r\\n'
elif [[ "$1" == "shell" && "${2:-}" == "pm" && "${3:-}" == "path" && "${4:-}" == "android" ]]; then
  printf 'package:/system/framework/framework-res.apk\\r\\n'
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
    assert "adb shell getprop sys.boot_completed" in text
    assert "adb shell getprop ro.build.version.sdk" in text
    assert "adb shell pm path android" in text
    assert "gradle --no-daemon connectedDebugAndroidTest --stacktrace" in text
    assert "svc wifi disable" not in text
    assert "svc data disable" not in text


def test_reader_smoke_test_owns_offline_transition():
    reader = (
        ROOT
        / "app/src/androidTest/java/com/orthodoxprayers/privateapp/ReaderSmokeTest.java"
    ).read_text(encoding="utf-8")
    assert '@BeforeClass' in reader
    assert 'executeShellCommand(command)' in reader
    assert 'runShellCommand("svc wifi disable")' in reader
    assert 'runShellCommand("svc data disable")' in reader
    assert 'NET_CAPABILITY_VALIDATED' in reader
    assert '@AfterClass' in reader
    assert 'runShellCommand("svc wifi enable")' in reader
    assert 'runShellCommand("svc data enable")' in reader


def test_instrumentation_job_waits_for_stable_emulator():
    build = (ROOT / ".github/workflows/build.yml").read_text(encoding="utf-8")
    block = build.split(
        "Run instrumentation and capture Arabic, English, and Greek screens", 1
    )[1].split("Upload generated Play Store screenshots", 1)[0]
    assert "emulator-boot-timeout: 900" in block
    assert "ram-size: 2048M" in block
    assert "heap-size: 512M" in block
    assert "-no-snapshot" in block
    assert "-no-boot-anim" not in block
