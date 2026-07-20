#!/usr/bin/env python3
"""Strict official-source resolver for Orthodox Prayers v3.3.

The resolver is deliberately fail-closed. It never treats a discovery API as a
publication authority and never lets a lower-priority source silently override a
valid higher-priority source.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "canonical" / "source_policy.json"
REGISTRY_PATH = ROOT / "canonical" / "official_source_registry.json"

BIDI = dict.fromkeys(map(ord, "\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069"), None)
POISON_DEFAULTS = (
    "lorem ipsum",
    "لوريم إيبسوم",
    "لوريم ايبسوم",
    "sample text",
    "placeholder",
)
ARABIC_DIACRITICS = re.compile(r"[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed]")
ARABIC_LETTERS = re.compile(r"[\u0621-\u063a\u0641-\u064a\u066e-\u06d3]")


@dataclass
class SourceEvidence:
    id: str
    priority: int
    official: bool
    url: str
    status: str
    date_iso: str | None = None
    epistle_reference: str | None = None
    gospel_reference: str | None = None
    tone: int | None = None
    prokeimenon_text: str | None = None
    sha256: str | None = None
    reason: str | None = None

    def publishable_for(self, fields: Iterable[str]) -> bool:
        if not self.official or self.status != "current":
            return False
        return all(bool(getattr(self, field, None)) for field in fields)


@dataclass
class Resolution:
    decision: str
    selected_source: str | None
    selected_priority: int | None
    fields: dict[str, Any]
    fallback_trace: list[dict[str, Any]]
    errors: list[str]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_policy() -> dict[str, Any]:
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def normalize_source_text(value: str) -> str:
    value = unicodedata.normalize("NFC", value or "").translate(BIDI)
    value = value.replace("\xa0", " ").replace("�", "")
    return re.sub(r"[ \t]+", " ", value)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def poisoned_text(value: str, extra_markers: Iterable[str] = ()) -> str | None:
    folded = normalize_source_text(value).casefold()
    for marker in (*POISON_DEFAULTS, *tuple(extra_markers)):
        if marker.casefold() in folded:
            return marker
    return None


def validate_source_document(
    *,
    source_id: str,
    target: date,
    detected_date: date | None,
    text: str,
    extra_poison_markers: Iterable[str] = (),
) -> tuple[str, str | None]:
    marker = poisoned_text(text, extra_poison_markers)
    if marker:
        return "poisoned", f"مصدر {source_id} يحتوي نصًا تجريبيًا/محجوزًا: {marker}"
    if detected_date is None:
        return "undated", f"تعذر إثبات أن صفحة {source_id} تخص التاريخ المطلوب."
    if detected_date != target:
        return "stale", f"صفحة {source_id} تخص {detected_date.isoformat()} لا {target.isoformat()}."
    return "current", None


def strict_resolve(
    evidence: list[SourceEvidence],
    required_fields: tuple[str, ...] = ("epistle_reference", "gospel_reference"),
) -> Resolution:
    ordered = sorted(evidence, key=lambda item: item.priority)
    trace: list[dict[str, Any]] = []
    for item in ordered:
        if item.publishable_for(required_fields):
            selected = {field: getattr(item, field) for field in required_fields}
            if item.tone is not None:
                selected["tone"] = item.tone
            if item.prokeimenon_text:
                selected["prokeimenon_text"] = item.prokeimenon_text
            trace.append({"source": item.id, "priority": item.priority, "status": "selected"})
            return Resolution(
                "PUBLISH",
                item.id,
                item.priority,
                selected,
                trace,
                [],
            )
        missing = [field for field in required_fields if not getattr(item, field, None)]
        trace.append({
            "source": item.id,
            "priority": item.priority,
            "status": item.status,
            "reason": item.reason or ("missing: " + ", ".join(missing) if missing else "not publishable"),
        })
    return Resolution(
        "BLOCK",
        None,
        None,
        {},
        trace,
        ["لم يتوفر مصدر أرثوذكسي رسمي صالح لجميع الحقول المطلوبة؛ يُحفظ آخر إصدار موقع موثوق."],
    )


def strip_arabic_diacritics(value: str) -> str:
    value = unicodedata.normalize("NFD", value or "")
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    value = value.translate(str.maketrans({
        "ٱ": "ا", "أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي", "ؤ": "و", "ئ": "ي", "ـ": ""
    }))
    value = re.sub(r"[^\u0621-\u063a\u0641-\u064a0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def diacritic_metrics(value: str) -> dict[str, Any]:
    marks = len(ARABIC_DIACRITICS.findall(value or ""))
    letters = len(ARABIC_LETTERS.findall(value or ""))
    return {
        "diacritic_count": marks,
        "arabic_letter_count": letters,
        "diacritic_ratio": round(marks / max(letters, 1), 6),
    }


def verify_vocalized_against_base(base: str, vocalized: str, minimum_ratio: float = 0.18) -> list[str]:
    errors: list[str] = []
    if strip_arabic_diacritics(base) != strip_arabic_diacritics(vocalized):
        errors.append("الكلمات في النص المشكول لا تطابق النص الكتابي الأساسي بعد إزالة الحركات.")
    metrics = diacritic_metrics(vocalized)
    if metrics["diacritic_ratio"] < minimum_ratio:
        errors.append(
            f"نسبة التشكيل {metrics['diacritic_ratio']:.3f} أقل من الحد المطلوب {minimum_ratio:.3f}."
        )
    return errors


def validate_verse_sequence(body: str, expected_start: int, expected_end: int) -> list[str]:
    found: list[int] = []
    for line in (body or "").splitlines():
        match = re.match(r"\s*(\d+)\s+", line)
        if match:
            found.append(int(match.group(1)))
    expected = list(range(expected_start, expected_end + 1))
    if found != expected:
        return [f"تسلسل الآيات غير صحيح: المتوقع {expected}، الموجود {found}."]
    return []


ANTIOCH_BOOKS = {
    "رو": "Romans", "روم": "Romans",
    "مت": "Matthew", "مر": "Mark", "لو": "Luke", "يو": "John",
    "تي": "Titus", "عب": "Hebrews", "يع": "James", "غل": "Galatians",
    "اف": "Ephesians", "أف": "Ephesians",
    "1 كو": "1 Corinthians", "١ كو": "1 Corinthians",
    "2 كو": "2 Corinthians", "٢ كو": "2 Corinthians",
    "1 تي": "1 Timothy", "١ تي": "1 Timothy",
    "2 تي": "2 Timothy", "٢ تي": "2 Timothy",
    "1 تس": "1 Thessalonians", "١ تس": "1 Thessalonians",
    "2 تس": "2 Thessalonians", "٢ تس": "2 Thessalonians",
}


def _find_antioch_entry(text: str, day: int) -> str | None:
    clean = normalize_source_text(text)
    # The official PDF is extracted in RTL visual order; entries begin with -12, -13, etc.
    start_re = re.compile(rf"(?m)^\s*-\s*{day}\s+")
    match = start_re.search(clean)
    if not match:
        return None
    next_match = re.compile(rf"(?m)^\s*-\s*{day + 1}\s+").search(clean, match.end())
    return clean[match.start(): next_match.start() if next_match else len(clean)]


def _extract_rtl_reference(block: str, kind: str) -> str | None:
    label = "الر.?سالة" if kind == "epistle" else "ال.?إنجيل"
    # pdftotext visual order: (رو .)14 – 6 :12  => Romans 12:6-14
    book_pattern = "|".join(sorted((re.escape(k) for k in ANTIOCH_BOOKS), key=len, reverse=True))
    patterns = [
        rf"{label}[^\n()]{{0,140}}\((?P<book>{book_pattern})\s*\.?\)?\s*(?P<end>\d+)\s*[-–]\s*(?P<start>\d+)\s*:\s*(?P<chapter>\d+)",
        rf"{label}[^\n()]{{0,140}}\((?P<book>{book_pattern})\s+(?P<chapter>\d+)\s*:\s*(?P<start>\d+)\s*[-–]\s*(?P<end>\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, block)
        if match:
            book = ANTIOCH_BOOKS[re.sub(r"\s+", " ", match.group("book")).strip()]
            return f"{book} {int(match.group('chapter'))}:{int(match.group('start'))}-{int(match.group('end'))}"
    return None


def parse_antioch_guide_text(text: str, target: date, url: str, sha256: str | None = None) -> SourceEvidence:
    block = _find_antioch_entry(text, target.day)
    if not block:
        return SourceEvidence(
            "antioch_patriarchate", 3, True, url, "unusable", target.isoformat(),
            sha256=sha256, reason="تعذر العثور على مدخل اليوم في الدليل الرسمي."
        )
    epistle = _extract_rtl_reference(block, "epistle")
    gospel = _extract_rtl_reference(block, "gospel")
    tone_match = re.search(r"اللحن\s*(\d+)", block)
    tone = int(tone_match.group(1)) if tone_match else None
    status = "current" if epistle and gospel else "partial"
    return SourceEvidence(
        "antioch_patriarchate", 3, True, url, status, target.isoformat(),
        epistle, gospel, tone=tone, sha256=sha256,
        reason=None if status == "current" else "الدليل موجود لكن أحد مرجعي الرسالة أو الإنجيل لم يُستخرج."
    )


def validate_source_order(policy: dict[str, Any] | None = None) -> list[str]:
    policy = policy or load_policy()
    expected = ["orthodox_jordan", "jerusalem_patriarchate", "antioch_patriarchate", "official_greek_orthodox", "orthodox_church_in_america"]
    errors: list[str] = []
    if policy.get("source_priority") != expected:
        errors.append("ترتيب المصادر لا يطابق: الأردن، القدس، أنطاكية، اليونان، ثم OCA كآخر مرجع رسمي احتياطي.")
    priorities = [policy.get("sources", {}).get(source, {}).get("priority") for source in expected]
    if priorities != [1, 2, 3, 4, 5]:
        errors.append(f"أرقام أولوية المصادر غير صحيحة: {priorities}")
    if policy.get("publication", {}).get("human_review_required") is not False:
        errors.append("سياسة الإصدار ما زالت تشترط مراجعة بشرية يومية.")
    return errors


if __name__ == "__main__":
    failures = validate_source_order()
    if failures:
        raise SystemExit("\n".join(failures))
    print("Official-source priority and fail-closed policy validated")
