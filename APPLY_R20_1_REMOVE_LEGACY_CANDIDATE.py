#!/usr/bin/env python3
"""Remove the obsolete unsigned rolling-window candidate from Git and disk."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

RELATIVE = Path("data/rolling-week/candidates/2026-07-28")


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, text=True, capture_output=True, check=check)


def main() -> int:
    try:
        root_text = run("git", "rev-parse", "--show-toplevel").stdout.strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("R20_1_FAIL: run this script inside the Git repository root.", file=sys.stderr)
        return 2

    root = Path(root_text).resolve()
    target = root / RELATIVE

    # git rm is essential: deleting only from Explorer or extracting a ZIP does not
    # record removals in Git. --ignore-unmatch also supports partially-applied fixes.
    result = run(
        "git", "rm", "-r", "-f", "--ignore-unmatch", "--", RELATIVE.as_posix(),
        check=False,
    )
    if result.returncode != 0:
        print(result.stdout, end="")
        print(result.stderr, end="", file=sys.stderr)
        return result.returncode

    # Remove any untracked residue left by an overlay extraction.
    if target.exists():
        shutil.rmtree(target)

    tracked = run("git", "ls-files", "--", f"{RELATIVE.as_posix()}/").stdout.strip()
    if tracked:
        print("R20_1_FAIL: legacy files are still tracked:\n" + tracked, file=sys.stderr)
        return 3
    if target.exists():
        print(f"R20_1_FAIL: path still exists: {RELATIVE}", file=sys.stderr)
        return 4

    print(f"R20_1_LEGACY_CANDIDATE_REMOVED path={RELATIVE}")
    print("R20_1_GIT_DELETION_STAGED=true")
    print("Next: git add -A && git commit -m \"Remove legacy unsigned rolling candidate\" && git push")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
