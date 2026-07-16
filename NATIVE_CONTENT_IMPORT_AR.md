# استيراد النصوص الدينية الأصلية المعتمدة

## قاعدة الاستيراد

كل لغة مستقلة. الملف العربي لا يُنشأ من الإنجليزية أو اليونانية، والإنجليزي لا يُنشأ من العربية، واليوناني لا يُنشأ من لغة أخرى.

الممنوع:

- الترجمة الآلية أو البشرية بين مسارات التطبيق.
- توليد النص أو إعادة صياغته بالذكاء الاصطناعي.
- إضافة التشكيل العربي أو النبرات اليونانية آليًا.
- التصحيح الصامت للنص الديني.
- نسخ نص جزئي وإعلانه كاملًا.

## 1. تسجيل المصدر

يجب أن يكون `source_id` موجودًا في:

```text
canonical/source_native_contract.json
canonical/native_language_sources.json
```

ويجب أن يطابق لغة النص ونطاق الموقع الرسمي.

## 2. استيراد حزمة خدمات

ملف الحزمة يجب أن يحتوي لغة واحدة فقط، مع حقول اللغتين الأخريين فارغة. ثم:

```bash
python scripts/install_authorized_native_pack.py --input authorized-library-en.json
python scripts/validate_native_language_packs.py
python scripts/build_search_index.py
```

لا تستخدم `--require-complete` إلا عند تجهيز الحزمة النهائية كاملة.

## 3. استيراد مكتبة الكتاب المقدس

جهّز JSON خارج المستودع بهذا الشكل:

```json
{
  "language": "el",
  "source_id": "church_of_greece_apostoliki_diakonia",
  "source_url": "https://apostoliki-diakonia.gr/...",
  "retrieved_at": "2026-07-14T00:00:00+03:00",
  "verses": [
    {
      "book_id": "MAT",
      "book_name": "Κατὰ Ματθαῖον",
      "chapter": 1,
      "verse": 1,
      "text": "ΤΟ ΑΚΡΙΒΕΣ ΚΕΙΜΕΝΟ ΤΗΣ ΠΗΓΗΣ"
    }
  ]
}
```

ثم:

```bash
python scripts/import_native_scripture_corpus.py /secure/greek-scripture.json
python scripts/build_search_index.py
python scripts/validate_native_source_contract.py
```

للاستبدال المقصود لمكتبة سبق استيرادها:

```bash
python scripts/import_native_scripture_corpus.py /secure/greek-scripture.json --replace

# لمصدر عام الملكية ومسجل في العقد
python scripts/import_native_scripture_corpus.py /secure/greek-scripture.json --replace --corpus-kind public-domain
```

الأداة تحفظ كل آية كما هي، وتحسب بصمتها، وترفض المصدر أو الأبجدية غير المطابقة. ملف المصدر الخام ووثائق الإذن يبقيان خارج المستودع العام.

## 4. تحديث اليوم

Workflow `Update` ينفذ بالترتيب:

1. يجلب مراجع اليوم من المصادر الرسمية.
2. يطلب لكل لغة دليل مرجع يومي من مصدر تابع لمسار اللغة نفسها.
3. يبحث عن المقطع الكامل داخل مكتبة الكتاب المقدس الأصلية لنفس اللغة.
4. يرفض نشر المقطع إذا كانت آية واحدة ناقصة.
5. يطبق سياسة الفصل، ويبني فهرس البحث، ثم يوقع البيانات.

## 5. فحص Production

```bash
python scripts/validate_release_readiness.py
```

ينجح عند اكتمال حزم الخدمات وتوافر نص الرسالة والإنجيل في اللغات الثلاث. لفحص مرشح غير موقع دون تغيير البيانات الموقعة الحالية:

```bash
python scripts/validate_release_readiness.py --daily-path data/calendar/candidates/2026-07-16.json
```

## 6. دمج دفعة جزئية مصرّح بها

إذا وصل ملف رسمي يغطي بعض الحقول الناقصة فقط، لا يلزم استبدال الحزمة كاملة. استخدم:

```bash
python scripts/merge_authorized_native_services.py --input /secure/authorized-en.json
python scripts/merge_authorized_native_services.py --input /secure/authorized-el.json
python scripts/build_search_index.py
python scripts/validate_native_language_packs.py
python scripts/validate_native_source_contract.py
```

الأداة ترفض الترجمة بين المسارات، والنص ذي الأبجدية الخاطئة، والمصدر غير المسجل، والملف الذي لا يحمل بيانات إذن واضحة. وهي لا تستبدل نصًا موجودًا إلا عند تمرير خيار الاستبدال المقصود وفق تعليماتها.

## 7. تقارير الحقول الناقصة

```bash
python scripts/export_missing_native_fields.py --language en --output docs/native_missing_en.json
python scripts/export_missing_native_fields.py --language el --output docs/native_missing_el.json
```

التقريران يحددان كل خدمة ومقطع وحقل مطلوب، ويمكن تسليمهما للمراجع أو الجهة المالكة للمصدر دون خلط اللغات أو تخمين النصوص.
