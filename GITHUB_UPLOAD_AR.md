# رفع Orthodox Prayers 4.2.0 إلى GitHub

المستودع المستهدف:

```text
maen1977/orthodox_prayers
```

استخدم ملف المصدر النظيف الناتج من:

```bash
python scripts/create_clean_source_archive.py ../OrthodoxPrayers-4.2.0-enhanced-source.zip
```

لا ترفع مجلد `.git` من نسخة قديمة، ولا ملفات الكاش أو المفاتيح الخاصة أو Android Keystore.

## أهم ما تضيفه النسخة

- التقويم الشهري والتاريخ اليولياني بجانب الغريغوري.
- تذكيرات الصلاة والقراءات والأعياد والصيام والتذكير الشخصي.
- سجل القراءة والتثبيت ومجموعات المفضلة وإعادة ترتيبها.
- إعدادات الخط وتباعد الأسطر والتمرير التلقائي.
- إدارة اللغات النشطة وتقارير النقص الإنجليزية واليونانية.
- WorkManager 2.11.2 وفحص احتياطي كل 12 ساعة.
- أدوات دمج نصوص أصلية مصرّح بها دون ترجمة أو خلط بين اللغات.

## رسالة Commit مقترحة

```text
Release Orthodox Prayers 4.2.0 with calendar, reminders, and reading tools
```

## بعد الرفع

1. افتح تبويب Actions وشغّل `Build`.
2. عند نجاح بوابة المصدر، راقب خطوات Android Unit Tests وLint Debug وDebug APK.
3. شغّل `Update` يدويًا بوضع `update` لنشر بيانات تاريخ اليوم إلى `verified-data`.
4. تأكد أن Environment باسم `production-data-signing` يحتوي `DATA_SIGNING_PRIVATE_KEY_B64`.
5. لا تنشئ إصدار Production ما دامت `validate_release_readiness.py` محجوبة بسبب نقص الإنجليزية واليونانية والنصوص الكتابية.

## فحص محلي

```bash
python -m pytest -q
python scripts/run_quality_gate.py --strict-native-lanes
python scripts/scan_repository_secrets.py
```
