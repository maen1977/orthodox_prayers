# رفع Orthodox Prayers 3.5.0 بواسطة GitHub Desktop

1. افتح GitHub Desktop واختر **File → Add local repository**.
2. حدد مجلد `OrthodoxPrayers-v3.5.0-github-ready`.
3. إذا لم يكن مستودعًا بعد، اختر إنشاء Repository محلي داخل المجلد نفسه.
4. راجع تبويب **Changes** كاملًا قبل Commit.
5. تأكد من عدم ظهور أي ملف `.pem` خاص أو `.jks` أو كلمات مرور.
6. اكتب رسالة Commit مثل:

```text
Orthodox Prayers 3.5.0 strict native-language architecture
```

7. اختر **Publish repository** أو **Push origin**.
8. أضف GitHub Secrets حسب `GITHUB_SECRETS_AR.md`.
9. شغّل **Actions → Update → Run workflow** بوضع `update`.
10. راقب Workflowي `Build` و`Update` فقط.

لا تنشئ Tag إنتاجيًا حتى ينجح:

```bash
python scripts/validate_release_readiness.py
```
