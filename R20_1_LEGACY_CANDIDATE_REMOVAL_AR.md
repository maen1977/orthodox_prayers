# R20.1 — حذف المرشح القديم من Git

سبب استمرار الفشل أن فك ZIP مع الاستبدال يضيف ويستبدل الملفات، لكنه لا يحذف الملفات القديمة المتتبعة في Git.

من جذر المستودع شغّل:

```powershell
powershell -ExecutionPolicy Bypass -File .\APPLY_R20_1_REMOVE_LEGACY_CANDIDATE.ps1
git add -A
git status --short
git commit -m "Remove legacy unsigned rolling candidate"
git push
```

أو باستخدام Python:

```bash
python APPLY_R20_1_REMOVE_LEGACY_CANDIDATE.py
git add -A
git status --short
git commit -m "Remove legacy unsigned rolling candidate"
git push
```

يجب أن يعرض `git status --short` سبعة ملفات محذوفة تحت:

`data/rolling-week/candidates/2026-07-28/`

ثم شغّل بوابة الجودة مجددًا.
