# R40.1 — إصلاح Bash في Android Emulator

## سبب الفشل

كانت قيمة `script` في `ReactiveCircus/android-emulator-runner` تبدأ مباشرة بالأمر:

```sh
set -euo pipefail
```

ينفذ الإجراء هذه القيمة بواسطة `/usr/bin/sh -c`. في Ubuntu يشير `/bin/sh` إلى `dash`، و`dash` لا يدعم الخيار `set -o pipefail`، لذلك توقفت مهمتا API 29 وAPI 35 قبل تشغيل اختبارات Android.

## الإصلاح

أصبحت كتلة المحاكي تطلق Bash صراحة:

```sh
bash -euo pipefail <<'BASH'
...
BASH
```

وبذلك تبقى حماية `errexit` و`nounset` و`pipefail` فعالة، بينما لا يعود التنفيذ معتمدًا على نوع `/bin/sh`.

## حماية عدم الرجوع

- تم تحديث `scripts/validate_workflows.py` ليفرض وجود غلاف Bash في خطوة المحاكي.
- تم تحديث اختبارات R40 لتمنع رجوع `set -euo pipefail` مباشرة بعد `script: |`.
- تمت محاكاة النص المستخرج من YAML عبر `/usr/bin/sh -c`، ونجح في تشغيل اختبار Gradle ومسار لقطات API 35.

## إصلاح إضافي

أعاد الإصدار ملفي العلامة التجارية اللذين كانا مفقودين من ZIP الخاص بـR40:

- `release/branding/Church-Prayers.ico`
- `release/branding/Church-Prayers-icon-512.png`

## التحقق

- 420 اختبارًا ناجحًا.
- 14 اختبارًا فرعيًا ناجحًا.
- 57/57 من اختبارات Workflow وR40 الموجهة ناجحة.
- جميع أجزاء بوابة الجودة نجحت.
- فحص حدود التقويم حتى 2050 نجح.
- محاكاة `/bin/sh` إلى Bash نجحت لمسار API 35.
- تعذر تنزيل Gradle محليًا بسبب عدم توفر DNS إلى `services.gradle.org` في بيئة العمل؛ يجب أن ينفذ GitHub البناء الفعلي.
