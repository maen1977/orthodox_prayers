#!/usr/bin/env python3
"""Compatibility entry point: translations are forbidden; validate native lanes."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", default="data/calendar/today.json")
    parser.add_argument("--language", choices=("ar", "en", "el"))
    args = parser.parse_args()

    command = [sys.executable, "scripts/validate_daily_native_content.py", args.path]
    if args.language:
        command.extend(["--language", args.language])
    subprocess.run(command, cwd=ROOT, check=True)
    print(
        "Scripture policy validated: no cross-language translation; "
        f"only exact same-language official text may be non-empty language={args.language or 'all'}"
    )


if __name__ == "__main__":
    main()
