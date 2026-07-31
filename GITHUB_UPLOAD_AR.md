# رفع Orthodox Prayers 5.0.23 إلى GitHub

هذه النسخة مجهزة كمستودع مصدر نظيف، مع Workflow للبناء وWorkflow مستقل لنشر البيانات الموقعة.

## الرفع

1. فك ملف `OrthodoxPrayers-5.0.23-GitHub-Ready.zip` داخل مجلد جديد.
2. أنشئ مستودع GitHub أو ارفع المحتويات إلى جذر المستودع الحالي.
3. ارفع كل الملفات والمجلدات كما هي، بما فيها `.github` و`gradle` و`gradlew`.
4. لا ترفع أي ملف Keystore أو مفتاح RSA خاص أو `local.properties`.

مثال أوامر Git:

```bash
git init
git add .
git commit -m "Release Orthodox Prayers 5.0.23 with moving liturgical window"
git branch -M main
git remote add origin https://github.com/OWNER/REPOSITORY.git
git push -u origin main
```

## الإعداد الأول بعد الرفع

1. أنشئ GitHub Environment باسم `production-data-signing`.
2. أضف إليه `DATA_SIGNING_PRIVATE_KEY_B64` المطابق للمفتاح العام المضمّن.
3. افتح Actions وشغّل `Rolling Liturgical Window Update` بوضع `update` مرة واحدة؛ سيُنشئ فرع `verified-data` إن لم يكن موجودًا.
4. بعد نجاح التحديث، شغّل `Build`. بناء Debug يستطيع البدء بالنسخة الموقعة المضمنة حتى قبل إنشاء `verified-data`، أما الإصدار Production فيتطلب الفرع الموقّع.
5. للإصدار الموقّع أنشئ Environment باسم `production` وأضف أسرار Android المذكورة في `GITHUB_SECRETS_AR.md`.

## نظام الأيام والأسابيع القادمة

- الافتراضي: 21 يومًا متحركًا.
- المسموح: 9 إلى 42 يومًا.
- التشغيل المجدول: `00:07` و`00:37` و`06:37` بتوقيت `Asia/Amman`.
- يمكن تغيير المدى في التشغيل اليدوي من حقل `window_days`.
- كل يوم يتضمن اختيار الخدمة، سبب الاختيار، القراءات الأصلية في اللغات الثلاث، والخدمة الكاملة أو تصريحًا صريحًا بعدم تعيين قداس.

## الفحص المحلي

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python scripts/run_quality_gate.py --strict-native-lanes
python scripts/scan_repository_secrets.py
```

يتطلب بناء Android لأول مرة اتصالًا يسمح بتنزيل Gradle 8.13 واعتماديات Android SDK.
