# R40.4 — إصلاح استقرار محاكي Android وDDMLib

## المشكلة

السجلان المرسلان متطابقان بالكامل، وكلاهما يشغّل API 29. نجح R40.3 في تشغيل سكربت Bash كأمر واحد، لكن المحاكي كان يعلن `sys.boot_completed=1` قبل استقرار خدمات Android وADB بصورة كافية.

بعد قطع Wi-Fi والبيانات من سكربت المضيف وقبل أن يبدأ Gradle باكتشاف الجهاز، تعذر على DDMLib قراءة خصائص الجهاز عدة مرات، فصنّف المحاكي على أنه `Unknown API Level` ورفض تشغيل الاختبارات.

## الإصلاح

1. أصبح سكربت `scripts/run_android_emulator_ci.sh` ينتظر ثلاث قراءات مستقرة متتالية لكل من:
   - `sys.boot_completed=1`
   - `ro.build.version.sdk` ومطابقته لمستوى API المطلوب
   - نجاح `pm path android`
2. أزيل قطع الشبكة بالكامل من سكربت المضيف قبل اكتشاف الجهاز.
3. نُقل اختبار وضع عدم الاتصال إلى `ReaderSmokeTest` بعد بدء Android Instrumentation:
   - تعطيل Wi-Fi والبيانات بأوامر Shell من `UiAutomation`
   - انتظار اختفاء `NET_CAPABILITY_VALIDATED`
   - تشغيل اختبارات القارئ بالحزمة المضمّنة
   - إعادة Wi-Fi والبيانات في `@AfterClass`
4. أضيفت إعدادات استقرار للمحاكي:
   - مهلة إقلاع 900 ثانية
   - نواتان
   - RAM بحجم 2048M
   - Heap بحجم 512M
   - تشغيل بارد دون Snapshot
   - إزالة `-no-boot-anim` الذي كان يسمح ببدء مبكر أكثر من اللازم
5. أضيفت اختبارات تمنع إعادة قطع الشبكة من سكربت المضيف وتفرض بقاء اختبار عدم الاتصال داخل Instrumentation.

## نتائج التحقق

- 425 اختبارًا ناجحًا.
- 14 اختبارًا فرعيًا ناجحًا.
- `validate_workflows.py`: ناجح.
- رزنامة 2026–2050 وحدود السنوات: ناجحة.
- اللغات الثلاث والموارد والقداس والقارئ: ناجحة.
- المصادر والتوقيع والصوم وجودة البيانات: ناجحة.
- تعذر تشغيل Gradle محليًا لأن البيئة لا تستطيع تنزيل Gradle 8.13 من `services.gradle.org`؛ لذلك يبقى تشغيل GitHub Actions هو إثبات المحاكي الفعلي.

## الملفات الرئيسية المعدلة

- `.github/workflows/build.yml`
- `scripts/run_android_emulator_ci.sh`
- `scripts/validate_workflows.py`
- `app/src/androidTest/java/com/orthodoxprayers/privateapp/ReaderSmokeTest.java`
- `tests/test_r40_3_emulator_script.py`
- `tests/test_r40_automated_source_research.py`
- `CHANGELOG.md`
