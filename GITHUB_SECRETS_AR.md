# GitHub Secrets المطلوبة

## Repository Secret لتحديث البيانات

```text
DATA_SIGNING_PRIVATE_KEY_B64
```

القيمة هي Base64 لملف RSA الخاص الذي سُلّم منفصلًا عن ZIP المشروع. المفتاح العام المقابل موجود داخل التطبيق والمستودع.

بصمة المفتاح العام المتوقعة بصيغة DER/SHA-256:

```text
cff1882f2ba6d6ee2b5b4621cd88a29242a988b845c9fa288f095f72cfe8e113
```

## Environment Secrets لإصدار Android

أنشئ Environment باسم `production` وأضف:

```text
ANDROID_KEYSTORE_B64
ANDROID_KEYSTORE_PASSWORD
ANDROID_KEY_ALIAS
ANDROID_KEY_PASSWORD
```

## قواعد إلزامية

- لا تضع قيمة Secret في YAML أو README أو Issue أو Screenshot.
- لا ترفع Keystore أو المفتاح الخاص حتى إلى مستودع خاص.
- احتفظ بنسختين مشفرتين خارج GitHub.
- عند الاشتباه بتسريب مفتاح بيانات اليوم، أوقف Workflow التحديث ودوّر المفتاح. يجب نشر تطبيق يحمل المفتاح العام الجديد قبل توقيع البيانات بالمفتاح الخاص الجديد.
- لا تغيّر Android signing key بلا خطة متوافقة مع Google Play App Signing.
