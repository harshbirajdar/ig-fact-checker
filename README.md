# Fact Check for Instagram

One-gesture fact-checker for Instagram reels and posts. Triggered from iOS's native share sheet; renders a verdict card in ~10 seconds.

Originally built as a personal tool. Open-sourced so anyone can self-host their own instance — fork the repo, bring your own API keys, deploy to your own Google Cloud project, install the iOS Shortcut, and you're live. Docs below walk through each step.

**Status:** working daily driver for the author. See [PRD.md](PRD.md) for the full spec and [CONTRIBUTING.md](CONTRIBUTING.md) if you'd like to send a PR.

## How it works

```
Instagram reel/post
  │
  ▼  [paper-plane → Share to → "Fact Check" iOS Shortcut]
  │
  ▼  POST url to backend /check
  │
Backend (Cloud Run · Python/FastAPI):
  1. Resolve metadata — hybrid fetcher (both anonymous, no cookies):
     a. Primary: httpx GET to the HTML endpoint (/p/<shortcode>/). Gentle
        rate-limit from datacenter IPs; handles most posts.
     b. Fallback: instaloader via IG's GraphQL endpoint. Tight rate-limit;
        guarded by a circuit breaker. Only used when HTML is a SPA shell.
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
| IG fetch | Hybrid: `httpx` HTML scrape (primary) + `instaloader` GraphQL fallback. Both anonymous, no cookies |
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
designs.html / prototype.html              # Misc prototypes from early iteration
```

## Self-hosting

Setting up your own instance takes about an hour end-to-end. These steps assume basic comfort with a terminal; see "Difficulty" at the bottom for an honest assessment.

### 0. Prerequisites

You'll need accounts on:

- **[Anthropic](https://console.anthropic.com/)** — for Claude API access. Pay-as-you-go; budget ~$0.008 per fact-check.
- **[Groq](https://console.groq.com/)** — for Whisper audio transcription. Free tier is sufficient for personal use.
- **[Google Cloud](https://console.cloud.google.com/)** — for hosting. Cloud Run + Firestore both have generous free tiers; at personal-scale usage the monthly bill should be ~$0.
- **An iPhone** — this is iOS Shortcuts only. No Android path.
- A laptop with [Python 3.12+](https://www.python.org/downloads/), [ffmpeg](https://ffmpeg.org/), and the [gcloud CLI](https://cloud.google.com/sdk/docs/install).

### 1. Clone the repo and install

```bash
git clone https://github.com/harshbirajdar/ig-fact-checker.git
cd ig-fact-checker/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Get your API keys

- **Anthropic:** console.anthropic.com → API Keys → Create Key → copy the `sk-ant-...` string
- **Groq:** console.groq.com → API Keys → Create API Key → copy the `gsk_...` string

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env and fill in:
#   ANTHROPIC_API_KEY=sk-ant-...
#   GROQ_API_KEY=gsk_...
#   GOOGLE_CLOUD_PROJECT=<your-gcp-project-id>  (set in step 4)
```

### 4. Create a GCP project + enable APIs

```bash
gcloud auth login
gcloud projects create fact-check-<yourname> --set-as-default
gcloud services enable run.googleapis.com firestore.googleapis.com cloudbuild.googleapis.com
gcloud firestore databases create --location=us-central1
```

Put the project ID in `.env` as `GOOGLE_CLOUD_PROJECT`.

### 5. Try it locally (optional but sanity-preserving)

```bash
uvicorn main:app --reload --port 8765
```

Design-preview endpoints (zero IG / Claude cost, pure fixtures):

```
http://127.0.0.1:8765/preview/processing_reel
http://127.0.0.1:8765/preview/false
http://127.0.0.1:8765/preview/mostly_false
http://127.0.0.1:8765/preview/mostly_accurate
http://127.0.0.1:8765/preview/accurate
http://127.0.0.1:8765/preview/unverifiable
http://127.0.0.1:8765/preview/error_private
```

### 6. Deploy to Cloud Run

```bash
# Still in backend/
gcloud run deploy fact-check \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars "ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY,GROQ_API_KEY=$GROQ_API_KEY,GOOGLE_CLOUD_PROJECT=$GOOGLE_CLOUD_PROJECT"
```

Takes ~3 min. Output prints a `Service URL:` like `https://fact-check-xxxxxx-uc.a.run.app` — copy it; you'll need it for the Shortcut.

(Optional: set up Cloud Build trigger from GitHub for auto-deploy on push — see `cloudbuild.yaml` in the repo.)

### 7. Build the iOS Shortcut

See [SHORTCUT.md](SHORTCUT.md) for the exact actions and a template iCloud link.

### 8. Test it

Open Instagram → pick any public reel or post → paper-plane icon → Share to… → tap your Shortcut. You should see the processing card, then a verdict in 10–15 seconds.

## Difficulty

Honest assessment:

| Your background | Realistic? |
|---|---|
| Python developer | Easy. ~1 hour. |
| Technical but not a coder (e.g. designer who dabbles in scripts) | Doable. ~2–3 hours, will hit friction on GCP setup and iOS Shortcut. |
| Non-technical | Not really. Consider asking a developer friend to host an instance you can share. |

## Shipping a change (for self-hosters)

```bash
git push    # if CI/CD is wired to your GCP project
```

Or manually:

```bash
cd backend
gcloud run deploy fact-check --source . --region us-central1 --allow-unauthenticated
```

Takes ~2–3 min. Env vars set in step 6 persist.

## Workflow

```bash
git add .
git commit -m "describe the change"
git push
```

Pushes to `main` auto-deploy to Cloud Run via the `fact-check-deploy-main` Cloud Build trigger (config: [cloudbuild.yaml](cloudbuild.yaml)). Manual deploy (above) is only needed if CI/CD is down.

## Security scanning

| Tool | What it checks | Where |
|---|---|---|
| **Dependabot alerts** | Known CVEs in Python deps (`requirements.txt`) and Docker base images | GitHub (Security tab). Enabled at the repo level. |
| **Dependabot security updates** | Auto-opens PRs to fix vulnerable deps | GitHub. Enabled at the repo level. |
| **Dependabot version updates** | Proactive weekly PRs to bump non-vulnerable-but-outdated deps | Config: [.github/dependabot.yml](.github/dependabot.yml) |
| **pip-audit** | On-demand CVE check on `requirements.txt` (same data, runs in CI) | CI: [.github/workflows/security-scan.yml](.github/workflows/security-scan.yml) |
| **Bandit** | Static analysis for insecure Python patterns (hardcoded secrets, injection, weak crypto, etc.) | Same workflow, medium+ severity gate |

Not using CodeQL — it requires GitHub Advanced Security, which isn't available on private repos on free personal plans. The pip-audit + Bandit combo covers the realistic threat surface for a Python-only backend (our stack).

The Security tab on GitHub shows any live alerts. There are zero open alerts at time of writing.

## Lessons learned: talking to Instagram anonymously

We burned about a day of outages and three iterations figuring this out. Notes here so future-me doesn't repeat them.

### 1. Hand-rolled HTML scrape → works, until it doesn't

Original approach: `httpx.get('/p/<shortcode>/')` and parse the embedded `<script type="application/json">` blocks for the media object. Worked reliably for a while, then started returning "could not locate media metadata" for a growing share of posts.

**What changed:** Instagram rolled out SPA-style page loads for many accounts. The initial HTML response became a minimal shell; the real media JSON is fetched client-side via XHR after React hydration. Our scraper can't see data that isn't in the HTML.

**BUT — crucially, not for everyone.** Cloud Run's datacenter IPs appear to be treated as crawlers and still receive the pre-rendered HTML variant with the JSON blocks. Residential IPs (like my laptop) get the SPA shell. This was the key diagnostic we missed on the first pass: local testing ≠ production behavior for this endpoint.

### 2. Instaloader → works, but the GraphQL endpoint is the rate-limit minefield

Second iteration: switch to `instaloader`, which calls IG's GraphQL API (`/graphql/query`). It handles everything (images/reels/carousels) and tracks IG's changes. Clean code.

**What we didn't appreciate:** IG throttles the **GraphQL endpoint** much, *much* more aggressively than the HTML endpoint from datacenter IPs. A burst of ~30 GraphQL calls over a few hours (our verification tests + real traffic combined) tripped a rate-limit that lasted **half a day**.

Once tripped, IG responds with `401 Unauthorized` and the message `"Please wait a few minutes before you try again."` — with **no `Retry-After` header** and no structured hint for how long to wait. "A few minutes" was empirically several hours. **Re-probing extends the flag.**

Notably, during this GraphQL cooldown, the HTML endpoint kept serving data to the same IP. Two different rate-limit counters.

### 3. Hybrid (HTML primary + instaloader fallback) → resolves both

Current approach. HTML path handles the vast majority of posts (it's what Cloud Run's IP gets pre-rendered for free). GraphQL fallback catches the SPA-shell cases. Result:

- ~95%+ of requests never touch GraphQL
- GraphQL rate-limit stays dormant
- Carousel support (via instaloader) still works

### 4. Circuit breaker: the re-probing trap

When IG rate-limits us on GraphQL, we store a cooldown timestamp in Firestore (`cache.mark_ig_rate_limited`). For 30 min after, any GraphQL fallback short-circuits **without calling IG**. This matters because:

- User retries during cooldown → short-circuit → zero IG impact ✅
- Without the breaker: every user retry would probe IG → each probe extends IG's flag → infinite loop

HTML path still runs normally during a GraphQL cooldown — so most posts still work.

### 5. Don't batch-test against real IG

The 2026-04-23 incident was self-inflicted: a 26-URL verification test of instaloader consumed most of IG's per-IP GraphQL budget in minutes. Rule now: **test ONE real URL per change**, use fixture `IGMedia` data for anything more. See the `DEV WARNING` comment block at the top of [backend/pipeline.py](backend/pipeline.py).

### 6. No `Retry-After`, no structured rate-limit signal

IG's anonymous responses don't include `Retry-After` headers, `X-RateLimit-*` headers, or structured retry hints in the body — just a "fail" status and the vague message. You cannot build smart backoff that respects IG's actual timer because IG doesn't publish one. Best you can do is pick an empirically-good cooldown (30 min default, extensible).
