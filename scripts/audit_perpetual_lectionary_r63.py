#!/usr/bin/env python3
"""Audit the R63 perpetual reference bootstrap and its priority contract."""
from __future__ import annotations
import argparse, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'canonical/perpetual_lectionary_2026_2050.json'
CAL=ROOT/'canonical/internal_calendar_2026_2050.json'
EXACT=ROOT/'canonical/jordan_2026_h2_lectionary.json'
RECORDS=ROOT/'canonical/daily_lectionary_records.json'
COMMIT='393d5bb55d31bf14fa9c2a706e21c2f1bb48f400'


def load(p): return json.loads(p.read_text(encoding='utf-8'))

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--require-baseline',action='store_true'); a=ap.parse_args()
    if not BASE.is_file():
        if a.require_baseline: raise SystemExit('R63_LECTIONARY_AUDIT_FAIL baseline file missing')
        print('R63_LECTIONARY_AUDIT_SOURCE_MODE baseline_not_bootstrapped; GitHub build performs pinned network bootstrap')
        return
    b=load(BASE); c=b.get('coverage') or {}; errors=[]
    if (b.get('source') or {}).get('repository_commit') != COMMIT: errors.append('source commit is not pinned')
    if (b.get('civil_range') or {}).get('day_count') != 9131 or len(b.get('dates') or {}) != 9131: errors.append('baseline must cover 9131 civil days')
    if int(c.get('days_with_appointed_readings') or 0) < 8800: errors.append('too few days with appointed readings')
    if int(c.get('days_with_reading_day_resolution') or 0) != 9131: errors.append('every civil day must carry an explicit reading-day resolution')
    if int(c.get('days_with_epistle_reference') or 0) < 6500: errors.append('too few Epistle references')
    if int(c.get('days_with_gospel_reference') or 0) < 6500: errors.append('too few Gospel references')
    # A display reference can be valid even when the local public-domain Bible
    # corpus has no canonical ID for an LXX/deuterocanonical book.  Do not turn
    # that corpus limitation into a false liturgical failure; every such item
    # remains visible with its original display reference and is audited below.
    if int(c.get('reference_parse_failures') or 0) > 1500: errors.append('unexpectedly high number of unparsed appointed references')
    if any(not str(item.get('display_reference') or '').strip() for item in (b.get('parse_failures') or [])):
        errors.append('an unparsed baseline item lost its display reference')
    # Do not import saint stories/titles into the Jerusalem/Jordan commemoration lane.
    serialized=json.dumps(b,ensure_ascii=False)
    for forbidden in ('"stories"','"saints"','"summary_title"'):
        if forbidden in serialized: errors.append(f'forbidden non-Jerusalem commemoration payload leaked: {forbidden}')

    # Existing exact 2026 H2 evidence must stay authoritative after regeneration.
    cal=load(CAL); by={d['date_iso']:d for d in cal.get('days') or []}
    exact=load(EXACT); samples=['2026-07-28','2026-08-19','2026-12-31']
    exact_by={d['date_iso']:d for d in exact.get('days') or []}
    for iso in samples:
        if iso not in exact_by: continue
        expected=exact_by[iso].get('reading_references') or {}
        actual=(by.get(iso) or {}).get('reading_references') or {}
        if actual != expected: errors.append(f'pinned exact reference was overridden for {iso}')
        if (by.get(iso) or {}).get('reference_status') != 'PINNED_EXACT_DATE_REFERENCE': errors.append(f'exact priority status missing for {iso}')

    # A future ordinary date should come from the perpetual baseline after bootstrap.
    future=by.get('2035-08-14') or {}
    if not future.get('appointed_readings'): errors.append('future date lacks appointed readings after bootstrap')
    if future.get('reference_status') not in {'PERPETUAL_GREEK_JULIAN_REFERENCE_BASELINE','PINNED_FIXED_FEAST_REFERENCE'}:
        errors.append('future date did not receive baseline/fixed priority status')

    if errors:
        for e in errors: print('R63_LECTIONARY_AUDIT_FAIL',e)
        raise SystemExit(1)
    print('R63_LECTIONARY_AUDIT_OK ' + ' '.join(f'{k}={v}' for k,v in c.items()))
if __name__=='__main__': main()
