import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import prepare_all_calendar_scripture_fallback as scripture_sync


def test_scripture_sync_writes_exact_same_manifest_and_verses_to_source_and_android_assets(tmp_path, monkeypatch):
    monkeypatch.setattr(scripture_sync, "ROOT", tmp_path)
    source = {
        "source_id": "fixture_native_scripture",
        "source_url": "https://example.invalid/fixture.zip",
        "title": "Fixture Native Scripture",
        "license": "Public Domain",
    }
    index = {
        ("ACT", 1, 1): {"book_id": "ACT", "book_name": "Acts", "chapter": 1, "verse": 1, "text": "one"},
        ("ACT", 1, 2): {"book_id": "ACT", "book_name": "Acts", "chapter": 1, "verse": 2, "text": "two"},
        ("JHN", 1, 1): {"book_id": "JHN", "book_name": "John", "chapter": 1, "verse": 1, "text": "three"},
    }
    monkeypatch.setattr(scripture_sync, "load_public_domain_corpus", lambda language: (source, index))

    refs = ["ACT.1.1-2", "JHN.1.1"]
    result = scripture_sync.write_language("ar", refs)
    assert result["references"] == 2

    source_manifest = tmp_path / "data/scripture/native/ar/manifest.json"
    asset_manifest = tmp_path / "app/src/main/assets/data/scripture/manifest_ar.json"
    source_verses = tmp_path / "data/scripture/native/ar/verses.json"
    asset_verses = tmp_path / "app/src/main/assets/data/scripture/verses_ar.json"

    manifest = json.loads(source_manifest.read_text(encoding="utf-8"))
    assert manifest["coverage_status"] == "ALL_EMBEDDED_CALENDAR_REFERENCES_2026_2050"
    assert manifest["supported_canonical_references"] == refs
    assert manifest["supported_canonical_reference_count"] == len(refs)
    assert source_manifest.read_bytes() == asset_manifest.read_bytes()
    assert source_verses.read_bytes() == asset_verses.read_bytes()


def test_workflow_synchronizes_scripture_after_calendar_rebuild_and_before_release_gate():
    workflow = (ROOT / ".github/workflows/church-prayers.yml").read_text(encoding="utf-8")
    rebuild = workflow.index("python scripts/build_internal_calendar_2050.py")
    sync = workflow.index("python scripts/prepare_all_calendar_scripture_fallback.py")
    gate = workflow.index("python scripts/run_local_daily_release_gate.py")
    assert rebuild < sync < gate
    assert "Restore all-calendar Scripture source cache" in workflow
    assert "Save all-calendar Scripture source cache" in workflow
    assert "path: .cache/scripture" in workflow


def test_release_gate_keeps_r64_2_regression_test():
    gate = (ROOT / "scripts/run_local_daily_release_gate.py").read_text(encoding="utf-8")
    assert "tests/test_r64_2_scripture_manifest_sync.py" in gate
