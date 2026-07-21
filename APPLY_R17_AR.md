# تطبيق R17

فك ضغط الحزمة مباشرة داخل جذر مستودع `orthodox_prayers` مع السماح باستبدال الملفات، ثم شغّل:

```powershell
python scripts/verify_r17_patch.py
python -m unittest discover -s tests -p "test_*.py"
git status --short
```

النتيجة المتوقعة من الفحص الأول:

```text
PATCH_R17_OK version=5.0.13 level=R17
```

> لا تحتاج هذه النسخة إلى إذن المنبهات الدقيقة. بعد بناء التطبيق، يتم تحديث البيانات بواسطة WorkManager عند 00:05 بتوقيت عمّان أو عند عودة الاتصال.
