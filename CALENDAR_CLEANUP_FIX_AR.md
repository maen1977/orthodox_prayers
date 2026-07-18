# إصلاح بقايا ملفات التقويم القديمة

سبب الفشل هو بقاء ملف قديم مثل:

`data/calendar/2026-07-14.json`

عند نسخ حزمة «ملفات التعديل فقط» فوق مستودع سابق، لأن النسخ يستبدل الملفات لكنه لا يحذف الملفات القديمة.

## Windows PowerShell

من جذر المستودع:

```powershell
powershell -ExecutionPolicy Bypass -File .\APPLY_CALENDAR_CLEANUP.ps1
python scripts/run_quality_gate.py --strict-native-lanes
```

## Linux / macOS

```bash
./APPLY_CALENDAR_CLEANUP.sh
python3 scripts/run_quality_gate.py --strict-native-lanes
```

بعد نجاح الفحص:

```bash
git add -A
git commit -m "Remove obsolete calendar snapshots"
git push
```

السكربت يحتفظ فقط بـ:

- `data/calendar/today.json`
- `data/calendar/today.json.sig`
- ملف التاريخ المشار إليه داخل `today.json`
- توقيع ملف التاريخ نفسه

ولا يلمس مجلد `data/calendar/candidates` أو أرشيف `data/daily`.
