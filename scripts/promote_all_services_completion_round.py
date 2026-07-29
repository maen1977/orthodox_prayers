#!/usr/bin/env python3
"""Build an all-services completed project from reviewed candidates.

All incomplete lanes must be present and approved. Work occurs in an isolated
staging copy. No runtime file in the active project changes unless --apply is
explicitly supplied and every post-promotion validator passes.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build_native_liturgy_review_packet import candidate_hash  # noqa: E402

CONTRACT = ROOT / "canonical/all_services_completion_round.json"
LANGS = ("ar", "en", "el")
TOUCHED = (
    "data/services/library.json",
    "app/src/main/assets/data/library.json",
    "canonical/native_service_manifest.json",
    "canonical/religious_completeness_manifest.json",
    "app/src/main/assets/data/religious_completeness.json",
    "canonical/liturgy_service_editions.json",
    "canonical/service_edition_evidence.json",
    "canonical/static_hashes.json",
    "data/services/native_overrides",
    "data/services/native",
    "app/src/main/assets/data/native",
)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def iter_localized(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        if value.get("editorial_metadata_only") is True:
            return
        if any(key in value for key in LANGS):
            yield value
        else:
            for child in value.values():
                yield from iter_localized(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_localized(child)


def digest_text(service: dict[str, Any], language: str) -> str:
    values = [str(item.get(language) or "").strip() for item in iter_localized(service)]
    return hashlib.sha256("\n".join(value for value in values if value).encode("utf-8")).hexdigest()


def visible_text(service: dict[str, Any], language: str) -> str:
    values: list[str] = []
    for segment in service.get("segments") or []:
        if not isinstance(segment, dict) or segment.get("editorial_metadata_only") is True:
            continue
        for key in ("title", "speaker", "text"):
            localized = segment.get(key)
            if isinstance(localized, dict):
                text = str(localized.get(language) or "").strip()
                if text:
                    values.append(text)
    return "\n".join(values)


def validate_reviewed_candidate(payload: dict[str, Any], lane_key: str, lane: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    language = lane["language"]
    if payload.get("status") != "CANDIDATE_REQUIRES_ECCLESIASTICAL_REVIEW":
        errors.append("invalid candidate status")
    if payload.get("completion_round") != "ALL_SERVICES_V1" or payload.get("lane_key") != lane_key:
        errors.append("completion round/lane identity mismatch")
    if payload.get("service_type") != lane["service"] or payload.get("service_id") != lane["service_id"]:
        errors.append("service identity mismatch")
    if payload.get("language") != language:
        errors.append("language mismatch")
    if payload.get("structure_status") != "STRUCTURED_EXACT_SOURCE_MAPPING":
        errors.append("candidate is not a source-mapped structured service")
    if payload.get("machine_translation_used") is not False or payload.get("ai_rewriting_or_correction_used") is not False:
        errors.append("forbidden translation or rewriting flag")
    health = payload.get("extraction_health") or {}
    if health.get("acceptable_candidate_extraction") is not True or health.get("failures"):
        errors.append("source extraction health did not pass")
    review = payload.get("ecclesiastical_review") or {}
    if review.get("status") != "APPROVED":
        errors.append("ecclesiastical review is not APPROVED")
    if review.get("source_page_verification") is not True:
        errors.append("source paragraph/page verification is not true")
    if not str(review.get("reviewer") or "").strip() or not str(review.get("reviewed_at") or "").strip():
        errors.append("reviewer and reviewed_at are required")
    if review.get("candidate_sha256") != candidate_hash(payload):
        errors.append("candidate hash mismatch")
    source = payload.get("source") or {}
    if source.get("source_id") != lane["source_id"]:
        errors.append("source id outside lane contract")
    if source.get("private_source_file_not_packaged") is not True:
        errors.append("private source retention flag is missing")
    service = payload.get("service") if isinstance(payload.get("service"), dict) else {}
    if service.get("id") != lane["service_id"] or not isinstance(service.get("segments"), list):
        errors.append("structured service payload is invalid")
    for item in iter_localized(service):
        for other in LANGS:
            if other != language and str(item.get(other) or "").strip():
                errors.append(f"{other} text leaked into {language} candidate")
                break
    required_slots = set(lane.get("required_dynamic_slots") or [])
    found_slots = {
        str(segment.get("dynamic_slot") or "")
        for segment in service.get("segments") or []
        if isinstance(segment, dict) and str(segment.get("dynamic_slot") or "")
    }
    if required_slots - found_slots:
        errors.append("missing dynamic slots: " + ",".join(sorted(required_slots - found_slots)))
    return errors


def load_reviewed(reviewed_root: Path, contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    failures: list[str] = []
    for lane_key in contract["required_new_source_lanes"]:
        lane = contract["lanes"][lane_key]
        path = reviewed_root / lane["service"] / f"{lane['language']}.json"
        if not path.is_file():
            failures.append(f"{lane_key}: reviewed candidate missing")
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            failures.append(f"{lane_key}: invalid JSON: {exc}")
            continue
        errors = validate_reviewed_candidate(payload, lane_key, lane)
        if errors:
            failures.append(f"{lane_key}: " + "; ".join(errors))
        else:
            result[lane_key] = payload
    if failures:
        raise RuntimeError("All-services promotion blocked:\n- " + "\n- ".join(failures))
    return result


def copy_project(destination: Path) -> None:
    def ignore(_dir: str, names: list[str]) -> set[str]:
        skipped = {".git", ".gradle", ".pytest_cache", "__pycache__", "build", "private_sources"}
        return {name for name in names if name in skipped or name.endswith(".pyc")}
    shutil.copytree(ROOT, destination, ignore=ignore)


def current_title(stage: Path, service_id: str, language: str) -> str:
    pack = json.loads((stage / f"data/services/native/library_{language}.json").read_text(encoding="utf-8"))
    for service in pack.get("services") or []:
        if service.get("id") == service_id:
            return str((service.get("title") or {}).get(language) or service_id)
    return service_id


def stage_changes(stage: Path, reviewed: dict[str, dict[str, Any]], contract: dict[str, Any]) -> None:
    library_path = stage / "data/services/library.json"
    library = json.loads(library_path.read_text(encoding="utf-8"))
    services = {str(item.get("id")): item for item in library.get("services") or [] if isinstance(item, dict)}
    manifest_path = stage / "canonical/native_service_manifest.json"
    native_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    for service_name in contract["required_services"]:
        service_id = contract["lanes"][f"{service_name}:ar"]["service_id"]
        if service_id not in services:
            titles: dict[str, str] = {}
            for language in LANGS:
                lane_key = f"{service_name}:{language}"
                candidate = reviewed.get(lane_key)
                if candidate:
                    titles[language] = str(((candidate.get("service") or {}).get("title") or {}).get(language) or service_id)
                else:
                    titles[language] = current_title(stage, service_id, language)
            stub = {
                "id": service_id,
                "category": "liturgy" if "liturgy" in service_name or service_name == "proskomide" else "daily",
                "icon": "⛪",
                "title": titles,
                "summary": {lang: titles[lang] for lang in LANGS},
                "segments": [],
            }
            library.setdefault("services", []).append(stub)
            services[service_id] = stub
        lane_manifest = native_manifest.setdefault("services", {}).setdefault(service_id, {})
        for language in LANGS:
            lane_key = f"{service_name}:{language}"
            lane = contract["lanes"][lane_key]
            candidate = reviewed.get(lane_key)
            source_id = (candidate.get("source") or {}).get("source_id") if candidate else lane["source_id"]
            source_url = (candidate.get("source") or {}).get("url") if candidate else lane["registered_source_url"]
            lane_manifest[language] = {"source_id": source_id, "url": source_url}
            if candidate:
                override = copy.deepcopy(candidate["service"])
                override["native_source"] = copy.deepcopy(candidate["service"].get("native_source") or {})
                write_json(stage / f"data/services/native_overrides/{language}/{service_id}.json", override)

    write_json(library_path, library)
    shutil.copy2(library_path, stage / "app/src/main/assets/data/library.json")
    write_json(manifest_path, native_manifest)

    completeness_path = stage / "canonical/religious_completeness_manifest.json"
    completeness = json.loads(completeness_path.read_text(encoding="utf-8"))
    for service_name in contract["required_services"]:
        completeness["packaged_service_ids"][service_name] = contract["lanes"][f"{service_name}:ar"]["service_id"]
        for language in LANGS:
            completeness["languages"][language][service_name] = "complete_exact_native_edition"
    completeness["status_notes"] = {
        "ar": "جميع الخدمات الخمس عشرة مستوردة من نصوص عربية أصلية ومراجعة ضمن الجولة الذرية.",
        "en": "All fifteen services are imported from reviewed native English editions in the atomic completion round.",
        "el": "Καὶ οἱ δεκαπέντε ἀκολουθίες εἰσήχθησαν ἀπὸ ἐλεγμένες πρωτότυπες ἑλληνικὲς ἐκδόσεις στὸν ἀτομικὸ κύκλο ολοκλήρωσης.",
    }
    write_json(completeness_path, completeness)
    shutil.copy2(completeness_path, stage / "app/src/main/assets/data/religious_completeness.json")

    editions_path = stage / "canonical/liturgy_service_editions.json"
    editions = json.loads(editions_path.read_text(encoding="utf-8"))
    for rite, service_name in (("chrysostom", "chrysostom_liturgy"), ("basil", "basil_liturgy"), ("presanctified", "presanctified_liturgy")):
        block = editions["editions"][rite]
        block["displayable"] = True
        for language in LANGS:
            block[language] = "IMPORTED_COMPLETE_NATIVE_EDITION_REVIEWED"
        block["completion_round"] = "ALL_SERVICES_V1"
        block["phase8_review_status"] = "COMPLETE_REVIEWED_NATIVE_EDITION"
    editions["phase8_finalization_pipeline"]["complete_release_allowed"] = True
    write_json(editions_path, editions)


def build_evidence(stage: Path, reviewed: dict[str, dict[str, Any]], contract: dict[str, Any]) -> None:
    evidence_path = stage / "canonical/service_edition_evidence.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    entries = evidence.setdefault("services", {})
    packs: dict[str, dict[str, dict[str, Any]]] = {}
    for language in LANGS:
        payload = json.loads((stage / f"data/services/native/library_{language}.json").read_text(encoding="utf-8"))
        packs[language] = {str(item.get("id")): item for item in payload.get("services") or [] if isinstance(item, dict)}
    for lane_key, lane in contract["lanes"].items():
        language = lane["language"]
        service = packs[language][lane["service_id"]]
        source = service.get("native_source") or {}
        candidate = reviewed.get(lane_key)
        proof = entries.get(lane_key, {}) if lane["already_release_ready"] else {}
        source_file_hash = ((candidate or {}).get("source") or {}).get("file_sha256") or proof.get("source_snapshot_sha256")
        entries[lane_key] = {
            "status": "complete_exact_native_edition",
            "packaged_service_id": lane["service_id"],
            "source_id": source.get("source_id"),
            "source_url": source.get("url"),
            "source_snapshot_sha256": source_file_hash,
            "content_sha256": digest_text(service, language),
            "minimum_segments": lane["minimum_paragraphs"],
            "minimum_characters": lane["minimum_characters"],
            "required_section_markers": [],
            "required_text_markers": lane["anchors"],
            "forbidden_text_patterns": ["placeholder", "todo", "text to be added", "يضاف لاحقا", "يضاف لاحقاً", "نص مؤقت"],
            "review_basis": "All-services atomic round: exact same-language source mapping plus explicit paragraph-by-paragraph ecclesiastical approval.",
        }
    write_json(evidence_path, evidence)


def protect_outputs(stage: Path) -> None:
    static_path = stage / "canonical/static_hashes.json"
    static = json.loads(static_path.read_text(encoding="utf-8"))
    protected = static.setdefault("files", {})
    for relative in (
        "canonical/all_services_completion_round.json",
        "canonical/all_services_source_bundle.template.json",
        "canonical/service_edition_evidence.json",
        "canonical/religious_completeness_manifest.json",
        "canonical/liturgy_service_editions.json",
        "canonical/native_service_manifest.json",
        "data/services/library.json",
        "app/src/main/assets/data/library.json",
        "app/src/main/assets/data/religious_completeness.json",
    ):
        protected.setdefault(relative, "")
    for root in ("data/services/native_overrides", "data/services/native", "app/src/main/assets/data/native"):
        for path in sorted((stage / root).rglob("*.json")):
            protected.setdefault(str(path.relative_to(stage)), "")
    write_json(static_path, static)
    subprocess.run([sys.executable, "scripts/verify_static_texts.py", "--update"], cwd=stage, check=True)


def validate_stage(stage: Path) -> None:
    commands = [
        [sys.executable, "scripts/build_native_service_packs.py"],
        [sys.executable, "scripts/validate_native_language_packs.py", "--require-complete"],
    ]
    for command in commands:
        subprocess.run(command, cwd=stage, check=True)


def final_validate_stage(stage: Path) -> None:
    commands = [
        [sys.executable, "scripts/validate_service_edition_evidence.py"],
        [sys.executable, "scripts/validate_religious_completeness.py"],
        [sys.executable, "scripts/validate_all_services_completion_round.py", "--production"],
        [sys.executable, "scripts/verify_static_texts.py"],
    ]
    for command in commands:
        subprocess.run(command, cwd=stage, check=True)


def apply_stage(stage: Path) -> None:
    backup = Path(tempfile.mkdtemp(prefix="all-services-rollback."))
    try:
        for relative in TOUCHED:
            source = ROOT / relative
            target = backup / relative
            if source.is_dir():
                shutil.copytree(source, target)
            elif source.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
        try:
            for relative in TOUCHED:
                source = stage / relative
                destination = ROOT / relative
                if destination.is_dir():
                    shutil.rmtree(destination)
                elif destination.exists():
                    destination.unlink()
                if source.is_dir():
                    shutil.copytree(source, destination)
                else:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, destination)
        except Exception:
            for relative in TOUCHED:
                original = backup / relative
                destination = ROOT / relative
                if destination.is_dir():
                    shutil.rmtree(destination)
                elif destination.exists():
                    destination.unlink()
                if original.is_dir():
                    shutil.copytree(original, destination)
                elif original.is_file():
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(original, destination)
            raise
    finally:
        shutil.rmtree(backup, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reviewed-root", type=Path, required=True)
    parser.add_argument("--output-project", type=Path, default=ROOT.parent / "orthodox_prayers_all_services_completed")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    reviewed = load_reviewed(args.reviewed_root.resolve(), contract)
    output = args.output_project.resolve()
    if output == ROOT or ROOT in output.parents:
        raise SystemExit("output project must be outside the active project tree")
    temp = Path(tempfile.mkdtemp(prefix="all-services-stage.", dir=output.parent if output.parent.exists() else None)) / "project"
    try:
        copy_project(temp)
        stage_changes(temp, reviewed, contract)
        validate_stage(temp)
        build_evidence(temp, reviewed, contract)
        protect_outputs(temp)
        final_validate_stage(temp)
        if output.exists():
            shutil.rmtree(output)
        os.replace(temp, output)
        if args.apply:
            apply_stage(output)
        print(f"ALL_SERVICES_ATOMIC_PROMOTION_OK lanes=45/45 output={output} applied={str(args.apply).lower()}")
    except Exception as exc:
        shutil.rmtree(temp.parent, ignore_errors=True)
        raise SystemExit(str(exc))


if __name__ == "__main__":
    main()
