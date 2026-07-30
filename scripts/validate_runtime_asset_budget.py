#!/usr/bin/env python3
"""Guard startup/runtime asset sizes so the lightweight app stays lightweight."""
from __future__ import annotations
import argparse, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'app/src/main/assets/data'
DEFAULT_MAX_STARTUP = 3_000_000
DEFAULT_MAX_SINGLE = 6_000_000

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--max-startup-bytes',type=int,default=DEFAULT_MAX_STARTUP)
    ap.add_argument('--max-single-asset-bytes',type=int,default=DEFAULT_MAX_SINGLE)
    a=ap.parse_args()
    startup=['today.json','service_coverage.json']
    startup_total=sum((ASSETS/n).stat().st_size for n in startup if (ASSETS/n).exists())
    largest=[]
    for p in ASSETS.rglob('*.json'):
        size=p.stat().st_size
        largest.append((size,p.relative_to(ROOT).as_posix()))
        if size>a.max_single_asset_bytes:
            raise SystemExit(f'ASSET_BUDGET_FAIL single={p} bytes={size} limit={a.max_single_asset_bytes}')
    if startup_total>a.max_startup_bytes:
        raise SystemExit(f'ASSET_BUDGET_FAIL startup_bytes={startup_total} limit={a.max_startup_bytes}')
    largest.sort(reverse=True)
    print(json.dumps({'status':'ok','startup_bytes':startup_total,'max_startup_bytes':a.max_startup_bytes,'largest_assets':[{'path':p,'bytes':s} for s,p in largest[:10]]},indent=2))
if __name__=='__main__': main()
