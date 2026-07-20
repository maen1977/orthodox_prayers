# تطبيق تحديث 5.0.9 R13

1. فك ملف `OrthodoxPrayers-5.0.9-r13-rootless-changes-only.zip` داخل جذر المستودع بجانب `gradlew` و`app` و`scripts`.
2. وافق على استبدال الملفات.
3. شغّل:

```powershell
python scripts/verify_r13_patch.py
python -m unittest discover -s tests -p "test_*.py"
python scripts/run_quality_gate.py --strict-native-lanes
python scripts/update.py --date "2026-07-20" --unsigned
```

يجب أن يظهر في البداية:

```text
PATCH_R13_OK version=5.0.9 level=R13
PIPELINE_PATCH_OK level=R13
```

وفي نهاية التحديث الجديد:

```text
Fasting guidance validated: permitted/forbidden foods, duration, novice notes, and documented abstinence are consistent
```

ثم ارفع الملفات:

```powershell
git add -A
git commit -m "Add clear Jordan fasting guidance and documented abstinence rules"
git push
```

ملاحظة: الصوم الانقطاعي لا يحمل ساعات تلقائية. تُقبل الساعات فقط من ملف override يومي موثق وبصيغة `HH:MM`.
