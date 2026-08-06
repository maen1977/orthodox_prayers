# التشغيل السريع — Safe Windows Cleaner Lite 2.4.0

## اختر الملف الصحيح

- Windows 10/11 ‏64-bit: حزمة `x64`.
- Windows 10/11 ‏32-bit: حزمة `x86`.
- Windows 7 SP1 أو Windows 8 أو Windows 8.1 ‏32 أو 64-bit: حزمة `Windows7-8-8.1-Legacy`.

لا تستخدم حزمة x64 على Windows ‏32-bit. لا تستخدم حزمة .NET 8 الحديثة على Windows 7/8/8.1.

## Windows 7/8/8.1

قبل تثبيت نسخة Legacy:

1. تأكد أن النظام Windows 7 SP1 أو Windows 8 أو Windows 8.1.
2. ثبّت ‎.NET Framework 4.6.1 أو أحدث إن لم يكن موجودًا.
3. أعد تشغيل Windows.
4. شغّل حزمة Legacy كمسؤول.

## GitHub Actions

1. ارفع محتويات المشروع إلى جذر المستودع.
2. افتح **Actions → Build Windows Cleaner**.
3. يجب أن ينجح كل من `build-modern` و`build-win7-legacy`.
4. نزّل:
   - `SafeWindowsCleaner-Lite-modern-assets`
   - `SafeWindowsCleaner-Lite-Windows-Legacy-assets`

## الذاكرة الافتراضية

البرنامج لا يفرض 16 غيغابايت على قرص صغير:

- يختار 16 غيغابايت إذا بقيت 8 غيغابايت حرة على الأقل.
- وإلا يختار 8 غيغابايت.
- وإلا يختار 4 غيغابايت.
- إذا لم يستطع إبقاء 8 غيغابايت حرة، يرفض التعديل برسالة واضحة.

يحفظ إعداد Windows السابق ويمكن استعادته من نفس الصفحة أو أثناء إزالة البرنامج.

## التحقق المحلي

```powershell
./scripts/validate-release.ps1
./build-windows.ps1
```
