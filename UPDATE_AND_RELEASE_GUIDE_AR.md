# دليل التحديث والنشر الآمن لتطبيق الصلوات

**تاريخ التحقق:** 2026-08-24
**applicationId الحالي:** `com.orthodoxprayers.privateapp`
**versionCode الحالي في Gradle:** `50606`
**versionName الحالي:** `5.6.6`

## الخلاصة العملية

يمكن تثبيت النسخة الجديدة فوق النسخة القديمة **من دون حذفها** عندما تكون `applicationId` نفسها، ويكون `versionCode` الجديد أعلى، وتكون شهادة التوقيع نفسها أو ضمن signing lineage صالح. عند تحقق هذه الشروط، ينفذ Android التحديث في مكانه ويحافظ على بيانات التطبيق. وثائق Android الرسمية تذكر هذه الشروط صراحةً [1] [2] [3].

أما APK debug المحلي أو APK مبني بمفتاح مختلف فلا يمكن اعتباره ترقية لنسخة production أو Play Store؛ سيظهر غالبًا خطأ تعارض في الشهادة، وحذف النسخة القديمة ليس حلًا آمنًا لأنه يحذف بيانات التطبيق. التطبيق لا ينبغي أن يحذف نفسه تلقائيًا، وAndroid لا يتيح تحويل اختلاف التوقيع إلى تحديث آمن.

## ما يحدث عند النشر على Google Play

يجب رفع **AAB release** بنفس `applicationId` إلى Play Console، مع الحفاظ على Play App Signing والإجراء الصحيح لتسليم مفتاح الرفع. يجب زيادة `versionCode` في كل إصدار. بعد ذلك يدير Google Play التحديثات وفق حساب المستخدم وإعداداته وسياسات الجهاز والاتصال؛ قد تكون تلقائية إذا كان المستخدم أو الجهاز يسمح بذلك، لكنها ليست وعدًا بأن كل جهاز سيحدّث فورًا أو دون موافقة.

توجد أيضًا Play In-App Updates بواجهتي Flexible وImmediate، لكنها تعمل عبر Google Play للمستخدم النشط، وليست بديلًا لمفتاح توقيع production ولا حلًا لنسخ GitHub. لم أضف dependency أو واجهة جديدة الآن لأن التطبيق غير منشور في Play ضمن الأدلة الحالية، ولأن المستخدم طلب عدم تغيير الواجهة والمنطق بلا حاجة. يمكن إضافتها لاحقًا بعد نشر Play واختبار مسار AAB الحقيقي [4].

## خياران صالحان للنشر

| النهج | المفاضلة | التكلفة | تعقيد الإعداد |
| --- | --- | --- | --- |
| **Play Store مع Play App Signing** | أفضل تجربة للمستخدم؛ المتجر يدير التنزيل والتحديث وفق الإعدادات. لا يغطي APKs الجانبية من GitHub تلقائيًا. | لا توجد خدمة polling داخل التطبيق؛ يلزم إعداد Play ومفتاح التوقيع. | متوسط مرة واحدة، ثم إصدار AAB ورفع `versionCode`. |
| **GitHub updater الحالي + Play Store لاحقًا** | يبقي التحديث خارج Play متاحًا مع HTTPS وSHA-256 وفحص package/version/certificate، لكن تثبيت APK يحتاج تأكيد المستخدم من Android. لا يجوز تثبيت صامت أو حذف القديم. | صيانة manifest/checksum/release؛ لا ضمان تثبيت تلقائي خارج Play. | أعلى قليلًا؛ يجب توقيع كل Release بالمفتاح الإنتاجي نفسه. |

النهج الآمن الحالي هو الاحتفاظ بالـupdater الموجود للنسخ الجانبية وعدم تسميته «تحديثًا تلقائيًا كاملًا»، ثم استخدام Play Store للتثبيتات المنشورة. لا ينبغي توزيع APK debug على الناس بوصفه إصدار ترقية.

## قائمة إصدار لا تكسر النسخ القديمة

| الفحص | المطلوب قبل النشر |
| --- | --- |
| هوية الحزمة | عدم تغيير `com.orthodoxprayers.privateapp`. تغييرها يصنع تطبيقًا جديدًا في Play. |
| التوقيع | توقيع release بالمفتاح الإنتاجي نفسه أو signing lineage صالح؛ لا تستخدم debug keystore. |
| رقم الإصدار | زيادة `versionCode` monotonically؛ `versionName` للعرض فقط. |
| نوع الملف | Play: AAB release؛ GitHub side-load: APK release موقّع بالمفتاح نفسه. |
| البيانات | لا حذف تلقائي؛ التحديث in-place يحافظ على البيانات عند تحقق الشروط. |
| التحقق المحلي | `apksigner verify --print-certs` على القديم والجديد، ثم مقارنة certificate SHA-256. |

## نتيجة الفحص المحلي الحالي

الحزم المحلية الموجودة ليست production reference موحدًا. APKs المتاحة تحمل شهادات debug مختلفة، مثل `Android Debug` مع بصمات مختلفة، والـrelease المحلي غير الموقّع لا يصلح للتثبيت. لذلك لا أستطيع إثبات توافق النسخة الجديدة مع APK الناس أو Play Store دون APK production القديم أو شهادة Play App Signing/بيانات Play Console. هذا ليس نقصًا في updater؛ إنه شرط أمان Android.

## المراجع

[1]: https://developer.android.com/google/play/app-updates "Android Developers — How app updates work"
[2]: https://developer.android.com/build/configure-app-module "Android Developers — Configure the app module"
[3]: https://developer.android.com/studio/publish/versioning "Android Developers — Version your app"
[4]: https://developer.android.com/guide/playcore/in-app-updates "Android Developers — In-app updates"
