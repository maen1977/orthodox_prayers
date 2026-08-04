#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API_LEVEL="${1:?Android API level is required}"
OUTPUT="${2:-app/build/reports/performance/runtime-api-$API_LEVEL.json}"
PACKAGE="com.orthodoxprayers.privateapp"
ACTIVITY="$PACKAGE/.MainActivity"
SCREEN_EXTRA="$PACKAGE.extra.SCREEN"
ARGUMENT_EXTRA="$PACKAGE.extra.ARGUMENT"
RAW_DIR="app/build/outputs/android-performance/api-$API_LEVEL"
mkdir -p "$RAW_DIR" "$(dirname "$OUTPUT")"

adb shell am force-stop "$PACKAGE"
adb shell cmd package compile --reset "$PACKAGE" >/dev/null 2>&1 || true
adb shell am start -S -W -n "$ACTIVITY" > "$RAW_DIR/am-start-cold.txt"
sleep 2
adb shell dumpsys meminfo "$PACKAGE" > "$RAW_DIR/meminfo-home.txt"

adb shell input keyevent KEYCODE_HOME
sleep 1
adb shell am start -W -n "$ACTIVITY" > "$RAW_DIR/am-start-warm.txt"

adb shell am start -W -n "$ACTIVITY" --es "$SCREEN_EXTRA" reader --es "$ARGUMENT_EXTRA" divine_liturgy > "$RAW_DIR/am-start-reader.txt"
sleep 2
adb shell dumpsys meminfo "$PACKAGE" > "$RAW_DIR/meminfo-reader.txt"
adb shell dumpsys gfxinfo "$PACKAGE" reset >/dev/null 2>&1 || true
for _ in 1 2 3 4 5 6; do
  adb shell input swipe 540 1500 540 450 240 >/dev/null 2>&1 || true
  sleep 0.2
done
adb shell dumpsys gfxinfo "$PACKAGE" > "$RAW_DIR/gfxinfo-reader.txt" || true

adb shell am start -W -n "$ACTIVITY" --es "$SCREEN_EXTRA" search > "$RAW_DIR/am-start-search.txt"
sleep 2
adb shell dumpsys meminfo "$PACKAGE" > "$RAW_DIR/meminfo-search.txt"

python "$SCRIPT_DIR/parse_android_runtime_metrics.py" \
  --api-level "$API_LEVEL" \
  --start-output "$RAW_DIR/am-start-cold.txt" \
  --warm-start-output "$RAW_DIR/am-start-warm.txt" \
  --meminfo-output "$RAW_DIR/meminfo-home.txt" \
  --reader-meminfo-output "$RAW_DIR/meminfo-reader.txt" \
  --search-meminfo-output "$RAW_DIR/meminfo-search.txt" \
  --gfxinfo-output "$RAW_DIR/gfxinfo-reader.txt" \
  --output "$OUTPUT"
