#!/usr/bin/env python3
"""Block a production release until daily Scripture is complete and verifiable.

A release may use an imported official corpus or a registered public-domain native
corpus. The official Orthodox calendar remains the authority for the appointed
reference; the independent corpus supplies only the exact same-language Bible text.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable

from native_text_contract import ROOT, LANGUAGES, load_contract, sha256_text, source_allowed, source_url_allowed

EXACT_STATUSES = {
    "VERIFIED_EXACT_NATIVE_SOURCE",
    "IMPORTED_EXACT_OFFICIAL_NATIVE_CORPUS",
    "IMPORTED_EXACT_PUBLIC_DOMAIN_NATIVE_CORPUS",
}


def reading_lists(data: dict[str, Any]) -> Iterable[list[Any]]:
    if isinstance(data.get("readings"), list):
        yield data["readings"]


def main() -> None:
    errors: list[str] = []
    result = subprocess.run(
        [sys.executable, "scripts/validate_native_language_packs.py", "--require-complete"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        errors.append("Native service packs are incomplete:\n" + (result.stdout + result.stderr).strip())

    contract = load_contract()
    today = json.loads((ROOT / "data" / "calendar" / "today.json").read_text(encoding="utf-8"))
    kinds = {"epistle": False, "gospel": False}
    complete_languages: set[str] = set()

    for readings in reading_lists(today):
        for reading in readings:
            if not isinstance(reading, dict) or reading.get("kind") not in kinds:
                continue
            kind = str(reading["kind"])
            kinds[kind] = True
            verification = reading.get("native_source_verification") or {}
            body = reading.get("body") or {}
            reference = reading.get("reference") or {}
            for language in LANGUAGES:
                text = str(body.get(language) or "").strip()
                ref = str(reference.get(language) or "").strip()
                evidence = verification.get(language) or {}
                status = str(evidence.get("status") or "")
                source_id = str(evidence.get("source_id") or "")
                source_url = str(evidence.get("source_url") or "")
                if not text or not ref or evidence.get("text_available") is not True:
                    errors.append(f"today {kind}: exact {language} text/reference is unavailable")
                    continue
                if status not in EXACT_STATUSES:
                    errors.append(f"today {kind}: {language} evidence status {status!r} is not exact")
                if not source_allowed(language, source_id, contract):
                    errors.append(f"today {kind}: {language} source {source_id!r} is outside its lane")
                if not source_url_allowed(source_id, source_url, contract):
                    errors.append(f"today {kind}: {language} source URL is outside the registered domain")
                if evidence.get("text_sha256") != sha256_text(text):
                    errors.append(f"today {kind}: {language} text hash mismatch")
                if evidence.get("ai_translation_used") is not False:
                    errors.append(f"today {kind}: {language} AI translation flag must be false")
                if evidence.get("automatic_diacritization_used") is not False:
                    errors.append(f"today {kind}: {language} automatic diacritization flag must be false")
                if status in EXACT_STATUSES and text and ref:
                    complete_languages.add(language)

    for kind, found in kinds.items():
        if not found:
            errors.append(f"today: missing {kind} reading")
    for language in LANGUAGES:
        if language not in complete_languages:
            errors.append(f"today: no complete exact Scripture was verified for {language}")

    if errors:
        raise SystemExit("Production release is blocked:\n- " + "\n- ".join(dict.fromkeys(errors)))
    print("Production release readiness validated: complete Arabic, English, and Greek Epistle/Gospel text with exact registered-source evidence")


if __name__ == "__main__":
    main()
