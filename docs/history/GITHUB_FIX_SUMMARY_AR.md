# ملخص إصلاح GitHub Actions — الإصدار 3.5.1

## الحالة قبل الإصلاح

- كان Dependabot مفعّلًا لثلاثة أنظمة حزم، ففتح Pull Requests كثيرة وشغّل Build لكل واحد.
- كان Update يعمل أيضًا عند Push إلى `main`، فاشتغل قبل إضافة مفتاح التوقيع.
- كانت أربعة أوامر Gradle مجمعة في خطوة واحدة، لذلك ظهر `exit code 1` دون معرفة الأمر الفاشل.
- كان CodeQL يعمل قبل تفعيل Code Scanning في إعدادات المستودع.
- كان اختبار المحاكي والبناء الموسع يعملان قبل تثبيت بناء Debug الأساسي.

## الحالة بعد الإصلاح

- لا يوجد `.github/dependabot.yml`، ولذلك توقفت تحديثات الإصدارات الآلية.
- يوجد Workflowان فقط داخل `.github/workflows`: `build.yml` و`update.yml`.
- Update لا يعمل عند Push؛ يعمل يدويًا أو عند 00:00 و00:15 بتوقيت عمّان.
- Build يعرض خطوات منفصلة: بوابة الجودة، Unit Tests، Lint Debug، Build Debug APK.
- CodeQL والمحاكي و`assembleDebugAndroidTest` معطلة مؤقتًا.
- إصدار Production الموقّع بقي محميًا ولم تُحذف منه اختبارات الإصدار أو التوقيع.
- رقم النسخة أصبح 3.5.1 واسم Gradle الظاهر أصبح `OrthodoxPrayers`.

## ما لا يستطيع الـCommit فعله تلقائيًا

- لا يمكنه إغلاق Pull Requests القديمة دون صلاحية حسابك؛ أغلقها يدويًا من تبويب Pull requests.
- لا يمكنه إضافة GitHub Secret؛ أضف `DATA_SIGNING_PRIVATE_KEY_B64` من Settings.
- تشغيلات Actions القديمة تبقى كسجل تاريخي حتى بعد نجاح الإصلاح.
