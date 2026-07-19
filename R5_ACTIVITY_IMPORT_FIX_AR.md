# إصلاح 5.0.1 R5 — استيراد Activity

## سبب الفشل

بعد تحويل `MainActivity` من `Activity` إلى `ComponentActivity` لإصلاح Predictive Back، بقي تنفيذ واجهة `ScreenHost` يحتوي:

```java
@Override public Activity activity() { return this; }
```

لكن استيراد `android.app.Activity` حُذف، لذلك فشل `compileDebugJavaWithJavac` برسالة `cannot find symbol: class Activity`.

## الإصلاح

أُعيد الاستيراد التالي إلى أعلى `MainActivity.java`:

```java
import android.app.Activity;
```

وبقيت آلية الرجوع الحديثة كما هي:

- `MainActivity extends ComponentActivity`
- `OnBackPressedDispatcher`
- `OnBackPressedCallback`
- لا يوجد `onBackPressed()` قديم

## التحقق

- نجاح 95/95 اختبار Python.
- نجاح فحص جدولة منتصف الليل والمحتوى والتوقيعات واللغات.
- نجاح فحص `quality_check.py`.
- تعذر تشغيل Gradle محليًا في بيئة التجهيز بسبب حجب DNS عن `services.gradle.org`، وليس بسبب الكود. سجل GitHub السابق وصل إلى هذا الخطأ الوحيد، وإضافة الاستيراد تعالجه مباشرة.
