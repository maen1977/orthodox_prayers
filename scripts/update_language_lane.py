#!/usr/bin/env python3
"""Extract and sign one independent native-language daily lane."""
from __future__ import annotations
import argparse, base64, copy, hashlib, json, subprocess, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
LANGS={"ar","el","en"}

def sign(path:Path,key:Path)->Path:
    sig=path.with_suffix(path.suffix+".sig")
    with tempfile.TemporaryDirectory() as d:
        raw=Path(d)/"sig.bin"
        subprocess.run(["openssl","dgst","-sha256","-sign",str(key),"-out",str(raw),str(path)],check=True)
        sig.write_bytes(base64.b64encode(raw.read_bytes())+b"\n")
    return sig

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--language",required=True,choices=sorted(LANGS)); ap.add_argument("--date",required=True); ap.add_argument("--private-key",required=True,type=Path); ap.add_argument("--source",default="data/calendar/today.json"); a=ap.parse_args()
    src=ROOT/a.source; data=json.loads(src.read_text(encoding="utf-8")); lang=a.language
    lane={k:copy.deepcopy(v) for k,v in data.items() if k not in {"readings","services","language_sources"}}
    lane.update({"lane_schema_version":1,"language":lang,"date_iso":a.date,"calendar_authority":"jerusalem_patriarchate","calendar":"julian_old_calendar","machine_translation_used":False,"automatic_diacritization_used":False})
    lane["language_source_policy"]=(data.get("language_sources") or {}).get(lang,{})
    lane["readings"]=[]
    for item in data.get("readings",[]):
        x={k:copy.deepcopy(v) for k,v in item.items() if k not in {"title","reference","body","source","native_source_verification"}}
        for field in ("title","reference","body","source"):
            val=item.get(field,{})
            x[field]=val.get(lang,"") if isinstance(val,dict) else val
        x["native_source_verification"]=(item.get("native_source_verification") or {}).get(lang,{})
        lane["readings"].append(x)
    out=ROOT/f"data/daily/{a.date}/{lang}.json"; out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(lane,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    current=ROOT/f"data/daily/current/{lang}.json"; current.parent.mkdir(parents=True,exist_ok=True); current.write_bytes(out.read_bytes())
    sign(out,a.private_key); sign(current,a.private_key)
    print(f"LANE_UPDATE_OK language={lang} date={a.date} readings={len(lane['readings'])}")
if __name__=='__main__': main()
