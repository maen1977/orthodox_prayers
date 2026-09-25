#!/usr/bin/env python3
"""Detect known omissions; a clean result is NOT proof of liturgical completeness."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def normalize(text):
    return re.sub(r"[\u064b-\u065f\u0670\u0640]", "", text).replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")


CHECKS = {
    "cherubic_priest_prayer": "ليس أحد من",
    "theotokos_hymn_second_half": "يا من هي أكرم",
    "bowing_heads_prayer": "نشكرك أيها الملك غير المنظور",
    "prayer_before_elevation": "من مسكنك المقدس",
    "post_communion_light_hymn": "قد نظرنا النور الحقيقي",
    "ambo_prayer_second_half": "يا أبا الأنوار",
    "final_prayers_of_fathers": "بصلوات آبائنا القديسين",
    "petition_peaceful_angel": "ملاك سلام",
}


def audit():
    path = ROOT / "data/services/native_overrides/ar/divine_liturgy.json"
    service = json.loads(path.read_text(encoding="utf-8"))
    text = normalize("\n".join(s.get("text", {}).get("ar", "") for s in service["segments"]))
    missing = [key for key, marker in CHECKS.items() if normalize(marker) not in text]
    return {
        "scope": "ARABIC_CHRYSOSTOM_FIXED_CORE_KNOWN_OMISSIONS_ONLY",
        "status": "INCOMPLETE" if missing else "KNOWN_MARKERS_PRESENT_FULL_REVIEW_STILL_REQUIRED",
        "missing": missing,
        "full_completeness_certified": False,
        "ecclesiastical_approval_claimed": False,
        "daily_propers_checked": False,
        "segment_count": len(service["segments"]),
    }


if __name__ == "__main__":
    result = audit()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if "--require-known-passages" in sys.argv and result["missing"]:
        sys.exit(1)
