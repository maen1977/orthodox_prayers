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


def test_current_day_merges_appointed_liturgy_when_daily_package_omits_it():
    repository = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java").read_text(encoding="utf-8")
    assert 'current.optJSONObject("liturgy_service_selection")' in repository
    assert 'annual.optJSONObject("liturgy_service_selection")' in repository
    assert 'merged.put("liturgy_service_selection"' in repository


def test_liturgy_tab_never_bypasses_hub_with_stale_daily_service():
    main = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/MainActivity.java").read_text(encoding="utf-8")
    assert 'case "liturgy": return new LiturgyHubScreen(this);' in main
    assert 'case "liturgy": return canOpenTodayLiturgyDirectly()' not in main


def test_church_eucharist_catalog_card_routes_to_complete_liturgy_hub():
    base = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/BaseScreen.java").read_text(encoding="utf-8")
    assert '"church_eucharist".equals(serviceId)' in base
    assert 'host.navigate("liturgy", null)' in base
