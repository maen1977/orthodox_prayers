#!/usr/bin/env python3
"""Health check used by the 00:15 Asia/Amman verification run."""
from __future__ import annotations
import argparse, json, subprocess, sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--expected-date'); args=parser.parse_args()
    expected=args.expected_date or datetime.now(ZoneInfo('Asia/Amman')).date().isoformat()
    data=json.loads((ROOT/'data/calendar/today.json').read_text(encoding='utf-8'))
    actual=str(data.get('date_iso') or '')
    if actual != expected: raise SystemExit(f'published date {actual!r} != expected {expected!r}')
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
