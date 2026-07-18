# بناء Orthodox Prayers 5.0.0

## المتطلبات

- JDK 17.
- Android SDK 36.
- اتصال يسمح بتنزيل Gradle 8.13 والاعتماديات المثبتة في المشروع.

## فحص المصدر

```bash
python -m pip install -r requirements-dev.txt
python scripts/run_quality_gate.py --require-current --strict-native-lanes
python scripts/validate_release_readiness.py
```

## بناء Debug

```bash
./gradlew --no-daemon testDebugUnitTest lintDebug assembleDebug
```

## بناء الإصدار الموقّع

يجب توفير المتغيرات التالية دون وضع أسرار داخل المستودع:

```text
ANDROID_KEYSTORE_FILE
ANDROID_KEYSTORE_PASSWORD
ANDROID_KEY_ALIAS
ANDROID_KEY_PASSWORD
```

ثم:

```bash
./gradlew --no-daemon clean testDebugUnitTest lintRelease assembleRelease bundleRelease
```

## إنشاء حزمة مصدر نظيفة

```bash
python scripts/create_clean_source_archive.py OrthodoxPrayers-5.0.0-source.zip
```

يُنشأ تلقائيًا ملف `OrthodoxPrayers-5.0.0-source.zip.sha256`.
