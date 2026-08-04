#!/usr/bin/env bash
set -euo pipefail
API_LEVEL="${1:?API level required}"
PREVIOUS_APK="${2:?Previous APK required}"
CURRENT_APK="${3:?Current APK required}"
TEST_APK="${4:?Instrumentation APK required}"
PACKAGE="com.orthodoxprayers.privateapp"
TEST_PACKAGE="$PACKAGE.test"
RUNNER="$TEST_PACKAGE/androidx.test.runner.AndroidJUnitRunner"
REPORT_DIR="app/build/reports/upgrade/api-$API_LEVEL"
mkdir -p "$REPORT_DIR"

run_phase() {
  local phase="$1" method="$2"
  adb shell am instrument -w -r \
    -e upgradePhase "$phase" \
    -e class "$PACKAGE.UpgradePersistenceTest#$method" \
    "$RUNNER" | tee "$REPORT_DIR/$phase.txt"
  grep -Eq '^[[:space:]]*OK \(1 test\)[[:space:]]*$' "$REPORT_DIR/$phase.txt"
}

adb wait-for-device
adb uninstall "$TEST_PACKAGE" >/dev/null 2>&1 || true
adb uninstall "$PACKAGE" >/dev/null 2>&1 || true
adb install -t "$PREVIOUS_APK"
adb install -t "$TEST_APK"
run_phase seed seedLegacyState
adb shell am force-stop "$PACKAGE"
adb install -r -t "$CURRENT_APK"
adb shell am start -W -n "$PACKAGE/.MainActivity" > "$REPORT_DIR/update-launch.txt"
run_phase verify verifyStateAfterUpgrade
adb shell dumpsys package "$PACKAGE" > "$REPORT_DIR/package-after-upgrade.txt"
echo "ANDROID_UPGRADE_OK api=$API_LEVEL previous=$(basename "$PREVIOUS_APK") current=$(basename "$CURRENT_APK")"
