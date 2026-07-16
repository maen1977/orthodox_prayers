# رفع إصلاح Android 3.5.1-r2 عبر GitHub Desktop

هذا الإصدار يصلح خطأ التجميع:

```text
String cannot be converted to byte[]
```

## الطريقة

1. فك ضغط ملف المشروع.
2. من GitHub Desktop اختر `Repository > Show in Explorer`.
3. انسخ كل محتويات مجلد `orthodox_prayers` الناتج إلى مجلد المستودع الحالي واختر Replace.
4. تأكد أن `.github/dependabot.yml` غير موجود.
5. استخدم رسالة Commit التالية:

**Summary**

```text
Fix Android SHA-256 compilation error
```

**Description**

```text
Hash verified native text as UTF-8 bytes in DataRepository.
Bump the Android app version to 3.5.1-r2.
Keep only Build and Update workflows and keep Dependabot disabled.
```

6. اضغط `Commit to main` ثم `Push origin`.
