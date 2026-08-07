#!/usr/bin/env python3
"""Validate store listing, privacy, and Data Safety source metadata."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    required = [
        ROOT / "PRIVACY.md",
        ROOT / "docs/privacy/index.html",
        ROOT / "play-store/DATA_SAFETY_AR.md",
        ROOT / "play-store/PLAY_CONSOLE_CHECKLIST_AR.md",
        ROOT / "play-store/STORE_LISTING_AR.md",
        ROOT / "play-store/STORE_LISTING_EN.md",
        ROOT / "play-store/STORE_LISTING_EL.md",
    ]
    for path in required:
        if not path.is_file() or path.stat().st_size < 300:
            raise SystemExit(f"Play metadata is missing or empty: {path.relative_to(ROOT)}")
    combined = "\n".join(path.read_text(encoding="utf-8") for path in required)
    for obsolete in ("v4.2.0", "targetSdk` على API 35"):
        if obsolete in combined:
            raise SystemExit(f"obsolete Play metadata remains: {obsolete}")
    for marker in (
        "https://maen1977.github.io/orthodox_prayers/privacy/",
        "com.orthodoxprayers.privateapp",
        "لا إعلانات",
        "no ads",
        "χωρὶς διαφημίσεις",
    ):
        if marker.casefold() not in combined.casefold():
            raise SystemExit(f"Play metadata marker is missing: {marker}")
    print("PLAY_STORE_METADATA_OK languages=ar,en,el privacy=true data_safety=true version=5.4.0")


if __name__ == "__main__":
    main()
