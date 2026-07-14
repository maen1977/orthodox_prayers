#!/usr/bin/env python3
"""Audit independent English and Greek native-source coverage without pretending unfinished content is complete.

By default this command writes a report and succeeds. Use --strict to require the
configured minimum. The Android UI enables all interface languages, but only
renders religious text in a target language when this audit considers it valid.
Unverified text is marked unavailable and the official source text can be shown.
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARABIC_RE = re.compile(r"[\u0600-\u06ff]")
LATIN_RE = re.compile(r"[A-Za-z]")
GREEK_RE = re.compile(r"[\u0370-\u03ff\u1f00-\u1fff]")


@dataclass
class Stats:
    total: int = 0
    valid: int = 0
    missing: int = 0
    copied_arabic: int = 0
    wrong_script: int = 0

    def percent(self) -> float:
        return round((self.valid * 100.0 / self.total), 2) if self.total else 100.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "valid": self.valid,
            "missing": self.missing,
            "copied_arabic": self.copied_arabic,
            "wrong_script": self.wrong_script,
            "coverage_percent": self.percent(),
        }


def clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def assess(ar: str, value: str, language: str, stats: Stats) -> None:
    stats.total += 1
    if not value:
        stats.missing += 1
        return
    if value == ar or ARABIC_RE.search(value):
        stats.copied_arabic += 1
        return
    expected = LATIN_RE if language == "en" else GREEK_RE
    if not expected.search(value):
        stats.wrong_script += 1
        return
    stats.valid += 1


def walk(value: Any, en: Stats, el: Stats) -> None:
    if isinstance(value, dict):
        if "ar" in value and ("en" in value or "el" in value) and all(
            not isinstance(value.get(key), (dict, list)) for key in ("ar", "en", "el")
        ):
            ar = clean(value.get("ar"))
            if ar:
                assess(ar, clean(value.get("en")), "en", en)
                assess(ar, clean(value.get("el")), "el", el)
        for child in value.values():
            walk(child, en, el)
    elif isinstance(value, list):
        for child in value:
            walk(child, en, el)


def audit(paths: list[Path]) -> dict[str, Any]:
    en, el = Stats(), Stats()
    for path in paths:
        walk(json.loads(path.read_text(encoding="utf-8")), en, el)
    return {
        "policy": {
            "complete_language_threshold_percent": 90,
            "rule": "A target-language native field is valid only when non-empty, not copied from Arabic, and written in the target script.",
            "ui_behavior": "All interface languages are enabled. Invalid or missing religious native text are never replaced by Arabic; they are marked unavailable with an option to show the official source text.",
        },
        "files": [str(path.relative_to(ROOT)) for path in paths],
        "en": en.as_dict(),
        "el": el.as_dict(),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--write-report", action="store_true", help="Write reports/translation_coverage.json for a manual audit.")
    parser.add_argument(
        "--reject-invalid",
        action="store_true",
        help="Fail when any non-empty target-language value is copied Arabic or uses the wrong script.",
    )
    parser.add_argument("--minimum", type=float, default=90.0)
    parser.add_argument("paths", nargs="*")
    args = parser.parse_args()
    paths = [ROOT / item for item in args.paths] if args.paths else [
        ROOT / "data/calendar/today.json",
        ROOT / "app/src/main/assets/data/library.json",
    ]
    report = audit(paths)
    print(
        "Native-language coverage: "
        f"English {report['en']['coverage_percent']}%, "
        f"Greek {report['el']['coverage_percent']}%"
    )
    if args.write_report:
        out = ROOT / "reports/translation_coverage.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Report: {out.relative_to(ROOT)}")
    if args.reject_invalid:
        invalid = {
            lang: report[lang]["copied_arabic"] + report[lang]["wrong_script"]
            for lang in ("en", "el")
        }
        failed_invalid = [lang for lang, count in invalid.items() if count]
        if failed_invalid:
            raise SystemExit(
                "Invalid target-language content found for: " + ", ".join(failed_invalid)
            )
    if args.strict:
        failed = [lang for lang in ("en", "el") if report[lang]["coverage_percent"] < args.minimum]
        if failed:
            raise SystemExit(
                "Native-language coverage is below the strict threshold for: " + ", ".join(failed)
            )


if __name__ == "__main__":
    main()
