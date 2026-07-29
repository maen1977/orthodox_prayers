#!/usr/bin/env python3
"""Shared exact-text rules for independent Arabic, English, and Greek lanes."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "canonical" / "source_native_contract.json"
LANGUAGES = ("ar", "en", "el")
ARABIC = re.compile(r"[\u0621-\u063a\u0641-\u064a]")
ARABIC_MARKS = re.compile(r"[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed]")
GREEK = re.compile(r"[\u0370-\u03ff\u1f00-\u1fff]")
LATIN = re.compile(r"[A-Za-z]")


def load_contract() -> dict[str, Any]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def exact_display_text(value: str) -> str:
    """Return source text byte-for-character; display text is never normalized."""
    if not isinstance(value, str):
        raise TypeError("religious text must be a string")
    return value


def source_allowed(language: str, source_id: str, contract: dict[str, Any] | None = None) -> bool:
    contract = contract or load_contract()
    return source_id in contract["language_lanes"][language]["priority"]


def source_url_allowed(source_id: str, url: str, contract: dict[str, Any] | None = None) -> bool:
    contract = contract or load_contract()
    source = contract["sources"].get(source_id) or {}
    expected = urlparse(source.get("base_url", ""))
    actual = urlparse(url or "")
    if not expected.hostname or not actual.hostname:
        return False
    return actual.hostname == expected.hostname or actual.hostname.endswith("." + expected.hostname)


def script_errors(language: str, text: str) -> list[str]:
    letters = {
        "ar": len(ARABIC.findall(text)),
        "el": len(GREEK.findall(text)),
        "en": len(LATIN.findall(text)),
    }
    dominant = max(letters, key=letters.get)
    errors: list[str] = []
    if text.strip() and letters[language] == 0:
        errors.append(f"{language}: text has no expected-script letters")
    if text.strip() and dominant != language and letters[dominant] > max(8, letters[language] * 2):
        errors.append(f"{language}: text appears to belong to {dominant}")
    return errors


def diacritic_ratio(text: str) -> float:
    letters = len(ARABIC.findall(text))
    return len(ARABIC_MARKS.findall(text)) / max(letters, 1)


def validate_exact_entry(entry: dict[str, Any], language: str, contract: dict[str, Any] | None = None) -> list[str]:
    contract = contract or load_contract()
    errors: list[str] = []
    text = entry.get("text")
    source_id = str(entry.get("source_id") or "")
    source_url = str(entry.get("source_url") or "")
    if not isinstance(text, str) or not text.strip():
        return ["text is empty"]
    errors.extend(script_errors(language, text))
    if not source_allowed(language, source_id, contract):
        errors.append(f"source {source_id!r} is not allowed for {language}")
    if not source_url_allowed(source_id, source_url, contract):
        errors.append(f"source URL is outside the registered official domain for {source_id}")
    if entry.get("machine_translation_used") is not False:
        errors.append("machine_translation_used must be false")
    if entry.get("automatic_diacritization_used") is not False:
        errors.append("automatic_diacritization_used must be false")
    expected_hash = entry.get("text_sha256")
    if expected_hash and expected_hash != sha256_text(text):
        errors.append("text_sha256 mismatch")
    return errors


def search_normalize(value: str, language: str) -> str:
    """Derived index text only; never returned to the UI as religious text."""
    value = unicodedata.normalize("NFD", value or "")
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    if language == "ar":
        value = value.translate(str.maketrans({"أ":"ا","إ":"ا","آ":"ا","ٱ":"ا","ى":"ي","ؤ":"و","ئ":"ي","ـ":""}))
    value = re.sub(r"\s+", " ", value.casefold()).strip()
    return value
