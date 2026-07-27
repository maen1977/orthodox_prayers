from __future__ import annotations
import hashlib, importlib.util, json, sys, unittest
from datetime import date
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; LANGS=("ar","en","el"); TARGETS=("2026-06-07","2026-06-14")
def load(name,rel):
 p=ROOT/rel; spec=importlib.util.spec_from_file_location(name,p); m=importlib.util.module_from_spec(spec); assert spec and spec.loader; sys.modules[name]=m; spec.loader.exec_module(m); return m
class R21Phase13Tests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.update=load("p13_update","scripts/update_liturgical_data.py"); cls.audit=load("p13_audit","scripts/build_liturgy_year_audit.py"); cls.gate=load("p13_gate","scripts/validate_liturgy_phase13_completion.py")
  cls.dates=json.loads((ROOT/"canonical/dated_liturgical_propers.json").read_text(encoding="utf-8"))["dates"]
 def test_phase13_dates_are_registered(self):
  for d in TARGETS: self.assertIn(d,self.dates)
 def test_all_saints_cycle_and_readings_are_exact(self):
  e=self.dates["2026-06-07"]; self.assertEqual((1,8,1),(e["sunday_after_pentecost"],e["resurrection_tone"],e["eothinon"])); self.assertEqual("Matthew 28:16-20",e["matins_gospel_reference"]); self.assertEqual("Hebrews 11:33-40; 12:1-2",e["readings"]["epistle"]["canonical_reference"]); self.assertEqual("Matthew 10:32-33, 37-38; 19:27-30",e["readings"]["gospel"]["canonical_reference"])
 def test_second_sunday_cycle_and_readings_are_exact(self):
  e=self.dates["2026-06-14"]; self.assertEqual((2,1,2),(e["sunday_after_pentecost"],e["resurrection_tone"],e["eothinon"])); self.assertEqual("Mark 16:1-8",e["matins_gospel_reference"]); self.assertEqual("Romans 2:10-16",e["readings"]["epistle"]["canonical_reference"]); self.assertEqual("Matthew 4:18-23",e["readings"]["gospel"]["canonical_reference"])
 def test_all_new_readings_have_three_native_lanes(self):
  for ds in TARGETS:
   for r in self.dates[ds]["readings"].values():
    for lane in ("reference","body"): self.assertTrue(all(str(r[lane][x]).strip() for x in LANGS),(ds,lane))
    for lang in LANGS: self.assertEqual("IMPORTED_EXACT_PUBLIC_DOMAIN_NATIVE_CORPUS",r["native_source_verification"][lang]["status"])
 def test_reading_and_verse_hashes_match_display_text(self):
  for ds in TARGETS:
   for r in self.dates[ds]["readings"].values():
    for lang in LANGS:
     v=r["native_source_verification"][lang]; text=r["body"][lang]; lines=text.splitlines()
     self.assertEqual(hashlib.sha256(text.encode()).hexdigest(),v["text_sha256"]); self.assertEqual(len(lines),v["verse_count"]); self.assertEqual([hashlib.sha256(x.encode()).hexdigest() for x in lines],v["verse_hashes"])
 def test_display_text_has_no_technical_markup(self):
  for ds in TARGETS:
   for r in self.dates[ds]["readings"].values():
    for text in r["body"].values():
     for token in (r"\+w","|strong=","cite"): self.assertNotIn(token,text)
 def test_all_saints_has_special_propers_in_three_languages(self):
  e=self.dates["2026-06-07"]
  for slot in ("troparion","kontakion","communion"): self.assertTrue(all(str(e[slot][x]).strip() for x in LANGS),slot)
  self.assertTrue(all(str(e["prokeimenon"]["body"][x]).strip() for x in LANGS)); self.assertIn("شُهَدائِكَ",e["troparion"]["ar"])
 def test_new_dates_resolve_complete_in_audit(self):
  for ds in TARGETS:
   row=self.audit.audit_day(self.update,date.fromisoformat(ds)); self.assertTrue(row["complete_for_release"],(ds,row["blockers"]))
 def test_all_saints_uses_special_prokeimenon_and_communion(self):
  d=date(2026,6,7); info=self.update.day_info(d); readings=self.update.discovery_readings(d,info); inserts=self.update.feast_inserts(info,d)
  prok=next(r for r in readings if r.get("kind")=="prokeimenon"); self.assertIn("saints",prok["title"]["en"].lower()); self.assertIn("righteous",inserts["communion"]["en"].lower())
 def test_second_sunday_uses_tone_one_prokeimenon(self):
  d=date(2026,6,14); info=self.update.day_info(d); readings=self.update.discovery_readings(d,info); prok=next(r for r in readings if r.get("kind")=="prokeimenon"); self.assertEqual(1,prok["tone"])
 def test_phase13_audit_covers_year_and_reaches_nine_days(self):
  r=self.audit.build_report(2026,phase="R21_PHASE13"); self.assertEqual(365,r["audited_days"]); self.assertFalse(r["network_fetch_used"]); self.assertGreaterEqual(r["complete_days"],9)
 def test_interpretations_remain_removed_and_previous_dates_preserved(self):
  c=json.loads((ROOT/"canonical/liturgy_phase13_completion_contract.json").read_text(encoding="utf-8")); self.assertFalse(c["scope"]["interpretations"]); self.assertEqual(list(TARGETS),c["dated_coverage_added"])
  for ds in c["dated_coverage_preserved"]: self.assertIn(ds,self.dates)
 def test_phase13_gate_remains_fail_closed_for_remaining_year(self):
  r=self.gate.build_report(); self.assertTrue(r["interpretations_removed"]); self.assertTrue(all(r["target_dates_complete"].values())); self.assertFalse(r["complete_release_allowed"]); self.assertIn("phase13_annual_daily_coverage_incomplete",r["blockers"])
if __name__=="__main__": unittest.main()
