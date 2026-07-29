from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_publication_tree_copies_complete_validator_runtime():
    workflow = (ROOT / ".github/workflows/update.yml").read_text(encoding="utf-8")
    assembled = workflow.split("Assemble and sign exact publication tree", 1)[1]
    assert 'rsync -a --delete "$SOURCE/scripts/" "$TARGET/scripts/"' in assembled
    for name in ("verify.py", "verify_language_lanes.py", "validate_rolling_week.py", "validate_reader_services.py"):
        assert f'test -f "$TARGET/scripts/{name}"' in assembled


def test_unexpected_refresh_exceptions_are_classified():
    repository = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java").read_text(encoding="utf-8")
    assert 'new RefreshOutcome(RefreshResult.FAILED, classifyError(error))' in repository
    assert 'new RefreshOutcome(RefreshResult.FAILED, "unexpected_refresh_error")' not in repository
