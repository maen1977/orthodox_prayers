#!/usr/bin/env python3
"""Compile complete native-language Orthodox church-service pages into offline APK assets.

BUILD-TIME ONLY. No Android runtime networking is introduced. The importer never
translates, transliterates, or copies content across language lanes.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
BUILDER_ID = "OrthodoxPrayers-ChurchServiceBuilder/5.6.6"
MAX_BYTES = 6_000_000
MAX_OPEN_SOURCE_BYTES = 80_000_000
MIN_CHARS_REQUIRED = 1200
MIN_CHARS_OPTIONAL = 500
MAX_SERVICE_CHARS = 80_000


class ParagraphParser(HTMLParser):
    """Prefer semantic text blocks; this avoids giant duplicated layout <div>s."""
    BLOCK_TAGS = {"p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "td"}
    IGNORE_TAGS = {"script", "style", "noscript", "svg", "form", "nav", "footer", "header"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ignore_depth = 0
        self.capture_depth = 0
        self.current: list[str] = []
        self.blocks: list[str] = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in self.IGNORE_TAGS:
            self.ignore_depth += 1
            return
        if self.ignore_depth:
            return
        if tag in self.BLOCK_TAGS:
            if self.capture_depth == 0:
                self.current = []
            self.capture_depth += 1
        elif tag == "br" and self.capture_depth:
            self.current.append("\n")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in self.IGNORE_TAGS:
            if self.ignore_depth:
                self.ignore_depth -= 1
            return
        if self.ignore_depth:
            return
        if tag in self.BLOCK_TAGS and self.capture_depth:
            self.capture_depth -= 1
            if self.capture_depth == 0:
                text = clean_text("".join(self.current))
                if text:
                    self.blocks.append(text)
                self.current = []

    def handle_data(self, data):
        if not self.ignore_depth and self.capture_depth:
            self.current.append(data)


class DivFallbackParser(HTMLParser):
    """Fallback for older liturgical pages whose article uses div + br instead of p."""
    IGNORE_TAGS = {"script", "style", "noscript", "svg", "form", "nav", "footer", "header"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ignore_depth = 0
        self.div_depth = 0
        self.current: list[str] = []
        self.blocks: list[str] = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in self.IGNORE_TAGS:
            self.ignore_depth += 1
            return
        if self.ignore_depth:
            return
        if tag == "div":
            if self.div_depth == 0:
                self.current = []
            self.div_depth += 1
        elif tag == "br" and self.div_depth:
            self.current.append("\n")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in self.IGNORE_TAGS:
            if self.ignore_depth:
                self.ignore_depth -= 1
            return
        if self.ignore_depth:
            return
        if tag == "div" and self.div_depth:
            self.div_depth -= 1
            if self.div_depth == 0:
                text = clean_text("".join(self.current))
                if text:
                    self.blocks.extend([clean_text(x) for x in text.split("\n") if clean_text(x)])
                self.current = []

    def handle_data(self, data):
        if not self.ignore_depth and self.div_depth:
            self.current.append(data)


class LegacyBrFlowParser(HTMLParser):
    """Parse legacy GLT pages whose service text is body-flow plus <br/> lines."""
    IGNORE_TAGS = {"script", "style", "noscript", "svg", "form", "nav", "footer", "header"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ignore_depth = 0
        self.capture = False
        self.current: list[str] = []
        self.blocks: list[str] = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in self.IGNORE_TAGS:
            self.ignore_depth += 1
            return
        if self.ignore_depth:
            return
        if tag == "body":
            self.capture = True
        elif tag == "br" and self.capture:
            self.flush()

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in self.IGNORE_TAGS:
            if self.ignore_depth:
                self.ignore_depth -= 1
            return
        if self.ignore_depth:
            return
        if tag == "p" and self.capture:
            self.flush()
        elif tag == "body":
            self.flush()
            self.capture = False

    def handle_data(self, data):
        if self.capture and not self.ignore_depth:
            self.current.append(data)

    def flush(self):
        text = clean_text("".join(self.current))
        self.current = []
        if text:
            self.blocks.append(text)


def clean_text(value: str) -> str:
    value = html.unescape(value).replace("\xa0", " ")
    value = value.replace("\u200f", "").replace("\u200e", "")
    value = re.sub(r"[ \t\r\f\v]+", " ", value)
    value = re.sub(r"\n\s*\n+", "\n", value)
    return value.strip()


def iri_to_uri(value: str) -> str:
    parts = urllib.parse.urlsplit(value)
    path = urllib.parse.quote(urllib.parse.unquote(parts.path), safe="/%:@")
    query = urllib.parse.quote(urllib.parse.unquote(parts.query), safe="=&%:+,;@/?_")
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, path, query, parts.fragment))


def _validate_download(data: bytes) -> bytes:
    if len(data) > MAX_BYTES:
        raise RuntimeError("source_too_large")
    if len(data) < 500:
        raise RuntimeError("source_too_small")
    probe = data[:5000].lower()
    if b"<html" not in probe and b"<!doctype html" not in probe:
        raise RuntimeError("source_not_html")
    return data


def _direct_headers(url: str) -> dict[str, str]:
    return {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ar,en-US;q=0.9,en;q=0.8,el;q=0.7",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "X-Orthodox-Prayers-Builder": BUILDER_ID,
    }


def fetch(url: str, cache: Path) -> bytes:
    """Fetch an explicitly registered HTML source without browser/proxy circumvention."""
    cache.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(url.encode("utf-8")).hexdigest() + ".html"
    target = cache / key
    if target.exists() and target.stat().st_size > 500:
        return target.read_bytes()
    last = None
    request_url = iri_to_uri(url)
    for attempt in range(3):
        try:
            req = urllib.request.Request(request_url, headers=_direct_headers(url))
            with urllib.request.urlopen(req, timeout=45) as response:
                if getattr(response, "status", 200) >= 400:
                    raise RuntimeError(f"http_status_{response.status}")
                data = response.read(MAX_BYTES + 1)
            _validate_download(data)
            target.write_bytes(data)
            return data
        except Exception as exc:  # pragma: no cover - network branch
            last = exc
            time.sleep(1.25 * (attempt + 1))
    raise RuntimeError(f"download_failed:{url}:{last}")


def _fetch_open_source(url: str, cache: Path, suffix: str = ".src") -> bytes:
    """Fetch a redistributable/public-domain source without HTML-only validation."""
    cache.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(url.encode("utf-8")).hexdigest() + suffix
    target = cache / key
    if target.exists() and target.stat().st_size > 500:
        return target.read_bytes()
    request_url = iri_to_uri(url)
    req = urllib.request.Request(request_url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=90) as response:
        if getattr(response, "status", 200) >= 400:
            raise RuntimeError(f"http_status_{response.status}")
        data = response.read(MAX_OPEN_SOURCE_BYTES + 1)
    if len(data) > MAX_OPEN_SOURCE_BYTES:
        raise RuntimeError("open_source_too_large")
    if len(data) < 500:
        raise RuntimeError("open_source_too_small")
    target.write_bytes(data)
    return data


def _pdf_to_text(raw: bytes) -> bytes:
    exe = shutil.which("pdftotext")
    if not exe:
        raise RuntimeError("pdftotext_unavailable")
    with tempfile.TemporaryDirectory(prefix="orthodox-prayers-euchologion-") as tmp:
        pdf = Path(tmp) / "source.pdf"
        txt = Path(tmp) / "source.txt"
        pdf.write_bytes(raw)
        completed = subprocess.run(
            [exe, "-layout", "-enc", "UTF-8", str(pdf), str(txt)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180, check=False,
        )
        if completed.returncode != 0 or not txt.exists():
            detail = completed.stderr.decode("utf-8", errors="replace").strip().replace("\n", " ")[-500:]
            raise RuntimeError(f"pdftotext_failed:{completed.returncode}:{detail}")
        data = txt.read_bytes()
    if len(data) < 1200:
        raise RuntimeError(f"pdf_text_too_short:{len(data)}")
    return data


def _pdf_to_ocr_text(raw: bytes, spec: dict) -> bytes:
    """OCR only registered page ranges of a scanned native-language PDF.

    This is a build-time transcription path, not translation or rewriting. Page
    ranges and language are explicit in the manifest so a scanned source cannot
    silently expand into neighboring rites.
    """
    pdftoppm = shutil.which("pdftoppm")
    tesseract = shutil.which("tesseract")
    if not pdftoppm or not tesseract:
        raise RuntimeError("pdf_ocr_tools_unavailable")
    page_ranges = spec.get("ocr_page_ranges") or []
    if not page_ranges:
        raise RuntimeError("pdf_ocr_page_ranges_missing")
    ocr_language = str(spec.get("ocr_language", "ell"))
    dpi = str(int(spec.get("ocr_dpi", 300)))
    psm = str(int(spec.get("ocr_psm", 6)))
    with tempfile.TemporaryDirectory(prefix="orthodox-prayers-euchologion-ocr-") as tmp:
        root = Path(tmp)
        pdf = root / "source.pdf"
        images = root / "images"
        texts = root / "texts"
        images.mkdir()
        texts.mkdir()
        pdf.write_bytes(raw)
        rendered: list[Path] = []
        for page_range in page_ranges:
            if not isinstance(page_range, list) or len(page_range) != 2:
                raise RuntimeError("pdf_ocr_invalid_page_range")
            start, end = (int(page_range[0]), int(page_range[1]))
            if start < 1 or end < start:
                raise RuntimeError("pdf_ocr_invalid_page_range")
            prefix = images / f"range_{start}_{end}"
            completed = subprocess.run(
                [pdftoppm, "-f", str(start), "-l", str(end), "-r", dpi,
                 "-jpeg", "-jpegopt", "quality=90", str(pdf), str(prefix)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300, check=False,
            )
            if completed.returncode != 0:
                detail = completed.stderr.decode("utf-8", errors="replace").strip()[-500:]
                raise RuntimeError(f"pdf_ocr_render_failed:{detail}")
            rendered.extend(sorted(images.glob(f"range_{start}_{end}-*.jpg")))
        output: list[str] = []
        for image in rendered:
            page_name = image.stem.rsplit("-", 1)[-1]
            target = texts / f"page-{page_name}"
            completed = subprocess.run(
                [tesseract, str(image), str(target), "-l", ocr_language, "--psm", psm],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120, check=False,
            )
            if completed.returncode != 0 or not target.with_suffix(".txt").exists():
                detail = completed.stderr.decode("utf-8", errors="replace").strip()[-500:]
                raise RuntimeError(f"pdf_ocr_text_failed:{page_name}:{detail}")
            output.append(f"===== PHYSICAL_PAGE {page_name} =====\n")
            output.append(target.with_suffix(".txt").read_text(encoding="utf-8", errors="replace"))
        data = "\n".join(output).encode("utf-8")
    if len(data) < 1200:
        raise RuntimeError(f"pdf_ocr_text_too_short:{len(data)}")
    return data


def _fold_marker(value: str) -> str:
    import unicodedata
    value = unicodedata.normalize("NFD", value.casefold())
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", value).strip()


def parse_plain_text_blocks(raw: bytes) -> list[str]:
    text = raw.decode("utf-8", errors="replace").replace("\ufeff", "").replace("\f", "\n")
    # OCR/plain-text books often wrap every printed line. Keep lines as blocks; later
    # deduplication and section boundaries protect us from table-of-contents matches.
    return [clean_text(line) for line in text.splitlines() if len(clean_text(line)) > 1]


def find_marker_occurrence(blocks: list[str], markers, occurrence: str = "first") -> int | None:
    if not markers:
        return None
    if isinstance(markers, str):
        markers = [markers]
    folded = [_fold_marker(str(m)) for m in markers if str(m).strip()]
    hits=[]
    for i, block in enumerate(blocks):
        b = _fold_marker(block)
        if any(m in b for m in folded):
            hits.append(i)
    if not hits:
        return None
    return hits[-1] if occurrence == "last" else hits[0]


def normalize_open_source_blocks(raw: bytes, language: str, spec: dict) -> list[str]:
    blocks = parse_plain_text_blocks(raw)
    start = find_marker_occurrence(blocks, spec.get("start_marker"), spec.get("marker_occurrence", "last"))
    if start is None:
        raise RuntimeError(f"open_source_start_marker_missing:{language}:{spec['id']}")
    blocks = blocks[start:]
    end = find_marker_occurrence(blocks[1:], spec.get("end_marker"), "first")
    if end is not None:
        # The search runs on blocks[1:], so +1 keeps the block before the next heading.
        blocks = blocks[:end + 1]
    blocks = apply_script_filter(blocks, spec.get("filter_script"))
    # Remove repeated page headers/page numbers without rewriting the source.
    result=[]
    seen=set()
    for block in blocks:
        if re.fullmatch(r"[ivxlcdm\d\-–—. ]{1,12}", block.casefold()):
            continue
        fp=re.sub(r"\s+", " ", block).strip()
        # Internet Archive OCR occasionally leaves a standalone HTML table token.
        if re.fullmatch(r"</?(?:td|tr|table|tbody|thead)(?:\s[^>]*)?>?", fp, flags=re.IGNORECASE):
            continue
        if len(fp) > 80 and fp in seen:
            continue
        result.append(block)
        if len(fp) > 80:
            seen.add(fp)
    return result


def _fetch_cc_pdf_ocr_text(spec: dict, cache: Path) -> bytes:
    cache.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256((spec["url"] + json.dumps(spec.get("ocr_page_ranges", []), sort_keys=True)).encode("utf-8")).hexdigest()
    txt = cache / (key + ".pdf-ocr.txt")
    if txt.exists() and txt.stat().st_size > 1200:
        return txt.read_bytes()
    pdf = _fetch_open_source(spec["url"], cache, ".pdf")
    data = _pdf_to_ocr_text(pdf, spec)
    txt.write_bytes(data)
    return data


def _fetch_cc_pdf_text(url: str, cache: Path) -> bytes:
    cache.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(url.encode("utf-8")).hexdigest()
    txt = cache / (key + ".pdftotext.txt")
    if txt.exists() and txt.stat().st_size > 1200:
        return txt.read_bytes()
    pdf = _fetch_open_source(url, cache, ".pdf")
    data = _pdf_to_text(pdf)
    txt.write_bytes(data)
    return data


def _fetch_local_native_text(spec: dict) -> bytes:
    path = Path(spec.get("local_path", ""))
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[1] / path
    if not path.exists():
        raise RuntimeError(f"local_source_missing:{path}")
    data = path.read_bytes()
    if len(data) < 500:
        raise RuntimeError("local_source_too_small")
    return data


def fetch_spec(spec: dict, cache: Path) -> bytes:
    transport = spec.get("source_transport", "html")
    if transport == "local_native_ocr_text":
        return _fetch_local_native_text(spec)
    if transport == "public_domain_plain_text":
        return _fetch_open_source(spec["url"], cache, ".txt")
    if transport == "cc_by_pdf_ocr_text":
        return _fetch_cc_pdf_ocr_text(spec, cache)
    if transport == "cc_by_pdf_text":
        return _fetch_cc_pdf_text(spec["url"], cache)
    if transport == "official_link_only":
        raise RuntimeError("official_link_only")
    return fetch(spec["url"], cache)

def parse_blocks(raw: bytes) -> list[str]:
    text = raw.decode("utf-8", errors="replace")
    primary = ParagraphParser()
    primary.feed(text)
    blocks = [clean_text(x) for x in primary.blocks if clean_text(x)]
    if sum(map(len, blocks)) >= 900:
        return blocks
    fallback = DivFallbackParser()
    fallback.feed(text)
    fallback_blocks = [clean_text(x) for x in fallback.blocks if clean_text(x)]
    if sum(map(len, fallback_blocks)) >= 900:
        return fallback_blocks

    # A few older official liturgical pages use one body-flow stream with <br/>.
    # Use this parser only when the semantic parsers did not obtain a substantial
    # text body, so modern pages keep their existing extraction behavior.
    legacy_blocks: list[str] = []
    if re.search(r"<br\s*/?>", text, flags=re.IGNORECASE):
        legacy = LegacyBrFlowParser()
        legacy.feed(text)
        legacy.close()
        legacy_blocks = [clean_text(x) for x in legacy.blocks if clean_text(x)]
    candidates = (blocks, fallback_blocks, legacy_blocks)
    return max(candidates, key=lambda value: sum(map(len, value)))


def apply_script_filter(blocks: list[str], mode: str | None) -> list[str]:
    if not mode:
        return blocks
    result=[]
    for block in blocks:
        greek=len(re.findall(r"[\u0370-\u03ff\u1f00-\u1fff]", block))
        latin=len(re.findall(r"[A-Za-z]", block))
        if mode == "greek":
            if greek > 0 and greek >= latin:
                result.append(block)
        elif mode == "latin":
            if latin > 0 and latin >= greek:
                result.append(block)
        else:
            result.append(block)
    return result


def find_marker(blocks: list[str], markers) -> int | None:
    if not markers:
        return None
    if isinstance(markers, str):
        markers = [markers]
    folded = [m.casefold().strip() for m in markers if str(m).strip()]
    for i, block in enumerate(blocks):
        b = block.casefold()
        if any(m in b for m in folded):
            return i
    return None


def normalize_blocks(raw: bytes, language: str, spec: dict) -> list[str]:
    if spec.get("source_transport") in {"public_domain_plain_text", "cc_by_pdf_text", "cc_by_pdf_ocr_text", "local_native_ocr_text"}:
        return normalize_open_source_blocks(raw, language, spec)
    blocks = parse_blocks(raw)
    nav_exact = {
        "الفئات", "وسم", "تحميل الصلاة", "اقرأ المزيد", "Print", "View »",
        "Liturgical Texts of the Orthodox Church", "Ελληνικά English", "English Ελληνικά", "Image",
    }
    blocks = [b for b in blocks if b not in nav_exact]

    # Explicit markers are the strongest boundary and are source-specific.
    marker_index = find_marker(blocks, spec.get("start_marker"))
    if marker_index is not None:
        blocks = blocks[marker_index:]
    else:
        # Fall back to exact article title when the site exposes it in semantic HTML.
        title_fold = re.sub(r"\s+", " ", spec["title"]).strip().casefold()
        for i, block in enumerate(blocks):
            if re.sub(r"\s+", " ", block).strip().casefold() == title_fold:
                blocks = blocks[i + 1:]
                break

    end_index = find_marker(blocks, spec.get("end_marker"))
    if end_index is not None and end_index > 0:
        blocks = blocks[:end_index]

    # Bilingual DCS pages are sliced before script filtering so a Greek or English
    # marker can establish the same service boundary for both native lanes.
    blocks = apply_script_filter(blocks, spec.get("filter_script"))

    if language == "ar" and not spec.get("start_marker"):
        liturgical_markers = ("الكاهن", "القارئ", "الجوق", "المرتل", "أ:", "ب:", "يتوجه", "يدخل", "تقام", "يلبس")
        for i, block in enumerate(blocks[:30]):
            if block.startswith(liturgical_markers) or any(m in block[:100] for m in liturgical_markers):
                blocks = blocks[i:]
                break

    stop_markers = (
        "5921146", "info@orthodoxjordan.org", "What's New on GOARCH?",
        "Privacy Policy", "Terms of Use", "View »", "Related Articles",
    )
    trimmed: list[str] = []
    for block in blocks:
        if any(marker in block for marker in stop_markers):
            break
        if len(block) <= 1:
            continue
        trimmed.append(block)

    result: list[str] = []
    seen_recent: list[str] = []
    for block in trimmed:
        if result and block == result[-1]:
            continue
        # Responsive pages can duplicate a whole paragraph a few blocks later.
        fingerprint = re.sub(r"\s+", " ", block).strip()
        if len(fingerprint) > 80 and fingerprint in seen_recent[-12:]:
            continue
        result.append(block)
        seen_recent.append(fingerprint)
    return result


def lane_object(lang: str, value: str) -> dict:
    return {"ar": value if lang == "ar" else "", "en": value if lang == "en" else "", "el": value if lang == "el" else ""}


def block_to_segment(block: str, lang: str) -> dict:
    short = len(block) <= 125
    heading_prefixes = (
        "###", "####", "ΑΚΟΛΟΥΘΙΑ", "Ἀκολουθία", "ΤΡΙΣΑΓΙΟ", "صلاة ", "خدمة ",
        "المزمور", "الرسالة", "الإنجيل", "The ", "Prayer", "Dismissal", "Epistle", "Holy Gospel",
    )
    looks_heading = short and (block.endswith(":") or block.startswith(heading_prefixes))
    if looks_heading:
        return {"type": "section", "title": lane_object(lang, block)}
    # Preserve rubrics as text; the source wording itself identifies priest/reader/choir.
    return {"type": "text", "text": lane_object(lang, block)}


def summary_for(lang: str) -> str:
    if lang == "ar":
        return "النص الطقسي الكامل من المصدر الكنسي الأصلي، محفوظ داخل التطبيق للعمل دون اتصال."
    if lang == "el":
        return "Πλήρες λειτουργικό κείμενο από την πρωτότυπη εκκλησιαστική πηγή, αποθηκευμένο για χρήση χωρίς σύνδεση."
    return "Complete liturgical text from the original Church source, bundled for offline use."


def build_service(spec: dict, lang: str, source_id: str, source_name: str, raw: bytes) -> dict:
    blocks = normalize_blocks(raw, lang, spec)
    chars = sum(len(b) for b in blocks)
    minimum = int(spec.get("min_chars", MIN_CHARS_REQUIRED if spec.get("required") else MIN_CHARS_OPTIONAL))
    maximum = int(spec.get("max_chars", MAX_SERVICE_CHARS))
    if chars < minimum:
        raise RuntimeError(f"service_too_short:{lang}:{spec['id']}:{chars}<{minimum}")
    if chars > maximum:
        raise RuntimeError(f"service_too_large:{lang}:{spec['id']}:{chars}>{maximum}")
    segments = [block_to_segment(b, lang) for b in blocks]
    if not segments:
        raise RuntimeError(f"service_empty:{lang}:{spec['id']}")
    digest = hashlib.sha256(raw).hexdigest()
    service_source_id = spec.get("source_id", source_id)
    service_source_name = spec.get("source_name", source_name)
    return {
        "id": spec["id"],
        "category": "church_service",
        "title": lane_object(lang, spec["title"]),
        "summary": lane_object(lang, summary_for(lang)),
        "icon": spec.get("icon", "☦"),
        "segments": segments,
        "content_mode": "FULL_AUTHORIZED_NATIVE_RITE_TEXT",
        "publication_status": "FULL_NATIVE_RITE_TEXT_BUNDLED_OFFLINE",
        "full_service": True,
        "native_source": {
            "source_id": service_source_id,
            "name": service_source_name,
            "official": True,
            "native_language": lang,
            "url": spec["url"],
            "permission_confirmed": bool(spec.get("permission_confirmed", False)),
            "redistribution_review_required": bool(spec.get("redistribution_review_required", not spec.get("permission_confirmed", False))),
            "rights_basis": spec.get("rights_basis", "REVIEW_REQUIRED"),
            "license_url": spec.get("license_url", ""),
            "machine_translation_used": False,
            "import_status": "FULL_AUTHORIZED_NATIVE_RITE_TEXT",
            "content_sha256": digest,
        },
        "source_word_count": sum(len(b.split()) for b in blocks),
        "source_character_count": chars,
        "source_block_count": len(blocks),
    }


def redistribution_allowed(spec: dict) -> bool:
    """Only bundle source text when redistribution is explicitly recorded as allowed."""
    return bool(spec.get("permission_confirmed", False)) and not bool(spec.get("redistribution_review_required", True))


def _source_key(lang: str, spec: dict) -> tuple[str, str, str]:
    transport = spec.get("source_transport", "html")
    identity = spec.get("local_path") or spec.get("url", "")
    if transport in {"cc_by_pdf_ocr_text", "local_native_ocr_text"}:
        identity = identity + "|" + json.dumps(spec.get("ocr_page_ranges", []), sort_keys=True, ensure_ascii=False)
    return (lang, transport, identity)


def prefetch_registered_sources(manifest: dict, cache: Path) -> dict[tuple[str, str, str], bytes | Exception]:
    """Fetch each distinct registered source once, concurrently, before service slicing.

    This keeps the native-language policy unchanged while preventing ten independent
    network waits from serializing the GitHub Actions build. Shared English/Greek
    source books are fetched/converted only once per run.
    """
    jobs: dict[tuple[str, str, str], tuple[str, dict]] = {}
    for lang, lane in manifest.get("languages", {}).items():
        for spec in lane.get("services", []):
            if spec.get("source_transport") == "official_link_only" or not redistribution_allowed(spec):
                continue
            key = _source_key(lang, spec)
            jobs.setdefault(key, (lang, spec))

    results: dict[tuple[str, str, str], bytes | Exception] = {}
    if not jobs:
        return results

    workers = min(8, max(1, len(jobs)))
    print(f"CHURCH_SERVICE_PREFETCH_START unique_sources={len(jobs)} workers={workers}", flush=True)
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="church-source") as pool:
        future_map = {}
        for key, (lang, spec) in jobs.items():
            transport = spec.get("source_transport", "html")
            print(f"CHURCH_SERVICE_FETCH_START {lang} {spec['id']} transport={transport}", flush=True)
            future_map[pool.submit(fetch_spec, spec, cache / lang)] = (key, lang, spec)
        for future in as_completed(future_map):
            key, lang, spec = future_map[future]
            try:
                raw = future.result()
                results[key] = raw
                print(f"CHURCH_SERVICE_FETCH_OK {lang} {spec['id']} bytes={len(raw)}", flush=True)
            except Exception as exc:
                results[key] = exc
                print(f"CHURCH_SERVICE_FETCH_FALLBACK {lang} {spec['id']} {exc}", flush=True)
    print("CHURCH_SERVICE_PREFETCH_DONE", flush=True)
    return results


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="canonical/church_service_full_sources.json")
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--cache-dir", required=True)
    ap.add_argument("--allow-partial", action="store_true")
    args = ap.parse_args()

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    if manifest.get("policy") not in {"AUTHORIZED_NATIVE_SOURCE_ONLY_NO_TRANSLATION", "RIGHTS_VERIFIED_NATIVE_SOURCE_ONLY_NO_TRANSLATION", "RIGHTS_AWARE_NATIVE_SOURCE_ONLY_NO_TRANSLATION"}:
        raise SystemExit("invalid_church_service_source_policy")
    out = Path(args.output_dir)
    cache = Path(args.cache_dir)
    out.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    prefetched = prefetch_registered_sources(manifest, cache)

    for lang, lane in manifest["languages"].items():
        if lang not in {"ar", "en", "el"}:
            failures.append(f"unsupported_language:{lang}")
            continue
        services = []
        fallbacks = []
        ids = set()
        for spec in lane.get("services", []):
            if spec["id"] in ids:
                failures.append(f"duplicate_service:{lang}:{spec['id']}")
                continue
            ids.add(spec["id"])
            try:
                if spec.get("source_transport") == "official_link_only" or not redistribution_allowed(spec):
                    print(f"CHURCH_SERVICE_RIGHTS_LINK_ONLY {lang} {spec['id']} {spec['url']}", flush=True)
                    fallbacks.append({
                        "id": spec["id"],
                        "title": lane_object(lang, spec["title"]),
                        "official_source_url": spec.get("url", ""),
                        "publication_status": "OFFICIAL_SOURCE_LINK_ONLY_RIGHTS_PENDING",
                        "full_service": False,
                        "reason": "redistribution_permission_not_confirmed",
                        "machine_translation_used": False,
                        "cross_language_fallback": False,
                    })
                    continue
                cached = prefetched.get(_source_key(lang, spec))
                if isinstance(cached, Exception):
                    raise cached
                raw = cached if isinstance(cached, bytes) else fetch_spec(spec, cache / lang)
                svc = build_service(spec, lang, lane["source_id"], lane["source_name"], raw)
                services.append(svc)
                print(f"CHURCH_SERVICE_OK {lang} {spec['id']} chars={svc['source_character_count']} blocks={svc['source_block_count']}", flush=True)
            except Exception as exc:
                if spec.get("required") and not spec.get("allow_link_fallback", False):
                    failures.append(f"{lang}:{spec['id']}:{exc}")
                else:
                    is_link_fallback = bool(spec.get("allow_link_fallback", False))
                    label = "CHURCH_SERVICE_LINK_FALLBACK" if is_link_fallback else "CHURCH_SERVICE_OPTIONAL_SKIP"
                    print(f"{label} {lang} {spec['id']} {exc}", flush=True)
                    if is_link_fallback:
                        fallbacks.append({
                            "id": spec["id"],
                            "title": lane_object(lang, spec["title"]),
                            "official_source_url": spec.get("url", ""),
                            "publication_status": "OFFICIAL_SOURCE_LINK_ONLY_BUILD_FALLBACK",
                            "full_service": False,
                            "reason": str(exc),
                            "machine_translation_used": False,
                            "cross_language_fallback": False,
                        })
        payload = {
            "schema_version": 2,
            "language": lang,
            "content_mode": "FULL_AUTHORIZED_NATIVE_RITE_TEXT",
            "source_policy": manifest["policy"],
            "machine_translation_used": False,
            "cross_language_fallback": False,
            "runtime_network_required": False,
            "services": services,
            "fallbacks": fallbacks,
        }
        (out / f"full_services_{lang}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    if failures and not args.allow_partial:
        for failure in failures:
            print("CHURCH_SERVICE_REQUIRED_FAILURE", failure, flush=True)
        return 2
    fallback_count = 0
    for lang in manifest["languages"].keys():
        path = out / f"full_services_{lang}.json"
        if path.exists():
            try:
                fallback_count += len(json.loads(path.read_text(encoding="utf-8")).get("fallbacks", []))
            except Exception:
                pass
    print(f"CHURCH_SERVICE_CORPUS_OK failures={len(failures)} fallbacks={fallback_count}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
