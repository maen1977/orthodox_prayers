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

from rolling_window_contract import resolve_day_count

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
    "meat": ("Meat and poultry", "Κρέας καὶ πουλερικά"),
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
    "wine_only": ("Wine permitted only", "Ἐπιτρέπεται μόνον οἶνος"),
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
    "annunciation_paschal_collision_wine_oil": ("Annunciation in the first four days of Holy Week", "Εὐαγγελισμὸς στὶς τέσσερις πρῶτες ἡμέρες τῆς Μεγάλης Ἑβδομάδας", "When the Annunciation falls in the first four days of Holy Week, oil and wine are permitted but fish is not.", "Ὅταν ὁ Εὐαγγελισμὸς πέφτει στὶς τέσσερις πρῶτες ἡμέρες τῆς Μεγάλης Ἑβδομάδας, ἐπιτρέπονται ἔλαιο καὶ οἶνος ἀλλὰ ὄχι ψάρι."),
    "annunciation_paschal_collision_wine_only": ("Annunciation on Great Friday or Holy Saturday", "Εὐαγγελισμὸς τὴ Μεγάλη Παρασκευὴ ἢ τὸ Μέγα Σάββατο", "When the Annunciation falls on Great Friday or Holy Saturday, wine is permitted but fish and oil are not.", "Ὅταν ὁ Εὐαγγελισμὸς πέφτει τὴ Μεγάλη Παρασκευὴ ἢ τὸ Μέγα Σάββατο, ἐπιτρέπεται οἶνος ἀλλὰ ὄχι ψάρι καὶ ἔλαιο."),
    "great_lent_weekend_wine_oil": ("Great Lent", "Μεγάλη Τεσσαρακοστή", "Oil and wine are permitted on Saturdays and Sundays of Great Lent, except Holy Saturday.", "Τὰ Σάββατα καὶ τὶς Κυριακὲς τῆς Μεγάλης Τεσσαρακοστῆς ἐπιτρέπονται ἔλαιο καὶ οἶνος, ἐκτὸς ἀπὸ τὸ Μέγα Σάββατο."),
    "great_lent_strict": ("Great Lent or Holy Week", "Μεγάλη Τεσσαρακοστὴ ἢ Μεγάλη Ἑβδομάδα", "The day falls within Great Lent or Holy Week.", "Ἡ ἡμέρα βρίσκεται μέσα στὴ Μεγάλη Τεσσαρακοστὴ ἢ τὴ Μεγάλη Ἑβδομάδα."),
    "single_day_strict_fast": ("One-day fast", "Μονοήμερη νηστεία", "This is a strict one-day fast.", "Πρόκειται γιὰ αὐστηρὴ μονοήμερη νηστεία."),
    "apostles_fast_fish": ("Apostles’ Fast", "Νηστεία τῶν Ἁγίων Ἀποστόλων", "Fish, oil, and wine are permitted on weekends and on the Nativity of Saint John the Baptist.", "Τὰ Σαββατοκύριακα καὶ στὸ Γενέσιο τοῦ Τιμίου Προδρόμου ἐπιτρέπονται ψάρι, ἔλαιο καὶ οἶνος."),
    "apostles_fast_tue_thu": ("Apostles’ Fast", "Νηστεία τῶν Ἁγίων Ἀποστόλων", "Oil and wine are permitted on Tuesday and Thursday according to the general rule.", "Τὴν Τρίτη καὶ τὴν Πέμπτη ἐπιτρέπονται ἔλαιο καὶ οἶνος κατὰ τὸν γενικὸ κανόνα."),
    "apostles_fast_mon_wed_fri": ("Apostles’ Fast", "Νηστεία τῶν Ἁγίων Ἀποστόλων", "The general rule is a strict fast on Monday, Wednesday, and Friday.", "Ὁ γενικὸς κανόνας προβλέπει αὐστηρὰ νηστεία Δευτέρα, Τετάρτη καὶ Παρασκευή."),
    "dormition_transfiguration_fish": ("Dormition Fast", "Νηστεία τῆς Κοιμήσεως", "The Transfiguration permits fish, oil, and wine during the Dormition Fast.", "Ἡ Μεταμόρφωση ἐπιτρέπει ψάρι, ἔλαιο καὶ οἶνο μέσα στὴ Νηστεία τῆς Κοιμήσεως."),
    "dormition_feast_fish": ("Dormition Feast after the fourteen-day fast", "Ἑορτὴ τῆς Κοιμήσεως μετὰ δεκατετραήμερη νηστεία", "The Dormition Fast is August 1–14. The feast on August 15 is outside those fourteen fasting days; when it falls on Wednesday or Friday, only fish is permitted, while meat, dairy, and eggs remain excluded.", "Ἡ Νηστεία τῆς Κοιμήσεως διαρκεί 1–14 Αὐγούστου. Ἡ ἑορτὴ τῆς Κοιμήσεως στὶς 15 Αὐγούστου βρίσκεται ἔξω ἀπὸ αὐτὲς τὶς δεκατέσσερις ἡμέρες· ἂν συμπέσει Τετάρτη ἢ Παρασκευή, ἐπιτρέπεται μόνον ψάρι, ἐνῶ κρέας, γαλακτοκομικὰ καὶ αὐγὰ παραμένουν ἀπαγορευμένα."),
    "dormition_feast_fast_free": ("Dormition Feast after the fourteen-day fast", "Ἑορτὴ τῆς Κοιμήσεως μετὰ δεκατετραήμερη νηστεία", "The Dormition Fast is August 1–14. The feast on August 15 is outside the fourteen-day fast and this day has no general fast because it does not fall on Wednesday or Friday.", "Ἡ Νηστεία τῆς Κοιμήσεως διαρκεί 1–14 Αὐγούστου. Ἡ ἑορτὴ στὶς 15 Αὐγούστου βρίσκεται ἔξω ἀπὸ τὶς δεκατέσσερις ἡμέρες καὶ αὐτὴ ἡ ἡμέρα δὲν ἔχει γενικὴ νηστεία, ἐπειδὴ δὲν συμπίπτει μὲ Τετάρτη ἢ Παρασκευή."),
    "dormition_weekend_wine_oil": ("Dormition Fast", "Νηστεία τῆς Κοιμήσεως", "Oil and wine are permitted on Saturdays and Sundays.", "Τὰ Σάββατα καὶ τὶς Κυριακὲς ἐπιτρέπονται ἔλαιο καὶ οἶνος."),
    "dormition_strict": ("Dormition Fast", "Νηστεία τῆς Κοιμήσεως", "The day falls within the Dormition Fast.", "Ἡ ἡμέρα βρίσκεται μέσα στὴ Νηστεία τῆς Κοιμήσεως."),
    "post_dormition_week_fish": ("Post-Dormition week", "Ἑβδομάδα μετὰ τὴν Κοίμηση", "In the first week after the Dormition feast, fish, oil, and wine are permitted on Wednesday and Friday according to the Jerusalem/Jordan local calendar rule.", "Τὴν πρώτη ἑβδομάδα μετὰ τὴν ἑορτὴ τῆς Κοιμήσεως, τὴν Τετάρτη καὶ τὴν Παρασκευὴ ἐπιτρέπονται ψάρι, ἔλαιο καὶ οἶνος κατὰ τὸ τοπικὸ ἡμερολόγιο Ἱεροσολύμων/Ἰορδανίας."),
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


UNREVIEWED_DAILY_FEAST_AR = "تذكار اليوم بحسب التقويم الكنسي القديم"


def is_generic_daily_commemoration(value: object) -> bool:
    return str(value or "").strip().startswith("تذكار قديسي يوم ")


UNAVAILABLE_DAILY_FEAST = {
    "ar": "تعذّر التحقق من تذكار هذا اليوم من المصدر الرسمي المحلي؛ تظهر آخر معلومة موثقة إن توفرت",
    "en": "This day’s commemoration could not be verified from the official local source; the last verified record is shown when available",
    "el": "Ἡ μνήμη τῆς ἡμέρας δὲν κατέστη δυνατόν νὰ ἐπαληθευθεῖ ἀπὸ τὴν ἐπίσημη τοπικὴ πηγή· ὅπου ὑπάρχει προβάλλεται ἡ τελευταία ἐπαληθευμένη καταχώριση",
}


def localized_feast(ar_text: str) -> dict:
    if ar_text == UNREVIEWED_DAILY_FEAST_AR or ar_text == UNAVAILABLE_DAILY_FEAST["ar"]:
        return copy.deepcopy(UNAVAILABLE_DAILY_FEAST)
    en, el = FEAST_TRANSLATIONS.get(
        ar_text,
        (
            "Commemoration listed by the old church calendar",
            "Μνήμη κατὰ τὸ παλαιὸ ἐκκλησιαστικὸ ἡμερολόγιο",
        ),
    )
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


def _localized_food_names(profile: dict, allowed_value: bool, language: str) -> list[str]:
    index = 0 if language == "en" else 1
    result: list[str] = []
    for item in profile.get("items") or []:
        if bool(item.get("allowed")) is not allowed_value:
            continue
        key = str(item.get("key") or "")
        result.append(FASTING_FOOD_LOCALIZATION.get(key, (key, key))[index])
    return result


def _join_foods(values: list[str], language: str) -> str:
    if not values:
        return "None" if language == "en" else "Κανένα"
    if language == "en":
        if len(values) == 1:
            return values[0]
        return ", ".join(values[:-1]) + ", and " + values[-1]
    return ", ".join(values)


def _complete_fasting_guidance(profile: dict) -> None:
    """Attach novice-friendly food and duration guidance without inventing hours.

    A documented daily override may replace ``abstinence`` with exact times or
    an explicit end condition. Automatic Typikon profiles never guess a clock
    interval and therefore use NOT_INDICATED.
    """
    if not isinstance(profile, dict):
        return
    is_fast = bool(profile.get("is_fast"))
    allowed_ar = [str(item.get("label", {}).get("ar") or "") for item in profile.get("items") or [] if item.get("allowed")]
    forbidden_ar = [str(item.get("label", {}).get("ar") or "") for item in profile.get("items") or [] if not item.get("allowed")]
    allowed_en = _localized_food_names(profile, True, "en")
    forbidden_en = _localized_food_names(profile, False, "en")
    allowed_el = _localized_food_names(profile, True, "el")
    forbidden_el = _localized_food_names(profile, False, "el")

    if is_fast:
        allowed_summary = loc(
            "المسموح: " + ("، ".join(allowed_ar) if allowed_ar else "أطعمة نباتية لا تحتوي الأصناف الممنوعة"),
            "Permitted: " + (_join_foods(allowed_en, "en") if allowed_en else "plant foods that do not contain the restricted categories"),
            "Ἐπιτρέπονται: " + (_join_foods(allowed_el, "el") if allowed_el else "φυτικὲς τροφὲς χωρὶς τὶς ἀπαγορευμένες κατηγορίες"),
        )
        forbidden_summary = loc(
            "غير المسموح: " + ("، ".join(forbidden_ar) if forbidden_ar else "لا توجد أصناف ممنوعة"),
            "Not permitted: " + (_join_foods(forbidden_en, "en") if forbidden_en else "none of the listed categories"),
            "Δὲν ἐπιτρέπονται: " + (_join_foods(forbidden_el, "el") if forbidden_el else "καμία ἀπὸ τὶς καταγεγραμμένες κατηγορίες"),
        )
        duration = loc(
            "هذا حكم الصوم الغذائي لليوم الكنسي المعروض. الصيام الانقطاعي، إن أقرته الكنيسة أو حدده الأب الروحي، يعني الامتناع عن الطعام والشراب حتى الوقت المحدد ثم تناول الأصناف المسموحة. لم يثبت المصدر لهذا اليوم ساعات بداية ونهاية منفصلة، لذلك لا يخمّن التطبيق وقتًا.",
            "This is the food-fasting rule for the displayed church day. If the Church or a spiritual father appoints total abstinence, it means refraining from food and drink until the appointed time and then eating the foods permitted for that day. The source does not provide separate start and end hours for this day, so the app does not guess a time.",
            "Αὐτὸς εἶναι ὁ διατροφικὸς κανόνας τῆς προβαλλόμενης ἐκκλησιαστικῆς ἡμέρας. Ἐὰν ἡ Ἐκκλησία ἢ ὁ πνευματικὸς ὁρίσει πλήρη ἀποχή, αὐτὴ σημαίνει ἀποχή ἀπὸ τροφὴ καὶ ποτὸ μέχρι τὴν καθορισμένη ὥρα καὶ ἔπειτα λήψη τῶν τροφῶν ποὺ ἐπιτρέπονται αὐτὴν τὴν ἡμέρα. Ἡ πηγὴ δὲν δίνει χωριστὲς ὧρες ἔναρξης καὶ λήξης γι’ αὐτὴν τὴν ἡμέρα, γι’ αὐτὸ ἡ ἐφαρμογὴ δὲν μαντεύει ὥρα.",
        )
    else:
        allowed_summary = loc(
            "المسموح: جميع الأصناف المذكورة بحسب القاعدة العامة",
            "Permitted: all listed food categories under the general rule",
            "Ἐπιτρέπονται: ὅλες οἱ καταγεγραμμένες κατηγορίες τροφίμων κατὰ τὸν γενικὸ κανόνα",
        )
        forbidden_summary = loc(
            "غير المسموح: لا توجد أصناف ممنوعة بسبب صوم عام في هذا اليوم",
            "Not permitted: no category is restricted by a general fast today",
            "Δὲν ἐπιτρέπονται: καμία κατηγορία δὲν περιορίζεται ἀπὸ γενικὴ νηστεία σήμερα",
        )
        duration = loc(
            "لا توجد مدة صوم عامة لهذا اليوم.",
            "No general fasting duration applies today.",
            "Δὲν ἰσχύει γενικὴ διάρκεια νηστείας σήμερα.",
        )

    guidance = profile.setdefault("guidance", {})
    guidance["allowed_summary"] = allowed_summary
    guidance["forbidden_summary"] = forbidden_summary
    guidance["duration"] = duration
    guidance["beginner_explanation"] = loc(
        "المقصود بنوع الصوم هو قاعدة الطعام العامة لليوم، وليس حكمًا على إيمان الشخص أو صحته.",
        "The fasting type describes the day’s general food rule; it is not a judgment on a person’s faith or health.",
        "Ὁ τύπος νηστείας περιγράφει τὸν γενικὸ διατροφικὸ κανόνα τῆς ἡμέρας· δὲν εἶναι κρίση γιὰ τὴν πίστη ἢ τὴν ὑγεία τοῦ προσώπου.",
    )
    guidance["spiritual_note"] = loc(
        "الصوم مرتبط أيضًا بالصلاة والتوبة والرحمة وضبط النفس، وليس بالطعام وحده.",
        "Fasting is also joined to prayer, repentance, mercy, and self-control; it is not only about food.",
        "Ἡ νηστεία συνδέεται μὲ προσευχή, μετάνοια, ἐλεημοσύνη καὶ ἐγκράτεια· δὲν ἀφορᾷ μόνο τὴν τροφή.",
    )
    guidance["health_note"] = loc(
        "تنبيه صحي: لا توقف دواءً ولا تغيّر علاجًا بسبب التطبيق. الأطفال والحوامل والمرضى وكبار السن وأصحاب الأعمال المجهدة قد يحتاجون ترتيبًا مناسبًا لحالتهم الصحية.",
        "Health note: do not stop medicine or change treatment because of the app. Children, pregnant people, the ill, older adults, and those doing strenuous work may need an arrangement appropriate to their health.",
        "Σημείωση ὑγείας: μὴ διακόπτετε φάρμακα καὶ μὴν ἀλλάζετε θεραπεία ἐξαιτίας τῆς ἐφαρμογῆς. Παιδιά, ἔγκυες, ἀσθενεῖς, ἡλικιωμένοι καὶ ὅσοι ἐργάζονται βαριὰ μπορεῖ νὰ χρειάζονται προσαρμογὴ στὴν ὑγεία τους.",
    )

    abstinence = profile.get("abstinence")
    if not isinstance(abstinence, dict):
        abstinence = {}
        profile["abstinence"] = abstinence
    if "applies" not in abstinence:
        abstinence["applies"] = False
    abstinence.setdefault("kind", "not_indicated")
    abstinence.setdefault("start_time", None)
    abstinence.setdefault("end_time", None)
    abstinence.setdefault("end_condition", loc(
        "لم يثبت المصدر صومًا انقطاعيًا مستقلًا لهذا اليوم.",
        "The source does not document a separate total-abstinence interval for this day.",
        "Ἡ πηγὴ δὲν τεκμηριώνει χωριστὸ διάστημα πλήρους ἀποχῆς γιὰ αὐτὴν τὴν ἡμέρα.",
    ))
    abstinence.setdefault("detail", loc(
        "إذا وُجد صوم انقطاعي موثق، يعرض التطبيق وقت البداية والنهاية أو شرط الانتهاء كما ورد في المصدر. عند غياب ذلك لا يضع ساعات من عنده.",
        "When a documented total-abstinence fast exists, the app shows its start, end, or ending condition exactly as sourced. Otherwise it does not invent hours.",
        "Ὅταν ὑπάρχει τεκμηριωμένη πλήρης ἀποχή, ἡ ἐφαρμογὴ προβάλλει ἀκριβῶς τὴν ἔναρξη, λήξη ἢ συνθήκη λήξης. Διαφορετικὰ δὲν ἐπινοεῖ ὧρες.",
    ))
    verification = abstinence.setdefault("verification", {})
    verification.setdefault("status", "NOT_INDICATED")
    verification.setdefault("source", "canonical/fasting_policy.json")


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
    _complete_fasting_guidance(profile)


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
    data["fasting_guidance_version"] = 1
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
        completed_feast = localized_feast(str(feast["ar"]))
        for language in ("en", "el"):
            if str(feast.get(language) or "").strip():
                completed_feast[language] = str(feast[language]).strip()
        data["feast"] = completed_feast
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
            completed_feast = localized_feast(str(ns_feast["ar"]))
            for language in ("en", "el"):
                if str(ns_feast.get(language) or "").strip():
                    completed_feast[language] = str(ns_feast[language]).strip()
            next_payload["feast"] = completed_feast
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
            completed_feast = localized_feast(str(item_feast["ar"]))
            for language in ("en", "el"):
                if str(item_feast.get(language) or "").strip():
                    completed_feast[language] = str(item_feast[language]).strip()
            item["feast"] = completed_feast
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


LITURGY_SERVICE_LABELS = {
    "chrysostom": loc("قداس القديس يوحنا الذهبي الفم", "Divine Liturgy of Saint John Chrysostom", "Θεία Λειτουργία τοῦ Ἁγίου Ἰωάννου τοῦ Χρυσοστόμου"),
    "basil": loc("قداس القديس باسيليوس الكبير", "Divine Liturgy of Saint Basil the Great", "Θεία Λειτουργία τοῦ Ἁγίου Βασιλείου τοῦ Μεγάλου"),
    "presanctified": loc("قداس السابق تقديسه", "Liturgy of the Presanctified Gifts", "Λειτουργία τῶν Προηγιασμένων Τιμίων Δώρων"),
    "james": loc("قداس القديس يعقوب أخي الرب", "Divine Liturgy of Saint James, the Brother of the Lord", "Θεία Λειτουργία τοῦ Ἁγίου Ἰακώβου τοῦ Ἀδελφοθέου"),
    "no_divine_liturgy": loc("لا يقام قداس إلهي", "No Divine Liturgy appointed", "Δεν τελεῖται Θεία Λειτουργία"),
    "typikon_override_required": loc("يلزم قرار طقسي مؤرخ", "Dated Typikon ruling required", "Ἀπαιτεῖται χρονολογημένη τυπικὴ διάταξη"),
}

LITURGY_SERVICE_FORM_LABELS = {
    "morning_divine_liturgy": loc("قداس إلهي صباحي", "Morning Divine Liturgy", "Πρωινὴ Θεία Λειτουργία"),
    "vespers_with_divine_liturgy": loc("الغروب مع القداس الإلهي", "Vespers with Divine Liturgy", "Ἑσπερινὸς μετὰ Θείας Λειτουργίας"),
    "lenten_vespers_with_presanctified": loc("غروب صيامي مع السابق تقديسه", "Lenten Vespers with the Presanctified Gifts", "Κατανυκτικὸς Ἑσπερινὸς μετὰ Προηγιασμένων"),
    "no_divine_liturgy": loc("لا توجد خدمة قداس إلهي", "No Divine Liturgy service", "Χωρὶς Θεία Λειτουργία"),
    "official_override_required": loc("يُحدّد بقرار كنسي مؤرخ", "Determined by a dated church ruling", "Καθορίζεται μὲ χρονολογημένη ἐκκλησιαστικὴ διάταξη"),
}

LITURGY_RULE_REASONS = {
    "dated_official_jordan_override": loc("تحديد رسمي مؤرخ من الجهة الكنسية المعتمدة", "Dated official ruling from the approved church authority", "Χρονολογημένη ἐπίσημη διάταξη τῆς ἐγκεκριμένης ἐκκλησιαστικῆς ἀρχῆς"),
    "annunciation_paschal_triduum_collision": loc("تزامن البشارة مع أيام ذات ترتيب فصحي خاص", "The Annunciation coincides with days governed by special Paschal rubrics", "Ὁ Εὐαγγελισμὸς συμπίπτει μὲ ἡμέρες ἰδιαίτερων πασχάλιων διατάξεων"),
    "great_friday_no_divine_liturgy": loc("الجمعة العظيمة لا يُقام فيها قداس إفخارستي كامل", "No full Eucharistic Divine Liturgy is appointed on Great Friday", "Τὴ Μεγάλη Παρασκευὴ δὲν τελεῖται πλήρης εὐχαριστιακὴ Θεία Λειτουργία"),
    "saint_basil_day": loc("عيد القديس باسيليوس الكبير", "Feast of Saint Basil the Great", "Ἑορτὴ τοῦ Ἁγίου Βασιλείου τοῦ Μεγάλου"),
    "great_lent_sunday": loc("أحد من الآحاد الخمسة الأولى للصوم الكبير", "One of the first five Sundays of Great Lent", "Μία ἀπὸ τὶς πέντε πρώτες Κυριακὲς τῆς Μεγάλης Τεσσαρακοστῆς"),
    "annunciation_chrysostom_exception": loc("عيد البشارة في يوم صومي بحسب قاعدة الاختيار المثبتة", "The Annunciation on a Lenten weekday under the documented selection rule", "Ὁ Εὐαγγελισμὸς σὲ καθημερινὴ τῆς Νηστείας κατὰ τὴν τεκμηριωμένη διάταξη"),
    "great_holy_thursday": loc("الخميس العظيم المقدس", "Great and Holy Thursday", "Μεγάλη καὶ Ἁγία Πέμπτη"),
    "great_holy_saturday": loc("السبت العظيم المقدس", "Great and Holy Saturday", "Μέγα καὶ Ἅγιο Σάββατο"),
    "nativity_theophany_basil_on_sunday_or_monday_feast": loc("قاعدة الميلاد أو الظهور الإلهي عندما يقع العيد يوم الأحد أو الاثنين", "Nativity or Theophany rule when the feast falls on Sunday or Monday", "Διάταξη Χριστουγέννων ἢ Θεοφανείων ὅταν ἡ ἑορτὴ πέφτει Κυριακὴ ἢ Δευτέρα"),
    "nativity_theophany_vesperal_basil_on_eve": loc("برامون الميلاد أو الظهور الإلهي مع قداس باسيليوس الغروبي", "Eve of Nativity or Theophany with the vesperal Liturgy of Saint Basil", "Παραμονὴ Χριστουγέννων ἢ Θεοφανείων μὲ ἑσπερινὴ Λειτουργία τοῦ Ἁγίου Βασιλείου"),
    "nativity_theophany_eve_when_basil_is_on_feast": loc("برامون العيد عندما يُقام قداس باسيليوس في يوم العيد", "The feast eve when Saint Basil’s Liturgy is appointed on the feast itself", "Ἡ παραμονὴ ὅταν ἡ Λειτουργία τοῦ Ἁγίου Βασιλείου τελεῖται τὴν ἡμέρα τῆς ἑορτῆς"),
    "first_three_days_of_holy_week": loc("الاثنين أو الثلاثاء أو الأربعاء العظيم", "Great Monday, Tuesday, or Wednesday", "Μεγάλη Δευτέρα, Τρίτη ἢ Τετάρτη"),
    "great_lent_wednesday_or_friday": loc("أربعاء أو جمعة من الصوم الكبير", "A Wednesday or Friday of Great Lent", "Τετάρτη ἢ Παρασκευὴ τῆς Μεγάλης Τεσσαρακοστῆς"),
    "ordinary_chrysostom_baseline": loc("لا توجد قاعدة موثقة تعيّن طقسًا آخر لهذا اليوم", "No documented rule appoints another rite for this day", "Καμία τεκμηριωμένη διάταξη δὲν ὁρίζει ἄλλον τύπο Λειτουργίας γιὰ αὐτὴ τὴν ἡμέρα"),
}


def _service_form_for(service_type: str, rule_id: str) -> str:
    if service_type == "presanctified":
        return "lenten_vespers_with_presanctified"
    if service_type == "no_divine_liturgy":
        return "no_divine_liturgy"
    if service_type == "typikon_override_required":
        return "official_override_required"
    if rule_id in {
        "great_holy_thursday",
        "great_holy_saturday",
        "nativity_theophany_vesperal_basil_on_eve",
    }:
        return "vespers_with_divine_liturgy"
    return "morning_divine_liturgy"


def _selection_payload(
    service_type: str,
    rule_id: str,
    authority: str,
    source_url: str,
    pascha_offset: int,
    edition: dict,
) -> dict:
    service_form = _service_form_for(service_type, rule_id)
    if service_type == "no_divine_liturgy":
        selection_status = "NO_DIVINE_LITURGY_APPOINTED"
    elif service_type == "typikon_override_required":
        selection_status = "DATED_OFFICIAL_OVERRIDE_REQUIRED"
    else:
        selection_status = "PRESCRIBED"
    return {
        "service_type": service_type,
        "service_form": service_form,
        "service_form_label": copy.deepcopy(LITURGY_SERVICE_FORM_LABELS[service_form]),
        "rule_id": rule_id,
        "reason": copy.deepcopy(LITURGY_RULE_REASONS.get(rule_id) or loc(rule_id, rule_id, rule_id)),
        "selection_status": selection_status,
        "authority": authority,
        "source_url": source_url,
        "pascha_offset": pascha_offset,
        "label": copy.deepcopy(LITURGY_SERVICE_LABELS[service_type]),
        "service_id": edition.get("service_id"),
        "native_editions": {lang: edition.get(lang) for lang in ("ar", "en", "el")},
        "availability_note": copy.deepcopy(edition.get("availability_note") or loc("", "", "")),
        "source_ids": copy.deepcopy(edition.get("source_ids") or []),
        "import_contract": edition.get("import_contract") or "",
        "displayable": bool(edition.get("displayable")),
        "full_service_required": True,
        "full_service_scope": "APPOINTED_LITURGY_FROM_OPENING_BLESSING_TO_DISMISSAL",
        "strict_core_only": True,
        "adjacent_offices_separate": True,
        "no_unappointed_material": True,
        "wrong_liturgy_fallback_allowed": False,
    }


def _old_calendar_key(day: date) -> tuple[int, int]:
    _jy, jm, jd = gregorian_to_julian_date(day)
    return jm, jd


def liturgy_service_selection(day: date, info: dict | None = None) -> dict:
    """Select the appointed Liturgy without silently substituting another rite.

    This is a conservative Typikon baseline. A dated Jordan/Jerusalem override
    may supersede it only when the override carries documented source evidence.
    """
    pascha = orthodox_pascha_gregorian(day.year)
    offset = (day - pascha).days
    jm, jd = _old_calendar_key(day)

    override = (info or {}).get("liturgy_service_override")
    if not isinstance(override, dict):
        override_path = ROOT / "scripts" / "overrides" / f"{day:%Y-%m-%d}.json"
        if override_path.is_file():
            override_payload = json.loads(override_path.read_text(encoding="utf-8"))
            candidate = override_payload.get("liturgy_service_override")
            if isinstance(candidate, dict):
                override = candidate
    if isinstance(override, dict):
        value = str(override.get("service_type") or "").strip()
        evidence = override.get("evidence") or {}
        if value not in {"chrysostom", "basil", "presanctified", "james", "no_divine_liturgy"}:
            raise RuntimeError(f"Invalid liturgy_service_override value: {value!r}")
        if str(evidence.get("status") or "") != "DOCUMENTED_OVERRIDE":
            raise RuntimeError("liturgy_service_override requires DOCUMENTED_OVERRIDE evidence")
        if not str(evidence.get("source_id") or "").strip() or not str(evidence.get("source_url") or "").strip():
            raise RuntimeError("liturgy_service_override requires source_id and source_url")
        editions = json.loads((ROOT / "canonical" / "liturgy_service_editions.json").read_text(encoding="utf-8"))
        edition = copy.deepcopy((editions.get("editions") or {}).get(value) or {})
        return _selection_payload(
            value,
            "dated_official_jordan_override",
            str(evidence.get("source_id")),
            str(evidence.get("source_url")),
            offset,
            edition,
        )

    # A collision of the Annunciation with the Paschal Triduum or Pascha has
    # detailed year-specific rubrics.  The conservative Jordan/Jerusalem lane
    # requires a dated official ruling rather than applying a generic shortcut.
    if (jm, jd) == (3, 25) and offset in {-3, -2, -1, 0}:
        selected, rule = "typikon_override_required", "annunciation_paschal_triduum_collision"
    # Great Friday has no Eucharistic Divine Liturgy when no higher documented
    # feast collision applies.
    elif offset == -2:
        selected, rule = "no_divine_liturgy", "great_friday_no_divine_liturgy"
    elif (jm, jd) == (1, 1):
        selected, rule = "basil", "saint_basil_day"
    # The five Sundays of Great Lent retain Basil even if a fixed feast is
    # combined with the Sunday office.
    elif offset in {-42, -35, -28, -21, -14}:
        selected, rule = "basil", "great_lent_sunday"
    # On a weekday of Great Lent (including Great Monday-Wednesday), the
    # Annunciation receives the Eucharistic Liturgy of Chrysostom instead of
    # the Presanctified service.
    elif (jm, jd) == (3, 25):
        selected, rule = "chrysostom", "annunciation_chrysostom_exception"
    elif offset == -3:
        selected, rule = "basil", "great_holy_thursday"
    elif offset == -1:
        selected, rule = "basil", "great_holy_saturday"
    else:
        # Nativity and Theophany: normally Basil is joined to Vespers on the
        # eve. When the feast is Sunday or Monday, Basil is appointed on the
        # feast itself. This remains overrideable by the local signed calendar.
        feast_keys = {(12, 25), (1, 6)}
        eve_keys = {(12, 24), (1, 5)}
        if (jm, jd) in feast_keys and day.weekday() in {0, 6}:
            selected, rule = "basil", "nativity_theophany_basil_on_sunday_or_monday_feast"
        elif (jm, jd) in eve_keys:
            feast_day = day + timedelta(days=1)
            if feast_day.weekday() not in {0, 6}:
                selected, rule = "basil", "nativity_theophany_vesperal_basil_on_eve"
            else:
                selected, rule = "chrysostom", "nativity_theophany_eve_when_basil_is_on_feast"
        elif offset in {-6, -5, -4}:
            selected, rule = "presanctified", "first_three_days_of_holy_week"
        elif -47 <= offset <= -9 and day.weekday() in {2, 4}:
            selected, rule = "presanctified", "great_lent_wednesday_or_friday"
        else:
            selected, rule = "chrysostom", "ordinary_chrysostom_baseline"

    editions = json.loads((ROOT / "canonical" / "liturgy_service_editions.json").read_text(encoding="utf-8"))
    edition = copy.deepcopy((editions.get("editions") or {}).get(selected) or {})
    return _selection_payload(
        selected,
        rule,
        "canonical/liturgy_service_rules.json",
        "",
        offset,
        edition,
    )


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
    "meat": {"icon": "🥩", "ar": "اللحوم والدواجن"},
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
    "wine_only": {"allowed": {"wine"}, "level_ar": "النبيذ مسموح وحده"},
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
    if level == "fast_free" and source_rule == "dormition_feast_fast_free":
        title_ar = f"{season_ar} — {level_ar}"
    else:
        title_ar = level_ar if level == "fast_free" else f"{season_ar} — {level_ar}"
    if allowed_names:
        detail = f"{reason_ar} المسموح بحسب القاعدة العامة: { '، '.join(allowed_names) }."
    else:
        detail = f"{reason_ar} صوم صارم بحسب القاعدة العامة: دون لحوم أو ألبان أو بيض أو سمك أو زيت أو نبيذ."
    if forbidden_names and allowed_names:
        detail += f" يُمتنع عن: { '، '.join(forbidden_names) }."
    profile = {
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
    complete_fasting_localizations(profile)
    return profile


def _document_optional_first_week_lent_abstinence(profile: dict) -> dict:
    """Attach the sourced optional total-abstinence practice for early Lent."""
    profile["abstinence"] = {
        "applies": True,
        "optional": True,
        "kind": "until_service_end",
        "start_time": None,
        "end_time": None,
        "end_condition": loc(
            "صيام انقطاعي اختياري لمن يستطيع في الأيام الشديدة من الأسبوع الأول للصوم الكبير؛ يكون كسر الانقطاع بعد صلاة الغروب أو خدمة السابق تقديسه بحسب ترتيب اليوم. من لا يستطيع ذلك لا يُلزم به.",
            "Optional total abstinence for those who have the strength during the severe days of the first week of Great Lent; the fast is broken after Vespers or the Presanctified Liturgy according to the day's order. Those unable to do this are not bound to it.",
            "Προαιρετικὴ πλήρης ἀποχὴ γιὰ ὅσους ἔχουν δύναμη κατὰ τὶς αὐστηρὲς ἡμέρες τῆς πρώτης ἑβδομάδας τῆς Μεγάλης Τεσσαρακοστῆς· ἡ ἀποχὴ λύεται μετὰ τὸν Ἑσπερινὸ ἢ τὴ Λειτουργία τῶν Προηγιασμένων, κατὰ τὴν τάξη τῆς ἡμέρας. Ὅσοι δὲν μποροῦν δὲν δεσμεύονται.",
        ),
        "detail": loc(
            "تذكر القاعدة الكنسية ممارسة انقطاعية اختيارية في الأيام الأشد من الأسبوع الأول للصوم الكبير لمن يستطيع، مع مراعاة القدرة والإرشاد الروحي، ولا تحدد ساعة عامة للتطبيق.",
            "The church rule documents optional total abstinence on the severe days of Great Lent's first week for those who have the strength, with pastoral guidance; it does not establish a universal clock time.",
            "Ὁ ἐκκλησιαστικὸς κανόνας τεκμηριώνει προαιρετικὴ πλήρη ἀποχὴ στὶς αὐστηρὲς ἡμέρες τῆς πρώτης ἑβδομάδας τῆς Μεγάλης Τεσσαρακοστῆς γιὰ ὅσους ἔχουν δύναμη, μὲ ποιμαντικὴ καθοδήγηση· δὲν καθορίζει γενικὴ ὥρα.",
        ),
        "verification": {
            "status": "DOCUMENTED_OPTIONAL",
            "source": "https://www.oca.org/liturgics/outlines/fasting-fast-free-seasons-of-the-church",
            "rule": "first_week_lent_optional_total_abstinence",
        },
    }
    return profile


def _document_optional_great_friday_abstinence(profile: dict) -> dict:
    """Attach the sourced optional total-abstinence practice for Great Friday.

    OCA describes total abstinence until sunset or after the Vespers veneration
    for those who have the strength, while explicitly allowing pastoral relief
    for those unable to keep it. No universal clock time is inferred here.
    """
    profile["abstinence"] = {
        "applies": True,
        "optional": True,
        "kind": "until_service_end",
        "start_time": None,
        "end_time": None,
        "end_condition": loc(
            "صيام انقطاعي اختياري لمن يستطيع: يمتنع عن الطعام والشراب حتى الغروب أو حتى إكرام الكفن في خدمة الغروب بحسب الترتيب الرعوي. من لا يستطيع ذلك لا يُلزم به، ويطلب إرشاد أبيه الروحي.",
            "Optional total abstinence for those who have the strength: abstain from food and drink until sunset or until the veneration at Vespers, according to the pastoral order. Those unable to do this are not bound to it and should seek their spiritual father's guidance.",
            "Προαιρετικὴ πλήρης ἀποχὴ γιὰ ὅσους ἔχουν δύναμη: ἀποχὴ ἀπὸ τροφὴ καὶ ποτὸ μέχρι τὴ δύση τοῦ ἡλίου ἢ μέχρι τὴν προσκύνηση στὸν Ἑσπερινό, κατὰ τὴν ποιμαντικὴ τάξη. Ὅσοι δὲν μποροῦν δὲν δεσμεύονται καὶ ζητοῦν καθοδήγηση ἀπὸ τὸν πνευματικό τους.",
        ),
        "detail": loc(
            "تذكر قاعدة الصوم الانقطاعي الاختياري في الجمعة العظيمة لمن يستطيع، ولا تضع هذه القاعدة كإلزام عام أو كساعة موحدة.",
            "The source documents optional total abstinence on Great Friday for those who have the strength; this is not a universal obligation or a guessed clock interval.",
            "Ἡ πηγὴ τεκμηριώνει προαιρετικὴ πλήρη ἀποχὴ τὴ Μεγάλη Παρασκευὴ γιὰ ὅσους ἔχουν δύναμη· δὲν πρόκειται γιὰ γενικὴ ὑποχρέωση οὔτε γιὰ ὑποθετικὴ ὥρα.",
        ),
        "verification": {
            "status": "DOCUMENTED_OPTIONAL",
            "source": "https://www.oca.org/liturgics/outlines/fasting-fast-free-seasons-of-the-church",
            "rule": "great_friday_optional_total_abstinence",
        },
    }
    return profile


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
    if old_key in {(1, 6), (6, 29), (12, 25)}:
        return _fasting_profile("fast_free", "عيد سيدي أو عيد كبير", "اليوم عيد كبير وتنتهي فيه فترة الصوم المرتبطة به.", "major_feast_fast_free")
    if old_key == (8, 15):
        if weekday in (2, 4):
            return _fasting_profile(
                "fish_allowed",
                "عيد رقاد والدة الإله بعد صوم أربعة عشر يومًا",
                "صوم رقاد والدة الإله مدته أربعة عشر يومًا من 1 إلى 14 آب بحسب التقويم القديم. يوم 15 آب هو عيد الرقاد، وهو خارج الأيام الأربعة عشر؛ وإذا وافق الأربعاء أو الجمعة يكون صومًا مخففًا وتُسمح فيه السمك والزيت والنبيذ، مع بقاء الامتناع عن اللحوم والألبان والبيض.",
                "dormition_feast_fish",
            )
        return _fasting_profile(
            "fast_free",
            "عيد رقاد والدة الإله بعد صوم أربعة عشر يومًا",
            "صوم رقاد والدة الإله مدته أربعة عشر يومًا من 1 إلى 14 آب بحسب التقويم القديم. يوم 15 آب هو عيد الرقاد، وهو خارج مدة الصوم وليس يومًا خامس عشر من الصوم، ولا صوم عام عليه لأنه لا يوافق الأربعاء أو الجمعة.",
            "dormition_feast_fast_free",
        )

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
        if old_key == (3, 25):
            if day in {pascha - timedelta(days=2), holy_saturday}:
                return _fasting_profile(
                    "wine_only",
                    "عيد البشارة والجمعة العظيمة أو السبت العظيم",
                    "إذا وقع عيد البشارة في الجمعة العظيمة أو السبت العظيم، يُسمح بالنبيذ وحده، ولا يُسمح بالسمك أو الزيت بحسب الحكم الموثق.",
                    "annunciation_paschal_collision_wine_only",
                )
            if pascha - timedelta(days=6) <= day <= pascha - timedelta(days=3):
                return _fasting_profile(
                    "wine_oil",
                    "عيد البشارة وأسبوع الآلام",
                    "إذا وقع عيد البشارة في الأيام الأربعة الأولى من أسبوع الآلام، يُسمح بالزيت والنبيذ دون السمك بحسب الحكم الموثق.",
                    "annunciation_paschal_collision_wine_oil",
                )
            return _fasting_profile("fish_allowed", "الصوم الكبير", "فسحة عيد البشارة داخل الصوم الكبير.", "great_lent_fish_exception")
        if day == palm_sunday:
            return _fasting_profile("fish_allowed", "الصوم الكبير", "فسحة أحد الشعانين داخل الصوم الكبير.", "great_lent_fish_exception")
        if day in {lent_start, lent_start + timedelta(days=1), lent_start + timedelta(days=3)}:
            return _document_optional_first_week_lent_abstinence(
                _fasting_profile(
                    "strict",
                    "الأسبوع الأول من الصوم الكبير",
                    "اليوم من الأيام الأشد في الأسبوع الأول للصوم الكبير، ويذكر المصدر صومًا انقطاعيًا اختياريًا لمن يستطيع دون ساعة عامة موحدة.",
                    "first_week_lent_optional_total_abstinence",
                )
            )
        if day == pascha - timedelta(days=2):
            return _document_optional_great_friday_abstinence(
                _fasting_profile(
                    "strict",
                    "الجمعة العظيمة وأسبوع الآلام",
                    "الجمعة العظيمة يوم صوم صارم، وتذكر المصادر صومًا انقطاعيًا اختياريًا لمن يستطيع حتى الغروب أو إكرام الكفن.",
                    "great_friday_optional_total_abstinence",
                )
            )
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

    # Jerusalem/Jordan local calendar: the first week after the Dormition feast
    # (old-calendar Aug 16-22) relaxes its Wednesday and Friday to fish, oil,
    # and wine. This must precede the ordinary weekly rule.
    if jm == 8 and jd in (20, 22):
        return _fasting_profile(
            "fish_allowed",
            "الأسبوع الأول بعد عيد رقاد السيدة والدة الإله",
            "بعد انتهاء صوم الرقاد، تسمح قاعدة التقويم المحلي في أسبوع العيد الأول يومي الأربعاء والجمعة بالسمك والزيت والنبيذ.",
            "post_dormition_week_fish",
        )
    # Ordinary Wednesday and Friday fast.
    if weekday in (2, 4):
        return _fasting_profile("strict", "صوم الأربعاء أو الجمعة", "صوم أسبوعي بحسب التقليد الأرثوذكسي، ما لم توجد فسحة موثقة أو تدبير محلي.", "weekly_wednesday_friday")

    return _fasting_profile("fast_free", "يوم عادي", "لا توجد فترة صوم عامة أو قاعدة أسبوعية لهذا اليوم.", "ordinary_fast_free")


LOCAL_COMMEMORATIONS_PATH = ROOT / "canonical" / "local_commemorations.json"
_INTERNAL_CALENDAR_YEAR_CACHE: dict[int, dict[str, dict]] = {}


def internal_calendar_entry(day: date) -> dict | None:
    """Load one compact offline calendar year lazily.

    The signed nine-day package remains authoritative. This entry only prevents
    year-boundary gaps and supplies calculated major occasions when live sources
    are unavailable. The calendar generator disables this lookup while rebuilding.
    """
    if os.getenv("ORTHODOX_DISABLE_INTERNAL_CALENDAR") == "1":
        return None
    year = day.year
    if year not in _INTERNAL_CALENDAR_YEAR_CACHE:
        path = ROOT / "app" / "src" / "main" / "assets" / "data" / "calendar" / f"calendar_{year}.json"
        if not path.is_file():
            _INTERNAL_CALENDAR_YEAR_CACHE[year] = {}
        else:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                _INTERNAL_CALENDAR_YEAR_CACHE[year] = {
                    str(item.get("date_iso") or item.get("date")): item
                    for item in payload.get("days", [])
                    if isinstance(item, dict) and (item.get("date_iso") or item.get("date"))
                }
            except (OSError, json.JSONDecodeError):
                _INTERNAL_CALENDAR_YEAR_CACHE[year] = {}
    entry = _INTERNAL_CALENDAR_YEAR_CACHE[year].get(day.isoformat())
    return copy.deepcopy(entry) if isinstance(entry, dict) else None


def local_official_commemoration(day: date) -> dict | None:
    """Return a short, source-attributed local commemoration only when verified.

    The collector never republishes long Synaxarion prose. It stores names, dates,
    authority, URLs, retrieval timestamp, and content hashes. A stale verified
    record may remain usable as the last known good record; unverified observations
    never replace reviewed annual/fixed entries.
    """
    if not LOCAL_COMMEMORATIONS_PATH.is_file():
        return None
    try:
        payload = json.loads(LOCAL_COMMEMORATIONS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    record = (payload.get("records") or {}).get(day.isoformat())
    if not isinstance(record, dict):
        return None
    if record.get("verification_status") not in {"LOCAL_OFFICIAL_SOURCE_VERIFIED", "LAST_VERIFIED_LOCAL_RECORD"}:
        return None
    names = record.get("commemorations") or {}
    if not isinstance(names, dict):
        return None
    if not any(str(names.get(lang) or "").strip() for lang in ("ar", "en", "el")):
        return None
    # A local record may verify only one native-language lane. Never allow a
    # missing lane to inherit text from Arabic or another language.
    return record


def day_info(day: date) -> dict:
    jy, jm, jd = gregorian_to_julian_date(day)
    pascha = orthodox_pascha_gregorian(day.year)
    apostles_start = pascha + timedelta(days=57)  # Monday after All Saints Sunday
    apostles_end = julian_to_gregorian_date(day.year, 6, 28)  # Eve of Peter and Paul on old calendar

    # Prefer the pinned annual registry, because it contains reviewed Sunday-cycle
    # names in all three native languages. Weekday records that still carry the
    # generic placeholder are published as an explicit unavailable notice rather
    # than as if that placeholder were an ecclesiastically reviewed commemoration.
    annual = h2_lectionary_entry(day)
    annual_feast = annual.get("feast") if isinstance(annual, dict) else None
    internal = internal_calendar_entry(day)
    internal_feast = internal.get("feast") if isinstance(internal, dict) else None
    fixed = fixed_old_feast(jm, jd)
    local_record = local_official_commemoration(day)
    if local_record:
        local_names = local_record.get("commemorations") or {}
        # Start from the normal reviewed/internal lane, then overlay only the
        # native-language strings actually supplied by the local record. This
        # intentionally prevents the historical Arabic-to-English/Greek copy.
        if isinstance(annual_feast, dict) and str(annual_feast.get("ar") or "").strip() and not is_generic_daily_commemoration(annual_feast.get("ar")):
            feast = {lang: str(annual_feast.get(lang) or "").strip() for lang in ("ar", "en", "el")}
        elif isinstance(internal_feast, dict) and str(internal_feast.get("ar") or "").strip():
            feast = {lang: str(internal_feast.get(lang) or "").strip() for lang in ("ar", "en", "el")}
        elif fixed:
            feast = localized_feast(fixed)
        else:
            feast = copy.deepcopy(UNAVAILABLE_DAILY_FEAST)
        for lang in ("ar", "en", "el"):
            value = str(local_names.get(lang) or "").strip()
            if value:
                feast[lang] = value
        feast_status = str(local_record.get("verification_status"))
    elif isinstance(annual_feast, dict) and str(annual_feast.get("ar") or "").strip() and not is_generic_daily_commemoration(annual_feast.get("ar")):
        feast = {lang: str(annual_feast.get(lang) or "").strip() for lang in ("ar", "en", "el")}
        if feast["ar"] == UNREVIEWED_DAILY_FEAST_AR:
            feast = copy.deepcopy(UNAVAILABLE_DAILY_FEAST)
            feast_status = "UNAVAILABLE_PENDING_ECCLESIASTICAL_REVIEW"
        else:
            feast_status = "PINNED_REVIEWED_ANNUAL_ENTRY"
    elif isinstance(internal_feast, dict) and str(internal_feast.get("ar") or "").strip():
        feast = {lang: str(internal_feast.get(lang) or "").strip() for lang in ("ar", "en", "el")}
        feast_status = str(internal.get("occasion_status") or "INTERNAL_CALENDAR_BASELINE")
    elif fixed:
        feast = localized_feast(fixed)
        feast_status = "PINNED_FIXED_FEAST"
    else:
        feast = copy.deepcopy(UNAVAILABLE_DAILY_FEAST)
        feast_status = "UNAVAILABLE_PENDING_ECCLESIASTICAL_REVIEW"

    fasting = fasting_profile(day, jm, jd, pascha, apostles_start, apostles_end)

    return {
        "julian_year": jy,
        "julian_month": jm,
        "julian_day": jd,
        "julian_label_ar": ar_julian_label(day),
        "pascha": pascha,
        "apostles_start": apostles_start,
        "apostles_end": apostles_end,
        "feast_ar": feast["ar"],
        "feast_en": feast["en"],
        "feast_el": feast["el"],
        "feast_status": feast_status,
        "fast_ar": fasting["title"]["ar"],
        "fast_en": fasting["title"].get("en", ""),
        "fast_el": fasting["title"].get("el", ""),
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
RESURRECTIONAL_PROPERS_REGISTRY = json.loads((ROOT / "canonical" / "resurrectional_propers.json").read_text(encoding="utf-8"))
DATED_LITURGICAL_PROPERS_REGISTRY = json.loads((ROOT / "canonical" / "dated_liturgical_propers.json").read_text(encoding="utf-8"))
JORDAN_2026_H2_LECTIONARY_REGISTRY = json.loads((ROOT / "canonical" / "jordan_2026_h2_lectionary.json").read_text(encoding="utf-8"))
JORDAN_2026_H2_BY_DATE = {item.get("date_iso"): item for item in JORDAN_2026_H2_LECTIONARY_REGISTRY.get("days", []) if isinstance(item, dict) and item.get("date_iso")}
PASCHAL_CYCLE_PROPERS_REGISTRY = json.loads((ROOT / "canonical" / "paschal_cycle_propers.json").read_text(encoding="utf-8"))
LITURGY_VARIABLE_PARTS_REGISTRY = json.loads((ROOT / "canonical" / "liturgy_variable_parts.json").read_text(encoding="utf-8"))


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


NATIVE_SOURCE_ID_ALIASES = {
    # Older canonical proper registries used these historical IDs. Normalize
    # them at runtime to the IDs registered by source_native_contract.json so
    # exact same-language text is not erased by the fail-closed lane enforcer.
    "antioch_tripoli_karma_archive_ar": "antioch_archdiocese_tripoli_ar",
    "orthodox_church_in_america_all_saints": "oca_official_english",
    "ebible_world_english_bible_classic": "ebible_world_english_bible",
}


def _canonical_native_source_id(source_id: object) -> str:
    value = str(source_id or "").strip()
    return NATIVE_SOURCE_ID_ALIASES.get(value, value)


def _native_verification(body: dict, sources: dict, canonical_reference: str = "") -> dict:
    result = {}
    for lang in ("ar", "en", "el"):
        text = str(body.get(lang) or "")
        source = sources.get(lang) if isinstance(sources.get(lang), dict) else {}
        source_id = _canonical_native_source_id(source.get("source_id"))
        if text and source_id:
            result[lang] = {
                "status": "VERIFIED_EXACT_NATIVE_SOURCE",
                "source_id": source_id,
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


def dated_liturgical_proper_entry(day: date) -> dict | None:
    entry = DATED_LITURGICAL_PROPERS_REGISTRY.get("dates", {}).get(day.isoformat())
    return copy.deepcopy(entry) if isinstance(entry, dict) else None


def h2_lectionary_entry(day: date) -> dict | None:
    entry = JORDAN_2026_H2_BY_DATE.get(day.isoformat())
    return copy.deepcopy(entry) if isinstance(entry, dict) else None


def _pinned_reference_reading(kind: str, payload: dict, day_entry: dict, reference_registry: str = "canonical/jordan_2026_h2_lectionary.json") -> dict:
    canonical_reference = str(payload.get("canonical_reference") or "").strip()
    reference = _localized(payload.get("reference"))
    titles = {
        "matins_gospel": loc("إنجيل السحر", "Matins Gospel", "Ἑωθινὸν Εὐαγγέλιον"),
        "epistle": loc("الرسالة", "Epistle", "Ἀπόστολος"),
        "gospel": loc("الإنجيل", "Gospel", "Εὐαγγέλιον"),
    }
    sources = day_entry.get("sources") if isinstance(day_entry.get("sources"), dict) else {}
    source_url = str(sources.get("regular_cycle") or sources.get("old_calendar_cross_check") or "")
    verification = {
        lang: {
            "status": "PINNED_EXACT_REFERENCE_TEXT_PENDING_NATIVE_CORPUS",
            "source_id": "official_orthodox_regular_cycle_with_jordan_old_calendar_overrides",
            "source_url": source_url,
            "canonical_reference": canonical_reference,
            "reference_available": bool(reference.get(lang)),
            "text_available": False,
            "ai_translation_used": False,
            "automatic_diacritization_used": False,
        } for lang in ("ar", "en", "el")
    }
    return {
        "icon": "📖" if kind in {"gospel", "matins_gospel"} else "📜",
        "kind": kind,
        "title": titles[kind],
        "reference": reference,
        "body": reading_loc(),
        "source": {lang: source_url for lang in ("ar", "en", "el")},
        "native_source_verification": verification,
        "translation_locked": True,
        "publication_status": "PINNED_EXACT_REFERENCE_TEXT_PENDING_NATIVE_CORPUS",
        "integrity": {
            "status": "PINNED_EXACT_REFERENCE",
            "canonical_reference": canonical_reference,
            "calendar": "JORDAN_JERUSALEM_OLD_CALENDAR",
            "reference_registry": reference_registry,
            "ai_translation_used": False,
            "automatic_diacritization_used": False,
        },
    }


def h2_reference_readings(day: date, info: dict) -> list[dict] | None:
    entry = h2_lectionary_entry(day)
    if not entry:
        return None
    refs = entry.get("reading_references") if isinstance(entry.get("reading_references"), dict) else {}
    resolved = [default_prokeimenon(info, day)]
    for kind in ("matins_gospel", "epistle", "gospel"):
        payload = refs.get(kind)
        if isinstance(payload, dict) and payload.get("canonical_reference"):
            resolved.append(_pinned_reference_reading(kind, payload, entry, "canonical/jordan_2026_h2_lectionary.json"))
    return resolved


def internal_calendar_reference_readings(day: date, info: dict) -> list[dict] | None:
    entry = internal_calendar_entry(day)
    if not isinstance(entry, dict):
        return None
    refs = entry.get("reading_references") if isinstance(entry.get("reading_references"), dict) else {}
    if not refs:
        return None
    resolved = [default_prokeimenon(info, day)]
    for kind in ("matins_gospel", "epistle", "gospel"):
        payload = refs.get(kind)
        if isinstance(payload, dict) and payload.get("canonical_reference"):
            resolved.append(_pinned_reference_reading(
                kind, payload, entry, "canonical/internal_calendar_2026_2050.json"
            ))
    return resolved if len(resolved) > 1 else None


def paschal_cycle_proper_entry(day: date, info: dict) -> dict | None:
    offset = (day - info["pascha"]).days
    entry = PASCHAL_CYCLE_PROPERS_REGISTRY.get("offsets", {}).get(str(offset))
    return copy.deepcopy(entry) if isinstance(entry, dict) else None


def resurrectional_proper_entry(tone: int | None) -> dict | None:
    if tone is None:
        return None
    entry = RESURRECTIONAL_PROPERS_REGISTRY.get("tones", {}).get(str(tone))
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


def named_reading_block_loc(reading: dict) -> dict:
    """Render a daily reading with its appointed name and localized reference."""
    block = reading_block_loc(reading, prefer_empty_ar_when_missing=True)
    title = reading.get("title", {}) if isinstance(reading.get("title"), dict) else {}
    out = {"ar": "", "en": "", "el": ""}
    for lang in ("ar", "en", "el"):
        content = str(block.get(lang) or "").strip()
        if not content:
            continue
        name = str(title.get(lang) or "").strip()
        out[lang] = (name + " — " + content).strip(" —") if name else content
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
    proper_candidates = (
        (dated_liturgical_proper_entry(day), f"dated:{day.isoformat()}"),
        (paschal_cycle_proper_entry(day, info), "paschal_cycle"),
        (fixed_proper_entry(info), "fixed_feast"),
    )
    for feast, provenance in proper_candidates:
        if feast and isinstance(feast.get("prokeimenon"), dict):
            return _prokeimenon_reading(
                feast["prokeimenon"],
                _proper_sources(feast),
                f"{provenance}:{feast.get('id')}",
            )

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
    # Sundays such as Pascha itself do not belong to the ordinary Octoechos
    # tone fallback. Keep the lane explicitly unavailable rather than crashing
    # the year-boundary/offline calendar or inventing a weekday prokeimenon.
    return {
        "icon": "🎵",
        "kind": "prokeimenon",
        "title": loc("البروكيمنن", "Prokeimenon", "Προκείμενον"),
        "reference": loc(
            "يُستكمل من المصدر الرسمي لليوم",
            "Completed from the official source for the day",
            "Συμπληρώνεται ἀπὸ τὴν ἐπίσημη πηγὴ τῆς ἡμέρας",
        ),
        "body": reading_loc(),
        "publication_status": "BLOCKED_MISSING_OFFICIAL_PROKEIMENON",
        "translation_locked": True,
        "integrity": {
            "status": "UNAVAILABLE_UNTIL_EXACT_OFFICIAL_NATIVE_SOURCE",
            "ai_translation_used": False,
            "automatic_diacritization_used": False,
        },
    }

def default_prokeimenon(info: dict, day: date | None = None) -> dict:
    return exact_or_sunday_prokeimenon(day or date.today(), info)


def reading_defaults(info: dict, day: date | None = None) -> list[dict]:
    day = day or date.today()
    h2 = h2_reference_readings(day, info)
    if h2 is not None:
        return h2
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
    """Compact available references for upcoming-day cards."""
    result: dict[str, dict] = {}
    for kind in ("matins_gospel", "epistle", "gospel"):
        reading = get_reading(readings, kind)
        if not reading:
            continue
        result[kind] = {
            "title": copy.deepcopy(reading.get("title") or loc("الرسالة" if kind == "epistle" else "الإنجيل")),
            "reference": copy.deepcopy(reading.get("reference") or loc("")),
        }
    return result


def synchronize_next_sunday_schedule(
    data: dict,
    next_readings: list[dict] | None = None,
    source: str | None = None,
    *,
    require_complete: bool | None = None,
) -> dict:
    """Keep next-Sunday cards synchronized with the verified reading payload.

    ``orthodox_integrity --apply`` resolves canonical references before the
    independent native-language corpora are filled. During that first pass the
    display references may intentionally be blank. ``require_complete=False``
    therefore records a pending state without publishing empty references. The
    final post-corpus rebuild uses the default strict mode and fails closed if
    either reference is still absent.
    """
    # Backward-compatible phase detection: older callers passed ``source``
    # during the pre-corpus phase but did not yet pass ``require_complete``.
    # Treat that call as pending, while source-less post-corpus calls remain
    # strict. Explicit True/False always wins.
    if require_complete is None:
        require_complete = source is None

    integrity_next = (data.get("integrity_inputs") or {}).get("next_sunday") or {}
    readings = next_readings if isinstance(next_readings, list) else integrity_next.get("readings")
    if not isinstance(readings, list):
        raise ValueError("missing integrity_inputs.next_sunday.readings")

    refs = reading_references(readings)
    missing: list[str] = []
    for kind in ("epistle", "gospel"):
        block = refs.get(kind) if isinstance(refs, dict) else None
        reference = block.get("reference") if isinstance(block, dict) else None
        has_reference = isinstance(reference, dict) and any(
            str(reference.get(lang) or "").strip() for lang in ("ar", "en", "el")
        )
        if not has_reference:
            missing.append(kind)

    if missing and not require_complete:
        sunday = data.get("next_sunday")
        if isinstance(sunday, dict):
            sunday["verification_status"] = "PENDING_NATIVE_CORPUS_REFERENCE"
        next_date = str(
            (sunday or {}).get("date_iso")
            or integrity_next.get("date_iso")
            or ""
        )
        for item in data.get("upcoming") or []:
            if isinstance(item, dict) and str(item.get("date") or "") == next_date:
                item["verification_status"] = "PENDING_NATIVE_CORPUS_REFERENCE"
        return {}

    if missing:
        joined = ", ".join(missing)
        raise ValueError(
            f"next Sunday {joined} reference is missing after native-corpus resolution"
        )

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
        raise ValueError("next Sunday is missing from the eight-day future list")
    return refs


def _empty_variable_parts() -> dict[str, dict]:
    return {
        "first_antiphon": loc(""),
        "second_antiphon": loc(""),
        "third_antiphon": loc(""),
        "entrance_hymn": loc(""),
        "trisagion_hymn": loc(""),
        "alleluia_verses": loc(""),
        "theotokos_hymn": loc(""),
        "dismissal": loc(""),
    }


def variable_liturgy_parts(day: date, info: dict, tone: int | None) -> dict:
    """Resolve seasonal groups with explicit per-slot priority and conflicts.

    A lower-priority rule can fill an empty slot but cannot erase a stronger
    rule. Two different texts at the same priority are treated as a registry
    error instead of being silently selected by file order.
    """
    result = _empty_variable_parts()
    applied: list[str] = []
    slot_state = {slot: {"priority": -1, "rule_id": None} for slot in result}
    variants = LITURGY_VARIABLE_PARTS_REGISTRY.get("variants", {})
    jy, jm, jd = gregorian_to_julian_date(day)
    pascha_offset = (day - info["pascha"]).days

    def apply_candidate(slot: str, candidate: dict, priority: int, rule_id: str) -> bool:
        if not _has_text(candidate):
            return False
        current = slot_state[slot]
        current_priority = int(current["priority"])
        if priority < current_priority:
            return False
        if priority == current_priority and _has_text(result[slot]) and result[slot] != candidate:
            raise ValueError(
                f"Conflicting Liturgy variable parts for slot {slot!r} at priority "
                f"{priority}: {current['rule_id']!r} vs {rule_id!r}"
            )
        result[slot] = candidate
        slot_state[slot] = {"priority": priority, "rule_id": rule_id}
        return True

    for rule in LITURGY_VARIABLE_PARTS_REGISTRY.get("rules", []):
        kind = rule.get("kind")
        matches = False
        if kind == "julian_fixed":
            matches = int(rule.get("month", 0)) == jm and int(rule.get("day", 0)) == jd
        elif kind == "pascha_offset":
            matches = int(rule.get("offset", 9999)) == pascha_offset
        elif kind == "pascha_offset_range":
            matches = int(rule.get("start", 9999)) <= pascha_offset <= int(rule.get("end", -9999))
        if not matches:
            continue
        variant_id = str(rule.get("variant") or "")
        rule_id = str(rule.get("id") or variant_id)
        priority = int(rule.get("priority", 100))
        variant = variants.get(variant_id) if isinstance(variants, dict) else None
        parts = variant.get("parts") if isinstance(variant, dict) else None
        accepted = False
        if isinstance(parts, dict):
            for slot in result:
                accepted = apply_candidate(slot, _localized(parts.get(slot)), priority, rule_id) or accepted
        if accepted:
            applied.append(rule_id)

    tone_entry = LITURGY_VARIABLE_PARTS_REGISTRY.get("alleluia_by_tone", {}).get(str(tone))
    tone_priority = int(
        LITURGY_VARIABLE_PARTS_REGISTRY.get("rule_resolution", {}).get(
            "ordinary_tone_alleluia_priority", 10
        )
    )
    if isinstance(tone_entry, dict):
        apply_candidate(
            "alleluia_verses", _localized(tone_entry.get("verses")),
            tone_priority, f"octoechos_alleluia_tone_{tone}",
        )

    if day.weekday() != 6:
        weekday_id = str(LITURGY_VARIABLE_PARTS_REGISTRY.get("ordinary_weekday_dismissal_variant") or "")
        weekday = variants.get(weekday_id) if isinstance(variants, dict) else None
        parts = weekday.get("parts") if isinstance(weekday, dict) else None
        candidate = _localized(parts.get("dismissal")) if isinstance(parts, dict) else loc("")
        weekday_priority = int(
            LITURGY_VARIABLE_PARTS_REGISTRY.get("rule_resolution", {}).get(
                "ordinary_weekday_dismissal_priority", 5
            )
        )
        if apply_candidate("dismissal", candidate, weekday_priority, weekday_id):
            applied.append(weekday_id)

    result["variant_ids"] = list(dict.fromkeys(applied))
    result["slot_provenance"] = slot_state
    result["pascha_offset"] = pascha_offset
    result["julian_date"] = f"{jy:04d}-{jm:02d}-{jd:02d}"
    return result


def feast_inserts(info: dict, day: date | None = None) -> dict[str, dict]:
    """Resolve source-backed propers and variable Liturgy groups fail-closed."""
    result: dict = {
        "troparion": loc(""), "kontakion": loc(""), "church_troparion": loc(""),
        "communion": loc(""), "evangelist": loc("الإنجيلي", "Evangelist", "Εὐαγγελιστής"),
        "proper_id": None, "sources": {}, "resurrection_tone": None, "eothinon": None,
    }
    dated = dated_liturgical_proper_entry(day) if day is not None else None
    if dated:
        result.update({
            "troparion": _localized(dated.get("troparion")),
            "kontakion": _localized(dated.get("kontakion")),
            "communion": _localized(dated.get("communion")),
            "proper_id": f"dated:{day.isoformat()}",
            "sources": copy.deepcopy(dated.get("authority") or {}),
            "resurrection_tone": dated.get("resurrection_tone"),
            "eothinon": dated.get("eothinon"),
        })
    else:
        movable = paschal_cycle_proper_entry(day, info) if day is not None else None
        entry = movable or fixed_proper_entry(info)
        if entry:
            provenance = "paschal" if movable else "fixed"
            result.update({
                "troparion": _localized(entry.get("troparion")),
                "kontakion": _localized(entry.get("kontakion")),
                "communion": _localized(entry.get("communion")),
                "proper_id": f"paschal:{entry.get('id')}" if movable else entry.get("id"),
                "proper_provenance": provenance,
                "sources": copy.deepcopy(entry.get("sources") or {}),
            })
        else:
            tone = resurrection_tone(day, info["pascha"]) if day is not None else None
            resurrectional = resurrectional_proper_entry(tone)
            if resurrectional:
                result.update({
                    "troparion": _localized(resurrectional.get("troparion")),
                    "communion": _localized(RESURRECTIONAL_PROPERS_REGISTRY.get("ordinary_sunday_communion")),
                    "proper_id": f"octoechos:tone:{tone}",
                    "proper_provenance": "octoechos",
                    "sources": copy.deepcopy(RESURRECTIONAL_PROPERS_REGISTRY.get("sources") or {}),
                    "resurrection_tone": tone,
                })
    if day is not None:
        variable = variable_liturgy_parts(day, info, result.get("resurrection_tone"))
        result.update(variable)
    else:
        result.update(_empty_variable_parts())
        result["variant_ids"] = []
    return result

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


def liturgy_day_plan(day: date, selection: dict, epistle: dict | None = None, gospel: dict | None = None, matins_gospel: dict | None = None, inserts: dict | None = None) -> dict:
    """Describe exactly what belongs to today's appointed Liturgy.

    Orthros/Matins, Hours, Proskomide and personal Communion offices are
    deliberately outside this plan.  This object is metadata, not prayer text.
    """
    inserts = inserts or {}
    def canonical(reading: dict | None) -> str:
        if not isinstance(reading, dict):
            return ""
        return str((reading.get("integrity") or {}).get("canonical_reference") or "")
    return {
        "date_iso": day.isoformat(),
        "appointed_liturgy_type": selection.get("service_type"),
        "appointed_service_id": selection.get("service_id"),
        "appointed_service_form": selection.get("service_form"),
        "selection_rule_id": selection.get("rule_id"),
        "selection_authority": selection.get("authority"),
        "displayable": bool(selection.get("displayable")),
        "strict_core_only": True,
        "scope": "APPOINTED_LITURGY_FROM_OPENING_BLESSING_TO_DISMISSAL",
        "no_unappointed_material": True,
        "wrong_rite_fallback_allowed": False,
        "machine_translation_allowed": False,
        "liturgy_readings": {
            "epistle_canonical": canonical(epistle),
            "gospel_canonical": canonical(gospel),
        },
        "orthros_separate": {
            "matins_gospel_canonical": canonical(matins_gospel),
            "matins_gospel_reference": copy.deepcopy(
                (matins_gospel or {}).get("reference") if isinstance((matins_gospel or {}).get("reference"), dict) else {}
            ),
            "belongs_to": "orthros_not_divine_liturgy",
        },
        "daily_propers": {
            "proper_id": inserts.get("proper_id"),
            "variable_part_ids": copy.deepcopy(inserts.get("variant_ids") or []),
            "fail_closed": True,
        },
        "separate_adjacent_offices": [
            "orthros", "hours", "proskomide",
            "pre_communion_prayers", "thanksgiving_after_communion",
        ],
    }


def build_liturgy_service(service_id: str, day: date, info: dict, readings: list[dict], label_prefix_ar: str) -> dict:
    """Build the appointed service overlay and never substitute a different rite.

    A complete native service template may be extended only when all three
    published language lanes are present.  Otherwise the selected rite is
    represented by a non-liturgical availability card with no prayer-text
    fallback, no template reference, and no dynamic replacements.
    """
    selection = liturgy_service_selection(day, info)
    is_upcoming = service_id == "next_sunday_full_liturgy"
    selected_type = str(selection.get("service_type") or "")
    selected_label = copy.deepcopy(selection.get("label") or LITURGY_SERVICE_LABELS[selected_type])
    prefix = loc(
        label_prefix_ar,
        "Next Sunday" if is_upcoming else "Today",
        "Ἡ ἐρχόμενη Κυριακή" if is_upcoming else "Σήμερα",
    )
    title = {
        lang: f"{prefix.get(lang, '')} — {selected_label.get(lang, '')}".strip(" —")
        for lang in ("ar", "en", "el")
    }
    contract = {
        "rules": "canonical/liturgy_service_rules.json",
        "editions": "canonical/liturgy_service_editions.json",
        "full_service_contract": "canonical/full_liturgy_service_contract.json",
        "selected_liturgy_type": selected_type,
        "selected_service_form": selection.get("service_form"),
        "selection_reason": copy.deepcopy(selection.get("reason") or loc("", "", "")),
        "selected_service_id": selection.get("service_id"),
        "selection_rule_id": selection.get("rule_id"),
        "selection_authority": selection.get("authority"),
        "selection_source_url": selection.get("source_url") or "",
        "pascha_offset": selection.get("pascha_offset"),
        "native_editions": copy.deepcopy(selection.get("native_editions") or {}),
        "availability_note": copy.deepcopy(selection.get("availability_note") or loc("", "", "")),
        "source_ids": copy.deepcopy(selection.get("source_ids") or []),
        "import_contract": selection.get("import_contract") or "",
        "displayable": bool(selection.get("displayable")),
        "full_service_required": True,
        "full_service_scope": "APPOINTED_LITURGY_FROM_OPENING_BLESSING_TO_DISMISSAL",
        "wrong_liturgy_fallback_allowed": False,
        "fail_closed": True,
        "strict_core_only": True,
        "adjacent_offices_separate": True,
        "no_unappointed_material": True,
    }

    if not selection.get("displayable"):
        if selected_type == "typikon_override_required":
            status_text = loc(
                "يتزامن في هذا التاريخ عيد كبير مع أيام لها ترتيب خاص. يلزم قرار طقسي مؤرخ من الجهة الكنسية المعتمدة قبل اختيار نوع القداس، لذلك لا يعرض التطبيق أي قداس بديل.",
                "A major feast coincides with days governed by special rubrics. A dated ruling from the approved church authority is required before selecting the Liturgy, so the app displays no substitute rite.",
                "Μεγάλη ἑορτὴ συμπίπτει μὲ ἡμέρες ἰδιαίτερων τυπικῶν διατάξεων. Ἀπαιτεῖται χρονολογημένη ἀπόφαση τῆς ἐγκεκριμένης ἐκκλησιαστικῆς ἀρχῆς, καὶ ἡ ἐφαρμογὴ δὲν προβάλλει ὑποκατάστατη Λειτουργία.",
            )
            publication_status = "BLOCKED_REQUIRES_DATED_OFFICIAL_TYPIKON_OVERRIDE"
        elif selected_type == "no_divine_liturgy":
            status_text = loc(
                "يحدّد التقويم الكنسي أن هذا اليوم لا تُقام فيه خدمة قداس إلهي. لذلك لا يعرض التطبيق قداسًا آخر مكانه.",
                "The church calendar appoints no Eucharistic Divine Liturgy for this day, so the app does not display another Liturgy in its place.",
                "Τὸ ἐκκλησιαστικὸ ἡμερολόγιο δὲν ὁρίζει εὐχαριστιακὴ Θεία Λειτουργία γιὰ αὐτὴ τὴν ἡμέρα· ἡ ἐφαρμογὴ δὲν προβάλλει ἄλλη Λειτουργία στὴ θέση της.",
            )
            publication_status = "NO_DIVINE_LITURGY_APPOINTED"
        else:
            status_text = loc(
                f"حدّد التقويم الكنسي لهذه الخدمة: {selected_label['ar']}. لم تُدمج بعد الطبعة الأصلية الكاملة في اللغات الثلاث، لذلك لا يعرض التطبيق قداس القديس يوحنا الذهبي الفم بدلها.",
                f"The church calendar appoints {selected_label['en']}. Its complete native editions have not yet been imported in all three languages, so the app does not substitute the Liturgy of Saint John Chrysostom.",
                f"Τὸ ἐκκλησιαστικὸ ἡμερολόγιο ὁρίζει: {selected_label['el']}. Οἱ πλήρεις πρωτότυπες ἐκδόσεις δὲν ἔχουν ἀκόμη εἰσαχθεῖ καὶ στὶς τρεῖς γλώσσες, γι’ αὐτὸ ἡ ἐφαρμογὴ δὲν ἀντικαθιστᾷ τὴν ἀκολουθία μὲ τὴ Λειτουργία τοῦ Ἁγίου Ἰωάννου τοῦ Χρυσοστόμου.",
            )
            publication_status = "BLOCKED_MISSING_COMPLETE_NATIVE_SERVICE_EDITION"
        return {
            "id": service_id,
            "category": "liturgy",
            "icon": "⛪",
            "title": title,
            "summary": copy.deepcopy(status_text),
            "source_language": "multilingual_status_metadata",
            "translation_status": "NON_LITURGICAL_AVAILABILITY_METADATA",
            "dynamic_date": f"{day:%Y-%m-%d}",
            "selected_liturgy_type": selected_type,
            "selected_service_form": selection.get("service_form"),
            "selected_liturgy": copy.deepcopy(selection),
            "liturgy_service_contract": contract,
            "publication_status": publication_status,
            "full_service_complete": False,
            "wrong_liturgy_fallback_allowed": False,
            "liturgy_day_plan": liturgy_day_plan(day, selection),
            "source_provenance": {
                "policy": "canonical/source_policy.json",
                "service_rules": "canonical/liturgy_service_rules.json",
                "service_editions": "canonical/liturgy_service_editions.json",
                "native_import_contract": selection.get("import_contract") or "canonical/liturgy_native_import_contracts.json",
                "source_ids": copy.deepcopy(selection.get("source_ids") or []),
                "complete_service_claim": False,
                "completeness_status": "SELECTED_RITE_NOT_AVAILABLE_AS_COMPLETE_THREE_LANGUAGE_NATIVE_EDITION",
                "ai_liturgical_translation_used": False,
                "fail_closed": True,
            },
            "segments": sanitize_segments([
                {
                    "type": "section",
                    "title": loc("نوع الخدمة المعيّن", "Appointed service type", "Ὁρισμένος τύπος ἀκολουθίας"),
                },
                {
                    "type": "text",
                    "speaker": loc("حالة الخدمة", "Service status", "Κατάσταση ἀκολουθίας"),
                    "text": status_text,
                },
                {
                    "type": "text",
                    "speaker": loc("حالة استيراد الطبعة الأصلية", "Native-edition import status", "Κατάσταση εἰσαγωγῆς πρωτότυπης ἐκδόσεως"),
                    "text": copy.deepcopy(selection.get("availability_note") or loc("", "", "")),
                },
            ]),
        }

    epistle = get_reading(readings, "epistle") or {}
    gospel = get_reading(readings, "gospel") or {}
    matins_gospel = get_reading(readings, "matins_gospel") or {}
    prok = get_reading(readings, "prokeimenon") or {}
    inserts = feast_inserts(info, day)

    exact_replacements = {
        "[طروبارية اليوم]": copy.deepcopy(inserts["troparion"]),
        "[طروبارية صاحب الكنيسة أو القديس إن وُجدت]": copy.deepcopy(inserts["church_troparion"]),
        "[القنداق]": copy.deepcopy(inserts["kontakion"]),
        "[البروكيمنن]": reading_block_loc(prok, prefer_empty_ar_when_missing=False),
        "[فصل من رسالة اليوم]": named_reading_block_loc(epistle),
        "[فصل الإنجيل المعيّن لهذا اليوم]": named_reading_block_loc(gospel),
        "[آية المناولة]": copy.deepcopy(inserts["communion"]),
    }
    inline_replacements = {"[اسم الإنجيلي]": loc(evangelist_for_reading(gospel))}
    daily_hymns = {
        language: "\n\n".join(
            str(block.get(language) or "").strip()
            for block in (inserts["troparion"], inserts["church_troparion"], inserts["kontakion"])
            if str(block.get(language) or "").strip()
        )
        for language in ("ar", "en", "el")
    }
    slot_replacements = {
        "daily_hymns": daily_hymns,
        "daily_troparion": copy.deepcopy(inserts["troparion"]),
        "church_troparion": copy.deepcopy(inserts["church_troparion"]),
        "daily_kontakion": copy.deepcopy(inserts["kontakion"]),
        "prokeimenon": reading_block_loc(prok, prefer_empty_ar_when_missing=False),
        "epistle": named_reading_block_loc(epistle),
        "gospel": named_reading_block_loc(gospel),
        "communion_hymn": copy.deepcopy(inserts["communion"]),
        "first_antiphon": copy.deepcopy(inserts["first_antiphon"]),
        "second_antiphon": copy.deepcopy(inserts["second_antiphon"]),
        "third_antiphon": copy.deepcopy(inserts["third_antiphon"]),
        "entrance_hymn": copy.deepcopy(inserts["entrance_hymn"]),
        "trisagion_hymn": copy.deepcopy(inserts["trisagion_hymn"]),
        "alleluia_verses": copy.deepcopy(inserts["alleluia_verses"]),
        "theotokos_hymn": copy.deepcopy(inserts["theotokos_hymn"]),
        "dismissal": copy.deepcopy(inserts["dismissal"]),
    }
    slot_inline_replacements = {"gospel_evangelist_name": loc(evangelist_for_reading(gospel))}
    summary = loc(
        f"{info['feast_ar']} — {info['fast_ar']} — تُركّب قراءات اليوم والقطع المتحققة فوق النص الثابت للخدمة المعيّنة دون استبدال طقس بآخر.",
        "Verified daily readings and feast texts are composed with the appointed complete native service template without substituting another rite.",
        "Τὰ ἐπαληθευμένα ἀναγνώσματα καὶ κείμενα τῆς ἡμέρας συντίθενται μὲ τὸ ὁρισμένο πλήρες πρωτότυπο κείμενο, χωρὶς ἀντικατάσταση ἄλλου τύπου Λειτουργίας.",
    )
    segments = sanitize_segments([
        {
            "type": "section",
            "title": loc(
                f"{label_prefix_ar}: خدمة اليوم",
                "Next Sunday’s service" if is_upcoming else "Today’s service",
                "Ἡ ἀκολουθία τῆς ἐρχόμενης Κυριακῆς" if is_upcoming else "Ἡ σημερινὴ ἀκολουθία",
            ),
        },
        {
            "type": "text",
            "speaker": loc("اليوم الكنسي", "Church day", "Ἐκκλησιαστικὴ ἡμέρα"),
            "text": loc(
                f"{ar_date_label(day)} — {info['feast_ar']} — {info['fast_ar']}. نوع الخدمة: {selected_label['ar']}.",
                f"{day:%Y-%m-%d} — {info.get('feast_en') or info['feast_ar']} — {info.get('fast_en') or info['fast_ar']}. Service: {selected_label['en']}.",
                f"{day:%Y-%m-%d} — {info.get('feast_el') or info['feast_ar']} — {info.get('fast_el') or info['fast_ar']}. Ἀκολουθία: {selected_label['el']}.",
            ),
        },
        {"type": "section", "title": loc("قراءات وقطع اليوم", "Readings and hymns of the day", "Ἀναγνώσματα καὶ ὕμνοι τῆς ἡμέρας")},
    ])
    selected_service_id = str(selection.get("service_id") or "divine_liturgy")
    return {
        "id": service_id,
        "extends_service_id": selected_service_id,
        "category": "liturgy",
        "icon": "⛪",
        "title": title,
        "summary": summary,
        "source_language": "ar",
        "translation_status": "verified_daily_overlay_v3_appointed_rite",
        "template_id": f"library:{selected_service_id}",
        "dynamic_date": f"{day:%Y-%m-%d}",
        "selected_liturgy_type": selected_type,
        "selected_service_form": selection.get("service_form"),
        "selected_liturgy": copy.deepcopy(selection),
        "liturgy_service_contract": contract,
        "publication_status": "DISPLAYABLE_COMPLETE_NATIVE_SERVICE_FROM_BEGINNING_TO_END",
        "full_service_complete": True,
        "full_service_scope": "APPOINTED_LITURGY_FROM_OPENING_BLESSING_TO_DISMISSAL",
        "wrong_liturgy_fallback_allowed": False,
        "liturgy_day_plan": liturgy_day_plan(day, selection, epistle, gospel, matins_gospel, inserts),
        "daily_reading_contract": {
            "authority": "orthodox_jordan",
            "contract": "canonical/jordan_liturgical_contract.json",
            "date_iso": f"{day:%Y-%m-%d}",
            "selected_liturgy_type": selected_type,
            "selected_liturgy_rule_id": selection.get("rule_id"),
            "epistle_canonical": str(epistle.get("integrity", {}).get("canonical_reference") or ""),
            "gospel_canonical": str(gospel.get("integrity", {}).get("canonical_reference") or ""),
            "orthros_matins_gospel_canonical": str(matins_gospel.get("integrity", {}).get("canonical_reference") or ""),
            "orthros_matins_gospel_belongs_to": "orthros_not_divine_liturgy",
            "resurrection_tone": inserts.get("resurrection_tone"),
            "eothinon": inserts.get("eothinon"),
            "proper_id": inserts.get("proper_id"),
            "variable_parts_registry": "canonical/liturgy_variable_parts.json",
            "variable_part_ids": copy.deepcopy(inserts.get("variant_ids") or []),
            "variable_parts_fail_closed": True,
            "strict_core_only": True,
            "no_unappointed_material": True,
            "fail_closed": True,
        },
        "notice": loc(
            "يُحفظ النص الثابت للخدمة المعيّنة مرة واحدة في المكتبة، ولا تُحقن القطع اليومية إلا بعد التحقق من المصدر والتوقيع.",
            "The appointed static service is stored once; daily pieces are injected only after source and signature validation.",
            "Τὸ σταθερὸ κείμενο τῆς ὁρισμένης ἀκολουθίας ἀποθηκεύεται μία φορά· τὰ ἡμερήσια κείμενα εἰσάγονται μόνο μετὰ τὴν ἐπαλήθευση πηγῆς καὶ ὑπογραφῆς.",
        ),
        "source_provenance": {
            "policy": "canonical/source_policy.json",
            "official_catalog_source": "orthodox_jordan",
            "official_catalog_url": "https://orthodoxjordan.org/تحميل-الصلوات/",
            "status": "PINNED_STATIC_TEXT_WITH_OFFICIAL_CATALOG_PROVENANCE",
            "complete_service_claim": True,
            "completeness_status": "COMPLETE_NATIVE_COMPOSITE_FROM_BEGINNING_TO_END",
            "completion_basis": "APPOINTED_NATIVE_LITURGY_CORE_PLUS_VERIFIED_DAILY_LITURGY_PROPERS",
            "exact_remote_byte_match": False,
            "dynamic_texts_fail_closed": True,
            "ai_liturgical_translation_used": False,
        },
        "segment_replacements": exact_replacements,
        "inline_replacements": inline_replacements,
        "slot_replacements": slot_replacements,
        "slot_inline_replacements": slot_inline_replacements,
        "segments": segments,
    }

def daily_context_segments(day: date, info: dict, readings: list[dict], service_id: str) -> list[dict]:
    """Build a clearly marked daily layer for every service.

    The base prayer text remains stable. Only the date-dependent context and
    pieces available from the daily data source are injected. This avoids
    pretending that a generic API supplies every local sticheron or canon.
    """
    inserts = feast_inserts(info, day)
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
    if "readings" in override and "services" not in override:
        info = day_info(day)
        rebuilt = build_liturgy_service(
            "divine_liturgy",
            day,
            info,
            data.get("readings") or [],
            "خدمة اليوم",
        )
        services = data.get("services") if isinstance(data.get("services"), list) else []
        data["services"] = [
            rebuilt if isinstance(service, dict) and service.get("id") == "divine_liturgy" else service
            for service in services
        ]
    fasting = data.get("fasting")
    if isinstance(fasting, dict) and "fasting" in override:
        verification = fasting.setdefault("verification", {})
        verification["status"] = "DOCUMENTED_OVERRIDE"
        verification["override_file"] = str(path.relative_to(ROOT)).replace("\\", "/")
        abstinence = fasting.get("abstinence") if isinstance(fasting.get("abstinence"), dict) else None
        if abstinence is not None and abstinence.get("applies") is True:
            kind = str(abstinence.get("kind") or "")
            evidence = abstinence.get("verification") if isinstance(abstinence.get("verification"), dict) else {}
            source = str(evidence.get("source") or "").strip()
            if kind not in {"documented_interval", "until_communion", "until_service_end"}:
                raise RuntimeError(f"{path.relative_to(ROOT)}: applied abstinence requires a documented kind")
            if str(evidence.get("status") or "") != "DOCUMENTED_OVERRIDE" or not source:
                raise RuntimeError(f"{path.relative_to(ROOT)}: abstinence requires DOCUMENTED_OVERRIDE evidence and a source")
            if kind == "documented_interval":
                clock = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")
                start = str(abstinence.get("start_time") or "")
                end = str(abstinence.get("end_time") or "")
                if not clock.fullmatch(start) or not clock.fullmatch(end):
                    raise RuntimeError(f"{path.relative_to(ROOT)}: documented_interval requires HH:MM start_time and end_time")
        data["fast"] = copy.deepcopy(fasting.get("title") or data.get("fast"))
        data["fast_detail"] = copy.deepcopy(fasting.get("detail") or data.get("fast_detail"))
    return data


def discovery_readings(day: date, info: dict) -> list[dict]:
    """Resolve the pinned annual registry first, then dated authorities, then discovery."""
    h2 = h2_reference_readings(day, info)
    if h2 is not None:
        return h2
    dated = dated_liturgical_proper_entry(day)
    if dated and isinstance(dated.get("readings"), dict):
        resolved = [default_prokeimenon(info, day)]
        for kind in ("matins_gospel", "epistle", "gospel"):
            reading = dated["readings"].get(kind)
            if isinstance(reading, dict):
                resolved.append(copy.deepcopy(reading))
        return resolved
    internal = internal_calendar_reference_readings(day, info)
    if internal is not None:
        return internal
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

    # Generate compact cards for the same configurable moving horizon used by publication. Each card carries
    # its own fasting profile and reading references, so the app never reuses
    # yesterday's Sunday or fasting information.
    upcoming: list[dict] = []
    upcoming_full_readings: dict[str, list[dict]] = {}
    for i in range(1, resolve_day_count()):
        d = day + timedelta(days=i)
        inf = day_info(d)
        future_readings = discovery_readings(d, inf)
        upcoming_full_readings[d.isoformat()] = future_readings
        refs = reading_references(future_readings)
        future_selection = liturgy_service_selection(d, inf)
        upcoming.append({
            "date": f"{d:%Y-%m-%d}",
            "day": loc(f"{AR_DAYS[d.weekday()]} {d.day} {AR_MONTHS[d.month-1]} / {inf['julian_day']} {AR_MONTHS[inf['julian_month']-1]} قديم", d.strftime("%A, %B %d")),
            "feast": loc(inf["feast_ar"], inf["feast_en"], inf["feast_el"]),
            "status": loc(inf["fast_ar"]),
            "note": loc(inf["feast_ar"], inf["feast_en"], inf["feast_el"]),
            "daily_proper_status": inf["feast_status"],
            "fasting": copy.deepcopy(inf["fasting"]),
            "reading_references": refs,
            "liturgy_service_selection": future_selection,
            "is_sunday": d.weekday() == 6,
        })

    ns = next_sunday(day)
    ns_info = day_info(ns)
    ns_readings = upcoming_full_readings.get(ns.isoformat())
    if ns_readings is None:
        ns_readings = discovery_readings(ns, ns_info)
    ns_refs = reading_references(ns_readings)
    today_liturgy_selection = liturgy_service_selection(day, info)
    next_sunday_liturgy_selection = liturgy_service_selection(ns, ns_info)

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
        "feast": loc(ns_info["feast_ar"], ns_info["feast_en"], ns_info["feast_el"]),
        "daily_proper_status": ns_info["feast_status"],
        "fast": loc(ns_info["fast_ar"]),
        "fasting": copy.deepcopy(ns_info["fasting"]),
        "reading_references": ns_refs,
        "service_id": "next_sunday_full_liturgy",
        "liturgy_service_selection": next_sunday_liturgy_selection,
    }

    data = {
        "schema_version": 10,
        "app_title": loc("الصلوات الكنسية", "Church Prayers", "Ἐκκλησιαστικὲς Προσευχές"),
        "patriarchate": loc("بطريركية الروم الأرثوذكس المقدسية", "Greek Orthodox Patriarchate of Jerusalem", "Πατριαρχεῖον Ἱεροσολύμων"),
        "date_iso": f"{day:%Y-%m-%d}",
        "date_label": loc(f"{ar_date_label(day)} / {info['julian_label_ar']}", day.strftime("%A, %B %d, %Y")),
        "calendar_label": loc("التقويم الكنسي القديم — بطريركية القدس", "Old church calendar — Jerusalem usage"),
        "julian_date": {"year": info["julian_year"], "month": info["julian_month"], "day": info["julian_day"], "label_ar": info["julian_label_ar"]},
        "fast": loc(info["fast_ar"]),
        "fast_detail": loc(info["fast_detail_ar"]),
        "fasting": copy.deepcopy(info["fasting"]),
        "feast": loc(info["feast_ar"], info["feast_en"], info["feast_el"]),
        "daily_proper_status": info["feast_status"],
        "source_note": loc(
            "تُستخدم بيانات الاكتشاف لتحديد اليوم فقط؛ ولا تُنشر النصوص إلا من مسارات عربية وإنجليزية ويونانية أرثوذكسية معتمدة ومستقلة.",
            "Discovery identifies the day only; text is published solely from approved independent Arabic, English, and Greek Orthodox source lanes.",
            "Ἡ ἀνακάλυψη προσδιορίζει μόνον τὴν ἡμέρα· τὰ κείμενα δημοσιεύονται μόνο ἀπὸ ἐγκεκριμένες ανεξάρτητες ὀρθόδοξες πηγές.",
        ),
        "translation_notice": loc("نصوص الكتاب المقدس من طبعة عربية مثبتة ومشكولة؛ ولا تُستخدم ترجمة آلية حرة للنص المقدس أو للقطع الليتورجية."),
        "translation_status": "source_native_only_or_unavailable",
        "language_content_mode": "THREE_INDEPENDENT_OFFICIAL_NATIVE_SOURCES",
        "machine_translation_used": False,
        "translation_fallback_policy": "DISABLED_NO_CROSS_LANGUAGE_FALLBACK",
        "liturgy_service_selection": today_liturgy_selection,
        "liturgy_service_rules": "canonical/liturgy_service_rules.json",
        "liturgy_service_editions": "canonical/liturgy_service_editions.json",
        "wrong_liturgy_fallback_allowed": False,
        "language_sources": {
            "ar": {
                "policy": "native_official_source_only",
                "primary": ["orthodox_jordan", "jerusalem_patriarchate_ar"],
                "translation_allowed": False,
            },
            "el": {
                "policy": "native_official_source_only",
                "primary": ["jerusalem_patriarchate_el", "church_of_greece_apostoliki_diakonia", "church_of_greece_ecclesia"],
                "fallback": ["goarch_digital_chant_stand_greek"],
                "translation_allowed": False,
            },
            "en": {
                "policy": "native_official_source_only",
                "primary": ["jerusalem_patriarchate_en", "goarch_online_chapel", "goarch_digital_chant_stand_english"],
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
            "source_priority": [
                "orthodox_jordan",
                "jerusalem_patriarchate",
                "official_greek_orthodox",
            ],
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
            "morning_prayer",
            "evening_prayer",
            "small_compline",
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
