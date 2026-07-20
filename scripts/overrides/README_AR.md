# توثيق الصوم الانقطاعي اليومي

لا يضع التطبيق ساعات صوم انقطاعي تلقائيًا. عند وجود إعلان رسمي موثق ليوم محدد، يمكن لملف
`scripts/overrides/YYYY-MM-DD.json` أن يستبدل كائن `fasting` كاملًا.

يشترط الصوم الانقطاعي:

- `abstinence.applies = true`
- نوعًا موثقًا: `documented_interval` أو `until_communion` أو `until_service_end`
- مصدرًا صريحًا في `abstinence.verification.source`
- الحالة `DOCUMENTED_OVERRIDE`
- وقتي `start_time` و`end_time` بصيغة `HH:MM` عند استعمال `documented_interval`
- نصوصًا عربية وإنجليزية ويونانية لشرط الانتهاء والتفصيل

مثال البنية فقط:

```json
{
  "fasting": {
    "code": "strict",
    "abstinence": {
      "applies": true,
      "kind": "documented_interval",
      "start_time": "00:00",
      "end_time": "15:00",
      "end_condition": {
        "ar": "ينتهي وفق الإعلان الرسمي الموثق لهذا اليوم.",
        "en": "Ends according to the documented official notice for this day.",
        "el": "Λήγει σύμφωνα μὲ τὴν τεκμηριωμένη ἐπίσημη ἀνακοίνωση τῆς ἡμέρας."
      },
      "detail": {
        "ar": "امتناع كلي عن الطعام والشراب خلال الفترة الموثقة.",
        "en": "Total abstinence from food and drink during the documented interval.",
        "el": "Πλήρης ἀποχὴ ἀπὸ τροφὴ καὶ ποτὸ κατὰ τὸ τεκμηριωμένο διάστημα."
      },
      "verification": {
        "status": "DOCUMENTED_OVERRIDE",
        "source": "رابط أو مرجع الإعلان الرسمي"
      }
    }
  }
}
```

يجب أن يتضمن كائن `fasting` بقية الحقول الكاملة أيضًا. يرفض النظام الساعة المكتوبة دون مصدر، أو الوقت غير المكتوب بصيغة `HH:MM`.
