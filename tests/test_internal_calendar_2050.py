import json
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = json.loads((ROOT / "canonical/internal_calendar_2026_2050.json").read_text(encoding="utf-8"))
INDEX = json.loads((ROOT / "app/src/main/assets/data/calendar/calendar_index.json").read_text(encoding="utf-8"))
BY_DATE = {item["date_iso"]: item for item in CANONICAL["days"]}


def test_internal_calendar_covers_every_day_through_2050():
    expected = (date(2050, 12, 31) - date(2026, 1, 1)).days + 1
    assert CANONICAL["civil_range"] == {
        "start": "2026-01-01",
        "end": "2050-12-31",
        "day_count": expected,
    }
    assert len(CANONICAL["days"]) == expected == 9131
    assert CANONICAL["days"][0]["date_iso"] == "2026-01-01"
    assert CANONICAL["days"][-1]["date_iso"] == "2050-12-31"


def test_internal_calendar_preserves_nine_day_twice_daily_policy():
    assert CANONICAL["visible_window_days"] == 9
    assert CANONICAL["update_schedule"] == {
        "timezone": "Asia/Amman",
        "times": ["04:23", "16:43"],
    }


def test_year_assets_are_split_for_low_memory_devices():
    assert set(INDEX["years"]) == {str(year) for year in range(2026, 2051)}
    for year in range(2026, 2051):
        meta = INDEX["years"][str(year)]
        path = ROOT / "app/src/main/assets" / meta["asset"]
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["year"] == year
        assert payload["days"][0]["date_iso"] == f"{year}-01-01"
        assert payload["days"][-1]["date_iso"] == f"{year}-12-31"


def test_pascha_and_year_boundary_are_available_offline():
    assert "الفصح" in BY_DATE["2026-04-12"]["feast"]["ar"]
    assert "الفصح" in BY_DATE["2027-05-02"]["feast"]["ar"]
    assert "الفصح" in BY_DATE["2050-04-17"]["feast"]["ar"]
    assert BY_DATE["2026-12-31"]["date_iso"] == "2026-12-31"
    assert BY_DATE["2027-01-01"]["date_iso"] == "2027-01-01"


def test_fixed_feasts_are_named_in_every_in_horizon_asset():
    from scripts.update_liturgical_data import julian_to_gregorian_date

    fixed = {
        (1, 1): "ختان",
        (1, 6): "الظهور",
        (2, 2): "دخول",
        (3, 25): "البشارة",
        (6, 24): "يوحنا",
        (6, 29): "بطرس وبولس",
        (8, 6): "تجلي",
        (8, 15): "رقاد",
        (9, 8): "ميلاد",
        (9, 14): "رفع الصليب",
        (11, 21): "دخول",
        (12, 25): "ميلاد",
    }
    for year in range(2026, 2051):
        for (month, day_number), anchor in fixed.items():
            civil = julian_to_gregorian_date(year, month, day_number)
            if civil.year > 2050:
                continue
            asset_path = ROOT / "app/src/main/assets/data/calendar" / f"calendar_{civil.year}.json"
            payload = json.loads(asset_path.read_text(encoding="utf-8"))
            item = next(day for day in payload["days"] if day["date_iso"] == civil.isoformat())
            feast = item["feast"]
            occasion_titles = [feast["ar"]]
            occasion_titles.extend(
                occasion.get("title", {}).get("ar", "")
                for occasion in item.get("occasions", [])
                if isinstance(occasion, dict)
            )
            assert anchor in " ".join(occasion_titles), (year, month, day_number, civil, item)
            for language in ("ar", "en", "el"):
                assert feast[language].strip(), (year, month, day_number, language)


def test_2026_transfiguration_and_fasting_detail_are_packaged():
    asset = json.loads((ROOT / "app/src/main/assets/data/calendar/calendar_2026.json").read_text(encoding="utf-8"))
    item = next(day for day in asset["days"] if day["date_iso"] == "2026-08-19")
    assert item["feast"] == {
        "ar": "عيد تجلي ربنا وإلهنا ومخلصنا يسوع المسيح",
        "en": "The Holy Transfiguration of our Lord, God and Savior Jesus Christ",
        "el": "Ἡ Ἁγία Μεταμόρφωσις τοῦ Κυρίου καὶ Θεοῦ καὶ Σωτῆρος ἡμῶν Ἰησοῦ Χριστοῦ",
    }
    fasting_ref = item["fasting"]
    fasting = asset["fasting_profiles"][fasting_ref["profile_id"]]
    assert fasting["code"] == "fish_allowed"
    assert "السمك" in fasting["detail"]["ar"]
    assert "Fish" in fasting["detail"]["en"]
    assert "ψάρι" in fasting["detail"]["el"]
    assert len(fasting["items"]) == 6
    assert not fasting["abstinence"].get("applies", False)


def test_commemoration_policy_renders_multiple_same_day_occasions():
    policy = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/CommemorationDisplayPolicy.java").read_text(encoding="utf-8")
    assert "displayOccasions" in policy
    assert 'day.optJSONArray("occasions")' in policy
    assert 'result.append("\\n")' in policy
    item = json.loads((ROOT / "app/src/main/assets/data/calendar/calendar_2026.json").read_text(encoding="utf-8"))
    item = next(day for day in item["days"] if day["date_iso"] == "2026-02-15")
    titles = [occasion["title"]["ar"] for occasion in item["occasions"]]
    assert any("الدينونة" in title for title in titles)
    assert any("دخول السيد" in title for title in titles)


def test_future_days_have_offline_commemoration_without_inventing_named_saints():
    day = BY_DATE["2040-08-02"]
    assert day["occasion_status"] in {
        "PINNED_INTERNAL_RULE",
        "PINNED_INTERNAL_OLD_CALENDAR_DATE",
        "PINNED_COMPARATIVE_ENGLISH_LANE",
        "PINNED_NATIVE_AND_COMPARATIVE_LANES",
        "PINNED_NATIVE_LANE",
    }
    commemoration = day["commemoration"]
    assert commemoration["status"] == day["commemoration_status"]
    for language in ("ar", "en", "el"):
        assert commemoration["name"][language].strip()
    if not day["reading_references"]:
        assert day["reference_status"] == "REFERENCE_PENDING_TWICE_DAILY_VERIFICATION"
    assert CANONICAL["policy"]["named_saints_require_verified_native_source"] is True
    assert CANONICAL["policy"]["machine_translation"] is False
    assert CANONICAL["policy"]["cross_language_fallback"] is False


def test_local_english_timetable_is_embedded_and_leap_slot_remains_comparative():
    day = BY_DATE["2026-03-02"]
    assert day["feast"]["ar"] == "القديس ثيودوروس العظيم في الشهداء التيروني وتذكار القديسين ماركيانوس وبلخيريا"
    assert day["feast"]["el"] == "Μνήμη τῶν Ἁγίων τῆς 17ης Φεβρουαρίου κατὰ τὸ παλαιὸ ἐκκλησιαστικὸ ἡμερολόγιο"
    assert day["feast"]["en"] == "Of the Souls, Theodore the Tyro, Marcian & Pulcheria"
    assert day["commemoration"]["source_kind"] == "verified_local_native_lane"
    evidence = json.loads((ROOT / "canonical/jerusalem_jordan_fixed_commemorations_native.json").read_text(encoding="utf-8"))
    evidence_day = next(item for item in evidence["records"] if item["old_calendar_month_day"] == "02-17")
    provenance = evidence_day["lanes"]["en"]
    assert provenance["source_id"] == "jerusalem_patriarchate_english_timetable_2019"
    assert provenance["comparative"] is False
    assert provenance["jurisdiction"] == "jerusalem_patriarchate"
    assert provenance["evidence_status"] == "VERIFIED_NATIVE_LOCAL_ENGLISH_SOURCE"


def test_dormition_fast_has_fourteen_days_and_separate_feast_day():
    policy = json.loads((ROOT / "canonical/fasting_policy.json").read_text(encoding="utf-8"))
    assert policy["dormition_fast_old_calendar"] == {
        "start": "08-01",
        "end": "08-14",
        "duration_days": 14,
        "feast_day": "08-15",
        "feast_day_is_outside_fast": True,
        "feast_day_rule": "fast_free_unless_wednesday_or_friday_fish",
        "feast_code": "fish_allowed_on_wednesday_or_friday",
        "source_id": "saint_sophia_dormition_fast",
        "source_url": "https://www.saintsophiadc.org/the-dormition-fast/",
    }
    asset = json.loads((ROOT / "app/src/main/assets/data/calendar/calendar_2026.json").read_text(encoding="utf-8"))
    by_date = {day["date_iso"]: day for day in asset["days"]}
    profiles = asset["fasting_profiles"]
    for civil_iso in ("2026-08-27", "2026-08-28"):
        fasting = profiles[by_date[civil_iso]["fasting"]["profile_id"]]
        if civil_iso == "2026-08-27":
            assert fasting["code"] in {"strict", "wine_oil"}
        else:
            assert fasting["code"] == "fish_allowed"
            assert fasting["verification"]["rule"] == "dormition_feast_fish"
            assert "أربعة عشر" in fasting["detail"]["ar"]
            allowed = {item["key"]: item["allowed"] for item in fasting["items"]}
            assert allowed["fish"] is True
            assert allowed["oil"] is True
            assert allowed["wine"] is True
            assert allowed["meat"] is False
            assert allowed["dairy"] is False
    saturday_feast = json.loads((ROOT / "app/src/main/assets/data/calendar/calendar_2027.json").read_text(encoding="utf-8"))
    saturday_day = next(day for day in saturday_feast["days"] if day["julian_date"] == "2027-08-15")
    saturday_profile = saturday_feast["fasting_profiles"][saturday_day["fasting"]["profile_id"]]
    assert saturday_day["date_iso"] == "2027-08-28"
    assert saturday_profile["code"] == "fast_free"
    assert saturday_profile["verification"]["rule"] == "dormition_feast_fast_free"


def test_every_day_has_semantically_valid_fasting_rule_through_2050():
    result = subprocess.run(
        [sys.executable, "scripts/validate_fasting_calendar_2050.py"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "FASTING_CALENDAR_2050_OK days=9131 years=25" in result.stdout
    assert "dormition_fast=14_days" in result.stdout
    assert "feast=fish_on_wed_fri_else_fast_free" in result.stdout


def test_android_uses_year_index_and_exact_nine_day_contract():
    repo = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java").read_text(encoding="utf-8")
    asset = json.loads((ROOT / "app/src/main/assets/data/calendar/calendar_2026.json").read_text(encoding="utf-8"))
    assert asset["fasting_profiles"]
    assert all("profile_id" in day["fasting"] for day in asset["days"])
    assert "resolveFastingProfile" in repo
    manifest = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/UpdateManifest.java").read_text(encoding="utf-8")
    screen = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/CalendarScreen.java").read_text(encoding="utf-8")
    assert 'data/calendar/calendar_index.json' in repo
    assert 'calendarDays(int year)' in repo
    assert 'MAX_ROLLING_WINDOW_DAYS = 9' in repo
    assert 'dayCount == 9' in manifest
    assert 'MIN_MONTH = YearMonth.of(2026, 1)' in screen
    assert 'MAX_MONTH = YearMonth.of(2050, 12)' in screen
    assert 'previous.setEnabled(month.isAfter(MIN_MONTH))' in screen
    assert 'next.setEnabled(month.isBefore(MAX_MONTH))' in screen


def test_verified_local_greek_and_local_english_lanes_are_language_isolated():
    day = BY_DATE["2026-08-08"]
    assert day["feast"]["el"] == "Παρασκευῆς ὁσιομάρτυρος, Ἑρμολάου ἱερομάρ."
    assert day["feast"]["ar"] == "القديسان الشهيدان إرمولاوس الأسقف وبراسكيفي البارّة الروميّة"
    assert day["feast"]["en"] == "Holy Martyr Paraskeve , Hieromartyr Hermolaus"
    evidence = json.loads((ROOT / "canonical/jerusalem_jordan_fixed_commemorations_native.json").read_text(encoding="utf-8"))
    evidence_day = next(item for item in evidence["records"] if item["old_calendar_month_day"] == "07-26")
    assert evidence_day["lanes"]["el"]["comparative"] is False
    assert evidence_day["lanes"]["el"]["jurisdiction"] == "jerusalem_patriarchate"
    assert evidence_day["lanes"]["en"]["comparative"] is False
    assert evidence_day["lanes"]["en"]["jurisdiction"] == "jerusalem_patriarchate"


def test_comparative_english_sidecar_preserves_full_text_without_asset_bloat():
    asset = json.loads((ROOT / "app/src/main/assets/data/calendar/comparative_english.json").read_text(encoding="utf-8"))
    day_asset = json.loads((ROOT / "app/src/main/assets/data/calendar/calendar_2028.json").read_text(encoding="utf-8"))
    day = next(item for item in day_asset["days"] if item["date_iso"] == "2028-03-13")
    reference = day["comparative_en_ref"]
    entry = asset["entries"][reference]
    assert reference == "02-29"
    assert entry["comparative"] is True
    assert entry["jurisdiction"] == "comparative_not_jerusalem_jordan"
    assert "Venerable John Cassian" in entry["text"]
    assert day["feast"]["en"] == "Commemoration of the saints of February 29 on the Old Church Calendar"
    assert set(asset["entries"]) == {"02-29"}
    repository = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java").read_text(encoding="utf-8")
    assert "comparative_english.json" in repository
    assert "resolveComparativeEnglishCommemoration" in repository


def test_major_fixed_feast_remains_primary_over_daily_greek_lane():
    day = BY_DATE["2026-08-19"]
    assert day["feast"]["ar"] == "عيد تجلي ربنا وإلهنا ومخلصنا يسوع المسيح"
    assert day["feast"]["en"] == "The Holy Transfiguration of our Lord, God and Savior Jesus Christ"
    assert day["feast"]["el"] == "Ἡ Ἁγία Μεταμόρφωσις τοῦ Κυρίου καὶ Θεοῦ καὶ Σωτῆρος ἡμῶν Ἰησοῦ Χριστοῦ"
