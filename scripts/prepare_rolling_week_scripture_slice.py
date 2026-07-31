#!/usr/bin/env python3
"""Prepare an exact native Scripture slice for any moving publication horizon.

The date range is read from the canonical Jordan lectionary. The appointed
references are resolved independently in the registered Arabic, English, and
Greek public-domain corpora. No translation, rewriting, or automatic marks are
introduced. The checked-in slice is merged rather than truncated so release
builds remain reproducible offline.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fill_daily_from_native_corpora import parse_reference_parts, passage_verses
from public_domain_scripture import load_public_domain_corpus
from rolling_window_contract import resolve_day_count

ROOT = Path(__file__).resolve().parents[1]
LECTIONARY = ROOT / "canonical/jordan_2026_h2_lectionary.json"
LANGUAGES = ("ar", "en", "el")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical_json_sha(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256_text(payload)


def lectionary_days() -> dict[str, dict[str, Any]]:
    payload = json.loads(LECTIONARY.read_text(encoding="utf-8"))
    return {
        str(item.get("date_iso") or item.get("date") or ""): item
        for item in payload.get("days") or []
        if isinstance(item, dict)
    }


def references_for_range(start: date, day_count: int) -> set[str]:
    """Include the horizon and one preview week for each day's next-Sunday card."""
    days = lectionary_days()
    end = start + timedelta(days=day_count - 1)
    preview_end = end + timedelta(days=7)
    references: set[str] = set()
    cursor = start
    while cursor <= preview_end:
        item = days.get(cursor.isoformat())
        if item is not None:
            blocks = item.get("reading_references") or {}
            for key in ("epistle", "gospel", "matins_gospel"):
                block = blocks.get(key) if isinstance(blocks, dict) else None
                if isinstance(block, dict):
                    canonical = str(block.get("canonical_reference") or "").strip().upper()
                    if canonical:
                        references.add(canonical)
        cursor += timedelta(days=1)
    missing_days = [
        (start + timedelta(days=offset)).isoformat()
        for offset in range(day_count)
        if (start + timedelta(days=offset)).isoformat() not in days
    ]
    if missing_days:
        raise ValueError(
            "canonical Jordan lectionary does not cover the requested horizon: "
            + ", ".join(missing_days[:5])
        )
    if not references:
        raise ValueError("requested horizon contains no canonical Scripture references")
    return references


def required_verses(
    references: set[str],
    index: dict[tuple[str, int, int], dict[str, Any]],
) -> dict[tuple[str, int, int], dict[str, Any]]:
    selected: dict[tuple[str, int, int], dict[str, Any]] = {}
    for canonical in sorted(references):
        parsed = parse_reference_parts(canonical)
        if parsed is None:
            raise ValueError(f"invalid canonical reference in lectionary: {canonical}")
        verses = passage_verses(index, parsed)
        if verses is None:
            raise ValueError(f"registered corpus does not contain the full passage: {canonical}")
        for verse in verses:
            key = (
                str(verse.get("book_id") or "").upper(),
                int(verse.get("chapter") or 0),
                int(verse.get("verse") or 0),
            )
            selected[key] = verse
    return selected


def write_slice(
    language: str,
    source_manifest: dict[str, Any],
    selected: dict[tuple[str, int, int], dict[str, Any]],
    *,
    start: date,
    day_count: int,
    references: set[str],
) -> dict[str, Any]:
    base = ROOT / "data/scripture/native" / language
    verses_path = base / "verses.json"
    manifest_path = base / "manifest.json"
    existing = json.loads(verses_path.read_text(encoding="utf-8")) if verses_path.is_file() else []
    merged: dict[tuple[str, int, int], dict[str, Any]] = {}
    for item in existing:
        if not isinstance(item, dict):
            continue
        key = (
            str(item.get("book_id") or "").upper(),
            int(item.get("chapter") or 0),
            int(item.get("verse") or 0),
        )
        if key[0] and key[1] > 0 and key[2] > 0:
            merged[key] = item

    source_id = str(source_manifest.get("source_id") or "")
    source_url = str(source_manifest.get("source_url") or "")
    for key, item in selected.items():
        text = str(item.get("text") or "")
        if not text.strip():
            raise ValueError(f"{language}: empty native verse {key}")
        merged[key] = {
            "automatic_diacritization_used": False,
            "book_id": key[0],
            "book_name": str(item.get("book_name") or key[0]),
            "chapter": key[1],
            "id": f"{key[0]}.{key[1]}.{key[2]}",
            "machine_translation_used": False,
            "source_id": source_id,
            "source_url": source_url,
            "text": text,
            "text_sha256": sha256_text(text),
            "verse": key[2],
        }

    verses = [merged[key] for key in sorted(merged)]
    verses_path.parent.mkdir(parents=True, exist_ok=True)
    verses_path.write_text(json.dumps(verses, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    persisted = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
    end = start + timedelta(days=day_count - 1)
    persisted.update(
        {
            "status": "IMPORTED_EXACT_PUBLIC_DOMAIN_NATIVE_CORPUS",
            "source_id": source_id,
            "source_url": source_url,
            "source_title": source_manifest.get("source_title", persisted.get("source_title", "")),
            "license": source_manifest.get("license", persisted.get("license", "Public Domain")),
            "verse_count": len(verses),
            "books": sorted({item["book_id"] for item in verses}),
            "machine_translation_used": False,
            "automatic_diacritization_used": False,
            "display_text_policy": "PRESERVE_SOURCE_UNICODE_CODEPOINTS_EXACTLY",
            "rolling_window_start": start.isoformat(),
            "rolling_window_end": end.isoformat(),
            "rolling_window_day_count": day_count,
            "rolling_window_reference_count": len(references),
            "rolling_window_required_verse_count": len(selected),
            "rolling_window_slice_prepared_at": datetime.now(timezone.utc).isoformat(),
            "content_sha256": canonical_json_sha(verses),
        }
    )
    for legacy_key in (
        "rolling_week_start",
        "rolling_week_end",
        "rolling_week_required_verse_count",
        "rolling_week_slice_prepared_at",
    ):
        persisted.pop(legacy_key, None)
    manifest_path.write_text(json.dumps(persisted, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "stored_verses": len(verses),
        "required_present": len(selected),
        "source_id": source_id,
        "content_sha256": persisted["content_sha256"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--days", type=int, default=None)
    args = parser.parse_args()
    start = date.fromisoformat(args.start_date)
    day_count = resolve_day_count(args.days)
    references = references_for_range(start, day_count)

    report: dict[str, Any] = {
        "schema_version": 2,
        "rolling_window_start": start.isoformat(),
        "rolling_window_end": (start + timedelta(days=day_count - 1)).isoformat(),
        "rolling_window_day_count": day_count,
        "canonical_reference_count": len(references),
        "languages": {},
    }
    expected_keys: set[tuple[str, int, int]] | None = None
    for language in LANGUAGES:
        manifest, index = load_public_domain_corpus(language)
        selected = required_verses(references, index)
        keys = set(selected)
        if expected_keys is None:
            expected_keys = keys
        elif keys != expected_keys:
            raise ValueError(f"{language}: native corpus range differs from the other language lanes")
        report["languages"][language] = write_slice(
            language,
            manifest,
            selected,
            start=start,
            day_count=day_count,
            references=references,
        )

    report["required_unique_verses_per_language"] = len(expected_keys or set())
    out = ROOT / "build/rolling-window/scripture-slice-audit.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
