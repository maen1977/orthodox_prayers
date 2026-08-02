#!/usr/bin/env python3
"""Validate permissions extracted from the final APK by apkanalyzer."""
from __future__ import annotations

import argparse
from pathlib import Path

ALLOWED = {
    "android.permission.INTERNET",
    "android.permission.ACCESS_NETWORK_STATE",
    "android.permission.POST_NOTIFICATIONS",
    "android.permission.RECEIVE_BOOT_COMPLETED",
    "android.permission.VIBRATE",
    "android.permission.WAKE_LOCK",
    "android.permission.FOREGROUND_SERVICE",
}
FORBIDDEN_PREFIXES = (
    "android.permission.ACCESS_FINE_LOCATION",
    "android.permission.ACCESS_COARSE_LOCATION",
    "android.permission.READ_CONTACTS",
    "android.permission.WRITE_CONTACTS",
    "android.permission.CAMERA",
    "android.permission.RECORD_AUDIO",
    "android.permission.READ_SMS",
    "android.permission.SEND_SMS",
    "android.permission.READ_CALL_LOG",
    "android.permission.WRITE_CALL_LOG",
    "android.permission.READ_PHONE_STATE",
    "android.permission.MANAGE_EXTERNAL_STORAGE",
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    lines = [line.strip() for line in args.path.read_text(encoding="utf-8").splitlines() if line.strip()]
    permissions = {line.split("'", 2)[1] if "'" in line else line.split()[-1] for line in lines}
    forbidden = sorted(permission for permission in permissions if permission.startswith(FORBIDDEN_PREFIXES))
    if forbidden:
        raise SystemExit("forbidden release permissions: " + ", ".join(forbidden))
    unknown = sorted(permission for permission in permissions if permission.startswith("android.permission.") and permission not in ALLOWED)
    if unknown:
        raise SystemExit("unreviewed release permissions: " + ", ".join(unknown))
    print("RELEASE_PERMISSIONS_OK " + ",".join(sorted(permissions)))


if __name__ == "__main__":
    main()
