from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_validator_runtime_remains_complete_under_local_daily_architecture():
    workflow = (ROOT / ".github/workflows/church-prayers.yml").read_text(encoding="utf-8")
    assert "run_local_daily_release_gate.py" in workflow
    assert not (ROOT / ".github/workflows/update.yml").exists()
    for name in ("verify.py", "verify_language_lanes.py", "validate_rolling_week.py", "validate_reader_services.py"):
        assert (ROOT / "scripts" / name).is_file()


def test_unexpected_refresh_exceptions_are_classified():
    repository = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java").read_text(encoding="utf-8")
    assert 'new RefreshOutcome(RefreshResult.FAILED, classifyError(error))' in repository
    assert 'new RefreshOutcome(RefreshResult.FAILED, "unexpected_refresh_error")' not in repository
