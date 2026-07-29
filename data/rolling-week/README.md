# Rolling-week update candidates

`candidates/YYYY-MM-DD/` contains a fully validated **unsigned** package for the
start date plus seven future days. It is deliberately not copied over the
currently trusted embedded/signed daily package.

The protected release workflow must:

1. regenerate or validate the candidate;
2. produce independent `ar`, `en`, and `el` lanes;
3. sign each lane and the update manifest with the existing private release key;
4. publish only after `validate_rolling_week.py` and signature verification pass.

Never add a test key or bypass signature verification in the Android client.
