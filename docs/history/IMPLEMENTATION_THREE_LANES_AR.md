# تقرير تنفيذ التحديثات الثلاثة — 4.1.0

## البنية

يبقى في GitHub ملفا Workflow فقط: `Build` و`Update`.
داخل `Update` توجد ثلاث خطوات مستقلة ظاهرة بالاسم:

- Update Arabic lane — Amman, Jerusalem, Antioch
- Update Greek lane — official Greek Orthodox sources
- Update English lane — GOARCH, Jerusalem, Antioch

ينتج كل مسار ملفًا مستقلًا موقّعًا:

- `data/daily/YYYY-MM-DD/ar.json`
- `data/daily/YYYY-MM-DD/el.json`
- `data/daily/YYYY-MM-DD/en.json`

وتوجد نسخة حالية لكل لغة تحت `data/daily/current/`.

## التقويم والمصادر

تقويم بطريركية القدس القديم هو سلطة التاريخ والمناسبة ومراجع القراءات. النصوص لا تترجم بين اللغات.

العربية: مطرانية عمان، ثم القدس، ثم أنطاكية.
اليونانية: Apostoliki Diakonia، ثم المصادر اليونانية الرسمية في GOARCH، ثم القدس باليونانية.
الإنجليزية: GOARCH، ثم القدس بالإنجليزية، ثم أنطاكية بالإنجليزية.

OCN وPemptousia وAghioritiki Estia وRomfea مسجلة كمراجع تعليمية أو إعلامية، وليست سلطة تلقائية لنص الرسالة والإنجيل.

## التطبيق

أزيل شرط رفض ملف اليوم كاملًا عند نقص خدمة اختيارية أو لغة أخرى. الهاتف ما زال يتحقق من التوقيع والتاريخ والمخطط وعدم الترجمة الآلية وبصمة أي نص ديني موجود، ثم يعرض الأقسام الموثقة المتاحة.

## الفحص

نجحت 64 من 64 اختبارات Python، ونجحت بوابة الجودة كاملة. تعذر تشغيل Gradle محليًا لأن بيئة الفحص لا تستطيع الوصول إلى `services.gradle.org`؛ سيجري GitHub Actions تجميع Android الفعلي.
