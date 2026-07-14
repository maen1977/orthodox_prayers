#!/usr/bin/env python3
"""Health check used by the 00:15 Asia/Amman verification run."""
from __future__ import annotations
import argparse, json, subprocess, sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[1]

def verify_status(expected: str) -> bool:
    payload = ROOT / 'data' / 'update-status' / f'{expected}.json'
    signature = ROOT / 'data' / 'update-status' / f'{expected}.json.sig'
    if not payload.is_file() or not signature.is_file():
        return False
    subprocess.run([sys.executable, 'scripts/verify_data_signature.py', str(payload), str(signature)], cwd=ROOT, check=True)
    data=json.loads(payload.read_text(encoding='utf-8'))
    if data.get('date_iso') != expected or data.get('status') != 'NO_COMPLETE_OFFICIAL_SOURCE':
        raise SystemExit('Published source-unavailable marker is invalid')
    if data.get('action') != 'PRESERVE_LAST_SIGNED_DATA' or data.get('fail_closed') is not True:
        raise SystemExit('Published source-unavailable marker does not preserve trusted data')
    print(f'Official sources were incomplete for {expected}; signed last-known-good preservation status verified')
    return True

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--expected-date'); args=parser.parse_args()
    expected=args.expected_date or datetime.now(ZoneInfo('Asia/Amman')).date().isoformat()
    data=json.loads((ROOT/'data/calendar/today.json').read_text(encoding='utf-8'))
    actual=str(data.get('date_iso') or '')
    if actual != expected:
        if verify_status(expected):
            return
        raise SystemExit(f'published date {actual!r} != expected {expected!r} and no signed preservation status exists')
    commands=[
      [sys.executable,'scripts/verify_data_signature.py'],
      [sys.executable,'scripts/validate_json_schema.py'],
      [sys.executable,'scripts/validate_native_source_contract.py'],
      [sys.executable,'scripts/validate_daily_native_content.py'],
      [sys.executable,'scripts/validate_official_sources.py'],
    ]
    for command in commands: subprocess.run(command,cwd=ROOT,check=True)
    print(f'Published signed native-language data verified for {expected}')
if __name__=='__main__': main()
