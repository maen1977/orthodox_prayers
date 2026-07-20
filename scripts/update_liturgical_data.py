#!/usr/bin/env python3
"""Build app-ready Orthodox daily data JSON for orthodox_prayers.

This version is intentionally centered on the Jerusalem/old-calendar use case:
- Uses Asia/Amman as the day boundary.
- Converts the civil date to the Julian/old ecclesiastical date.
- Calculates the Apostles' Fast from Orthodox Pascha through the old-calendar feast of Peter and Paul.
- Generates a full follow-along Divine Liturgy service, not only a short summary.
- Keeps override support: scripts/overrides/YYYY-MM-DD.json can force feast, fast, readings, or service inserts.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import html
import urllib.error
import urllib.request
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
CALENDAR_DIR = DATA_DIR / "calendar"
SERVICES_DIR = DATA_DIR / "services"
ASSET_TODAY = ROOT / "app" / "src" / "main" / "assets" / "data" / "today.json"
LIBRARY_PATH = ROOT / "app" / "src" / "main" / "assets" / "data" / "library.json"
TZ = ZoneInfo("Asia/Amman")
AR_DAYS = ["الإثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]
AR_MONTHS = ["كانون الثاني", "شباط", "آذار", "نيسان", "أيار", "حزيران", "تموز", "آب", "أيلول", "تشرين الأول", "تشرين الثاني", "كانون الأول"]

FULL_CREED_AR = """أؤمن بإله واحد، آب ضابط الكل، خالق السماء والأرض، كل ما يُرى وما لا يُرى.
وبرب واحد يسوع المسيح، ابن الله الوحيد، المولود من الآب قبل كل الدهور. نور من نور، إله حق من إله حق، مولود غير مخلوق، مساوٍ للآب في الجوهر، الذي به كان كل شيء.
الذي من أجلنا نحن البشر ومن أجل خلاصنا نزل من السماوات، وتجسد من الروح القدس ومن مريم العذراء، وتأنس.
وصُلب عنا على عهد بيلاطس البنطي، وتألم وقُبر.
وقام في اليوم الثالث كما في الكتب.
وصعد إلى السماوات، وجلس عن يمين الآب.
وأيضاً يأتي بمجد ليدين الأحياء والأموات، الذي لا فناء لملكه.
وبالروح القدس، الرب المحيي، المنبثق من الآب، الذي هو مع الآب والابن مسجود له وممجد، الناطق بالأنبياء.
وبكنيسة واحدة، جامعة، مقدسة، رسولية.
وأعترف بمعمودية واحدة لمغفرة الخطايا.
وأترجى قيامة الموتى والحياة في الدهر الآتي. آمين."""

LORDS_PRAYER_AR = """أبانا الذي في السماوات، ليتقدس اسمك، ليأتِ ملكوتك، لتكن مشيئتك كما في السماء كذلك على الأرض.
خبزنا الجوهري أعطنا اليوم، واترك لنا ما علينا كما نترك نحن لمن لنا عليه، ولا تدخلنا في تجربة، لكن نجّنا من الشرير."""

PRE_LITURGY_PRAYERS = [
    ("إشارة الصليب", "القارئ", "باسم الآب والابن والروح القدس، الإله الواحد. آمين."),
    ("صلاة الروح القدس", "القارئ", "أيها الملك السماوي، المعزي، روح الحق، الحاضر في كل مكان والمالئ الكل، كنز الصالحات ورازق الحياة، هلم واسكن فينا، وطهرنا من كل دنس، وخلص أيها الصالح نفوسنا."),
    ("الثلاثة تقديسات", "القارئ", "قدوس الله، قدوس القوي، قدوس الذي لا يموت، ارحمنا.\nقدوس الله، قدوس القوي، قدوس الذي لا يموت، ارحمنا.\nقدوس الله، قدوس القوي، قدوس الذي لا يموت، ارحمنا."),
    ("المجد والآن", "القارئ", "المجد للآب والابن والروح القدس، الآن وكل أوان وإلى دهر الداهرين. آمين."),
    ("الثالوث القدوس", "القارئ", "أيها الثالوث القدوس ارحمنا، يا رب اغفر خطايانا، يا سيد تجاوز عن سيئاتنا، يا قدوس اطّلع واشفِ أمراضنا من أجل اسمك."),
    ("يا رب ارحم", "القارئ", "يا رب ارحم. يا رب ارحم. يا رب ارحم."),
    ("الصلاة الربانية قبل القداس", "القارئ", LORDS_PRAYER_AR + "\nلأن لك الملك والقوة والمجد، أيها الآب والابن والروح القدس، الآن وكل أوان وإلى دهر الداهرين. آمين."),
]



def loc(ar: str, en: str | None = None, el: str | None = None) -> dict:
    """Build a localized object without copying one language into another.

    Missing translations remain empty so the Android UI can show the verified source
    instead of presenting Arabic or English text as if it were a real translation.
    """
    return {"ar": ar or "", "en": en or "", "el": el or ""}



EN_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
EN_MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
EL_DAYS = ["Δευτέρα", "Τρίτη", "Τετάρτη", "Πέμπτη", "Παρασκευή", "Σάββατο", "Κυριακή"]
EL_MONTHS = ["Ιανουαρίου", "Φεβρουαρίου", "Μαρτίου", "Απριλίου", "Μαΐου", "Ιουνίου", "Ιουλίου", "Αυγούστου", "Σεπτεμβρίου", "Οκτωβρίου", "Νοεμβρίου", "Δεκεμβρίου"]

FEAST_TRANSLATIONS = {
    "تذكار اليوم بحسب التقويم الكنسي القديم": (
        "Today’s commemoration according to the old church calendar",
        "Ἡ σημερινὴ μνήμη κατὰ τὸ παλαιὸ ἐκκλησιαστικὸ ἡμερολόγιο",
    ),
    "ختان الرب بالجسد وتذكار القديس باسيليوس الكبير": (
        "Circumcision of the Lord and commemoration of Saint Basil the Great",
        "Ἡ κατὰ σάρκα Περιτομὴ τοῦ Κυρίου καὶ ἡ μνήμη τοῦ Ἁγίου Βασιλείου τοῦ Μεγάλου",
    ),
    "عيد الظهور الإلهي المقدس": ("Holy Theophany", "Τὰ Ἅγια Θεοφάνεια"),
    "دخول السيد إلى الهيكل": ("Meeting of the Lord in the Temple", "Ἡ Ὑπαπαντὴ τοῦ Κυρίου"),
    "عيد البشارة المقدسة": ("Annunciation of the Most Holy Theotokos", "Ὁ Εὐαγγελισμὸς τῆς Ὑπεραγίας Θεοτόκου"),
    "ميلاد القديس يوحنا المعمدان": ("Nativity of Saint John the Baptist", "Τὸ Γενέσιον τοῦ Ἁγίου Ἰωάννου τοῦ Προδρόμου"),
    "عيد هامتي الرسل القديسين بطرس وبولس": ("Holy Apostles Peter and Paul", "Οἱ Ἅγιοι Πρωτοκορυφαῖοι Ἀπόστολοι Πέτρος καὶ Παῦλος"),
    "عيد التجلي الإلهي": ("Holy Transfiguration of the Lord", "Ἡ Μεταμόρφωσις τοῦ Κυρίου"),
    "رقاد السيدة والدة الإله": ("Dormition of the Most Holy Theotokos", "Ἡ Κοίμησις τῆς Ὑπεραγίας Θεοτόκου"),
    "ميلاد والدة الإله": ("Nativity of the Most Holy Theotokos", "Τὸ Γενέσιον τῆς Ὑπεραγίας Θεοτόκου"),
    "رفع الصليب الكريم المحيي": ("Exaltation of the Precious and Life-giving Cross", "Ἡ Ὕψωσις τοῦ Τιμίου καὶ Ζωοποιοῦ Σταυροῦ"),
    "دخول والدة الإله إلى الهيكل": ("Entry of the Most Holy Theotokos into the Temple", "Τὰ Εἰσόδια τῆς Ὑπεραγίας Θεοτόκου"),
    "عيد ميلاد ربنا وإلهنا ومخلصنا يسوع المسيح بالجسد": ("Nativity according to the flesh of our Lord, God, and Savior Jesus Christ", "Ἡ κατὰ σάρκα Γέννησις τοῦ Κυρίου καὶ Θεοῦ καὶ Σωτῆρος ἡμῶν Ἰησοῦ Χριστοῦ"),
}

FASTING_FOOD_LOCALIZATION = {
    "meat": ("Meat", "Κρέας"),
    "dairy": ("Dairy", "Γαλακτοκομικά"),
    "eggs": ("Eggs", "Αὐγά"),
    "fish": ("Fish", "Ψάρι"),
    "wine": ("Wine", "Οἶνος"),
    "oil": ("Oil", "Ἔλαιο"),
}

FASTING_LEVEL_LOCALIZATION = {
    "fast_free": ("No fast", "Χωρὶς νηστεία"),
    "dairy_allowed": ("Dairy, eggs, and fish permitted", "Ἐπιτρέπονται γαλακτοκομικά, αὐγὰ καὶ ψάρι"),
    "fish_allowed": ("Fish, oil, and wine permitted", "Ἐπιτρέπονται ψάρι, ἔλαιο καὶ οἶνος"),
    "wine_oil": ("Oil and wine permitted", "Ἐπιτρέπονται ἔλαιο καὶ οἶνος"),
    "strict": ("Strict fast", "Αὐστηρὰ νηστεία"),
}

# Native UI translations for every automatic Typikon rule emitted by this generator.
FASTING_RULE_LOCALIZATION = {
    "publican_pharisee_fast_free_week": ("Fast-free week", "Ἀπολύτως ἄλυτη ἑβδομάδα", "The week from the Sunday of the Publican and the Pharisee through the Sunday of the Prodigal Son is fast-free.", "Ἡ ἑβδομάδα ἀπὸ τὴν Κυριακὴ τοῦ Τελώνου καὶ Φαρισαίου ἕως τὴν Κυριακὴ τοῦ Ἀσώτου εἶναι ἄλυτη."),
    "bright_week": ("Bright Week", "Διακαινήσιμος Ἑβδομάδα", "Bright Week after Pascha is fast-free.", "Ἡ Διακαινήσιμος Ἑβδομάδα μετὰ τὸ Πάσχα εἶναι ἄλυτη."),
    "pentecost_fast_free_week": ("Week after Pentecost", "Ἑβδομάδα μετὰ τὴν Πεντηκοστή", "The week after Pentecost is fast-free.", "Ἡ ἑβδομάδα μετὰ τὴν Πεντηκοστὴ εἶναι ἄλυτη."),
    "nativity_to_theophany_fast_free": ("Nativity season", "Ἡμέρες Χριστουγέννων", "There is no general fast from the Nativity through the day before the Eve of Theophany.", "Δὲν προβλέπεται γενικὴ νηστεία ἀπὸ τὰ Χριστούγεννα ἕως τὴν παραμονὴ τῶν Θεοφανείων."),
    "major_feast_fast_free": ("Great feast", "Μεγάλη ἑορτή", "A great feast ends the associated fasting period.", "Ἡ μεγάλη ἑορτὴ καταλύει τὴν ἀντίστοιχη περίοδο νηστείας."),
    "cheesefare_week": ("Cheesefare Week", "Ἑβδομάδα Τυρινῆς", "Meat is omitted; dairy, eggs, fish, oil, and wine are permitted.", "Γίνεται ἀποχὴ ἀπὸ κρέας· ἐπιτρέπονται γαλακτοκομικά, αὐγά, ψάρι, ἔλαιο καὶ οἶνος."),
    "great_lent_fish_exception": ("Great Lent", "Μεγάλη Τεσσαρακοστή", "The Annunciation or Palm Sunday permits fish, oil, and wine during Great Lent.", "Ὁ Εὐαγγελισμὸς ἢ ἡ Κυριακὴ τῶν Βαΐων ἐπιτρέπει ψάρι, ἔλαιο καὶ οἶνο μέσα στὴ Μεγάλη Τεσσαρακοστή."),
    "great_lent_weekend_wine_oil": ("Great Lent", "Μεγάλη Τεσσαρακοστή", "Oil and wine are permitted on Saturdays and Sundays of Great Lent, except Holy Saturday.", "Τὰ Σάββατα καὶ τὶς Κυριακὲς τῆς Μεγάλης Τεσσαρακοστῆς ἐπιτρέπονται ἔλαιο καὶ οἶνος, ἐκτὸς ἀπὸ τὸ Μέγα Σάββατο."),
    "great_lent_strict": ("Great Lent or Holy Week", "Μεγάλη Τεσσαρακοστὴ ἢ Μεγάλη Ἑβδομάδα", "The day falls within Great Lent or Holy Week.", "Ἡ ἡμέρα βρίσκεται μέσα στὴ Μεγάλη Τεσσαρακοστὴ ἢ τὴ Μεγάλη Ἑβδομάδα."),
    "single_day_strict_fast": ("One-day fast", "Μονοήμερη νηστεία", "This is a strict one-day fast.", "Πρόκειται γιὰ αὐστηρὴ μονοήμερη νηστεία."),
    "apostles_fast_fish": ("Apostles’ Fast", "Νηστεία τῶν Ἁγίων Ἀποστόλων", "Fish, oil, and wine are permitted on weekends and on the Nativity of Saint John the Baptist.", "Τὰ Σαββατοκύριακα καὶ στὸ Γενέσιο τοῦ Τιμίου Προδρόμου ἐπιτρέπονται ψάρι, ἔλαιο καὶ οἶνος."),
    "apostles_fast_tue_thu": ("Apostles’ Fast", "Νηστεία τῶν Ἁγίων Ἀποστόλων", "Oil and wine are permitted on Tuesday and Thursday according to the general rule.", "Τὴν Τρίτη καὶ τὴν Πέμπτη ἐπιτρέπονται ἔλαιο καὶ οἶνος κατὰ τὸν γενικὸ κανόνα."),
    "apostles_fast_mon_wed_fri": ("Apostles’ Fast", "Νηστεία τῶν Ἁγίων Ἀποστόλων", "The general rule is a strict fast on Monday, Wednesday, and Friday.", "Ὁ γενικὸς κανόνας προβλέπει αὐστηρὰ νηστεία Δευτέρα, Τετάρτη καὶ Παρασκευή."),
    "dormition_transfiguration_fish": ("Dormition Fast", "Νηστεία τῆς Κοιμήσεως", "The Transfiguration permits fish, oil, and wine during the Dormition Fast.", "Ἡ Μεταμόρφωση ἐπιτρέπει ψάρι, ἔλαιο καὶ οἶνο μέσα στὴ Νηστεία τῆς Κοιμήσεως."),
    "dormition_weekend_wine_oil": ("Dormition Fast", "Νηστεία τῆς Κοιμήσεως", "Oil and wine are permitted on Saturdays and Sundays.", "Τὰ Σάββατα καὶ τὶς Κυριακὲς ἐπιτρέπονται ἔλαιο καὶ οἶνος."),
    "dormition_strict": ("Dormition Fast", "Νηστεία τῆς Κοιμήσεως", "The day falls within the Dormition Fast.", "Ἡ ἡμέρα βρίσκεται μέσα στὴ Νηστεία τῆς Κοιμήσεως."),
    "nativity_entry_theotokos_fish": ("Nativity Fast", "Νηστεία Χριστουγέννων", "The Entry of the Theotokos permits fish, oil, and wine.", "Στὰ Εἰσόδια τῆς Θεοτόκου ἐπιτρέπονται ψάρι, ἔλαιο καὶ οἶνος."),
    "nativity_weekend": ("Nativity Fast", "Νηστεία Χριστουγέννων", "The weekend rule of the Nativity Fast applies; fish is omitted during the final days before the Nativity.", "Ἰσχύει ὁ κανόνας τοῦ Σαββατοκύριακου τῆς Νηστείας Χριστουγέννων· στὶς τελευταῖες ἡμέρες δὲν ἐπιτρέπεται ψάρι."),
    "nativity_tue_thu": ("Nativity Fast", "Νηστεία Χριστουγέννων", "Oil and wine are permitted on Tuesday and Thursday according to the general rule.", "Τὴν Τρίτη καὶ τὴν Πέμπτη ἐπιτρέπονται ἔλαιο καὶ οἶνος κατὰ τὸν γενικὸ κανόνα."),
    "nativity_mon_wed_fri": ("Nativity Fast", "Νηστεία Χριστουγέννων", "The general rule is a strict fast on Monday, Wednesday, and Friday.", "Ὁ γενικὸς κανόνας προβλέπει αὐστηρὰ νηστεία Δευτέρα, Τετάρτη καὶ Παρασκευή."),
    "major_feast_weekly_fast_relaxation": ("Great feast", "Μεγάλη ἑορτή", "A great feast on a weekly fast day permits fish, oil, and wine according to the general rule.", "Μεγάλη ἑορτὴ σὲ ἡμέρα νηστείας ἐπιτρέπει ψάρι, ἔλαιο καὶ οἶνο κατὰ τὸν γενικὸ κανόνα."),
    "weekly_wednesday_friday": ("Wednesday or Friday fast", "Νηστεία Τετάρτης ἢ Παρασκευῆς", "This is the regular weekly Orthodox fast unless a documented relaxation or local dispensation applies.", "Πρόκειται γιὰ τὴν τακτικὴ ἑβδομαδιαία ὀρθόδοξη νηστεία, ἐκτὸς ἂν ὑπάρχει τεκμηριωμένη κατάλυση ἢ τοπικὴ οἰκονομία."),
    "ordinary_fast_free": ("Ordinary day", "Συνήθης ἡμέρα", "No general fasting season or weekly fast applies today.", "Σήμερα δὲν ἰσχύει γενικὴ περίοδος νηστείας οὔτε ἑβδομαδιαία νηστεία."),
}

BOOK_EL = {
    "Romans": "ΠΡΟΣ ΡΩΜΑΙΟΥΣ",
    "Matthew": "ΚΑΤΑ ΜΑΤΘΑΙΟΝ",
    "Mark": "ΚΑΤΑ ΜΑΡΚΟΝ",
    "Luke": "ΚΑΤΑ ΛΟΥΚΑΝ",
    "John": "ΚΑΤΑ ΙΩΑΝΝΗΝ",
    "Acts": "ΠΡΑΞΕΙΣ ΑΠΟΣΤΟΛΩΝ",
    "1 Corinthians": "ΠΡΟΣ ΚΟΡΙΝΘΙΟΥΣ Α΄",
    "2 Corinthians": "ΠΡΟΣ ΚΟΡΙΝΘΙΟΥΣ Β΄",
    "Galatians": "ΠΡΟΣ ΓΑΛΑΤΑΣ",
    "Ephesians": "ΠΡΟΣ ΕΦΕΣΙΟΥΣ",
    "Philippians": "ΠΡΟΣ ΦΙΛΙΠΠΗΣΙΟΥΣ",
    "Colossians": "ΠΡΟΣ ΚΟΛΟΣΣΑΕΙΣ",
    "1 Thessalonians": "ΠΡΟΣ ΘΕΣΣΑΛΟΝΙΚΕΙΣ Α΄",
    "2 Thessalonians": "ΠΡΟΣ ΘΕΣΣΑΛΟΝΙΚΕΙΣ Β΄",
    "1 Timothy": "ΠΡΟΣ ΤΙΜΟΘΕΟΝ Α΄",
    "2 Timothy": "ΠΡΟΣ ΤΙΜΟΘΕΟΝ Β΄",
    "Titus": "ΠΡΟΣ ΤΙΤΟΝ",
    "Philemon": "ΠΡΟΣ ΦΙΛΗΜΟΝΑ",
    "Hebrews": "ΠΡΟΣ ΕΒΡΑΙΟΥΣ",
    "James": "ΙΑΚΩΒΟΥ",
    "1 Peter": "ΠΕΤΡΟΥ Α΄",
    "2 Peter": "ΠΕΤΡΟΥ Β΄",
    "1 John": "ΙΩΑΝΝΟΥ Α΄",
    "2 John": "ΙΩΑΝΝΟΥ Β΄",
    "3 John": "ΙΩΑΝΝΟΥ Γ΄",
    "Jude": "ΙΟΥΔΑ",
    "Revelation": "ΑΠΟΚΑΛΥΨΙΣ ΙΩΑΝΝΟΥ",
}


def en_date_label(day: date, include_year: bool = True) -> str:
    year = f", {day.year}" if include_year else ""
    return f"{EN_DAYS[day.weekday()]}, {EN_MONTHS[day.month - 1]} {day.day}{year}"


def el_date_label(day: date, include_year: bool = True) -> str:
    year = f" {day.year}" if include_year else ""
    return f"{EL_DAYS[day.weekday()]}, {day.day} {EL_MONTHS[day.month - 1]}{year}"


def localized_civil_old_date(day: date, include_year: bool = True) -> dict:
    jy, jm, jd = gregorian_to_julian_date(day)
    ar = f"{ar_date_label(day)} / {jd} {AR_MONTHS[jm - 1]} {jy} بحسب التقويم الكنسي القديم"
    en = f"{en_date_label(day, include_year)} / {EN_MONTHS[jm - 1]} {jd}, {jy} (Old Style)"
    el = f"{el_date_label(day, include_year)} / {jd} {EL_MONTHS[jm - 1]} {jy} (παλαιὸ ἡμερολόγιο)"
    return loc(ar, en, el)


def localized_feast(ar_text: str) -> dict:
    en, el = FEAST_TRANSLATIONS.get(ar_text, ("Commemoration listed by the old church calendar", "Μνήμη κατὰ τὸ παλαιὸ ἐκκλησιαστικὸ ἡμερολόγιο"))
    return loc(ar_text, en, el)


def greek_reference(display: str) -> str:
    ref = (display or "").replace("(Epistle)", "").replace("(Gospel)", "").strip()
    for en, el in sorted(BOOK_EL.items(), key=lambda item: -len(item[0])):
        ref = re.sub(rf"\b{re.escape(en)}\b", el, ref)
    return ref.replace(".", ":").strip()


def localized_evangelist(reading: dict) -> dict:
    refs = reading.get("reference") if isinstance(reading.get("reference"), dict) else {}
    combined = " ".join(str(refs.get(lang) or "") for lang in ("ar", "en", "el"))
    if "متى" in combined or "Matthew" in combined or "ΜΑΤΘ" in combined:
        return loc("متى البشير", "Matthew the Evangelist", "Ματθαῖος ὁ Εὐαγγελιστής")
    if "مرقس" in combined or "Mark" in combined or "ΜΑΡΚ" in combined:
        return loc("مرقس البشير", "Mark the Evangelist", "Μᾶρκος ὁ Εὐαγγελιστής")
    if "لوقا" in combined or "Luke" in combined or "ΛΟΥΚ" in combined:
        return loc("لوقا البشير", "Luke the Evangelist", "Λουκᾶς ὁ Εὐαγγελιστής")
    if "يوحنا" in combined or "John" in combined or "ΙΩΑΝ" in combined:
        return loc("يوحنا البشير", "John the Evangelist", "Ἰωάννης ὁ Εὐαγγελιστής")
    return loc("الإنجيلي", "Evangelist", "Εὐαγγελιστής")


def _localized_fasting_detail(profile: dict, language: str) -> str:
    rule = str((profile.get("verification") or {}).get("rule") or "")
    code = str(profile.get("code") or "")
    translation = FASTING_RULE_LOCALIZATION.get(rule)
    reason = translation[2 if language == "en" else 3] if translation else (
        "The conservative Typikon baseline applies." if language == "en" else "Ἰσχύει ὁ συντηρητικὸς βασικὸς κανόνας τοῦ Τυπικοῦ."
    )
    items = profile.get("items") if isinstance(profile.get("items"), list) else []
    allowed = [FASTING_FOOD_LOCALIZATION.get(str(item.get("key")), (str(item.get("key")), str(item.get("key"))))[0 if language == "en" else 1] for item in items if item.get("allowed")]
    forbidden = [FASTING_FOOD_LOCALIZATION.get(str(item.get("key")), (str(item.get("key")), str(item.get("key"))))[0 if language == "en" else 1] for item in items if not item.get("allowed")]
    if code == "fast_free":
        suffix = " All listed foods are permitted." if language == "en" else " Ἐπιτρέπονται ὅλες οἱ καταγεγραμμένες τροφές."
    elif allowed:
        suffix = (" Permitted: " + ", ".join(allowed) + ". Avoid: " + ", ".join(forbidden) + ".") if language == "en" else (" Ἐπιτρέπονται: " + ", ".join(allowed) + ". Ἀποχή: " + ", ".join(forbidden) + ".")
    else:
        suffix = " Avoid meat, dairy, eggs, fish, oil, and wine." if language == "en" else " Ἀποχὴ ἀπὸ κρέας, γαλακτοκομικά, αὐγά, ψάρι, ἔλαιο καὶ οἶνο."
    return reason + suffix


def complete_fasting_localizations(profile: dict) -> None:
    if not isinstance(profile, dict):
        return
    rule = str((profile.get("verification") or {}).get("rule") or "")
    code = str(profile.get("code") or "")
    rule_text = FASTING_RULE_LOCALIZATION.get(rule, ("Fasting day", "Ἡμέρα νηστείας", "The conservative Typikon baseline applies.", "Ἰσχύει ὁ συντηρητικὸς βασικὸς κανόνας τοῦ Τυπικοῦ."))
    level = FASTING_LEVEL_LOCALIZATION.get(code, ("Fasting rule", "Κανόνας νηστείας"))
    profile.setdefault("season", {}).update({"en": rule_text[0], "el": rule_text[1]})
    title_en = level[0] if code == "fast_free" else f"{rule_text[0]} — {level[0]}"
    title_el = level[1] if code == "fast_free" else f"{rule_text[1]} — {level[1]}"
    profile.setdefault("title", {}).update({"en": title_en, "el": title_el})
    profile.setdefault("level", {}).update({"en": level[0], "el": level[1]})
    profile.setdefault("detail", {}).update({"en": _localized_fasting_detail(profile, "en"), "el": _localized_fasting_detail(profile, "el")})
    for item in profile.get("items") or []:
        key = str(item.get("key") or "")
        en, el = FASTING_FOOD_LOCALIZATION.get(key, (key, key))
        item.setdefault("label", {}).update({"en": en, "el": el})
    verification = profile.setdefault("verification", {})
    verification.setdefault("note", loc(""))
    verification["note"].update({
        "en": "Conservative automatic baseline; a documented override may apply a local dispensation or a special feast rank.",
        "el": "Συντηρητικὸς αὐτόματος βασικὸς κανόνας· τεκμηριωμένη ἐξαίρεση μπορεῖ νὰ ἐφαρμόσει τοπικὴ οἰκονομία ἢ ἰδιαίτερη τάξη ἑορτῆς.",
    })


def _complete_reading_labels(reading: dict, fill_missing_reference: bool = True) -> None:
    if not isinstance(reading, dict):
        return
    kind = str(reading.get("kind") or "")
    if kind in {"epistle", "gospel"}:
        title = reading.setdefault("title", loc(""))
        if kind == "epistle":
            title.update({"ar": title.get("ar") or "الرسالة", "en": title.get("en") or "Epistle", "el": title.get("el") or "Ἀπόστολος"})
        else:
            title.update({"ar": title.get("ar") or "الإنجيل", "en": title.get("en") or "Gospel", "el": title.get("el") or "Εὐαγγέλιο"})
        reference = reading.setdefault("reference", loc(""))
        if fill_missing_reference and not str(reference.get("el") or "").strip() and str(reference.get("en") or "").strip():
            reference["el"] = greek_reference(str(reference["en"]))


def _complete_reference_block(block: dict) -> None:
    if not isinstance(block, dict):
        return
    for kind in ("epistle", "gospel"):
        entry = block.get(kind)
        if not isinstance(entry, dict):
            continue
        title = entry.setdefault("title", loc(""))
        if kind == "epistle":
            title.update({"ar": title.get("ar") or "الرسالة", "en": title.get("en") or "Epistle", "el": title.get("el") or "Ἀπόστολος"})
        else:
            title.update({"ar": title.get("ar") or "الإنجيل", "en": title.get("en") or "Gospel", "el": title.get("el") or "Εὐαγγέλιο"})
        reference = entry.setdefault("reference", loc(""))
        if not str(reference.get("el") or "").strip() and str(reference.get("en") or "").strip():
            reference["el"] = greek_reference(str(reference["en"]))


def _complete_service_overlay(service: dict, today: dict, next_sunday: dict) -> None:
    if not isinstance(service, dict):
        return
    service_id = str(service.get("id") or "")
    context = next_sunday if service_id == "next_sunday_full_liturgy" else today
    dynamic_date = str(service.get("dynamic_date") or context.get("date_iso") or "")
    try:
        day = datetime.strptime(dynamic_date, "%Y-%m-%d").date()
    except ValueError:
        day = None
    feast = context.get("feast") if isinstance(context.get("feast"), dict) else loc("")
    fast = context.get("fast") if isinstance(context.get("fast"), dict) else loc("")
    refs = context.get("reading_references") if isinstance(context.get("reading_references"), dict) else {}
    gospel_ref = refs.get("gospel") if isinstance(refs.get("gospel"), dict) else {}
    gospel_reading = {"reference": gospel_ref.get("reference") if isinstance(gospel_ref.get("reference"), dict) else loc("")}
    inline = service.get("inline_replacements")
    if isinstance(inline, dict) and "[اسم الإنجيلي]" in inline:
        inline["[اسم الإنجيلي]"] = localized_evangelist(gospel_reading)
    segments = service.get("segments") if isinstance(service.get("segments"), list) else []
    for segment in segments:
        if not isinstance(segment, dict):
            continue
        title = segment.get("title")
        if isinstance(title, dict) and str(title.get("ar") or "").strip():
            ar_title = str(title.get("ar") or "")
            title_map = {
                "ملحق اليوم الكنسي": ("Church-day supplement", "Συμπλήρωμα τῆς ἐκκλησιαστικῆς ἡμέρας"),
                "قطع اليوم": ("Texts of the day", "Κείμενα τῆς ἡμέρας"),
                "خدمة اليوم: ملحق اليوم": ("Today: daily supplement", "Σήμερα: ἡμερήσιο συμπλήρωμα"),
                "الأحد القادم: ملحق اليوم": ("Next Sunday: daily supplement", "Ἐρχόμενη Κυριακή: ἡμερήσιο συμπλήρωμα"),
                "ترتيب قراءات اليوم": ("Order of today’s readings", "Τάξη τῶν σημερινῶν ἀναγνωσμάτων"),
            }
            if ar_title in title_map:
                en, el = title_map[ar_title]
                title.update({"en": title.get("en") or en, "el": title.get("el") or el})
        speaker = segment.get("speaker")
        if isinstance(speaker, dict) and str(speaker.get("ar") or "") == "ملاحظة اختيارية":
            speaker.update({"en": speaker.get("en") or "Optional note", "el": speaker.get("el") or "Προαιρετικὴ σημείωση"})
        text = segment.get("text")
        if isinstance(text, dict) and day and str(text.get("ar") or "").startswith("التاريخ المدني:"):
            text.update({
                "en": text.get("en") or f"Civil date: {en_date_label(day)}. Old-calendar date: {localized_civil_old_date(day)['en'].split(' / ', 1)[1]}. Commemoration: {feast.get('en', '')}. Fasting: {fast.get('en', '')}.",
                "el": text.get("el") or f"Πολιτικὴ ἡμερομηνία: {el_date_label(day)}. Ἡμερομηνία παλαιοῦ ἡμερολογίου: {localized_civil_old_date(day)['el'].split(' / ', 1)[1]}. Μνήμη: {feast.get('el', '')}. Νηστεία: {fast.get('el', '')}.",
            })


def complete_daily_localizations(data: dict) -> dict:
    """Complete non-scriptural UI metadata in Arabic, English, and Greek.

    This function never translates Scripture or liturgical prayer bodies. It only
    fills deterministic UI labels, dates, fasting descriptions, and references.
    """
    if not isinstance(data, dict):
        return data
    try:
        day = datetime.strptime(str(data.get("date_iso") or ""), "%Y-%m-%d").date()
    except ValueError:
        day = None
    if day:
        data["date_label"] = localized_civil_old_date(day)
    data["calendar_label"] = loc(
        "التقويم الكنسي القديم — بطريركية القدس",
        "Old church calendar — Jerusalem Patriarchate usage",
        "Παλαιὸ ἐκκλησιαστικὸ ἡμερολόγιο — χρήση Πατριαρχείου Ἱεροσολύμων",
    )
    feast = data.get("feast") if isinstance(data.get("feast"), dict) else loc("")
    if str(feast.get("ar") or ""):
        data["feast"] = localized_feast(str(feast["ar"]))
    complete_fasting_localizations(data.get("fasting"))
    if isinstance(data.get("fasting"), dict):
        data["fast"] = copy.deepcopy(data["fasting"].get("title") or data.get("fast"))
        data["fast_detail"] = copy.deepcopy(data["fasting"].get("detail") or data.get("fast_detail"))
    data["source_note"] = loc(
        "تُستخدم بيانات الاكتشاف مؤقتاً فقط؛ ولا يصبح الملف قابلاً للنشر إلا بعد بوابة المصادر الرسمية والتوقيع المحمي.",
        "Discovery data is temporary; a file becomes publishable only after the official-source gate and protected signing.",
        "Τὰ δεδομένα ἐντοπισμοῦ εἶναι προσωρινά· ἕνα ἀρχεῖο δημοσιεύεται μόνον μετὰ τὸν ἔλεγχο ἐπισήμων πηγῶν καὶ τὴν προστατευμένη ὑπογραφή.",
    )
    data["translation_notice"] = loc(
        "تُعرض النصوص الكتابية والليتورجية من مصادر أصلية مستقلة لكل لغة، من دون ترجمة آلية أو رجوع إلى لغة أخرى.",
        "Scripture and liturgical texts come from independent native sources for each language, without machine translation or cross-language fallback.",
        "Τὰ βιβλικὰ καὶ λειτουργικὰ κείμενα προέρχονται ἀπὸ ἀνεξάρτητες πρωτότυπες πηγὲς κάθε γλώσσας, χωρὶς μηχανικὴ μετάφραση ἢ ἐφεδρικὴ χρήση ἄλλης γλώσσας.",
    )
    for reading in data.get("readings") or []:
        _complete_reading_labels(reading)
    next_payload = data.get("next_sunday") if isinstance(data.get("next_sunday"), dict) else {}
    if next_payload:
        try:
            ns_day = datetime.strptime(str(next_payload.get("date_iso") or ""), "%Y-%m-%d").date()
        except ValueError:
            ns_day = None
        if ns_day:
            next_payload["day"] = localized_civil_old_date(ns_day)
        ns_feast = next_payload.get("feast") if isinstance(next_payload.get("feast"), dict) else loc("")
        if str(ns_feast.get("ar") or ""):
            next_payload["feast"] = localized_feast(str(ns_feast["ar"]))
        complete_fasting_localizations(next_payload.get("fasting"))
        if isinstance(next_payload.get("fasting"), dict):
            next_payload["fast"] = copy.deepcopy(next_payload["fasting"].get("title") or next_payload.get("fast"))
        _complete_reference_block(next_payload.get("reading_references"))
    for item in data.get("upcoming") or []:
        if not isinstance(item, dict):
            continue
        try:
            future_day = datetime.strptime(str(item.get("date") or ""), "%Y-%m-%d").date()
        except ValueError:
            future_day = None
        if future_day:
            item["day"] = localized_civil_old_date(future_day, include_year=False)
        item_feast = item.get("feast") if isinstance(item.get("feast"), dict) else loc("")
        if str(item_feast.get("ar") or ""):
            item["feast"] = localized_feast(str(item_feast["ar"]))
            item["note"] = copy.deepcopy(item["feast"])
        complete_fasting_localizations(item.get("fasting"))
        if isinstance(item.get("fasting"), dict):
            item["status"] = copy.deepcopy(item["fasting"].get("title") or item.get("status"))
        _complete_reference_block(item.get("reading_references"))
    integrity_next = ((data.get("integrity_inputs") or {}).get("next_sunday") or {}).get("readings") or []
    for reading in integrity_next:
        # Internal publication lanes must keep missing references empty unless a
        # same-language source explicitly verifies them. User-facing preview
        # cards are localized separately without claiming source-lane evidence.
        _complete_reading_labels(reading, fill_missing_reference=False)
    today_context = {
        "date_iso": data.get("date_iso"),
        "feast": data.get("feast"),
        "fast": data.get("fast"),
        "reading_references": reading_references(data.get("readings") or []),
    }
    for service in data.get("services") or []:
        _complete_service_overlay(service, today_context, next_payload)
    return data


def gregorian_to_jdn(y: int, m: int, d: int) -> int:
    a = (14 - m) // 12
    y2 = y + 4800 - a
    m2 = m + 12 * a - 3
    return d + ((153 * m2 + 2) // 5) + 365 * y2 + y2 // 4 - y2 // 100 + y2 // 400 - 32045


def julian_to_jdn(y: int, m: int, d: int) -> int:
    a = (14 - m) // 12
    y2 = y + 4800 - a
    m2 = m + 12 * a - 3
    return d + ((153 * m2 + 2) // 5) + 365 * y2 + y2 // 4 - 32083


def jdn_to_gregorian(jdn: int) -> date:
    a = jdn + 32044
    b = (4 * a + 3) // 146097
    c = a - (146097 * b) // 4
    d = (4 * c + 3) // 1461
    e = c - (1461 * d) // 4
    m = (5 * e + 2) // 153
    day = e - (153 * m + 2) // 5 + 1
    month = m + 3 - 12 * (m // 10)
    year = 100 * b + d - 4800 + (m // 10)
    return date(year, month, day)


def jdn_to_julian(jdn: int) -> tuple[int, int, int]:
    c = jdn + 32082
    d = (4 * c + 3) // 1461
    e = c - (1461 * d) // 4
    m = (5 * e + 2) // 153
    day = e - (153 * m + 2) // 5 + 1
    month = m + 3 - 12 * (m // 10)
    year = d - 4800 + (m // 10)
    return year, month, day


def julian_to_gregorian_date(y: int, m: int, d: int) -> date:
    return jdn_to_gregorian(julian_to_jdn(y, m, d))


def gregorian_to_julian_date(day: date) -> tuple[int, int, int]:
    return jdn_to_julian(gregorian_to_jdn(day.year, day.month, day.day))


def orthodox_pascha_gregorian(year: int) -> date:
    """Orthodox Pascha using the Julian-calendar formula, returned as Gregorian date."""
    a = year % 4
    b = year % 7
    c = year % 19
    d = (19 * c + 15) % 30
    e = (2 * a + 4 * b - d + 34) % 7
    month = (d + e + 114) // 31
    day = ((d + e + 114) % 31) + 1
    return julian_to_gregorian_date(year, month, day)


def ar_date_label(day: date) -> str:
    return f"{AR_DAYS[day.weekday()]} {day.day} {AR_MONTHS[day.month-1]} {day.year}"


def ar_julian_label(day: date) -> str:
    jy, jm, jd = gregorian_to_julian_date(day)
    return f"{jd} {AR_MONTHS[jm-1]} {jy} بحسب التقويم الكنسي القديم"


def fetch_orthocal_old(day: date, attempts: int = 4) -> dict:
    """Fetch old-calendar daily data from Orthocal for a civil date.

    Orthocal's ``/api/julian/YYYY/MM/DD/`` endpoint expects the civil date in
    the URL.  The ``julian`` part selects the old-calendar rules; callers must
    not subtract the Gregorian/Julian offset before building the URL.
    """
    fixture_root = Path(
        os.getenv("ORTHODOX_ORTHOCAL_FIXTURE_DIR", str(ROOT / "scripts" / "fixtures" / "orthocal"))
    )
    fixture_path = fixture_root / f"{day.isoformat()}.json"
    if fixture_path.is_file():
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not isinstance(payload.get("readings"), list):
            raise RuntimeError(f"Invalid Orthocal fixture: {fixture_path}")
        return payload

    url = f"https://orthocal.info/api/julian/{day.year}/{day.month}/{day.day}/"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "orthodox-prayers-daily-updater/5.0.2 (+https://github.com/maen1977/orthodox_prayers)",
        },
    )
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=30) as resp:
                if getattr(resp, "status", 200) != 200:
                    raise RuntimeError(f"Orthocal returned HTTP {getattr(resp, 'status', 'unknown')}")
                payload = json.loads(resp.read().decode("utf-8"))
                if not isinstance(payload, dict):
                    raise RuntimeError("Orthocal returned a non-object JSON response")
                if not isinstance(payload.get("readings"), list):
                    raise RuntimeError("Orthocal response is missing the readings list")
                return payload
        except urllib.error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")[:500]
            last_error = RuntimeError(f"Orthocal HTTP {exc.code}: {details}")
            retryable = exc.code in {408, 425, 429, 500, 502, 503, 504}
            if not retryable:
                break
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, RuntimeError) as exc:
            last_error = exc
        if attempt < attempts:
            delay = min(20, 2 ** (attempt - 1))
            print(f"Orthocal attempt {attempt}/{attempts} failed for {day:%Y-%m-%d}; retrying in {delay}s: {last_error}")
            time.sleep(delay)
    raise RuntimeError(
        f"Orthocal old-calendar data could not be fetched for civil date {day:%Y-%m-%d} "
        f"after {attempts} attempts: {last_error}"
    )


def fixed_old_feast(j_month: int, j_day: int) -> str | None:
    fixed = {
        (1, 1): "ختان الرب بالجسد وتذكار القديس باسيليوس الكبير",
        (1, 6): "عيد الظهور الإلهي المقدس",
        (2, 2): "دخول السيد إلى الهيكل",
        (3, 25): "عيد البشارة المقدسة",
        (6, 24): "ميلاد القديس يوحنا المعمدان",
        (6, 29): "عيد هامتي الرسل القديسين بطرس وبولس",
        (8, 6): "عيد التجلي الإلهي",
        (8, 15): "رقاد السيدة والدة الإله",
        (9, 8): "ميلاد والدة الإله",
        (9, 14): "رفع الصليب الكريم المحيي",
        (11, 21): "دخول والدة الإله إلى الهيكل",
        (12, 25): "عيد ميلاد ربنا وإلهنا ومخلصنا يسوع المسيح بالجسد",
    }
    return fixed.get((j_month, j_day))


FASTING_FOODS = {
    "meat": {"icon": "🥩", "ar": "اللحوم"},
    "dairy": {"icon": "🥛", "ar": "الألبان"},
    "eggs": {"icon": "🥚", "ar": "البيض"},
    "fish": {"icon": "🐟", "ar": "السمك"},
    "wine": {"icon": "🍷", "ar": "النبيذ"},
    "oil": {"icon": "🫒", "ar": "الزيت"},
}

FASTING_LEVELS = {
    "fast_free": {"allowed": set(FASTING_FOODS), "level_ar": "لا صوم"},
    "dairy_allowed": {"allowed": {"dairy", "eggs", "fish", "wine", "oil"}, "level_ar": "الألبان والبيض والسمك مسموحة"},
    "fish_allowed": {"allowed": {"fish", "wine", "oil"}, "level_ar": "السمك والزيت والنبيذ مسموحة"},
    "wine_oil": {"allowed": {"wine", "oil"}, "level_ar": "الزيت والنبيذ مسموحان"},
    "strict": {"allowed": set(), "level_ar": "صوم صارم"},
}


def _fasting_profile(level: str, season_ar: str, reason_ar: str, source_rule: str) -> dict:
    if level not in FASTING_LEVELS:
        raise ValueError(f"Unknown fasting level: {level}")
    allowed = FASTING_LEVELS[level]["allowed"]
    rules = {key: key in allowed for key in FASTING_FOODS}
    if level == "strict":
        display_icons = ["🍞", "💧"]
    elif level == "fast_free":
        display_icons = ["✅"]
    else:
        display_icons = [FASTING_FOODS[key]["icon"] for key in ("fish", "dairy", "eggs", "oil", "wine") if key in allowed]
    allowed_names = [FASTING_FOODS[key]["ar"] for key in FASTING_FOODS if key in allowed]
    forbidden_names = [FASTING_FOODS[key]["ar"] for key in FASTING_FOODS if key not in allowed]
    level_ar = FASTING_LEVELS[level]["level_ar"]
    title_ar = level_ar if level == "fast_free" else f"{season_ar} — {level_ar}"
    if allowed_names:
        detail = f"{reason_ar} المسموح بحسب القاعدة العامة: { '، '.join(allowed_names) }."
    else:
        detail = f"{reason_ar} صوم صارم بحسب القاعدة العامة: دون لحوم أو ألبان أو بيض أو سمك أو زيت أو نبيذ."
    if forbidden_names and allowed_names:
        detail += f" يُمتنع عن: { '، '.join(forbidden_names) }."
    return {
        "code": level,
        "season": loc(season_ar),
        "title": loc(title_ar),
        "level": loc(level_ar),
        "detail": loc(detail),
        "is_fast": level != "fast_free",
        "allowed": rules,
        "display_icons": display_icons,
        "items": [
            {
                "key": key,
                "icon": meta["icon"],
                "label": loc(meta["ar"]),
                "allowed": rules[key],
            }
            for key, meta in FASTING_FOODS.items()
        ],
        "verification": {
            "status": "TYPICON_BASELINE",
            "policy": "canonical/fasting_policy.json",
            "rule": source_rule,
            "note": loc("قاعدة آلية محافظة؛ يمكن لملف override موثق أن يطبق تدبيراً محلياً أو رتبة عيد خاصة."),
        },
    }


def fasting_profile(day: date, jm: int, jd: int, pascha: date, apostles_start: date, apostles_end: date) -> dict:
    """Return a conservative old-calendar fasting profile.

    The automatic profile follows the common Typikon baseline. It intentionally
    does not invent saint-rank exceptions that are unavailable from the daily
    machine-readable source; those belong in a dated override.
    """
    weekday = day.weekday()
    old_key = (jm, jd)

    # Explicit fast-free periods and major feast endings.
    publican_sunday = pascha - timedelta(days=70)
    prodigal_sunday = pascha - timedelta(days=63)
    bright_end = pascha + timedelta(days=6)
    pentecost_monday = pascha + timedelta(days=50)
    pentecost_week_end = pascha + timedelta(days=56)
    if publican_sunday <= day <= prodigal_sunday:
        return _fasting_profile("fast_free", "أسبوع خالٍ من الصوم", "الأسبوع من أحد الفريسي والعشار إلى أحد الابن الشاطر خالٍ من الصوم.", "publican_pharisee_fast_free_week")
    if pascha <= day <= bright_end:
        return _fasting_profile("fast_free", "الأسبوع المشرق", "الأسبوع المشرق بعد الفصح خالٍ من الصوم.", "bright_week")
    if pentecost_monday <= day <= pentecost_week_end:
        return _fasting_profile("fast_free", "أسبوع ما بعد العنصرة", "الأسبوع التالي لعيد العنصرة خالٍ من الصوم.", "pentecost_fast_free_week")
    if (jm == 12 and jd >= 25) or (jm == 1 and jd <= 4):
        return _fasting_profile("fast_free", "أيام الميلاد", "من عيد الميلاد حتى اليوم السابق لبرامون الظهور الإلهي لا صوم عام.", "nativity_to_theophany_fast_free")
    if old_key in {(1, 6), (6, 29), (8, 15), (12, 25)}:
        return _fasting_profile("fast_free", "عيد سيدي أو عيد كبير", "اليوم عيد كبير وتنتهي فيه فترة الصوم المرتبطة به.", "major_feast_fast_free")

    # Cheesefare week: no meat, but dairy/eggs/fish/wine/oil are allowed.
    cheesefare_start = pascha - timedelta(days=55)
    cheesefare_end = pascha - timedelta(days=49)
    if cheesefare_start <= day <= cheesefare_end:
        return _fasting_profile("dairy_allowed", "أسبوع مرفع الجبن", "أسبوع التهيئة السابق للصوم الكبير: يُمتنع عن اللحم وتبقى الألبان والبيض والسمك مسموحة.", "cheesefare_week")

    # Great Lent and Holy Week.
    lent_start = pascha - timedelta(days=48)
    holy_saturday = pascha - timedelta(days=1)
    palm_sunday = pascha - timedelta(days=7)
    if lent_start <= day <= holy_saturday:
        if old_key == (3, 25) or day == palm_sunday:
            return _fasting_profile("fish_allowed", "الصوم الكبير", "فسحة عيد البشارة أو أحد الشعانين داخل الصوم الكبير.", "great_lent_fish_exception")
        if weekday in (5, 6) and day != holy_saturday:
            return _fasting_profile("wine_oil", "الصوم الكبير", "في سبوت وآحاد الصوم الكبير يُسمح بالزيت والنبيذ، ما عدا السبت العظيم.", "great_lent_weekend_wine_oil")
        return _fasting_profile("strict", "الصوم الكبير أو أسبوع الآلام", "اليوم داخل الصوم الكبير أو أسبوع الآلام.", "great_lent_strict")

    # One-day strict fasts on the old calendar.
    if old_key in {(1, 5), (8, 29), (9, 14)}:
        names = {(1, 5): "برامون الظهور الإلهي", (8, 29): "قطع رأس القديس يوحنا المعمدان", (9, 14): "رفع الصليب الكريم"}
        return _fasting_profile("strict", names[old_key], f"{names[old_key]} يوم صوم صارم.", "single_day_strict_fast")

    # Apostles' Fast: Mon/Wed/Fri strict, Tue/Thu wine+oil, weekends fish.
    if apostles_start <= day <= apostles_end:
        if old_key == (6, 24) or weekday in (5, 6):
            return _fasting_profile("fish_allowed", "صوم الرسل", "في عطلة نهاية الأسبوع، وكذلك في عيد ميلاد السابق، تُعطى فسحة السمك والزيت والنبيذ.", "apostles_fast_fish")
        if weekday in (1, 3):
            return _fasting_profile("wine_oil", "صوم الرسل", "في الثلاثاء والخميس من صوم الرسل يُسمح بالزيت والنبيذ بحسب القاعدة العامة.", "apostles_fast_tue_thu")
        return _fasting_profile("strict", "صوم الرسل", "في الإثنين والأربعاء والجمعة من صوم الرسل تكون القاعدة العامة صارمة.", "apostles_fast_mon_wed_fri")

    # Dormition Fast.
    if jm == 8 and 1 <= jd <= 14:
        if old_key == (8, 6):
            return _fasting_profile("fish_allowed", "صوم السيدة والدة الإله", "عيد التجلي الإلهي داخل صوم الرقاد وله فسحة السمك والزيت والنبيذ.", "dormition_transfiguration_fish")
        if weekday in (5, 6):
            return _fasting_profile("wine_oil", "صوم السيدة والدة الإله", "في سبوت وآحاد صوم الرقاد يُسمح بالزيت والنبيذ.", "dormition_weekend_wine_oil")
        return _fasting_profile("strict", "صوم السيدة والدة الإله", "اليوم داخل صوم رقاد السيدة والدة الإله.", "dormition_strict")

    # Nativity Fast. From 20-24 December old style there is no fish even on weekends.
    if (jm == 11 and jd >= 15) or (jm == 12 and jd <= 24):
        if old_key == (11, 21):
            return _fasting_profile("fish_allowed", "صوم الميلاد", "عيد دخول والدة الإله إلى الهيكل له فسحة السمك والزيت والنبيذ.", "nativity_entry_theotokos_fish")
        late_nativity = jm == 12 and 20 <= jd <= 24
        if weekday in (5, 6):
            level = "wine_oil" if late_nativity else "fish_allowed"
            reason = "في الأيام الأخيرة قبل الميلاد لا تُعطى فسحة السمك، ويُسمح في نهاية الأسبوع بالزيت والنبيذ." if late_nativity else "في سبوت وآحاد صوم الميلاد قبل الأيام الأخيرة تُعطى فسحة السمك والزيت والنبيذ."
            return _fasting_profile(level, "صوم الميلاد", reason, "nativity_weekend")
        if weekday in (1, 3):
            return _fasting_profile("wine_oil", "صوم الميلاد", "في الثلاثاء والخميس من صوم الميلاد يُسمح بالزيت والنبيذ بحسب القاعدة العامة.", "nativity_tue_thu")
        return _fasting_profile("strict", "صوم الميلاد", "في الإثنين والأربعاء والجمعة من صوم الميلاد تكون القاعدة العامة صارمة.", "nativity_mon_wed_fri")

    # Great-feast relaxation when a feast falls on a weekly fast day.
    if old_key in {(2, 2), (3, 25), (8, 6), (9, 8), (11, 21)} and weekday in (2, 4):
        return _fasting_profile("fish_allowed", "عيد كبير", "وقع عيد كبير في يوم صوم أسبوعي، فتُعطى فسحة السمك والزيت والنبيذ بحسب القاعدة العامة.", "major_feast_weekly_fast_relaxation")

    # Ordinary Wednesday and Friday fast.
    if weekday in (2, 4):
        return _fasting_profile("strict", "صوم الأربعاء أو الجمعة", "صوم أسبوعي بحسب التقليد الأرثوذكسي، ما لم توجد فسحة موثقة أو تدبير محلي.", "weekly_wednesday_friday")

    return _fasting_profile("fast_free", "يوم عادي", "لا توجد فترة صوم عامة أو قاعدة أسبوعية لهذا اليوم.", "ordinary_fast_free")


def day_info(day: date) -> dict:
    jy, jm, jd = gregorian_to_julian_date(day)
    pascha = orthodox_pascha_gregorian(day.year)
    apostles_start = pascha + timedelta(days=57)  # Monday after All Saints Sunday
    apostles_end = julian_to_gregorian_date(day.year, 6, 28)  # Eve of Peter and Paul on old calendar
    feast = fixed_old_feast(jm, jd) or "تذكار اليوم بحسب التقويم الكنسي القديم"
    fasting = fasting_profile(day, jm, jd, pascha, apostles_start, apostles_end)

    return {
        "julian_year": jy,
        "julian_month": jm,
        "julian_day": jd,
        "julian_label_ar": ar_julian_label(day),
        "pascha": pascha,
        "apostles_start": apostles_start,
        "apostles_end": apostles_end,
        "feast_ar": feast,
        "fast_ar": fasting["title"]["ar"],
        "fast_detail_ar": fasting["detail"]["ar"],
        "is_fast": fasting["is_fast"],
        "fasting": fasting,
    }


BOOK_AR = {
    "Romans": "رومية", "Matthew": "متى", "Mark": "مرقس", "Luke": "لوقا", "John": "يوحنا",
    "Acts": "أعمال الرسل", "1 Corinthians": "١ كورنثوس", "2 Corinthians": "٢ كورنثوس",
    "Galatians": "غلاطية", "Ephesians": "أفسس", "Philippians": "فيلبي", "Colossians": "كولوسي",
    "1 Thessalonians": "١ تسالونيكي", "2 Thessalonians": "٢ تسالونيكي", "1 Timothy": "١ تيموثاوس",
    "2 Timothy": "٢ تيموثاوس", "Titus": "تيطس", "Philemon": "فليمون", "Hebrews": "عبرانيين",
    "James": "يعقوب", "1 Peter": "١ بطرس", "2 Peter": "٢ بطرس", "1 John": "١ يوحنا",
    "2 John": "٢ يوحنا", "3 John": "٣ يوحنا", "Jude": "يهوذا", "Revelation": "الرؤيا",
}


def reading_loc(ar: str = "", en: str = "", el: str = "") -> dict:
    return {"ar": ar or "", "en": en or "", "el": el or ""}


def arabic_reference(display: str) -> str:
    ref = display or ""
    ref = ref.replace("(Epistle)", "").replace("(Gospel)", "").strip()
    # Longest keys first so 1 Corinthians is replaced before Corinthians.
    for en, ar in sorted(BOOK_AR.items(), key=lambda x: -len(x[0])):
        ref = re.sub(rf"\b{re.escape(en)}\b", ar, ref)
    ref = ref.replace(".", ":")
    return ref.strip()


def clean_html_text(value: str) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def passage_to_text(reading: dict) -> str:
    passage = reading.get("passage") or []
    if isinstance(passage, list) and passage:
        lines = []
        for verse in passage:
            if not isinstance(verse, dict):
                continue
            number = str(verse.get("verse") or verse.get("number") or "").strip()
            content = clean_html_text(verse.get("content") or verse.get("text") or verse.get("html") or "")
            if content:
                lines.append(f"{number} {content}".strip())
        if lines:
            return "\n".join(lines)
    return clean_html_text(reading.get("text") or reading.get("body") or "")


SUNDAY_PROKEIMENA_REGISTRY = json.loads((ROOT / "canonical" / "sunday_prokeimena.json").read_text(encoding="utf-8"))
SUNDAY_PROKEIMENA = {
    int(tone): (entry["verse"], entry["stich"])
    for tone, entry in SUNDAY_PROKEIMENA_REGISTRY["tones"].items()
}
DAILY_PROPERS_REGISTRY = json.loads((ROOT / "canonical" / "daily_propers.json").read_text(encoding="utf-8"))


def _localized(value: object) -> dict:
    if not isinstance(value, dict):
        return loc(str(value or ""))
    return {lang: str(value.get(lang) or "") for lang in ("ar", "en", "el")}


def _has_text(value: object) -> bool:
    return isinstance(value, dict) and any(str(value.get(lang) or "").strip() for lang in ("ar", "en", "el"))


def _proper_sources(entry: dict | None = None) -> dict:
    if isinstance(entry, dict) and isinstance(entry.get("sources"), dict):
        return entry["sources"]
    return DAILY_PROPERS_REGISTRY.get("weekly_sources", {})


def _native_verification(body: dict, sources: dict, canonical_reference: str = "") -> dict:
    result = {}
    for lang in ("ar", "en", "el"):
        text = str(body.get(lang) or "")
        source = sources.get(lang) if isinstance(sources.get(lang), dict) else {}
        if text and source.get("source_id"):
            result[lang] = {
                "status": "VERIFIED_EXACT_NATIVE_SOURCE",
                "source_id": source.get("source_id"),
                "source_url": source.get("url"),
                "canonical_reference": canonical_reference,
                "reference_available": True,
                "text_available": True,
                "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "ai_translation_used": False,
                "automatic_diacritization_used": False,
            }
        else:
            result[lang] = {
                "status": "UNAVAILABLE_UNTIL_EXACT_OFFICIAL_NATIVE_SOURCE",
                "source_id": None,
                "canonical_reference": canonical_reference,
                "reference_available": False,
                "text_available": False,
                "ai_translation_used": False,
                "automatic_diacritization_used": False,
            }
    return result


def fixed_proper_entry(info: dict) -> dict | None:
    key = f"{int(info['julian_month']):02d}-{int(info['julian_day']):02d}"
    entry = DAILY_PROPERS_REGISTRY.get("fixed_feasts", {}).get(key)
    return copy.deepcopy(entry) if isinstance(entry, dict) else None



def resurrection_tone(day: date, pascha: date) -> int | None:
    """Return Byzantine resurrection tone for Sundays after Pascha when applicable."""
    if day.weekday() != 6 or day < pascha + timedelta(days=7):
        return None
    weeks = (day - pascha).days // 7
    return ((weeks - 1) % 8) + 1


def reading_block_loc(reading: dict, prefer_empty_ar_when_missing: bool = False) -> dict:
    """Return a renderable localized reading block without cross-language fallback.

    Exact native text is shown only when its same-language verification and hash
    are valid. Before the native corpus stage fills a reading, keep only its
    verified reference; never inject an "unavailable" sentence into the service.
    """
    ref = reading.get("reference", {}) if isinstance(reading.get("reference"), dict) else {}
    body = reading.get("body", {}) if isinstance(reading.get("body"), dict) else {}
    native = reading.get("native_source_verification") if isinstance(reading.get("native_source_verification"), dict) else {}
    legacy = reading.get("translation_verification") if isinstance(reading.get("translation_verification"), dict) else {}
    canonical_ref = str(reading.get("integrity", {}).get("canonical_reference") or "")
    out = {"ar": "", "en": "", "el": ""}
    for lang in ("ar", "en", "el"):
        lang_ref = str(ref.get(lang) or "").strip()
        lang_body = str(body.get(lang) or "").strip()
        evidence = native.get(lang) if isinstance(native.get(lang), dict) else {}
        exact_native = (
            evidence.get("status") in {"VERIFIED_EXACT_NATIVE_SOURCE", "IMPORTED_EXACT_OFFICIAL_NATIVE_CORPUS", "IMPORTED_EXACT_PUBLIC_DOMAIN_NATIVE_CORPUS"}
            and bool(lang_body)
            and evidence.get("text_sha256") == hashlib.sha256(lang_body.encode("utf-8")).hexdigest()
            and evidence.get("ai_translation_used") is False
            and evidence.get("automatic_diacritization_used") is False
            and evidence.get("canonical_reference") in (None, "", canonical_ref)
        )
        # Legacy compatibility for previously verified independent translations.
        legacy_check = legacy.get(lang) if isinstance(legacy.get(lang), dict) else {}
        exact_legacy = (
            lang in {"en", "el"}
            and legacy_check.get("status") == "VERIFIED_EXACT_TRANSLATION"
            and bool(lang_body)
            and legacy_check.get("body_sha256") == hashlib.sha256(lang_body.encode("utf-8")).hexdigest()
            and legacy_check.get("ai_translation_used") is False
            and bool(str(legacy_check.get("source") or "").strip())
            and legacy_check.get("canonical_reference") in (None, "", canonical_ref)
        )
        if exact_native or exact_legacy:
            out[lang] = (lang_ref + "\n" + lang_body).strip() if lang_ref else lang_body
        else:
            out[lang] = lang_ref
    return out


def _prokeimenon_reading(entry: dict, sources: dict, provenance: str) -> dict:
    body = _localized(entry.get("body"))
    reference = _localized(entry.get("reference"))
    title = _localized(entry.get("title"))
    tone = entry.get("tone")
    canonical_reference = str(entry.get("canonical_reference") or "")
    return {
        "icon": "🎵",
        "kind": "prokeimenon",
        "title": title,
        "reference": reference,
        "body": body,
        "tone": tone,
        "source": {lang: str((sources.get(lang) or {}).get("url") or "") for lang in ("ar", "en", "el")},
        "native_source_verification": _native_verification(body, sources, canonical_reference),
        "translation_locked": True,
        "integrity": {
            "status": "VERIFIED_EXACT_NATIVE_SOURCE",
            "canonical_reference": canonical_reference,
            "proper_provenance": provenance,
            "ai_translation_used": False,
            "automatic_diacritization_used": False,
        },
    }


def exact_or_sunday_prokeimenon(day: date, info: dict) -> dict:
    feast = fixed_proper_entry(info)
    if feast and isinstance(feast.get("prokeimenon"), dict):
        return _prokeimenon_reading(feast["prokeimenon"], _proper_sources(feast), f"fixed_feast:{feast.get('id')}")

    tone = resurrection_tone(day, info["pascha"])
    if tone:
        verse, stich = SUNDAY_PROKEIMENA[tone]
        entry = {
            "tone": tone,
            "title": {"ar": f"البروكيمنن — اللحن {tone}", "en": f"Prokeimenon — Tone {tone}", "el": f"Προκείμενον — Ἦχος {tone}"},
            "reference": {"ar": f"لحن القيامة {tone}", "en": f"Resurrection Tone {tone}", "el": f"Ἀναστάσιμος Ἦχος {tone}"},
            "body": {lang: f"{verse.get(lang, '')}\n{stich.get(lang, '')}".strip() for lang in ("ar", "en", "el")},
        }
        sources = {
            lang: {
                "source_id": SUNDAY_PROKEIMENA_REGISTRY.get("source_ids", {}).get(lang),
                "url": SUNDAY_PROKEIMENA_REGISTRY.get("source_urls", {}).get(lang),
            } for lang in ("ar", "en", "el")
        }
        return _prokeimenon_reading(entry, sources, f"octoechos_tone:{tone}")

    weekday = DAILY_PROPERS_REGISTRY.get("weekday_prokeimena", {}).get(str(day.weekday()))
    if isinstance(weekday, dict):
        return _prokeimenon_reading(weekday, _proper_sources(), f"weekday:{day.weekday()}")
    raise RuntimeError(f"No prokeimenon registry entry for weekday {day.weekday()}")

def default_prokeimenon(info: dict, day: date | None = None) -> dict:
    return exact_or_sunday_prokeimenon(day or date.today(), info)


def reading_defaults(info: dict, day: date | None = None) -> list[dict]:
    day = day or date.today()
    if info["julian_month"] == 6 and info["julian_day"] == 29:
        return [
            default_prokeimenon(info, day),
            {"icon":"📜","kind":"epistle","title":loc("الرسالة","Epistle"),"reference":reading_loc("٢ كورنثوس 11:21–12:9","2 Corinthians 11:21–12:9"),"body":reading_loc("أيها الإخوة، بما أن كثيرين يفتخرون حسب الجسد، فأنا أيضاً أفتخر؛ أقول هذا لا كمن يتكلم بحسب الرب، بل كمن في ضعف. لقد تعبت أكثر، وجلدت أكثر، وتعرضت للأخطار والأسفار والجوع والعطش والسهر، ومع هذا كله كان عليّ اهتمام الكنائس. ولئلا أرتفع من فرط الإعلانات، أُعطيت شوكة في الجسد. من أجل هذا طلبت إلى الرب أن تفارقني، فقال لي: تكفيك نعمتي، لأن قوتي في الضعف تكمل.")},
            {"icon":"📖","kind":"gospel","title":loc("الإنجيل","Gospel"),"reference":reading_loc("متى 16:13–19","Matthew 16:13–19"),"body":reading_loc("في ذلك الزمان، جاء يسوع إلى نواحي قيصرية فيلبس، وسأل تلاميذه قائلاً: من يقول الناس إني أنا ابن الإنسان؟ فقالوا: قوم يقولون يوحنا المعمدان، وآخرون إيليا، وآخرون إرميا أو واحد من الأنبياء. قال لهم: وأنتم، من تقولون إني أنا؟ فأجاب سمعان بطرس وقال: أنت هو المسيح ابن الله الحي. فأجابه يسوع: طوبى لك يا سمعان بن يونا، لأن لحماً ودماً لم يعلنا لك، بل أبي الذي في السماوات. وأنا أقول لك أيضاً: أنت بطرس، وعلى هذه الصخرة أبني كنيستي، وأبواب الجحيم لن تقوى عليها.")},
        ]
    if info["julian_month"] == 6 and info["julian_day"] == 26:
        return [
            default_prokeimenon(info, day),
            {"icon":"📜","kind":"epistle","title":loc("الرسالة","Epistle"),"reference":reading_loc("رومية 11:25–36","Romans 11.25-36"),"body":reading_loc("أيها الإخوة، لا أريد أن تجهلوا هذا السر، لئلا تكونوا حكماء عند أنفسكم: إن قساوة جزئية قد أصابت إسرائيل إلى أن يدخل ملء الأمم، وهكذا يخلص إسرائيل كله، كما هو مكتوب: سيأتي من صهيون المنقذ، ويرد الفجور عن يعقوب. هذه هي عهدي معهم حين أرفع خطاياهم. أما من جهة الإنجيل فهم أعداء لأجلكم، وأما من جهة الاختيار فهم محبوبون من أجل الآباء، لأن هبات الله ودعوته بلا ندامة. فكما أنكم أنتم عصيتم الله سابقاً ونلتم الآن رحمة بسبب عصيانهم، هكذا هم أيضاً قد عصوا الآن لكي ينالوا هم أيضاً رحمة. لأن الله أغلق على الجميع في العصيان لكي يرحم الجميع. يا لعمق غنى الله وحكمته وعلمه! ما أبعد أحكامه عن الفحص وطرقه عن الاستقصاء! من عرف فكر الرب؟ أو من صار له مشيراً؟ أو من أعطاه أولاً فيكافأ؟ لأن منه وبه وله كل الأشياء. له المجد إلى الدهور. آمين.")},
            {"icon":"📖","kind":"gospel","title":loc("الإنجيل","Gospel"),"reference":reading_loc("متى 12:1–8","Matthew 12.1-8"),"body":reading_loc("في ذلك الزمان، سار يسوع في السبت بين الزروع، فجاع تلاميذه وابتدأوا يقطفون سنابل ويأكلون. فلما رأى الفريسيون قالوا له: هوذا تلاميذك يفعلون ما لا يحل فعله في السبت. فقال لهم: أما قرأتم ما فعله داود حين جاع هو والذين معه، كيف دخل بيت الله وأكل خبز التقدمة الذي لم يكن يحل له أن يأكله ولا للذين معه، بل للكهنة وحدهم؟ أو ما قرأتم في الناموس أن الكهنة في الهيكل يكسرون السبت وهم بلا لوم؟ ولكن أقول لكم إن ههنا أعظم من الهيكل. ولو عرفتم معنى القول: إني أريد رحمة لا ذبيحة، لما حكمتم على الأبرياء، فإن ابن الإنسان هو رب السبت أيضاً.")},
        ]
    return [
        default_prokeimenon(info, day),
        {"icon":"📜","kind":"epistle","title":loc("الرسالة","Epistle"),"reference":loc("غير منشورة قبل التحقق الرسمي","Not published before official verification"),"body":reading_loc(),"publication_status":"BLOCKED_MISSING_OFFICIAL_REFERENCE"},
        {"icon":"📖","kind":"gospel","title":loc("الإنجيل","Gospel"),"reference":loc("غير منشور قبل التحقق الرسمي","Not published before official verification"),"body":reading_loc(),"publication_status":"BLOCKED_MISSING_OFFICIAL_REFERENCE"},
    ]


def readings_from_orthocal(src: dict | None, info: dict, day: date | None = None) -> list[dict]:
    day = day or date.today()
    if not src:
        return reading_defaults(info, day)

    raw_readings = src.get("readings") or []
    indices = src.get("abbreviated_reading_indices") or []
    selected = []
    if isinstance(indices, list) and indices:
        for index in indices:
            try:
                selected.append(raw_readings[int(index)])
            except Exception:
                pass
    if not selected:
        selected = raw_readings

    out = [default_prokeimenon(info, day)]
    seen_kinds = {"prokeimenon"}
    for r in selected[:8]:
        if not isinstance(r, dict):
            continue
        display = r.get("display") or r.get("source") or r.get("book") or "Reading"
        lower = display.lower()
        is_gospel = any(x in lower for x in ["matt", "mark", "luke", "john", "gospel"])
        kind = "gospel" if is_gospel else "epistle"
        if kind in seen_kinds:
            continue
        seen_kinds.add(kind)
        en_text = passage_to_text(r)
        ar_ref = arabic_reference(display)
        out.append({
            "icon": "📖" if is_gospel else "📜",
            "kind": kind,
            "title": loc("الإنجيل" if is_gospel else "الرسالة", "Gospel" if is_gospel else "Epistle"),
            "reference": reading_loc(ar_ref, display),
            "body": reading_loc(),
            "discovery_text": en_text or "",
            "source": loc("المصدر: Orthocal old-calendar API لاكتشاف المرجع فقط. لا يُنشر النص قبل حقن النسخة العربية الرسمية والتحقق منها.", "Source: Orthocal old-calendar API for reference discovery only."),
        })
    if len(out) < 3:
        defaults = reading_defaults(info, day)
        for d in defaults:
            if d.get("kind") not in {x.get("kind") for x in out}:
                out.append(d)
    return out


def load_library_service(service_id: str) -> dict:
    lib = json.loads(LIBRARY_PATH.read_text(encoding="utf-8"))
    for service in lib.get("services", []):
        if service.get("id") == service_id:
            return copy.deepcopy(service)
    raise RuntimeError(f"Missing base service {service_id!r} in app library")


def load_base_liturgy_segments() -> list[dict]:
    service = load_library_service("divine_liturgy")
    segments = copy.deepcopy(service.get("segments", []))
    # The daily service builder creates its own updated pre-liturgy section,
    # with feast/fast inserts. The offline base text also contains a pre-liturgy
    # section, so remove that first static block to avoid duplication.
    if segments and segments[0].get("type") == "section" and segments[0].get("title", {}).get("ar") == "صلوات قبل القداس":
        start = 0
        for idx, seg in enumerate(segments):
            if seg.get("type") == "section" and seg.get("title", {}).get("ar") == "الاستعداد وبداية القداس":
                start = idx
                break
        if start:
            segments = segments[start:]
    return segments


def get_reading(readings: list[dict], kind: str) -> dict | None:
    for r in readings:
        if r.get("kind") == kind:
            return r
    return None



def reading_references(readings: list[dict]) -> dict:
    """Compact epistle/Gospel references for upcoming-day cards."""
    result: dict[str, dict] = {}
    for kind in ("epistle", "gospel"):
        reading = get_reading(readings, kind)
        if not reading:
            continue
        result[kind] = {
            "title": copy.deepcopy(reading.get("title") or loc("الرسالة" if kind == "epistle" else "الإنجيل")),
            "reference": copy.deepcopy(reading.get("reference") or loc("")),
        }
    return result


def synchronize_next_sunday_schedule(data: dict, next_readings: list[dict] | None = None, source: str | None = None) -> dict:
    """Keep next-Sunday cards synchronized with the verified reading payload.

    Native Scripture is resolved after the initial seven-day schedule is built.
    This final synchronization prevents a complete next-Sunday Epistle/Gospel
    from remaining hidden behind stale or empty preview references.
    """
    integrity_next = (data.get("integrity_inputs") or {}).get("next_sunday") or {}
    readings = next_readings if isinstance(next_readings, list) else integrity_next.get("readings")
    if not isinstance(readings, list):
        raise ValueError("missing integrity_inputs.next_sunday.readings")

    refs = reading_references(readings)
    for kind in ("epistle", "gospel"):
        block = refs.get(kind) if isinstance(refs, dict) else None
        reference = block.get("reference") if isinstance(block, dict) else None
        has_reference = isinstance(reference, dict) and any(str(reference.get(lang) or "").strip() for lang in ("ar", "en", "el"))
        if not has_reference:
            raise ValueError(f"next Sunday {kind} reference is missing after native-corpus resolution")

    sunday = data.get("next_sunday")
    if not isinstance(sunday, dict):
        raise ValueError("missing next_sunday object")
    sunday["reading_references"] = copy.deepcopy(refs)
    next_date = str(sunday.get("date_iso") or integrity_next.get("date_iso") or "")
    if not next_date:
        raise ValueError("missing next_sunday.date_iso")

    matched = False
    for item in data.get("upcoming") or []:
        if not isinstance(item, dict) or str(item.get("date") or "") != next_date:
            continue
        item["reading_references"] = copy.deepcopy(refs)
        item["verification_status"] = "VERIFIED_NEXT_SUNDAY_REFERENCES"
        if source:
            item["source"] = source
        matched = True
    if not matched:
        raise ValueError("next Sunday is missing from the seven-day upcoming list")
    return refs


def feast_inserts(info: dict) -> dict[str, dict]:
    entry = fixed_proper_entry(info)
    if entry:
        return {
            "troparion": _localized(entry.get("troparion")),
            "kontakion": _localized(entry.get("kontakion")),
            "church_troparion": loc(""),
            "communion": _localized(entry.get("communion")),
            "evangelist": loc("الإنجيلي", "Evangelist", "Εὐαγγελιστής"),
            "proper_id": entry.get("id"),
            "sources": copy.deepcopy(entry.get("sources") or {}),
        }
    return {
        "troparion": loc(""),
        "kontakion": loc(""),
        "church_troparion": loc(""),
        "communion": loc(""),
        "evangelist": loc("الإنجيلي", "Evangelist", "Εὐαγγελιστής"),
        "proper_id": None,
        "sources": {},
    }

def evangelist_for_reading(reading: dict) -> str:
    ref = str(reading.get("reference", {}).get("ar") or reading.get("reference", {}).get("en") or "")
    if "متى" in ref or "Matthew" in ref:
        return "متى البشير"
    if "مرقس" in ref or "Mark" in ref:
        return "مرقس البشير"
    if "لوقا" in ref or "Luke" in ref:
        return "لوقا البشير"
    if "يوحنا" in ref or "John" in ref:
        return "يوحنا البشير"
    return "الإنجيلي"


def replace_placeholders(text: str, replacements: dict[str, str]) -> str:
    out = text
    for k, v in replacements.items():
        out = out.replace(k, v)
    return out


def merge_loc_with_inline_placeholders(text_obj: dict, exact: dict[str, dict], inline: dict[str, dict]) -> dict:
    """Replace liturgy placeholders per language.

    Exact reading placeholders become full localized objects.  This is important
    because some non-scripture translations may be completed manually after the update
    step; we must not insert a fake Arabic placeholder before translation.
    """
    if not isinstance(text_obj, dict):
        return text_obj
    values = [v.strip() for v in text_obj.values() if isinstance(v, str)]
    for marker, loc_obj in exact.items():
        if any(v == marker for v in values):
            return copy.deepcopy(loc_obj)
    out = copy.deepcopy(text_obj)
    for lang in ("ar", "en", "el"):
        val = out.get(lang, "")
        if not isinstance(val, str):
            continue
        for marker, loc_obj in inline.items():
            replacement = loc_obj.get(lang) or (loc_obj.get("ar") if lang == "ar" else "") or ""
            val = val.replace(marker, replacement)
        out[lang] = val
    return out


BANNED_GUIDANCE_PLACEHOLDERS = (
    "راجع الكنيسة",
    "راجع النص الكنسي",
    "راجع كتاب الخدمة المحلي",
    "أضفه في ملف override",
    "تضاف هنا القطع",
    "تُضاف هنا القطع",
    "تُوضع الاستيخيرات",
)


def sanitize_segments(segments: list[dict]) -> list[dict]:
    """Remove placeholder guidance and collapse genuine notes by default."""
    cleaned: list[dict] = []
    for original in segments:
        if not isinstance(original, dict):
            continue
        seg = copy.deepcopy(original)
        ar_text = str(seg.get("text", {}).get("ar") or "") if isinstance(seg.get("text"), dict) else ""
        if any(marker in ar_text for marker in BANNED_GUIDANCE_PLACEHOLDERS):
            continue
        speaker = seg.get("speaker")
        if isinstance(speaker, dict) and str(speaker.get("ar") or "").strip() == "إرشاد":
            seg["speaker"] = loc("ملاحظة اختيارية", "Optional note", "Προαιρετικὴ σημείωση")
            seg["type"] = "note"
            seg["collapsed_by_default"] = True
        elif seg.get("type") == "note":
            seg["collapsed_by_default"] = True
        cleaned.append(seg)
    return cleaned


def liturgy_text_segment(speaker_ar: str, text_ar: str, kind: str = "text") -> dict:
    if speaker_ar == "ملاحظة اختيارية" and kind in {"rubric", "text"}:
        kind = "note"
    return {"type": kind, "speaker": loc(speaker_ar), "text": loc(text_ar)}


def liturgy_section(title_ar: str) -> dict:
    return {"type": "section", "title": loc(title_ar)}


def pre_liturgy_segments(info: dict, inserts: dict[str, str]) -> list[dict]:
    segments: list[dict] = [
        liturgy_section("صلوات قبل القداس"),
        liturgy_text_segment("ملاحظة اختيارية", "هذه الصلوات تهيئة اختيارية قبل القداس الإلهي."),
        liturgy_text_segment("ملاحظة اختيارية", f"اليوم الكنسي: {info['feast_ar']}. حالة الصوم: {info['fast_ar']}.", "rubric"),
    ]
    for title, speaker, text in PRE_LITURGY_PRAYERS:
        segments.append(liturgy_section(title))
        segments.append(liturgy_text_segment(speaker, text))
    proper_segments: list[dict] = []
    if _has_text(inserts["troparion"]) or _has_text(inserts["kontakion"]):
        proper_segments.append(liturgy_section("قطع اليوم قبل القداس"))
        if _has_text(inserts["troparion"]):
            proper_segments.append({"type": "text", "speaker": loc("المرتل", "Chanter", "Ψάλτης"), "text": copy.deepcopy(inserts["troparion"])})
        if _has_text(inserts["kontakion"]):
            proper_segments.append({"type": "text", "speaker": loc("المرتل", "Chanter", "Ψάλτης"), "text": copy.deepcopy(inserts["kontakion"])})
    segments.extend(proper_segments)
    segments.append(liturgy_section("بداية القداس الإلهي"))
    return segments


def build_liturgy_service(service_id: str, day: date, info: dict, readings: list[dict], label_prefix_ar: str) -> dict:
    """Create a small daily overlay instead of duplicating the static Liturgy.

    The Android repository composes this object with ``library:divine_liturgy``
    and applies the exact placeholder replacements after signature verification.
    """
    epistle = get_reading(readings, "epistle") or {}
    gospel = get_reading(readings, "gospel") or {}
    prok = get_reading(readings, "prokeimenon") or {}
    inserts = feast_inserts(info)

    exact_replacements = {
        "[طروبارية اليوم]": copy.deepcopy(inserts["troparion"]),
        "[طروبارية صاحب الكنيسة أو القديس إن وُجدت]": copy.deepcopy(inserts["church_troparion"]),
        "[القنداق]": copy.deepcopy(inserts["kontakion"]),
        "[البروكيمنن]": reading_block_loc(prok, prefer_empty_ar_when_missing=False),
        "[فصل من رسالة اليوم]": reading_block_loc(epistle, prefer_empty_ar_when_missing=True),
        "[فصل الإنجيل المعيّن لهذا اليوم]": reading_block_loc(gospel, prefer_empty_ar_when_missing=True),
        "[آية المناولة]": copy.deepcopy(inserts["communion"]),
    }
    inline_replacements = {
        "[اسم الإنجيلي]": loc(evangelist_for_reading(gospel)),
    }

    is_upcoming = service_id == "next_sunday_full_liturgy"
    title = loc(
        f"{label_prefix_ar} — القداس الإلهي",
        "Next Sunday — Divine Liturgy" if is_upcoming else "Today — Divine Liturgy",
        "Ἡ ἐρχόμενη Κυριακή — Θεία Λειτουργία" if is_upcoming else "Σήμερα — Θεία Λειτουργία",
    )
    summary = loc(
        f"{info['feast_ar']} — {info['fast_ar']} — تُركّب قراءات اليوم والقطع المتحققة فوق نص القداس الثابت دون تكراره.",
        "Verified daily readings and feast texts are composed with the single static Liturgy template.",
        "Τὰ ἐπαληθευμένα ἀναγνώσματα καὶ κείμενα τῆς ἡμέρας συντίθενται μὲ τὸ μοναδικὸ σταθερὸ πρότυπο τῆς Θείας Λειτουργίας.",
    )
    segments = sanitize_segments([
        {"type": "section", "title": loc(f"{label_prefix_ar}: ملحق اليوم")},
        {
            "type": "note",
            "speaker": loc("ملاحظة اختيارية", "Optional note", "Προαιρετικὴ σημείωση"),
            "text": loc(
                f"التاريخ المدني: {ar_date_label(day)}. التاريخ الكنسي القديم: {info['julian_label_ar']}. حالة اليوم: {info['fast_ar']}. التذكار: {info['feast_ar']}.",
                f"Civil date: {day:%Y-%m-%d}. Verified daily texts are inserted below where available.",
                f"Πολιτικὴ ἡμερομηνία: {day:%Y-%m-%d}. Τὰ ἐπαληθευμένα κείμενα τῆς ἡμέρας εἰσάγονται ὅπου διατίθενται.",
            ),
        },
        {"type": "section", "title": loc("ترتيب قراءات اليوم", "Order of today’s readings", "Τάξη τῶν σημερινῶν ἀναγνωσμάτων")},
        {
            "type": "note",
            "speaker": loc("ملاحظة اختيارية", "Optional note", "Προαιρετικὴ σημείωση"),
            "text": loc(
                "البروكيمنن، ثم الرسالة، ثم هلليلويا، ثم الإنجيل. أي نص غير موثق في اللغة المختارة يُحجب تلقائيًا.",
                "Prokeimenon, Epistle, Alleluia, and Gospel. Any unverified target-language text is hidden automatically.",
                "Προκείμενον, Ἀπόστολος, Ἀλληλούϊα καὶ Εὐαγγέλιο. Κάθε μὴ ἐπαληθευμένο κείμενο τῆς ἐπιλεγμένης γλώσσας ἀποκρύπτεται αὐτόματα.",
            ),
        },
    ])
    return {
        "id": service_id,
        "extends_service_id": "divine_liturgy",
        "category": "liturgy",
        "icon": "⛪",
        "title": title,
        "summary": summary,
        "source_language": "ar",
        "translation_status": "verified_daily_overlay_v2",
        "template_id": "library:divine_liturgy",
        "dynamic_date": f"{day:%Y-%m-%d}",
        "daily_reading_contract": {
            "authority": "orthodox_jordan",
            "contract": "canonical/jordan_liturgical_contract.json",
            "date_iso": f"{day:%Y-%m-%d}",
            "epistle_canonical": str(epistle.get("integrity", {}).get("canonical_reference") or ""),
            "gospel_canonical": str(gospel.get("integrity", {}).get("canonical_reference") or ""),
            "fail_closed": True,
        },
        "notice": loc(
            "يُحفظ نص القداس الثابت مرة واحدة في المكتبة. ولا تُحقن القطع اليومية إلا بعد نجاح التحقق من المصدر والتوقيع.",
            "The static Liturgy is stored once. Daily pieces are injected only after source and signature validation.",
            "Ἡ σταθερὴ Θεία Λειτουργία ἀποθηκεύεται μία φορά. Τὰ ἡμερήσια κείμενα εἰσάγονται μόνον μετὰ τὴν ἐπαλήθευση πηγῆς καὶ ὑπογραφῆς.",
        ),
        "source_provenance": {
            "policy": "canonical/source_policy.json",
            "official_catalog_source": "orthodox_jordan",
            "official_catalog_url": "https://orthodoxjordan.org/تحميل-الصلوات/",
            "status": "PINNED_STATIC_TEXT_WITH_OFFICIAL_CATALOG_PROVENANCE",
            "complete_service_claim": True,
            "exact_remote_byte_match": False,
            "dynamic_texts_fail_closed": True,
            "ai_liturgical_translation_used": False,
        },
        "segment_replacements": exact_replacements,
        "inline_replacements": inline_replacements,
        "segments": segments,
    }

def daily_context_segments(day: date, info: dict, readings: list[dict], service_id: str) -> list[dict]:
    """Build a clearly marked daily layer for every service.

    The base prayer text remains stable. Only the date-dependent context and
    pieces available from the daily data source are injected. This avoids
    pretending that a generic API supplies every local sticheron or canon.
    """
    inserts = feast_inserts(info)
    segments: list[dict] = [
        liturgy_section("ملحق اليوم الكنسي"),
        liturgy_text_segment(
            "ملاحظة اختيارية",
            f"التاريخ المدني: {ar_date_label(day)}. التاريخ الكنسي القديم: {info['julian_label_ar']}. "
            f"التذكار: {info['feast_ar']}. حالة الصوم: {info['fast_ar']}.",
            "rubric",
        ),
    ]
    if _has_text(inserts["troparion"]) or _has_text(inserts["kontakion"]):
        segments.append(liturgy_section("قطع اليوم"))
        if _has_text(inserts["troparion"]):
            segments.append({"type": "text", "speaker": loc("المرتل", "Chanter", "Ψάλτης"), "text": copy.deepcopy(inserts["troparion"])})
        if _has_text(inserts["kontakion"]):
            segments.append({"type": "text", "speaker": loc("المرتل", "Chanter", "Ψάλτης"), "text": copy.deepcopy(inserts["kontakion"])})
    return segments


def build_daily_aware_service(service_id: str, day: date, info: dict, readings: list[dict]) -> dict:
    base = load_library_service(service_id)
    title_ar = {
        "vespers": "قطع الغروب الموثقة لليوم",
        "orthros": "قطع السَحَر الموثقة لليوم",
        "morning_prayer": "صلاة صباح منزلية مع قطع اليوم",
        "evening_prayer": "صلاة مساء منزلية مع قطع اليوم",
        "small_compline": "صلاة قبل النوم مع قطع اليوم",
    }.get(service_id, f"{base.get('title', {}).get('ar', service_id)} — اليوم")
    return {
        "id": service_id,
        "extends_service_id": service_id,
        "category": base.get("category", "daily"),
        "icon": base.get("icon", "✥"),
        "title": loc(
            title_ar,
            f"{base.get('title', {}).get('en', service_id)} — verified daily texts",
            f"{base.get('title', {}).get('el', service_id)} — ἐπαληθευμένα κείμενα ἡμέρας",
        ),
        "summary": loc(
            f"{info['feast_ar']} — {info['fast_ar']} — يعرض النصوص المتوفرة فعلًا والتي اجتازت التحقق، من دون الادعاء بأنها خدمة ليتورجية كاملة.",
            "Shows only the available texts that passed verification; it does not claim to be a complete office.",
            "Προβάλλει μόνον τὰ διαθέσιμα ἐπαληθευμένα κείμενα, χωρὶς νὰ τὰ παρουσιάζει ὡς πλήρη ἀκολουθία.",
        ),
        "source_language": base.get("source_language", "ar"),
        "translation_status": "daily_context_overlay",
        "dynamic_date": f"{day:%Y-%m-%d}",
        "notice": loc(
            "يُركّب هذا الملحق فوق النص الثابت الموجود مرة واحدة في المكتبة، ولا يكرر الخدمة كاملة داخل ملف كل يوم.",
            "This verified daily overlay is composed with the single static library service at runtime.",
            "Τὸ ἐπαληθευμένο ἡμερήσιο ἐπίθεμα συντίθεται μὲ τὸ μοναδικὸ σταθερὸ κείμενο τῆς βιβλιοθήκης.",
        ),
        "source_provenance": copy.deepcopy(base.get("source_provenance") or {}),
        "segments": sanitize_segments(daily_context_segments(day, info, readings, service_id)),
    }


def next_sunday(day: date) -> date:
    delta = (6 - day.weekday()) % 7
    if delta == 0:
        delta = 7
    return day + timedelta(days=delta)


def apply_override(day: date, data: dict) -> dict:
    path = ROOT / "scripts" / "overrides" / f"{day:%Y-%m-%d}.json"
    if not path.exists():
        return data
    override = json.loads(path.read_text(encoding="utf-8"))
    if ("fast" in override or "fast_detail" in override) and "fasting" not in override:
        raise RuntimeError(
            f"{path.relative_to(ROOT)} changes fasting text without a complete fasting object. "
            "Provide fasting.code, allowed booleans, display_icons, and verification evidence."
        )
    # Shallow update for top-level keys; arrays/objects intentionally replace.
    data.update(override)
    fasting = data.get("fasting")
    if isinstance(fasting, dict) and "fasting" in override:
        verification = fasting.setdefault("verification", {})
        verification["status"] = "DOCUMENTED_OVERRIDE"
        verification["override_file"] = str(path.relative_to(ROOT)).replace("\\", "/")
        data["fast"] = copy.deepcopy(fasting.get("title") or data.get("fast"))
        data["fast_detail"] = copy.deepcopy(fasting.get("detail") or data.get("fast_detail"))
    return data


def discovery_readings(day: date, info: dict) -> list[dict]:
    """Use Orthocal for discovery only; network failure must not stop generation.

    Official Jordan/Jerusalem resolution later replaces these discovery slots.
    A missing discovery API therefore yields blocked placeholders, never guessed
    publication references.
    """
    if os.getenv("ORTHODOX_DISABLE_DISCOVERY_NETWORK") == "1":
        return readings_from_orthocal(None, info, day)
    try:
        return readings_from_orthocal(fetch_orthocal_old(day), info, day)
    except Exception as exc:
        print(f"DISCOVERY_SOURCE_UNAVAILABLE date={day.isoformat()} source=orthocal error={exc}")
        return readings_from_orthocal(None, info, day)


def build_day(day: date) -> dict:
    info = day_info(day)
    readings = discovery_readings(day, info)

    # Generate the next seven civil days every run. Each compact card carries
    # its own fasting profile and reading references, so the app never reuses
    # yesterday's Sunday or fasting information.
    upcoming: list[dict] = []
    upcoming_full_readings: dict[str, list[dict]] = {}
    for i in range(1, 8):
        d = day + timedelta(days=i)
        inf = day_info(d)
        future_readings = discovery_readings(d, inf)
        upcoming_full_readings[d.isoformat()] = future_readings
        refs = reading_references(future_readings)
        upcoming.append({
            "date": f"{d:%Y-%m-%d}",
            "day": loc(f"{AR_DAYS[d.weekday()]} {d.day} {AR_MONTHS[d.month-1]} / {inf['julian_day']} {AR_MONTHS[inf['julian_month']-1]} قديم", d.strftime("%A, %B %d")),
            "feast": loc(inf["feast_ar"]),
            "status": loc(inf["fast_ar"]),
            "note": loc(inf["feast_ar"]),
            "fasting": copy.deepcopy(inf["fasting"]),
            "reading_references": refs,
            "is_sunday": d.weekday() == 6,
        })

    ns = next_sunday(day)
    ns_info = day_info(ns)
    ns_readings = upcoming_full_readings.get(ns.isoformat())
    if ns_readings is None:
        ns_readings = discovery_readings(ns, ns_info)
    ns_refs = reading_references(ns_readings)

    today_service = build_liturgy_service("divine_liturgy", day, info, readings, "خدمة اليوم")
    vespers_service = build_daily_aware_service("vespers", day, info, readings)
    orthros_service = build_daily_aware_service("orthros", day, info, readings)
    morning_service = build_daily_aware_service("morning_prayer", day, info, readings)
    evening_service = build_daily_aware_service("evening_prayer", day, info, readings)
    compline_service = build_daily_aware_service("small_compline", day, info, readings)
    sunday_service = build_liturgy_service("next_sunday_full_liturgy", ns, ns_info, ns_readings, "الأحد القادم")

    next_sunday_payload = {
        "date_iso": f"{ns:%Y-%m-%d}",
        "day": loc(f"{AR_DAYS[ns.weekday()]} {ns.day} {AR_MONTHS[ns.month-1]} / {ns_info['julian_day']} {AR_MONTHS[ns_info['julian_month']-1]} قديم", ns.strftime("%A, %B %d, %Y")),
        "feast": loc(ns_info["feast_ar"]),
        "fast": loc(ns_info["fast_ar"]),
        "fasting": copy.deepcopy(ns_info["fasting"]),
        "reading_references": ns_refs,
        "service_id": "next_sunday_full_liturgy",
    }

    data = {
        "schema_version": 8,
        "app_title": loc("الأجندة الكنسية", "Church Agenda", "Εκκλησιαστική Ατζέντα"),
        "patriarchate": loc("بطريركية الروم الأرثوذكس المقدسية", "Greek Orthodox Patriarchate of Jerusalem", "Πατριαρχεῖον Ἱεροσολύμων"),
        "date_iso": f"{day:%Y-%m-%d}",
        "date_label": loc(f"{ar_date_label(day)} / {info['julian_label_ar']}", day.strftime("%A, %B %d, %Y")),
        "calendar_label": loc("التقويم الكنسي القديم — بطريركية القدس", "Old church calendar — Jerusalem usage"),
        "julian_date": {"year": info["julian_year"], "month": info["julian_month"], "day": info["julian_day"], "label_ar": info["julian_label_ar"]},
        "fast": loc(info["fast_ar"]),
        "fast_detail": loc(info["fast_detail_ar"]),
        "fasting": copy.deepcopy(info["fasting"]),
        "feast": loc(info["feast_ar"]),
        "source_note": loc("تُستخدم بيانات الاكتشاف مؤقتاً فقط؛ ولا يصبح الملف قابلاً للنشر إلا بعد بوابة الأردن ثم القدس ثم أنطاكية ثم المصدر اليوناني الرسمي ثم الكنيسة الأرثوذكسية في أمريكا عند الحاجة."),
        "translation_notice": loc("نصوص الكتاب المقدس من طبعة عربية مثبتة ومشكولة؛ ولا تُستخدم ترجمة آلية حرة للنص المقدس أو للقطع الليتورجية."),
        "translation_status": "source_native_only_or_unavailable",
        "language_content_mode": "THREE_INDEPENDENT_OFFICIAL_NATIVE_SOURCES",
        "machine_translation_used": False,
        "translation_fallback_policy": "DISABLED_NO_CROSS_LANGUAGE_FALLBACK",
        "language_sources": {
            "ar": {
                "policy": "native_official_source_only",
                "primary": ["orthodox_jordan", "jerusalem_patriarchate", "antioch_patriarchate"],
                "translation_allowed": False,
            },
            "el": {
                "policy": "native_official_source_only",
                "primary": ["church_of_greece_apostoliki_diakonia"],
                "fallback": ["goarch_digital_chant_stand"],
                "translation_allowed": False,
            },
            "en": {
                "policy": "native_official_source_only",
                "primary": ["goarch_online_chapel", "goarch_digital_chant_stand"],
                "translation_allowed": False,
            },
        },
        "content_metadata": {
            "calendar_system": "old_calendar_julian",
            "jurisdiction": "jerusalem_patriarchate_usage",
            "source_policy": "canonical/source_policy.json",
            "rights_notice": "CONTENT_RIGHTS.md",
            "review_status": "automatic_official_sources_pending",
            "human_review_required": False,
        },
        "publication": {
            "status": "BLOCKED_PENDING_OFFICIAL_SOURCE_GATE",
            "human_review_required": False,
            "fail_closed": True,
            "source_priority": ["orthodox_jordan", "jerusalem_patriarchate", "antioch_patriarchate", "official_greek_orthodox", "orthodox_church_in_america"],
            "selected_source": None,
            "fallback_trace": [],
        },
        "source_evidence": [],
        "readings": readings,
        "next_sunday": next_sunday_payload,
        "integrity_inputs": {
            "next_sunday": {
                "date_iso": f"{ns:%Y-%m-%d}",
                "readings": ns_readings,
            },
            "upcoming_reference_dates": [item["date"] for item in upcoming],
        },
        "recommended_services": [
            "divine_liturgy",
            "vespers",
            "orthros",
            "morning_prayer",
            "evening_prayer",
            "small_compline",
            "next_sunday_full_liturgy",
        ],
        "services": [
            today_service,
            vespers_service,
            orthros_service,
            morning_service,
            evening_service,
            compline_service,
            sunday_service,
        ],
        "upcoming": upcoming,
    }
    return complete_daily_localizations(apply_override(day, data))


def main() -> None:
    forced = os.getenv("ORTHODOX_DATE", "").strip()
    if forced:
        day = datetime.strptime(forced, "%Y-%m-%d").date()
    else:
        day = datetime.now(TZ).date()
    CALENDAR_DIR.mkdir(parents=True, exist_ok=True)
    SERVICES_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    data = build_day(day)
    out = json.dumps(data, ensure_ascii=False, indent=2)
    (CALENDAR_DIR / "today.json").write_text(out, encoding="utf-8")
    (CALENDAR_DIR / f"{day:%Y-%m-%d}.json").write_text(out, encoding="utf-8")
    # Daily services are already embedded in today.json. Keep only the static
    # library as a separate service file to avoid duplicate generated snapshots.
    for generated_service in SERVICES_DIR.glob("*.json"):
        if generated_service.name != "library.json":
            generated_service.unlink()
    # Deliberately do not write the Android embedded asset here. This generator
    # produces an untrusted candidate. scripts/update.py copies it into the app
    # only after the strict Jordan/date/readings/Liturgy gate has passed.
    active_ids = [service.get("id") for service in data.get("services", []) if service.get("id")]
    manifest = {
        "schema_version": 5,
        "updated_at": datetime.now(TZ).isoformat(),
        "today": "data/calendar/today.json",
        "calendar_mode": "julian_old_calendar",
        "daily_service_ids": active_ids,
    }
    (DATA_DIR / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Generated old-calendar full-service data for {day:%Y-%m-%d}")


if __name__ == "__main__":
    main()
