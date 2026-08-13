# تعديل بطاقة الصوم — R66

تم تبسيط المسار الذي يبدأ من بطاقة الصوم في الشاشة الرئيسية.

كما تم إصلاح import الناقص في `MainActivity.java` الذي كان يمنع GitHub Actions من التعرف على `FastingSummaryScreen` أثناء ترجمة Java.

عند الضغط على البطاقة، تفتح الآن شاشة **تفاصيل الصوم** المختصرة بدل شاشة تفاصيل يوم التقويم العامة. تعرض الشاشة اسم أو نوع الصوم، فترة الصوم، عدد الأيام، وما هو مسموح به وما هو ممنوع بحسب بيانات التقويم الموقعة والمضمّنة في التطبيق.

بقيت شاشة تفاصيل يوم التقويم الكاملة متاحة عند الدخول من التقويم نفسه، كما بقيت شاشة **التقويم والصيام** دون تغيير.

## الملفات الرئيسية المعدلة

- `app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/HomeScreen.java`
- `app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/FastingSummaryScreen.java`
- `app/src/main/java/com/orthodoxprayers/privateapp/MainActivity.java`
- `app/src/main/res/values/ui_strings.xml`
- `app/src/main/res/values-en/ui_strings.xml`
- `app/src/main/res/values-el/ui_strings.xml`
- اختبارات المسار في مجلد `tests/`

## التحقق

تم تشغيل اختبارات Python الكاملة من جذر المشروع باستخدام `PYTHONPATH=.` وكانت النتيجة: **662 اختبارًا ناجحًا و14 اختبارًا فرعيًا ناجحًا**.

بعد إصلاح import، ينبغي إعادة تشغيل أمر Gradle الموجود في سجل GitHub للتأكد من إكمال البناء والـ lint وإنشاء ملفات الإصدار.

لم يكتمل بناء Android عبر Gradle داخل بيئة الفحص لأن Android SDK غير مثبت فيها. لذلك يجب تنفيذ البناء النهائي في بيئة Android/CI التي تحتوي على Android SDK مناسب.
