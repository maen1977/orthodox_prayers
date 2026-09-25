from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_liturgy_hub_uses_current_annual_calendar_when_snapshot_is_stale():
    hub = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/LiturgyHubScreen.java").read_text(encoding="utf-8")
    assert "data.currentDayForDisplay()" in hub
    assert "data.today()" not in hub
    assert "appointedServiceId(selection)" in hub


def test_main_liturgy_route_uses_current_calendar_and_all_rite_ids():
    main = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/MainActivity.java").read_text(encoding="utf-8")
    assert "repository.currentDayForDisplay()" in main
    assert '"divine_liturgy_basil"' in main
    assert '"presanctified_liturgy"' in main
