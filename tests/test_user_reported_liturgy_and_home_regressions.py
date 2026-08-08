from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BAD_PROSKOMIDE = (
    "واثعنليمعشرصجولتاد",
    "هلماندهنسجد",
    "صلوة نصفالليل اليومية",
    "१ صلوة",
)


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def service(path: str, service_id: str) -> dict:
    payload = json.loads(read(path))
    if payload.get("id") == service_id:
        return payload
    return next(item for item in payload["services"] if item["id"] == service_id)


def test_arabic_proskomide_stops_at_its_real_conclusion_everywhere() -> None:
    paths = (
        "data/services/native_overrides/ar/proskomide.json",
        "data/services/native/library_ar.json",
        "app/src/main/assets/data/native/library_ar.json",
    )
    for path in paths:
        item = service(path, "proskomide")
        assert len(item["segments"]) == 77
        assert item["segments"][-2]["title"]["ar"] == "ختام خدمة التقدمة"
        visible = json.dumps(item["segments"], ensure_ascii=False)
        for marker in BAD_PROSKOMIDE:
            assert marker not in visible


def test_arabic_search_index_uses_the_clean_proskomide() -> None:
    for path in (
        "data/search/search_index_ar.json",
        "app/src/main/assets/data/search/search_index_ar.json",
    ):
        payload = json.loads(read(path))
        document = next(item for item in payload["documents"] if item["id"] == "service:proskomide")
        assert document["display_text"].rstrip().endswith(
            "ثم تكون الصرفة بحسب اليوم، وتبقى القرابين مغطاة ومحفوظة بوقار إلى بدء القداس الإلهي."
        )
        for marker in BAD_PROSKOMIDE:
            assert marker not in document["display_text"]


def test_thanksgiving_is_filtered_for_the_selected_liturgy() -> None:
    source = read("app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java")
    assert "thanksgivingSegmentsForLiturgy" in source
    assert "طروبارية القديس يوحنا الذهبي الفم" in source
    assert "طروبارية القديس باسيليوس الكبير" in source
    assert "طروبارية القديس غريغوريوس الكبير" in source
    assert "activeArabicVariant.equals(selected)" in source


def test_home_uses_calendar_driven_fasting_notice_instead_of_continue_reading() -> None:
    source = read("app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/HomeScreen.java")
    assert "FastingNoticeEngine.evaluate" in source
    assert "addSmartFastingNotice" in source
    assert "addContinueReading" not in source
    assert "ui_old_church_calendar_home_format" in source
    assert 'host.navigate("calendar_day", notice.targetDate.toString())' in source
    assert "specificCommemoration(today)" not in source


def test_unavailable_commemoration_wording_is_never_displayed() -> None:
    source = read("app/src/main/java/com/orthodoxprayers/privateapp/data/CommemorationDisplayPolicy.java")
    assert "تعذّر التحقق من تذكار هذا اليوم" in source
    assert "this day’s commemoration could not be verified" in source
    assert "ἡ μνήμη τῆς ἡμέρας δὲν κατέστη δυνατόν" in source

def test_java_unit_test_covers_each_thanksgiving_variant() -> None:
    source = read("app/src/test/java/com/orthodoxprayers/privateapp/data/ThanksgivingVariantSelectionTest.java")
    assert "arabicStJohnShowsOnlyItsOwnTroparion" in source
    assert "arabicBasilShowsOnlyItsOwnTroparion" in source
    assert "arabicPresanctifiedShowsOnlyItsOwnTroparion" in source
    assert 'assertFalse(visible.contains("عند إقامة قداس"))' in source

