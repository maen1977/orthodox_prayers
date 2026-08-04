#!/usr/bin/env python3
"""Read and validate the current Android release version without pinning old patch checks."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def current_release() -> tuple[str, int]:
    text = (ROOT / "app/build.gradle.kts").read_text(encoding="utf-8")
    name_match = re.search(r'versionName\s*=\s*"([^"]+)"', text)
    code_match = re.search(r'versionCode\s*=\s*(\d+)', text)
    if not name_match or not code_match:
        raise SystemExit("ANDROID_RELEASE_VERSION_MISSING")
    return name_match.group(1), int(code_match.group(1))


def require_minimum(minimum_code: int) -> tuple[str, int]:
    name, code = current_release()
    if code < minimum_code:
        raise SystemExit(f"ANDROID_RELEASE_VERSION_TOO_OLD current={code} required={minimum_code}")
    return name, code
