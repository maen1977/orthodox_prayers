# تقرير R40.6 — إصلاح إقلاع محاكي Android بالتسريع العتادي

## المشكلة

توقفت مهمة `android-emulator-runner` بعد نحو 30 دقيقة برسالة:

```text
Timeout waiting for emulator to boot.
```

وقع الفشل قبل تشغيل سكربت الاختبارات وقبل تثبيت APK، لذلك لم يكن سببه التطبيق أو اختبارات القارئ. كان Workflow يشغّل محاكي Linux من دون خطوة صريحة لتفعيل والتحقق من KVM، مع صورة `google_apis` وملف Pixel 5 وذاكرة 3072 MB.

## الإصلاح الجذري

1. تثبيت مهمة المحاكي على `ubuntu-24.04` بدل الاعتماد على تغير `ubuntu-latest`.
2. إضافة خطوة `Enable and verify KVM acceleration` التي:
   - تضبط قاعدة udev لـ`/dev/kvm`.
   - تعيد تحميل القواعد.
   - تتحقق أن الجهاز Character Device.
   - تتحقق من صلاحية القراءة والكتابة.
3. إضافة `scripts/verify_android_emulator_host.sh` كفحص قبل الإقلاع:
   - يسجل نظام التشغيل والنواة وعدد الأنوية والذاكرة.
   - يشغّل `emulator -accel-check` ويوقف المهمة فورًا إذا لم يعمل التسريع.
   - يعيد تشغيل ADB ويسجل إصداره.
4. استخدام صورة أخف:
   - Android 15 / API 35.
   - `target: default` بدل `google_apis` لأن التطبيق لا يحتاج خدمات Google للاختبار.
   - `profile: pixel_2`.
   - نواتان، RAM 2048 MB، Heap 256 MB، Disk 4 GB.
   - `disable-linux-hw-accel: false` و`-accel on`.
5. خفض مهلة إقلاع المحاكي من 900 إلى 480 ثانية. عند فشل البنية التحتية يظهر الخطأ خلال دقائق، وليس بعد نصف ساعة.
6. بناء `app-debug.apk` و`app-debug-androidTest.apk` قبل تشغيل المحاكي؛ المحاكي مخصص الآن للتثبيت والاختبار واللقطات فقط.
7. الإبقاء على مهمة Runtime واحدة فقط، وعلى التثبيت المباشر عبر ADB وتشغيل `AndroidJUnitRunner` مباشرة.
8. إعادة ملفي العلامة التجارية المطلوبين:
   - `release/branding/Church-Prayers.ico`
   - `release/branding/Church-Prayers-icon-512.png`
9. إضافة `tests/conftest.py` حتى تكون استيرادات سكربتات الاختبار مستقلة عن ترتيب الملفات.

## الملفات الرئيسية المعدلة

- `.github/workflows/build.yml`
- `scripts/verify_android_emulator_host.sh`
- `scripts/run_android_emulator_ci.sh`
- `scripts/validate_workflows.py`
- `tests/conftest.py`
- `tests/test_r40_3_emulator_script.py`
- `tests/test_r40_release_automation.py`
- `tests/test_r40_automated_source_research.py`
- `tests/test_release_contract.py`
- `CHANGELOG.md`

## نتائج التحقق

- 426 اختبارًا ناجحًا.
- 14 اختبارًا فرعيًا ناجحًا.
- 65 اختبار Workflow/Release موجهًا ناجحًا.
- `validate_workflows.py`: ناجح.
- `validate_android_sdk_contract.py`: ناجح، `minSdk=26`, `targetSdk=36`, `compileSdk=36`, runtime API 35.
- التقويم الداخلي: 9,131 يومًا من 2026 إلى 2050.
- حدود السنوات: 24 انتقالًا و6 نوافذ سنوات كبيسة.
- فحوص المصادر والتوقيع واللغات والموارد والخدمات والصوم والبيانات المضمنة: ناجحة.
- فحص الأسرار: لا توجد مفاتيح خاصة أو بيانات اعتماد حرفية.

## السلوك المتوقع على GitHub

- إذا كان KVM غير متاح: تفشل خطوة التحقق مبكرًا مع ملف `emulator-accel-check.txt`، ولا تنتظر مهمة الإقلاع 30 دقيقة.
- إذا كان KVM متاحًا: يبدأ AVD الخفيف، ثم يثبت APK التطبيق وAPK الاختبارات، ويشغّل اختبارات عدم الاتصال ويلتقط صور العربية والإنجليزية واليونانية.
- لا يوجد سوى تطبيق واحد ومهمة Runtime واحدة.
