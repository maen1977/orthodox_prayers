from __future__ import annotations
import hashlib, importlib.util, json, sys, unittest
from datetime import date
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
LANGS=("ar","en","el")

def load(name,rel):
 p=ROOT/rel; spec=importlib.util.spec_from_file_location(name,p); m=importlib.util.module_from_spec(spec); assert spec and spec.loader; sys.modules[name]=m; spec.loader.exec_module(m); return m

class R21Phase12Tests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.update=load("p12_update","scripts/update_liturgical_data.py"); cls.audit=load("p12_audit","scripts/build_liturgy_year_audit.py"); cls.gate=load("p12_gate","scripts/validate_liturgy_phase12_completion.py")
  cls.registry=json.loads((ROOT/"canonical/dated_liturgical_propers.json").read_text(encoding="utf-8")); cls.dates=cls.registry["dates"]
 def test_phase12_dates_are_registered(self):
  self.assertIn("2026-06-21",self.dates); self.assertIn("2026-06-28",self.dates)
 def test_june_21_sunday_cycle_is_exact(self):
  e=self.dates["2026-06-21"]; self.assertEqual(3,e["sunday_after_pentecost"]); self.assertEqual(2,e["resurrection_tone"]); self.assertEqual(3,e["eothinon"]); self.assertEqual("Mark 16:9-20",e["matins_gospel_reference"]); self.assertEqual("Romans 5:1-10",e["readings"]["epistle"]["integrity"]["canonical_reference"]); self.assertEqual("Matthew 6:22-33",e["readings"]["gospel"]["integrity"]["canonical_reference"])
 def test_june_28_sunday_cycle_is_exact(self):
  e=self.dates["2026-06-28"]; self.assertEqual(4,e["sunday_after_pentecost"]); self.assertEqual(3,e["resurrection_tone"]); self.assertEqual(4,e["eothinon"]); self.assertEqual("Luke 24:1-12",e["matins_gospel_reference"]); self.assertEqual("Romans 6:18-23",e["readings"]["epistle"]["integrity"]["canonical_reference"]); self.assertEqual("Matthew 8:5-13",e["readings"]["gospel"]["integrity"]["canonical_reference"])
 def test_all_new_readings_have_three_native_lanes(self):
  for ds in ("2026-06-21","2026-06-28"):
   for kind in ("matins_gospel","epistle","gospel"):
    r=self.dates[ds]["readings"][kind]
    for lane in ("reference","body"): self.assertTrue(all(str(r[lane][x]).strip() for x in LANGS),(ds,kind,lane))
    for lang in LANGS: self.assertEqual("IMPORTED_EXACT_PUBLIC_DOMAIN_NATIVE_CORPUS",r["native_source_verification"][lang]["status"])
 def test_reading_and_verse_hashes_match_display_text(self):
  for ds in ("2026-06-21","2026-06-28"):
   for r in self.dates[ds]["readings"].values():
    for lang in LANGS:
     v=r["native_source_verification"][lang]; text=r["body"][lang]
     self.assertEqual(hashlib.sha256(text.encode()).hexdigest(),v["text_sha256"])
     lines=text.splitlines(); self.assertEqual(len(lines),v["verse_count"]); self.assertEqual([hashlib.sha256(x.encode()).hexdigest() for x in lines],v["verse_hashes"])
 def test_display_text_has_no_technical_markup(self):
  for ds in ("2026-06-21","2026-06-28"):
   for r in self.dates[ds]["readings"].values():
    for text in r["body"].values():
     for token in (r"\+w","|strong=","cite"): self.assertNotIn(token,text)
 def test_new_dates_resolve_complete_in_audit(self):
  for ds in ("2026-06-21","2026-06-28"):
   row=self.audit.audit_day(self.update,date.fromisoformat(ds)); self.assertTrue(row["complete_for_release"],(ds,row["blockers"]))
 def test_tones_supply_localized_prokeimena_and_ordinary_communion(self):
  for ds in ("2026-06-21","2026-06-28"):
   d=date.fromisoformat(ds); info=self.update.day_info(d); readings=self.update.discovery_readings(d,info); inserts=self.update.feast_inserts(info,d)
   prok=next(r for r in readings if r.get("kind")=="prokeimenon")
   self.assertTrue(all(prok["body"].get(x) for x in LANGS)); self.assertTrue(all(inserts["communion"].get(x) for x in LANGS))
 def test_phase12_audit_covers_year_and_reaches_seven_days(self):
  r=self.audit.build_report(2026,phase="R21_PHASE12"); self.assertEqual("R21_PHASE12",r["phase"]); self.assertEqual(365,r["audited_days"]); self.assertFalse(r["network_fetch_used"]); self.assertGreaterEqual(r["complete_days"],7)
 def test_phase12_contract_keeps_interpretations_removed(self):
  c=json.loads((ROOT/"canonical/liturgy_phase12_completion_contract.json").read_text(encoding="utf-8")); self.assertFalse(c["scope"]["interpretations"]); self.assertEqual(["2026-06-21","2026-06-28"],c["dated_coverage_added"])
 def test_previous_dated_services_remain_registered(self):
  for ds in ("2026-07-05","2026-07-12","2026-07-19","2026-07-26"): self.assertIn(ds,self.dates)
 def test_phase12_gate_remains_fail_closed_for_remaining_year(self):
  r=self.gate.build_report(); self.assertTrue(r["interpretations_removed"]); self.assertTrue(all(r["target_dates_complete"].values())); self.assertFalse(r["complete_release_allowed"]); self.assertIn("phase12_annual_daily_coverage_incomplete",r["blockers"])
if __name__=="__main__": unittest.main()
