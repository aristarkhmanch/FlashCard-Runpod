"""Caption + creative generation.

Default is a smart template filled from REAL scraped LinkedIn data — instant and
100% reliable for the demo. An optional RunPod LLM upgrade hook is at the bottom.

make_copy(profile, event) -> {
    "card_title": str,      # short hero alias for the card name band
    "image_subject": str,   # 4-8 word visual concept for the image prompt
    "tweet": str,           # <= 230 chars
    "linkedin_post": str,   # multi-line post w/ sponsors + hashtags
}
"""
from __future__ import annotations

import re

TWEET_LIMIT = 230


def _pick_interest(interests: list) -> str:
    """Choose a clean, caption-worthy interest from scraped strings."""
    for raw in interests:
        s = (raw or "").strip()
        # LinkedIn og:description often yields "Experience: X" / "Location: Y" labels.
        if re.match(r"^(location|education)\s*:", s, re.I):
            continue
        s = re.sub(r"^(experience|about|skills?)\s*:\s*", "", s, flags=re.I).strip()
        if 3 <= len(s) <= 48:
            return s
    return "building with AI"


def make_copy(profile: dict, event: str) -> dict:
    name = (profile.get("name") or "").strip() or "there"
    first = name.split()[0] if name != "there" else "there"
    title = (profile.get("title") or "").strip()
    company = (profile.get("company") or "").strip()
    interest = _pick_interest(profile.get("interests") or [])

    role = title or "builder"
    image_subject = f"a legendary hero embodying '{interest}'"
    card_title = (title.split(",")[0][:22] if title else "Hero Builder")

    # ---- tweet (<=230) ----
    tweet = (
        f"I'm at {event} ⚡ turned my LinkedIn into a hero trading card — "
        f"generated on RunPod GPUs with Bright Data. Scan to connect 👇 "
        f"#RunPodFlash #BrightData"
    )
    if len(tweet) > TWEET_LIMIT:
        tweet = (
            f"I'm at {event} ⚡ my LinkedIn is now a hero card, made on RunPod GPUs. "
            f"Scan to connect 👇 #RunPodFlash"
        )
    tweet = tweet[:TWEET_LIMIT]

    # ---- linkedin post ----
    who = role + (f" at {company}" if company else "")
    ident = f"I'm {name}" + (f" — {who}" if who and who != "builder" else "")
    linkedin_post = (
        f"Just forged my personalized hero card at {event} 🦸⚡\n\n"
        f"{ident}. At an event this fun, why network the boring way? "
        f"This card was generated live: a RunPod GPU painted the art in seconds, "
        f"with Bright Data pulling my profile for the vibe.\n\n"
        f"Scan the QR on my card to connect with me 👇\n\n"
        f"Huge thanks to RunPod & Bright Data for hosting. #RunPodFlash #BrightData #AI #GPU"
    )

    return {
        "card_title": card_title,
        "image_subject": image_subject,
        "tweet": tweet,
        "linkedin_post": linkedin_post,
        "_first": first,
    }


# ---------------------------------------------------------------------------
# OPTIONAL upgrade: generate the copy with a RunPod-hosted LLM instead of the
# template. Wire this in only if you have spare time — the template above already
# ships a real, personalized post. Point it at your vLLM serverless endpoint
# (OpenAI-compatible) and parse the JSON it returns.
# ---------------------------------------------------------------------------
# import os, json, requests
# def make_copy_llm(profile, event):
#     prompt = f"""Return STRICT JSON: {{"card_title","image_subject","tweet","linkedin_post"}}.
#     Profile: {json.dumps(profile)}  Event: {event}
#     Rules: tweet <=230 chars, first person, fun, end with @runpodlol @bright_data + 1 hashtag.
#     linkedin_post: 3-6 short lines, thank RunPod Flash & Bright Data, <=5 hashtags,
#     CTA 'scan my card to connect'. Use only facts from the profile."""
#     r = requests.post(os.environ["RUNPOD_LLM_URL"], headers={...}, json={...}, timeout=30)
#     return json.loads(r.json()[...])
