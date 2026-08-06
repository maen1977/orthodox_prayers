# إعداد التوقيع الرقمي على GitHub Actions

المشروع يضم خطوات توقيع اختيارية باستخدام SignTool. لا يمكن إنشاء توقيع موثوق بمجرد كتابة اسم الناشر في الكود؛ يلزم امتلاك شهادة Windows Code Signing بصيغة PFX.

## اسم الشهادة

حتى يظهر الاسم المطلوب في نافذة Windows UAC، يجب أن تكون الشهادة صادرة إلى:

```text
معن حنونة للستلايت
```

البرنامج والمثبت يعرضان أيضًا رقم التواصل التالي في بيانات المشروع وصفحة «حول» وملف BUILD-INFO:

```text
00962788272988
```

رقم الهاتف ليس جزءًا من هوية توقيع Authenticode التي يعرضها Windows.

## أسرار GitHub المطلوبة

من المستودع افتح:

```text
Settings → Secrets and variables → Actions
```

أضف Repository secrets:

```text
WINDOWS_CERTIFICATE_BASE64
WINDOWS_CERTIFICATE_PASSWORD
```

يمكن إضافة Repository variable اختياري:

```text
WINDOWS_TIMESTAMP_URL
```

إذا لم تضف المتغير الأخير، يستخدم workflow:

```text
http://timestamp.digicert.com
```

## تحويل ملف PFX إلى Base64

نفّذ على جهاز Windows آمن:

```powershell
$bytes = [IO.File]::ReadAllBytes("C:\Secure\publisher-certificate.pfx")
[Convert]::ToBase64String($bytes) | Set-Clipboard
```

ألصق القيمة داخل `WINDOWS_CERTIFICATE_BASE64`، وضع كلمة مرور PFX داخل `WINDOWS_CERTIFICATE_PASSWORD`.

## ما يفعله workflow

1. يبني التطبيق ويشغل اختبارات الأمان بصلاحية قراءة فقط في وظيفة البناء.
2. ينشر `SafeWindowsCleaner.exe`.
3. يفك الشهادة مؤقتًا داخل مجلد Runner المؤقت.
4. يوقع التطبيق بخوارزمية SHA-256 ويضيف ختمًا زمنيًا.
5. يتحقق من التوقيع باستخدام `signtool verify /pa`.
6. يبني Setup بعد توقيع التطبيق.
7. يوقع Setup ويتحقق من توقيعه.
8. ينشئ ملفات SHA-256 بعد التوقيع.
9. يحذف ملف PFX المؤقت في خطوة تعمل حتى عند فشل البناء.
10. لا يقرأ أسرار التوقيع داخل Pull Request، وتعمل وظيفة إنشاء Release منفصلة فقط عند رفع Tag.

إذا لم تكن الأسرار موجودة، لا يفشل البناء؛ ينتج نسخة غير موقعة ويضع:

```text
Signed: false
```

داخل `BUILD-INFO.txt`.

## قواعد مهمة

- لا ترفع ملف PFX إلى GitHub مطلقًا.
- لا تضع كلمة المرور داخل YAML أو PowerShell أو README.
- قيّد صلاحية الوصول إلى أسرار المستودع.
- استخدم شهادة توزيع حقيقية، لا شهادة Self-Signed، عند النشر للعامة.
- تحقق من Subject الشهادة وتاريخ انتهائها قبل كل إصدار.
- ألغِ الشهادة فورًا إذا شككت في تسرب المفتاح الخاص.
