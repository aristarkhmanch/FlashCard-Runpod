"""FlashCard — single-process app: serves the frontend AND the API.

Run:
    pip install -r requirements.txt
    cp .env.example .env          # fill keys (optional — runs in mock mode without)
    uvicorn app:app --reload --port 8787
    open http://localhost:8787
"""
from __future__ import annotations

import base64
import json
import os
import re
import time
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

from captions import make_copy           # noqa: E402
from cardgen import build_card, build_prompt, generate_art, make_qr  # noqa: E402
from scrape import scrape_linkedin       # noqa: E402

HERE = Path(__file__).parent
LEADS = HERE / "leads.jsonl"
EVENT_DEFAULT = os.environ.get("EVENT_DEFAULT", "RunPod Flash Hack Day")

app = FastAPI(title="FlashCard")


class CardReq(BaseModel):
    email: str
    linkedin_url: Optional[str] = None
    event: Optional[str] = None


# ---------------------------------------------------------------------------
# Core endpoint
# ---------------------------------------------------------------------------
@app.post("/generate-card")
def generate_card(req: CardReq):
    t0 = time.time()
    event = _clean_event(req.event)

    profile = scrape_linkedin(req.linkedin_url or "") or _manual_profile(req)
    copy = make_copy(profile, event)
    prompt = build_prompt(copy, profile, event)
    art = generate_art(prompt)
    qr = make_qr(req.linkedin_url)
    png = build_card(art, profile["name"], _role_line(profile), qr)
    _save_lead(req.email, req.linkedin_url, event)

    return {
        "image_url": "data:image/png;base64," + base64.b64encode(png).decode(),
        "name": profile["name"],
        "title": profile.get("title", ""),
        "company": profile.get("company", ""),
        "tweet": copy["tweet"],
        "linkedin_post": copy["linkedin_post"],
        "took_s": round(time.time() - t0, 1),
    }


def _clean_event(raw: Optional[str]) -> str:
    """A pasted URL (e.g. the Luma link) reads terribly inside a post. If the
    event looks like a URL or slug, fall back to a clean human name."""
    e = (raw or "").strip()
    if not e or re.match(r"^https?://", e) or "luma.com" in e or "/" in e:
        return EVENT_DEFAULT
    return e


def _manual_profile(req: CardReq) -> dict:
    """Fallback identity when scraping is unavailable — derive a name."""
    name = None
    if req.linkedin_url:
        m = re.search(r"/in/([^/?#]+)", req.linkedin_url)
        if m:
            name = m.group(1).replace("-", " ").replace("_", " ").title()
            name = re.sub(r"\s*\d+\s*$", "", name).strip()
    if not name and req.email:
        name = req.email.split("@")[0].replace(".", " ").replace("_", " ").title()
    return {"name": name or "Mystery Builder", "title": "", "company": "", "interests": []}


def _role_line(profile: dict) -> str:
    bits = [b for b in (profile.get("title"), profile.get("company")) if b]
    return "  -  ".join(bits)


def _save_lead(email: str, linkedin_url: str | None, event: str) -> None:
    try:
        row = {"email": email, "linkedin_url": linkedin_url, "event": event,
               "ts": time.strftime("%Y-%m-%d %H:%M:%S")}
        with LEADS.open("a") as f:
            f.write(json.dumps(row) + "\n")
    except Exception as e:
        print(f"[app] lead save failed: {e!r}")  # never block the demo


# ---------------------------------------------------------------------------
# Warm-leads dashboard (show this on stage)
# ---------------------------------------------------------------------------
@app.get("/leads")
def leads(format: str = "html"):
    rows = []
    if LEADS.exists():
        for line in LEADS.read_text().splitlines():
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    rows.reverse()
    if format == "json":
        return JSONResponse(rows)
    cells = "".join(
        f"<tr><td>{r.get('ts','')}</td><td>{r.get('email','')}</td>"
        f"<td>{r.get('linkedin_url') or ''}</td><td>{r.get('event','')}</td></tr>"
        for r in rows
    )
    html = f"""<!doctype html><meta charset=utf-8><title>Warm leads</title>
<style>body{{font:15px/1.5 -apple-system,Inter,sans-serif;background:#0d0717;color:#eee;padding:32px}}
h1{{font-weight:700}}table{{border-collapse:collapse;width:100%;max-width:900px}}
td,th{{text-align:left;padding:10px 14px;border-bottom:1px solid #2a1840}}
th{{color:#c9a6ff}}meta{{}}</style>
<h1>Warm leads &nbsp;<span style="color:#c9a6ff">({len(rows)})</span></h1>
<p style="color:#9a86c0">Auto-refreshes every 4s.</p>
<table><tr><th>Time</th><th>Email</th><th>LinkedIn</th><th>Event</th></tr>{cells}</table>
<script>setTimeout(()=>location.reload(),4000)</script>"""
    return HTMLResponse(html)


@app.get("/health")
def health():
    return {
        "ok": True,
        "image_backend": os.environ.get("IMAGE_BACKEND", "runpod_public"),
        "has_runpod_key": bool(os.environ.get("RUNPOD_API_KEY")),
        "has_brightdata_key": bool(os.environ.get("BRIGHTDATA_API_KEY")),
    }


# Static frontend at "/" (mounted last so /generate-card etc. win)
app.mount("/", StaticFiles(directory=str(HERE / "static"), html=True), name="static")
