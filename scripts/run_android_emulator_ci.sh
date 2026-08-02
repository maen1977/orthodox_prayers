#!/usr/bin/env bash
set -euo pipefail

API_LEVEL="${1:?Android API level is required}"
ADB_TIMEOUT_SECONDS="${ADB_TIMEOUT_SECONDS:-20}"

adb_command() {
  timeout --preserve-status "${ADB_TIMEOUT_SECONDS}s" adb "$@"
}

adb_shell() {
  adb_command shell "$@"
}

wait_for_android_framework() {
  local attempt boot sdk package_path stable
  adb wait-for-device
  stable=0

  for ((attempt = 1; attempt <= 120; attempt++)); do
    boot="$(adb_shell getprop sys.boot_completed 2>/dev/null | tr -d '\r' || true)"
    sdk="$(adb_shell getprop ro.build.version.sdk 2>/dev/null | tr -d '\r' || true)"
    package_path="$(adb_shell pm path android 2>/dev/null | tr -d '\r' || true)"

    if [[ "$boot" == "1" && "$sdk" == "$API_LEVEL" && "$package_path" == package:* ]]; then
      stable=$((stable + 1))
      if ((stable >= 3)); then
        echo "Android framework ready: api=$sdk stable_probes=$stable"
        return 0
      fi
    else
      stable=0
    fi
    sleep 2
  done

  echo "Android emulator framework did not become stable for API $API_LEVEL" >&2
  adb devices -l >&2 || true
  adb shell getprop >&2 || true
  return 1
}

wait_for_android_framework

# The APKs are prebuilt before the emulator action starts. Keeping the device
# discovery phase free of network-service mutations prevents DDMLib from
# caching an Unknown API Level while Android system services are still settling.
./gradlew --no-daemon connectedDebugAndroidTest --stacktrace

if [[ "$API_LEVEL" == "35" ]]; then
  mkdir -p play-store/assets/screenshots
  adb_command pull /sdcard/Android/data/com.orthodoxprayers.privateapp/files/store-screenshots/. play-store/assets/screenshots/
  python scripts/validate_play_store_assets.py --require-screenshots
fi
