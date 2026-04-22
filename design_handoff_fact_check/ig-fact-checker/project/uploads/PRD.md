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
- One content item at a time

**Out of scope (v1)**
- Stories, highlights, IGTV
- Carousel posts (multi-image)
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
  - `NEEDS CONTEXT` — orange gradient
  - `ACCURATE` — green gradient
  - `CAN'T VERIFY` — gray gradient
  - Structure: "VERDICT" (small caps) · big verdict word · **"Verdict certainty: NN%"** (always shown; `—` when verdict is `CAN'T VERIFY`)
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
Host: **Railway** free tier initially. `$5/mo` if usage exceeds.

Pipeline:
```
POST /check { url }
  │
  ├─ 1. Fetch IG page HTML
  │     GET <url> with User-Agent: Mozilla/5.0 ... Safari/17.0
  │     (anonymous browser pathway — same one non-IG users use)
  │
  ├─ 2. Parse embedded JSON
  │     Regex-extract <script type="application/json"> blocks
  │     Deep-search for object with "code" == shortcode
  │     Target path: .data.xdt_api__v1__media__shortcode__web_info.items[0]
  │
  ├─ 3. Extract metadata
  │     - caption.text
  │     - user.username, user.full_name
  │     - media_type: 1 = image, 2 = video (reel)
  │     - image_versions2[0].url  (for posts)
  │     - video_versions[0].url   (for reels)
  │     - like_count, comment_count, taken_at, dimensions
  │
  ├─ 4. Branch on media_type
  │     ┌─ POST (image): download image → base64
  │     │
  │     └─ REEL (video):
  │           4a. Download MP4 (HEAD check, cap at ~10 MB)
  │           4b. ffmpeg: extract 5 frames at t=0,1,2,3,4 → 5 JPEGs
  │           4c. ffmpeg: extract audio → m4a
  │           4d. Groq whisper-large-v3-turbo → transcript
  │
  ├─ 5. Claude call
  │     Model: claude-sonnet-4-6 (extended thinking off for speed)
  │     Tools: web_search (enabled)
  │     Input (multi-part):
  │       - text: "fact-check this Instagram [post|reel]"
  │       - text: caption + author handle + timestamp
  │       - text: transcript (reels only)
  │       - image: 5 frames (reels) or 1 image (post)
  │     Output: structured JSON (see §5.4)
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
  "verdict": "false" | "misleading" | "true" | "unverifiable",
  "label": "FALSE" | "NEEDS CONTEXT" | "ACCURATE" | "CAN'T VERIFY",
  "confidence": 0-100,
  "claim": "Plain-text restatement of the specific claim being checked",
  "tldr": "2-3 sentence plain-language verdict explanation",
  "transcript_excerpt": "Quote from the reel audio (reels only, optional)",
  "sources": [
    { "title": "Source title", "url": "https://...", "domain": "nasa.gov" }
  ]
}
```

### 5.5 Claude system prompt (v1 draft)
> You are a fact-checker for Instagram content. Given an Instagram post or reel (caption, image/frames, transcript if available), identify the primary factual claim and verify it using web search. Return a JSON verdict. Rules:
> - Use web_search to find authoritative sources (scientific bodies, fact-checkers, government/academic sites, reputable news).
> - Prefer 3 primary sources over 10 blog posts.
> - If the content is opinion, satire, or non-factual (aesthetic reels, music, personal experience), return `verdict: "unverifiable"` with `tldr` noting why.
> - Keep `tldr` under 40 words.
> - Confidence reflects source quality × claim specificity. Don't hedge past 95 unless you genuinely can't verify.

### 5.6 TOS posture
- The backend hits `instagram.com/<url>` exactly once per check, with a browser UA, no cookies.
- This replicates the anonymous-viewer pathway IG serves to non-logged-in browsers.
- No authentication bypass, no session cookies, no third-party scraping services.
- Still technically "automated access" per Meta TOS; acceptable at personal scale.
- Mitigation: rate limit self to ≤100/day; back off on 429/403.

### 5.7 Error handling
Error screen copy (all cases): **"Sorry, unable to process! :("** with a sub-line explaining the likely reason.

- **IG returns login wall / empty JSON** → error screen: "The post might be from a private account, deleted, or temporarily unreachable."
- **Video too long (>60s) or too large (>15MB)** → truncate to first 30 sec before processing (no error shown)
- **Claude returns no claim to check** (aesthetic reel, music video) → `CAN'T VERIFY` verdict card with `tldr: "No factual claim detected."` — not the error screen
- **Backend timeout (>30s)** → error screen: "Took too long. Try again in a moment."
- **Backend 5xx or unreachable** → error screen: "Something went wrong on our end."

---

## 6. Stack summary

| Layer | Choice | Why |
|---|---|---|
| Trigger | iOS Shortcut | No app install, $0, 3-tap entry |
| UI surface | Quick Look HTML | Best UX Shortcuts sandbox allows |
| Backend | Python + FastAPI | ffmpeg + audio pipeline friendlier than Node |
| Host | Railway | Free tier; trivial deploy |
| LLM | Claude Sonnet 4.6 | Vision + web_search in one call |
| ASR | Groq whisper-large-v3-turbo | 10× faster + 5× cheaper than OpenAI Whisper |
| Media | ffmpeg (binary in Railway container) | Frame + audio extraction |

**Estimated cost per fact-check:** ~$0.008 (Claude vision + search) + ~$0.0001 (Whisper, reels only) = <1¢ per check. At 50 checks/day, ~$12/mo all-in (after Railway free tier).

---

## 7. Decisions locked

1. **Verdict card tone** — Clinical (factual, scientific, no humor)
2. **Source count** — Show all, first 3 visible, rest behind "Show N more" expand
3. **Confidence display** — Always shown, labeled **"Verdict certainty: NN%"** to disambiguate from "confidence the reel is right." Shows `—` when verdict is `CAN'T VERIFY`.
4. **Error copy** — "Sorry, unable to process! :(" with a reason sub-line
5. **Branding** — Name: "Fact Check". Icon/colors to be defined during design phase.
6. **Theme** — Matches iOS system theme (light + dark variants both required)

---

## 8. Screens to design (design brief)

Based on this spec, three screens need pixel-perfect designs:

1. **Processing screen** — animated step-list, dark theme
2. **Verdict card — FALSE variant** — red banner, full anatomy
3. **Verdict card — ACCURATE variant** — green banner (same structure, different color)

Plus states: **NEEDS CONTEXT** (orange), **CAN'T VERIFY** (gray), **Error** (can't read post).

All screens are portrait, iPhone-sized, rendered as HTML inside Quick Look (so no native iOS components — must be pure HTML/CSS).

---

## 9. Not building

To be explicit:
- No native iOS app
- No backend scraping beyond anonymous-browser pathway
- No login, no accounts, no history, no share-the-verdict
- No Android, no web app
- No notification-based delivery (Quick Look only)
