# R64.2 — إصلاح مزامنة مراجع الكتاب المقدس حتى 2050

## سبب الفشل على GitHub
بعد أن أنهى R64.1 بناء القراءات المعيّنة لـ 9131/9131 يوم، تغيّرت مجموعة `canonical_reference` في ملفات التقويم. لكن الـWorkflow انتقل مباشرة إلى `run_local_daily_release_gate.py` من دون إعادة تشغيل `prepare_all_calendar_scripture_fallback.py`، فبقيت `supported_canonical_references` في ملفات Scripture manifest على المجموعة القديمة. أول لغة فحصها الـvalidator كانت العربية، ولذلك ظهر:

`LOCAL_DAILY_ENGINE_FAIL scripture_reference_manifest_drift:ar:missing=381:extra=0`

هذا فشل مزامنة، وليس فشل تغطية للتقويم أو القراءات.

## الإصلاح
- أضيفت خطوة GitHub مستقلة بعد `build_internal_calendar_2050.py` وقبل Release Gate.
- الخطوة تشغّل `prepare_all_calendar_scripture_fallback.py` على التقويم النهائي، وبالتالي تعيد توليد **الـverses والـmanifest معًا** للعربية والإنجليزية واليونانية من corpus أصلي native/public-domain، بلا ترجمة آلية.
- أضيف Cache مستقل لأرشيفات USFM الثلاثة حتى لا يعاد تنزيلها في كل Build.
- أضيف خيار `--archive-dir` للسكربت بدل الاعتماد على cache محلي مخفي فقط.
- بعد المزامنة يشغّل الـWorkflow `validate_local_daily_engine.py --date 2026-08-06` فورًا، لذلك أي drift جديد يتوقف في نفس الخطوة قبل Release Gate الكبير.
- أضيف regression test يثبت أن خطوة المزامنة تأتي بعد إعادة بناء التقويم وقبل Release Gate، وأن ملفات source/assets للـmanifest والـverses تظل متطابقة.

## قاعدة R64.2
لا يتم تعديل manifest وحده لإرضاء الاختبار. أي canonical reference جديد يجب أن يُحل إلى آيات أصلية في corpus اللغة نفسها، ثم يُكتب الـmanifest والـverses كزوج متطابق. إذا كانت آية مطلوبة غير موجودة في المصدر ولم تكن omission موثقة مسبقًا، يفشل البناء.
