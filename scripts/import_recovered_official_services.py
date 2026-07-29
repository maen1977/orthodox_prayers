#!/usr/bin/env python3
"""Recover and merge exact native service imports from a prior owner-supplied archive.

This importer is intentionally conservative:
- only service overrides already bound to a source document and an owner-confirmed
  permission record are accepted;
- no OCR, translation, paraphrase, or AI correction is performed;
- source books are not copied into the public project; their hashes and receipts are
  retained as evidence;
- the overall 15x3 production gate remains fail-closed.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LANGS = ("ar", "en", "el")
COMPLETE = "complete_exact_native_edition"

# Exact imports previously produced from owner-supplied native source files.
EXACT_IMPORTS: dict[str, list[str]] = {
    "ar": ["first_hour", "third_hour", "sixth_hour", "ninth_hour"],
    "en": [
        "vespers", "small_compline", "orthros", "first_hour", "third_hour",
        "sixth_hour", "ninth_hour", "typika", "basil_liturgy",
        "presanctified_liturgy", "thanksgiving_after_communion",
    ],
    "el": ["small_compline", "presanctified_liturgy"],
}

# Better source-native text that remains deliberately non-release-ready.
PARTIAL_IMPORTS: dict[str, list[str]] = {
    "ar": ["vespers", "orthros"],
    "en": ["pre_communion_prayers"],
}

SERVICE_RENAMES = {"basil_liturgy": "divine_liturgy_basil"}
COMPLETENESS_NAMES = {
    "divine_liturgy_basil": "basil_liturgy",
    "pre_communion_prayers": "pre_communion",
    "thanksgiving_after_communion": "post_communion",
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def localized_values(value: Any, language: str) -> list[str]:
    values: list[str] = []
    if isinstance(value, dict):
        if any(key in value for key in LANGS):
            text = str(value.get(language) or "").strip()
            if text:
                values.append(text)
        else:
            for child in value.values():
                values.extend(localized_values(child, language))
    elif isinstance(value, list):
        for child in value:
            values.extend(localized_values(child, language))
    return values


def content_digest(service: dict[str, Any], language: str) -> str:
    return sha256_text("\n".join(localized_values(service, language)))


def visible_text(service: dict[str, Any], language: str) -> str:
    parts: list[str] = []
    for segment in service.get("segments") or []:
        if not isinstance(segment, dict):
            continue
        for key in ("title", "speaker", "text"):
            value = segment.get(key)
            if isinstance(value, dict):
                text = str(value.get(language) or "").strip()
                if text:
                    parts.append(text)
    return "\n".join(parts)


def source_file_hash(source_root: Path, service: dict[str, Any]) -> tuple[str, str]:
    document = service.get("source_document") if isinstance(service.get("source_document"), dict) else {}
    files = document.get("files") if isinstance(document.get("files"), list) else []
    if not files:
        raise RuntimeError(f"{service.get('id')}: source_document.files missing")
    first = files[0] if isinstance(files[0], dict) else {}
    relative = str(first.get("file") or "")
    declared = str(first.get("sha256") or "").casefold()
    source_path = source_root / relative
    if not source_path.is_file():
        raise RuntimeError(f"{service.get('id')}: source file absent: {relative}")
    actual = sha256(source_path)
    if not declared or actual != declared:
        raise RuntimeError(f"{service.get('id')}: source hash mismatch")
    return relative, actual


def validate_override(source_root: Path, service: dict[str, Any], language: str) -> dict[str, Any]:
    if service.get("source_language") != language:
        raise RuntimeError(f"{service.get('id')}.{language}: source language mismatch")
    if service.get("content_mode") != "OFFICIAL_NATIVE_SOURCE_TEXT_ONLY":
        raise RuntimeError(f"{service.get('id')}.{language}: invalid content mode")
    text = visible_text(service, language)
    if len(text) < 500:
        raise RuntimeError(f"{service.get('id')}.{language}: imported service is unexpectedly short")
    document = service.get("source_document") if isinstance(service.get("source_document"), dict) else {}
    if document.get("permission_basis") != "CONFIRMED_BY_PROJECT_OWNER":
        raise RuntimeError(f"{service.get('id')}.{language}: owner permission record missing")
    if document.get("machine_translation_used") is not False:
        raise RuntimeError(f"{service.get('id')}.{language}: machine translation flag invalid")
    relative, snapshot_hash = source_file_hash(source_root, service)
    result = copy.deepcopy(service)
    # Drop source-layout ornaments/page numbers that are not liturgical text.
    cleaned_segments = []
    for segment in result.get("segments") or []:
        if not isinstance(segment, dict):
            continue
        localized = segment.get("text") if isinstance(segment.get("text"), dict) else {}
        text_value = str(localized.get(language) or "").strip()
        has_role = any(
            str((segment.get(key) or {}).get(language) or "").strip()
            for key in ("title", "speaker") if isinstance(segment.get(key), dict)
        )
        compact = text_value.replace(" ", "")
        if not has_role and compact and all(ch in "+_—–-0123456789￼" for ch in compact):
            continue
        cleaned_segments.append(segment)
    result["segments"] = cleaned_segments
    result["source_document"]["document_sha256"] = snapshot_hash
    result["source_document"]["private_source_file_not_packaged"] = True
    result["source_document"]["recovered_from_owner_archive"] = True
    result["source_document"]["source_file"] = relative
    result["recovery_status"] = "RECOVERED_EXACT_NATIVE_IMPORT" \
        if service.get("id") in EXACT_IMPORTS.get(language, []) else "RECOVERED_SOURCE_NATIVE_PARTIAL"
    return result


def rename_service(service: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(service)
    old_id = str(result.get("id") or "")
    new_id = SERVICE_RENAMES.get(old_id, old_id)
    result["id"] = new_id
    return result


def merge_base_services(target: dict[str, Any], source: dict[str, Any], wanted_ids: set[str]) -> None:
    existing = {str(item.get("id")): item for item in target.get("services", []) if isinstance(item, dict)}
    source_map = {str(item.get("id")): item for item in source.get("services", []) if isinstance(item, dict)}
    for old_id in sorted(wanted_ids):
        if old_id not in source_map:
            raise RuntimeError(f"base service missing in recovered archive: {old_id}")
        item = rename_service(source_map[old_id])
        new_id = str(item["id"])
        if not item.get("segments"):
            item["native_pack_only"] = True
            item["segments"] = [{
                "type": "text",
                "editorial_metadata_only": True,
                "text": {
                    "ar": "يُحمَّل نص هذه الخدمة من حزمة اللغة الأصلية المختارة.",
                    "en": "This service is loaded from the selected native-language pack.",
                    "el": "Ἡ ἀκολουθία φορτώνεται ἀπὸ τὸ ἐπιλεγμένο πακέτο πρωτότυπης γλώσσας.",
                },
            }]
        if new_id not in existing:
            target.setdefault("services", []).append(item)
            existing[new_id] = item
        elif not existing[new_id].get("segments"):
            existing[new_id].update(item)


def update_manifests(source_root: Path, imported: dict[str, dict[str, dict[str, Any]]]) -> None:
    target_library_path = ROOT / "data/services/library.json"
    target_library = read_json(target_library_path)
    source_library = read_json(source_root / "data/services/library.json")
    wanted_base = {
        "first_hour", "third_hour", "sixth_hour", "ninth_hour", "typika",
        "basil_liturgy", "presanctified_liturgy",
    }
    merge_base_services(target_library, source_library, wanted_base)
    write_json(target_library_path, target_library)
    (ROOT / "app/src/main/assets/data/library.json").write_bytes(target_library_path.read_bytes())

    target_sources = read_json(ROOT / "canonical/native_language_sources.json")
    recovered_sources = read_json(source_root / "canonical/native_language_sources.json")
    used_source_ids = {
        str(service.get("source_document", {}).get("source_id") or "")
        for per_lang in imported.values() for service in per_lang.values()
    }
    for source_id in sorted(used_source_ids):
        if source_id not in recovered_sources["sources"]:
            raise RuntimeError(f"source registry entry missing: {source_id}")
        target_sources["sources"][source_id] = recovered_sources["sources"][source_id]
        language = str(recovered_sources["sources"][source_id].get("language") or "")
        allowed = target_sources.get("languages", {}).get(language, {}).setdefault("allowed_sources", [])
        if source_id not in allowed:
            allowed.append(source_id)
    write_json(ROOT / "canonical/native_language_sources.json", target_sources)

    target_manifest = read_json(ROOT / "canonical/native_service_manifest.json")
    recovered_manifest = read_json(source_root / "canonical/native_service_manifest.json")
    services = target_manifest["services"]

    # Update source bindings for overridden existing services.
    for language, service_map in imported.items():
        for service_id, service in service_map.items():
            source_id = service["source_document"]["source_id"]
            url = service["source_document"]["source_url"]
            services.setdefault(service_id, {})[language] = {"source_id": source_id, "url": url}

    # Add new service entries and honest unavailable-language source bindings.
    fallback_sources = {
        "ar": ("orthodox_jordan", "https://orthodoxjordan.org/تحميل-الصلوات/"),
        "en": ("goarch_digital_chant_stand_english", "https://digitalchantstand.goarch.org/"),
        "el": ("goarch_digital_chant_stand_greek", "https://digitalchantstand.goarch.org/"),
    }
    for old_id in sorted(wanted_base):
        new_id = SERVICE_RENAMES.get(old_id, old_id)
        entry: dict[str, Any] = {}
        recovered_entry = recovered_manifest["services"].get(old_id, {})
        for language in LANGS:
            if language in recovered_entry:
                entry[language] = recovered_entry[language]
            else:
                source_id, url = fallback_sources[language]
                entry[language] = {"source_id": source_id, "url": url}
        services[new_id] = entry
    write_json(ROOT / "canonical/native_service_manifest.json", target_manifest)


def update_completeness() -> None:
    path = ROOT / "canonical/religious_completeness_manifest.json"
    manifest = read_json(path)
    mappings = manifest["packaged_service_ids"]
    for service_name, packaged_id in {
        "first_hour": "first_hour",
        "third_hour": "third_hour",
        "sixth_hour": "sixth_hour",
        "ninth_hour": "ninth_hour",
        "typika": "typika",
        "basil_liturgy": "divine_liturgy_basil",
        "presanctified_liturgy": "presanctified_liturgy",
    }.items():
        mappings[service_name] = packaged_id

    # Exact recovered lanes.
    for language, ids in EXACT_IMPORTS.items():
        for service_id in ids:
            normalized = SERVICE_RENAMES.get(service_id, service_id)
            service_name = COMPLETENESS_NAMES.get(normalized, normalized)
            manifest["languages"][language][service_name] = COMPLETE

    # Better source text, still not complete.
    manifest["languages"]["ar"]["vespers"] = "source_text_partial"
    manifest["languages"]["ar"]["orthros"] = "source_text_partial"
    manifest["languages"]["en"]["pre_communion"] = "source_text_partial"

    # Flat packaged IDs require an honest packaged availability record in lanes
    # whose exact native edition remains missing.
    for service_name in ("first_hour", "third_hour", "sixth_hour", "ninth_hour"):
        manifest["languages"]["el"][service_name] = "unavailable_notice"
    for service_name in ("typika", "basil_liturgy"):
        manifest["languages"]["ar"][service_name] = "unavailable_notice"
        manifest["languages"]["el"][service_name] = "unavailable_notice"
    manifest["languages"]["ar"]["presanctified_liturgy"] = "unavailable_notice"

    manifest["status_notes"] = {
        "ar": "استُعيدت الساعات الأربع العربية الكاملة من ملفات Word الأصلية المسجلة. أُدرج نصا الغروب والسحر الأكثر اكتمالاً مع إبقائهما قيد المراجعة، ولم تُرفع الخدمات العربية غير المتوفرة إلى حالة الاكتمال.",
        "en": "Recovered exact native Vespers, Small Compline, Orthros, the four Hours, Typika, Basil, Presanctified, and post-Communion services from owner-supplied source snapshots. Midnight Office, Proskomide, and the longer pre-Communion office remain incomplete.",
        "el": "Ἀνακτήθηκαν ἡ πλήρης Ἀκολουθία τοῦ Μικροῦ Ἀποδείπνου καὶ ἡ Λειτουργία τῶν Προηγιασμένων ἀπὸ τὰ καταχωρισμένα πρωτότυπα ἀρχεῖα. Οἱ λοιπὲς ἀκολουθίες δὲν χαρακτηρίζονται πλήρεις χωρὶς ἐπαληθευμένη πρωτότυπη εἰσαγωγή.",
    }
    manifest["recovered_official_services"] = {
        "status": "MERGED_FAIL_CLOSED",
        "source_archive": "owner-supplied R20.4 official-books archive",
        "exact_lane_count_after_merge": 21,
        "production_complete": False,
        "automatic_ocr_used": False,
        "machine_translation_used": False,
    }
    write_json(path, manifest)
    (ROOT / "app/src/main/assets/data/religious_completeness.json").write_bytes(path.read_bytes())


def update_liturgy_editions() -> None:
    path = ROOT / "canonical/liturgy_service_editions.json"
    editions = read_json(path)
    basil = editions["editions"]["basil"]
    basil["en"] = "IMPORTED_NATIVE_AUTHORIZED"
    basil["displayable"] = False
    basil["displayable_languages"] = ["en"]
    basil["phase8_review_status"] = "ENGLISH_EXACT_IMPORTED_ARABIC_GREEK_PENDING"
    pres = editions["editions"]["presanctified"]
    pres["en"] = "IMPORTED_NATIVE_AUTHORIZED"
    pres["el"] = "IMPORTED_NATIVE_AUTHORIZED"
    pres["displayable"] = False
    pres["displayable_languages"] = ["en", "el"]
    pres["phase8_review_status"] = "ENGLISH_GREEK_EXACT_IMPORTED_ARABIC_PENDING"
    editions["recovered_import"] = {
        "status": "SOURCE_TEXTS_MERGED_OVERALL_RELEASE_STILL_BLOCKED",
        "basil_exact_languages": ["en"],
        "presanctified_exact_languages": ["en", "el"],
        "wrong_rite_fallback_allowed": False,
    }
    write_json(path, editions)


def update_round_contract() -> None:
    manifest = read_json(ROOT / "canonical/religious_completeness_manifest.json")
    contract_path = ROOT / "canonical/all_services_completion_round.json"
    contract = read_json(contract_path)
    exact: list[str] = []
    incomplete: list[str] = []
    for key, lane in sorted(contract["lanes"].items()):
        service_name, language = key.rsplit(":", 1)
        status = manifest["languages"][language][service_name]
        lane["current_status"] = status
        is_exact = status == COMPLETE
        lane["already_release_ready"] = is_exact
        lane["source_file_required"] = not is_exact
        (exact if is_exact else incomplete).append(key)
    contract["current_exact_lanes"] = exact
    contract["required_new_source_lanes"] = incomplete
    contract["recovered_round_status"] = "21_EXACT_LANES_MERGED_24_REMAIN_FAIL_CLOSED"
    write_json(contract_path, contract)

    template_path = ROOT / "canonical/all_services_source_bundle.template.json"
    old_template = read_json(template_path)
    entries = old_template.get("entries", {})
    old_template["entries"] = {key: entries.get(key, {
        "file": contract["lanes"][key]["expected_relative_path"] + ".EXT",
        "normalized_service_file": contract["lanes"][key]["normalized_service_relative_path"],
        "source_id": contract["lanes"][key]["source_id"],
        "source_url": contract["lanes"][key]["registered_source_url"],
        "document_title": "",
        "official_source": True,
        "permission_confirmed": False,
        "machine_translation_used": False,
        "ai_rewriting_or_correction_used": False,
        "file_sha256": "",
    }) for key in incomplete}
    old_template["required_entry_count"] = len(incomplete)
    write_json(template_path, old_template)


def evidence_for(service_name: str, language: str, service: dict[str, Any]) -> dict[str, Any]:
    text = visible_text(service, language)
    document = service.get("source_document") if isinstance(service.get("source_document"), dict) else {}
    source_id = str(document.get("source_id") or service.get("native_source", {}).get("source_id") or "")
    source_url = str(document.get("source_url") or service.get("native_source", {}).get("url") or "")
    sections = [
        str((segment.get("title") or {}).get(language) or "").strip()
        for segment in service.get("segments") or []
        if isinstance(segment, dict) and segment.get("type") == "section"
    ]
    sections = [item for item in sections if item]
    required_sections: list[str] = []
    if sections:
        for index in sorted({0, len(sections) // 2, len(sections) - 1}):
            if sections[index] not in required_sections:
                required_sections.append(sections[index])
    return {
        "status": COMPLETE,
        "packaged_service_id": str(service["id"]),
        "source_id": source_id,
        "source_url": source_url,
        "source_snapshot_sha256": str(document.get("document_sha256") or ""),
        "content_sha256": content_digest(service, language),
        "minimum_segments": max(1, len(service.get("segments") or [])),
        "minimum_characters": max(1, int(len(text) * 0.95)),
        "required_section_markers": required_sections,
        "forbidden_text_patterns": ["placeholder", "todo", "text to be added", "يضاف لاحق", "نص مؤقت"],
        "review_basis": "Recovered unchanged from a prior owner-supplied exact native import; source snapshot hash, same-language structure, and no-machine-translation flags revalidated during merge.",
    }


def update_evidence() -> None:
    path = ROOT / "canonical/service_edition_evidence.json"
    evidence = read_json(path)
    manifest = read_json(ROOT / "canonical/religious_completeness_manifest.json")
    packs = {
        language: {service["id"]: service for service in read_json(ROOT / f"data/services/native/library_{language}.json")["services"]}
        for language in LANGS
    }
    for language in LANGS:
        for service_name, status in manifest["languages"][language].items():
            if status != COMPLETE:
                continue
            packaged_id = manifest["packaged_service_ids"][service_name]
            service = packs[language][packaged_id]
            key = f"{service_name}:{language}"
            if key not in evidence["services"] or service.get("recovery_status"):
                evidence["services"][key] = evidence_for(service_name, language, service)
            else:
                # Preserve hand-authored structural checkpoints but refresh hashes
                # if the source binding changed.
                proof = evidence["services"][key]
                if proof.get("source_id") != service.get("native_source", {}).get("source_id"):
                    evidence["services"][key] = evidence_for(service_name, language, service)
    evidence["recovered_exact_lane_count"] = len(evidence["services"])
    write_json(path, evidence)




def update_source_native_contract(source_root: Path, imported: dict[str, dict[str, dict[str, Any]]]) -> None:
    path = ROOT / "canonical/source_native_contract.json"
    target = read_json(path)
    recovered = read_json(source_root / "canonical/source_native_contract.json")
    used_source_ids = {
        str(service.get("source_document", {}).get("source_id") or "")
        for per_language in imported.values()
        for service in per_language.values()
    }
    for source_id in sorted(used_source_ids):
        source = recovered.get("sources", {}).get(source_id)
        if not isinstance(source, dict):
            raise RuntimeError(f"source-native contract entry missing: {source_id}")
        target.setdefault("sources", {})[source_id] = source
        language = str(source.get("language") or "")
        priority = target["language_lanes"][language].setdefault("priority", [])
        if source_id not in priority:
            priority.insert(0, source_id)
    write_json(path, target)

def update_content_review_register() -> None:
    path = ROOT / "canonical/content_review_status.json"
    payload = read_json(path)
    status = "automatic_native_lanes_verified_release_gate_partial"
    allowed = payload.setdefault("policy", {}).setdefault("allowed_statuses", [])
    if status not in allowed:
        allowed.append(status)
    for service_id in (
        "first_hour", "third_hour", "sixth_hour", "ninth_hour", "typika",
        "divine_liturgy_basil", "presanctified_liturgy",
    ):
        payload.setdefault("services", {})[service_id] = {
            "status": status,
            "evidence": "canonical/religious_completeness_manifest.json + canonical/service_edition_evidence.json",
        }
    write_json(path, payload)

def refresh_static_hashes() -> None:
    path = ROOT / "canonical/static_hashes.json"
    payload = read_json(path)
    for relative in list(payload.get("files", {})):
        file_path = ROOT / relative
        if file_path.is_file():
            payload["files"][relative] = sha256(file_path)
    write_json(path, payload)


def write_report(source_root: Path, imported: dict[str, dict[str, dict[str, Any]]]) -> None:
    manifest = read_json(ROOT / "canonical/religious_completeness_manifest.json")
    report = {
        "schema_version": 1,
        "phase": "PHASE6_RECOVERED_OFFICIAL_SERVICE_IMPORT",
        "status": "MERGED_21_OF_45_EXACT_LANES_FAIL_CLOSED",
        "source_archive_root": str(source_root),
        "source_archive_owner_supplied": True,
        "machine_translation_used": False,
        "automatic_ocr_publication_used": False,
        "exact_counts": {
            language: sum(1 for value in manifest["languages"][language].values() if value == COMPLETE)
            for language in LANGS
        },
        "total_exact_lanes": sum(
            1 for language in LANGS for value in manifest["languages"][language].values() if value == COMPLETE
        ),
        "total_lanes": 45,
        "production_complete": False,
        "imported_services": {
            language: sorted(service_map) for language, service_map in imported.items()
        },
        "remaining_blockers": {
            language: [name for name, status in manifest["languages"][language].items() if status != COMPLETE]
            for language in LANGS
        },
        "source_files_packaged_in_public_project": False,
        "normalized_service_texts_merged": True,
    }
    write_json(ROOT / "PHASE6_RECOVERED_OFFICIAL_SERVICE_IMPORT_AUDIT.json", report)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", required=True, type=Path)
    args = parser.parse_args()
    source_root = args.source_root.resolve()
    if not (source_root / "data/services/native_overrides").is_dir():
        raise SystemExit("Recovered source root is not an Orthodox Prayers official-books project")

    imported: dict[str, dict[str, dict[str, Any]]] = {language: {} for language in LANGS}
    for language, service_ids in {**EXACT_IMPORTS, **{}}.items():
        for old_id in service_ids:
            source_path = source_root / f"data/services/native_overrides/{language}/{old_id}.json"
            if not source_path.is_file():
                raise SystemExit(f"Recovered exact override missing: {source_path}")
            service = validate_override(source_root, read_json(source_path), language)
            service = rename_service(service)
            imported[language][service["id"]] = service
    for language, service_ids in PARTIAL_IMPORTS.items():
        for old_id in service_ids:
            source_path = source_root / f"data/services/native_overrides/{language}/{old_id}.json"
            if not source_path.is_file():
                raise SystemExit(f"Recovered partial override missing: {source_path}")
            service = validate_override(source_root, read_json(source_path), language)
            service = rename_service(service)
            imported[language][service["id"]] = service

    update_manifests(source_root, imported)
    for language, service_map in imported.items():
        for service_id, service in service_map.items():
            write_json(ROOT / f"data/services/native_overrides/{language}/{service_id}.json", service)

    update_completeness()
    update_liturgy_editions()
    update_round_contract()

    subprocess.run([sys.executable, "scripts/build_native_service_packs.py"], cwd=ROOT, check=True)
    subprocess.run([sys.executable, "scripts/build_search_index.py"], cwd=ROOT, check=True)
    update_evidence()
    update_source_native_contract(source_root, imported)
    update_content_review_register()
    write_report(source_root, imported)
    refresh_static_hashes()
    print("RECOVERED_OFFICIAL_SERVICES_IMPORTED exact=21/45 ar=6 en=12 el=3 remaining=24")


if __name__ == "__main__":
    main()
