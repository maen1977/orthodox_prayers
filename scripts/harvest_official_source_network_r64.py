#!/usr/bin/env python3
"""R64 exhaustive-but-bounded harvester for the public Jerusalem/Jordan network.

The owner has stated that the project has the needed content permissions.  This
crawler still remains deliberately non-invasive: public HTTP(S) only, no auth or
CAPTCHA bypass, and recursive navigation is restricted to the institutional
network declared in canonical/r64_official_source_network.json.

Raw public responses are cached under app/build so repeated GitHub builds do not
re-download the same corpus.  The canonical output contains metadata, hashes,
plain-text search excerpts, discovered official URLs, and external social links;
it does not copy binary bodies into the repository.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from threading import Lock
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
NETWORK = ROOT / "canonical" / "r64_official_source_network.json"
DEFAULT_CACHE = ROOT / "app" / "build" / "official-source-harvest-r64"
DEFAULT_OUTPUT = ROOT / "canonical" / "r64_official_source_harvest.json"
UA = "OrthodoxPrayers/5.6.5 R64 official-source-audit (authorized public-source harvester)"
SOCIAL_HOSTS = {
    "youtube.com", "www.youtube.com", "youtu.be", "facebook.com", "www.facebook.com",
    "instagram.com", "www.instagram.com", "x.com", "twitter.com", "t.me", "telegram.me",
    "wa.me", "whatsapp.com", "www.whatsapp.com",
}
TEXT_CONTENT_TYPES = ("text/html", "text/plain", "application/xhtml+xml", "application/xml", "text/xml")
PDF_CONTENT_TYPES = ("application/pdf",)


class LinkTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []
        self._text: list[str] = []
        self.title = ""
        self._in_title = False
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag.lower() in {"a", "link"}:
            href = attrs.get("href")
            if href: self.links.append(href)
        if tag.lower() in {"iframe", "video", "audio", "source", "embed"}:
            src = attrs.get("src")
            if src: self.links.append(src)
        if tag.lower() == "title": self._in_title = True
    def handle_endtag(self, tag):
        if tag.lower() == "title": self._in_title = False
    def handle_data(self, data):
        data = " ".join(str(data).split())
        if data:
            self._text.append(data)
            if self._in_title: self.title += (" " if self.title else "") + data
    @property
    def text(self) -> str:
        return "\n".join(self._text)


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalized_url(url: str) -> str:
    p = urllib.parse.urlsplit(url.strip())
    if p.scheme not in {"http", "https"}: return ""
    host = (p.hostname or "").lower().strip(".")
    if not host: return ""
    port = f":{p.port}" if p.port and not ((p.scheme == "https" and p.port == 443) or (p.scheme == "http" and p.port == 80)) else ""
    path = re.sub(r"/{2,}", "/", p.path or "/")
    # Tracking/query fragments never define ecclesiastical content identity.
    return urllib.parse.urlunsplit((p.scheme.lower(), host + port, path, p.query if _keep_query(p.query) else "", ""))


def _keep_query(query: str) -> bool:
    if not query: return False
    keys = {k.casefold() for k, _ in urllib.parse.parse_qsl(query, keep_blank_values=True)}
    # Keep pagination/date/search identity but throw away common tracking params.
    return bool(keys - {"utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term", "fbclid", "gclid"})


def host_allowed(host: str, suffixes: Iterable[str]) -> bool:
    host = (host or "").lower().strip(".")
    return any(host == suffix or host.endswith("." + suffix) for suffix in suffixes)


def cache_path(cache_dir: Path, url: str) -> Path:
    key = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return cache_dir / key[:2] / (key + ".bin")


def meta_path(cache_dir: Path, url: str) -> Path:
    return cache_path(cache_dir, url).with_suffix(".json")


def read_cache(cache_dir: Path, url: str):
    rawp, metap = cache_path(cache_dir, url), meta_path(cache_dir, url)
    if rawp.is_file() and metap.is_file():
        try: return rawp.read_bytes(), json.loads(metap.read_text(encoding="utf-8")), True
        except Exception: return None
    return None


def write_cache(cache_dir: Path, url: str, raw: bytes, meta: dict) -> None:
    rawp, metap = cache_path(cache_dir, url), meta_path(cache_dir, url)
    rawp.parent.mkdir(parents=True, exist_ok=True)
    rawp.write_bytes(raw)
    metap.write_text(json.dumps(meta, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")


@dataclass
class HostRate:
    last: float = 0.0


class Fetcher:
    def __init__(self, cache_dir: Path, timeout: int, attempts: int, rate: float, refresh: bool):
        self.cache_dir = cache_dir; self.timeout = timeout; self.attempts = attempts
        self.interval = 1.0 / max(rate, 0.1); self.refresh = refresh
        self.lock = Lock(); self.hosts: dict[str, HostRate] = {}
    def _pace(self, host: str) -> None:
        with self.lock:
            state = self.hosts.setdefault(host, HostRate())
            delay = self.interval - (time.monotonic() - state.last)
            if delay > 0: time.sleep(delay)
            state.last = time.monotonic()
    def get(self, url: str) -> tuple[bytes, dict, bool]:
        if not self.refresh:
            cached = read_cache(self.cache_dir, url)
            if cached: return cached
        host = urllib.parse.urlsplit(url).hostname or ""
        last = None
        for attempt in range(1, self.attempts + 1):
            try:
                self._pace(host)
                req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,application/xml,application/pdf,text/plain;q=0.9,*/*;q=0.5"})
                with urllib.request.urlopen(req, timeout=self.timeout) as response:
                    raw = response.read(15 * 1024 * 1024 + 1)
                    if len(raw) > 15 * 1024 * 1024:
                        raise RuntimeError("document exceeds 15 MiB harvest safety limit")
                    final = normalized_url(response.geturl()) or url
                    ctype = str(response.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
                    meta = {"url": url, "final_url": final, "status": int(getattr(response, "status", 200)), "content_type": ctype, "fetched_at_utc": now_iso(), "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
                write_cache(self.cache_dir, url, raw, meta)
                return raw, meta, False
            except Exception as exc:
                last = exc
                if attempt < self.attempts: time.sleep(min(2.0, 0.25 * attempt))
        raise RuntimeError(f"fetch failed {url}: {last}")


def decode_text(raw: bytes) -> str:
    for enc in ("utf-8", "utf-8-sig", "windows-1256", "iso-8859-7", "windows-1253"):
        try: return raw.decode(enc)
        except UnicodeDecodeError: pass
    return raw.decode("utf-8", errors="replace")


def sitemap_urls(raw: bytes) -> tuple[list[str], list[str]]:
    try: root = ET.fromstring(raw)
    except ET.ParseError: return [], []
    locs = [((el.text or "").strip()) for el in root.iter() if str(el.tag).lower().endswith("loc") and (el.text or "").strip()]
    if str(root.tag).lower().endswith("sitemapindex"):
        return [], locs
    return locs, []


def classify(text: str, url: str, keyword_map: dict[str, list[str]]) -> list[str]:
    hay = (url + "\n" + text[:250000]).casefold()
    cats = []
    for cat, words in keyword_map.items():
        if any(str(word).casefold() in hay for word in words): cats.append(cat)
    return cats or ["other"]


def excerpt(text: str, limit: int = 1200) -> str:
    value = re.sub(r"\s+", " ", text).strip()
    return value[:limit]


def candidate_seed_urls(root_url: str) -> list[str]:
    base = root_url.rstrip("/")
    origin = urllib.parse.urlunsplit((*urllib.parse.urlsplit(base)[:2], "", "", ""))
    return [
        root_url,
        origin + "/sitemap.xml", origin + "/sitemap_index.xml", origin + "/wp-sitemap.xml",
    ]


LOW_VALUE_PATH_TOKENS = {
    "/tag/", "/tags/", "/author/", "/feed/", "/comments/", "/comment-page-",
    "/wp-json/", "/wp-admin/", "/wp-login", "/xmlrpc.php", "/trackback/",
    "/attachment/", "/amp/", "/page/",
}
LOW_VALUE_QUERY_KEYS = {"s", "search", "q", "replytocom", "share", "output"}
BINARY_ASSET_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico", ".css", ".js",
    ".woff", ".woff2", ".ttf", ".eot", ".mp4", ".m4v", ".webm", ".mp3", ".wav",
    ".zip", ".rar", ".7z", ".apk", ".aab",
}
# URL-only hints. Arabic/Greek slugs are decoded before matching.  This list is
# intentionally broader than the canonical text classifier because it is used
# only to decide which sitemap entries deserve an HTTP fetch during CI.
URL_RELEVANCE_HINTS = (
    # Arabic
    "صلاة", "صلوات", "تذكار", "سنكسار", "قديس", "قدّيس", "تقويم", "رزنامة",
    "صوم", "صيام", "رسالة", "إنجيل", "انجيل", "قراءات", "قداس", "ليتورج",
    "سحر", "غروب", "نوم", "خدمة", "كنيسة", "كنائس", "دير", "أديرة", "بث",
    "إذاعة", "راديو", "مكتبة", "كتاب", "تحميل",
    # English
    "prayer", "commemoration", "synax", "saint", "calendar", "fast", "epistle",
    "gospel", "reading", "liturgy", "service", "matins", "orthros", "vesper",
    "compline", "church", "parish", "monastery", "live", "radio", "library",
    "book", "download",
    # Greek (stems)
    "προσευχ", "συναξ", "ἁγ", "αγ", "ημερολόγ", "εορτολόγ", "νηστε", "ἀπόστολ",
    "εὐαγγέλ", "λειτουργ", "ὄρθρ", "ορθρ", "ἑσπεριν", "εσπεριν", "μονή", "εκκλησ",
)


def is_relevant_candidate_url(url: str, root_urls: Iterable[str] = ()) -> bool:
    """Return whether a discovered URL is worth fetching during the CI harvest.

    Sitemaps may expose tens of thousands of archive, tag, media and pagination
    URLs.  R64 only needs ecclesiastical source material, so CI indexes the full
    sitemap but downloads only likely liturgical/source pages.  Root/language
    landing pages and PDFs are always retained.
    """
    n = normalized_url(url)
    if not n:
        return False
    p = urllib.parse.urlsplit(n)
    decoded_path = urllib.parse.unquote(p.path or "/").casefold()
    decoded_query = urllib.parse.unquote_plus(p.query or "").casefold()
    if any(decoded_path.endswith(ext) for ext in BINARY_ASSET_EXTENSIONS):
        return False
    if decoded_path.endswith(".pdf"):
        return True
    if any(token in decoded_path for token in LOW_VALUE_PATH_TOKENS):
        return False
    query_keys = {k.casefold() for k, _ in urllib.parse.parse_qsl(p.query, keep_blank_values=True)}
    if query_keys & LOW_VALUE_QUERY_KEYS:
        return False
    root_norm = {normalized_url(x).rstrip("/") + "/" for x in root_urls if normalized_url(x)}
    if n.rstrip("/") + "/" in root_norm:
        return True
    hay = decoded_path + "?" + decoded_query
    return any(hint.casefold() in hay for hint in URL_RELEVANCE_HINTS)


def _queue_candidate(queue, url: str, root_id: str, depth: int, *, roots: list[dict], sitemap_stats: Counter | None = None) -> bool:
    root_urls = [r["url"] for r in roots]
    if is_relevant_candidate_url(url, root_urls):
        queue.append((url, root_id, depth))
        if sitemap_stats is not None:
            sitemap_stats["accepted"] += 1
        return True
    if sitemap_stats is not None:
        sitemap_stats["filtered"] += 1
    return False

def harvest(args) -> dict:
    cfg = json.loads(NETWORK.read_text(encoding="utf-8"))
    suffixes = cfg["allowed_domain_suffixes"]
    keyword_map = cfg["relevance_keywords"]
    roots = cfg["roots"]
    direct_documents = cfg.get("direct_documents") or []
    fetcher = Fetcher(args.cache_dir, args.timeout, args.attempts, args.rate, args.refresh)

    discovered: set[str] = set()
    sitemap_queue = deque()
    page_queue = deque()
    root_ids: dict[str, set[str]] = {}
    for root in roots:
        for seed in candidate_seed_urls(root["url"]):
            u = normalized_url(seed)
            if not u: continue
            if "sitemap" in urllib.parse.urlsplit(u).path: sitemap_queue.append((u, root["id"]))
            else: page_queue.append((u, root["id"], 0))
        root_ids.setdefault(root["id"], set()).add(normalized_url(root["url"]))

    # Some official annual calendars are linked from historical pages but are
    # not present in a sitemap. Seed them explicitly and preserve their
    # authority/language metadata in the harvest record. They are evidence
    # documents only until native-language and parser verification is complete.
    direct_by_url = {}
    for direct in direct_documents:
        u = normalized_url(str(direct.get("url") or ""))
        host = urllib.parse.urlsplit(u).hostname if u else ""
        if not u or not host_allowed(host or "", suffixes):
            raise RuntimeError(f"direct document outside official network: {direct.get('url')}")
        direct_by_url[u] = dict(direct)
        page_queue.append((u, f"direct:{direct.get('id') or 'document'}", 0))

    sitemap_seen = set(); sitemap_failures = []; sitemap_stats = Counter()
    # Sitemap discovery is sequential and small; nested sitemap indexes are followed.
    while sitemap_queue and len(sitemap_seen) < 200:
        u, rid = sitemap_queue.popleft()
        if u in sitemap_seen: continue
        sitemap_seen.add(u)
        try:
            raw, meta, _ = fetcher.get(u)
            pages, nested = sitemap_urls(raw)
            for link in pages:
                n = normalized_url(link)
                host = urllib.parse.urlsplit(n).hostname if n else ""
                if n and host_allowed(host or "", suffixes):
                    sitemap_stats["discovered"] += 1
                    _queue_candidate(page_queue, n, rid, 1, roots=roots, sitemap_stats=sitemap_stats)
            for link in nested:
                n = normalized_url(link)
                host = urllib.parse.urlsplit(n).hostname if n else ""
                if n and host_allowed(host or "", suffixes): sitemap_queue.append((n, rid))
        except Exception as exc:
            sitemap_failures.append({"url": u, "root_id": rid, "error": str(exc)[:400]})

    # Deduplicate seeds while preserving best/lowest depth and all discovery roots.
    pending: dict[str, dict] = {}
    while page_queue:
        u, rid, depth = page_queue.popleft()
        if not u or u in discovered: continue
        item = pending.setdefault(u, {"depth": depth, "roots": set()})
        item["depth"] = min(item["depth"], depth); item["roots"].add(rid)
    ordered = deque(sorted(pending.items(), key=lambda kv: (kv[1]["depth"], kv[0])))

    records = []; failures = []; external = {}; queued = set(pending)
    workers = max(1, args.workers)
    while ordered and len(records) < args.max_pages:
        batch = []
        while ordered and len(batch) < workers * 3 and len(records) + len(batch) < args.max_pages:
            u, info = ordered.popleft()
            if u in discovered: continue
            discovered.add(u); batch.append((u, info))
        if not batch: continue
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(fetcher.get, u): (u, info) for u, info in batch}
            for fut in concurrent.futures.as_completed(futures):
                u, info = futures[fut]
                try:
                    raw, meta, cache_hit = fut.result()
                    final = normalized_url(meta.get("final_url") or u) or u
                    final_host = urllib.parse.urlsplit(final).hostname or ""
                    if not host_allowed(final_host, suffixes):
                        failures.append({"url": u, "error": "redirected outside official network", "final_url": final})
                        continue
                    ctype = str(meta.get("content_type") or "").lower()
                    title = ""; text = ""; links = []
                    if ctype in TEXT_CONTENT_TYPES or (not ctype and raw.lstrip().startswith(b"<")):
                        decoded = decode_text(raw)
                        parser = LinkTextParser(); parser.feed(decoded)
                        title = parser.title.strip(); text = parser.text; links = parser.links
                    elif ctype in PDF_CONTENT_TYPES or final.lower().endswith(".pdf"):
                        title = Path(urllib.parse.urlsplit(final).path).name
                    else:
                        title = Path(urllib.parse.urlsplit(final).path).name
                    categories = classify(text, final, keyword_map)
                    direct_meta = direct_by_url.get(u) or direct_by_url.get(final)
                    if direct_meta:
                        categories = sorted(set(categories).union({"calendar"}))
                    record = {
                        "url": final, "requested_url": u, "root_ids": sorted(info["roots"]), "depth": info["depth"],
                        "title": title, "content_type": ctype, "sha256": meta.get("sha256"), "bytes": meta.get("bytes"),
                        "cache_hit": bool(cache_hit), "categories": categories, "excerpt": excerpt(text),
                    }
                    if direct_meta:
                        record["source_document_id"] = direct_meta.get("id")
                        record["source_language"] = direct_meta.get("language")
                        record["source_authority"] = direct_meta.get("authority")
                        record["coverage_note"] = direct_meta.get("coverage")
                        record["promotion_note"] = direct_meta.get("promotion")
                    records.append(record)
                    # Recursive same-network discovery from public HTML.
                    if info["depth"] < args.max_depth:
                        for href in links:
                            joined = normalized_url(urllib.parse.urljoin(final, href))
                            if not joined: continue
                            host = urllib.parse.urlsplit(joined).hostname or ""
                            if host_allowed(host, suffixes):
                                root_urls = [r["url"] for r in roots]
                                if (joined not in discovered and joined not in queued
                                        and is_relevant_candidate_url(joined, root_urls)):
                                    queued.add(joined)
                                    ordered.append((joined, {"depth": info["depth"] + 1, "roots": set(info["roots"])}))
                            elif host in SOCIAL_HOSTS:
                                ext = external.setdefault(joined, {"url": joined, "discovered_from": set()})
                                ext["discovered_from"].add(final)
                except Exception as exc:
                    failures.append({"url": u, "root_ids": sorted(info["roots"]), "error": str(exc)[:500]})
        print(f"R64_OFFICIAL_HARVEST_PROGRESS pages={len(records)} queued={len(ordered)} failures={len(failures)}", flush=True)

    category_counts = Counter(cat for rec in records for cat in rec["categories"])
    host_counts = Counter(urllib.parse.urlsplit(rec["url"]).hostname or "" for rec in records)
    output = {
        "schema_version": 1,
        "generated_at_utc": now_iso(),
        "network_config_sha256": hashlib.sha256(NETWORK.read_bytes()).hexdigest(),
        "jurisdiction": cfg["jurisdiction"],
        "public_only": True,
        "scope": {
            "roots": roots,
            "allowed_domain_suffixes": suffixes,
            "max_pages": args.max_pages,
            "max_depth": args.max_depth,
            "sitemaps_seen": len(sitemap_seen),
            "sitemap_urls_discovered": int(sitemap_stats["discovered"]),
            "sitemap_urls_accepted": int(sitemap_stats["accepted"]),
            "sitemap_urls_filtered": int(sitemap_stats["filtered"]),
        },
        "coverage": {
            "documents": len(records),
            "failures": len(failures),
            "hosts": dict(sorted(host_counts.items())),
            "categories": dict(sorted(category_counts.items())),
            "external_social_links": len(external),
        },
        "documents": sorted(records, key=lambda r: r["url"]),
        "external_social_links": [
            {"url": v["url"], "discovered_from": sorted(v["discovered_from"])} for _, v in sorted(external.items())
        ],
        "sitemap_failures": sitemap_failures,
        "failures": failures,
    }
    return output


def main() -> None:
    cfg = json.loads(NETWORK.read_text(encoding="utf-8"))
    policy = cfg["crawl_policy"]
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    ap.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    ap.add_argument("--workers", type=int, default=int(policy["default_workers"]))
    ap.add_argument("--timeout", type=int, default=int(policy["default_timeout_seconds"]))
    ap.add_argument("--attempts", type=int, default=int(policy["default_attempts"]))
    ap.add_argument("--rate", type=float, default=float(policy["rate_limit_requests_per_host_per_second"]))
    ap.add_argument("--max-pages", type=int, default=int(policy["default_max_pages"]))
    ap.add_argument("--max-depth", type=int, default=int(policy.get("default_max_depth", 2)))
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()
    payload = harvest(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    c = payload["coverage"]
    print("R64_OFFICIAL_HARVEST_OK " + " ".join([
        f"documents={c['documents']}", f"hosts={len(c['hosts'])}", f"categories={len(c['categories'])}",
        f"failures={c['failures']}", f"external_social_links={c['external_social_links']}"
    ]))

if __name__ == "__main__":
    main()
