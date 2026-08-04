# النشر الداخلي المغلق على Google Play

1. شغّل Workflow `Build` لإنتاج AAB موقع وناجح الاختبارات.
2. جهّز سر `PLAY_SERVICE_ACCOUNT_JSON` لحساب خدمة مخوّل للتطبيق.
3. شغّل Workflow `Play Internal Testing` وأدخل رقم تشغيل Build والإصدار.
4. اترك `publish=false` أول مرة للتحقق فقط، ثم أعد التشغيل مع `publish=true` داخل بيئة `play-internal` المحمية بالموافقة.
5. لا يُنقل الإصدار إلى الإنتاج قبل نجاح تقرير الأجهزة الحقيقية.

الرفع يتم عبر Google Play Developer API إلى مسار `internal`، ولا تدخل بيانات الاعتماد إلى المشروع أو ملفات البناء.
