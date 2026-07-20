# إصلاح توطين البروكيمنن — 5.0.8 R12

## سبب الخطأ

كان `prepare_native_corpus_readings()` يعيد تهيئة `prokeimenon` و`epistle` و`gospel` معًا قبل ملء نصوص الكتاب المقدس. لكن مرحلة `fill_daily_from_native_corpora.py` تعيد ملء الرسالة والإنجيل فقط، لأن البروكيمنن نص طقسي يومي مصدره `canonical/daily_propers.json` أو سجل الألحان المثبت.

لذلك كان مرجع البروكيمنن يُمسح في العربية والإنجليزية واليونانية، ثم يفشل:

```text
readings[0].reference.ar is empty
readings[0].reference.en is empty
readings[0].reference.el is empty
```

## الإصلاح

- الحفاظ على البروكيمنن كاملًا أثناء إعداد مسارات الـCorpus.
- إعادة تهيئة الرسالة والإنجيل فقط.
- إبقاء مرجع البروكيمنن ونصه ومصدره وبصماته في اللغات الثلاث.
- تشغيل `validate_daily_ui_localizations.py` داخل `update.py` قبل إعلان نجاح التحديث.
- إضافة اختبار يعيد إنتاج يوم الاثنين 20 تموز 2026.
- رفع الإصدار إلى `5.0.8` ورقم البناء إلى `50008`.

## التحقق

```powershell
python scripts/verify_r12_patch.py
python -m unittest discover -s tests -p "test_*.py"
python scripts/update.py --date "2026-07-20" --unsigned
```

يجب أن يظهر:

```text
PATCH_R12_OK version=5.0.8 level=R12
PIPELINE_PATCH_OK level=R12
Daily UI localization validated for Arabic, English, and Greek
DAILY_UPDATE_UNSIGNED_OK date=2026-07-20 mode=full
```
