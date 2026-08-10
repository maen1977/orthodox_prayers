#!/usr/bin/env python3
"""Recompute the approved 2026-2050 calendar lock after an intentional source refresh."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
LOCK=ROOT/'canonical/calendar_2026_2050_lock.json'
CANONICAL=ROOT/'canonical/internal_calendar_2026_2050.json'
ASSET_DIR=ROOT/'app/src/main/assets/data/calendar'
LEGACY_H2_ASSET=ROOT/'app/src/main/assets/data/calendar_2026_h2.json'


def sha(raw: bytes)->str:
    return hashlib.sha256(raw).hexdigest()


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--approve-r63-perpetual-lectionary', action='store_true')
    args=ap.parse_args()
    if not args.approve_r63_perpetual_lectionary:
        raise SystemExit('Refusing to rewrite immutable calendar lock without --approve-r63-perpetual-lectionary')
    payload=json.loads(CANONICAL.read_text(encoding='utf-8'))
    civil=payload.get('civil_range') or {}
    if civil != {'start':'2026-01-01','end':'2050-12-31','day_count':9131}:
        raise SystemExit(f'Unexpected calendar range: {civil}')
    paths=[CANONICAL]+sorted(ASSET_DIR.glob('*.json'))
    # R39/R62 immutability also locks the legacy H2 compatibility asset.
    # Preserve it during approved R63 rewrites so the new updater never
    # silently weakens the historical lock contract.
    if LEGACY_H2_ASSET.is_file():
        paths.append(LEGACY_H2_ASSET)
    records=[]; lines=[]
    for path in paths:
        raw=path.read_bytes(); rel=path.relative_to(ROOT).as_posix(); digest=sha(raw)
        records.append({'path':rel,'bytes':len(raw),'sha256':digest})
        lines.append(f'{digest}  {rel}')
    aggregate=sha('\n'.join(lines).encode('utf-8'))
    lock={
      'schema_version':1,
      'policy':'IMMUTABLE_OFFLINE_CALENDAR_2026_2050_DO_NOT_REGENERATE_OR_EDIT',
      'civil_range':civil,
      'file_count':len(records),
      'aggregate_sha256':aggregate,
      'approved_change':'R63_PERPETUAL_GREEK_JULIAN_REFERENCE_BASELINE_WITH_JERUSALEM_JORDAN_OVERRIDES',
      'files':records,
    }
    LOCK.write_text(json.dumps(lock,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'CALENDAR_LOCK_R63_OK files={len(records)} aggregate_sha256={aggregate}')
if __name__=='__main__': main()
