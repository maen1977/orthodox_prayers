#!/usr/bin/env bash
set -euo pipefail

API_LEVEL="${1:?Android API level is required}"

wait_for_android_boot() {
  local attempt
  adb wait-for-device
  for ((attempt = 1; attempt <= 60; attempt++)); do
    if [[ "$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" == "1" ]]; then
      return 0
    fi
    sleep 2
  done
  echo "Android emulator did not finish booting" >&2
  return 1
}

retry_adb_shell() {
  local attempt
  for ((attempt = 1; attempt <= 5; attempt++)); do
    if adb shell "$@"; then
      return 0
    fi
    sleep 2
  done
  echo "adb shell command failed after retries: $*" >&2
  return 1
}

restore_network() {
  retry_adb_shell svc wifi enable || true
  retry_adb_shell svc data enable || true
}

wait_for_android_boot
trap restore_network EXIT

retry_adb_shell svc wifi disable
retry_adb_shell svc data disable

./gradlew --no-daemon connectedDebugAndroidTest --stacktrace

restore_network
trap - EXIT

if [[ "$API_LEVEL" == "35" ]]; then
  mkdir -p play-store/assets/screenshots
  adb pull /sdcard/Android/data/com.orthodoxprayers.privateapp/files/store-screenshots/. play-store/assets/screenshots/
  python scripts/validate_play_store_assets.py --require-screenshots
fi
