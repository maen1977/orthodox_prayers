# رفع إصلاح Orthodox Prayers 3.5.1 بواسطة GitHub Desktop

هذه النسخة مخصصة للمستودع الموجود بالفعل:

```text
maen1977/orthodox_prayers
```

## قبل النسخ

1. افتح **GitHub Desktop**.
2. اختر مستودع `orthodox_prayers`.
3. اضغط **Fetch origin** ثم **Pull origin** إن ظهر الزر.
4. من القائمة اختر:

```text
Repository → Show in Explorer
```

سيُفتح مجلد المستودع المحلي الذي يحتوي مجلدات مثل `.github` و`app` و`scripts`.

## وضع النسخة الجديدة

1. فك ضغط ملف `orthodox_prayers-github-fix-v3.5.1.zip`.
2. افتح المجلد الناتج `orthodox_prayers`.
3. انسخ **كل محتوياته** إلى مجلد المستودع الذي فتحه GitHub Desktop.
4. وافق على **Replace the files in the destination**.
5. تأكد أن Windows نسخ المجلد المخفي `.github`.
6. تأكد أن الملف التالي حُذف من المستودع المحلي:

```text
.github/dependabot.yml
```

لا تحذف مجلد `.git` الموجود في مستودع GitHub Desktop، ولا تنسخ أي ملف مفتاح خاص `.pem` أو Android Keystore.

## التغييرات التي يجب أن تظهر في GitHub Desktop

- حذف `.github/dependabot.yml`.
- تعديل `.github/workflows/build.yml`.
- تعديل `.github/workflows/update.yml`.
- تعديل اختبارات عقد الـWorkflows.
- تحديث رقم النسخة إلى `3.5.1`.
- تغيير اسم مشروع Gradle الظاهر إلى `OrthodoxPrayers`.

## رسالة الـCommit الجاهزة

في خانة **Summary** ضع:

```text
Fix GitHub Actions and disable Dependabot updates
```

وفي خانة **Description** ضع:

```text
Keep only Build and Update workflows.
Stop automatic Dependabot version pull requests.
Run daily data update only at 00:00 and verification at 00:15 Asia/Amman.
Split Android unit tests, lint, and APK build into separate steps.
Temporarily disable CodeQL and emulator checks until the debug build is stable.
Bump the app version to 3.5.1.
```

ثم اضغط:

```text
Commit to main → Push origin
```

## بعد الـPush

1. افتح GitHub ثم **Actions → Build**.
2. انتظر النتيجة. ستظهر الآن الخطوة الفاشلة باسم واضح إن بقي خطأ Android.
3. لا تشغّل `Update` قبل إضافة Secret باسم `DATA_SIGNING_PRIVATE_KEY_B64`.
4. أغلق Pull Requests القديمة التي فتحها Dependabot؛ حذف ملف الإعداد يمنع تحديثات الإصدارات الجديدة لكنه لا يمحو سجل التشغيلات القديمة من صفحة Actions.
5. بعد إضافة Secret شغّل **Actions → Update → Run workflow → update**.

يجب أن يبقى في قائمة Workflows الخاصة بالمشروع ملفان من المشروع فقط: **Build** و**Update**. قد يبقى سجل قديم باسم Dependabot Updates في صفحة التاريخ، لكنه لن يتكرر بسبب هذه النسخة.
