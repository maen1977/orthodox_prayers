Orthodox Prayers — one-shot CI fix

1. Extract this ZIP.
2. Open PowerShell in the orthodox_prayers repository root.
3. Run:

   powershell -ExecutionPolicy Bypass -File "<extracted-folder>\apply_and_verify.ps1"

What it fixes:
- validate_native_source_contract.py previously accepted only source IDs already present
  in canonical/source_native_contract.json.
- The current packs also contain exact owner-confirmed or public-domain recovered
  sources with strict embedded provenance.
- The replacement validator accepts those sources only when source ID, language,
  permission/public-domain status, machine-translation flag, and URL host all agree.

The script then runs the complete strict quality gate, git diff checks, commit, and push.
