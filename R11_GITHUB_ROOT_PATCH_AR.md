# إصلاح R11 — التأكد من استبدال ملفات GitHub الفعلية

## السبب

سجل GitHub أظهر أرقام أسطر مطابقة لإصدار R9، لا R10. هذا يعني أن ملفات التعديل فُكّت داخل مجلد فرعي أو لم تُستبدل الملفات الموجودة في جذر المستودع.

## التطبيق

فك ملف `changes-only-rootless.zip` مباشرة داخل جذر المستودع، بحيث تصبح الملفات مثل:

- `scripts/update.py`
- `scripts/orthodox_integrity.py`
- `scripts/update_liturgical_data.py`

ولا تصبح داخل مجلد إضافي باسم الإصدار. وافق على الاستبدال.

ثم شغّل:

```powershell
python scripts/verify_r11_patch.py
python scripts/update.py --date "2026-07-20" --unsigned
```

يجب أن يكون أول سطر:

```text
PATCH_R11_OK version=5.0.7 level=R11
PIPELINE_PATCH_OK level=R11
```

إذا لم يظهر السطران، فلا تشغّل التحديث؛ الفرع لا يزال يستخدم ملفات قديمة.
