# تطبيق R18

1. ارفع محتويات الحزمة إلى جذر المستودع مع الاستبدال.
2. تأكد من بقاء سر المفتاح الخاص داخل GitHub Actions فقط.
3. شغّل `python scripts/verify_r18_patch.py`.
4. شغّل `python -m unittest discover -s tests -p "test_*.py"`.
5. ادمج التغييرات في `main` ثم شغّل Workflow التحديث يدويًا لأول مرة.
6. راقب ملف `data/sources/health/current.json` وفرع `verified-data` قبل إصدار التطبيق.

لا تنسخ المفتاح الخاص إلى المشروع، ولا تعدّل ملفات اليوم الموقعة يدويًا.
