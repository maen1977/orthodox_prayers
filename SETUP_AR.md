# إعداد Orthodox Prayers 4.2.0 على GitHub

## 1. إنشاء المستودع ورفع المشروع

ارفع **مجلد المشروع العام فقط**. لا ترفع مفتاح توقيع البيانات المنفصل، ولا Android Keystore، ولا ملفات الموافقات الخاصة.

راجع `GITHUB_UPLOAD_AR.md` أو `GITHUB_DESKTOP_AR.md` للخطوات التفصيلية.

## 2. صلاحيات GitHub Actions

من:

```text
Settings → Actions → General → Workflow permissions
```

اختر **Read and write permissions**. يحتاج Workflow `Update` إلى الكتابة في فرع `verified-data` وفتح Issue عند الفشل.

يفضل أيضًا حماية فرع `main` ومنع Force Push واشتراط نجاح Workflow `Build` قبل الدمج.

## 3. سر توقيع بيانات اليوم

أضف Repository Secret باسم:

```text
أنشئ GitHub Environment باسم `production-data-signing` وضع داخله السر التالي:

DATA_SIGNING_PRIVATE_KEY_B64
```

أنشئ القيمة من ملف المفتاح الخاص الذي سُلّم منفصلًا عن المشروع.

PowerShell:

```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("C:\secure\OrthodoxPrayers-data-private-key.pem"))
```

Linux/macOS:

```bash
base64 < /secure/OrthodoxPrayers-data-private-key.pem | tr -d '\n'
```

لا تطبع القيمة في سجل عام، ولا تحفظها في ملف داخل المستودع.

## 4. تشغيل التحديث الأول

من GitHub:

```text
Actions → Update → Run workflow → mode: update
```

بعد النجاح يُنشأ أو يُحدّث فرع:

```text
verified-data
```

الجدولة التلقائية:

```text
00:00 Asia/Amman  توليد البيانات والتحقق والتوقيع والنشر
00:15 Asia/Amman  فحص النسخة المنشورة ومحاولة إصلاح واحدة عند الفشل
```

لا توجد خطوة تصحيح بشري يومية؛ التحديث آلي ومغلق عند الخطأ. عند تعذر مصدر أو وجود تعارض لا يُنشر نص غير موثوق، وتبقى آخر نسخة موقعة سليمة.

## 5. مكتبات النصوص الأصلية

سجل المصادر والعقد:

```text
canonical/source_native_contract.json
canonical/native_language_sources.json
```

حزم الخدمات:

```text
data/services/native/library_ar.json
data/services/native/library_en.json
data/services/native/library_el.json
```

مكتبات الكتاب المقدس:

```text
data/scripture/native/ar/
data/scripture/native/en/
data/scripture/native/el/
```

اتبع `NATIVE_CONTENT_IMPORT_AR.md`. لا تُدخل نصًا عبر ترجمة أو تشكيل آلي.

## 6. أسرار توقيع Android

أنشئ GitHub Environment باسم:

```text
production
```

وأضف إليه:

```text
ANDROID_KEYSTORE_B64
ANDROID_KEYSTORE_PASSWORD
ANDROID_KEY_ALIAS
ANDROID_KEY_PASSWORD
```

احتفظ بنسخة مشفرة من Keystore طوال عمر التطبيق. فقدانه قد يمنع تحديث التطبيق على المتجر بحسب إعدادات التوقيع.

## 7. بناء الاختبار

Workflow `Build` يعمل عند Push وPull Request ويمكن تشغيله يدويًا. ينفذ بوابة الجودة وUnit Tests وLint Debug وبناء Debug APK في خطوات منفصلة. التطبيق يعرض حالة عدم التوفر بدل الترجمة، ويتضمن التقويم والتذكيرات وسجل القراءة وأدوات القراءة الجديدة.

فحص محلي:

```bash
python scripts/run_quality_gate.py --strict-native-lanes
./gradlew testDebugUnitTest lintDebug assembleDebug
```

## 8. إصدار Production

قبل إنشاء Tag يجب أن ينجح:

```bash
python scripts/run_quality_gate.py --require-current --strict-native-lanes
python scripts/validate_release_readiness.py
```

الفحص الثاني يُحجب حاليًا إلى أن:

- تكتمل حزم الخدمات الإنجليزية واليونانية.
- تُستورد مكتبات الكتاب المقدس الرسمية الأصلية للغات الثلاث.
- تتوفر رسالة وإنجيل اليوم بنصهما الأصلي في اللغات الثلاث.

بعد النجاح فقط:

```bash
git tag v4.2.0
git push origin v4.2.0
```

عندها يبني Workflow `Build` ملفي APK وAAB موقعين، ويتحقق من APK، وينشئ `SHA256SUMS.txt`.
