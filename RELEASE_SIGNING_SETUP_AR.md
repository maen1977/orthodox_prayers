# إعداد التوقيع والإصدار التلقائي — Orthodox Prayers 5.5.2

هذه الخطوة تُنفذ **مرة واحدة فقط** على جهاز Windows موثوق. هدفها إنشاء مفتاح Android إنتاجي ثابت ثم حفظه في GitHub Actions Secrets بدون إضافته للمستودع.

## قبل التنفيذ

ثبّت:
- Java JDK 17 أو أحدث بحيث يكون `keytool` متاحًا.
- GitHub CLI (`gh`) وسجّل الدخول عبر `gh auth login`.

## التنفيذ

من مجلد المشروع افتح PowerShell وشغّل:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_release_signing.ps1
```

السكربت يقوم تلقائيًا بـ:
1. إنشاء `.release-signing/orthodox-prayers-release.jks` إن لم يوجد مفتاح سابق.
2. إنشاء كلمة مرور قوية عشوائية.
3. حفظ كلمات المرور محليًا بصيغة DPAPI مرتبطة بحساب Windows الحالي في `release-signing.dpapi.json`.
4. رفع الأسرار التالية إلى GitHub:
   - `ANDROID_KEYSTORE_B64`
   - `ANDROID_KEYSTORE_PASSWORD`
   - `ANDROID_KEY_ALIAS`
   - `ANDROID_KEY_PASSWORD`
5. منع `.release-signing/` من الدخول إلى Git.

**احتفظ بنسخة احتياطية آمنة من مجلد `.release-signing` ولا تحذفه.** هذا المفتاح هو هوية التطبيق للإصدارات القادمة.

## نشر 5.5.2 بعد إعداد التوقيع

1. افتح GitHub > Actions > **Build Church Prayers**.
2. اختر **Run workflow**.
3. فعّل **Publish a signed GitHub Release for the current version**.
4. شغّل الـworkflow.

الـworkflow سيقرأ `versionName` من `app/build.gradle.kts`، وينشئ Tag `v5.5.2` تلقائيًا إذا لم يكن موجودًا، ثم ينشر Release يحتوي على:
- `Church-Prayers.apk`
- `Church-Prayers.aab`
- `Church-Prayers.apk.sha256`
- `app-update.json`

بعدها `releases/latest` يصبح متاحًا، والتطبيق يستطيع اكتشاف التحديث.

## ملاحظة التوقيع لأول مرة

النسخ السابقة التي بُنيت على `main` بدون Secrets كانت تستخدم debug signing. Android لا يسمح بتحديث تطبيق موقّع بمفتاح مختلف. لذلك إذا كانت النسخة الموجودة على الهاتف موقّعة بمفتاح debug قديم، قد تحتاج **مرة واحدة فقط** إلى إزالة النسخة القديمة وتثبيت أول APK إنتاجي موقّع بهذا المفتاح. بعد هذه النقطة، كل الإصدارات التالية يمكن تثبيتها كتحديث طبيعي بشرط الحفاظ على نفس المفتاح.
