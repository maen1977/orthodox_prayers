from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from build_church_directory import merge_verified_seed_localizations
from update_language_lane import keep_only_language
from source_connectors import load_registry
from validate_source_intelligence import validate_church_directory


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def reviewed_seed_directory() -> dict[str, object]:
    seed = json.loads((ROOT / "canonical/jordan_church_directory_seed.json").read_text(encoding="utf-8"))
    churches = copy.deepcopy(seed["churches"])
    return {
        "authority": "orthodox_jordan",
        "directory_url": "https://orthodoxjordan.org/churches/",
        "count": len(churches),
        "churches": churches,
    }


def test_live_directory_merges_only_reviewed_seed_localizations():
    live = copy.deepcopy(
        json.loads((ROOT / "data/daily/current/ar.json").read_text(encoding="utf-8"))["church_directory"]["churches"]
    )
    seed = json.loads((ROOT / "canonical/jordan_church_directory_seed.json").read_text(encoding="utf-8"))["churches"]
    merged, enriched = merge_verified_seed_localizations(live, seed)
    assert enriched == 5
    assert sum(bool((item.get("name") or {}).get("en")) for item in merged) == 5
    assert sum(bool((item.get("name") or {}).get("el")) for item in merged) == 5
    assert all((item.get("name") or {}).get("ar") for item in merged)


def test_greek_lane_accepts_reviewed_native_subset_and_structural_official_links():
    aggregate = reviewed_seed_directory()
    churches = aggregate["churches"]
    assert isinstance(churches, list)
    churches.extend(
        [
            {
                "id": f"arabic-only-{index}",
                "name": {"ar": f"كنيسة رسمية {index}", "en": "", "el": ""},
                "city": {"ar": "عمان", "en": "", "el": ""},
                "url": f"https://orthodoxjordan.org/church-{index}/",
                "source_id": "orthodox_jordan",
                "official": True,
            }
            for index in range(3)
        ]
    )
    aggregate["count"] = len(churches)
    greek_lane = keep_only_language(aggregate, "el")
    validated, counts = validate_church_directory(greek_lane, "el")
    assert len(validated) == 8
    assert counts == {"ar": 0, "en": 0, "el": 5}


def test_language_lane_still_fails_without_reviewed_native_church_names():
    directory = reviewed_seed_directory()
    greek_lane = keep_only_language(directory, "el")
    for church in greek_lane["churches"]:
        church["name"]["el"] = ""
    with pytest.raises(SystemExit, match="lacks reviewed native names for el"):
        validate_church_directory(greek_lane, "el")


def test_legacy_aggregate_bootstrap_can_precede_localization_enrichment():
    directory = reviewed_seed_directory()
    for church in directory["churches"]:
        church["name"]["en"] = ""
        church["name"]["el"] = ""
    churches, counts = validate_church_directory(
        directory,
        "all",
        strict_reviewed_names=False,
    )
    assert len(churches) == 5
    assert counts == {"ar": 5, "en": 0, "el": 0}


def test_aggregate_directory_requires_all_arabic_names_and_reviewed_en_el_subset():
    directory = reviewed_seed_directory()
    churches, counts = validate_church_directory(directory, "all")
    assert len(churches) == 5
    assert counts == {"ar": 5, "en": 5, "el": 5}



def test_full_source_intelligence_validator_accepts_generated_greek_lane(tmp_path: Path):
    aggregate = json.loads((ROOT / "data/daily/current/ar.json").read_text(encoding="utf-8"))
    seed = json.loads((ROOT / "canonical/jordan_church_directory_seed.json").read_text(encoding="utf-8"))["churches"]
    merged, enriched = merge_verified_seed_localizations(aggregate["church_directory"]["churches"], seed)
    assert enriched == 5
    aggregate["church_directory"]["churches"] = merged
    aggregate["church_directory"]["count"] = len(merged)

    _, connectors = load_registry()
    observations = {item.get("connector_id"): item for item in aggregate["source_health"]["observations"]}
    for connector in connectors:
        observations.setdefault(
            connector.id,
            {
                "connector_id": connector.id,
                "url": f"https://example.org/source/{connector.id}",
                "status": "available",
                "rights_mode": connector.rights_mode,
            },
        )
    aggregate["source_health"]["observations"] = [observations[item.id] for item in connectors]
    aggregate["source_health"]["date_iso"] = aggregate["date_iso"]

    greek_lane = keep_only_language(aggregate, "el")
    greek_lane["language"] = "el"
    payload = tmp_path / "el.json"
    payload.write_text(json.dumps(greek_lane, ensure_ascii=False), encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/validate_source_intelligence.py"),
            str(payload),
            "--expected-date",
            aggregate["date_iso"],
            "--language",
            "el",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "41 church links language=el" in result.stdout
    assert "el:5" in result.stdout

def test_automated_gate_forwards_language_to_source_intelligence(monkeypatch):
    module = load_module(
        "r40_11_automated_evidence",
        ROOT / "scripts/validate_automated_religious_evidence.py",
    )
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(module, "run", lambda *args: calls.append(args))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "validate_automated_religious_evidence.py",
            "--start-date",
            "2026-08-03",
            "--daily",
            "data/daily/2026-08-03/el.json",
            "--language",
            "el",
        ],
    )
    module.main()
    assert (
        "scripts/validate_source_intelligence.py",
        "data/daily/2026-08-03/el.json",
        "--expected-date",
        "2026-08-03",
        "--language",
        "el",
    ) in calls
