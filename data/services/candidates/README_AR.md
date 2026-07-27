# مرشحات النصوص الليتورجية الأصلية

هذا المجلد لا يدخل في بيانات التطبيق ولا يجوز نسخ أي ملف منه إلى حزم العرض مباشرة.

المسار الإلزامي:

1. استيراد كل لغة من مصدرها الأصلي المسجل بواسطة `scripts/import_native_liturgy_service.py`.
2. رفض أي استخراج يحوي أحرف استبدال أو نسبة كتابة غير صحيحة أو نصًا أقصر من عقد الخدمة.
3. مراجعة كل فقرة مقابل صفحات المصدر وتعبئة بيانات الموافقة الكنسية داخل المرشح.
4. تشغيل `scripts/promote_native_liturgy_service.py` على اللغات الثلاث معًا.
5. مراجعة تغييرات البصمات وتشغيل بوابة الجودة والتوقيع الرسمي.

لا ترجمة آلية، لا تصحيح بالذكاء الاصطناعي، ولا نشر لمرشح منفرد.

## المرحلة الثامنة: حزمة المراجعة فقرة بفقرة

بعد إنشاء مرشح آمن بواسطة `import_native_liturgy_service.py`:

```bash
python scripts/build_native_liturgy_review_packet.py candidate.json --output review-packet.json
```

يقارن المراجع الكنسي كل فقرة بالمصدر الرسمي، ويغيّر قرار كل فقرة يدويًا من `PENDING` إلى `APPROVED`، ثم يملأ اسم المراجع والتاريخ والنص الحرفي التالي:

`I compared every segment with the registered official source.`

بعد ذلك فقط يمكن تسجيل المراجعة داخل مرشح جديد، من دون ترقية أو نشر:

```bash
python scripts/apply_native_liturgy_review_packet.py candidate.json review-packet.json --output reviewed-candidate.json
```

تبقى الترقية ثلاثية اللغة منفصلة، ولا تُنفذ إلا بعد نجاح مرشحات العربية والإنجليزية واليونانية معًا.

لحفظ صفحة DCS اليونانية–الإنجليزية محليًا وتقسيمها من دون ترجمة:

```bash
python scripts/import_dcs_bilingual_source.py service-gr-en.html --output-dir source-lanes
```

ولبناء Android عند توفر ملف Gradle الرسمي محليًا:

```bash
python scripts/build_android_with_local_gradle.py --gradle-zip /path/to/gradle-8.13-bin.zip
```
