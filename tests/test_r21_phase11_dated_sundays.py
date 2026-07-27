from __future__ import annotations
import hashlib, importlib.util, json, sys, unittest
from datetime import date
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
LANGS=("ar","en","el")

def load(name,rel):
 p=ROOT/rel; spec=importlib.util.spec_from_file_location(name,p); m=importlib.util.module_from_spec(spec); assert spec and spec.loader; sys.modules[name]=m; spec.loader.exec_module(m); return m

class R21Phase11Tests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.update=load("p11_update","scripts/update_liturgical_data.py"); cls.audit=load("p11_audit","scripts/build_liturgy_year_audit.py"); cls.gate=load("p11_gate","scripts/validate_liturgy_phase11_completion.py")
  cls.registry=json.loads((ROOT/"canonical/dated_liturgical_propers.json").read_text(encoding="utf-8")); cls.dates=cls.registry["dates"]
 def test_phase11_dates_are_registered(self):
  self.assertIn("2026-07-05",self.dates); self.assertIn("2026-07-12",self.dates)
 def test_july_5_sunday_cycle_is_exact(self):
  e=self.dates["2026-07-05"]; self.assertEqual(4,e["resurrection_tone"]); self.assertEqual(5,e["eothinon"]); self.assertEqual("Luke 24:12-35",e["matins_gospel_reference"]); self.assertEqual("Romans 10:1-10",e["readings"]["epistle"]["integrity"]["canonical_reference"]); self.assertEqual("Matthew 8:28-9:1",e["readings"]["gospel"]["integrity"]["canonical_reference"])
 def test_july_12_uses_old_calendar_peter_and_paul_propers(self):
  e=self.dates["2026-07-12"]; self.assertEqual("peter_and_paul_06_29_old_calendar",e["fixed_feast_id"]); self.assertEqual(5,e["resurrection_tone"]); self.assertEqual(6,e["eothinon"]); self.assertEqual("2 Corinthians 11:21-12:9",e["readings"]["epistle"]["integrity"]["canonical_reference"]); self.assertEqual("Matthew 16:13-19",e["readings"]["gospel"]["integrity"]["canonical_reference"])
 def test_all_new_readings_have_three_native_lanes(self):
  for ds in ("2026-07-05","2026-07-12"):
   e=self.dates[ds]
   for kind in ("matins_gospel","epistle","gospel"):
    r=e["readings"][kind]
    for lane in ("reference","body"): self.assertTrue(all(str(r[lane][x]).strip() for x in LANGS),(ds,kind,lane))
    for lang in LANGS: self.assertIn(r["native_source_verification"][lang]["status"],{"VERIFIED_EXACT_NATIVE_SOURCE","IMPORTED_EXACT_OFFICIAL_NATIVE_CORPUS","IMPORTED_EXACT_PUBLIC_DOMAIN_NATIVE_CORPUS"})
 def test_reading_hashes_match_display_text(self):
  for ds in ("2026-07-05","2026-07-12"):
   for r in self.dates[ds]["readings"].values():
    for lang in LANGS:
     expected=r["native_source_verification"][lang]["text_sha256"]
     self.assertEqual(hashlib.sha256(r["body"][lang].encode()).hexdigest(),expected)
 def test_display_text_has_no_usfm_or_strongs_markup(self):
  for ds in ("2026-07-05","2026-07-12"):
   for r in self.dates[ds]["readings"].values():
    for text in r["body"].values(): self.assertNotIn(r"\+w",text); self.assertNotIn("|strong=",text)
 def test_new_dates_resolve_complete_in_audit(self):
  for ds in ("2026-07-05","2026-07-12"):
   row=self.audit.audit_day(self.update,date.fromisoformat(ds)); self.assertTrue(row["complete_for_release"],(ds,row["blockers"]))
 def test_july_12_feast_prokeimenon_and_communion_are_localized(self):
  d=date(2026,7,12); info=self.update.day_info(d); readings=self.update.discovery_readings(d,info); inserts=self.update.feast_inserts(info,d)
  prok=next(r for r in readings if r.get("kind")=="prokeimenon")
  self.assertTrue(all(prok["body"].get(x) for x in LANGS)); self.assertTrue(all(inserts["communion"].get(x) for x in LANGS))
 def test_phase11_audit_covers_year_and_reaches_five_days(self):
  r=self.audit.build_report(2026); self.assertEqual("R21_PHASE11",r["phase"]); self.assertEqual(365,r["audited_days"]); self.assertFalse(r["network_fetch_used"]); self.assertGreaterEqual(r["complete_days"],5)
 def test_phase11_contract_keeps_interpretations_removed(self):
  c=json.loads((ROOT/"canonical/liturgy_phase11_completion_contract.json").read_text(encoding="utf-8")); self.assertFalse(c["scope"]["interpretations"]); self.assertEqual(["2026-07-05","2026-07-12"],c["dated_coverage_added"])
 def test_phase11_gate_remains_fail_closed_for_remaining_year(self):
  r=self.gate.build_report(); self.assertTrue(r["interpretations_removed"]); self.assertTrue(all(r["target_dates_complete"].values())); self.assertFalse(r["complete_release_allowed"]); self.assertIn("phase11_annual_daily_coverage_incomplete",r["blockers"])
if __name__=="__main__": unittest.main()
