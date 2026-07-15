#!/usr/bin/env python3
from __future__ import annotations
import argparse,base64,json,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; PUB=ROOT/'canonical/signing/data_signing_public_key.pub'
def verify(p,s):
 raw=base64.b64decode(s.read_bytes().strip(),validate=True)
 with tempfile.TemporaryDirectory() as d:
  r=Path(d)/'s';r.write_bytes(raw)
  x=subprocess.run(['openssl','dgst','-sha256','-verify',str(PUB),'-signature',str(r),str(p)],capture_output=True,text=True)
  if x.returncode: raise SystemExit(f'lane signature invalid: {p}: {x.stderr}')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--date',required=True);ap.add_argument('--language',choices=['ar','el','en']);a=ap.parse_args()
 langs=[a.language] if a.language else ['ar','el','en']
 for l in langs:
  for p in [ROOT/f'data/daily/{a.date}/{l}.json',ROOT/f'data/daily/current/{l}.json']:
   if not p.is_file(): raise SystemExit(f'missing lane: {p}')
   j=json.loads(p.read_text(encoding='utf-8'))
   if j.get('date_iso')!=a.date or j.get('language')!=l: raise SystemExit(f'lane metadata invalid: {p}')
   if j.get('machine_translation_used') is not False: raise SystemExit(f'translation flag invalid: {p}')
   verify(p,Path(str(p)+'.sig'))
 print('LANGUAGE_LANES_OK '+','.join(langs))
if __name__=='__main__':main()
