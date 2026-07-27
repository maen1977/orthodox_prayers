from __future__ import annotations
import importlib.util,json,sys,unittest
from datetime import date
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(name,rel):
 p=ROOT/rel; spec=importlib.util.spec_from_file_location(name,p); m=importlib.util.module_from_spec(spec); assert spec and spec.loader; sys.modules[name]=m; spec.loader.exec_module(m); return m
class R21Phase10Tests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.update=load("p10_update","scripts/update_liturgical_data.py"); cls.audit=load("p10_audit","scripts/build_liturgy_year_audit.py"); cls.gate=load("p10_gate","scripts/validate_liturgy_phase10_completion.py")
  cls.propers=json.loads((ROOT/"canonical/dated_liturgical_propers.json").read_text(encoding="utf-8"))
 def test_interpretation_registry_and_scripts_are_removed(self):
  for p in ["canonical/patristic_commentary_registry.json","canonical/patristic_commentary_sources.json","scripts/patristic_commentary.py","scripts/import_patristic_commentary.py","scripts/validate_patristic_commentary.py","R21_PHASE9_CANDIDATE_2026-07-26.json","R21_PHASE9_PATRISTIC_VALIDATION.json"]: self.assertFalse((ROOT/p).exists(),p)
 def test_native_libraries_have_no_commentary_slot(self):
  for base in [ROOT/"data/services/native",ROOT/"app/src/main/assets/data/native"]:
   for p in base.glob("library_*.json"):
    s=p.read_text(encoding="utf-8"); self.assertNotIn("gospel_commentary",s); self.assertNotIn("patristic_commentary",s)
 def test_follow_along_contract_keeps_homily_but_no_app_interpretation(self):
  c=json.loads((ROOT/"canonical/follow_along_liturgy_contract.json").read_text(encoding="utf-8")); self.assertFalse(c["post_gospel_policy"]["app_interpretation_or_commentary"]); self.assertTrue(c["post_gospel_policy"]["homily_position_preserved"])
 def test_updater_emits_no_commentary_contract(self):
  service=self.update.build_liturgy_service("test",date(2026,7,19),self.update.day_info(date(2026,7,19)),self.update.discovery_readings(date(2026,7,19),self.update.day_info(date(2026,7,19))),"Test")
  self.assertNotIn("gospel_commentary",json.dumps(service,ensure_ascii=False))
 def test_reference_sunday_has_dated_authority(self):
  e=self.propers["dates"]["2026-07-19"]; self.assertEqual(6,e["resurrection_tone"]); self.assertEqual(7,e["eothinon"]); self.assertEqual("John 20:1-10",e["matins_gospel_reference"])
 def test_reference_sunday_readings_complete_in_three_languages(self):
  e=self.propers["dates"]["2026-07-19"]
  for kind in ["matins_gospel","epistle","gospel"]:
   for lane in ["body","reference"]: self.assertTrue(all(str(e["readings"][kind][lane][x]).strip() for x in ["ar","en","el"]))
 def test_reference_sunday_display_text_has_no_usfm_or_strongs_markup(self):
  e=self.propers["dates"]["2026-07-19"]
  for kind in ["matins_gospel","epistle","gospel"]:
   for text in e["readings"][kind]["body"].values():
    self.assertNotIn("\\+w",text); self.assertNotIn("|strong=",text)
 def test_reference_sunday_audits_complete(self):
  day=self.audit.audit_day(self.update,date(2026,7,19)); self.assertTrue(day["complete_for_release"],day["blockers"])
 def test_phase10_audit_covers_every_day(self):
  r=self.audit.build_report(2026); self.assertEqual(365,r["audited_days"]); self.assertFalse(r["network_fetch_used"]); self.assertGreaterEqual(r["complete_days"],3)
 def test_phase10_contract_excludes_interpretations(self):
  c=json.loads((ROOT/"canonical/liturgy_phase10_completion_contract.json").read_text(encoding="utf-8")); self.assertFalse(c["scope"]["interpretations"]); self.assertFalse(c["scope"]["commentary"])
 def test_phase10_gate_is_fail_closed_for_remaining_work(self):
  r=self.gate.build_report(); self.assertTrue(r["interpretations_removed"]); self.assertTrue(r["reference_sunday_complete"]); self.assertFalse(r["complete_release_allowed"]); self.assertIn("phase10_annual_daily_coverage_incomplete",r["blockers"])
if __name__=="__main__": unittest.main()
