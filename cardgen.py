"""Image generation + card compositing.

- generate_art(prompt)      -> PNG bytes   (RunPod GPU / Flash / mock)
- make_qr(url)              -> PIL.Image | None   (LinkedIn QR)
- build_prompt(copy, ...)   -> str
- build_card(art, name, role, qr) -> PNG bytes (art + name band + QR + foil frame)
"""
from __future__ import annotations

import base64
import io
import math
import os

import requests
from PIL import Image, ImageDraw, ImageFont

RUNPOD_FLUX_URL = "https://api.runpod.ai/v2/black-forest-labs-flux-1-schnell/runsync"

NEGATIVE = (
    "text, words, letters, typography, watermark, logo, signature, blurry, lowres, "
    "deformed hands, extra fingers, jpeg artifacts, nsfw"
)


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------
def build_prompt(copy: dict, profile: dict, event: str) -> str:
    subject = copy.get("image_subject", "a heroic tech builder")
    interest = (profile.get("interests") or ["building with AI"])[0]
    return (
        f"Epic collectible trading-card character portrait. The hero is {subject}, "
        f"powers themed around {interest}. Set at a futuristic tech summit ({event}). "
        f"Dynamic heroic pose, glowing neon-purple and magenta energy, holographic "
        f"GPU and circuit motifs, confetti sparks, cinematic rim lighting, premium foil "
        f"trading-card aesthetic, ornate border. Vibrant polished digital illustration, "
        f"trading-card game art, ultra detailed."
    )


# ---------------------------------------------------------------------------
# Image backends
# ---------------------------------------------------------------------------
def generate_art(prompt: str) -> bytes:
    backend = os.environ.get("IMAGE_BACKEND", "runpod_public")
    if not os.environ.get("RUNPOD_API_KEY") and backend != "flash":
        backend = "mock"
    try:
        if backend == "runpod_public":
            return _runpod_flux(prompt)
        if backend == "flash":
            from flash_image import generate_image_flash  # lazy import
            return generate_image_flash(prompt)
    except Exception as e:  # never let the demo die — fall back to mock art
        print(f"[cardgen] image backend '{backend}' failed: {e!r} -> mock")
    return _mock_art(prompt)


def _runpod_flux(prompt: str) -> bytes:
    key = os.environ["RUNPOD_API_KEY"]
    resp = requests.post(
        RUNPOD_FLUX_URL,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"input": {"prompt": prompt, "width": 1024, "height": 1024, "num_inference_steps": 4}},
        timeout=120,
    )
    resp.raise_for_status()
    return _extract_image(resp.json())


def _extract_image(data) -> bytes:
    """Pull image bytes out of a RunPod response (url or base64), shape-tolerant."""
    out = data.get("output", data) if isinstance(data, dict) else data
    candidates = []
    if isinstance(out, dict):
        for k in ("result", "image_url", "image", "url", "image_base64", "base64"):
            if out.get(k):
                candidates.append(out[k])
        if isinstance(out.get("images"), list) and out["images"]:
            candidates.append(out["images"][0])
    elif isinstance(out, list) and out:
        candidates.append(out[0])
    elif isinstance(out, str):
        candidates.append(out)
    for c in candidates:
        if isinstance(c, dict):
            c = c.get("image") or c.get("url") or c.get("image_url")
        if not isinstance(c, str):
            continue
        if c.startswith("http"):
            r = requests.get(c, timeout=60)
            r.raise_for_status()
            return r.content
        b64 = c.split(",", 1)[1] if c.startswith("data:") else c
        return base64.b64decode(b64)
    raise ValueError(f"no image in RunPod response: {str(data)[:200]}")


def _mock_art(seed_text: str) -> bytes:
    """Deterministic gradient placeholder so the UI works with no API keys."""
    W = H = 1024
    img = Image.new("RGB", (W, H))
    px = img.load()
    base = sum(ord(c) for c in seed_text) % 60
    for y in range(H):
        for x in range(0, W, 4):  # step 4 for speed
            r = 26 + int(60 * (x / W)) + base
            g = 11 + int(20 * (y / H))
            b = 48 + int(120 * (y / H))
            col = (min(r, 255), min(g, 255), min(b, 255))
            for dx in range(4):
                if x + dx < W:
                    px[x + dx, y] = col
    d = ImageDraw.Draw(img)
    cx, cy = W // 2, int(H * 0.4)
    for rad in range(180, 40, -14):
        a = int(120 * (rad / 180))
        d.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], outline=(230, 53, 200), width=2)
    d.text((cx - 90, cy - 20), "MOCK ART", font=_font(40), fill=(240, 220, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# QR
# ---------------------------------------------------------------------------
def make_qr(url: str | None):
    if not url:
        return None
    try:
        import qrcode
        from qrcode.constants import ERROR_CORRECT_H
        qr = qrcode.QRCode(error_correction=ERROR_CORRECT_H, box_size=10, border=2)
        qr.add_data(url)
        qr.make(fit=True)
        return qr.make_image(fill_color="black", back_color="white").convert("RGB")
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Compositing
# ---------------------------------------------------------------------------
def build_card(art_bytes: bytes, name: str, role: str, qr_img) -> bytes:
    art = Image.open(io.BytesIO(art_bytes)).convert("RGB").resize((1024, 1024))
    W, H = 1024, 1300
    canvas = Image.new("RGB", (W, H), (13, 7, 23))
    canvas.paste(art, (0, 0))
    d = ImageDraw.Draw(canvas)

    # text must stop before the QR (if present) so long names don't collide with it
    text_right = (W - 236 - 16) if qr_img is not None else (W - 44)
    max_w = text_right - 44

    # name band text — auto-shrink so long names fit the available width
    name_font = _fit_font(d, name or "Hero", max_w, start=66, min_size=34)
    d.text((44, 1040), name or "Hero", font=name_font, fill=(255, 255, 255))
    if role:
        d.text((46, 1124), _truncate(d, role, max_w, _font(34)), font=_font(34), fill=(217, 194, 255))
    d.text((46, 1238), "Forged on RunPod Flash  -  Bright Data", font=_font(24), fill=(176, 146, 216))

    # LinkedIn QR, bottom-right, white quiet zone
    if qr_img is not None:
        qr = qr_img.resize((196, 196))
        pad = Image.new("RGB", (216, 216), (255, 255, 255))
        pad.paste(qr, (10, 10))
        canvas.paste(pad, (W - 236, 1044))
        d.text((W - 232, 1262), "scan to connect", font=_font(22), fill=(176, 146, 216))

    # foil frame
    d.rounded_rectangle([6, 6, W - 6, H - 6], radius=28, outline=(230, 53, 200), width=5)

    buf = io.BytesIO()
    canvas.save(buf, format="PNG")
    return buf.getvalue()


_FONT_PATHS = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def _font(size: int):
    for p in _FONT_PATHS:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _text_w(draw, text, font) -> float:
    try:
        return draw.textlength(text, font=font)
    except Exception:
        return len(text) * font.size * 0.6


def _fit_font(draw, text, max_w, start=66, min_size=34):
    """Largest font (down to min_size) at which `text` fits within max_w px."""
    size = start
    while size > min_size:
        f = _font(size)
        if _text_w(draw, text, f) <= max_w:
            return f
        size -= 2
    return _font(min_size)


def _truncate(draw, text, max_w, font):
    """Trim with an ellipsis if `text` overflows max_w at the given font."""
    if _text_w(draw, text, font) <= max_w:
        return text
    s = text
    while s and _text_w(draw, s + "…", font) > max_w:
        s = s[:-1]
    return (s + "…") if s else text
