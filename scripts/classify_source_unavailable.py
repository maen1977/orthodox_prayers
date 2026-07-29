#!/usr/bin/env python3
"""Convert an expected official-source gap into a signed, non-failing update status."""
from __future__ import annotations
import argparse, json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
ROOT = Path(__file__).resolve().parents[1]
EXPECTED = "لم يتوفر مصدر أرثوذكسي رسمي صالح لجميع الحقول المطلوبة"

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--date', required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    report_path = ROOT / '.cache' / 'integrity-reports' / 'latest.json'
    if not report_path.is_file():
        raise SystemExit('Integrity report is missing; this is not a recognized source-unavailable result')
    report = json.loads(report_path.read_text(encoding='utf-8'))
    errors = report.get('errors')
    if not isinstance(errors, list) or not errors:
        raise SystemExit('Integrity failed without a classified official-source error')
    if any(EXPECTED not in str(error) for error in errors):
        raise SystemExit('Integrity contains a real validation error; refusing to downgrade it to a no-update status')
    payload = {
        'schema_version': 1,
        'date_iso': args.date,
        'status': 'NO_COMPLETE_OFFICIAL_SOURCE',
        'action': 'PRESERVE_LAST_SIGNED_DATA',
        'generated_at': datetime.now(ZoneInfo('Asia/Amman')).isoformat(),
        'errors': errors,
        'fail_closed': True,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Classified expected official-source gap for {args.date}')

if __name__ == '__main__':
    main()
