#!/usr/bin/env python3
"""Build a compact category inventory from the R64 official-network harvest."""
from __future__ import annotations
import argparse, json
from collections import defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
HARVEST=ROOT/'canonical/r64_official_source_harvest.json'
OUT=ROOT/'canonical/r64_official_content_inventory.json'

CORE=('daily','calendar','fasting','readings','prayers','services','churches','monasteries','live','radio','library','schedule','events')

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--require-harvest',action='store_true'); a=ap.parse_args()
    if not HARVEST.is_file():
        if a.require_harvest: raise SystemExit('R64_OFFICIAL_INVENTORY_FAIL harvest missing')
        print('R64_OFFICIAL_INVENTORY_SOURCE_MODE harvest_not_present')
        return
    h=json.loads(HARVEST.read_text(encoding='utf-8')); groups=defaultdict(list)
    for doc in h.get('documents') or []:
        for cat in doc.get('categories') or []:
            if cat in CORE:
                groups[cat].append({k:doc.get(k) for k in ('url','title','content_type','sha256','root_ids')})
    out={
      'schema_version':1,
      'jurisdiction':h.get('jurisdiction'),
      'source_harvest_sha256':__import__('hashlib').sha256(HARVEST.read_bytes()).hexdigest(),
      'categories':{cat:{'count':len(groups.get(cat,[])),'documents':groups.get(cat,[])} for cat in CORE},
      'external_social_links':h.get('external_social_links') or [],
    }
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('R64_OFFICIAL_INVENTORY_OK ' + ' '.join(f'{k}={len(groups.get(k,[]))}' for k in CORE))
if __name__=='__main__': main()
