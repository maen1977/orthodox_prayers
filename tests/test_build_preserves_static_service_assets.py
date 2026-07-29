from pathlib import Path


def test_build_restores_static_service_assets_after_verified_data_import():
    workflow = Path(".github/workflows/build.yml").read_text(encoding="utf-8")
    marker = "git restore --source=HEAD --worktree --"
    assert workflow.count(marker) == 2
    for required in (
        "data/services/library.json",
        "data/services/native",
        "app/src/main/assets/data/library.json",
        "app/src/main/assets/data/native",
        "tests/test_native_service_category_alignment.py",
    ):
        assert workflow.count(required) >= 2

    for block in workflow.split(marker)[1:]:
        restore_end = block.find("python -m pytest -q tests/test_native_service_category_alignment.py")
        assert restore_end >= 0
