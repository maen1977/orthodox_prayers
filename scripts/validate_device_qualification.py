#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser(); p.add_argument('--matrix',type=Path,default=ROOT/'config/device-qualification-matrix.json'); p.add_argument('--results',type=Path); p.add_argument('--require-physical',action='store_true'); p.add_argument('--report',type=Path)
    a=p.parse_args(); matrix=json.loads(a.matrix.read_text(encoding='utf-8'))
    errors=[]
    apis=[int(x['api']) for x in matrix.get('automated_emulators',[])]
    if apis != sorted(set(apis)) or apis[0] != 26 or apis[-1] < 35: errors.append('emulator matrix must cover unique ordered APIs from 26 through current Android')
    result={'schema_version':1,'status':'PASS','automated_apis':apis,'physical_required':a.require_physical}
    if a.require_physical:
        if not a.results or not a.results.is_file(): errors.append('physical device results are required for production')
        else:
            payload=json.loads(a.results.read_text(encoding='utf-8')); rows=payload.get('devices',[])
            for target in matrix.get('physical_device_targets',[]):
                if not target.get('required_for_production'): continue
                count=sum(1 for row in rows if row.get('class')==target['class'] and row.get('status')=='PASS')
                if count < int(target['minimum_devices']): errors.append(f"missing passing physical device class: {target['class']}")
            result['physical_results']=rows
    if errors: result['status']='FAIL'; result['errors']=errors
    if a.report: a.report.parent.mkdir(parents=True,exist_ok=True); a.report.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print('DEVICE_QUALIFICATION_'+result['status']+' apis='+','.join(map(str,apis)))
    if errors: raise SystemExit('; '.join(errors))
if __name__=='__main__': main()
