from __future__ import annotations

import importlib.util
import io
import os
import sys
import tempfile
import zipfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


public = load("r642_public", "scripts/public_domain_scripture.py")
prepare = load("r642_prepare", "scripts/prepare_all_calendar_scripture_fallback.py")
fill = load("r642_fill", "scripts/fill_daily_from_native_corpora.py")


def acts_15_usfm() -> str:
    lines = ["\\id ACT", "\\toc1 Acts", "\\c 15", "\\p"]
    for verse in range(5, 34):
        lines.append(f"\\v {verse} Exact source wording {verse}")
    # The source preserves the verse number but has only variant-note material.
    lines.append("\\v 34 \\f + \\ft Some manuscripts add this verse.\\f*")
    lines.append("\\v 35 Exact source wording 35")
    return "\n".join(lines) + "\n"


def test_explicit_numbered_textless_verse_is_recorded_not_fabricated():
    book, title, verses, omissions = public.parse_usfm_document_detailed(acts_15_usfm())
    assert book == "ACT"
    assert title == "Acts"
    assert (15, 34) not in verses
    assert (15, 34) in omissions
    assert verses[(15, 33)].startswith("Exact source wording")
    assert verses[(15, 35)].startswith("Exact source wording")


def test_verse_bridge_placeholder_is_not_reported_as_source_omission():
    raw = "\\id ACT\n\\toc1 Acts\n\\c 1\n\\v 3-4 One source bridge\n\\v 5 Next verse\n"
    _, _, verses, omissions = public.parse_usfm_document_detailed(raw)
    assert verses[(1, 3)] == "One source bridge"
    assert (1, 4) not in omissions


def test_load_corpus_exports_detected_numbered_omission_and_passage_resolves():
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        source = public.SOURCES["en"]
        with zipfile.ZipFile(directory / source["archive_name"], "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("45-ACT.usfm", acts_15_usfm())
        with mock.patch.dict(os.environ, {"ORTHODOX_SCRIPTURE_ARCHIVE_DIR": str(directory)}):
            manifest, index = public.load_public_domain_corpus("en")

    assert "ACT.15.34" in manifest["numbered_source_omissions"]
    parsed = fill.parse_reference_parts("ACT.15.5-34")
    assert parsed is not None
    assert fill.passage_verses(index, parsed) is None
    selected = fill.passage_verses(index, parsed, fill.declared_source_omissions(manifest))
    assert selected is not None
    assert selected[0]["verse"] == 5
    assert selected[-1]["verse"] == 33
    assert all(item["verse"] != 34 for item in selected)


def test_all_calendar_builder_accepts_source_edition_omission_without_changing_reference():
    _, _, index = None, None, None
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        source = public.SOURCES["en"]
        with zipfile.ZipFile(directory / source["archive_name"], "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("45-ACT.usfm", acts_15_usfm())
        with mock.patch.dict(os.environ, {"ORTHODOX_SCRIPTURE_ARCHIVE_DIR": str(directory)}):
            manifest, index = public.load_public_domain_corpus("en")
    omissions = set(manifest["numbered_source_omissions"])
    selected = prepare.selected_for_reference("en", "ACT.15.5-34", index, omissions)
    assert selected[0]["verse"] == 5
    assert selected[-1]["verse"] == 33
    assert "ACT.15.34" in prepare.ALLOWED_SOURCE_OMISSIONS["en"]


def test_workflow_regenerates_scripture_manifest_after_2050_calendar_bootstrap():
    workflow = (ROOT / ".github/workflows/church-prayers.yml").read_text(encoding="utf-8")
    bootstrap = workflow.index("python scripts/bootstrap_perpetual_lectionary_2050.py --workers 8")
    calendar = workflow.index("python scripts/build_internal_calendar_2050.py", bootstrap)
    scripture = workflow.index("python scripts/prepare_all_calendar_scripture_fallback.py", calendar)
    gate = workflow.index("Check content, languages, security, and calendar")
    assert bootstrap < calendar < scripture < gate
    assert "Restore all-calendar Scripture source cache" in workflow
    assert "Save all-calendar Scripture source cache" in workflow


def test_local_daily_validator_passes_declared_omissions_to_window_check():
    validator = (ROOT / "scripts/validate_local_daily_engine.py").read_text(encoding="utf-8")
    assert "verify_reference_window(years, ids, omissions, anchor)" in validator
    assert "endpoints_available(canonical, ids[language], omissions[language])" in validator


def romans_relocation_usfm() -> str:
    return "\n".join([
        "\\id ROM",
        "\\toc1 Romans",
        "\\c 14",
        "\\v 19 Source Romans 14:19",
        "\\v 20 Source Romans 14:20",
        "\\v 21 Source Romans 14:21",
        "\\v 22 Source Romans 14:22",
        "\\v 23 Source Romans 14:23",
        "\\v 24 Doxology source line one",
        "\\v 25 Doxology source line two",
        "\\v 26 Doxology source line three",
        "\\c 16",
        "\\v 25 \\f + \\fr 16:25 \\ft TR places Romans 14:24-26 here as 16:25-27.\\f*",
    ]) + "\n"


def test_english_romans_doxology_source_relocation_resolves_canonical_16_25_27():
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        source = public.SOURCES["en"]
        with zipfile.ZipFile(directory / source["archive_name"], "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("45-ROM.usfm", romans_relocation_usfm())
        with mock.patch.dict(os.environ, {"ORTHODOX_SCRIPTURE_ARCHIVE_DIR": str(directory)}):
            manifest, index = public.load_public_domain_corpus("en")

    assert manifest["source_verse_relocations"] == [
        {"canonical_id": "ROM.16.25", "source_id": "ROM.14.24"},
        {"canonical_id": "ROM.16.26", "source_id": "ROM.14.25"},
        {"canonical_id": "ROM.16.27", "source_id": "ROM.14.26"},
    ]
    assert "ROM.16.25" in manifest["source_numbered_omissions"]
    assert "ROM.16.25" not in manifest["numbered_source_omissions"]
    assert index[("ROM", 16, 25)]["text"] == "Doxology source line one"
    assert index[("ROM", 16, 26)]["text"] == "Doxology source line two"
    assert index[("ROM", 16, 27)]["text"] == "Doxology source line three"
    assert index[("ROM", 16, 26)]["source_chapter"] == 14
    assert index[("ROM", 16, 26)]["source_verse"] == 25
    assert index[("ROM", 16, 26)]["source_verse_relocation"] is True

    reference = "ROM.14.19-23;ROM.16.25-27"
    parsed = fill.parse_reference_parts(reference)
    assert parsed is not None
    selected = fill.passage_verses(index, parsed, fill.declared_source_omissions(manifest))
    assert selected is not None
    assert [(item["chapter"], item["verse"]) for item in selected] == [
        (14, 19), (14, 20), (14, 21), (14, 22), (14, 23),
        (16, 25), (16, 26), (16, 27),
    ]
    prepared = prepare.selected_for_reference(
        "en", reference, index, set(manifest["numbered_source_omissions"])
    )
    assert [item["text"] for item in prepared[-3:]] == [
        "Doxology source line one",
        "Doxology source line two",
        "Doxology source line three",
    ]


def test_greek_romans_doxology_source_relocation_resolves_canonical_16_25_27():
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        source = public.SOURCES["el"]
        with zipfile.ZipFile(directory / source["archive_name"], "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("51-ROM.usfm", romans_relocation_usfm())
        with mock.patch.dict(os.environ, {"ORTHODOX_SCRIPTURE_ARCHIVE_DIR": str(directory)}):
            manifest, index = public.load_public_domain_corpus("el")

    assert manifest["source_verse_relocations"] == [
        {"canonical_id": "ROM.16.25", "source_id": "ROM.14.24"},
        {"canonical_id": "ROM.16.26", "source_id": "ROM.14.25"},
        {"canonical_id": "ROM.16.27", "source_id": "ROM.14.26"},
    ]
    assert index[("ROM", 16, 25)]["text"] == "Doxology source line one"
    assert index[("ROM", 16, 26)]["text"] == "Doxology source line two"
    assert index[("ROM", 16, 27)]["text"] == "Doxology source line three"

    reference = "ROM.14.19-23;ROM.16.25-27"
    parsed = fill.parse_reference_parts(reference)
    assert parsed is not None
    selected = fill.passage_verses(index, parsed, fill.declared_source_omissions(manifest))
    assert selected is not None
    assert [(item["chapter"], item["verse"]) for item in selected][-3:] == [
        (16, 25), (16, 26), (16, 27),
    ]
    prepared = prepare.selected_for_reference(
        "el", reference, index, set(manifest["numbered_source_omissions"])
    )
    assert [item["text"] for item in prepared[-3:]] == [
        "Doxology source line one",
        "Doxology source line two",
        "Doxology source line three",
    ]
