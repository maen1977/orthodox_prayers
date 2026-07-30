# إصلاح بوابة الجودة R20 — الإصدار 5.0.22

يعالج هذا الإصلاح الأعطال الثلاثة الظاهرة في GitHub Actions:

1. حذف المرشح القديم غير الموقّع `data/rolling-week/candidates/2026-07-28`.
2. إعادة حقل `status` في تقرير تغطية الخدمات.
3. اعتبار الخدمات التي لا تحتاج متغيرات يومية `not_applicable` بدل ناقصة.

## التطبيق على المستودع الحالي

1. فك الحزمة في جذر المستودع مع الاستبدال.
2. نفّذ أحد الأمرين:

```powershell
powershell -ExecutionPolicy Bypass -File .\APPLY_R20_QUALITY_GATE_HOTFIX.ps1
```

أو:

```bash
python APPLY_R20_QUALITY_GATE_HOTFIX.py
```

3. تأكد أن Git يسجل حذف المجلد القديم، ثم ارفع جميع التغييرات.
4. شغّل:

```bash
python scripts/run_quality_gate.py --strict-native-lanes
```

لا تعدّل الاختبارات ولا تعيد إنشاء مجلد المرشح القديم.
