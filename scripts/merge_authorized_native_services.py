#!/usr/bin/env python3
"""Merge reviewed native-language fields into the existing service pack.

The input may contain one or more complete or sparse service objects. Only non-empty
localized fields in the declared language are copied, and every pointer must already
exist in the canonical service shape. Existing text is protected unless the caller
passes --replace-existing explicitly.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

from install_authorized_native_pack import (
    LANGS,
    MANIFEST,
    OUTPUTS,
    REGISTRY,
    content_digest,
    localized_nodes,
    script_valid,
)

ROOT = Path(__file__).resolve().parents[1]


def count_fields(service: dict[str, Any], language: str) -> tuple[int, int]:
    total = filled = 0
    for _, node in localized_nodes(service):
        total += 1
        if str(node.get(language) or "").strip():
            filled += 1
    return total, filled


def merge_localized_fields(
    current: dict[str, Any],
    submitted: dict[str, Any],
    language: str,
    *,
    replace_existing: bool,
) -> int:
    """Copy submitted native fields into matching canonical pointers."""
    current_nodes = {pointer: node for pointer, node in localized_nodes(current)}
    merged = 0
    for pointer, node in localized_nodes(submitted):
        text = str(node.get(language) or "").strip()
        if not text:
            continue
        if not script_valid(language, text):
            raise SystemExit(f"{current.get('id')}.{pointer}: wrong script for {language}")
        for other in LANGS:
            if other != language and str(node.get(other) or "").strip():
                raise SystemExit(f"{current.get('id')}.{pointer}: {other} text leaked into {language} pack")
        target = current_nodes.get(pointer)
        if target is None:
            raise SystemExit(f"{current.get('id')}.{pointer}: pointer is not present in the canonical service shape")
        existing = str(target.get(language) or "").strip()
        if existing and existing != text and not replace_existing:
            raise SystemExit(
                f"{current.get('id')}.{pointer}: existing native text differs; "
                "use --replace-existing only after deliberate review"
            )
        if existing != text:
            target[language] = text
            merged += 1
    return merged


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--require-submitted-complete", action="store_true")
    parser.add_argument("--replace-existing", action="store_true")
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
    submitted = incoming.get("services")
    if not isinstance(submitted, list) or not submitted:
        raise SystemExit("services must be a non-empty array")

    expected_ids = set(manifest["services"])
    submitted_ids = [str(item.get("id") or "") for item in submitted if isinstance(item, dict)]
    if len(submitted_ids) != len(submitted):
        raise SystemExit("Every submitted service must be an object with an id")
    if len(submitted_ids) != len(set(submitted_ids)):
        raise SystemExit("Duplicate service IDs in submitted pack")
    unknown = sorted(set(submitted_ids) - expected_ids)
    if unknown:
        raise SystemExit("Unknown service IDs: " + ", ".join(unknown))

    target = ROOT / "data/services/native" / f"library_{language}.json"
    current = json.loads(target.read_text(encoding="utf-8"))
    by_id = {str(item.get("id") or ""): copy.deepcopy(item) for item in current.get("services", [])}
    allowed = set(registry["languages"][language]["allowed_sources"])
    sources = registry["sources"]
    total_merged = 0

    for raw in submitted:
        service_id = str(raw.get("id") or "")
        if service_id not in by_id:
            raise SystemExit(f"Current pack is missing required service {service_id}")
        source = raw.get("native_source") if isinstance(raw.get("native_source"), dict) else {}
        source_id = str(source.get("source_id") or "")
        if source_id not in allowed:
            raise SystemExit(f"{service_id}: source {source_id!r} is not allowed for {language}")
        source_entry = sources.get(source_id, {})
        if source_entry.get("official") is not True or source_entry.get("language") != language:
            raise SystemExit(f"{service_id}: source is not an official {language} source")
        if source_entry.get("permission_confirmed") is not True:
            raise SystemExit(f"{service_id}: permission is not recorded")

        submitted_nodes = list(localized_nodes(raw))
        if not submitted_nodes:
            raise SystemExit(f"{service_id}: no localized fields were submitted")
        if args.require_submitted_complete:
            missing = [pointer for pointer, node in submitted_nodes if not str(node.get(language) or "").strip()]
            if missing:
                raise SystemExit(f"{service_id}: submitted subset contains empty fields ({len(missing)})")

        merged_service = by_id[service_id]
        merged = merge_localized_fields(
            merged_service,
            raw,
            language,
            replace_existing=args.replace_existing,
        )
        if merged == 0:
            raise SystemExit(f"{service_id}: no new or changed native fields were supplied")
        total_merged += merged

        service_total, service_filled = count_fields(merged_service, language)
        merged_service["source_language"] = language
        merged_service["content_mode"] = "OFFICIAL_NATIVE_SOURCE_TEXT_ONLY"
        merged_service["native_content_status"] = {
            "filled_fields": service_filled,
            "total_fields": service_total,
            "complete": service_filled == service_total,
        }
        normalized_source = copy.deepcopy(source)
        normalized_source.update({
            "name": source_entry["name"],
            "official": True,
            "native_language": language,
            "permission_confirmed": True,
            "machine_translation_used": False,
            "content_sha256": content_digest(merged_service, language),
            "import_status": "AUTHORIZED_NATIVE_SOURCE_IMPORT",
        })
        merged_service["native_source"] = normalized_source

    ordered = []
    for service_id in manifest["services"]:
        if service_id not in by_id:
            raise SystemExit(f"Current pack is missing required service {service_id}")
        ordered.append(by_id[service_id])

    pack_total = pack_filled = 0
    for service in ordered:
        total, filled = count_fields(service, language)
        pack_total += total
        pack_filled += filled
        service["native_content_status"] = {
            "filled_fields": filled,
            "total_fields": total,
            "complete": filled == total,
        }

    result = copy.deepcopy(current)
    result["services"] = ordered
    result["native_content_status"] = {
        "filled_fields": pack_filled,
        "total_fields": pack_total,
        "percent": 100 if pack_total == 0 else round(pack_filled * 100 / pack_total, 1),
        "complete": pack_filled == pack_total,
    }
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    for directory in OUTPUTS:
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f"library_{language}.json").write_text(payload, encoding="utf-8")
    print(
        f"Merged {total_merged} authorized {language} field(s) across "
        f"{len(submitted)} service(s): {pack_filled}/{pack_total} "
        f"({result['native_content_status']['percent']}%)"
    )


if __name__ == "__main__":
    main()
