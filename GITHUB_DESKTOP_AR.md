# رفع Orthodox Prayers 4.2.0 بواسطة GitHub Desktop

## قبل البدء

- نزّل `OrthodoxPrayers-4.2.0-enhanced-source.zip` وفك الضغط في مجلد جديد.
- لا تنسخ مجلد `.git` من أي أرشيف قديم.
- احتفظ بنسخة احتياطية من المستودع الحالي قبل الاستبدال.

## الاستبدال داخل المستودع الحالي

1. افتح مستودع `orthodox_prayers` في GitHub Desktop.
2. من **Repository → Show in Explorer** افتح مجلد المستودع.
3. احذف ملفات المشروع القديمة مع إبقاء مجلد `.git` المخفي.
4. انسخ محتويات مجلد `orthodox_prayers` الموجود داخل ZIP الجديد إلى مجلد المستودع.
5. ارجع إلى GitHub Desktop وراجع قائمة الملفات المعدلة.
6. استخدم رسالة Commit:

```text
Release Orthodox Prayers 4.2.0 with calendar, reminders, and reading tools
```

7. اضغط **Commit to main** ثم **Push origin**.

## بعد الرفع

1. افتح GitHub → Actions → Build.
2. راقب بوابة الجودة ثم Unit Tests وLint Debug وBuild Debug APK.
3. شغّل Update يدويًا بوضع `update` بعد التأكد من وجود سر توقيع البيانات.
4. نزّل Debug APK من Artifacts واختبره على جهازك.

راجع `GITHUB_UPLOAD_AR.md` و`UPLOAD_4.2.0_AR.md` للتفاصيل الأمنية ومتطلبات Production.
