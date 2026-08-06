# إعداد التحديث التلقائي عبر GitHub — Orthodox Prayers 5.2.1

## ما تم تنفيذه

يتحقق التطبيق من آخر **GitHub Release مستقر** في المستودع `maen1977/orthodox_prayers`. عند وجود `versionCode` أعلى من النسخة المثبتة، يعرض التحديث وينزّل `Church-Prayers.apk`، ثم يتحقق من:

1. حجم الملف وبصمة SHA-256.
2. أن اسم الحزمة هو نفسه `com.orthodoxprayers.privateapp`.
3. أن `versionCode` مطابق وأحدث.
4. أن شهادة توقيع APK مطابقة لشهادة النسخة المثبتة.

بعد نجاح الفحص يفتح Android شاشة التثبيت، ويبقى الضغط النهائي على **تثبيت** للمستخدم.

> **مهم لأول مرة:** النسخ الأقدم من 5.2.1 لا تحتوي على محرك التحديث، لذلك يجب تثبيت 5.2.1 يدويًا مرة واحدة فوق النسخة الحالية. بعد ذلك تستطيع 5.2.1 اكتشاف 5.2.2 وما بعدها تلقائيًا.

## إعداد أسرار التوقيع مرة واحدة

في GitHub افتح: **Settings → Secrets and variables → Actions** ثم أضف:

- `ANDROID_KEYSTORE_B64`: ملف keystore مشفّر Base64 كسطر واحد.
- `ANDROID_KEYSTORE_PASSWORD`
- `ANDROID_KEY_ALIAS`
- `ANDROID_KEY_PASSWORD`

يجب استخدام **ملف التوقيع نفسه لكل الإصدارات**. فقدانه يعني أن Android لن يقبل تثبيت إصدار جديد فوق النسخة القديمة.

لإنشاء قيمة Base64 في PowerShell:

```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("C:\Path\orthodox-prayers.keystore")) | Set-Clipboard
```

## نشر إصدار جديد

1. عدّل في `app/build.gradle.kts`:

```kotlin
versionCode = 50202
versionName = "5.2.2"
```

2. ادفع التغييرات إلى `main`.
3. أنشئ tag مطابقًا تمامًا للنسخة وادفعه:

```powershell
git tag v5.2.2
git push origin main
git push origin v5.2.2
```

عند وصول tag، يقوم GitHub Actions تلقائيًا بالبناء والاختبار والتوقيع، ثم ينشر Release يحتوي على:

- `Church-Prayers.apk`
- `Church-Prayers.aab`
- `Church-Prayers.apk.sha256`
- `app-update.json`

لا تنشر Release من APK موقّع بمفتاح debug، ولا تغيّر `applicationId`.

## إعدادات المستخدم داخل التطبيق

في **الإعدادات → التحديث والبيانات** توجد خيارات:

- البحث الآن عن تحديث.
- تشغيل أو إيقاف الفحص التلقائي.
- التنزيل التلقائي على شبكة غير محدودة فقط.
- عرض النسخة المثبتة وآخر فحص والنسخة المتاحة.

الفحص يجري عند فتح التطبيق، وكذلك دوريًا في الخلفية. Android قد يؤخر الفحص الخلفي حسب البطارية والاتصال. وإذا لم يمنح المستخدم إذن الإشعارات، يبقى التحديث ظاهرًا عند فتح التطبيق.

## إصدار إجباري اختياري

الافتراضي أن التحديث غير إجباري. يمكن توليد `app-update.json` يدويًا مع `--mandatory`، أو تحديد `--minimum-supported-version-code`، لكن يُنصح باستخدام ذلك فقط عندما تكون النسخة القديمة غير آمنة أو غير قابلة للعمل.
