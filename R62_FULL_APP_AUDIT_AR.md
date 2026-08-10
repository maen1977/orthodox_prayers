# تدقيق R62 الكامل لتطبيق Orthodox Prayers

تاريخ التدقيق: **2026-08-10**  
النسخة الأساسية: **5.6.4 R61**

> هذا التقرير يفرّق بين سلامة البرنامج تقنيًا وبين اكتمال المحتوى الكنسي. نجاح Release Gate لا يعني تلقائيًا وجود نص كامل أو قراءة موثقة لكل يوم.

## النتائج

### ✅ PASS — Home date + old calendar
9131 civil days are precomputed for 2026-01-01..2050-12-31 with julian_date.

### ✅ FIXED R62 — Prayer of the Day by local time
Home now selects morning_prayer 04:00-11:59, thanksgiving 12:00-17:29, evening_prayer 17:30-21:29, small_compline otherwise, using Asia/Amman time.

### ✅ PASS (بنطاق موثق) — Fasting state and food-rule type
4817/9131 days are marked fasting; codes include {'wine_oil': 861, 'strict': 3246, 'dairy_allowed': 175, 'fish_allowed': 535}. Exact abstinence clock times are intentionally not invented.
**الإجراء:** Keep fail-closed behavior for abstinence start/end unless an official dated source states it.

### ❌ INCOMPLETE — Daily commemorations through 2050
2144 days contain explicit occasion entries; 6987 days still use generic date-based commemoration wording.
**الإجراء:** Import a verified annual Jerusalem/Jordan native commemoration corpus; do not AI-generate saint names.

### ❌ INCOMPLETE — Daily Epistle/Gospel coverage through 2050
Pinned references: epistle 182/9131, gospel 182/9131, matins gospel 22/9131.
**الإجراء:** Build/verify a full Jerusalem-compatible regular lectionary and fixed-feast override corpus before claiming 2050 completeness.

### ✅ PASS — 2026-08-10 reading spot check
Internal refs are 2 Corinthians 2:4-15 and Matthew 23:13-22; this date was cross-checked against the official OCA daily lectionary as a lower-priority regular-cycle authority.

### ⚠️ PARTIAL + روابط رسمية — Daily prayer library
Arabic embedded core: morning 5 segments; evening 4; small compline 15; before/after food present; pre/post Communion are exact recovered native editions. 4 additional official Jordan daily-prayer links are exposed without repackaging their text.
**الإجراء:** Import additional native texts only when redistribution permission is recorded; until then keep official-link-only behavior.

### ❌ INCOMPLETE — Fail closed — Arabic Orthros / Matins
Raw Arabic source is BLOCKED_ARABIC_OCR_REIMPORT_REQUIRED; the reader uses a safe core and does not display broken OCR.
**الإجراء:** Requires a clean authorized Arabic native edition; do not AI-correct OCR.

### ⚠️ PARTIAL — Arabic Vespers
Arabic library has 45 segments / 9787 chars from the historical Arabic source, but no recovered exact-native-lane audit marks it complete.
**الإجراء:** Replace/verify against a clean authorized Jerusalem/Jordan Arabic edition.

### ⚠️ PARTIAL — Arabic Small Compline
Arabic library has 15 segments / 4511 chars; English and Greek have substantially larger exact native imports.
**الإجراء:** Replace/verify against a clean authorized Arabic native edition.

### ✅ PASS (طبقة قارئ) — Divine Liturgy
Arabic Divine Liturgy is COMPLETE_NATIVE_SOURCE_COMPILATION with 198 source segments. Optional quiet believer prayers remain a reader overlay, not part of the canonical-text hash.

### ⚠️ البطاقات موجودة / النصوص الكاملة ناقصة — Church-service section
13 fallback service cards exist in each language; pending full authorized rite text in source packs: ar=13, en=13, el=13. Arabic build manifest has 10/10 registered web sources whose redistribution is not confirmed; R62 blocks bundling them and exposes official links instead.
**الإجراء:** Do not label catalog/reference cards as complete services until native full texts are imported and gated. Public-domain/CC-BY lanes may still generate full text at build time where their registered rights permit it.

### ⚠️ PARTIAL + روابط الدليل الرسمي الكامل — Church directory
Packaged directory has 57 entries grouped as {'jordan': 42, 'palestine': 9, 'jerusalem': 6}: the Jordan list and West Bank list are expanded from the official directories, while Jerusalem/Holy Land currently contains selected major entries plus direct links to the complete official Patriarchate directories. No clergy phone numbers are republished.
**الإجراء:** Do not claim every Holy Land church/monastery is individually packaged until the official Jerusalem and outside-Jerusalem lists are fully normalized.

### ✅ FIXED R62 — Official live resources
3 verified official portal/radio links are packaged; unverified direct/stale links were removed from the visible Live section.

### ✅ PASS / Gate — Arabic / English / Greek isolation
All newly added directory metadata contains independent ar/en/el values; existing localization gate remains authoritative.

## الخلاصة
R62 لا يدّعي أن كل المحتوى الديني مكتمل. الإصلاحات الآمنة التي لا تحتاج اختراع نص ديني نُفذت، أما الفجوات التي تتطلب نصًا كنسيًا عربيًا أصليًا أو مرجع قراءات كاملًا فبقيت معلّمة صراحةً حتى يتم استيراد مصدر مخوّل ومتحقق.
