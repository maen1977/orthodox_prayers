#!/usr/bin/env python3
"""Build the compact Jordan/Jerusalem old-calendar lectionary index for 2026 H2.

The index covers every civil day from 2026-07-28 through 2026-12-31.  It stores
references and calendar metadata only; shared liturgical and Scripture texts stay
in their existing canonical registries/corpora so the Android package remains
small.
"""
from __future__ import annotations

import copy
import json
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from update_liturgical_data import day_info  # noqa: E402
from orthodox_integrity import parse_reference  # noqa: E402

START = date(2026, 7, 28)
END = date(2026, 12, 31)
OUT_CANONICAL = ROOT / "canonical" / "jordan_2026_h2_lectionary.json"
OUT_ASSET = ROOT / "app" / "src" / "main" / "assets" / "data" / "calendar_2026_h2.json"
DAILY_RECORDS = ROOT / "canonical" / "daily_lectionary_records.json"

RAW = r"""
2026-07-28|1 Corinthians 12:12-26|Matthew 18:18-22; 19:1-2,13-15
2026-07-29|1 Corinthians 13:4-14:5|Matthew 20:1-16
2026-07-30|1 Corinthians 14:6-19|Matthew 20:17-28
2026-07-31|1 Corinthians 14:26-40|Matthew 21:12-14,17-20
2026-08-01|Romans 14:6-9|Matthew 15:32-39
2026-08-02|1 Corinthians 3:9-17|Matthew 14:22-34
2026-08-03|1 Corinthians 15:12-19|Matthew 21:18-22
2026-08-04|1 Corinthians 15:29-38|Matthew 21:23-27
2026-08-05|1 Corinthians 16:4-12|Matthew 21:28-32
2026-08-06|2 Corinthians 1:1-7|Matthew 21:43-46
2026-08-07|2 Corinthians 1:12-20|Matthew 22:23-33
2026-08-08|Romans 15:30-33|Matthew 17:24-18:4
2026-08-09|1 Corinthians 4:9-16|Matthew 17:14-23
2026-08-10|2 Corinthians 2:4-15|Matthew 23:13-22
2026-08-11|2 Corinthians 2:14-3:3|Matthew 23:23-28
2026-08-12|2 Corinthians 3:4-11|Matthew 23:29-39
2026-08-13|2 Corinthians 4:1-6|Matthew 24:13-28
2026-08-14|2 Corinthians 4:13-18|Matthew 24:27-33,42-51
2026-08-15|1 Corinthians 1:3-9|Matthew 19:3-12
2026-08-16|1 Corinthians 9:2-12|Matthew 18:23-35
2026-08-17|2 Corinthians 5:10-15|Mark 1:9-15
2026-08-18|2 Corinthians 5:15-21|Mark 1:16-22
2026-08-19|2 Corinthians 6:11-16|Mark 1:23-28
2026-08-20|2 Corinthians 7:1-10|Mark 1:29-35
2026-08-21|2 Corinthians 7:10-16|Mark 2:18-22
2026-08-22|1 Corinthians 1:26-29|Matthew 20:29-34
2026-08-23|1 Corinthians 15:1-11|Matthew 19:16-26
2026-08-24|2 Corinthians 8:7-15|Mark 3:6-12
2026-08-25|2 Corinthians 8:16-9:5|Mark 3:13-19
2026-08-26|2 Corinthians 9:12-10:7|Mark 3:20-27
2026-08-27|2 Corinthians 10:7-18|Mark 3:28-35
2026-08-28|2 Corinthians 11:5-21|Mark 4:1-9
2026-08-29|1 Corinthians 2:6-9|Matthew 22:15-22
2026-08-30|1 Corinthians 16:13-24|Matthew 21:33-42
2026-08-31|2 Corinthians 12:10-19|Mark 4:10-23
2026-09-01|2 Corinthians 12:20-13:2|Mark 4:24-34
2026-09-02|2 Corinthians 13:3-14|Mark 4:35-41
2026-09-03|Galatians 1:1-10,20-2:5|Mark 5:1-20
2026-09-04|Galatians 2:6-10|Mark 5:22-24,35-6:1
2026-09-05|1 Corinthians 4:1-5|Matthew 23:1-12
2026-09-06|2 Corinthians 1:21-2:4|Matthew 22:1-14
2026-09-07|Galatians 2:11-16|Mark 5:24-34
2026-09-08|Galatians 2:21-3:7|Mark 6:1-7
2026-09-09|Galatians 3:15-22|Mark 6:7-13
2026-09-10|Galatians 3:23-4:5|Mark 6:30-45
2026-09-11|Galatians 4:8-21|Mark 6:45-53
2026-09-12|1 Corinthians 4:17-5:5|Matthew 24:1-13
2026-09-13|2 Corinthians 4:6-15|Matthew 22:35-46
2026-09-14|Galatians 4:28-5:10|Mark 6:54-7:8
2026-09-15|Galatians 5:11-21|Mark 7:5-16
2026-09-16|Galatians 6:2-10|Mark 7:14-24
2026-09-17|Ephesians 1:1-9|Mark 7:24-30
2026-09-18|Ephesians 1:7-17|Mark 8:1-10
2026-09-19|1 Corinthians 10:23-28|Matthew 24:34-44
2026-09-20|2 Corinthians 6:1-10|Matthew 25:14-30
2026-09-21|Ephesians 1:22-2:3|Luke 3:19-22
2026-09-22|Ephesians 2:19-3:7|Luke 3:23-4:1
2026-09-23|Ephesians 3:8-21|Luke 4:1-15
2026-09-24|Ephesians 4:14-19|Luke 4:16-22
2026-09-25|Ephesians 4:17-25|Luke 4:22-30
2026-09-26|1 Corinthians 14:20-25|Luke 4:31-36
2026-09-27|2 Corinthians 6:16-7:1|Luke 5:1-11
2026-09-28|Ephesians 4:25-32|Luke 4:37-44
2026-09-29|Ephesians 5:20-26|Luke 5:12-16
2026-09-30|Ephesians 5:25-33|Luke 5:33-39
2026-10-01|Ephesians 5:33-6:9|Luke 6:12-19
2026-10-02|Ephesians 6:18-24|Luke 6:17-23
2026-10-03|1 Corinthians 15:39-45|Luke 5:17-26
2026-10-04|2 Corinthians 9:6-11|Luke 6:31-36
2026-10-05|Philippians 1:1-7|Luke 6:24-30
2026-10-06|Philippians 1:8-14|Luke 6:37-45
2026-10-07|Philippians 1:12-20|Luke 6:46-7:1
2026-10-08|Philippians 1:20-27|Luke 7:17-30
2026-10-09|Philippians 1:27-2:4|Luke 7:31-35
2026-10-10|1 Corinthians 15:58-16:3|Luke 5:27-32
2026-10-11|2 Corinthians 11:31-12:9|Luke 7:11-16
2026-10-12|Philippians 2:12-16|Luke 7:36-50
2026-10-13|Philippians 2:17-23|Luke 8:1-3
2026-10-14|Philippians 2:24-30|Luke 8:22-25
2026-10-15|Philippians 3:1-8|Luke 9:7-11
2026-10-16|Philippians 3:8-19|Luke 9:12-18
2026-10-17|2 Corinthians 1:8-11|Luke 6:1-10
2026-10-18|Galatians 1:11-19|Luke 8:5-15
2026-10-19|Philippians 4:10-23|Luke 9:18-22
2026-10-20|Colossians 1:1-2,7-11|Luke 9:23-27
2026-10-21|Colossians 1:18-23|Luke 9:44-50
2026-10-22|Colossians 1:24-29|Luke 9:49-56
2026-10-23|Colossians 2:1-7|Luke 10:1-15
2026-10-24|2 Corinthians 3:12-18|Luke 7:1-10
2026-10-25|Galatians 2:16-20|Luke 16:19-31
2026-10-26|Colossians 2:13-20|Luke 10:22-24
2026-10-27|Colossians 2:20-3:3|Luke 11:1-10
2026-10-28|Colossians 3:17-4:1|Luke 11:9-13
2026-10-29|Colossians 4:2-9|Luke 11:14-23
2026-10-30|Colossians 4:10-18|Luke 11:23-26
2026-10-31|2 Corinthians 5:1-10|Luke 8:16-21
2026-11-01|Galatians 6:11-18|Luke 8:26-39
2026-11-02|1 Thessalonians 1:1-5|Luke 11:29-33
2026-11-03|1 Thessalonians 1:6-10|Luke 11:34-41
2026-11-04|1 Thessalonians 2:1-8|Luke 11:42-46
2026-11-05|1 Thessalonians 2:9-14|Luke 11:47-12:1
2026-11-06|1 Thessalonians 2:14-19|Luke 12:2-12
2026-11-07|2 Corinthians 8:1-5|Luke 9:1-6
2026-11-08|Ephesians 2:4-10|Luke 8:41-56
2026-11-09|1 Thessalonians 2:20-3:8|Luke 12:13-15,22-31
2026-11-10|1 Thessalonians 3:9-13|Luke 12:42-48
2026-11-11|1 Thessalonians 4:1-12|Luke 12:48-59
2026-11-12|1 Thessalonians 5:1-8|Luke 13:1-9
2026-11-13|1 Thessalonians 5:9-13,24-28|Luke 13:31-35
2026-11-14|2 Corinthians 11:1-6|Luke 9:37-43
2026-11-15|Ephesians 2:14-22|Luke 10:25-37
2026-11-16|2 Thessalonians 1:1-10|Luke 14:12-15
2026-11-17|2 Thessalonians 1:10-2:2|Luke 14:25-35
2026-11-18|2 Thessalonians 2:1-12|Luke 15:1-10
2026-11-19|2 Thessalonians 2:13-3:5|Luke 16:1-9
2026-11-20|2 Thessalonians 3:6-18|Luke 16:15-18; 17:1-4
2026-11-21|Galatians 1:3-10|Luke 9:57-62
2026-11-22|Ephesians 4:1-6|Luke 12:16-21
2026-11-23|1 Timothy 1:1-7|Luke 17:20-25
2026-11-24|1 Timothy 1:8-14|Luke 17:26-37
2026-11-25|1 Timothy 1:18-20; 2:8-15|Luke 18:15-17,26-30
2026-11-26|1 Timothy 3:1-13|Luke 18:31-34
2026-11-27|1 Timothy 4:4-8,16|Luke 19:12-28
2026-11-28|Galatians 3:8-12|Luke 10:19-21
2026-11-29|Ephesians 5:9-19|Luke 13:10-17
2026-11-30|1 Timothy 5:1-10|Luke 19:37-44
2026-12-01|1 Timothy 5:11-21|Luke 19:45-48
2026-12-02|1 Timothy 5:22-6:11|Luke 20:1-8
2026-12-03|1 Timothy 6:17-21|Luke 20:9-18
2026-12-04|2 Timothy 1:1-2,8-18|Luke 20:19-26
2026-12-05|Galatians 5:22-6:2|Luke 12:32-40
2026-12-06|Ephesians 6:10-17|Luke 17:12-19
2026-12-07|2 Timothy 2:20-26|Luke 20:27-44
2026-12-08|2 Timothy 3:16-4:4|Luke 21:12-19
2026-12-09|2 Timothy 4:9-22|Luke 21:5-7,10-11,20-24
2026-12-10|Titus 1:5-2:1|Luke 21:28-33
2026-12-11|Titus 1:15-2:10|Luke 21:37-22:8
2026-12-12|Ephesians 1:16-23|Luke 13:18-29
2026-12-13|Colossians 3:4-11|Luke 14:16-24
2026-12-14|Hebrews 3:5-11,17-19|Mark 8:11-21
2026-12-15|Hebrews 4:1-13|Mark 8:22-26
2026-12-16|Hebrews 5:11-6:8|Mark 8:30-34
2026-12-17|Hebrews 7:1-6|Mark 9:10-16
2026-12-18|Hebrews 7:18-25|Mark 9:33-41
2026-12-19|Ephesians 2:11-13|Luke 14:1-11
2026-12-20|Hebrews 11:9-10,17-23,32-40|Matthew 1:1-25
2026-12-21|Hebrews 8:7-13|Mark 9:42-10:1
2026-12-22|Hebrews 9:8-10,15-23|Mark 10:2-12
2026-12-23|Hebrews 10:1-18|Mark 10:11-16
2026-12-24|Hebrews 10:35-11:7|Mark 10:17-27
2026-12-25|Hebrews 11:17-23,27-31|Mark 10:46-52
2026-12-26|Ephesians 5:1-8|Luke 13:18-29
2026-12-27|Colossians 3:4-11|Luke 14:16-24
2026-12-28|Hebrews 11:17-23,27-31|Mark 10:46-52
2026-12-29|Hebrews 12:25-26; 13:22-25|Mark 11:11-23
2026-12-30|James 1:1-18|Mark 11:22-26
2026-12-31|James 1:19-27|Mark 11:27-33
"""

OVERRIDES = {
    "2026-08-19": ("2 Peter 1:10-19", "Matthew 17:1-9", "transfiguration"),
    "2026-08-28": ("Philippians 2:5-11", "Luke 10:38-42; 11:27-28", "dormition"),
    "2026-09-11": ("Acts 13:25-33", "Mark 6:14-30", "beheading_forerunner"),
    "2026-09-20": ("Galatians 6:11-18", "John 3:13-17", "sunday_before_cross"),
    "2026-09-21": ("Philippians 2:5-11", "Luke 10:38-42; 11:27-28", "nativity_theotokos"),
    "2026-09-26": ("1 Corinthians 2:6-9", "Matthew 10:37-11:1", "saturday_before_cross"),
    "2026-09-27": ("1 Corinthians 1:18-24", "John 19:6-11,13-20,25-28,30-35", "exaltation_cross"),
    "2026-10-03": ("1 Corinthians 1:26-29", "John 8:21-30", "saturday_after_cross"),
    "2026-10-04": ("Galatians 2:16-20", "Mark 8:34-9:1", "sunday_after_cross"),
    "2026-10-09": ("1 John 4:12-19", "John 19:25-27; 21:24-25", "john_theologian"),
    "2026-10-14": ("Hebrews 9:1-7", "Luke 10:38-42; 11:27-28", "protection_theotokos"),
    "2026-12-04": ("Hebrews 9:1-7", "Luke 10:38-42; 11:27-28", "entry_theotokos"),
    "2026-12-13": ("Colossians 1:12-18", "Luke 14:16-24", "old_calendar_28th_sunday"),
    "2026-12-20": ("Colossians 3:4-11", "Luke 17:12-19", "old_calendar_29th_sunday"),
    "2026-12-25": ("Hebrews 11:8,11-16", "Luke 21:37-22:8", "old_calendar_december_12"),
    "2026-12-26": ("Ephesians 5:1-8", "Luke 13:18-29", "old_calendar_december_13"),
    "2026-12-27": ("Colossians 3:4-11", "Luke 14:16-24", "sunday_forefathers"),
}

FEASTS = {
    "2026-08-19": {"ar": "عيد تجلي ربنا وإلهنا ومخلصنا يسوع المسيح", "en": "The Holy Transfiguration of our Lord, God and Savior Jesus Christ", "el": "Ἡ Ἁγία Μεταμόρφωσις τοῦ Κυρίου καὶ Θεοῦ καὶ Σωτῆρος ἡμῶν Ἰησοῦ Χριστοῦ"},
    "2026-08-28": {"ar": "عيد رقاد سيدتنا والدة الإله الدائمة البتولية مريم", "en": "The Dormition of our Most Holy Lady the Theotokos and Ever-Virgin Mary", "el": "Ἡ Κοίμησις τῆς Ὑπεραγίας Δεσποίνης ἡμῶν Θεοτόκου καὶ Ἀειπαρθένου Μαρίας"},
    "2026-09-11": {"ar": "قطع رأس القديس السابق المجيد يوحنا المعمدان", "en": "The Beheading of the Holy and Glorious Prophet, Forerunner and Baptist John", "el": "Ἡ Ἀποτομὴ τῆς Τιμίας Κεφαλῆς τοῦ Ἁγίου Ἰωάννου τοῦ Προδρόμου"},
    "2026-09-20": {"ar": "الأحد قبل رفع الصليب الكريم", "en": "Sunday before the Exaltation of the Holy Cross", "el": "Κυριακὴ πρὸ τῆς Ὑψώσεως τοῦ Τιμίου Σταυροῦ"},
    "2026-09-21": {"ar": "ميلاد سيدتنا والدة الإله الدائمة البتولية مريم", "en": "The Nativity of our Most Holy Lady the Theotokos and Ever-Virgin Mary", "el": "Τὸ Γενέσιον τῆς Ὑπεραγίας Θεοτόκου"},
    "2026-09-26": {"ar": "السبت قبل رفع الصليب الكريم", "en": "Saturday before the Exaltation of the Holy Cross", "el": "Σάββατον πρὸ τῆς Ὑψώσεως τοῦ Τιμίου Σταυροῦ"},
    "2026-09-27": {"ar": "عيد رفع الصليب الكريم المحيي", "en": "The Universal Exaltation of the Precious and Life-Giving Cross", "el": "Ἡ Παγκόσμιος Ὕψωσις τοῦ Τιμίου καὶ Ζωοποιοῦ Σταυροῦ"},
    "2026-10-03": {"ar": "السبت بعد رفع الصليب الكريم", "en": "Saturday after the Exaltation of the Holy Cross", "el": "Σάββατον μετὰ τὴν Ὕψωσιν τοῦ Τιμίου Σταυροῦ"},
    "2026-10-04": {"ar": "الأحد بعد رفع الصليب الكريم", "en": "Sunday after the Exaltation of the Holy Cross", "el": "Κυριακὴ μετὰ τὴν Ὕψωσιν τοῦ Τιμίου Σταυροῦ"},
    "2026-10-09": {"ar": "انتقال القديس الرسول والإنجيلي يوحنا اللاهوتي", "en": "The Falling Asleep of the Holy Apostle and Evangelist John the Theologian", "el": "Ἡ Μετάστασις τοῦ Ἁγίου Ἀποστόλου καὶ Εὐαγγελιστοῦ Ἰωάννου τοῦ Θεολόγου"},
    "2026-10-14": {"ar": "حماية سيدتنا والدة الإله", "en": "The Protection of our Most Holy Lady the Theotokos", "el": "Ἡ Ἁγία Σκέπη τῆς Ὑπεραγίας Θεοτόκου"},
    "2026-12-04": {"ar": "دخول سيدتنا والدة الإله إلى الهيكل", "en": "The Entry of our Most Holy Lady the Theotokos into the Temple", "el": "Τὰ Εἰσόδια τῆς Ὑπεραγίας Θεοτόκου"},
    "2026-12-13": {"ar": "الأحد الثامن والعشرون بعد العنصرة", "en": "Twenty-eighth Sunday after Pentecost", "el": "Κυριακὴ ΚΗ΄ μετὰ τὴν Πεντηκοστήν"},
    "2026-12-20": {"ar": "الأحد التاسع والعشرون بعد العنصرة", "en": "Twenty-ninth Sunday after Pentecost", "el": "Κυριακὴ ΚΘ΄ μετὰ τὴν Πεντηκοστήν"},
    "2026-12-27": {"ar": "أحد الأجداد القديسين", "en": "Sunday of the Holy Forefathers", "el": "Κυριακὴ τῶν Ἁγίων Προπατόρων"},
}

BOOK_AR = {
    "Romans": "رومية", "Matthew": "متى", "Mark": "مرقس", "Luke": "لوقا", "John": "يوحنا", "Acts": "أعمال الرسل",
    "1 Corinthians": "كورنثوس الأولى", "2 Corinthians": "كورنثوس الثانية", "Galatians": "غلاطية", "Ephesians": "أفسس",
    "Philippians": "فيلبي", "Colossians": "كولوسي", "1 Thessalonians": "تسالونيكي الأولى", "2 Thessalonians": "تسالونيكي الثانية",
    "1 Timothy": "تيموثاوس الأولى", "2 Timothy": "تيموثاوس الثانية", "Titus": "تيطس", "Hebrews": "العبرانيين",
    "James": "يعقوب", "1 Peter": "بطرس الأولى", "2 Peter": "بطرس الثانية", "1 John": "يوحنا الأولى",
}
BOOK_EL = {
    "Romans": "Πρὸς Ῥωμαίους", "Matthew": "Κατὰ Ματθαῖον", "Mark": "Κατὰ Μᾶρκον", "Luke": "Κατὰ Λουκᾶν", "John": "Κατὰ Ἰωάννην", "Acts": "Πράξεις Ἀποστόλων",
    "1 Corinthians": "Πρὸς Κορινθίους Α΄", "2 Corinthians": "Πρὸς Κορινθίους Β΄", "Galatians": "Πρὸς Γαλάτας", "Ephesians": "Πρὸς Ἐφεσίους",
    "Philippians": "Πρὸς Φιλιππησίους", "Colossians": "Πρὸς Κολοσσαεῖς", "1 Thessalonians": "Πρὸς Θεσσαλονικεῖς Α΄", "2 Thessalonians": "Πρὸς Θεσσαλονικεῖς Β΄",
    "1 Timothy": "Πρὸς Τιμόθεον Α΄", "2 Timothy": "Πρὸς Τιμόθεον Β΄", "Titus": "Πρὸς Τίτον", "Hebrews": "Πρὸς Ἑβραίους",
    "James": "Ἰακώβου", "1 Peter": "Πέτρου Α΄", "2 Peter": "Πέτρου Β΄", "1 John": "Ἰωάννου Α΄",
}
EOTHINA = {
    1: "Matthew 28:16-20", 2: "Mark 16:1-8", 3: "Mark 16:9-20", 4: "Luke 24:1-12",
    5: "Luke 24:12-35", 6: "Luke 24:36-53", 7: "John 20:1-10", 8: "John 20:11-18",
    9: "John 20:19-31", 10: "John 21:1-14", 11: "John 21:15-25",
}
WEEKDAY = {
    0: {"ar": "الاثنين", "en": "Monday", "el": "Δευτέρα"}, 1: {"ar": "الثلاثاء", "en": "Tuesday", "el": "Τρίτη"},
    2: {"ar": "الأربعاء", "en": "Wednesday", "el": "Τετάρτη"}, 3: {"ar": "الخميس", "en": "Thursday", "el": "Πέμπτη"},
    4: {"ar": "الجمعة", "en": "Friday", "el": "Παρασκευή"}, 5: {"ar": "السبت", "en": "Saturday", "el": "Σάββατο"},
    6: {"ar": "الأحد", "en": "Sunday", "el": "Κυριακή"},
}


def parse_raw() -> dict[str, tuple[str, str]]:
    result: dict[str, tuple[str, str]] = {}
    for raw in RAW.strip().splitlines():
        iso, epistle, gospel = [part.strip() for part in raw.split("|", 2)]
        if iso in result:
            raise RuntimeError(f"duplicate date {iso}")
        result[iso] = (epistle, gospel)
    return result


def localized_reference(reference: str) -> dict[str, str]:
    ar, el = reference, reference
    for book in sorted(BOOK_AR, key=len, reverse=True):
        if reference.startswith(book + " "):
            suffix = reference[len(book):].strip()
            ar = f"{BOOK_AR[book]} {suffix}"
            el = f"{BOOK_EL[book]} {suffix}"
            break
    return {"ar": ar, "en": reference, "el": el}


def default_feast(day: date, sunday_number: int | None) -> dict[str, str]:
    if sunday_number is not None:
        return {
            "ar": f"الأحد {sunday_number} بعد العنصرة",
            "en": f"{sunday_number} Sunday after Pentecost",
            "el": f"Κυριακὴ {sunday_number} μετὰ τὴν Πεντηκοστήν",
        }
    return {
        "ar": "تذكار اليوم بحسب التقويم الكنسي القديم",
        "en": "Daily commemoration according to the old ecclesiastical calendar",
        "el": "Μνήμη τῆς ἡμέρας κατὰ τὸ παλαιὸ ἐκκλησιαστικὸ ἡμερολόγιο",
    }


def sunday_metadata(day: date) -> dict | None:
    if day.weekday() != 6:
        return None
    first = date(2026, 8, 2)
    if day < first:
        return None
    index = (day - first).days // 7
    number = 9 + index
    tone = ((8 - 1 + index) % 8) + 1
    eothinon = ((9 - 1 + index) % 11) + 1
    return {
        "sunday_after_pentecost": number,
        "resurrection_tone": tone,
        "eothinon": eothinon,
        "matins_gospel_reference": EOTHINA[eothinon],
    }


def source_urls(iso: str, override_id: str | None) -> dict:
    month = iso[:7]
    monthly = {
        "2026-07": "https://www.oca.org/readings/monthly/2026/07",
        "2026-08": "https://www.oca.org/readings/monthly/2026/08",
        "2026-09": "https://www.oca.org/readings/monthly/2026/09",
        "2026-10": "https://www.oca.org/readings/monthly/2026/10",
        "2026-11": "https://www.oca.org/readings/monthly/2026/11",
        "2026-12": "https://www.oca.org/readings/monthly/2026/12",
    }[month]
    return {
        "regular_cycle": monthly,
        "old_calendar_cross_check": f"https://orthocal.info/api/julian/{iso[:4]}/{int(iso[5:7])}/{int(iso[8:10])}/",
        "jordan_calendar": "https://orthodoxjo.tv/التقويم-الكنسّي-2026/",
        "override_id": override_id,
    }


def build() -> dict:
    regular = parse_raw()
    expected = (END - START).days + 1
    if len(regular) != expected:
        raise RuntimeError(f"expected {expected} raw dates, got {len(regular)}")
    days = []
    cursor = START
    while cursor <= END:
        iso = cursor.isoformat()
        if iso not in regular:
            raise RuntimeError(f"missing date {iso}")
        epistle, gospel = regular[iso]
        override_id = None
        if iso in OVERRIDES:
            epistle, gospel, override_id = OVERRIDES[iso]
        # Fail early on malformed canonical references.
        parse_reference(epistle)
        parse_reference(gospel)
        info = day_info(cursor)
        sunday = sunday_metadata(cursor)
        feast = copy.deepcopy(FEASTS.get(iso) or default_feast(cursor, sunday["sunday_after_pentecost"] if sunday else None))
        entry = {
            "date": iso,
            "date_iso": iso,
            "civil_weekday": copy.deepcopy(WEEKDAY[cursor.weekday()]),
            "julian_date": f"{info['julian_year']:04d}-{info['julian_month']:02d}-{info['julian_day']:02d}",
            "julian_label": {
                "ar": f"{info['julian_day']:02d}/{info['julian_month']:02d}/{info['julian_year']}",
                "en": f"{info['julian_day']:02d}/{info['julian_month']:02d}/{info['julian_year']} (Julian)",
                "el": f"{info['julian_day']:02d}/{info['julian_month']:02d}/{info['julian_year']} (Ἰουλιανὸν)",
            },
            "feast": feast,
            "status": copy.deepcopy(info["fasting"]["title"]),
            "fast": copy.deepcopy(info["fasting"]["title"]),
            "fasting": copy.deepcopy(info["fasting"]),
            "reading_references": {
                "epistle": {"canonical_reference": parse_reference(epistle)[0], "display_reference": epistle, "reference": localized_reference(epistle)},
                "gospel": {"canonical_reference": parse_reference(gospel)[0], "display_reference": gospel, "reference": localized_reference(gospel)},
            },
            "is_sunday": sunday is not None,
            "sources": source_urls(iso, override_id),
            "publication_status": "PINNED_REFERENCE_READY_TEXT_FROM_NATIVE_CORPORA",
        }
        if sunday:
            entry["sunday"] = copy.deepcopy(sunday)
            matins = sunday["matins_gospel_reference"]
            entry["reading_references"]["matins_gospel"] = {
                "canonical_reference": parse_reference(matins)[0],
                "display_reference": matins,
                "reference": localized_reference(matins),
            }
        days.append(entry)
        cursor += timedelta(days=1)
    return {
        "schema_version": 1,
        "calendar": "jerusalem_jordan_julian_old_calendar",
        "civil_range": {"start": START.isoformat(), "end": END.isoformat(), "day_count": len(days)},
        "sunday_count": sum(1 for item in days if item["is_sunday"]),
        "policy": {
            "reference_first": True,
            "same_language_text_only": True,
            "machine_translation": False,
            "cross_language_fallback": False,
            "shared_texts_not_duplicated_per_day": True,
        },
        "days": days,
    }


def write_outputs(payload: dict) -> None:
    OUT_CANONICAL.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    asset = copy.deepcopy(payload)
    # Keep source URLs and long repeated fasting guidance in the canonical evidence
    # file. Android receives only the compact fields needed by the calendar UI.
    for item in asset["days"]:
        fasting = item.get("fasting") if isinstance(item.get("fasting"), dict) else {}
        item["fasting"] = {
            "code": fasting.get("code"),
            "title": copy.deepcopy(fasting.get("title") or item.get("status") or {}),
            "detail": copy.deepcopy(fasting.get("detail") or {}),
            "is_fast": bool(fasting.get("is_fast")),
            "display_icons": copy.deepcopy(fasting.get("display_icons") or []),
        }
        item["sources"] = {"status": "PINNED_CANONICAL_EVIDENCE", "registry": "canonical/jordan_2026_h2_lectionary.json"}
    OUT_ASSET.parent.mkdir(parents=True, exist_ok=True)
    OUT_ASSET.write_text(json.dumps(asset, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")

    records = json.loads(DAILY_RECORDS.read_text(encoding="utf-8"))
    dates = records.setdefault("dates", {})
    by_date = {item["date_iso"]: item for item in payload["days"]}
    for iso, item in by_date.items():
        sources = item["sources"]
        dates[iso] = {
            "source_id": "official_orthodox_regular_cycle_with_jordan_old_calendar_overrides",
            "official": True,
            "calendar_compatibility": "JORDAN_JERUSALEM_OLD_CALENDAR",
            "url": sources["regular_cycle"],
            "cross_check_url": sources["old_calendar_cross_check"],
            "jordan_calendar_url": sources["jordan_calendar"],
            "override_id": sources.get("override_id"),
            "epistle_reference": item["reading_references"]["epistle"]["display_reference"],
            "gospel_reference": item["reading_references"]["gospel"]["display_reference"],
            "matins_gospel_reference": (item["reading_references"].get("matins_gospel") or {}).get("display_reference"),
            "epistle_canonical_reference": item["reading_references"]["epistle"]["canonical_reference"],
            "gospel_canonical_reference": item["reading_references"]["gospel"]["canonical_reference"],
            "reference_status": "PINNED_EXACT_REFERENCE",
            "text_policy": "EXACT_SAME_LANGUAGE_NATIVE_CORPUS_ONLY",
        }
    records["coverage"] = {
        "start": START.isoformat(), "end": END.isoformat(), "reference_complete_days": len(payload["days"]),
        "sundays_with_matins_reference": payload["sunday_count"],
    }
    DAILY_RECORDS.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    payload = build()
    write_outputs(payload)
    print(f"H2_LECTIONARY_OK days={len(payload['days'])} sundays={payload['sunday_count']} asset={OUT_ASSET.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
