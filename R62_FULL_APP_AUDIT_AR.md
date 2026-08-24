# تدقيق R62 الكامل لتطبيق Orthodox Prayers

تاريخ التدقيق: **2026-08-13**  
النسخة الأساسية: **5.6.4 — إكمال النصوص الطقسية المصرّح بها R66**

> هذا التقرير يفرّق بين سلامة البرنامج تقنيًا وبين اكتمال المحتوى الكنسي. نجاح Release Gate لا يعني تلقائيًا وجود نص كامل أو قراءة موثقة لكل يوم.

## النتائج

### ✅ PASS — Home date + old calendar
9131 civil days are precomputed for 2026-01-01..2050-12-31 with julian_date; the home card intentionally omits the daily commemoration line.

### ✅ FIXED R62 — Prayer of the Day by local time
Home now selects morning_prayer 04:00-11:59, thanksgiving 12:00-17:29, evening_prayer 17:30-21:29, small_compline otherwise, using Asia/Amman time.

### ✅ PASS (بنطاق موثق) — Fasting state and food-rule type
4824/9131 days are marked fasting; codes include {'wine_oil': 864, 'strict': 3246, 'dairy_allowed': 175, 'fish_allowed': 536, 'wine_only': 3}. Exact abstinence clock times are intentionally not invented.
**الإجراء:** Keep fail-closed behavior for abstinence start/end unless an official dated source states it.

### ❌ INCOMPLETE — Daily commemorations through 2050
9131/9131 days have source-backed or explicit named commemoration records; 2151 days contain explicit occasion entries; 0 days use generic date-based commemoration wording. The remaining incompleteness is the local three-language gate, not an invented saint-name fallback.
**الإجراء:** Keep the English leap-day record and any non-local Greek slots explicitly marked; do not AI-generate or cross-language-translate saint names.

### ❌ INCOMPLETE — Daily Epistle/Gospel coverage through 2050
Pinned references: epistle 182/9131, gospel 182/9131, matins gospel 22/9131.
**الإجراء:** Build/verify a full Jerusalem-compatible regular lectionary and fixed-feast override corpus before claiming 2050 completeness.

### ✅ PASS — 2026-08-10 reading spot check
Internal refs are 2 Corinthians 2:4-15 and Matthew 23:13-22; this date was cross-checked against the official OCA daily lectionary as a lower-priority regular-cycle authority.

### ✅ داخل التطبيق / بلا بطاقات صلاة خارجية — Daily prayer library
Arabic embedded core: morning 5 segments; evening 4; small compline 14; the complete pinned Arabic before/after-meal sequence and pre/post-Communion texts open inside the reader. 4 official Jordan references remain catalog evidence and are not rendered as external prayer cards.
**الإجراء:** Import any additional native text only after exact-text and redistribution evidence are recorded.

### ✅ PASS R66 — نص أصلي مصرّح به — Arabic Orthros / Matins
Arabic Orthros is DISPLAYABLE_COMPLETE_AUTHORIZED_NATIVE_SOURCE with 159 source segments / 16610 chars; its authorized exact native edition is displayed and searchable without machine translation.

### ✅ PASS — Arabic Vespers
Arabic Vespers is packaged as a complete exact native edition with 44 segments / 9768 chars.

### ✅ PASS — Arabic Small Compline
Arabic Small Compline is packaged as a complete exact native edition with 14 segments / 4500 chars.

### ✅ PASS (طبقة قارئ) — Divine Liturgy
Arabic Divine Liturgy is COMPLETE_NATIVE_SOURCE_COMPILATION with 198 source segments. Optional quiet believer prayers remain a reader overlay, not part of the canonical-text hash.

### ✅ PASS R66 — نص أصلي مصرّح به — Saint Basil Liturgy
Complete authorized native editions are displayable in Arabic (206 segments), English (455), and Greek (228); the smart selector attaches the Basil template on appointed days without a wrong-rite fallback.

### ✅ PASS R66 — نص أصلي مصرّح به — Presanctified Liturgy
Complete authorized native editions are displayable in Arabic (3302 segments), English (590), and Greek (915); the smart selector attaches the Presanctified template on appointed days without a wrong-rite fallback.

### ⚠️ التغطية مختلفة حسب اللغة — Church-service section
هذا الكتالوج منفصل عن نطاق الخدمات الأساسية الخمس عشرة. بعد التوليد الحالي: العربية `10/10` نصوص كاملة offline، والإنجليزية `11/11` نصوص كاملة offline بعد تصحيح حدود Hapgood، واليونانية `0/11` نصوص كاملة و`11` بطاقات روابط مصدر فقط لأن مصدر Ioannina المسجل أعاد HTTP 500. الرابط فقط لا يُسمّى خدمة كاملة، ولا يوجد cross-language fallback.
**الإجراء:** لا تُسمَّ بطاقات الكتالوج/المرجع خدمات كاملة إلا بعد استيراد نص أصلي كامل واجتياز البوابة. بقيت الفجوة اليونانية صريحة، كما أن اكتمال 15/15 لا يشمل هذا الكتالوج ولا يشهد بمراجعة كنسية بشرية.

### ⚠️ PARTIAL + روابط الدليل الرسمي الكامل — Church directory
Packaged directory has 57 entries grouped as {'jordan': 42, 'palestine': 9, 'jerusalem': 6}: the Jordan list and West Bank list are expanded from the official directories, while Jerusalem/Holy Land currently contains selected major entries plus direct links to the complete official Patriarchate directories. No clergy phone numbers are republished.
**الإجراء:** Do not claim every Holy Land church/monastery is individually packaged until the official Jerusalem and outside-Jerusalem lists are fully normalized.

### ✅ FIXED R62 — Official live resources
3 verified official portal/radio links are packaged; unverified direct/stale links were removed from the visible Live section.

### ✅ PASS / Gate — Arabic / English / Greek isolation
All newly added directory metadata contains independent ar/en/el values; existing localization gate remains authoritative.

## الخلاصة
R62 لا يدّعي أن كل المحتوى الديني مكتمل. الإصلاحات الآمنة التي لا تحتاج اختراع نص ديني نُفذت، أما الفجوات التي تتطلب نصًا كنسيًا عربيًا أصليًا أو مرجع قراءات كاملًا فبقيت معلّمة صراحةً حتى يتم استيراد مصدر مخوّل ومتحقق.
