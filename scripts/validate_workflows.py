#!/usr/bin/env python3
"""Validate the exactly-two-workflow GitHub Actions contract."""
from __future__ import annotations
import re
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[1]
WORKFLOW_DIR=ROOT/'.github/workflows'
EXPECTED={'build.yml','update.yml'}
FULL_SHA=re.compile(r'^[^@\s]+@[0-9a-f]{40}$')

def fail(message): raise SystemExit(message)

def main():
    files={p.name:p for p in WORKFLOW_DIR.glob('*.yml')}
    if set(files)!=EXPECTED: fail(f'Expected exactly {sorted(EXPECTED)}; found {sorted(files)}')
    for name,path in sorted(files.items()):
        text=path.read_text(encoding='utf-8')
        try: yaml.compose(text)
        except yaml.YAMLError as e: fail(f'Invalid YAML in {name}: {e}')
        if '\t' in text: fail(f'Tabs are not allowed in {name}')
        for action in re.findall(r'uses:\s*([^\s#]+)',text):
            if not FULL_SHA.match(action): fail(f'Action is not pinned to a full SHA in {name}: {action}')
    build=files['build.yml'].read_text(encoding='utf-8')
    for required in (
        'scripts/run_quality_gate.py --strict-native-lanes','wrapper-validation@','testDebugUnitTest lintDebug lintRelease',
        'assembleDebug bundleRelease','connectedDebugAndroidTest','SHA256SUMS.txt','chmod +x ./gradlew',
        'github/codeql-action/init@','github/codeql-action/analyze@','environment: production','ANDROID_KEYSTORE_B64',
        'assembleRelease bundleRelease','apksigner','RELEASE_VERSION','origin/verified-data',
        '--require-current --strict-native-lanes','Tag/version mismatch','publish_release'):
        if required not in build: fail(f'Build workflow is missing: {required}')
    update=files['update.yml'].read_text(encoding='utf-8')
    for required in (
        'name: 00:00 update, validate, sign, publish','name: 00:15 verify published update',
        'scripts/update_liturgical_data.py','scripts/orthodox_integrity.py --apply','scripts/enforce_native_daily_lanes.py',
        'scripts/build_search_index.py','scripts/validate_native_source_contract.py','scripts/validate_daily_native_content.py',
        'scripts/verify_published_daily.py','DATA_SIGNING_PRIVATE_KEY_B64','scripts/sign_daily_data.py',
        'VERIFIED_DATA_BRANCH: verified-data','HEAD:refs/heads/$VERIFIED_DATA_BRANCH','timezone: "Asia/Amman"',
        'cron: "0 0 * * *"','cron: "15 0 * * *"','Enforce independent native-language lanes','Trigger one repair attempt',
        'gh workflow run update.yml','Open or update failure alert'):
        if required not in update: fail(f'Update workflow is missing: {required}')
    for forbidden in ('git push origin main','HEAD:main','GEMINI_API_KEY','pull-requests: write'):
        if forbidden in update: fail(f'Update workflow contains forbidden behavior: {forbidden}')
    if not (ROOT/'.github/dependabot.yml').is_file(): fail('Dependabot configuration is missing')
    print('Workflow validation passed: exactly build.yml and update.yml, 00:00 update, 00:15 verification/repair, protected secrets, pinned actions')
if __name__=='__main__': main()
