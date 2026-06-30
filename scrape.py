"""Bright Data LinkedIn scraper — total function, never raises.

    from scrape import scrape_linkedin
    data = scrape_linkedin("https://www.linkedin.com/in/some-handle")

Success -> {"name", "title", "company", "interests": [...]}
Failure -> None   (bad URL / no key / timeout / blocked / unparseable)

Env: BRIGHTDATA_API_KEY (required for live), BRIGHTDATA_ZONE (default web_unlocker1)
"""
from __future__ import annotations

import html as _htmllib
import json
import os
import re
import time
from pathlib import Path
from typing import Optional

import requests

# LinkedIn via Web Unlocker is slow (often 8-30s). Give it room; the cache below
# makes pre-warmed profiles instant on stage so this timeout rarely bites live.
_TIMEOUT = 25.0
_ENDPOINT = "https://api.brightdata.com/request"
_PROFILE_RE = re.compile(r"linkedin\.com/in/[^/?#\s]+", re.IGNORECASE)

# Persistent cache: scrape a profile once (e.g. pre-demo) -> instant next time.
_CACHE_FILE = Path(__file__).parent / "scrape_cache.json"


def scrape_linkedin(url: str, use_cache: bool = True) -> Optional[dict]:
    try:
        if not (isinstance(url, str) and _PROFILE_RE.search(url)):
            return None

        handle = _handle(url)
        if use_cache:
            cached = _cache_get(handle)
            if cached:
                return cached

        api_key = os.environ.get("BRIGHTDATA_API_KEY")
        if not api_key:
            return None
        zone = os.environ.get("BRIGHTDATA_ZONE", "sdk_unlocker")
        html = _fetch(url, api_key, zone)
        if not html:
            return None
        data = _parse(html)
        if data:
            _cache_put(handle, data)
        return data
    except Exception:
        return None


def _handle(url: str) -> str:
    m = re.search(r"/in/([^/?#]+)", url)
    return (m.group(1) if m else url).lower()


def _cache_get(handle: str) -> Optional[dict]:
    try:
        if _CACHE_FILE.exists():
            return json.loads(_CACHE_FILE.read_text()).get(handle)
    except Exception:
        pass
    return None


def _cache_put(handle: str, data: dict) -> None:
    try:
        cache = {}
        if _CACHE_FILE.exists():
            cache = json.loads(_CACHE_FILE.read_text())
        cache[handle] = data
        _CACHE_FILE.write_text(json.dumps(cache, indent=2))
    except Exception:
        pass


def _fetch(url: str, api_key: str, zone: str) -> Optional[str]:
    try:
        resp = requests.post(
            _ENDPOINT,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"zone": zone, "url": url, "format": "raw"},
            timeout=_TIMEOUT,
        )
    except Exception:
        return None
    if resp.status_code != 200:
        return None
    text = resp.text or ""
    return text if text.strip() else None


def _parse(html: str) -> Optional[dict]:
    name = title = company = None
    interests: list[str] = []

    person = _person_jsonld(html)
    if person:
        name = _clean(person.get("name"))
        title = _clean(_first(person.get("jobTitle")))
        company = _clean(_org(person.get("worksFor")))
        interests = _strlist(person.get("knowsAbout"))

    if not (name and title and company):
        n, t, c = _meta_title(html)
        name, title, company = name or n, title or t, company or c
    if not interests:
        interests = _interests_from_desc(html)
    if not name:
        return None
    return {"name": name, "title": title or "", "company": company or "", "interests": interests}


def _person_jsonld(html: str) -> Optional[dict]:
    for block in re.findall(
        r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', html, re.DOTALL | re.IGNORECASE
    ):
        try:
            data = json.loads(block.strip())
        except Exception:
            continue
        found = _find_person(data)
        if found:
            return found
    return None


def _find_person(data):
    if isinstance(data, dict):
        t = data.get("@type")
        if "Person" in (t if isinstance(t, list) else [t]):
            return data
        for v in data.values():
            f = _find_person(v)
            if f:
                return f
    elif isinstance(data, list):
        for it in data:
            f = _find_person(it)
            if f:
                return f
    return None


def _meta_title(html: str):
    tag = _meta(html, "og:title") or _title(html)
    if not tag:
        return None, None, None
    cleaned = re.sub(r"\s*\|\s*LinkedIn\s*$", "", tag).strip()
    parts = [p.strip() for p in re.split(r"\s+[-–—]\s+", cleaned) if p.strip()]
    return (parts[0] if parts else None,
            parts[1] if len(parts) > 1 else None,
            parts[2] if len(parts) > 2 else None)


def _interests_from_desc(html: str) -> list[str]:
    desc = _meta(html, "og:description") or ""
    out = []
    for chunk in re.split(r"[•·|]|\s[-–—]\s", desc):
        p = chunk.strip(" .,")
        if 3 <= len(p) <= 40 and p.lower() != "linkedin":
            out.append(p)
        if len(out) >= 3:
            break
    return out[:3]


def _meta(html: str, prop: str) -> Optional[str]:
    for pat in (
        rf'<meta[^>]+property=["\']{re.escape(prop)}["\'][^>]+content=["\'](.*?)["\']',
        rf'<meta[^>]+content=["\'](.*?)["\'][^>]+property=["\']{re.escape(prop)}["\']',
    ):
        m = re.search(pat, html, re.IGNORECASE | re.DOTALL)
        if m:
            return _clean(m.group(1))
    return None


def _title(html: str) -> Optional[str]:
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    return _clean(m.group(1)) if m else None


def _first(v):
    return (v[0] if v else None) if isinstance(v, list) else v


def _org(works_for):
    o = _first(works_for)
    if isinstance(o, dict):
        return o.get("name")
    return o if isinstance(o, str) else None


def _strlist(v) -> list[str]:
    if isinstance(v, str):
        v = [v]
    if not isinstance(v, list):
        return []
    return [s for s in (_clean(x) for x in v if isinstance(x, str)) if s][:5]


def _clean(v) -> Optional[str]:
    if not isinstance(v, str):
        return None
    s = _htmllib.unescape(re.sub(r"\s+", " ", v).strip())
    return s or None


if __name__ == "__main__":
    import sys
    target = sys.argv[1] if len(sys.argv) > 1 else "https://www.linkedin.com/in/williamhgates"
    print(json.dumps(scrape_linkedin(target), indent=2))
