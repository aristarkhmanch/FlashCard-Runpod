# FlashCard ⚡ (solo build)

Drop your LinkedIn → get a personalized **hero trading card** (with your own LinkedIn QR baked in)
in seconds. Image generated on **RunPod GPUs**, context pulled with **Bright Data**. The host walks
away with a database of **warm leads**.

Single Python process serves both the frontend and the API. Runs on localhost, no GPU needed locally.

## Run (60 seconds)

```bash
cd flashcard-solo
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # optional — it runs WITHOUT keys in mock mode
uvicorn app:app --reload --port 8787
```
Open <http://localhost:8787>. Leads dashboard: <http://localhost:8787/leads>.

## Keys (optional, upgrades mock → real)

Put these in `.env`:
- `RUNPOD_API_KEY` — turns on real GPU image generation (RunPod public Flux-schnell endpoint).
- `BRIGHTDATA_API_KEY` (+ `BRIGHTDATA_ZONE`) — turns on real LinkedIn scraping.

Without keys: the app still works end-to-end — placeholder art + real QR + real captions + lead
capture — so you can build/test the UI immediately. Check `/health` to see what's live.

## How it works

```
POST /generate-card {email, linkedin_url, event}
  → Bright Data scrape (scrape.py)         → name/title/company/interests
  → captions.py                            → tweet (<=230) + LinkedIn post  [template, LLM-upgradable]
  → RunPod GPU image (cardgen.py)          → trading-card art (text-free)
  → Pillow composite + LinkedIn QR         → final PNG
  → lead saved to leads.jsonl              → shown live at /leads
  ← {image_url(dataURI), name, tweet, linkedin_post, ...}
```

## Flip to RunPod Flash (for the "best use of Flash" prize)

Default image backend is the reliable RunPod **public** endpoint. To run the image step through a
Flash `@Endpoint` instead (see `flash_image.py`):

```bash
pip install runpod-flash && flash login
flash dev --auto-provision          # pre-warm so there's no cold start on stage
# set IMAGE_BACKEND=flash in .env, then restart uvicorn
```

## Demo-safety

- Pre-run one card so the model/endpoint is warm.
- Keep `/leads` open in a tab — rows appear live as people generate.
- Keep one saved card PNG as a fallback if generation stalls.
- The loading checklist intentionally tells the technical story (Bright Data → RunPod GPU → QR).
