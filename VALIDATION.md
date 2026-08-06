# Validation Notes — Safe Windows Cleaner Lite 2.4.0

## بوابة المصدر

```bash
python scripts/static-validate.py
```

تفحص XAML وXML وJSON، معالجات WPF في المشروعين، أقواس C#، عقد الإصدار، الترجمة الثنائية، مثبتات x64/x86/Win7، الذاكرة الافتراضية المتدرجة، وهوية التطبيق الموحدة.

## بوابة Windows

```powershell
./scripts/validate-release.ps1
```

تفحص:

- المشروع الحديث `net8.0-windows`.
- مشروع Windows Legacy ‏`net461` و`AnyCPU`.
- طلب Administrator في التطبيق والمثبت.
- حزم x64 وx86 وحزمة Legacy لويندوز 7 SP1 وويندوز 8 وويندوز 8.1.
- `runascurrentuser` لمنع خطأ CreateProcess 740.
- ‎.NET Framework 4.6.1 أو أحدث في مثبت Windows 7/8/8.1.
- لغتي العربية وEnglish فقط.
- 4/8/16 غيغابايت مع إبقاء 8 غيغابايت حرة.
- عدم وجود تقليص Working Set أو إغلاق تلقائي للبرامج.

## ما لا يمكن إثباته في Linux

بوابة المصدر لا تستبدل البناء الحقيقي. قبل النشر يجب أن ينجح GitHub Actions، وأن تُختبر حزمة Legacy يدويًا على Windows 7 SP1 وWindows 8 وWindows 8.1 لأن Runner الحديث لا يستطيع تشغيل مثبت مقيد بويندوز 7/8/8.1 فقط.
