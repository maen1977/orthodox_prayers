#!/usr/bin/env python3
"""Validate concise, native Play Store release notes for every app language."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTES = ROOT / "play-store/release-notes"
FILES = {"ar": NOTES / "ar.txt", "en": NOTES / "en.txt", "el": NOTES / "el.txt"}
PLACEHOLDERS = re.compile(r"(?i)todo|tbd|placeholder|lorem ipsum|ضع هنا|لاحقاً")


def main() -> None:
    results: list[str] = []
    for language, path in FILES.items():
        if not path.is_file():
            raise SystemExit(f"Missing Play release notes: {path.relative_to(ROOT)}")
        text = " ".join(path.read_text(encoding="utf-8").split())
        if len(text) < 80 or len(text) > 500:
            raise SystemExit(
                f"Play release notes length is invalid for {language}: {len(text)} characters"
            )
        if PLACEHOLDERS.search(text):
            raise SystemExit(f"Play release notes contain a placeholder: {language}")
        if "http://" in text or "https://" in text:
            raise SystemExit(f"Play release notes must not contain a URL: {language}")
        if language == "ar" and not re.search(r"[\u0600-\u06ff]", text):
            raise SystemExit("Arabic release notes contain no Arabic text")
        if language == "el" and not re.search(r"[\u0370-\u03ff\u1f00-\u1fff]", text):
            raise SystemExit("Greek release notes contain no Greek text")
        results.append(f"{language}={len(text)}")
    print("PLAY_RELEASE_NOTES_OK " + " ".join(results))


if __name__ == "__main__":
    main()
