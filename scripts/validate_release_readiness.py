#!/usr/bin/env python3
"""Block a production release until all native religious content is complete.

Daily updates may safely publish references or "unavailable" states. A signed
production APK/AAB has a stricter contract: all three service packs must be
complete, all three official native Scripture corpora must be imported, and the
current Epistle/Gospel must have exact text in every language.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = ("ar", "en", "el")


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

    for language in LANGUAGES:
        manifest_path = ROOT / "data" / "scripture" / "native" / language / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("status") != "IMPORTED_EXACT_OFFICIAL_NATIVE_CORPUS":
            errors.append(f"{language}: official native Scripture corpus has not been imported")
        if int(manifest.get("verse_count") or 0) <= 0:
            errors.append(f"{language}: Scripture corpus is empty")
        if manifest.get("machine_translation_used") is not False:
            errors.append(f"{language}: machine translation flag must be false")
        if manifest.get("automatic_diacritization_used") is not False:
            errors.append(f"{language}: automatic diacritization flag must be false")

    today = json.loads((ROOT / "data" / "calendar" / "today.json").read_text(encoding="utf-8"))
    kinds = {"epistle": False, "gospel": False}
    for readings in reading_lists(today):
        for reading in readings:
            if not isinstance(reading, dict) or reading.get("kind") not in kinds:
                continue
            kind = str(reading["kind"])
            kinds[kind] = True
            verification = reading.get("native_source_verification") or {}
            body = reading.get("body") or {}
            for language in LANGUAGES:
                evidence = verification.get(language) or {}
                if not str(body.get(language) or "").strip() or evidence.get("text_available") is not True:
                    errors.append(f"today {kind}: exact {language} text is unavailable")
    for kind, found in kinds.items():
        if not found:
            errors.append(f"today: missing {kind} reading")

    if errors:
        raise SystemExit("Production release is blocked:\n- " + "\n- ".join(dict.fromkeys(errors)))
    print("Production release readiness validated: complete native service packs, corpora, and daily Scripture in all three languages")


if __name__ == "__main__":
    main()
