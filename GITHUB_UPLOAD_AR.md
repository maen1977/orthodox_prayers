# رفع إصلاح GitHub إلى المستودع الحالي

المستودع المستهدف:

```text
maen1977/orthodox_prayers
```

الطريقة الأسهل موضحة في `GITHUB_DESKTOP_AR.md`.

## ما الذي تصلحه هذه النسخة؟

- تحذف إعداد Dependabot الذي فتح طلبات تحديث كثيرة.
- تترك Workflowين فقط: `Build` و`Update`.
- تمنع `Update` من التشغيل عند كل Push.
- تشغّل `Update` عند 00:00 و00:15 بتوقيت `Asia/Amman` أو يدويًا فقط.
- تفصل Unit Tests وLint وبناء APK حتى يظهر اسم الخطوة الفاشلة.
- توقف CodeQL واختبار المحاكي مؤقتًا لأنهما كانا يضيفان أخطاء لا تساعد على تشخيص بناء APK الأول.
- ترفع رقم التطبيق إلى 3.5.1 وتغيّر اسم مشروع Gradle الظاهر إلى `OrthodoxPrayers`.

## رسالة Commit

```text
Fix GitHub Actions and disable Dependabot updates
```

## بعد الرفع

1. أغلق Pull Requests القديمة الخاصة بـDependabot دون Merge.
2. أضف Secret `DATA_SIGNING_PRIVATE_KEY_B64`.
3. شغّل Build وتابع اسم أول خطوة حمراء إن وجدت.
4. بعد نجاح Build شغّل Update يدويًا بوضع `update`.
5. تحقق من إنشاء فرع `verified-data`.

## فحص أمان محلي

```bash
python scripts/scan_repository_secrets.py
python scripts/run_quality_gate.py --strict-native-lanes
```

لا ترفع `.pem` خاصًا أو `.jks` أو `.keystore` أو ملف كلمات مرور.
