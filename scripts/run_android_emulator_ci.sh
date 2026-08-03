#!/usr/bin/env bash
set -euo pipefail

API_LEVEL="${1:-35}"
EXPECTED_API_LEVEL="35"
ADB_TIMEOUT_SECONDS="${ADB_TIMEOUT_SECONDS:-30}"
ADB_WAIT_TIMEOUT_SECONDS="${ADB_WAIT_TIMEOUT_SECONDS:-180}"
ADB_INSTALL_TIMEOUT_SECONDS="${ADB_INSTALL_TIMEOUT_SECONDS:-180}"
ADB_INSTRUMENT_TIMEOUT_SECONDS="${ADB_INSTRUMENT_TIMEOUT_SECONDS:-1200}"
ADB_PULL_TIMEOUT_SECONDS="${ADB_PULL_TIMEOUT_SECONDS:-180}"
REPORT_DIR="app/build/reports/androidTests/direct"
DIAGNOSTICS_DIR="app/build/outputs/androidTest-diagnostics"
INSTRUMENTATION_LOG="$REPORT_DIR/instrumentation-api-$API_LEVEL.txt"
APP_APK="app/build/outputs/apk/debug/app-debug.apk"
TEST_APK="app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk"
TEST_RUNNER="com.orthodoxprayers.privateapp.test/androidx.test.runner.AndroidJUnitRunner"

if [[ "$API_LEVEL" != "$EXPECTED_API_LEVEL" ]]; then
  echo "This workflow intentionally runs one stable runtime emulator: API $EXPECTED_API_LEVEL; got API $API_LEVEL" >&2
  exit 2
fi

mkdir -p "$REPORT_DIR" "$DIAGNOSTICS_DIR"

adb_timed() {
  local timeout_seconds="$1"
  shift
  timeout --preserve-status "${timeout_seconds}s" adb "$@"
}

adb_command() {
  adb_timed "$ADB_TIMEOUT_SECONDS" "$@"
}

adb_shell() {
  adb_command shell "$@"
}

collect_diagnostics() {
  local status=$?
  if command -v adb >/dev/null 2>&1; then
    adb devices -l > "$DIAGNOSTICS_DIR/adb-devices.txt" 2>&1 || true
    adb_command shell getprop > "$DIAGNOSTICS_DIR/getprop.txt" 2>&1 || true
    adb_command shell dumpsys package com.orthodoxprayers.privateapp > "$DIAGNOSTICS_DIR/package.txt" 2>&1 || true
    adb_command logcat -d -v threadtime > "$DIAGNOSTICS_DIR/logcat.txt" 2>&1 || true
    adb_command exec-out screencap -p > "$DIAGNOSTICS_DIR/final-screen.png" 2>/dev/null || true
  fi
  exit "$status"
}
trap collect_diagnostics EXIT

wait_for_android_framework() {
  local attempt boot sdk package_path stable
  adb_timed "$ADB_WAIT_TIMEOUT_SECONDS" wait-for-device
  stable=0

  for ((attempt = 1; attempt <= 150; attempt++)); do
    boot="$(adb_shell getprop sys.boot_completed 2>/dev/null | tr -d '\r' || true)"
    sdk="$(adb_shell getprop ro.build.version.sdk 2>/dev/null | tr -d '\r' || true)"
    package_path="$(adb_shell pm path android 2>/dev/null | tr -d '\r' || true)"

    if [[ "$boot" == "1" && "$sdk" == "$API_LEVEL" && "$package_path" == package:* ]]; then
      stable=$((stable + 1))
      if ((stable >= 5)); then
        echo "Android framework ready: api=$sdk stable_probes=$stable"
        return 0
      fi
    else
      stable=0
    fi
    sleep 2
  done

  echo "Android emulator framework did not become stable for API $API_LEVEL" >&2
  return 1
}

wait_for_android_framework

# APKs are built before the emulator starts. This keeps Gradle compilation out
# of the resource-sensitive emulator window and makes boot/test failures easier
# to diagnose.
test -s "$APP_APK"
test -s "$TEST_APK"

adb_timed "$ADB_INSTALL_TIMEOUT_SECONDS" install -r -t "$APP_APK"
adb_timed "$ADB_INSTALL_TIMEOUT_SECONDS" install -r -t "$TEST_APK"

if ! adb_shell pm list instrumentation | tr -d '\r' | grep -Fq "instrumentation:$TEST_RUNNER"; then
  echo "Android test runner was not registered: $TEST_RUNNER" >&2
  adb_shell pm list instrumentation >&2 || true
  exit 1
fi

set +e
adb_timed "$ADB_INSTRUMENT_TIMEOUT_SECONDS" shell am instrument -w -r "$TEST_RUNNER" 2>&1 | tr -d '\r' | tee "$INSTRUMENTATION_LOG"
instrumentation_status=${PIPESTATUS[0]}
set -e

if ((instrumentation_status != 0)); then
  echo "Android instrumentation command failed with status $instrumentation_status" >&2
  exit "$instrumentation_status"
fi

if grep -Eq 'FAILURES!!!|INSTRUMENTATION_FAILED|Process crashed|shortMsg=' "$INSTRUMENTATION_LOG"; then
  echo "Android instrumentation reported a test or process failure" >&2
  exit 1
fi

if ! grep -Eq '^[[:space:]]*OK \([0-9]+ tests?\)[[:space:]]*$' "$INSTRUMENTATION_LOG"; then
  echo "Android instrumentation did not report a successful JUnit completion" >&2
  exit 1
fi

mkdir -p play-store/assets/screenshots
adb_timed "$ADB_PULL_TIMEOUT_SECONDS" pull /sdcard/Android/data/com.orthodoxprayers.privateapp/files/store-screenshots/. play-store/assets/screenshots/
python scripts/validate_play_store_assets.py --require-screenshots

trap - EXIT
collect_diagnostics
