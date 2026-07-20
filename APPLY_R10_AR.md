# تطبيق إصلاح 5.0.6 R10

1. انسخ محتويات حزمة التعديل إلى جذر المشروع مع الاستبدال.
2. لا تحذف ملفات البيانات الموقعة الحالية يدويًا.
3. شغّل:

```powershell
python scripts/run_quality_gate.py --strict-native-lanes
python scripts/update.py --date "2026-07-20" --unsigned
python scripts/validate_liturgical_schedule.py data/calendar/today.json
```

4. بعد النجاح:

```powershell
git add -A
git commit -m "Fix two-phase next Sunday reference synchronization"
git push
```

يجب ألا يظهر خطأ `next Sunday epistle reference is missing after native-corpus resolution` في المرحلة المبكرة، بينما يبقى الفحص النهائي صارمًا بعد ملء النصوص.
