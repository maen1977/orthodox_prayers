from pathlib import Path
import os
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run_android_emulator_ci.sh"


def test_android_emulator_ci_script_is_valid_bash():
    subprocess.run(["bash", "-n", str(SCRIPT)], check=True)


def test_android_emulator_runner_is_preserved_as_standalone_qualification_tool():
    workflow = (ROOT / ".github/workflows/church-prayers.yml").read_text(encoding="utf-8")
    script = SCRIPT.read_text(encoding="utf-8")
    assert "python scripts/run_local_daily_release_gate.py" in workflow
    assert "testDebugUnitTest lintRelease assembleDebug assembleRelease bundleRelease" in workflow
    assert "26|29|33|35" in script
    assert "am instrument -w -r" in script
    assert not (ROOT / ".github/workflows/build.yml").exists()

def test_android_emulator_ci_script_runs_direct_instrumentation_with_fake_adb(tmp_path: Path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "commands.log"

    adb = bin_dir / "adb"
    adb.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
printf 'adb %s\\n' \"$*\" >> \"$FAKE_LOG\"
if [[ \"$1\" == \"shell\" && \"${2:-}\" == \"getprop\" && \"${3:-}\" == \"sys.boot_completed\" ]]; then
  printf '1\\r\\n'
elif [[ \"$1\" == \"shell\" && \"${2:-}\" == \"getprop\" && \"${3:-}\" == \"ro.build.version.sdk\" ]]; then
  printf '35\\r\\n'
elif [[ \"$1\" == \"shell\" && \"${2:-}\" == \"pm\" && \"${3:-}\" == \"path\" && \"${4:-}\" == \"android\" ]]; then
  printf 'package:/system/framework/framework-res.apk\\r\\n'
elif [[ \"$1\" == \"shell\" && \"${2:-}\" == \"pm\" && \"${3:-}\" == \"list\" && \"${4:-}\" == \"instrumentation\" ]]; then
  printf 'instrumentation:com.orthodoxprayers.privateapp.test/androidx.test.runner.AndroidJUnitRunner (target=com.orthodoxprayers.privateapp)\\n'
elif [[ \"$1\" == \"shell\" && \"${2:-}\" == \"am\" && \"${3:-}\" == \"instrument\" ]]; then
  printf 'OK (4 tests)\\nINSTRUMENTATION_CODE: -1\\n'
fi
exit 0
""",
        encoding="utf-8",
    )
    adb.chmod(0o755)

    app_apk = tmp_path / "app/build/outputs/apk/debug/app-debug.apk"
    test_apk = tmp_path / "app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk"
    app_apk.parent.mkdir(parents=True, exist_ok=True)
    test_apk.parent.mkdir(parents=True, exist_ok=True)
    app_apk.write_bytes(b"app")
    test_apk.write_bytes(b"test")

    python = bin_dir / "python"
    python.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
printf 'python %s\\n' \"$*\" >> \"$FAKE_LOG\"
""",
        encoding="utf-8",
    )
    python.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env['PATH']}"
    env["FAKE_LOG"] = str(log)
    subprocess.run(
        ["/bin/sh", "-c", f'bash "{SCRIPT}" 35'],
        cwd=tmp_path,
        env=env,
        check=True,
    )
    text = log.read_text(encoding="utf-8")
    assert "wait-for-device" in text
    assert "adb shell getprop sys.boot_completed" in text
    assert "adb shell getprop ro.build.version.sdk" in text
    assert "gradle " not in text
    assert "adb install -r -t app/build/outputs/apk/debug/app-debug.apk" in text
    assert "adb install -r -t app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk" in text
    assert "adb shell am instrument -w -r com.orthodoxprayers.privateapp.test/androidx.test.runner.AndroidJUnitRunner" in text
    assert "connectedDebugAndroidTest" not in text


def test_reader_smoke_test_owns_offline_transition():
    reader = (
        ROOT
        / "app/src/androidTest/java/com/orthodoxprayers/privateapp/ReaderSmokeTest.java"
    ).read_text(encoding="utf-8")
    assert "@BeforeClass" in reader
    assert "executeShellCommand(command)" in reader
    assert 'runShellCommand("svc wifi disable")' in reader
    assert 'runShellCommand("svc data disable")' in reader
    assert "NET_CAPABILITY_VALIDATED" in reader
    assert "@AfterClass" in reader
    assert 'runShellCommand("svc wifi enable")' in reader
    assert 'runShellCommand("svc data enable")' in reader


def test_instrumentation_support_files_remain_valid_after_fast_workflow_refactor():
    workflow = (ROOT / ".github/workflows/church-prayers.yml").read_text(encoding="utf-8")
    runner = SCRIPT.read_text(encoding="utf-8")
    host = (ROOT / "scripts/verify_android_emulator_host.sh").read_text(encoding="utf-8")
    assert "testDebugUnitTest lintRelease assembleDebug assembleRelease bundleRelease" in workflow
    assert "collect_android_runtime_metrics.sh" in runner
    assert "am instrument -w -r" in runner
    assert "/dev/kvm" in host
    assert "emulator" in host.lower()
    assert not (ROOT / ".github/workflows/build.yml").exists()

def test_emulator_host_preflight_is_fail_fast_and_valid_bash():
    script = ROOT / "scripts/verify_android_emulator_host.sh"
    subprocess.run(["bash", "-n", str(script)], check=True)
    text = script.read_text(encoding="utf-8")
    assert "test -c /dev/kvm" in text
    assert "test -r /dev/kvm" in text
    assert "test -w /dev/kvm" in text
    assert "emulator -accel-check" in text
    assert "adb start-server" in text
