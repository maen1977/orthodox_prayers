#!/usr/bin/env python3
"""Validate the no-translation, same-language source contract and corpus/search integrity."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from native_text_contract import (
    ROOT,
    LANGUAGES,
    load_contract,
    sha256_text,
    source_allowed,
    source_url_allowed,
    script_errors,
)


def walk_localized(value: Any, pointer: str = "root"):
    if isinstance(value, dict):
        if any(lang in value for lang in LANGUAGES):
            yield pointer, value
        for key, child in value.items():
            yield from walk_localized(child, pointer + "." + str(key))
    elif isinstance(value, list):
        for i, child in enumerate(value):
            yield from walk_localized(child, f"{pointer}[{i}]")


def hostname(value: str) -> str:
    return (urlparse(value or "").hostname or "").casefold()


def embedded_source_allowed(
    language: str,
    service: dict[str, Any],
    source_id: str,
    url: str,
) -> bool:
    """Accept a recovered native source only when strict embedded provenance agrees."""
    document = service.get("source_document")
    if not isinstance(document, dict):
        return False

    if str(document.get("source_id") or "") != source_id:
        return False

    if str(service.get("source_language") or language) != language:
        return False

    if document.get("machine_translation_used") is not False:
        return False

    permission_basis = str(document.get("permission_basis") or "")
    permitted = (
        document.get("public_domain") is True
        or permission_basis.startswith("CONFIRMED_BY_PROJECT_OWNER")
    )
    if not permitted:
        return False

    document_url = str(
        document.get("url")
        or document.get("source_url")
        or ""
    )
    expected_host = hostname(document_url)
    actual_host = hostname(url)

    return bool(
        expected_host
        and actual_host
        and (
            actual_host == expected_host
            or actual_host.endswith("." + expected_host)
        )
    )


def validate_packs(errors: list[str], contract: dict[str, Any]) -> None:
    for lang in LANGUAGES:
        path = ROOT / "app/src/main/assets/data/native" / f"library_{lang}.json"
        data = json.loads(path.read_text(encoding="utf-8"))

        if data.get("language") != lang or data.get("machine_translation_used") is not False:
            errors.append(f"{path}: invalid language/machine translation metadata")

        for index, service in enumerate(data.get("services") or []):
            native = service.get("native_source") or {}
            source_id = str(native.get("source_id") or "")
            url = str(native.get("url") or "")

            central_source_ok = source_allowed(lang, source_id, contract)
            embedded_source_ok = embedded_source_allowed(
                lang,
                service,
                source_id,
                url,
            )

            if not central_source_ok and not embedded_source_ok:
                errors.append(
                    f"{path}: services[{index}] source {source_id!r} "
                    f"is outside {lang} lane"
                )

            if url and not (
                (
                    central_source_ok
                    and source_url_allowed(source_id, url, contract)
                )
                or embedded_source_ok
            ):
                errors.append(
                    f"{path}: services[{index}] URL is outside "
                    "registered or embedded source domain"
                )

            if native.get("machine_translation_used") is not False:
                errors.append(
                    f"{path}: services[{index}] machine translation flag "
                    "is not false"
                )

            for pointer, loc in walk_localized(
                service,
                f"services[{index}]",
            ):
                for other in LANGUAGES:
                    text = str(loc.get(other) or "")
                    if other != lang and text.strip():
                        errors.append(
                            f"{path}: {pointer}.{other} must be empty "
                            f"in a {lang} native pack"
                        )


def validate_corpora(errors: list[str], contract: dict[str, Any]) -> None:
    for lang in LANGUAGES:
        base = ROOT / "data/scripture/native" / lang
        manifest = json.loads(
            (base / "manifest.json").read_text(encoding="utf-8")
        )
        verses = json.loads(
            (base / "verses.json").read_text(encoding="utf-8")
        )

        if manifest.get("language") != lang:
            errors.append(f"{lang} corpus manifest language mismatch")

        if (
            manifest.get("machine_translation_used") is not False
            or manifest.get("automatic_diacritization_used") is not False
        ):
            errors.append(f"{lang} corpus forbidden transformation flag")

        if manifest.get("verse_count") != len(verses):
            errors.append(f"{lang} corpus verse_count mismatch")

        source_id = manifest.get("source_id")
        if verses and not source_allowed(
            lang,
            str(source_id or ""),
            contract,
        ):
            errors.append(f"{lang} corpus source is outside language lane")

        seen = set()
        for verse in verses:
            key = verse.get("id")
            if key in seen:
                errors.append(f"{lang} duplicate corpus verse {key}")
            seen.add(key)

            text = str(verse.get("text") or "")
            if verse.get("text_sha256") != sha256_text(text):
                errors.append(f"{lang} corpus verse {key} hash mismatch")

            for error in script_errors(lang, text):
                errors.append(f"{lang} corpus verse {key}: {error}")

            if (
                verse.get("machine_translation_used") is not False
                or verse.get("automatic_diacritization_used") is not False
            ):
                errors.append(
                    f"{lang} corpus verse {key} forbidden transformation flag"
                )


def validate_search(errors: list[str]) -> None:
    for lang in LANGUAGES:
        path = (
            ROOT
            / "app/src/main/assets/data/search"
            / f"search_index_{lang}.json"
        )
        data = json.loads(path.read_text(encoding="utf-8"))

        if data.get("language") != lang:
            errors.append(f"{path}: language mismatch")

        for document in data.get("documents") or []:
            display = str(document.get("display_text") or "")

            if document.get("display_sha256") != sha256_text(display):
                errors.append(
                    f"{path}: {document.get('id')} display hash mismatch"
                )

            if display and not str(document.get("search_text") or ""):
                errors.append(
                    f"{path}: {document.get('id')} missing derived search text"
                )


def main() -> None:
    contract = load_contract()
    errors: list[str] = []

    if (
        contract
        .get("religious_text_rules", {})
        .get("translation_between_lanes")
        is not False
    ):
        errors.append("translation_between_lanes must be false")

    validate_packs(errors, contract)
    validate_corpora(errors, contract)
    validate_search(errors)

    if errors:
        raise SystemExit("\n".join(dict.fromkeys(errors)))

    print(
        "Native-source contract validated: independent languages, "
        "registered or strictly embedded provenance, exact display hashes, "
        "no translation or automatic diacritization"
    )


if __name__ == "__main__":
    main()
