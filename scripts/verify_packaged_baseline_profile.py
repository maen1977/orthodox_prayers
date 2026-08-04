#!/usr/bin/env python3
"""Verify release APK/AAB contain the compiled Baseline Profile pair."""
from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

PROFILE_SUFFIXES = ("dexopt/baseline.prof", "dexopt/baseline.profm")


def verify(path: Path) -> tuple[str, str]:
    if not path.is_file():
        raise SystemExit(f"Release package is missing: {path}")
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            matches: dict[str, str] = {}
            for suffix in PROFILE_SUFFIXES:
                candidates = [name for name in names if name.endswith(suffix)]
                if len(candidates) != 1:
                    raise SystemExit(
                        f"{path.name} must contain exactly one {suffix}; found {len(candidates)}"
                    )
                info = archive.getinfo(candidates[0])
                if info.file_size < 1:
                    raise SystemExit(f"{path.name} contains an empty {candidates[0]}")
                if info.file_size > 1536 * 1024:
                    raise SystemExit(f"{path.name} Baseline Profile exceeds 1.5 MiB")
                matches[suffix] = candidates[0]
    except zipfile.BadZipFile as error:
        raise SystemExit(f"Invalid Android package ZIP: {path}") from error
    return matches[PROFILE_SUFFIXES[0]], matches[PROFILE_SUFFIXES[1]]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apk", type=Path, required=True)
    parser.add_argument("--aab", type=Path, required=True)
    args = parser.parse_args()

    apk_prof, apk_profm = verify(args.apk)
    aab_prof, aab_profm = verify(args.aab)
    print(
        "PACKAGED_BASELINE_PROFILE_OK "
        f"apk={apk_prof},{apk_profm} aab={aab_prof},{aab_profm}"
    )


if __name__ == "__main__":
    main()
