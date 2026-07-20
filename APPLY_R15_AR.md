# تطبيق R15

فك حزمة التعديل الجذرية داخل جذر المستودع بجانب `gradlew` و`app` و`scripts`، ثم وافق على استبدال الملفات.

شغّل:

```powershell
python scripts/verify_r15_patch.py
python -m unittest discover -s tests -p "test_*.py"
./gradlew --no-daemon testDebugUnitTest --stacktrace
```

يجب أن تظهر: `PATCH_R15_OK version=5.0.11 level=R15`.
