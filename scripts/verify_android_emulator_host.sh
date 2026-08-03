#!/usr/bin/env bash
set -euo pipefail

DIAGNOSTICS_DIR="app/build/outputs/androidTest-diagnostics"
mkdir -p "$DIAGNOSTICS_DIR"

{
  echo "runner_os=${RUNNER_OS:-unknown}"
  echo "runner_arch=${RUNNER_ARCH:-unknown}"
  echo "kernel=$(uname -a)"
  echo "cpus=$(nproc)"
  free -h || true
  ls -l /dev/kvm
} | tee "$DIAGNOSTICS_DIR/emulator-host.txt"

test -c /dev/kvm
test -r /dev/kvm
test -w /dev/kvm

# This command is available after android-emulator-runner installs the emulator
# package and before it launches the AVD. Its non-zero status is a fail-fast
# signal that hardware acceleration is unavailable or misconfigured.
emulator -accel-check 2>&1 | tee "$DIAGNOSTICS_DIR/emulator-accel-check.txt"

adb kill-server >/dev/null 2>&1 || true
adb start-server
adb version | tee "$DIAGNOSTICS_DIR/adb-version.txt"
