# Orthodox Prayers 5.0.7 R11 — إصلاح تطبيق التعديل في جذر المستودع

## التشخيص المؤكد

سجل GitHub الأخير أظهر `orthodox_integrity.py:1680` يستدعي المزامنة من دون `require_complete=False`، و`update_liturgical_data.py:1098` يرمي الخطأ مباشرة. هذه الأسطر تطابق R9، بينما R10 يحتوي الاستدعاء المؤجل بالفعل. لذلك لم تكن ملفات R10 الفعلية مستبدلة في جذر الفرع المستخدم بواسطة GitHub Actions.

## إصلاح R11

- حزمة التعديل بلا مجلد غلاف؛ المسارات تبدأ مباشرة بـ `scripts/` و`tests/` و`app/`.
- مزامنة الأحد القادم تتعرف تلقائيًا على المرحلة المبكرة عندما يمرر المستدعي `source`، حتى لو كان المستدعي من R9 ولا يمرر `require_complete=False`.
- الاستدعاء النهائي الذي لا يمرر `source` يبقى صارمًا ويمنع النشر عند نقص أي مرجع.
- `scripts/update.py` يتحقق من مستوى الملفات قبل بدء التحديث ويطبع `PIPELINE_PATCH_OK level=R11`.
- `scripts/verify_r11_patch.py` يثبت أن الملفات الأربعة الصحيحة موجودة في جذر المستودع.

## التطبيق

فك حزمة التعديل مباشرة داخل جذر المستودع ووافق على استبدال الملفات، ثم شغّل:

```powershell
python scripts/verify_r11_patch.py
python -m unittest discover -s tests -p "test_*.py"
python scripts/update.py --date "2026-07-20" --unsigned
```

يجب أن يظهر قبل التحديث:

```text
PATCH_R11_OK version=5.0.7 level=R11
PIPELINE_PATCH_OK level=R11
```
