#!/usr/bin/env python3
"""Validate three independent official native-language service libraries."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "canonical/native_language_sources.json"
MANIFEST_PATH = ROOT / "canonical/native_service_manifest.json"
PACK_DIR = ROOT / "data/services/native"
LANGS = ("ar", "el", "en")
AR = re.compile(r"[\u0600-\u06ff]")
EL = re.compile(r"[\u0370-\u03ff\u1f00-\u1fff]")
EN = re.compile(r"[A-Za-z]")


def iter_localized(value: Any, pointer: str = "") -> Iterable[tuple[str, dict[str, Any]]]:
    if isinstance(value, dict):
        if any(key in value for key in LANGS):
            yield pointer, value
        else:
            for key, child in value.items():
                yield from iter_localized(child, f"{pointer}.{key}" if pointer else key)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from iter_localized(child, f"{pointer}[{index}]")


def script_valid(lang: str, text: str) -> bool:
    if not text.strip():
        return True
    if lang == "ar":
        return bool(AR.search(text)) and not bool(EL.search(text))
    if lang == "el":
        return bool(EL.search(text)) and not bool(AR.search(text))
    return bool(EN.search(text)) and not bool(AR.search(text) or EL.search(text))


def digest_text(service: dict[str, Any], lang: str) -> str:
    pieces = [str(obj.get(lang) or "").strip() for _, obj in iter_localized(service)]
    pieces = [item for item in pieces if item]
    return hashlib.sha256("\n".join(pieces).encode("utf-8")).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-complete", action="store_true")
    parser.add_argument("--report", type=Path, help="Optional JSON coverage report path")
    args = parser.parse_args()

    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    allowed = {lang: set(registry["languages"][lang]["allowed_sources"]) for lang in LANGS}
    source_registry = registry["sources"]
    expected_services = set(manifest["services"])
    errors: list[str] = []
    report: dict[str, Any] = {"content_mode": manifest["content_mode"], "languages": {}}

    for lang in LANGS:
        path = PACK_DIR / f"library_{lang}.json"
        if not path.exists():
            errors.append(f"missing {path.relative_to(ROOT)}")
            continue
        pack = json.loads(path.read_text(encoding="utf-8"))
        if pack.get("language") != lang:
            errors.append(f"{path.name}: wrong language")
        if pack.get("machine_translation_used") is not False:
            errors.append(f"{path.name}: machine translation must be false")
        services = pack.get("services") if isinstance(pack.get("services"), list) else []
        ids = {service.get("id") for service in services if isinstance(service, dict)}
        if ids != expected_services:
            errors.append(f"{path.name}: service IDs differ from manifest")

        total = filled = 0
        per_service: dict[str, Any] = {}
        for service in services:
            if not isinstance(service, dict):
                errors.append(f"{path.name}: invalid service object")
                continue
            service_id = str(service.get("id") or "")
            source = service.get("native_source") if isinstance(service.get("native_source"), dict) else {}
            source_id = str(source.get("source_id") or "")
            if source_id not in allowed[lang]:
                errors.append(f"{service_id}.{lang}: disallowed source {source_id!r}")
            registry_entry = source_registry.get(source_id, {})
            if registry_entry.get("language") != lang or registry_entry.get("official") is not True:
                errors.append(f"{service_id}.{lang}: source is not official native-language source")
            if source.get("permission_confirmed") is not True:
                errors.append(f"{service_id}.{lang}: permission not recorded")
            if source.get("machine_translation_used") is not False:
                errors.append(f"{service_id}.{lang}: machine translation flag is invalid")
            if source.get("content_sha256") != digest_text(service, lang):
                errors.append(f"{service_id}.{lang}: content hash mismatch")

            service_total = service_filled = 0
            for pointer, localized in iter_localized(service):
                service_total += 1
                text = str(localized.get(lang) or "").strip()
                if text:
                    service_filled += 1
                    if not script_valid(lang, text):
                        errors.append(f"{service_id}.{pointer}: text does not match {lang} script")
                for other in LANGS:
                    if other != lang and str(localized.get(other) or "").strip():
                        errors.append(f"{service_id}.{pointer}: {other} text leaked into {lang} pack")
            total += service_total
            filled += service_filled
            percent = 100 if service_total == 0 else round(service_filled * 100 / service_total, 1)
            per_service[service_id] = {"filled": service_filled, "total": service_total, "percent": percent}
            if args.require_complete and service_filled != service_total:
                errors.append(f"{service_id}.{lang}: incomplete native pack ({service_filled}/{service_total})")

        declared = pack.get("native_content_status") if isinstance(pack.get("native_content_status"), dict) else {}
        expected_percent = 100 if total == 0 else round(filled * 100 / total, 1)
        if declared.get("filled_fields") != filled or declared.get("total_fields") != total:
            errors.append(f"{path.name}: declared native content counts do not match")
        if declared.get("percent") != expected_percent or declared.get("complete") is not (filled == total):
            errors.append(f"{path.name}: declared native content completeness does not match")
        report["languages"][lang] = {
            "filled": filled,
            "total": total,
            "percent": expected_percent,
            "complete": filled == total,
            "services": per_service,
        }

    if args.report:
        report_path = args.report if args.report.is_absolute() else ROOT / args.report
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for lang, stats in report["languages"].items():
        print(f"{lang}: {stats['filled']}/{stats['total']} ({stats['percent']}%)")
    if errors:
        raise SystemExit("\n".join(errors))
    print("Native-language source packs validated")


if __name__ == "__main__":
    main()
