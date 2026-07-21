#!/usr/bin/env python3
"""Build per-language search documents while preserving exact display text."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from native_text_contract import ROOT, LANGUAGES, search_normalize, sha256_text

ASSET_DIR = ROOT / "app" / "src" / "main" / "assets" / "data" / "search"
DATA_DIR = ROOT / "data" / "search"
SYNONYMS_PATH = ROOT / "canonical" / "search_synonyms.json"


def load_synonyms(lang: str) -> dict[str, list[str]]:
    payload = json.loads(SYNONYMS_PATH.read_text(encoding="utf-8"))
    return {str(key): [str(value) for value in values] for key, values in payload.get("languages", {}).get(lang, {}).items()}


def expand_search_text(value: str, lang: str, synonyms: dict[str, list[str]]) -> str:
    normalized = search_normalize(value, lang)
    additions: list[str] = []
    for key, aliases in synonyms.items():
        group = [key, *aliases]
        normalized_group = [search_normalize(item, lang) for item in group]
        if any(item and item in normalized for item in normalized_group):
            additions.extend(group)
    return search_normalize(value + " " + " ".join(additions), lang)


def localized(value: Any, lang: str) -> str:
    return str(value.get(lang) or "") if isinstance(value, dict) else ""


def service_documents(lang: str, synonyms: dict[str, list[str]]) -> list[dict[str, Any]]:
    path = ROOT / "app" / "src" / "main" / "assets" / "data" / "native" / f"library_{lang}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    documents: list[dict[str, Any]] = []
    for service in data.get("services") or []:
        pieces = []
        for segment in service.get("segments") or []:
            if isinstance(segment, dict):
                text = localized(segment.get("text"), lang) or localized(segment.get("title"), lang)
                if text:
                    pieces.append(text)
        exact = "\n".join(pieces)
        title = localized(service.get("title"), lang)
        summary = localized(service.get("summary"), lang)
        if not (title or exact):
            continue
        documents.append({
            "id": "service:" + str(service.get("id")),
            "type": "service",
            "target_id": service.get("id"),
            "title": title,
            "reference": "",
            "display_text": exact or summary,
            "display_sha256": sha256_text(exact or summary),
            "search_text": expand_search_text(" ".join((title, summary, exact, str(service.get("id") or ""))), lang, synonyms),
            "source": service.get("native_source") or {},
        })
    return documents


def scripture_documents(lang: str, synonyms: dict[str, list[str]]) -> list[dict[str, Any]]:
    path = ROOT / "data" / "scripture" / "native" / lang / "verses.json"
    verses = json.loads(path.read_text(encoding="utf-8"))
    docs = []
    for verse in verses:
        text = verse["text"]
        reference = f"{verse['book_name']} {verse['chapter']}:{verse['verse']}"
        docs.append({
            "id": "scripture:" + verse["id"],
            "type": "scripture",
            "target_id": "scripture:" + verse["id"],
            "title": reference,
            "reference": reference,
            "display_text": text,
            "display_sha256": sha256_text(text),
            "search_text": expand_search_text(reference + " " + text, lang, synonyms),
            "source": {"source_id": verse["source_id"], "url": verse["source_url"]},
        })
    return docs


def pseudo_service(doc: dict[str, Any], lang: str) -> dict[str, Any]:
    loc = {"ar":"", "en":"", "el":""}
    loc[lang] = doc["title"]
    summary = {"ar":"", "en":"", "el":""}
    summary[lang] = doc.get("reference") or ("نص كتابي" if lang == "ar" else "Scripture" if lang == "en" else "Γραφή")
    text = {"ar":"", "en":"", "el":""}
    text[lang] = doc["display_text"]
    source = doc.get("source") or {}
    return {
        "id": doc["target_id"], "category": "scripture", "icon": "📖", "title": loc, "summary": summary,
        "segments": [{"speaker": loc, "text": text}],
        "content_mode": "OFFICIAL_NATIVE_SOURCE_TEXT_ONLY", "source_language": lang,
        "native_source": {"source_id": source.get("source_id"), "url": source.get("url"), "content_sha256": doc["display_sha256"], "machine_translation_used": False},
        "search_only": doc["type"] != "scripture",
    }


def main() -> None:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for lang in LANGUAGES:
        synonyms = load_synonyms(lang)
        docs = service_documents(lang, synonyms) + scripture_documents(lang, synonyms)
        ids = [d["id"] for d in docs]
        if len(ids) != len(set(ids)):
            raise SystemExit(f"duplicate search document IDs for {lang}")
        payload = {
            "schema_version": 1, "language": lang,
            "display_text_policy": "EXACT_SOURCE_TEXT_HASHED; NORMALIZATION_IS_INDEX_ONLY",
            "documents": docs,
            "query_synonyms": synonyms,
            "reader_services": [pseudo_service(d, lang) for d in docs if d["type"] == "scripture"],
        }
        text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        (ASSET_DIR / f"search_index_{lang}.json").write_text(text, encoding="utf-8")
        (DATA_DIR / f"search_index_{lang}.json").write_text(text, encoding="utf-8")
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        print(f"Built {lang} search index: {len(docs)} documents, sha256={digest}")


if __name__ == "__main__":
    main()
