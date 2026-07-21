#!/usr/bin/env python3
"""Official-source connector framework for daily Orthodox content intelligence.

The framework deliberately separates observation from publication. Connectors may
collect dates, references, service links, and official directory metadata, but no
connector is allowed to invent, translate, or silently republish restricted full
liturgical text.
"""
from __future__ import annotations

import hashlib
import html as html_module
import json
import re
import socket
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "canonical" / "source_connectors.json"
USER_AGENT = "OrthodoxPrayersSourceMonitor/5.0.14 (+https://github.com/maen1977/orthodox_prayers)"
POISON_MARKERS = ("lorem ipsum", "لوريم إيبسوم", "لوريم ايبسوم", "�")
ALLOWED_HOST_SUFFIXES = (
    "orthodoxjordan.org",
    "jerusalem-patriarchate.info",
    "antiochpatriarchate.org",
    "goarch.org",
    "digitalchantstand.goarch.org",
    "oca.org",
    "apostoliki-diakonia.gr",
)

MONTHS_EN = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


@dataclass(frozen=True)
class ConnectorDefinition:
    id: str
    source_id: str
    name: dict[str, str]
    official: bool
    authority_tier: int
    languages: list[str]
    calendar_profile: str
    publication_role: str
    capabilities: list[str]
    parser: str
    url_template: str
    rights_mode: str
    required_for_publication: bool = False
    timeout_seconds: int = 25
    max_bytes: int = 2_000_000
    service_url_templates: list[str] = field(default_factory=list)

    def url_for(self, target: date) -> str:
        return self.url_template.format(year=target.year, month=target.month, day=target.day)


@dataclass
class ConnectorObservation:
    connector_id: str
    source_id: str
    official: bool
    authority_tier: int
    publication_role: str
    calendar_profile: str
    target_date: str
    url: str
    status: str
    checked_at_utc: str
    http_status: int | None = None
    content_sha256: str | None = None
    content_bytes: int | None = None
    detected_date: str | None = None
    epistle_reference: str | None = None
    gospel_reference: str | None = None
    commemorations: list[str] = field(default_factory=list)
    service_links: list[dict[str, str]] = field(default_factory=list)
    church_count: int | None = None
    confidence: float = 0.0
    rights_mode: str = ""
    reason: str | None = None
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class TextAndLinksParser(HTMLParser):
    def __init__(self, base_url: str):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.text_parts: list[str] = []
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._anchor_parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg"}:
            self._ignored_depth += 1
            return
        if self._ignored_depth:
            return
        if tag == "a":
            attributes = dict(attrs)
            self._href = attributes.get("href")
            self._anchor_parts = []
        if tag in {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "article", "section"}:
            self.text_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg"} and self._ignored_depth:
            self._ignored_depth -= 1
            return
        if self._ignored_depth:
            return
        if tag == "a" and self._href:
            label = compact_text(" ".join(self._anchor_parts))
            url = urllib.parse.urljoin(self.base_url, self._href)
            self.links.append((label, url))
            self._href = None
            self._anchor_parts = []

    def handle_data(self, data: str) -> None:
        if self._ignored_depth:
            return
        self.text_parts.append(data)
        if self._href is not None:
            self._anchor_parts.append(data)

    @property
    def text(self) -> str:
        return compact_text(" ".join(self.text_parts), preserve_newlines=True)


def compact_text(value: str, preserve_newlines: bool = False) -> str:
    value = html_module.unescape(value or "").replace("\xa0", " ")
    value = unicodedata.normalize("NFC", value).translate(ARABIC_DIGITS)
    if preserve_newlines:
        value = re.sub(r"[ \t\r\f\v]+", " ", value)
        value = re.sub(r"\n\s*\n+", "\n", value)
        return value.strip()
    return re.sub(r"\s+", " ", value).strip()


def normalize_reference(value: str | None) -> str:
    value = compact_text(value or "").lower()
    value = unicodedata.normalize("NFD", value)
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    replacements = {
        "رِسَالَةُ": "", "رسالة": "", "بولس الرسول": "", "paul’s": "", "paul's": "",
        "first letter to the": "1 ", "second letter to the": "2 ", "letter to the": "",
        "the good news according to": "", "gospel according to": "", "the holy gospel according to": "", "انجيل": "",
        "κατα": "", "προς": "", "α΄": "1", "β΄": "2", "γ΄": "3",
        "كورِنثوس": "corinthians", "كورنثوس": "corinthians", "رومية": "romans", "روميه": "romans",
        "متى": "matthew", "مرقس": "mark", "لوقا": "luke", "يوحنا": "john",
    }
    for old, new in replacements.items():
        value = value.replace(old, new)
    value = value.replace("–", "-").replace("—", "-").replace("٫", ":").replace("،", ",")
    value = re.sub(r"[^a-zα-ω0-9:,-]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def load_registry() -> tuple[dict[str, Any], list[ConnectorDefinition]]:
    raw = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    connectors = [ConnectorDefinition(**entry) for entry in raw.get("connectors", [])]
    return raw.get("policy", {}), connectors


def _allowed_host(host: str) -> bool:
    host = (host or "").lower().split(":", 1)[0]
    return any(host == suffix or host.endswith("." + suffix) for suffix in ALLOWED_HOST_SUFFIXES)


def safe_fetch(url: str, timeout_seconds: int, max_bytes: int) -> tuple[int, bytes, str]:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or not _allowed_host(parsed.netloc):
        raise ValueError(f"Blocked non-allowlisted source URL: {url}")
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.5",
            "Accept-Language": "ar,en;q=0.8,el;q=0.7",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        final_url = response.geturl()
        final = urllib.parse.urlparse(final_url)
        if final.scheme != "https" or not _allowed_host(final.netloc):
            raise ValueError(f"Redirected outside source allowlist: {final_url}")
        status = int(getattr(response, "status", 200))
        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) > max_bytes:
            raise ValueError(f"Source response exceeds maximum size: {content_length} > {max_bytes}")
        data = response.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise ValueError(f"Source response exceeds maximum size: > {max_bytes}")
        return status, data, final_url


def decode_document(raw: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "windows-1256", "iso-8859-7", "windows-1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def parse_html(raw: bytes, url: str) -> TextAndLinksParser:
    parser = TextAndLinksParser(url)
    parser.feed(decode_document(raw))
    parser.close()
    return parser


def poison_marker(text: str) -> str | None:
    folded = text.casefold()
    return next((marker for marker in POISON_MARKERS if marker.casefold() in folded), None)


def extract_date(text: str, target: date) -> str | None:
    candidates = [
        target.isoformat(),
        f"{target.day:02d}/{target.month:02d}/{target.year}",
        f"{target.day}/{target.month}/{target.year}",
        f"{target.month:02d}/{target.day:02d}/{target.year}",
        f"{target.month}/{target.day}/{target.year}",
    ]
    folded = compact_text(text).lower()
    if any(candidate.lower() in folded for candidate in candidates):
        return target.isoformat()
    for month_name, month in MONTHS_EN.items():
        if month != target.month:
            continue
        patterns = (
            rf"\b{month_name}\s+{target.day}(?:st|nd|rd|th)?[,]?\s+{target.year}\b",
            rf"\b{target.day}(?:st|nd|rd|th)?\s+{month_name}\s+{target.year}\b",
        )
        if any(re.search(pattern, folded, re.I) for pattern in patterns):
            return target.isoformat()
    return None


BOOK_PATTERN = r"(?:[123]\s*)?[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3}"
REFERENCE_PATTERN = rf"({BOOK_PATTERN}\s+\d{{1,3}}:\d{{1,3}}(?:\s*[-–—]\s*\d{{1,3}}(?::\d{{1,3}})?)?(?:\s*,\s*\d{{1,3}}(?:[-–—]\d{{1,3}})?)?)"


def extract_labeled_reference(text: str, labels: Iterable[str]) -> str | None:
    clean = compact_text(text, preserve_newlines=True)
    for label in labels:
        match = re.search(rf"{label}\s*[:\-]?\s*{REFERENCE_PATTERN}", clean, re.I)
        if match:
            return compact_text(match.group(1)).replace("–", "-").replace("—", "-")
    return None


def extract_unlabeled_references(text: str) -> list[str]:
    clean = compact_text(text, preserve_newlines=True)
    found: list[str] = []
    for match in re.finditer(REFERENCE_PATTERN, clean):
        value = compact_text(match.group(1)).replace("–", "-").replace("—", "-")
        if value not in found:
            found.append(value)
    return found


def base_observation(definition: ConnectorDefinition, target: date, url: str) -> ConnectorObservation:
    return ConnectorObservation(
        connector_id=definition.id,
        source_id=definition.source_id,
        official=definition.official,
        authority_tier=definition.authority_tier,
        publication_role=definition.publication_role,
        calendar_profile=definition.calendar_profile,
        target_date=target.isoformat(),
        url=url,
        status="unknown",
        checked_at_utc=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        rights_mode=definition.rights_mode,
    )


def parse_availability(definition: ConnectorDefinition, target: date, url: str, status: int, raw: bytes) -> ConnectorObservation:
    observation = base_observation(definition, target, url)
    parser = parse_html(raw, url)
    marker = poison_marker(parser.text)
    if marker:
        observation.status = "poisoned"
        observation.reason = f"poison marker detected: {marker}"
        return observation
    observation.status = "available" if 200 <= status < 400 and len(parser.text) >= 40 else "unusable"
    observation.confidence = 0.55 if observation.status == "available" else 0.1
    observation.detected_date = extract_date(parser.text, target)
    return observation


def parse_orthodox_jordan_daily(definition: ConnectorDefinition, target: date, url: str, status: int, raw: bytes) -> ConnectorObservation:
    observation = base_observation(definition, target, url)
    parser = parse_html(raw, url)
    text = parser.text
    marker = poison_marker(text)
    if marker:
        observation.status = "poisoned"
        observation.reason = f"poison marker detected: {marker}"
        return observation
    observation.detected_date = extract_date(text, target)
    observation.epistle_reference = extract_labeled_reference(text, ("رسالة اليوم", "الرسالة", "Epistle Reading"))
    observation.gospel_reference = extract_labeled_reference(text, ("إنجيل اليوم", "انجيل اليوم", "الإنجيل", "Gospel Reading"))
    for heading in ("تذكار", "القديس", "القديسين"):
        match = re.search(rf"{heading}\s*[:：]?\s*([^\n]{{8,500}})", text)
        if match:
            commemoration = compact_text(match.group(1))
            if commemoration and commemoration not in observation.commemorations:
                observation.commemorations.append(commemoration)
    if observation.detected_date:
        observation.status = "current"
        observation.confidence = 0.95 if observation.epistle_reference and observation.gospel_reference else 0.8
    elif observation.epistle_reference or observation.gospel_reference or observation.commemorations:
        observation.status = "undated"
        observation.confidence = 0.45
        observation.reason = "content was found but the requested civil date was not proven"
    else:
        observation.status = "unusable"
        observation.confidence = 0.1
        observation.reason = "daily fields were not detected"
    return observation



def parse_orthodox_jordan_churches(definition: ConnectorDefinition, target: date, url: str, status: int, raw: bytes) -> ConnectorObservation:
    observation = base_observation(definition, target, url)
    parser = parse_html(raw, url)
    marker = poison_marker(parser.text)
    if marker:
        observation.status = "poisoned"
        observation.reason = f"poison marker detected: {marker}"
        return observation
    markers = ("كنيسة", "كاتدرائية", "دير", "Church", "Cathedral", "Monastery")
    official_links = {link for label, link in parser.links if _allowed_host(urllib.parse.urlparse(link).netloc) and any(value.casefold() in label.casefold() for value in markers)}
    observation.church_count = len(official_links)
    if observation.church_count >= 5:
        observation.status = "available"
        observation.confidence = 0.9
    elif observation.church_count:
        observation.status = "partial"
        observation.confidence = 0.45
        observation.reason = "fewer than five official church links were detected"
    else:
        observation.status = "unusable"
        observation.confidence = 0.1
        observation.reason = "no official church links were detected"
    return observation

def parse_goarch_online_chapel(definition: ConnectorDefinition, target: date, url: str, status: int, raw: bytes) -> ConnectorObservation:
    observation = base_observation(definition, target, url)
    parser = parse_html(raw, url)
    text = parser.text
    marker = poison_marker(text)
    if marker:
        observation.status = "poisoned"
        observation.reason = f"poison marker detected: {marker}"
        return observation
    observation.detected_date = extract_date(text, target)
    observation.epistle_reference = extract_labeled_reference(text, ("Epistle Reading", "Epistle", "Ἀπόστολος"))
    observation.gospel_reference = extract_labeled_reference(text, ("Gospel Reading", "Gospel", "Εὐαγγέλιο"))
    if observation.detected_date and (observation.epistle_reference or observation.gospel_reference):
        observation.status = "current"
        observation.confidence = 0.85
    elif observation.epistle_reference or observation.gospel_reference:
        observation.status = "undated"
        observation.confidence = 0.45
        observation.reason = "reading references found without a provable target date"
    else:
        observation.status = "available" if len(text) > 100 else "unusable"
        observation.confidence = 0.35 if observation.status == "available" else 0.1
    return observation


def parse_oca_daily_readings(definition: ConnectorDefinition, target: date, url: str, status: int, raw: bytes) -> ConnectorObservation:
    observation = base_observation(definition, target, url)
    parser = parse_html(raw, url)
    text = parser.text
    observation.detected_date = extract_date(text, target)
    references = extract_unlabeled_references(text)
    gospel_books = {"Matthew", "Mark", "Luke", "John"}
    for reference in references:
        first = reference.split()[0]
        if first in gospel_books and not observation.gospel_reference:
            observation.gospel_reference = reference
        elif not observation.epistle_reference:
            observation.epistle_reference = reference
    if observation.detected_date and (observation.epistle_reference or observation.gospel_reference):
        observation.status = "current"
        observation.confidence = 0.75
    elif observation.detected_date:
        observation.status = "partial"
        observation.confidence = 0.5
        observation.reason = "target date was found but reading references were not extracted"
    else:
        observation.status = "unusable"
        observation.confidence = 0.15
        observation.reason = "target date was not proven"
    observation.warnings.append("OCA page Scripture text is not redistributed; references only")
    return observation


DCS_REFERENCE_BOOKS = {
    "1 Cor.": "1 Corinthians", "2 Cor.": "2 Corinthians",
    "Rom.": "Romans", "Gal.": "Galatians", "Eph.": "Ephesians",
    "Phil.": "Philippians", "Col.": "Colossians",
    "1 Thess.": "1 Thessalonians", "2 Thess.": "2 Thessalonians",
    "1 Tim.": "1 Timothy", "2 Tim.": "2 Timothy", "Tit.": "Titus",
    "Heb.": "Hebrews", "Jas.": "James", "1 Pet.": "1 Peter",
    "2 Pet.": "2 Peter", "1 Jn.": "1 John", "2 Jn.": "2 John",
    "3 Jn.": "3 John", "Matt.": "Matthew", "Mt.": "Matthew",
    "Mk.": "Mark", "Lk.": "Luke", "Jn.": "John",
}


def normalize_dcs_reference(value: str) -> str | None:
    value = compact_text(value).replace("–", "-").replace("—", "-")
    value = re.sub(r"\s*-\s*", "-", value)
    value = re.sub(r"\s*:\s*", ":", value)
    for short, full in sorted(DCS_REFERENCE_BOOKS.items(), key=lambda item: len(item[0]), reverse=True):
        if value.startswith(short):
            value = full + value[len(short):]
            break
    value = re.sub(r"\s+", " ", value).strip(" .")
    pattern = (
        r"(?:[123] )?[A-Za-z]+(?: [A-Za-z]+)* "
        r"\d{1,3}:\d{1,3}(?:-(?:\d{1,3}:)?\d{1,3})?"
        r"(?:;\s*\d{1,3}:\d{1,3}(?:-(?:\d{1,3}:)?\d{1,3})?)*"
    )
    return value if re.fullmatch(pattern, value) else None


def dcs_reference_after_heading(text: str, heading: str) -> str | None:
    lines = [compact_text(line) for line in text.splitlines() if compact_text(line)]
    for index, line in enumerate(lines):
        if line.casefold() != heading.casefold():
            continue
        for candidate in lines[index + 1:index + 9]:
            if not re.search(r"\d+\s*:\s*\d+", candidate):
                continue
            normalized = normalize_dcs_reference(candidate)
            if normalized:
                return normalized
    return None


def parse_dcs_probe(definition: ConnectorDefinition, target: date, url: str, status: int, raw: bytes) -> ConnectorObservation:
    observation = parse_availability(definition, target, url, status, raw)
    labels = ("Divine Liturgy", "Matins / Orthros", "Vespers")
    for label, template in zip(labels, definition.service_url_templates):
        observation.service_links.append({
            "title": label,
            "url": template.format(year=target.year, month=target.month, day=target.day),
            "status": "candidate",
        })
    observation.warnings.append("Service links are discovery links; full text import remains rights-gated")
    return observation


PARSERS = {
    "availability_only": parse_availability,
    "orthodox_jordan_daily": parse_orthodox_jordan_daily,
    "orthodox_jordan_churches": parse_orthodox_jordan_churches,
    "goarch_online_chapel": parse_goarch_online_chapel,
    "oca_daily_readings": parse_oca_daily_readings,
    "dcs_service_probe": parse_dcs_probe,
}


def observe_connector(
    definition: ConnectorDefinition,
    target: date,
    *,
    raw: bytes | None = None,
    fixture_status: int = 200,
) -> ConnectorObservation:
    url = definition.url_for(target)
    try:
        if raw is None:
            http_status, raw, url = safe_fetch(url, definition.timeout_seconds, definition.max_bytes)
        else:
            http_status = fixture_status
        digest = hashlib.sha256(raw).hexdigest()
        parser = PARSERS.get(definition.parser)
        if parser is None:
            raise ValueError(f"Unknown connector parser: {definition.parser}")
        observation = parser(definition, target, url, http_status, raw)
        observation.http_status = http_status
        observation.content_sha256 = digest
        observation.content_bytes = len(raw)
        return observation
    except urllib.error.HTTPError as exc:
        observation = base_observation(definition, target, url)
        observation.status = "http_error"
        observation.http_status = exc.code
        observation.reason = f"HTTP {exc.code}"
        return observation
    except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
        observation = base_observation(definition, target, url)
        observation.status = "network_error"
        observation.reason = str(getattr(exc, "reason", exc))[:300]
        return observation
    except Exception as exc:  # Fail closed per connector without aborting the complete monitor.
        observation = base_observation(definition, target, url)
        observation.status = "parser_error"
        observation.reason = f"{type(exc).__name__}: {exc}"[:500]
        return observation



def probe_service_links(observation: ConnectorObservation, definition: ConnectorDefinition) -> ConnectorObservation:
    """Verify dated service URLs without importing or retaining their full text."""
    if not observation.service_links:
        return observation
    available = 0
    for link in observation.service_links:
        url = str(link.get("url") or "")
        try:
            status, raw, final_url = safe_fetch(url, min(definition.timeout_seconds, 15), min(definition.max_bytes, 300_000))
            text = decode_document(raw)
            marker = poison_marker(text)
            if marker:
                link["status"] = "poisoned"
                link["reason"] = f"poison marker detected: {marker}"
            elif 200 <= status < 400 and len(compact_text(text)) >= 80:
                link["status"] = "available"
                link["url"] = final_url
                link["content_sha256"] = hashlib.sha256(raw).hexdigest()
                if "/h91/" in final_url:
                    parsed = parse_html(raw, final_url)
                    epistle = dcs_reference_after_heading(parsed.text, "The Epistle")
                    gospel = dcs_reference_after_heading(parsed.text, "The Gospel")
                    if epistle and gospel:
                        observation.epistle_reference = epistle
                        observation.gospel_reference = gospel
                        observation.warnings.append("DCS regular-cycle references extracted; full Scripture text is not imported")
                available += 1
            else:
                link["status"] = "unusable"
        except urllib.error.HTTPError as exc:
            link["status"] = "http_error"
            link["http_status"] = str(exc.code)
        except Exception as exc:
            link["status"] = "network_error"
            link["reason"] = f"{type(exc).__name__}: {exc}"[:240]
    if available:
        observation.status = "current"
        observation.detected_date = observation.target_date
        observation.confidence = max(observation.confidence, min(0.95, 0.65 + available * 0.1))
    elif observation.status == "available":
        observation.status = "partial"
        observation.reason = "index available but dated service pages were not proven"
    return observation

def source_consensus(observations: list[ConnectorObservation]) -> dict[str, Any]:
    fields: dict[str, dict[str, list[str]]] = {"epistle_reference": {}, "gospel_reference": {}}
    for item in observations:
        if item.status not in {"current", "partial"} or not item.official:
            continue
        for field_name in fields:
            value = getattr(item, field_name)
            normalized = normalize_reference(value)
            if not normalized:
                continue
            fields[field_name].setdefault(normalized, []).append(item.connector_id)
    result: dict[str, Any] = {"status": "INSUFFICIENT_EVIDENCE", "fields": {}, "conflicts": []}
    for field_name, groups in fields.items():
        ranked = sorted(groups.items(), key=lambda pair: (-len(pair[1]), pair[0]))
        if not ranked:
            result["fields"][field_name] = {"status": "missing", "value": None, "sources": []}
            continue
        value, sources = ranked[0]
        field_status = "agreement" if len(sources) >= 2 else "single_source"
        result["fields"][field_name] = {"status": field_status, "normalized": value, "sources": sources}
        if len(ranked) > 1:
            result["conflicts"].append({
                "field": field_name,
                "variants": [{"normalized": variant, "sources": ids} for variant, ids in ranked],
            })
    if result["conflicts"]:
        result["status"] = "CONFLICT_REQUIRES_AUTHORITY_RULE"
    elif any(value["status"] == "agreement" for value in result["fields"].values()):
        result["status"] = "MULTI_SOURCE_AGREEMENT"
    elif any(value["status"] == "single_source" for value in result["fields"].values()):
        result["status"] = "SINGLE_SOURCE_ONLY"
    return result


def summarize_health(observations: list[ConnectorObservation]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for item in observations:
        counts[item.status] = counts.get(item.status, 0) + 1
    usable = sum(counts.get(status, 0) for status in ("current", "partial", "available", "undated"))
    return {
        "connector_count": len(observations),
        "usable_connector_count": usable,
        "official_current_count": sum(1 for item in observations if item.official and item.status == "current"),
        "status_counts": counts,
        "consensus": source_consensus(observations),
    }
