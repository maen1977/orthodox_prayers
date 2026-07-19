# إصلاح Android Lint — Predictive Back

## سبب الفشل

كان `MainActivity` يعيد تعريف `onBackPressed()`، بينما التطبيقات التي تستهدف Android 16 / API 36 تحتاج مسار AndroidX المتوافق مع إيماءة الرجوع التنبؤية.

## التعديل

- أصبحت `MainActivity` ترث من `ComponentActivity`.
- أضيف `OnBackPressedCallback` إلى `getOnBackPressedDispatcher()`.
- بقيت دالة `goBack()` هي المصدر الوحيد لمنطق مكدس التنقل.
- حُذف `onBackPressed()` القديم والتسجيل اليدوي بـ `OnBackInvokedDispatcher`.
- أضيف اعتماد AndroidX Activity واختبار رجعي يحمي هذا العقد.

## التحقق

- 95/95 اختبارًا ناجحًا.
- فحص Workflow ناجح.
- Gradle Wrapper موثّق وسليم.
- فحص الأسرار والتوقيعات واللغات ناجح.

يجب تشغيل `./gradlew --no-daemon lintDebug` داخل GitHub Actions أو جهاز يحوي Android SDK لتأكيد تقرير Android Lint النهائي.
