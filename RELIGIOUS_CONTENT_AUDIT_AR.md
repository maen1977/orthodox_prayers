# تقرير التدقيق الديني والتقني للمحتوى

**تاريخ التقرير:** 2026-08-24

**حالة المستودع عند التوليد:** `72a26c02b68f84e4ba4018c2485acd2880961155`

**الكاتب:** **Manus AI**

## النتيجة الصادقة

أُجري هذا التدقيق على نطاق معلن، وليس على عبارة مطلقة مثل «كل الصلوات الموجودة في جميع مواقع الكنيسة». لا توجد قائمة عالمية نهائية واحدة لكل الكتب والخدمات الأرثوذكسية، كما أن اختلاف الطبعات والاختصاصات الرعائية يمنع تحويل جرد تقني إلى اعتماد كنسي. لذلك يميّز التقرير بين **نطاق الخدمات الأساسية الخمس عشرة**، و**المتغيرات اليومية**، و**كتالوج الخدمات الكنسية المنفصل**.

> **لا يثبت هذا التقرير اعتمادًا أو مراجعة بشرية من بطريركية أو أبرشية.** يثبت فقط ما أمكن التحقق منه تقنيًا من الملفات والمصادر المسجلة، مع إبقاء الفجوات صريحة.

## ملخص التغطية

| النطاق | العربية | English | Ελληνικά | المعنى |
| --- | --- | --- | --- | --- |
| الخدمات الأساسية المعلنة | 15/15 | 15/15 | 15/15 | نطاق ضيق: مكاتب يومية/قداسات/مناولة |
| الخدمات الكنسية المنفصلة | 10/10 كامل | 11/11 كامل | 10/11 كامل | الرابط فقط لا يُسمّى نصًا كاملاً |
| متغيرات القداس اليومية | 3/6 | 3/6 | 3/6 | الأسماء المسجلة في service_coverage |

نجحت فحوص فصل اللغات وسلامة lane metadata: كل lane يحتوي نصًا بلغته المسجلة، ولم يُستخدم cross-language fallback أو machine translation. كما احتفظ كل lane بمعرّف مصدره الأصلي وhash المسجل. نجاح validator الخاص بـ15 خدمة يعني النطاق المحدد في manifest فقط، ولا يعني أن كل الخدمات السرائرية أو كل القراءات اليومية موجودة.

## القداس الإلهي وصلوات الكاهن السرية

تحتوي حزم القداس الثلاث على أقسام وأدوار للقارئ والكاهن والشعب والشماس. كما أن metadata التسليم تسجل المقاطع ذات `delivery=silent`؛ وفيها مقاطع للكاهن ومقاطع هادئة للشعب بحسب الطبعة. هذه علامة تقنية على وجود النصوص الموسومة، وليست حكمًا كنسيًا بأن كل اختلاف طباعي بين الأبرشيات قد حُسم.

| اللغة | قداس يوحنا | قداس باسيليوس | السابق تقديسه | صامت إجمالًا | صامت للكاهن |
| --- | --- | --- | --- | --- | --- |
| العربية | 198 | 206 | 3302 | 17 | 12 |
| English | 328 | 455 | 590 | 5 | 4 |
| Ελληνικά | 324 | 228 | 915 | 5 | 4 |

جرى استعمال صفحة [قداس القديس يوحنا الذهبي الفم الرسمية في GOARCH][5] كقائمة تحقق للأقسام الظاهرة ولفئات صلوات الكاهن بصوت منخفض، ومنها صلوات الأنطايفونا والدخول والثلاث تقديسات والإنجيل والمؤمنين والشيروبيكون والأنفورا. لم تُترجم هذه الصفحة إلى العربية أو اليونانية ولم تُستخدم لاستبدال النصين الأصليين؛ بل استُخدمت كقائمة بنيوية، بينما احتفظ كل نص بمصدره الأصلي المسجل. أما المقارنة النصية الكاملة لكل segment فبقيت غير مكتملة كما هو موضح أدناه.

## المتغيرات اليومية

النص الثابت للقداس موجود في lanes الثلاثة، لكن **المتغيرات اليومية ليست مكتملة** وفق سياسة المشروع: verified `3/6` فقط. العناصر المفقودة المسجلة حرفيًا هي: **[طروبارية اليوم]، [القنداق]، [آية المناولة]**. لذلك لا يصح تسمية قداس اليوم المتغير كاملًا بنسبة 100% قبل إدخال هذه النصوص من مصادر أصلية في كل لغة، ولا يجوز اختراعها أو ترجمتها آليًا.

## الخدمات الكنسية المنفصلة

| اللغة | نصوص كاملة offline | بطاقات رابط فقط | حالة المصدر |
| --- | --- | --- | --- |
| العربية | 10 | 0 | مصادر عربية مسجلة؛ لا fallback في الحزمة |
| English | 11 | 0 | Hapgood public-domain؛ حدود 8 خدمات صُححت |
| Ελληνικά | 10 | 1 | ست صفحات GLT native وأربع خدمات من صفحات UOI اليونانية المرخّصة؛ خدمة واحدة بقيت رابطًا |

في العربية أصبحت الخدمات الكاملة offline هي: **church_baptism، church_confession، church_betrothal، church_marriage، church_crowns_removal، church_unction، church_funeral، church_memorial، church_trisagion، church_great_water**. وفي الإنجليزية أصبحت: **church_baptism، church_confession، church_betrothal، church_marriage، church_crowns_removal، church_unction، church_funeral، church_memorial، church_home_blessing، church_priesthood، church_great_water**. أما اليونانية فأصبحت فيها **10** خدمات كاملة offline من مصادر يونانية أصلية مسجلة: ست صفحات GLT وأربع خدمات من صفحات محددة في PDF UOI المصوّر المرخّص، وهي: **church_baptism، church_confession، church_betrothal، church_marriage، church_crowns_removal، church_unction، church_funeral، church_trisagion، church_priesthood، church_great_water**. وبقيت الخدمات التالية روابط مصدر فقط لأن حدود نص يوناني مستقل لها لم تُثبت: **church_memorial**. هذا قرار fail-closed مقصود؛ لم أستعمل نسخة Scribd أو نسخة تجارية غير متحقق من حقوقها، ولم أضع ترجمة بدل النص اليوناني.

الإصلاح الإنجليزي الذي أُدخل لا يغير النصوص الدينية ولا يعيد كتابتها؛ إنه يصحح حدود القص في كتاب Hapgood ذي المصدر العام، اعتمادًا على العناوين المطبوعة الفعلية. شمل ذلك الاعتراف والخطبة والزواج وإزالة الأكاليل والتذكار وبركة البيت والرسامة والماء العظيم. وتبقى بركة البيت خدمة قصيرة في المصدر نفسه، لذلك سُمح لها بحد طول صريح لا بملء النص اصطناعيًا.

## المصادر والحقوق ومنهج المقارنة

المصادر العربية واليونانية والإنجليزية محفوظة كـ provenance مستقل لكل lane، مع منع الترجمة الآلية ومنع خلط اللغات. هذا يثبت استقلال المسارات ومصدرها المسجل، ولا يحوّل الفحص البنيوي إلى مراجعة نصية كاملة أو اعتماد كنسي. فهرس GOARCH الرسمي يميز بين الليتورجيا والماتين والصلوات والخدمات السرائرية والجنازات، بينما يذكر فهرس [St Andrew's Greek Orthodox Theological College][7] أن نصوصًا مثل القداس والزواج والمعمودية والجنازات مرتبطة بكتب وطبعات محددة؛ وهذا سبب إضافي لعدم ادعاء وجود «كل شيء» من دون تحديد الطبعة والاختصاص.

المصدر الإنجليزي للخدمات الكنسية هو [Service Book of the Holy Orthodox-Catholic Apostolic Church (Hapgood) في Internet Archive][8]، وقد استُخدمت عناوينه المطبوعة لمراجعة حدود الاستخراج، لا لإثبات أن هذه الطبعة هي الصيغة الرعائية الوحيدة في القدس أو أنطاكية. المصادر اليونانية الجديدة لست خدمات هي صفحات GLT اليونانية التابعة لنطاق GOARCH، وقد سُجلت في manifest مع تصريح المستخدم بإعادة التوزيع: [المعمودية][10] [الزواج والخطبة][11] [مسحة المرضى][12] [الجنازة][13] [التريصاجيون للراقدين][14]. كما أُضيفت أربعة اقتباسات يونانية محددة الصفحات من ملف Eucharologion المصوّر في University of Ioannina، المسجل CC-BY، مع provenance وOCR build-time وعدم ترجمة. بقيت خدمة التذكار مستقلةً كرابط فقط لأن الملف لا يثبت لها حدًا منفصلًا صالحًا للإدخال.

## ما لم أعتبره مكتملًا

| الفحص | الحالة | السبب |
| --- | --- | --- |
| مقارنة نص-لنص كاملة لكل segment مع snapshot source موحد | غير مكتملة | `validate_source_comparison.py` لم يعمل لأن `data/sources/comparison/current.json` غير موجود؛ لا أدعي اكتمال هذه المقارنة. |
| الخدمات الكنسية اليونانية offline | جزئية 10/11 | ست خدمات أُدرجت من صفحات GLT وأربع من صفحات UOI اليونانية المرخّصة؛ خدمة التذكار بقيت رابطًا لعدم ثبوت حدود مستقلة لها. |
| متغيرات قداس اليوم | جزئية 3/6 | الطروبارية والقنداق وآية المناولة غير مثبتة في الملف الحالي. |
| اعتماد كنسي بشري | غير معتمد | manifest يثبت `ecclesiastical_approval_certified=false`. |

لم أعدّل الواجهات أو منطق الاختيار أو التقويم. التغيير الدائم في هذه الجولة يشمل دعم parser لصفحات GLT القديمة، وإضافة أربع خدمات يونانية native من صفحات UOI محددة مع provenance وحقوق OCR build-time، وتحديث claims نطاق الاكتمال، مع بقاء مسارات العربية والإنجليزية دون استبدال.

## المراجع

[1]: https://developer.android.com/google/play/app-updates "Android Developers — How app updates work"
[2]: https://developer.android.com/build/configure-app-module "Android Developers — Configure the app module"
[3]: https://developer.android.com/studio/publish/versioning "Android Developers — Version your app"
[4]: https://developer.android.com/guide/playcore/in-app-updates "Android Developers — In-app updates"
[5]: https://www.goarch.org/-/the-divine-liturgy-of-saint-john-chrysostom "GOARCH — The Divine Liturgy of Saint John Chrysostom"
[6]: https://www.goarch.org/chapel/texts "GOARCH — Liturgical Texts of the Orthodox Church"
[7]: https://www.sagotc.edu.au/liturgical-texts "St Andrew's Greek Orthodox Theological College — Liturgical Texts"
[8]: https://archive.org/details/servicebookofhol0000orth_i9n7 "Hapgood Service Book — Internet Archive"
[9]: https://olympias.lib.uoi.gr/jspui/bitstream/123456789/28576/1/BK.%CE%9666.pdf "University of Ioannina — registered Greek Eucharologion source"
[10]: https://glt.goarch.org/texts/Euch/Baptism.html "GOARCH GLT — Greek Baptism and Chrismation"
[11]: https://glt.goarch.org/texts/Euch/Wedding.html "GOARCH GLT — Greek Betrothal and Marriage"
[12]: https://glt.goarch.org/texts/Euch/Uncion.html "GOARCH GLT — Greek Holy Unction"
[13]: https://glt.goarch.org/texts/Euch/Funeral.html "GOARCH GLT — Greek Funeral Service"
[14]: https://glt.goarch.org/texts/Euch/Trisagion.html "GOARCH GLT — Greek Trisagion for the Departed"
