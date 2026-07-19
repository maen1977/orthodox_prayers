# تطبيق إصلاح R8

انسخ ملفات الحزمة فوق جذر المشروع مع الاستبدال، ثم نفّذ:

```powershell
python scripts/run_quality_gate.py --strict-native-lanes
python scripts/update.py --date "2026-07-20" --unsigned

git add -A
git commit -m "Fix overlapping integrity envelopes in daily JSON schema"
git push
```

الإصلاح يستبدل `oneOf` بـ`anyOf` في عقد `integrity` لأن مرشح الإصدار الصحيح قد يحمل الغلافين المتوافقين معًا.
