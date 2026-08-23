# ملاحظات بحث R64 — 23 آب/أغسطس 2026

## Orthodox Jordan

الرابط: https://orthodoxjordan.org/%D8%B5%D9%84%D8%A7%D8%A9-%D8%A7%D9%84%D9%8A%D9%88%D9%85/

الصفحة الرسمية تعرض حقولًا يومية مستقلة للتاريخ الغربي والشرقي، و«تذكار»، و«آية اليوم». في المحتوى الظاهر كانت الصفحة تعرض 7 كانون الثاني/يناير 2026 غربيًا الموافق 25 كانون الأول 2025 شرقيًا، مع اسم عيد ميلاد المسيح وذكرى المجوس والرعاة. هذا يثبت أن المصدر المحلي يملك نمطًا يوميًا غنيًا بالتذكارات، لكنه لا يثبت وحده جدولًا كاملًا 2026–2050 قابلًا للتنزيل.

## GOARCH

الرابط: https://www.goarch.org/chapel/calendar

تعذر فتح الصفحة في جلسة المتصفح بسبب Cloudflare («Attention Required!»)، لذلك لم تُستخدم لإثبات أسماء أو تواريخ في هذه الجولة. نتائج البحث أشارت إلى صفحة تقويم يومي، لكنها لا تُعامل كدليل حتى تُقرأ الصفحة أو ملف رسمي قابل للاستخراج.

## قرار أولي

لا يجوز إزالة تحذير R64 بمجرد تسمية الأيام العامة بأسماء مخترعة. يلزم إما corpus يومي أصلي متعدد اللغات للقدس/الأردن، أو ترقية محدودة للأيام التي يثبتها مصدر صريح مع إبقاء بقية الأيام في حالة generic/pending.

## Serbian Orthodox Diocese of Eastern America

الرابط: https://www.easterndiocese.org/daily1

الصفحة تعرض يومًا كاملًا مع التاريخين القديم والجديد، اسم الأحد، الصوم، قائمة تذكارات متعددة، وقراءات الكتاب المقدس. في الصفحة المفتوحة بتاريخ 23 آب/أغسطس 2026 ظهر صوم رقاد والدة الإله «Food with Oil» مع عدة تذكارات وقراءات. هذا مصدر مقارن قوي لبنية تقويم يومي، لكنه ليس مصدر القدس/الأردن ولا يكفي وحده لترقية السجلات إلى سياسة محلية فلسطينية/أردنية.

## Orthodox Jordan homepage

الرابط: https://orthodoxjordan.org/

الصفحة الرئيسية تعرض نفس بطاقة «صلاة اليوم» ومحتوى التذكار، وتؤكد وجود خدمة يومية محلية. لم يظهر في النص المستخرج رابط أرشيف تاريخي أو تنزيل روزنامة 2026–2050. الصفحة الحالية تعرض محتوى يوم 7 كانون الثاني/يناير 2026، ما يدل على أن الخدمة قد تكون snapshot أو endpoint داخليًا لا يتبع تاريخ جهاز التصفح.

## فحص واجهة Orthodox Jordan

استخراج الروابط من DOM أظهر أن روابط «الصلاة» و«صلاة اليوم» تعود كلها إلى الصفحة نفسها، ولم يظهر رابط تقويم أو أرشيف بتاريخ. وفحص موارد الصفحة لم يُظهر طلب API أو JSON أو Ajax أو GraphQL متعلقًا بالتقويم. لذلك لا يوجد في الواجهة العامة المفتوحة مسار واضح لاسترجاع 9131 تذكارًا تاريخيًا.

## فحص WordPress REST في Orthodox Jordan

الروابط المفحوصة:

- https://orthodoxjordan.org/wp-json/
- https://orthodoxjordan.org/wp-json/wp/v2/types
- https://orthodoxjordan.org/wp-json/wp/v2/pages?slug=%D8%B5%D9%84%D8%A7%D8%A9-%D8%A7%D9%84%D9%8A%D9%88%D9%85
- https://orthodoxjordan.org/wp-json/wp/v2/posts?search=%D8%AA%D8%B0%D9%83%D8%A7%D8%B1&per_page=20&orderby=date&order=desc

REST يعلن أنواع WordPress التقليدية (pages/posts) ولا يعلن مورد تقويم يومي مستقلًا. صفحة «صلاة اليوم» ذات المعرّف 41230 تحتوي في محتواها تاريخًا وتذكارًا وصورًا/عناصر عرض، وكانت في الاستجابة تعرض 7 كانون الثاني 2026 غربيًا الموافق 25 كانون الأول شرقيًا. البحث في posts يعرض أخبارًا ومقالات مناسبات منشورة في تواريخ متفرقة، وليس جدولًا يوميًا مكتملًا 2026–2050. كما أن الصفحة التي يحمّلها الموقع عبر REST تتضمن محتوى أخبار وتحميلًا تدريجيًا، لا corpus سنكسار منظمًا لكل يوم.

الاستنتاج: يمكن استخدام صفحات Orthodox Jordan لإثبات مناسبات محلية محددة عندما يكون التاريخ والتذكار صريحين، لكن لا يجوز تحويل عناوين الأخبار أو الصفحة الحالية إلى أسماء يومية لجميع 9131 يومًا. تحذير R64 حقيقي من حيث اكتمال corpus، وليس عطلًا في بناء APK.

## صفحة تقويم أخوية القبر المقدس

فتحت صفحة بطريركية القدس عن «توزيع التقويم السنوي لعام 2010». الصفحة أظهرت رابطًا باسم «تقويم أخوية القبر المقدس» ضمن روابط الموقع، لكن محاولة النقر الآلي تعثرت بسبب انتهاء فهرس DOM، ثم ظهرت جلسة المتصفح على about:blank عند إعادة الالتقاط. لم يُستخدم الرابط كدليل ولم تُستخرج منه بيانات، لتجنب نسبة محتوى غير مُتحقق إلى البطريركية.

## اكتشاف تقويم أخوية القبر المقدس 2026

صفحة بطريركية القدس عن تقويم 2010 تذكر أن التقاويم السنوية كانت تُوزّع عبر الموقع الرسمي، وتعرض رابطًا حاليًا مباشرًا داخل DOM:

https://ar.jerusalem-patriarchate.info/wp-content/uploads/2026/02/arabic_2026.pdf

النص الظاهر في الصفحة يقول إن التقويم السنوي يُوزع عبر الموقع الرسمي لبطريركية الروم الأرثوذكسية الأورشليمية، وأن الحصول على تقاويم السنوات السابقة كان يتم من الموقع. هذا الرابط الرسمي لعام 2026 مرشح قوي لمصدر عربي سنوي، لكنه لا يثبت بعد وجود نسختين إنجليزية ويونانية أو قابلية استقراء 2027–2050؛ يجب تنزيله وقراءة صفحاته والتحقق من تواريخ وأسماءه قبل دمجه.

## مكتبة وسائط بطريركية القدس

فحص WordPress media REST أظهر ملفاتًا كثيرة باسم 2026، ومع البحث عن calendar ظهرت نسختان رسميتان لعام 2024: `2024_GREEK_CALENDAR_OF_PATRIARCHATE-2024__R.pdf` و`Russian_CALENDAR-OF-PATRIARCHATE_2024_R.pdf`. لم تظهر نسخة إنجليزية/يونانية 2026 في نتيجة البحث، بينما رابط الصفحة المباشر لعام 2026 هو `arabic_2026.pdf`. لذلك لا تُفترض تغطية ثلاثية اللغات من PDF العربي وحده.

## نتيجة فحص نسخ اللغات لعام 2026

فحص مكتبة الوسائط وطلب أسماء الملفات المحتملة وفق نمط تقويم 2024 أكد أن النسخة المباشرة المتاحة لعام 2026 هي `arabic_2026.pdf` فقط. أسماء English/Greek/Russian المحتملة لعام 2026 أعادت 404. لذلك يمكن استخدام PDF العربي الرسمي لإثبات أسماء عربية لعام 2026 بعد parser موثوق، لكن لا يمكن ترقيته وحده إلى سجل ثلاثي اللغات أو إلى corpus رسمي 2027–2050.

الـPDF العربي الرسمي من إنتاج Adobe InDesign، حجمه نحو 3.05 MB، وعدد صفحاته 212، ويحتوي قسم جداول شهرية مع تذكارات يومية عربية واضحة ابتداءً من صفحة النص 62 تقريبًا، إضافة إلى صفحات أخرى كالسيرة والصلوات. يلزم استخراج صفحات الجداول بدقة وعدم اعتبار كل نص PDF جدولًا.

## تقويم OCA الإنجليزي للمقارنة

إعلان OCA الرسمي: https://www.oca.org/news/headline-news/orthodox-church-in-americas-2026-desk-calendar-now-available

الرابط الرسمي لملف PDF ذي الصفحة الواحدة: https://www.oca.org/files/PDF/NEWS/2025/2026-OCA-Desk-Calendar-single.pdf

الإعلان يصفه كتقويم مكتب OCA لعام 2026 ويذكر أن فيه «تذكارات ليتورجية رئيسية» وتواريخ تاريخية، لا أنه corpus كامل لأسماء كل قديسي كل يوم. لذلك لا يصلح وحده لإثبات تغطية يومية كاملة أو سياسة القدس/الأردن، حتى لو استُخدم كمرجع إنجليزي مقارن.

## اختبار دمج الوثيقة المباشرة

شغّل اختبار حصاد مصغر محليًا بإعداد 40 صفحة، وظهر سجل الوثيقة الرسمية `jerusalem_patriarchate_calendar_2026_ar` مع `content_type=application/pdf` و`categories=[calendar, library]`، واللغة `ar`، والسلطة `Jerusalem Patriarchate official annual calendar`. هذا يثبت أن الوثيقة لا تعتمد على ظهورها في sitemap، مع بقاء ترقية التذكارات المسماة ممنوعة حتى اكتمال الأدلة الأصلية باللغات الثلاث.

## مصادر عربية جديدة جرى فحصها

1. [فهرس القديسين العربي — بطريركية أنطاكية](https://www.antiochpatriarchate.org/ar/category/115/): موقع بطريركي رسمي يعرض صفحات قديسين عربية مع تاريخ بصيغة شهر-يوم، مثل 12-29 و12-27 و12-20. الصفحة الحالية تعرض Pagination وعددًا محدودًا من النتائج وليست بعدُ corpus سنويًا مستخرجًا؛ كما أن مرجعيتها أنطاكية وليست القدس/الأردن، لذلك تُستخدم للمقارنة أو لسد أسماء مشتركة بعد مطابقة مستقلة، لا لتغيير قانون القدس تلقائيًا.

2. [تقويم كنيسة القديس أنطونيوس الكبير — زحلة](https://stantoniosthegreat.com/calendar): صفحة عربية لرعية أرثوذكسية تعرض «السنكسار اليومي» وأسماء قديسين يومية في الواجهة، لكنها صفحة ديناميكية حالية، والنتيجة الظاهرة تتضمن أسماء وأرشيفًا قديمًا مع تاريخ 2020. هي مصدر عربي رعوي مقارن، ولا تثبت وحدها corpus القدس/الأردن 2026–2050.

## مصادر إنجليزية جرى فحصها

1. [GOARCH Chapel Calendar](https://www.goarch.org/chapel/calendar): صفحة تقويم يومي أرثوذكسي، لكن جلسة التصفح واجهت CAPTCHA؛ لم تُبنَ نتيجة تفصيلية منها في هذه الجولة. صفحة [The Planner](https://www.goarch.org/chapel/planner) تصف وجود قراءات وأيام صوم وقديسين، لكن لا يكفي ذلك وحده لإثبات corpus القدس/الأردن القديم.

2. [Holy Trinity Monastery Jordanville — Daily Orthodox Calendar](https://jordanville.org/daily-orthodox-calendar/): صفحة إنجليزية يومية تُظهر التاريخين، مثل Sunday August 23, 2026 / August 10, 2026، وتعرض أسماء قديسين يومية وروابط سير القديسين وقراءات. هي مصدر إنجليزي أصلي من دير أرثوذكسي ومفيد جدًا للمقارنة واستخراج أسماء ثابتة، لكنها ليست بطريركية القدس/الأردن، وبعض العناصر مصنفة Greek أو روسية، لذلك لا تُرقّى تلقائيًا إلى المرجع المحلي النهائي.

## مصادر يونانية جرى فحصها

1. [Ορθόδοξος Συναξαριστής — saint.gr](https://www.saint.gr/calendar.aspx): يعرض تقويمًا يونانيًا يوميًا مع أسماء قديسين وصفحات أشهر متعددة. الصفحة نفسها تصرّح بأن الموقع خاص/شخصي ومعلوماته لأغراض إعلامية وأن على الزائر التحقق من المعلومات؛ لذلك هو corpus يوناني أصلي مفيد للمقارنة، لكنه ليس مصدرًا بطريركيًا نهائيًا.

2. [البوابة اليونانية الرسمية لبطريركية القدس](https://jerusalem-patriarchate.info/): الصفحة تعرض رابطًا مباشرًا بعنوان «Ἁγιοταφιτικόν Ἡμερολόγιον» إلى ملف `GREEK_CALENDAR_OF_PATRIARCHATE_2025_R.pdf`. هذا يثبت وجود تقويم سنوي يوناني أصلي من بطريركية القدس، وهو أقوى من saint.gr. يلزم تنزيله وفحصه ومقارنته مع PDF العربي قبل ترقية أي اسم، كما يلزم العثور على English native corpus أو اعتماد صريح لنطاقه.

## مصدر القدس اليوناني ووصف التقويم الرسمي

[صفحة الصحافة الكنسية لبطريركية القدس](https://en.jerusalem-patriarchate.info/administrative-structure/ecclesiastical-press/) تصف «Hagiotaphite Calendar» بأنه يُنشر مرة كل سنة ويشمل الـKyriakodromion وكل أعياد السنة والملخص التاريخي والتواريخ المهمة وبنية كنيسة القدس. الصفحة تذكر أن جمع المادة اليونانية يتم بواسطة Archimandrite Christodoulos، وأن للترجمة العربية منسقة مستقلة، لكنها لا تثبت وجود نسخة إنجليزية أصلية كاملة للتذكارات اليومية. هذا يؤكد أن أفضل corpus يوناني محلي هو التقويم الهاغيوتافيتي الرسمي، وأن العربية تحتاج مطابقة النسخة العربية الأصلية لا ترجمة آلية.

[التقويم الكامل لـHoly Trinity Russian Orthodox Church](https://www.holytrinityorthodox.com/htc/orthodox-calendar/) يعرض يوميًا التاريخ الغربي/اليولياني، التذكارات الإنجليزية، رموز الصوم، وروابط السير والقراءات. الصفحة تصرّح بأنها تابعة لكنيسة روسية أرثوذكسية في بالتيمور، لذا هي مصدر إنجليزي أصلي واسع ومفيد للمقارنة واستخراج الثابت، لكنها ليست مرجعًا محليًا لبطريركية القدس أو الأردن.

## قابلية الاستخراج اليونانية والإنجليزية

تم تنزيل وفحص [تقويم القدس اليوناني الرسمي لعام 2025](https://jerusalem-patriarchate.info/wp-content/uploads/2025/03/GREEK_CALENDAR_OF_PATRIARCHATE_2025_R.pdf). الملف بعنوان `AGIOTAFITIKO HMEROLOGIO` وعدد صفحاته 166، ويحتوي قسم `ΚΥΡΙΑΚΟΔΡΟΜΙΟΝ` وجداول شهرية يونانية يومية؛ العينة تتضمن أعمدة اليوم القديم والجديد وأسماء تذكارات يونانية أصلية. هذا مصدر محلي قوي، لكنه لعام 2025، ويجب توفير/العثور على ملف 2026 وما بعده أو اعتماد طبقة ثابتة موثقة بحذر.

تم تحليل loader لتقويم [Holy Trinity](https://www.holytrinityorthodox.com/htc/orthodox-calendar/). الصفحة تقبل معاملات `year`, `today`, و`month`، وتعرض تاريخًا غربيًا/يوليانيًا وأسماء قديسين يومية إنجليزية. هذا يجعل بناء حصاد إنجليزي يومي قابلًا لإعادة الإنتاج ممكنًا، لكنه يظل مصدر كنيسة روسية أرثوذكسية في الولايات المتحدة لا مصدر القدس/الأردن؛ لذلك يلزم وسمه `comparative_english_source` وعدم استعماله وحده لإثبات الاختصاص المحلي.

## فحص مكتبة الوسائط اليونانية الرسمية

فحص REST العام للبوابة اليونانية `jerusalem-patriarchate.info` أعاد ملفات التقويم التالية عند البحث عن calendar:

- `2024_GREEK_CALENDAR_OF_PATRIARCHATE-2024__R.pdf` بنسختين/مسارين في 2024.
- `Russian_CALENDAR-OF-PATRIARCHATE_2024_R.pdf`.

لم يُظهر البحث عن `2026` ملف PDF يونانيًا، بل أظهر صورًا لأخبار وأحداث عام 2026. البوابة الرئيسية تعرض رابط `GREEK_CALENDAR_OF_PATRIARCHATE_2025_R.pdf`، وقد تم تنزيله وفحصه وهو تقويم يوناني رسمي كامل يحتوي جداول شهرية. النتيجة الحالية: يوجد مصدر يوناني محلي قوي، لكن لا توجد بعد سلسلة عامة واضحة للسنوات 2026–2050.


## Greek 2024 leap-PDF visual spot checks (2026-08-23)

The official Jerusalem Greek 2024 PDF at `https://jerusalem-patriarchate.info/wp-content/uploads/2024/02/2024_GREEK_CALENDAR_OF_PATRIARCHATE-2024__R.pdf` is 163 pages. Its embedded text layer uses a custom/broken glyph map for many pages, so plain `pdftotext` is not a trustworthy source of names. Greek OCR language data was installed and daily pages were rendered for research only.

Visual review of rendered page 62 confirms the monthly table is legible and contains native Greek rows for 26 March (old-calendar date 13 March) and 25 March (old-calendar date 12 March). Visual review of rendered page 67 is a different May 2024 reference page, not the daily May table; it confirms the document's Greek local calendar context but does not promote any OCR string. The Greek 2024 leap corpus therefore remains `REQUIRES_VISUAL_REVIEW`; no OCR-derived Greek 29 February name is promoted or merged into the app.

The 2025 Greek parser corpus remains a separate local source with 365/365 old-calendar slots. Two extracted names contain Latin look-alike characters (`03-26` and `05-25`) and require visual review before any strict all-slot promotion. Typicon symbols were removed as non-name table markers only; no name text was translated or rewritten.


## Native evidence promotion boundary after contextual-row audit (2026-08-23)

The canonical evidence layer now distinguishes a daily row from a reusable fixed `MM-DD` commemoration. In the Jerusalem Greek 2025 calendar, 365 rows were parsed; 308 are eligible for fixed-slot enrichment, 56 contain year-specific Sunday/Pascha/Pentecost/other movable context and are not copied across years, and 2 remain visual-review records because of Latin look-alike glyphs. The Arabic 2024/2026 rows remain pending RTL visual review. The complete English Holy Trinity corpus remains comparative-only and contributes zero local Jerusalem/Jordan slots.

The builder therefore enriches only the Greek lane on ordinary days whose local source row is explicitly verified and fixed-slot eligible. Major fixed and movable occasions remain primary and unchanged. Arabic and English continue to use their own existing same-language baseline labels; no cross-language fallback occurs. The strict three-language named gate remains closed (`0` verified local Arabic+English+Greek slots).


## Follow-up search for local English annual calendar (2026-08-23)

The official Jerusalem Patriarchate English home page was opened and reviewed. It exposes the English site, news, patriarchate structure, holy shrines, and communication sections, but the page does not expose a clearly published annual English calendar PDF or a daily English commemoration table. The English timetable page found in search is a historical service timetable rather than a full annual daily named-commemoration corpus. Therefore the English lane remains unresolved locally; no Arabic/Greek text is copied into it, and the Holy Trinity English endpoint remains comparative only.


The English site's internal search for `calendar` was also checked across the first two result pages. Results are historical news, feast reports, Holy Week messages, and service/event articles; the page explicitly does not expose a specific annual/daily saints calendar or a verifiable English daily schedule. These pages can support individual major-event cross-checks, but cannot safely supply a 366-slot named English corpus.


The official Orthodox Jordan `/en/` landing page was opened. Although some navigation labels are English, the daily content block's `Memorial` text is Arabic and the page does not expose an English annual calendar or a 366-slot native-English commemorations feed. This is evidence that the English route cannot be harvested as an independent English lane without cross-language copying, so it remains unresolved for the strict local gate.


The HTML review of `https://orthodoxjordan.org/en/` confirms that the English route is not an independent English commemorations source: its daily `Date`, `Memorial`, and verse content are Arabic, and key navigation links resolve to Arabic URLs. It can remain a local Arabic source, but it cannot legally or linguistically fill the English lane.


## Verified Greek leap-day evidence (2026-08-23)

The official Jerusalem Patriarchate media library on the English site exposes the Greek 2024 leap calendar PDF at `https://en.jerusalem-patriarchate.info/wp-content/uploads/2024/02/2024_GREEK_CALENDAR_OF_PATRIARCHATE-2024__R.pdf`. The PDF was downloaded and page 60 was visually reviewed. The daily February table clearly shows old-calendar day 29 with the original Greek text `Κασσιανοῦ ὁσίου`. This single leap-slot record is now included as `jerusalem_hagiotaphite_calendar_el_2024`, page 60, with `fixed_slot_eligible=true`; the PDF SHA-256 is `648ba69f46120faae3e6fd3b669ea5d09c99d140ac1f3d457a5ceb322fcb6270`.

This closes the Greek evidence gap for 02-29 only. It does not provide a local English calendar and does not change the strict three-language R64 gate.


## Full English-site media scan (2026-08-23)

The official Jerusalem Patriarchate English WordPress media library was scanned through 101 of 103 date-filtered pages covering 2024–2026. The PDF results found were: the Greek 2024 Hagiotaphite calendar (`https://en.jerusalem-patriarchate.info/wp-content/uploads/2024/02/2024_GREEK_CALENDAR_OF_PATRIARCHATE-2024__R.pdf`), a Russian 2024 calendar (`https://en.jerusalem-patriarchate.info/wp-content/uploads/2024/02/Russian_CALENDAR-OF-PATRIARCHATE_2024_R.pdf`), a national celebration PDF, Greek/Arabic patriarchal letters, and 2026 Easter/Three Hierarchs documents. No annual native-English saints calendar PDF appeared. The Greek PDF was used only as Greek evidence; the Russian document was not used for any of the app's required Arabic/English/Greek lanes.


## Orthodox Jordan Calendar page discovery (2026-08-23)

The WordPress REST API exposes an official page at `https://orthodoxjordan.org/calendar/` titled `Calendar - Orthodox Jordan`. The page renders an `Agenda` interface with a date chooser and subscription control, but the first browser load did not expose a static annual named-commemoration table; its content is dynamic. The page must be inspected through its HTML/scripts or calendar API before any records can be treated as native evidence. No English lane has been promoted from it.


The official Orthodox Jordan Calendar page (WordPress page ID 71427) is published but has empty page content. Its All-in-One Event Calendar Agenda/month routes render the calendar shell with `ai1ec-no-results`, and both the Arabic and English ICS export URLs returned a VCALENDAR with zero VEVENT entries. Thus this official page is not currently a usable annual named-commemoration feed in either language.
