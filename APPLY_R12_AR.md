# تطبيق R12

1. فك حزمة `rootless-changes-only` داخل جذر المستودع بجانب `gradlew` و`scripts` و`app`.
2. وافق على استبدال الملفات.
3. شغّل:

```powershell
python scripts/verify_r12_patch.py
python -m unittest discover -s tests -p "test_*.py"
python scripts/update.py --date "2026-07-20" --unsigned
```

لا تكمل إذا لم يظهر `PATCH_R12_OK` و`PIPELINE_PATCH_OK level=R12`.
