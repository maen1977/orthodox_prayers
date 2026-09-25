from __future__ import annotations
import importlib.util, json, sys, tempfile, unittest
from datetime import date
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def load():
 p=ROOT/"scripts/update_liturgical_data.py"; spec=importlib.util.spec_from_file_location("local_comm_test",p); m=importlib.util.module_from_spec(spec); sys.modules[spec.name]=m; spec.loader.exec_module(m); return m
class LocalCommemorationTests(unittest.TestCase):
 def test_clear_unavailable_wording(self):
  m=load(); self.assertIn("تعذّر التحقق",m.UNAVAILABLE_DAILY_FEAST["ar"]); self.assertNotIn("المراجعة الكنسية",m.UNAVAILABLE_DAILY_FEAST["ar"])
 def test_verified_local_record_has_priority(self):
  m=load(); old=m.LOCAL_COMMEMORATIONS_PATH
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/"local.json"; p.write_text(json.dumps({"records":{"2026-08-01":{"verification_status":"LOCAL_OFFICIAL_SOURCE_VERIFIED","commemorations":{"ar":"تذكار محلي موثق","en":"Verified local commemoration","el":"Τοπικὴ μνήμη"}}}},ensure_ascii=False),encoding="utf-8")
   m.LOCAL_COMMEMORATIONS_PATH=p
   try:
    info=m.day_info(date(2026,8,1)); self.assertEqual("تذكار محلي موثق",info["feast_ar"]); self.assertEqual("Verified local commemoration",info["feast_en"]); self.assertEqual("Τοπικὴ μνήμη",info["feast_el"]); self.assertEqual("LOCAL_OFFICIAL_SOURCE_VERIFIED",info["feast_status"])
   finally: m.LOCAL_COMMEMORATIONS_PATH=old
 def test_arabic_only_record_does_not_copy_across_language_lanes(self):
  m=load(); old=m.LOCAL_COMMEMORATIONS_PATH
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/"local.json"; p.write_text(json.dumps({"records":{"2026-08-01":{"verification_status":"LOCAL_OFFICIAL_SOURCE_VERIFIED","commemorations":{"ar":"تذكار عربي موثق"}}}},ensure_ascii=False),encoding="utf-8")
   m.LOCAL_COMMEMORATIONS_PATH=p
   try:
    info=m.day_info(date(2026,8,1)); self.assertEqual("تذكار عربي موثق",info["feast_ar"]); self.assertNotEqual("تذكار عربي موثق",info["feast_en"]); self.assertNotEqual("تذكار عربي موثق",info["feast_el"])
   finally: m.LOCAL_COMMEMORATIONS_PATH=old
if __name__=="__main__": unittest.main()
