# إصلاح 4.1.5-r3: خطأ gradlew في GitHub Actions

## سبب الخطأ

عند رفع المشروع من Windows أو واجهة GitHub، قد يُسجّل الملف `gradlew` في Git بوضع `100644` من دون بتّ التنفيذ. كانت بوابة الجودة تشغّل اختبار `test_gradle_wrapper_contract` قبل خطوة `chmod +x ./gradlew`، لذلك كانت تفشل مبكرًا.

## الإصلاح

- يشغّل `scripts/run_quality_gate.py` أداة `scripts/ensure_gradlew_executable.py` قبل اكتشاف الاختبارات.
- ينفذ `build.yml` الأداة أيضًا قبل بوابتي Debug وRelease للدفاع متعدد الطبقات.
- يضع `create_clean_source_archive.py` الملف `gradlew` دائمًا بوضع `0755` داخل ZIP.
- يحاكي اختبار الحزمة النظيفة وضع `0644` ويتأكد أن الناتج يبقى تنفيذيًا.

## النتيجة المتوقعة

عند تشغيل:

```bash
python scripts/run_quality_gate.py --strict-native-lanes
```

يجب أن يظهر أولًا سطر مشابه:

```text
GRADLEW_MODE_OK platform=posix action=normalized mode=0755
```

ثم تنجح اختبارات Python وعددها 84.
