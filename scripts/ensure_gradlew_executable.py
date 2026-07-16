#!/usr/bin/env python3
"""Normalize the Unix execute bits of the trusted Gradle wrapper script.

GitHub's web uploader and Windows worktrees commonly create ``gradlew`` as
mode 0644 even when a source ZIP records it as executable.  This helper changes
permissions only; wrapper bytes are verified separately by
``verify_gradle_wrapper.py`` and the release-contract tests.
"""
from __future__ import annotations

import os
import stat
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "gradlew"


def ensure_gradlew_executable() -> bool:
    """Make gradlew executable on POSIX and return whether its mode changed."""
    if os.name == "nt":
        print("GRADLEW_MODE_OK platform=windows action=not-required")
        return False
    if WRAPPER.is_symlink():
        raise SystemExit("Refusing to chmod a symbolic-link Gradle wrapper")
    if not WRAPPER.is_file():
        raise SystemExit(f"Gradle wrapper is missing or not a regular file: {WRAPPER}")

    current = stat.S_IMODE(WRAPPER.stat().st_mode)
    desired = current | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
    changed = desired != current
    if changed:
        WRAPPER.chmod(desired)
    final = stat.S_IMODE(WRAPPER.stat().st_mode)
    if not final & stat.S_IXUSR:
        raise SystemExit(f"Could not make Gradle wrapper executable: mode={final:04o}")

    action = "normalized" if changed else "already-executable"
    print(f"GRADLEW_MODE_OK platform=posix action={action} mode={final:04o}")
    return changed


if __name__ == "__main__":
    ensure_gradlew_executable()
