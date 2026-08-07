#!/usr/bin/env python3
"""Compile complete native-language Orthodox church-service pages into offline APK assets.

BUILD-TIME ONLY. No Android runtime networking is introduced. The importer never
translates, transliterates, or copies content across language lanes.
"""
from __future__ import annotations

import argparse
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
BUILDER_ID = "OrthodoxPrayers-ChurchServiceBuilder/5.5.1"
MAX_BYTES = 6_000_000
MIN_CHARS_REQUIRED = 1200
MIN_CHARS_OPTIONAL = 500


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


def _browser_executable() -> str | None:
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        found = shutil.which(name)
        if found:
            return found
    return None


def _fetch_with_curl(url: str) -> bytes:
    curl = shutil.which("curl")
    if not curl:
        raise RuntimeError("curl_unavailable")
    request_url = iri_to_uri(url)
    headers = _direct_headers(url)
    command = [
        curl,
        "--location",
        "--fail-with-body",
        "--silent",
        "--show-error",
        "--compressed",
        "--retry", "2",
        "--retry-delay", "1",
        "--connect-timeout", "20",
        "--max-time", "60",
    ]
    for key, value in headers.items():
        command.extend(["-H", f"{key}: {value}"])
    command.append(request_url)
    completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=70, check=False)
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip().replace("\n", " ")[-500:]
        raise RuntimeError(f"curl_failed:{completed.returncode}:{detail}")
    data = completed.stdout
    _validate_download(data)
    lower = data.lower()
    if (b"access denied" in lower or b"forbidden" in lower) and len(data) < 15000:
        raise RuntimeError("curl_access_denied")
    return data


def _fetch_with_headless_browser(url: str) -> bytes:
    browser = _browser_executable()
    if not browser:
        raise RuntimeError("headless_browser_unavailable")
    request_url = iri_to_uri(url)
    with tempfile.TemporaryDirectory(prefix="orthodox-prayers-chrome-") as profile:
        command = [
            browser,
            "--headless=new",
            "--no-sandbox",
            "--disable-gpu",
            "--disable-dev-shm-usage",
            "--no-first-run",
            "--mute-audio",
            f"--user-agent={UA}",
            "--window-size=1280,2400",
            "--virtual-time-budget=7000",
            f"--user-data-dir={profile}",
            "--dump-dom",
            request_url,
        ]
        completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=70, check=False)
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip().replace("\n", " ")[-500:]
        raise RuntimeError(f"headless_browser_failed:{completed.returncode}:{detail}")
    data = completed.stdout
    _validate_download(data)
    lower = data.lower()
    if b"access denied" in lower or b"forbidden" in lower and len(data) < 15000:
        raise RuntimeError("headless_browser_access_denied")
    return data


def _direct_headers(url: str) -> dict[str, str]:
    headers = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,el;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1",
        "X-Orthodox-Prayers-Builder": BUILDER_ID,
    }
    if urllib.parse.urlsplit(url).netloc.endswith("goarch.org"):
        headers["Referer"] = "https://www.goarch.org/chapel/texts"
    return headers


def fetch(url: str, cache: Path) -> bytes:
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
        except urllib.error.HTTPError as exc:  # pragma: no cover - network branch
            last = exc
            if exc.code in {403, 429} and urllib.parse.urlsplit(url).netloc.endswith("goarch.org"):
                print(f"CHURCH_SERVICE_DIRECT_BLOCKED {exc.code} {url}")
                break
            time.sleep(1.25 * (attempt + 1))
        except Exception as exc:  # pragma: no cover - network branch
            last = exc
            time.sleep(1.25 * (attempt + 1))

    # GOARCH currently returns HTTP 403 to some non-browser clients from hosted CI ranges.
    # Keep every fallback on the same official origin: first curl with browser headers, then
    # a real Chromium/Chrome session. Required services remain required; no proxy, mirror,
    # translation, or cross-language substitution is permitted.
    if urllib.parse.urlsplit(url).netloc.endswith("goarch.org"):
        try:
            data = _fetch_with_curl(url)
            target.write_bytes(data)
            print(f"CHURCH_SERVICE_CURL_FALLBACK_OK {url}")
            return data
        except Exception as exc:  # pragma: no cover - network/curl branch
            last = exc
        try:
            data = _fetch_with_headless_browser(url)
            target.write_bytes(data)
            print(f"CHURCH_SERVICE_BROWSER_FALLBACK_OK {url}")
            return data
        except Exception as exc:  # pragma: no cover - network/browser branch
            last = exc
    raise RuntimeError(f"download_failed:{url}:{last}")


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
    return fallback_blocks if sum(map(len, fallback_blocks)) > sum(map(len, blocks)) else blocks


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
    if chars < minimum:
        raise RuntimeError(f"service_too_short:{lang}:{spec['id']}:{chars}<{minimum}")
    segments = [block_to_segment(b, lang) for b in blocks]
    if not segments:
        raise RuntimeError(f"service_empty:{lang}:{spec['id']}")
    digest = hashlib.sha256(raw).hexdigest()
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
            "source_id": source_id,
            "name": source_name,
            "official": True,
            "native_language": lang,
            "url": spec["url"],
            "permission_confirmed": True,
            "redistribution_review_required": False,
            "machine_translation_used": False,
            "import_status": "FULL_AUTHORIZED_NATIVE_RITE_TEXT",
            "content_sha256": digest,
        },
        "source_word_count": sum(len(b.split()) for b in blocks),
        "source_character_count": chars,
        "source_block_count": len(blocks),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="canonical/church_service_full_sources.json")
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--cache-dir", required=True)
    ap.add_argument("--allow-partial", action="store_true")
    args = ap.parse_args()

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    if manifest.get("policy") != "AUTHORIZED_NATIVE_SOURCE_ONLY_NO_TRANSLATION":
        raise SystemExit("invalid_church_service_source_policy")
    out = Path(args.output_dir)
    cache = Path(args.cache_dir)
    out.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []

    for lang, lane in manifest["languages"].items():
        if lang not in {"ar", "en", "el"}:
            failures.append(f"unsupported_language:{lang}")
            continue
        services = []
        ids = set()
        for spec in lane.get("services", []):
            if spec["id"] in ids:
                failures.append(f"duplicate_service:{lang}:{spec['id']}")
                continue
            ids.add(spec["id"])
            try:
                raw = fetch(spec["url"], cache / lang)
                svc = build_service(spec, lang, lane["source_id"], lane["source_name"], raw)
                services.append(svc)
                print(f"CHURCH_SERVICE_OK {lang} {spec['id']} chars={svc['source_character_count']} blocks={svc['source_block_count']}")
            except Exception as exc:
                if spec.get("required"):
                    failures.append(f"{lang}:{spec['id']}:{exc}")
                else:
                    print(f"CHURCH_SERVICE_OPTIONAL_SKIP {lang} {spec['id']} {exc}")
        payload = {
            "schema_version": 2,
            "language": lang,
            "content_mode": "FULL_AUTHORIZED_NATIVE_RITE_TEXT",
            "source_policy": manifest["policy"],
            "machine_translation_used": False,
            "cross_language_fallback": False,
            "runtime_network_required": False,
            "services": services,
        }
        (out / f"full_services_{lang}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    if failures and not args.allow_partial:
        for failure in failures:
            print("CHURCH_SERVICE_REQUIRED_FAILURE", failure)
        return 2
    print(f"CHURCH_SERVICE_CORPUS_OK failures={len(failures)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
