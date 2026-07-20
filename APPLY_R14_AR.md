# تطبيق تحديث 5.0.10 R14

1. فك ملف `OrthodoxPrayers-5.0.10-r14-rootless-changes-only.zip` داخل جذر المستودع، بجانب `gradlew` و`app` و`scripts` و`tests`.
2. وافق على استبدال الملفات.
3. شغّل:

```powershell
python scripts/verify_r14_patch.py
python -m unittest discover -s tests -p "test_*.py"
python scripts/run_quality_gate.py --strict-native-lanes
```

يجب أن يظهر:

```text
PATCH_R14_OK version=5.0.10 level=R14
```

وعند تشغيل التحديث اليومي يجب أن يبدأ السجل بـ:

```text
PIPELINE_PATCH_OK level=R14
```

ثم ارفع التغييرات:

```powershell
git add -A
git commit -m "Simplify home and show explicit fasting food rules"
git push
```
