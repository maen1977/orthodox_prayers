# رفع الإصدار 4.1.5 إلى GitHub

1. فك ضغط ملف `OrthodoxPrayers-v4.1.5-GitHub-replacement-files.zip`.
2. انسخ محتوياته إلى جذر مستودع `orthodox_prayers` ووافق على استبدال الملفات.
3. تأكد أن `app/build.gradle.kts` يحتوي:

```kotlin
versionCode = 41005
versionName = "4.1.5"
```

4. نفّذ:

```bash
git add -A
git commit -m "fix(liturgics): publish daily propers and remove stale service placeholders"
git push
```

5. شغّل Workflow باسم `Update` مع `mode: update` واترك التاريخ فارغًا.
6. بعد نجاحه، شغّل Workflow بناء Android وثبّت APK الجديد.
7. تأكد من ظهور الإصدار `4.1.5` داخل الإعدادات، ثم اضغط «تحديث بيانات اليوم الآن».

يجب رفع الكود قبل تشغيل Update؛ تشغيل Update من فرع `main` القديم لن يستخدم سجل القطع الجديد.
