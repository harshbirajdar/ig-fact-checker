# Fact Check for Instagram

One-gesture fact-checker for Instagram reels and posts. Triggered from iOS's native share sheet; renders a verdict card in ~10 seconds. Personal-scale, single user (me).

## How it works

```
Instagram reel/post
  │
  ▼  [paper-plane → Share to → "Fact Check" iOS Shortcut]
  │
  ▼  POST url to backend /check
  │
Backend (Cloud Run · Python/FastAPI):
  1. Resolve metadata via `instaloader` (anonymous, no cookies) — handles images, reels, and carousels uniformly
  2. Download media:
     - Image post → the single image URL
     - Reel → the MP4 + ffmpeg → 5 frames @ 1 fps + 60-sec audio clip
     - Carousel → up to first 5 item images (videos inside carousels use their thumbnail)
  3. Reels only: Groq Whisper → audio transcript (non-fatal if it fails)
  4. Claude Sonnet (vision + web_search tool): returns the JSON verdict
  5. Firestore cache write (keyed on shortcode, 7-day TTL)
  6. Render Jinja2 template → HTML
  │
  ▼  HTML response
  │
iPhone shows the verdict card → tap Done → back to Instagram.
```

Full details: see [PRD.md](PRD.md).

## Verdict taxonomy (5 buckets, no neutral middle)

| Verdict | Meaning | Color |
|---|---|---|
| `FALSE` | Core claim wrong; sources contradict | red |
| `MOSTLY FALSE` | Core claim wrong, some surrounding facts real | red-orange |
| `MOSTLY ACCURATE` | Core claim right but materially off in detail | lime |
| `ACCURATE` | Core claim correct | green |
| `CAN'T VERIFY` | No testable claim, or no authoritative sources | gray |

The prompt explicitly forbids using `MOSTLY *` as a hedge (see PRD §5.5).

## Supported content

- Image posts
- Reels (videos)
- Carousels (multi-image, first 5 items processed)

Out of scope: Stories, IGTV, private accounts, DM-shared content. See PRD §3.

## Stack

| Layer | Choice |
|---|---|
| Trigger | iOS Shortcut (Share Sheet) |
| UI | HTML rendered by backend; opened in Instagram's in-app browser or Quick Look |
| Backend | Python + FastAPI |
| Host | Google Cloud Run (service name: `fact-check`, region: `us-central1`) |
| CI/CD | Cloud Build trigger `fact-check-deploy-main` (push to `main` → build → deploy) |
| Cache | Firestore (`fact_check_cache` collection) |
| Jobs | Firestore (`fact_check_jobs` collection, for async processing polling) |
| IG fetch | `instaloader` Python library — anonymous, no cookies |
| LLM | Claude Sonnet 4.6 with `web_search` tool |
| ASR | Groq `whisper-large-v3-turbo` (non-fatal if it fails) |
| Media | ffmpeg (bundled into Docker image) |

## Repo tour

```
backend/
  main.py          # FastAPI app: routes, verdict→tone mapping, preview endpoints
  pipeline.py      # IG fetch, ffmpeg, Whisper, Claude call, JSON validation
  cache.py         # Firestore verdict cache (fail-open)
  jobs.py          # Firestore async-job state
  templates/
    verdict.html   # Single Jinja2 template: processing/verdict/error screens
  Dockerfile       # Python 3.12 + ffmpeg
  requirements.txt
  .env.example     # Template for required env vars (copy to .env locally)

design_handoff_fact_check/   # Original design canvas (3 directions, all states)
PRD.md                       # Spec — source of truth
README.md                    # This file
demo.html / designs.html / prototype.html  # Misc prototypes from early iteration
```

## Env vars required

Create `backend/.env` (never committed) with:

```
ANTHROPIC_API_KEY=sk-ant-...
GROQ_API_KEY=gsk_...
GOOGLE_CLOUD_PROJECT=<your-gcp-project-id>   # enables Firestore cache
```

## Running locally

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8765
```

Design-iteration endpoints (no IG hit, no Claude call, pure fixtures):

```
http://127.0.0.1:8765/preview/processing_reel
http://127.0.0.1:8765/preview/false
http://127.0.0.1:8765/preview/mostly_false
http://127.0.0.1:8765/preview/mostly_accurate
http://127.0.0.1:8765/preview/accurate
http://127.0.0.1:8765/preview/unverifiable
http://127.0.0.1:8765/preview/error_private
```

## Shipping a change

```bash
cd backend
gcloud run deploy fact-check \
  --source . \
  --region us-central1 \
  --allow-unauthenticated
```

Takes ~2–3 min. Env vars already set on Cloud Run; `--source .` doesn't touch them.

## Workflow

```bash
git add .
git commit -m "describe the change"
git push
```

Pushes to `main` auto-deploy to Cloud Run via the `fact-check-deploy-main` Cloud Build trigger (config: [cloudbuild.yaml](cloudbuild.yaml)). Manual deploy (above) is only needed if CI/CD is down.
