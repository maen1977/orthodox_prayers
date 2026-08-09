# R58.1 — إصلاح AAPT2 لمورد تذكار اليوم

الإصدار: **5.6.4** (`50604`)

## المشكلة

فشل GitHub Actions في `:app:mergeDebugResources` لأن مورد اللغة الإنجليزية
`ui_today_commemoration_home_format` استخدم كيان XML `&apos;`. بعد فك الكيان،
يتعامل AAPT2 مع الفاصلة العليا ASCII وفق قواعد Android الخاصة بالهروب، فظهر الخطأ
`Invalid unicode escape sequence in string`.

## الإصلاح

- استبدال `Today&apos;s` بـ `Today’s` باستخدام الفاصلة العليا الطباعية U+2019.
- إضافة فحص إلى `validate_android_resources.py` يمنع `&apos;` داخل مجلدات `values*`.
- إضافة اختبار regression ضمن R58.
- إدخال اختبارات R58 وAndroid resources في Release Gate الرئيسي.

لا يتغير أي نص ليتورجي أو بيانات تذكارات أو منطق الصوم في هذا الإصلاح.
