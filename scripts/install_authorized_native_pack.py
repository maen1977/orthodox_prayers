#!/usr/bin/env python3
"""Install a reviewed authorized native-language service pack.

The input must contain original text in exactly one language. The command rejects
cross-language leakage, machine-translation flags, unknown services/sources, and
partial packs when --require-complete is requested. It then writes byte-identical
copies for source control and Android offline assets.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "canonical/native_language_sources.json"
MANIFEST = ROOT / "canonical/native_service_manifest.json"
OUTPUTS = (ROOT / "data/services/native", ROOT / "app/src/main/assets/data/native")
LANGS = ("ar", "el", "en")
AR = re.compile(r"[\u0600-\u06ff]")
EL = re.compile(r"[\u0370-\u03ff\u1f00-\u1fff]")
EN = re.compile(r"[A-Za-z]")


def localized_nodes(value: Any, pointer: str = "") -> Iterable[tuple[str, dict[str, Any]]]:
    if isinstance(value, dict):
        if any(key in value for key in LANGS):
            yield pointer, value
        else:
            for key, child in value.items():
                yield from localized_nodes(child, f"{pointer}.{key}" if pointer else key)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from localized_nodes(child, f"{pointer}[{index}]")


def script_valid(language: str, text: str) -> bool:
    if not text.strip():
        return True
    if language == "ar":
        return bool(AR.search(text)) and not bool(EL.search(text))
    if language == "el":
        return bool(EL.search(text)) and not bool(AR.search(text))
    return bool(EN.search(text)) and not bool(AR.search(text) or EL.search(text))


def content_digest(service: dict[str, Any], language: str) -> str:
    pieces = [str(node.get(language) or "").strip() for _, node in localized_nodes(service)]
    return hashlib.sha256("\n".join(item for item in pieces if item).encode("utf-8")).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()

    incoming = json.loads(args.input.read_text(encoding="utf-8"))
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    language = str(incoming.get("language") or "")
    if language not in LANGS:
        raise SystemExit("Pack language must be ar, el, or en")
    if incoming.get("machine_translation_used") is not False:
        raise SystemExit("machine_translation_used must be false")
    if incoming.get("content_mode") != "OFFICIAL_NATIVE_SOURCE_TEXT_ONLY":
        raise SystemExit("content_mode must be OFFICIAL_NATIVE_SOURCE_TEXT_ONLY")

    services = incoming.get("services")
    if not isinstance(services, list):
        raise SystemExit("services must be an array")
    expected_ids = set(manifest["services"])
    actual_ids = {str(item.get("id") or "") for item in services if isinstance(item, dict)}
    if actual_ids != expected_ids:
        raise SystemExit(f"Service IDs differ from manifest; missing={sorted(expected_ids-actual_ids)}, extra={sorted(actual_ids-expected_ids)}")

    allowed = set(registry["languages"][language]["allowed_sources"])
    sources = registry["sources"]
    total = filled = 0
    clean_services: list[dict[str, Any]] = []
    for raw in services:
        service = copy.deepcopy(raw)
        service_id = str(service.get("id") or "")
        source = service.get("native_source") if isinstance(service.get("native_source"), dict) else {}
        source_id = str(source.get("source_id") or "")
        if source_id not in allowed:
            raise SystemExit(f"{service_id}: source {source_id!r} is not allowed for {language}")
        source_entry = sources.get(source_id, {})
        if source_entry.get("official") is not True or source_entry.get("language") != language:
            raise SystemExit(f"{service_id}: source is not an official {language} source")
        if source_entry.get("permission_confirmed") is not True:
            raise SystemExit(f"{service_id}: permission is not recorded")

        service_total = service_filled = 0
        for pointer, node in localized_nodes(service):
            service_total += 1
            text = str(node.get(language) or "").strip()
            if text:
                service_filled += 1
                if not script_valid(language, text):
                    raise SystemExit(f"{service_id}.{pointer}: wrong script for {language}")
            for other in LANGS:
                if other != language and str(node.get(other) or "").strip():
                    raise SystemExit(f"{service_id}.{pointer}: {other} text leaked into {language} pack")
        if args.require_complete and service_filled != service_total:
            raise SystemExit(f"{service_id}: incomplete ({service_filled}/{service_total})")
        total += service_total
        filled += service_filled
        service["source_language"] = language
        service["content_mode"] = "OFFICIAL_NATIVE_SOURCE_TEXT_ONLY"
        service["native_content_status"] = {
            "filled_fields": service_filled,
            "total_fields": service_total,
            "complete": service_filled == service_total,
        }
        source.update({
            "name": source_entry["name"],
            "official": True,
            "native_language": language,
            "permission_confirmed": True,
            "machine_translation_used": False,
            "content_sha256": content_digest(service, language),
            "import_status": "AUTHORIZED_NATIVE_SOURCE_IMPORT" if service_filled else "AUTHORIZED_SOURCE_REGISTERED_TEXT_PENDING",
        })
        service["native_source"] = source
        clean_services.append(service)

    result = copy.deepcopy(incoming)
    result["schema_version"] = 1
    result["language"] = language
    result["content_mode"] = "OFFICIAL_NATIVE_SOURCE_TEXT_ONLY"
    result["machine_translation_used"] = False
    result["permission_basis"] = registry["permission_basis"]
    result["services"] = clean_services
    result["native_content_status"] = {
        "filled_fields": filled,
        "total_fields": total,
        "percent": 100 if total == 0 else round(filled * 100 / total, 1),
        "complete": filled == total,
    }
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    for directory in OUTPUTS:
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f"library_{language}.json").write_text(payload, encoding="utf-8")
    print(f"Installed authorized native {language} pack: {filled}/{total} ({result['native_content_status']['percent']}%)")


if __name__ == "__main__":
    main()
