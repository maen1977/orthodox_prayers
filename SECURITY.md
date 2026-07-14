# Security Policy

## Sensitive reports

Do not publish passwords, API keys, Android signing material, data-signing private keys, permission documents, private source exports, or exploit details in a public issue. Report them privately to the repository owner.

## Daily-data integrity

- Daily JSON is accepted only after detached RSA/SHA-256 verification with the public key bundled in the app.
- Verification occurs before parsing and semantic validation.
- The app retains a signed last-known-good generation and rejects unsigned, malformed, future-dated, wrong-date, cross-language, or tampered updates.
- `DATA_SIGNING_PRIVATE_KEY_B64` must exist only in GitHub Secrets and encrypted offline backups.
- Key rotation requires an app release containing the new public key before new live data is signed with the new private key.

## Native religious-text integrity

- Display text is preserved as imported; normalization is restricted to a derived search index.
- Cross-language fallback, machine translation, AI rewriting, and automatic diacritization are prohibited.
- Partial Scripture passages are not published.
- Production release is blocked until native-content readiness validation succeeds.

## Android release integrity

- Android signing material belongs in the protected `production` Environment and encrypted offline backups.
- Release APKs must pass `apksigner verify`; APK/AAB artifacts include SHA-256 checksums.
- R8 and resource shrinking are enabled for release builds.
- GitHub Actions are pinned to full commit SHAs.
- GitHub Actions are pinned to full commit SHAs. Dependabot version updates and CodeQL are temporarily disabled while the first stable Android debug build is diagnosed; repository secret scanning remains mandatory.

## Repository protection

Protect `main`, require successful Build checks, and block force pushes. The Update workflow publishes only to `verified-data`, never directly to `main`.
