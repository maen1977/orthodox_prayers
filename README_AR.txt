إصلاح Build 5.0.21 — ملف واحد فقط

المشكلة:
كان Workflow يشغّل python -m pytest، لكن requirements-dev.txt لا يحتوي pytest.

التطبيق:
انسخ requirements-dev.txt إلى جذر مستودع orthodox_prayers على فرع main واستبدل الملف الموجود.
ثم شغّل Actions > Build من جديد.

لا حاجة لتشغيل Rolling Week Update، ولا لتغيير رقم الإصدار.
