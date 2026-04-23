# Fact Check for Instagram — PRD + Tech Spec

One-person iPhone tool that fact-checks Instagram reels and posts on-demand, triggered from Instagram's native share sheet.

---

## 1. Problem

Misinformation spreads fast on Instagram reels and posts. Doomscrolling users encounter dubious claims constantly, but verifying each one means leaving the app, opening a browser, typing a query, scanning results — enough friction that nobody does it. We want a one-gesture fact check that returns a verdict in ~10 seconds without breaking the scroll flow.

## 2. User

- Primary (and only) user: Harsh, a daily Instagram scroller on iPhone.
- Uses iPhone + iOS Shortcuts; not building a native app.
- Comfortable with 3-tap trigger flows (paper-plane → Share to → Shortcut).
- Personal-scale usage: estimated <50 fact-checks per day.

## 3. Scope

**In scope (v1)**
- Public Instagram reels (single video)
- Public Instagram photo posts (single image)
- Public Instagram carousel posts (multi-image, up to first 5 items — videos in a carousel use their thumbnail)
- One content item at a time

**Out of scope (v1)**
- Stories, highlights, IGTV
- Private accounts
- DM-shared content
- Saving history, sharing verdicts, multi-user

## 4. User experience

### 4.1 Entry flow
1. User sees a questionable reel/post in Instagram.
2. Taps paper-plane icon → **Share to…** → **Fact Check** (iOS Shortcut).
3. Quick Look modal opens over Instagram showing the processing state.
4. After 8–15 seconds, the modal transitions to the verdict card.
5. User taps **Done** (top-right) to dismiss → returns to Instagram mid-scroll.

### 4.2 Processing state (first 8–15 sec)
- Title: "Fact-checking…"
- Subtitle: "Analyzing the shared reel/post"
- Animated step list showing pipeline progress:
  1. Fetching post data
  2. Extracting frames *(reels only)*
  3. Transcribing audio *(reels only)*
  4. Searching the web
  5. Cross-referencing sources
  6. Writing verdict
- Active step pulses in blue, completed steps collapse to green checkmarks.

### 4.3 Verdict card
**Tone:** clinical — factual, scientific, no humor or hedging phrases.
**Theme:** matches iOS system theme (light + dark variants required).

Sections, top to bottom:
- **Banner** (full-width, color-coded):
  - `FALSE` — red gradient
  - `MOSTLY FALSE` — red-orange gradient
  - `MOSTLY ACCURATE` — lime / yellow-green gradient
  - `ACCURATE` — green gradient
  - `CAN'T VERIFY` — gray gradient
  - Structure: "VERDICT" (small caps) · big verdict word · **"Verdict certainty: NN%"** (always shown; `—` when verdict is `CAN'T VERIFY`)
  - **No neutral middle bucket.** Every verifiable claim must lean either toward true or toward false. The `MOSTLY *` tiers exist only for genuinely mixed claims (substance partly wrong, not wording nitpicks) — see §5.5 for prompt rules that prevent hedging into these tiers.
- **The claim** — italic blockquote, the specific factual assertion being checked. Below it, small chips for author handle and content type (e.g., "@wellness.daily", "Reel · 12 sec")
- **Audio transcript excerpt** *(reels only)* — shows what was said on the voiceover
- **What we found** — 2–3 sentence plain-language explanation
- **Sources** — show first 3 by default; remainder collapsed behind **"Show N more"** expand button. Each source has title + domain, clickable.

### 4.4 Constraints the UX has to live with
- Quick Look is not a native bottom sheet — it's a full-screen modal with a Done button top-right. No swipe-to-dismiss. Acceptable for v1 (confirmed with working demo).
- There is a ~0.5s context switch out of Instagram and back; unavoidable with Shortcuts.

---

## 5. Technical architecture

### 5.1 Overall flow
```
Instagram Reel/Post
       │
       ▼
Paper-plane → Share to → "Fact Check" iOS Shortcut
       │
       ▼
Shortcut: POST { url } to backend /check
       │
       ▼
Backend: fetch + parse + AI + render HTML
       │
       ▼
Shortcut: save HTML to temp file → Quick Look
       │
       ▼
User sees verdict card → taps Done → back to IG
```

### 5.2 iOS Shortcut (minimal)
Actions:
1. **Get URL from input** (Share Sheet, type: URLs)
2. **Get contents of** `POST https://<backend>/check` with body `{ "url": <URL> }`, response as file
3. **Quick Look** the response

(The current demo shortcut does `Get File → Quick Look`. The real shortcut swaps `Get File` for `Get Contents of URL`.)

### 5.3 Backend
Single endpoint: `POST /check`
Stack: **Python + FastAPI** (Python wins over Node for ffmpeg/Whisper ergonomics).
Host: **Google Cloud Run** (containerized, always-free tier covers our usage; no cold-start killer unlike Render; no 12-month cliff unlike AWS EC2 free tier).

Pipeline:
```
POST /check { url }
  │
  ├─ 0. Extract shortcode from URL  (instagram.com/(p|reel|tv)/<code>/)
  │
  ├─ 0a. Cache lookup (Firestore, keyed on shortcode)
  │     HIT + within TTL + valid verdict → return cached, skip pipeline
  │     MISS / expired / prior failure → continue
  │
  ├─ 1. Fetch metadata via instaloader (anonymous)
  │     Uses instaloader.Post.from_shortcode(). No cookies, no login.
  │     Replaces earlier hand-rolled HTML+JSON scraping which broke when IG
  │     moved media data out of the initial page HTML into client-side XHR
  │     (SPA hydration). Instaloader tracks IG's API changes so we don't.
  │     Rate-limit posture: max_connection_attempts=2 (1 retry). On sustained
  │     403/429 from IG we surface `rate_limited` to the user rather than
  │     hammering — PRD §5.6.
  │
  ├─ 2. Extract metadata from the Post object
  │     - post.caption
  │     - post.owner_username, post.owner_profile.full_name
  │     - post.typename: GraphImage | GraphVideo | GraphSidecar
  │     - post.url          (image posts)
  │     - post.video_url    (reels)
  │     - post.get_sidecar_nodes() + node.display_url (carousels)
  │     - post.video_duration
  │
  ├─ 3. Branch on typename
  │     ┌─ GraphImage: download image → base64 (content-type sniffed)
  │     │
  │     ├─ GraphSidecar (carousel):
  │     │    3a. Take first MAX_CAROUSEL_ITEMS nodes (= 5)
  │     │    3b. Download each node.display_url → base64 (multi-image vision)
  │     │        (video nodes inside the carousel use their thumbnail in v1)
  │     │
  │     └─ GraphVideo (reel):
  │           3a. Download MP4 (cap at MAX_VIDEO_BYTES ~15 MB)
  │           3b. ffmpeg: 5 frames @ 1 fps, first 5 sec, scaled 720w → JPEGs
  │           3c. ffmpeg: extract audio → mp3 (64kbps, capped 60 sec)
  │           3d. Groq whisper-large-v3-turbo → transcript (non-fatal if fails)
  │
  ├─ 4. Claude call
  │     Model: claude-sonnet-4-6
  │     Tools: web_search (server-side)
  │     Input (multi-part):
  │       - text: "Instagram {Reel|Photo post} from @handle ... CAPTION: ... AUDIO TRANSCRIPT: ..."
  │       - image: 5 frames (reels) OR 1 image (image post) OR up to 5 images (carousel), base64
  │       - text: "Return the JSON verdict now."
  │     Image content-type (jpeg/png/webp/gif) is sniffed from magic bytes before
  │     base64-encoding — IG can serve any of those and Claude rejects mismatches.
  │     System prompt enforces JSON-only output matching §5.4 schema.
  │
  ├─ 5. Cache write (Firestore)
  │     Store { verdict: <json>, cached_at: <unix_ts> } under shortcode
  │     Failures only propagate to logs; never block the response.
  │
  ├─ 6. Render HTML
  │     Jinja2 template with verdict card markup
  │     Inlines CSS (no external fetches — Quick Look sandbox restrictions)
  │
  └─ 7. Return HTML (Content-Type: text/html)
```

### 5.4 Verdict JSON schema (Claude's structured output)
```json
{
  "verdict": "false" | "mostly_false" | "mostly_true" | "true" | "unverifiable",
  "label": "FALSE" | "MOSTLY FALSE" | "MOSTLY ACCURATE" | "ACCURATE" | "CAN'T VERIFY",
  "confidence": 0-100,
  "claim": "Plain-text restatement of the specific claim being checked",
  "tldr": "2-3 sentence plain-language verdict explanation",
  "transcript_excerpt": "Quote from the reel audio (reels only, optional)",
  "sources": [
    { "title": "Source title", "url": "https://...", "domain": "nasa.gov" }
  ]
}
```

Internal mapping: `verdict` key → CSS tone class → display word
- `false` → `.tone-false` → "False"
- `mostly_false` → `.tone-mostly_false` → "Mostly false"
- `mostly_true` → `.tone-mostly_accurate` → "Mostly accurate"
- `true` → `.tone-accurate` → "Accurate"
- `unverifiable` → `.tone-unverified` → "Can't verify"

### 5.5 Claude system prompt (v2 — anti-hedging)
> You are a fact-checker for Instagram content. Given an Instagram post or reel (caption, image/frames, transcript if available), identify the primary factual claim and verify it using web search. Return a JSON verdict.
>
> **Sourcing**
> - Use `web_search` to find authoritative sources (scientific bodies, fact-checkers, government/academic sites, reputable news).
> - Prefer 3 primary sources over 10 blog posts.
>
> **Verdict selection — commit to a side. Do not hedge.**
> - `true` (ACCURATE): the core claim is correct. Minor wording imprecision, unstated caveats, or peripheral inaccuracies do **not** downgrade it.
> - `mostly_true` (MOSTLY ACCURATE): the core claim is correct but has a meaningful, substantive caveat — e.g., wrong scope ("only X" when it's "X among several"), outdated figure, over-simplified mechanism. The claim is right in spirit but materially off in detail.
> - `mostly_false` (MOSTLY FALSE): the core claim is wrong, but some surrounding context, numbers, or named entities are real. Classic shape: the person/event/study exists, but the described cause, outcome, or mechanism is wrong.
> - `false` (FALSE): the core claim is wrong and authoritative sources directly contradict it.
> - `unverifiable` (CAN'T VERIFY): there is no specific, testable factual claim (aesthetic/music/opinion/personal-experience reel), or no authoritative sources exist on the topic.
>
> **Anti-hedging rule (important).** The `mostly_*` tiers are **not** a safe middle. If you're tempted to pick one because you're unsure, re-read the claim and decide: is it broadly right → `true`; broadly wrong → `false`; not a factual claim → `unverifiable`. Only use `mostly_true` / `mostly_false` when the claim is **genuinely half-right in substance** (not in wording). Previous versions of this system returned "needs context" for ~99% of inputs; that is a failure mode, not a target.
>
> **Worked examples**
> - "Octopuses have three hearts, blue copper-based blood" → `true`. All substantive parts correct.
> - "Einstein failed math as a student" → `mostly_false`. The person is real; the core claim is wrong (grading-scale misread).
> - "The Great Wall is the only man-made structure visible from space" → `mostly_true`. Visible under ideal conditions: yes. Only: no.
> - "Drinking celery juice cures autoimmune disease" → `false`. Sources directly contradict.
> - "I've never felt better since taking these supplements" → `unverifiable`. Personal experience, no testable claim.
>
> **Output constraints**
> - Keep `tldr` under 40 words.
> - `confidence` reflects source quality × claim specificity. Don't hedge past 95 unless you genuinely can't verify. Use `null` only for `unverifiable`.

### 5.6 TOS posture
- Metadata fetched via `instaloader` (Python library) in anonymous mode — **no cookies, no login, no session.** Same surface area as the old hand-rolled parser, just with a maintained library that tracks IG's anti-scraping changes.
- Instaloader calls IG's public GraphQL endpoint at `https://www.instagram.com/graphql/query` — the same endpoint IG's own JavaScript calls for anonymous viewers.
- No authentication bypass, no session cookies, no third-party scraping services.
- Still technically "automated access" per Meta TOS; acceptable at personal scale.
- **Rate-limit posture:** `max_connection_attempts=2` (one retry max). On sustained 403/429 we surface `rate_limited` to the user rather than hammering IG — this is a deliberate "respect the rate limit, don't get flagged" choice, not a usability optimization.
- Self-rate-limit to ≤100/day.

### 5.7 Error handling
Error screen copy (all cases): **"Sorry, unable to process! :("** with a sub-line explaining the likely reason.

- **IG returns login wall / post deleted / private account** (`IGFetchError`) → error screen: "The post might be from a private account, deleted, or temporarily unreachable."
- **IG rate-limits us** (`IGRateLimitError`, sustained 403/429 from the GraphQL endpoint after retries exhausted) → error screen: "Instagram is rate-limiting us. Please try again in a few minutes." Retrying is the user's choice, not ours; we do not escalate.
- **Video too long (>60s) or too large (>15MB)** → truncate to first 60 sec before processing (no error shown)
- **Claude returns no claim to check** (aesthetic reel, music video) → `CAN'T VERIFY` verdict card with `tldr: "No factual claim detected."` — not the error screen
- **Backend timeout (>30s)** → error screen: "Took too long. Try again in a moment."
- **Backend 5xx or unreachable** → error screen: "Something went wrong on our end."
- **Any unhandled exception** → error screen (backend_error). Graceful failure is a hard requirement — the user never sees a 500 or a blank page.
- **Cache-layer failures** (Firestore unavailable, auth problems, etc.) are logged and silently fall through to the real pipeline. Cache is an optimization, not a dependency.

### 5.8 Cache

Purpose: save ~$0.008 + ~10 sec latency on repeat checks of the same shortcode. Viral reels get re-scrolled; expected hit rate 30–50%.

- **Store:** Firestore (GCP), collection `fact_check_cache`
- **Key:** Instagram shortcode (e.g., `DVYaCCfE8OM`) — identical URL with different query params (e.g., `igsh=...`) resolves to the same key
- **Value:** `{ verdict: <full Claude JSON>, cached_at: <unix timestamp> }`
- **TTL:** 7 days, checked on read (not enforced by Firestore itself)
- **What is cached:** only successful verdicts. Failures (IG fetch errors, Claude errors, timeouts) are **not** cached — next request retries from scratch.
- **Enabled when:** `GOOGLE_CLOUD_PROJECT` env var is set (automatic on Cloud Run; requires `gcloud auth application-default login` for local dev).
- **Fail-open:** any Firestore error is swallowed; pipeline runs as if cache were disabled.

Firestore free tier: 1 GB storage, 50K reads/day, 20K writes/day. At 50 checks/day, we use ~0.3% of the write quota.

---

## 6. Stack summary

| Layer | Choice | Why |
|---|---|---|
| Trigger | iOS Shortcut | No app install, $0, 3-tap entry |
| UI surface | Quick Look HTML | Best UX Shortcuts sandbox allows |
| Backend | Python + FastAPI | ffmpeg + audio pipeline friendlier than Node |
| Host | Google Cloud Run | Always-free 2M req/mo, Docker-native, no cold-start pain |
| Cache | Google Firestore | Free tier, persists across Cloud Run scale-to-zero |
| Secrets | GCP Secret Manager | Encrypted at rest, mounted as env vars into Cloud Run |
| IG fetch | `instaloader` (anonymous) | Maintained library tracking IG's anti-scraping changes; works for images, reels, and carousels uniformly |
| LLM | Claude Sonnet 4.6 | Vision + web_search in one call |
| ASR | Groq whisper-large-v3-turbo | 10× faster + 5× cheaper than OpenAI Whisper |
| Media | ffmpeg (apt-installed in the Docker image) | Frame + audio extraction |
| CI/CD | Cloud Build trigger on `git push main` | Auto-build Docker image → auto-deploy to Cloud Run (no manual `gcloud` after every change) |

**Estimated cost per fact-check (cache miss):** ~$0.008 (Claude vision + search) + ~$0.0001 (Whisper, reels only) = <1¢ per check.
**Cache hit cost:** effectively $0 (Firestore free tier).
At 50 checks/day with 40% cache hit rate, ~$4/mo all-in (stays within Cloud Run + Firestore free tiers).

---

## 7. Decisions locked

1. **Verdict card tone** — Clinical (factual, scientific, no humor)
2. **Source count** — Show all, first 3 visible, rest behind "Show N more" expand
3. **Confidence display** — Always shown, labeled **"Verdict certainty: NN%"** to disambiguate from "confidence the reel is right." Shows `—` when verdict is `CAN'T VERIFY`.
4. **Error copy** — "Sorry, unable to process! :(" with a reason sub-line
5. **Branding** — Name: "Fact Check". Icon/colors to be defined during design phase.
6. **Theme** — Matches iOS system theme (light + dark variants both required)
7. **Verdict taxonomy** — Five buckets (`FALSE · MOSTLY FALSE · MOSTLY ACCURATE · ACCURATE · CAN'T VERIFY`), no neutral middle. Replaces the earlier 4-bucket model whose `NEEDS CONTEXT` middle became a hedging sink (~99% of real verdicts). New system prompt (§5.5) explicitly bans hedging into the `MOSTLY *` tiers.

---

## 8. Design system

**Direction:** *Calm System* — iOS-native feel. SF system font, soft rounded cards, circular confidence ring on the verdict banner, Apple system colors. Two alternate directions (Clinical Lab / mono, and Editorial / serif) were explored and rejected.

### 8.1 Screens delivered

| Screen | When shown | Key elements |
|---|---|---|
| **Processing** | Rendered on GET `/processing` (reserved for future async mode). Today the request is synchronous and ~10s, so users typically see Quick Look's own loading, then jump to the verdict. | H1 + subtitle + 6-step progress card (reels; 4 steps for posts) + "This usually takes 8–15 seconds" footer. |
| **Verdict — FALSE** | `verdict == "false"` | Red banner (`#FF3B30` light / `#FF453A` dark), claim card, transcript (reels), findings, sources. |
| **Verdict — MOSTLY FALSE** | `verdict == "mostly_false"` | Red-orange banner (`#FF6B35` / `#FF7A45`). White banner fg in both themes. |
| **Verdict — MOSTLY ACCURATE** | `verdict == "mostly_true"` | Lime / yellow-green banner (bg `#8FC13E` / `#9FCE4E`; accent `#6FA524` / `#9FCE4E` for source domain links). |
| **Verdict — ACCURATE** | `verdict == "true"` | Green banner (`#34C759` / `#30D158`). |
| **Verdict — CAN'T VERIFY** | `verdict == "unverifiable"` | Gray banner (`#8E8E93` / `#98989F`). Certainty shows `—`, ring is track-only. |
| **Error** | Any pipeline failure | Red warning icon in a tinted circle + title + reason sub-line + info card. |

### 8.2 Visual tokens

**Page**
- Light: bg `#F2F2F7` · ink `#1C1C1E` · card `#FFFFFF` · muted `#8E8E93` · hairline `rgba(60,60,67,0.12)`
- Dark:  bg `#000000` · ink `#FFFFFF` · card `#1C1C1E` · muted `#8E8E93` · hairline `rgba(84,84,88,0.35)` · card border `rgba(84,84,88,0.30)` (cards use a border in dark, shadow in light)

**Typography**
- Stack: `-apple-system, "SF Pro Text", "SF Pro Display", system-ui, sans-serif` (system only, no Google Fonts)
- Page H1 (processing): 34 / 700 / -0.6
- Error H1: 28 / 700 / -0.4
- Verdict word: **44 / 700 / -1.0 / line-height 1.0**
- Claim body: 17 / italic / 400 / line-height 1.4
- Findings body: 15 / 400 / line-height 1.5
- Transcript body: 14 / 400 / line-height 1.5 / muted
- Section labels (uppercase): 11–12 / 600–700 / letter-spacing 0.4–1.4
- Chips: 12 / 500
- Certainty number: 15 / 700 / tabular-nums / -0.2
- Muted footnote: 13 / 400

**Spacing scale:** 6 · 8 · 10 · 12 · 14 · 16 · 18 · 20 · 22 · 24 · 28

**Radii:** banner 22 · card 18 · step card 16 · error icon / chip / step indicator 99 (pill)

**Shadows / borders**
- Light cards: `box-shadow: 0 1px 2px rgba(0,0,0,0.04)`
- Dark cards: no shadow; `border: 1px solid rgba(84,84,88,0.30)`
- Verdict banner: `box-shadow: 0 6px 20px <accent>40` (25% alpha on accent)

**Banner internals**
- 135° gradient from accent → accent darkened ~10%
- Subtle white sheen (`160×160` circle, `rgba(255,255,255,0.1)`, offset `-40,-40`)
- Divider above certainty row: `1px solid rgba(255,255,255,0.2)` (or `rgba(0,0,0,0.18)` on dark-mode orange)

### 8.3 Confidence ring
- Diameter 28, stroke 3
- Track: `rgba(255,255,255,0.22)`, always drawn
- Fill arc: `rgba(255,255,255,0.95)`, rounded cap, rotated `-90°` (starts at 12 o'clock), `stroke-dasharray` / `stroke-dashoffset` precomputed from the confidence value in Python
- When `confidence == null`: track-only (no arc), certainty number renders as `—`

### 8.4 Dark-mode handling
- Single template; CSS custom properties switch via `@media (prefers-color-scheme: dark)`
- Tone accents are per-tone via `.tone-<name>` class variables on the verdict body; both light and dark colors live in the same CSS
- No JavaScript theme logic; no two-template dance

### 8.5 Animation + interaction
- Active processing step uses a CSS-only border-spinner keyframe (`@keyframes dirC_spin 0.9s linear infinite`)
- "Show N more" sources uses native `<details>`/`<summary>` (zero JS). Summary styled to look like a source row; hidden when `[open]`
- "Done" button top-right is **visual only** — Quick Look provides the real dismiss
- No `position: fixed`, no scroll-anchoring — Quick Look's viewport is finicky

### 8.6 Sandbox constraints (why the design looks the way it does)
- All CSS inlined in `<style>` block — Quick Look blocks external CSS/font fetches
- All icons are inline SVG — no external assets
- System font stack only — iOS ships SF Pro natively
- Document size kept under 100 KB so the shortcut's `Get Contents of URL` completes quickly

---

## 9. Not building

To be explicit:
- No native iOS app
- No backend scraping beyond anonymous-browser pathway
- No login, no accounts, no history, no share-the-verdict
- No Android, no web app
- No notification-based delivery (Quick Look only)
