#!/usr/bin/env python3
"""Protect the follow-along Liturgy from guidance-only and empty-reader regressions."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANGS = ("ar", "en", "el")
PACK = {
    "ar": ROOT / "data/services/native/library_ar.json",
    "en": ROOT / "data/services/native/library_en.json",
    "el": ROOT / "data/services/native/library_el.json",
}
OPTIONAL_LABELS = {
    "ar": "ملاحظة اختيارية",
    "en": "Optional note",
    "el": "Προαιρετικὴ σημείωση",
}
BANNED_GUIDANCE = {
    "هذه صلوات شخصية هادئة للمؤمن تساعده على متابعة القداس في قلبه. لا تُقال جهراً ولا تُبدل نصوص الكاهن أو الشماس أو المرتل.",
    "تُقرأ أو تُرتل آيات الأنتيفونا حسب اليوم. في الأعياد تُستبدل بنصوص العيد.",
    "تُرتل طروبارية القيامة أو طروبارية العيد بحسب اليوم.",
    "هنا تظهر قطع اليوم المتغيرة. عند تشغيل التحديث اليومي يملأ البرنامج طروبارية العيد أو الأحد والقنداق المناسب.",
    "بعد الإنجيل قد تكون العظة أو تفسير القراءة بحسب ترتيب الكنيسة.",
    "في هذا الموضع تتم الدورة الكبرى بالقرابين. يتابع القارئ النص بهدوء، وتظهر هنا المقاطع التي يقولها الشعب أو يسمعها أثناء الحركة.",
    "يتم الدخول الكبير بالقرابين المقدسة. يتوقف القارئ هنا ويتابع بعد عودة الكاهن والشماس إلى الهيكل.",
    "تُرتل آية المناولة المعيّنة لليوم. عند وجود عيد خاص يضع التحديث اليومي آية المناولة المناسبة.",
}
ORDINARY_COMMUNION = {
    "ar": "سبحوا الرب من السماوات، سبحوه في الأعالي. هللويا.",
    "en": "Praise the Lord from the Heavens; praise Him in the highest. Alleluia (3)",
    "el": "Αἰνεῖτε τόν Κύριον ἐκ τῶν οὐρανῶν. Αἰνεῖτε Αὐτόν ἐν τοῖς ὑψίστοις. Ἀλληλούϊα (3)",
}


def service(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return next(item for item in payload.get("services", []) if item.get("id") == "divine_liturgy")


def local(value: object, language: str) -> str:
    return str(value.get(language) or "").strip() if isinstance(value, dict) else ""


def main() -> None:
    errors: list[str] = []
    for language in LANGS:
        liturgy = service(PACK[language])
        slots: dict[str, list[dict]] = {}
        for index, segment in enumerate(liturgy.get("segments", [])):
            if not isinstance(segment, dict):
                continue
            speaker = local(segment.get("speaker"), language)
            text = local(segment.get("text"), language)
            if speaker == OPTIONAL_LABELS[language]:
                errors.append(f"{language}: optional-note label remains at segment {index}")
            if text in BANNED_GUIDANCE:
                errors.append(f"{language}: guidance-only text remains at segment {index}")
            slot = str(segment.get("dynamic_slot") or "")
            if slot:
                slots.setdefault(slot, []).append(segment)

        communion = slots.get("communion_hymn", [])
        if len(communion) != 1:
            errors.append(f"{language}: expected one communion_hymn slot, found {len(communion)}")
        elif communion[0].get("dynamic_slot_mode") != "replace_if_present":
            errors.append(f"{language}: communion_hymn must preserve ordinary text when no proper is available")
        elif local(communion[0].get("text"), language) != ORDINARY_COMMUNION[language]:
            errors.append(f"{language}: ordinary Communion hymn is missing or changed")

        required = {"matins_gospel", "prokeimenon", "epistle", "gospel", "communion_hymn"}
        if language == "ar":
            required |= {"daily_troparion", "church_troparion", "daily_kontakion"}
        else:
            required.add("daily_hymns")
        missing = sorted(required - set(slots))
        if missing:
            errors.append(f"{language}: missing semantic slots: {', '.join(missing)}")

    java = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java").read_text(encoding="utf-8")
    for marker in ("replace_if_present", "appendDailyLiturgyOverlay", "appendNativePrayerService"):
        if marker not in java:
            errors.append(f"Android composition is missing {marker}")

    if errors:
        raise SystemExit("\n".join(errors))
    print("LITURGY_READER_INTEGRITY_OK languages=ar,en,el optional_guidance=0 ordinary_communion_preserved=true")


if __name__ == "__main__":
    main()
