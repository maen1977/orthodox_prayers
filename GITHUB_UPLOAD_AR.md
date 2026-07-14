# رفع المشروع إلى GitHub لأول مرة

## بواسطة موقع GitHub وGit

1. أنشئ مستودعًا جديدًا فارغًا، ولا تضف README أو License لأنهما موجودان.
2. افتح Terminal داخل مجلد المشروع.
3. نفّذ:

```bash
git init
git branch -M main
git add .
git status
git commit -m "Orthodox Prayers 3.5.0 strict native-language architecture"
git remote add origin YOUR_REPOSITORY_URL
git push -u origin main
```

4. قبل `git commit` افحص `git status` وتأكد من عدم وجود:
   - `.jks` أو `.keystore` أو `.pem` خاص.
   - ملفات كلمات مرور أو `.env`.
   - مجلد `authorized-source-snapshots/`.
   - وثائق الموافقات الخاصة.
5. أضف الأسرار حسب `GITHUB_SECRETS_AR.md`.
6. شغّل Workflow `Update` يدويًا أول مرة.
7. تأكد من نجاح Workflow `Build` ومن ظهور فرع `verified-data`.

## فحص أمان قبل الرفع

```bash
python scripts/scan_repository_secrets.py
python scripts/run_quality_gate.py --strict-native-lanes
```

إذا ظهر المفتاح الخاص في أي Commit فلا يكفي حذفه من آخر نسخة؛ يجب تدوير المفتاح وتنظيف السجل قبل جعل المستودع عامًا.
