from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def exact_evidence(text: str) -> dict[str, object]:
    return {
        "status": "IMPORTED_EXACT_PUBLIC_DOMAIN_NATIVE_CORPUS",
        "source_id": "ebible_arabic_van_dyck",
        "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "text_available": True,
        "reference_available": True,
        "ai_translation_used": False,
        "automatic_diacritization_used": False,
    }


def isolated_arabic_lane() -> dict[str, object]:
    epistle = "يا إخوتي، اثبتوا في المحبة والرجاء."
    gospel = "في ذلك الزمان، علّم الرب الجموع بكلمة الحق."
    readings = [
        {
            "kind": "epistle",
            "reference": {"ar": "رسالة مختبرة", "en": "", "el": ""},
            "body": {"ar": epistle, "en": "", "el": ""},
            "native_source_verification": {"ar": exact_evidence(epistle)},
        },
        {
            "kind": "gospel",
            "reference": {"ar": "إنجيل مختبر", "en": "", "el": ""},
            "body": {"ar": gospel, "en": "", "el": ""},
            "native_source_verification": {"ar": exact_evidence(gospel)},
        },
    ]
    return {
        "language": "ar",
        "language_content_mode": "THREE_STRICTLY_INDEPENDENT_OFFICIAL_NATIVE_LANGUAGE_LANES",
        "machine_translation_used": False,
        "automatic_diacritization_used": False,
        "translation_fallback_policy": "DISABLED_NO_CROSS_LANGUAGE_FALLBACK",
        "readings": readings,
        "services": [
            {
                "id": "divine_liturgy",
                "segment_replacements": {
                    "[فصل من رسالة اليوم]": {"ar": epistle},
                    "[فصل الإنجيل المعيّن لهذا اليوم]": {"ar": gospel},
                },
            }
        ],
    }


def test_isolated_language_lane_validates_only_its_native_evidence(tmp_path: Path):
    payload = tmp_path / "ar.json"
    payload.write_text(json.dumps(isolated_arabic_lane(), ensure_ascii=False), encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/validate_daily_native_content.py"),
            str(payload),
            "--require-complete",
            "--language",
            "ar",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "complete in native lane ar" in result.stdout
    assert "language=ar" in result.stdout


def test_isolated_lane_still_fails_when_misvalidated_as_multilingual(tmp_path: Path):
    payload = tmp_path / "ar.json"
    payload.write_text(json.dumps(isolated_arabic_lane(), ensure_ascii=False), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/validate_daily_native_content.py"), str(payload), "--require-complete"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "missing native verification" in result.stdout + result.stderr


def test_automated_gate_forwards_selected_language(monkeypatch):
    module = load_module(
        "r40_10_automated_evidence",
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
            "data/daily/2026-08-03/ar.json",
            "--language",
            "ar",
        ],
    )
    module.main()
    assert (
        "scripts/validate_daily_native_content.py",
        "data/daily/2026-08-03/ar.json",
        "--require-complete",
        "--language",
        "ar",
    ) in calls
    assert (
        "scripts/validate_scripture_translations.py",
        "data/daily/2026-08-03/ar.json",
        "--language",
        "ar",
    ) in calls
