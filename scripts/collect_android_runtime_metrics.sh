#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API_LEVEL="${1:?Android API level is required}"
OUTPUT="${2:-app/build/reports/performance/runtime-api-$API_LEVEL.json}"
ENFORCEMENT_MODE="${3:-${ANDROID_METRICS_MODE:-strict}}"
PACKAGE="com.orthodoxprayers.privateapp"
ACTIVITY="$PACKAGE/.MainActivity"
SCREEN_EXTRA="$PACKAGE.extra.SCREEN"
ARGUMENT_EXTRA="$PACKAGE.extra.ARGUMENT"
RAW_DIR="app/build/outputs/android-performance/api-$API_LEVEL"
mkdir -p "$RAW_DIR" "$(dirname "$OUTPUT")"

case "$ENFORCEMENT_MODE" in
  strict|compatibility) ;;
  *) echo "Unsupported Android metrics enforcement mode: $ENFORCEMENT_MODE" >&2; exit 2 ;;
esac

adb shell settings put global window_animation_scale 0 >/dev/null 2>&1 || true
adb shell settings put global transition_animation_scale 0 >/dev/null 2>&1 || true
adb shell settings put global animator_duration_scale 0 >/dev/null 2>&1 || true

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

# Use the emulator's actual display size so the gesture remains valid for every profile.
DISPLAY_SIZE="$(adb shell wm size 2>/dev/null | tr -d '\r' | grep -Eo '[0-9]+x[0-9]+' | tail -1 || true)"
DISPLAY_WIDTH="${DISPLAY_SIZE%x*}"
DISPLAY_HEIGHT="${DISPLAY_SIZE#*x}"
if [[ ! "$DISPLAY_WIDTH" =~ ^[0-9]+$ || ! "$DISPLAY_HEIGHT" =~ ^[0-9]+$ ]]; then
  DISPLAY_WIDTH=1080
  DISPLAY_HEIGHT=1920
fi
SWIPE_X=$((DISPLAY_WIDTH / 2))
SWIPE_FROM=$((DISPLAY_HEIGHT * 78 / 100))
SWIPE_TO=$((DISPLAY_HEIGHT * 22 / 100))

# Warm the reader before resetting gfxinfo so first layout, font rasterization, and
# RecyclerView creation are not misclassified as scrolling jank.
for _ in 1 2; do
  adb shell input swipe "$SWIPE_X" "$SWIPE_FROM" "$SWIPE_X" "$SWIPE_TO" 650 >/dev/null 2>&1 || true
  sleep 0.35
done
sleep 1
adb shell dumpsys gfxinfo "$PACKAGE" reset >/dev/null 2>&1 || true

# Capture a longer, controlled sample. Compatibility emulators report this metric
# diagnostically; API 35 remains the strict render-performance gate.
for _ in 1 2 3 4; do
  adb shell input swipe "$SWIPE_X" "$SWIPE_FROM" "$SWIPE_X" "$SWIPE_TO" 650 >/dev/null 2>&1 || true
  sleep 0.35
done
sleep 1
adb shell dumpsys gfxinfo "$PACKAGE" > "$RAW_DIR/gfxinfo-reader.txt" || true

adb shell am start -W -n "$ACTIVITY" --es "$SCREEN_EXTRA" search > "$RAW_DIR/am-start-search.txt"
sleep 2
adb shell dumpsys meminfo "$PACKAGE" > "$RAW_DIR/meminfo-search.txt"

python "$SCRIPT_DIR/parse_android_runtime_metrics.py" \
  --api-level "$API_LEVEL" \
  --enforcement-mode "$ENFORCEMENT_MODE" \
  --start-output "$RAW_DIR/am-start-cold.txt" \
  --warm-start-output "$RAW_DIR/am-start-warm.txt" \
  --meminfo-output "$RAW_DIR/meminfo-home.txt" \
  --reader-meminfo-output "$RAW_DIR/meminfo-reader.txt" \
  --search-meminfo-output "$RAW_DIR/meminfo-search.txt" \
  --gfxinfo-output "$RAW_DIR/gfxinfo-reader.txt" \
  --output "$OUTPUT"
