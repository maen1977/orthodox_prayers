# رفع الإصدار 4.1.3 والتحقق منه

هذا الإصدار يعالج رفض ملف اليوم بسبب اعتبار خرائط `language_sources` و`native_source_verification` نصوص ترجمة.

## قبل البناء

تحقق في `app/build.gradle.kts` من وجود:

```text
versionCode = 41003
versionName = "4.1.3"
```

وتحقق في `TranslationCoverage.java` من وجود الدالة:

```text
isLocalizedTextObject
```

## الاختبار على GitHub

بعد رفع الملفات إلى فرع `main` شغّل Workflow الخاص ببناء Android. يجب أن ينجح اختبار `testDebugUnitTest` قبل إنشاء APK.

بعد تثبيت APK افتح الإعدادات وتأكد أن إصدار التطبيق هو `4.1.3`. إذا ظهر `4.1.1` أو `4.1.2` فالنسخة المثبتة قديمة.

في الإصدار 4.1.3 يظهر أيضًا `رمز تشخيص التحديث` داخل الإعدادات.
