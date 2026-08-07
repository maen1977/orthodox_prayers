from pathlib import Path


def test_simple_build_uses_checked_in_static_service_assets_without_remote_overwrite():
    workflow = Path(".github/workflows/church-prayers.yml").read_text(encoding="utf-8")
    assert "verified-data" not in workflow
    assert "rsync -a --delete" not in workflow
    assert "python scripts/run_local_daily_release_gate.py" in workflow
    gate = Path("scripts/run_local_daily_release_gate.py").read_text(encoding="utf-8")
    assert "scripts/simple_quality_gate.py" in gate
    for required in (
        Path("data/services/native/library_ar.json"),
        Path("data/services/native/library_en.json"),
        Path("data/services/native/library_el.json"),
        Path("app/src/main/assets/data/native/library_ar.json"),
        Path("app/src/main/assets/data/native/library_en.json"),
        Path("app/src/main/assets/data/native/library_el.json"),
    ):
        assert required.is_file()
