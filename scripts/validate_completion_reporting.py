#!/usr/bin/env python3
"""Reject contradictory 15-service completion reports."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = ("ar", "en", "el")
EXACT = "complete_exact_native_edition"
COMPILATION = "complete_native_source_compilation"


def load(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def main() -> None:
    manifest_path = ROOT / "canonical/religious_completeness_manifest.json"
    asset_path = ROOT / "app/src/main/assets/data/religious_completeness.json"
    if manifest_path.read_bytes() != asset_path.read_bytes():
        raise SystemExit("Canonical and embedded religious completeness reports diverge")

    manifest = load("canonical/religious_completeness_manifest.json")
    master = load("MASTER_COMPLETION_AUDIT.json")
    gaps = load("CONTENT_GAP_MATRIX.json")
    headline = load("canonical/all_languages_15_of_15_report.json")
    required = manifest["required_services"]
    complete_statuses = set(manifest["production_complete_statuses"])

    expected_exact = 0
    expected_compilations = 0
    for language in LANGUAGES:
        statuses = [manifest["languages"][language][service] for service in required]
        technical = sum(status in complete_statuses for status in statuses)
        exact = statuses.count(EXACT)
        compilations = statuses.count(COMPILATION)
        expected_exact += exact
        expected_compilations += compilations
        expected = {
            "technical_complete": technical,
            "exact_single_edition": exact,
            "native_source_compilation": compilations,
            "required": len(required),
        }
        if master.get("summary", {}).get(language) != expected:
            raise SystemExit(f"MASTER_COMPLETION_AUDIT summary mismatch for {language}")
        gap_summary = gaps.get("summary", {}).get(language, {})
        for key, value in expected.items():
            if gap_summary.get(key) != value:
                raise SystemExit(f"CONTENT_GAP_MATRIX {language}.{key} mismatch")
        if gap_summary.get("remaining_gaps") != len(required) - technical:
            raise SystemExit(f"CONTENT_GAP_MATRIX remaining_gaps mismatch for {language}")
        if headline.get("technical_language_scores", {}).get(language) != f"{technical}/{len(required)}":
            raise SystemExit(f"Headline completion score mismatch for {language}")

    expected_total = len(required) * len(LANGUAGES)
    expected_complete = sum(
        manifest["languages"][language][service] in complete_statuses
        for language in LANGUAGES
        for service in required
    )
    expected_release_allowed = expected_complete == expected_total
    if master.get("technical_release_allowed") is not expected_release_allowed:
        raise SystemExit("Master technical release flag does not match the canonical lane count")
    if headline.get("total_complete_lanes") != f"{expected_complete}/{expected_total}":
        raise SystemExit("Headline total lane count is inconsistent")
    if headline.get("exact_single_edition_lanes") != expected_exact:
        raise SystemExit("Headline exact-edition count is inconsistent")
    if headline.get("native_source_compilation_lanes") != expected_compilations:
        raise SystemExit("Headline native-compilation count is inconsistent")
    if expected_exact + expected_compilations != expected_complete:
        raise SystemExit("Complete lanes are not truthfully classified as exact or compiled")
    if manifest.get("machine_translation_allowed") is not False:
        raise SystemExit("Machine translation must remain prohibited")
    if master.get("ecclesiastical_approval_certified") is not False:
        raise SystemExit("Technical reports must not claim ecclesiastical approval")

    stale_phrases = (
        "14 من 15 خدمة بالعربية",
        "15 ἀπὸ 15 ἀκολουθίες στὰ ἑλληνικά",
    )
    report_text = "\n".join(
        (ROOT / path).read_text(encoding="utf-8")
        for path in (
            "canonical/religious_completeness_manifest.json",
            "app/src/main/assets/data/religious_completeness.json",
            "MASTER_COMPLETION_AUDIT.json",
            "CONTENT_GAP_MATRIX.json",
        )
    )
    for phrase in stale_phrases:
        if phrase in report_text:
            raise SystemExit(f"Stale contradictory completion phrase remains: {phrase}")

    print(
        "COMPLETION_REPORTING_OK "
        f"technical={expected_complete}/{expected_total} exact={expected_exact}/{expected_total} "
        f"native_compilations={expected_compilations}/{expected_total} ecclesiastical_approval=false"
    )


if __name__ == "__main__":
    main()
