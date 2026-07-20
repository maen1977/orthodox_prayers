# تطبيق R16

1. فك حزمة التعديل داخل جذر المستودع بجانب `gradlew` و`app` و`scripts`.
2. وافق على استبدال الملفات.
3. شغّل:

```powershell
python scripts/verify_r16_patch.py
python -m unittest discover -s tests -p "test_*.py"
python scripts/run_quality_gate.py --strict-native-lanes
./gradlew --no-daemon testDebugUnitTest --stacktrace
```

يجب أن يظهر:

```text
PATCH_R16_OK version=5.0.12 level=R16
```

وعند التحديث اليومي:

```text
PIPELINE_PATCH_OK level=R16
```
