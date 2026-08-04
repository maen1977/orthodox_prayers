#!/usr/bin/env bash
set -euo pipefail
API_LEVEL="${1:?API level required}"
APP_APK="${2:-app/build/outputs/apk/debug/app-debug.apk}"
TEST_APK="${3:-app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk}"
PACKAGE="com.orthodoxprayers.privateapp"
TEST_PACKAGE="$PACKAGE.test"
RUNNER="$TEST_PACKAGE/androidx.test.runner.AndroidJUnitRunner"
REPORT_DIR="app/build/reports/failure-recovery/api-$API_LEVEL"
mkdir -p "$REPORT_DIR"

adb wait-for-device
adb install -r -t "$APP_APK"
adb install -r -t "$TEST_APK"
adb shell svc wifi disable >/dev/null 2>&1 || true
adb shell svc data disable >/dev/null 2>&1 || true
adb shell am force-stop "$PACKAGE"
adb shell am start -S -W -n "$PACKAGE/.MainActivity" > "$REPORT_DIR/offline-cold-start.txt"
adb shell am instrument -w -r -e class "$PACKAGE.ReaderSmokeTest" "$RUNNER" | tee "$REPORT_DIR/offline-reader.txt"
grep -Eq '^[[:space:]]*OK \([0-9]+ tests?\)[[:space:]]*$' "$REPORT_DIR/offline-reader.txt"
adb shell am force-stop "$PACKAGE"
adb install -r -t "$APP_APK"
adb shell am start -W -n "$PACKAGE/.MainActivity" > "$REPORT_DIR/reinstall-preserve-data.txt"
adb shell am instrument -w -r -e class "$PACKAGE.FailureRecoverySmokeTest" "$RUNNER" | tee "$REPORT_DIR/corrupt-cache-recovery.txt"
grep -Eq '^[[:space:]]*OK \(1 test\)[[:space:]]*$' "$REPORT_DIR/corrupt-cache-recovery.txt"
adb shell svc wifi enable >/dev/null 2>&1 || true
echo "ANDROID_FAILURE_RECOVERY_OK api=$API_LEVEL"
