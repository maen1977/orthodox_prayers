# إصلاح تجميع HomeScreen — الإصدار 5.0.11 R15

كان `HomeScreen.java` يستخدم الثوابت `ThemePalette.NAVY` و`ThemePalette.GOLD` في بطاقة الأحد القادم دون استيراد الصنف `ThemePalette`.

تمت إضافة:

```java
import com.orthodoxprayers.privateapp.ui.ThemePalette;
```

لم يتغير محتوى الرسالة أو الإنجيل أو القداس أو الصوم أو تصميم البطاقة؛ الإصلاح خاص بتجميع Java فقط.

أضيف اختبار يمنع حذف الاستيراد مستقبلًا، وأداة تحقق `scripts/verify_r15_patch.py`.
