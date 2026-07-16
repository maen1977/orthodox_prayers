# خطوات رفع الإصدار 4.2.0

1. فك ضغط `OrthodoxPrayers-4.2.0-enhanced-source.zip` في مجلد جديد.
2. افتح المجلد في GitHub Desktop أو انسخ محتوياته إلى مستودعك الحالي مع الاحتفاظ بمجلد `.git` الموجود عندك فقط.
3. تأكد أن `app/build.gradle.kts` يحتوي:

```text
versionCode = 42000
versionName = "4.2.0"
```

4. نفذ Commit بالرسالة المقترحة في `GITHUB_UPLOAD_AR.md` ثم Push إلى `main`.
5. شغّل Workflow `Build`.
6. شغّل Workflow `Update` بوضع `update` لإنشاء بيانات اليوم الموقعة.
7. نزّل Debug APK من Artifacts بعد نجاح البناء واختبر التقويم والتذكيرات والقراءة على جهاز Android حقيقي.

لا تنشر Release موقّعًا قبل نجاح `scripts/validate_release_readiness.py`.
