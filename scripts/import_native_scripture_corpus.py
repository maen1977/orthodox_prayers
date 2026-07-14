#!/usr/bin/env python3
"""Import an owner-authorized official native-language Scripture snapshot.

Input JSON format:
{
  "language": "ar|en|el",
  "source_id": "registered source id",
  "source_url": "official URL",
  "retrieved_at": "ISO timestamp",
  "verses": [{"book_id":"MAT","book_name":"...","chapter":1,"verse":1,"text":"exact source text"}]
}
The importer never translates, corrects, rewraps, or automatically adds marks.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from native_text_contract import ROOT, LANGUAGES, exact_display_text, load_contract, sha256_text, source_allowed, source_url_allowed, script_errors


def fail(message: str) -> None:
    raise SystemExit(message)


def canonical_payload(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--replace", action="store_true", help="replace a previously imported corpus")
    args = parser.parse_args()
    raw = json.loads(args.input.read_text(encoding="utf-8"))
    language = raw.get("language")
    if language not in LANGUAGES:
        fail("language must be ar, en, or el")
    contract = load_contract()
    source_id = str(raw.get("source_id") or "")
    source_url = str(raw.get("source_url") or "")
    if not source_allowed(language, source_id, contract):
        fail(f"{source_id!r} is not registered for the {language} lane")
    if "scripture_corpus" not in contract["sources"][source_id].get("capabilities", []):
        fail(f"{source_id!r} is not registered as a Scripture-corpus source")
    if not source_url_allowed(source_id, source_url, contract):
        fail("source_url is outside the registered official domain")
    verses = raw.get("verses")
    if not isinstance(verses, list) or not verses:
        fail("verses must be a non-empty list")

    normalized: list[dict[str, Any]] = []
    seen: set[tuple[str, int, int]] = set()
    errors: list[str] = []
    for index, item in enumerate(verses):
        if not isinstance(item, dict):
            errors.append(f"verses[{index}] is not an object")
            continue
        book_id = str(item.get("book_id") or "").strip().upper()
        book_name = str(item.get("book_name") or "").strip()
        try:
            chapter = int(item.get("chapter"))
            verse = int(item.get("verse"))
        except Exception:
            errors.append(f"verses[{index}] has invalid chapter/verse")
            continue
        text = exact_display_text(str(item.get("text") or ""))
        key = (book_id, chapter, verse)
        if not book_id or not book_name or chapter < 1 or verse < 1 or not text.strip():
            errors.append(f"verses[{index}] has missing required fields")
            continue
        if key in seen:
            errors.append(f"duplicate verse {book_id}.{chapter}.{verse}")
            continue
        seen.add(key)
        for error in script_errors(language, text):
            errors.append(f"verses[{index}]: {error}")
        normalized.append({
            "id": f"{book_id}.{chapter}.{verse}",
            "book_id": book_id,
            "book_name": book_name,
            "chapter": chapter,
            "verse": verse,
            "text": text,
            "text_sha256": sha256_text(text),
            "source_id": source_id,
            "source_url": source_url,
            "machine_translation_used": False,
            "automatic_diacritization_used": False,
        })
    if errors:
        fail("\n".join(errors))
    normalized.sort(key=lambda x: (x["book_id"], x["chapter"], x["verse"]))

    out_dir = ROOT / "data" / "scripture" / "native" / language
    manifest_path = out_dir / "manifest.json"
    existing = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    if existing.get("verse_count", 0) and not args.replace:
        fail("corpus already exists; pass --replace for an explicit replacement")
    books = []
    for item in normalized:
        if item["book_id"] not in books:
            books.append(item["book_id"])
    payload_hash = hashlib.sha256(canonical_payload(normalized)).hexdigest()
    retrieved_at = str(raw.get("retrieved_at") or datetime.now(timezone.utc).isoformat())
    manifest = {
        "schema_version": 1,
        "language": language,
        "contract": "canonical/source_native_contract.json",
        "status": "IMPORTED_EXACT_OFFICIAL_NATIVE_CORPUS",
        "source_id": source_id,
        "source_url": source_url,
        "retrieved_at": retrieved_at,
        "imported_at": datetime.now(timezone.utc).isoformat(),
        "verse_count": len(normalized),
        "books": books,
        "machine_translation_used": False,
        "automatic_diacritization_used": False,
        "display_text_policy": "PRESERVE_SOURCE_UNICODE_CODEPOINTS_EXACTLY",
        "source_snapshot_sha256": hashlib.sha256(args.input.read_bytes()).hexdigest(),
        "content_sha256": payload_hash,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "verses.json").write_bytes(canonical_payload(normalized))
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Imported {len(normalized)} exact {language} verses from {source_id}; sha256={payload_hash}")


if __name__ == "__main__":
    main()
