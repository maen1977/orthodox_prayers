# قائمة فحص الإصدار 2.4.0

## قبل الرفع

1. شغّل `python scripts/static-validate.py`.
2. على Windows شغّل `./scripts/validate-release.ps1`.
3. ادفع التغييرات إلى GitHub Actions.
4. تأكد من نجاح وظيفتي:
   - `build-modern`
   - `build-win7-legacy`

## الملفات المتوقعة

### Windows 10/11

```text
SafeWindowsCleaner-2.4.0-Win10-11-x64-Setup.exe
SafeWindowsCleaner-2.4.0-Win10-11-x64-Portable.zip
SafeWindowsCleaner-2.4.0-Win10-11-x86-Setup.exe
SafeWindowsCleaner-2.4.0-Win10-11-x86-Portable.zip
```

### Windows 7 SP1 / Windows 8 / Windows 8.1

```text
SafeWindowsCleaner-2.4.0-Windows7-8-8.1-Legacy-Setup.exe
SafeWindowsCleaner-2.4.0-Windows7-8-8.1-Legacy-Portable.zip
```

يجب أن يوجد ملف `.sha256` لكل حزمة.

## اختبارات إلزامية

- نجاح بناء .NET 8 الحديث واختبارات الأمان.
- نجاح بناء مشروع net461 Legacy.
- نجاح ترجمة مثبتات Inno الثلاثة.
- نجاح تثبيت وإزالة x64 وx86 صامتًا ضمن مهلة محددة.
- تحقق يدوي لنسخة Legacy على Windows 7 SP1 / 8 / 8.1 حقيقي أو VM قبل نشرها للعامة.
- عدم ظهور خطأ 740 بعد التثبيت.
- عدم إنشاء نسخة ثانية عند الترقية.
- عدم عرض مسار تقرير التشخيص للمستخدم العادي.
- اختيار الذاكرة الافتراضية المتدرج وفق مساحة القرص.

## Release

```bash
git add -A
git commit -m "Add Windows 10/11 x64-x86 and Windows 7/8/8.1 Legacy packages"
git push
git tag v2.4.0
git push origin v2.4.0
```
