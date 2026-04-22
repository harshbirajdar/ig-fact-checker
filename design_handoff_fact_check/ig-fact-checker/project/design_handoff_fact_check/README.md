# Handoff: Fact Check for Instagram — Verdict UI

## Overview

"Fact Check" is a one-person iPhone utility that fact-checks Instagram reels and posts on-demand, triggered from Instagram's native share sheet. The user taps paper-plane → Share to → Fact Check (iOS Shortcut), which hits a Python/FastAPI backend. The backend fetches the post, extracts frames + audio (for reels), runs Claude with web search, and returns a rendered HTML page. The HTML is opened **inside Instagram's in-app browser** via a deep link, so the visible chrome is Instagram's (dark status bar area at top, URL pill, back/share/reload/compass pill at bottom) — not Safari, not iOS Quick Look.

**This handoff covers the HTML page returned by the backend** — the processing screen, the verdict card (5 variants), and the error screen.

---

## About the Design Files

The files in this bundle are **design references created in HTML** — a prototype and canvas showing the intended look and behavior. They are **not** production code to copy directly.

The target implementation is a **Jinja2 HTML template** rendered server-side by the FastAPI backend. The template must inline all CSS (no external fetches — the Instagram in-app browser is a sandboxed WebView and aggressive network requests from the doc have been flaky in testing) and be self-contained. Recreate the visual design in that Jinja2 template using its conventions. No JavaScript framework — it's a single rendered HTML document per request, plus optionally a tiny inline `<script>` for the processing ticker.

**Note on chrome:** the IGBrowserChrome shown in the prototype (top URL bar, bottom navigation pill) is Instagram's own in-app browser UI. **Do not reproduce it in the template** — Instagram will draw it automatically over the page. Your template renders only the content that sits *inside* the WebView viewport. Plan for ~108pt of space reserved at the top (status bar + URL pill) and ~80pt at the bottom (floating back + tools pill) — any tappable content under those areas will be occluded by Instagram's chrome.

---

## Fidelity

**High-fidelity.** Every color, size, spacing value, font, and radius in this bundle is the final intended value. Reproduce them pixel-perfectly. The design system is consistent with iOS native UI — values were chosen to feel like a well-made Apple system sheet, rendered inside a dark (or light) WebView.

---

## Chosen Direction

Three aesthetic directions were explored. **Direction C — "Calm System"** was selected. It feels native to iOS: SF-style type, soft rounded cards, a circular confidence ring, and the iOS system color palette.

Directions A (Clinical Lab / monospace) and B (Editorial / serif) were not selected. Only implement Direction C.

---

## Screens

### 1. Processing screen

Shown for the first 8–15 seconds while the backend runs the pipeline. Rendered server-side with the current step marked `active` at render time. If you want the subsequent steps to visibly tick forward while the page is open, add a tiny inline `<script>` that advances the active row on a ~1.8s interval — nothing fancier.

**Layout (top to bottom, inside the WebView viewport):**
- Top spacer reserved by IGBrowserChrome (108pt) — do not render content here
- Content area:
  - H1: "Fact-checking…" — 34pt, weight 700, letter-spacing −0.6
  - Subtitle: "Analyzing the shared reel" (or "shared post") — 16pt, muted color
  - Rounded card (16pt radius) containing the 6 pipeline steps as rows
  - Footer text: "This usually takes 8–15 seconds" — 13pt, muted, centered
- Bottom spacer reserved by IGBrowserChrome (~80pt)

**Step rows:**
- Padding 14 × 16, 0.5px hairline divider between rows
- Left: 22×22pt status indicator
  - **Done** → filled green circle `#34C759` with white checkmark inside
  - **Active** → spinning circle (2px ring, `#007AFF33` base, `#007AFF` top arc), animation 0.9s linear infinite
  - **Pending** → 16×16 hollow circle, 1.5px border, muted color, 40% opacity
- Right: step name, 16pt
  - Done: muted color, weight 400
  - Active: ink color, **weight 600**
  - Pending: ink color, weight 400

**Steps (reels):**
1. Fetching post data
2. Extracting frames
3. Transcribing audio
4. Searching the web
5. Cross-referencing sources
6. Writing verdict

**Steps (photo posts):** Omit steps 2 and 3.

---

### 2. Verdict card

**Five variants** share the same structure; only the **banner** (and a couple of accent hits in sources) change color.

| Variant | Light banner | Dark banner | Light sources accent | Dark sources accent |
|---|---|---|---|---|
| FALSE | `#FF3B30` | `#FF453A` | `#FF3B30` | `#FF453A` |
| MOSTLY FALSE | `#FF6B35` | `#FF7A45` | `#FF6B35` | `#FF7A45` |
| MOSTLY ACCURATE | `#8FC13E` | `#9FCE4E` | `#6FA524` | `#9FCE4E` |
| ACCURATE | `#34C759` | `#30D158` | `#34C759` | `#30D158` |
| CAN'T VERIFY | `#8E8E93` | `#98989F` | `#8E8E93` | `#98989F` |

Note the light-mode MOSTLY ACCURATE accent in source domains is `#6FA524` — a darkened variant — because the lime-green banner color doesn't have enough contrast as inline text on white.

**Layout (top to bottom, 16pt horizontal margin):**

#### Banner (accent-colored card)
- Radius 22pt, padding 18 top / 20 sides / 20 bottom
- Background: 135° linear-gradient from accent color to the same color darkened ~10% (light mode) or lightened ~6% (dark mode)
- Soft glow shadow: `0 6px 20px` of the accent at 25% opacity
- Subtle top-right sheen: 160×160 circle, `rgba(255,255,255,0.1)`, offset −40,−40, pointer-events none
- All text white (`#ffffff`) on every variant
- Contents:
  - Uppercase "Verdict" label — 11pt, letter-spacing 1.4, weight 700, 90% opacity
  - 10pt gap
  - Verdict word (e.g., "False", "Mostly false", "Mostly accurate", "Accurate", "Can't verify") — **44pt, weight 700, letter-spacing −1.0, line-height 1.0**. The two-word variants are allowed to wrap to a second line; do not shrink the type to keep them on one line.
  - 22pt gap
  - Divider: `1px solid rgba(255,255,255,0.2)`, 14pt padding-top below it
  - Certainty row (flex, items center, gap 10):
    - Ring: **42×42**, **5pt stroke**, white (`#ffffff`) arc on track `rgba(0,0,0,0.2)`, rotated −90°, round linecap on the arc, butt on the track
    - Label: "Verdict certainty" — 12pt, weight 500, 85% opacity
    - Number: right-aligned (margin-left auto), 15pt, weight 700, tabular numerals, letter-spacing −0.2
  - When `confidence == null` (CAN'T VERIFY): show `—` instead of `NN%`; ring renders only the track, no arc

#### Claim card (rounded card)
- 14pt top margin, 18pt radius, 16 × 18 padding
- Light mode: no border, card background `#FFFFFF`, shadow `0 1px 2px rgba(0,0,0,0.04)`
- Dark mode: 1px border `rgba(84,84,88,0.30)`, card background `#1C1C1E`, no shadow
- Contents:
  - Uppercase label "The claim" — 12pt, letter-spacing 0.4, weight 600, muted color
  - 8pt gap
  - Claim text — 17pt, italic, line-height 1.4, ink color
  - 12pt gap
  - Chips row (flex gap 6, wrap): author handle + content type
    - Chip: 12pt text, weight 500, padding 4 × 9, radius 99
    - Chip background: light `rgba(120,120,128,0.12)`, dark `rgba(120,120,128,0.24)`

#### Transcript card (reels only — omit for photo posts)
- 12pt top margin, same shell as claim card
- Label: "Transcript" (same styling as "The claim")
- Text: 14pt, line-height 1.5, muted color, straight (not italic), wrapped in curly quotes

#### What we found card
- 12pt top margin, same shell
- Label: "What we found"
- Text: 15pt, line-height 1.5, ink color

#### Sources card
- 12pt top margin, same shell but with `overflow: hidden` so inner dividers clip cleanly against the rounded corners
- Header row (14 top / 18 sides / 8 bottom padding): "Sources · N" (muted uppercase label, N = total count)
- Each source row:
  - Top border `0.5px solid` line color
  - Padding 12 × 18
  - Left (flex 1): title (15pt, ink, single-line truncate), domain (12pt, weight 500, **sources-accent color from table above** — matches verdict tone)
  - Right: 14×14 external-link glyph, muted, 50% opacity
- Show first 3 sources. If more exist, final row: "Show N more" — centered, 15pt, weight 500, accent color
- Expanded: show all sources, no "Show more" row. See "Show N more sources" in Behavior.

#### Bottom spacer
- 16pt internal padding at the end of the content, then the scroll area's own `paddingBottom: 90` clears Instagram's bottom pill

---

### 3. Error screen

- IGBrowserChrome spacer at top
- Then 40pt top padding, 24pt horizontal
- Icon: 64×64 rounded pill
  - Light: background `#FFE5E3`
  - Dark: background `#3A1F1D`
  - Contains a 32×32 SVG warning glyph — red `#FF3B30` circle outline (2.2 stroke) with a vertical line + dot inside
- 20pt gap
- H1: "Sorry, unable to process! :(" — 28pt, weight 700, letter-spacing −0.4
- 10pt gap
- Subtitle (reason): muted 16pt, line-height 1.45. Copy varies by error:
  - Private/deleted: "The post might be from a private account, deleted, or temporarily unreachable."
  - Timeout: "Took too long. Try again in a moment."
  - Backend 5xx: "Something went wrong on our end."
- 28pt gap
- Info card (same card shell): muted 14pt line-height 1.5 text: "Try sharing again in a moment. If the account is private, Fact Check can't see the post."

---

## Design Tokens

### Colors — Light mode
- Page background: `#F2F2F7`
- Card background: `#FFFFFF`
- Ink (primary text): `#1C1C1E`
- Muted (secondary text): `#8E8E93`
- Hairline/divider: `rgba(60, 60, 67, 0.12)`
- Card border (unused in light): `rgba(60, 60, 67, 0.10)`
- Banners & accents: see Verdict variants table above
- Done button (if used): `#007AFF`

### Colors — Dark mode
- Page background: `#000000`
- Card background: `#1C1C1E`
- Ink: `#FFFFFF`
- Muted: `#8E8E93`
- Hairline: `rgba(84, 84, 88, 0.35)`
- Card border: `rgba(84, 84, 88, 0.30)`
- Banners & accents: see Verdict variants table above

### Typography
- Font stack: `-apple-system, "SF Pro Text", "SF Pro Display", system-ui, sans-serif`
- Italic claim rendering uses the same stack in italic (no separate serif)
- Tabular numerals on the certainty number: `font-variant-numeric: tabular-nums`
- Global: `-webkit-font-smoothing: antialiased`

Key sizes used:
| Role | Size | Weight | Letter-spacing |
|---|---|---|---|
| Page H1 (processing/error) | 34 / 28 | 700 | −0.6 / −0.4 |
| Verdict word | 44 | 700 | −1.0 |
| Section label (uppercase) | 11–12 | 600–700 | 0.4–1.4 |
| Claim | 17 italic | 400 | — |
| Body / findings | 15 | 400 | — |
| Transcript / secondary body | 14 | 400 | — |
| Chips, small labels | 12 | 500–600 | — |
| Muted footnote | 13 | 400 | — |
| Certainty number | 15 | 700 | −0.2 |

### Spacing scale
6 · 8 · 10 · 12 · 14 · 16 · 18 · 20 · 22 · 24 · 28 — applied as margins between sections and internal padding.

### Radii
- Banner: 22
- Cards (claim / findings / transcript / sources): 18
- Status step card (processing): 16
- Error icon: 99 (pill/circle)
- Chip: 99
- Step status indicators: 99

### Shadows
- Cards, light mode: `0 1px 2px rgba(0, 0, 0, 0.04)`
- Verdict banner: `0 6px 20px ${accent}25` (accent hex + 25% alpha)
- No shadows on dark-mode cards (borders instead)

### Dividers
- Card-internal: `0.5px solid` hairline color
- Banner internal (above certainty row): `1px solid rgba(255, 255, 255, 0.2)`

---

## Behavior

### Live ticking (processing screen)
Render the page with one step already `active` matching whatever stage the pipeline is at when the template renders. If you want the row to visibly tick forward without polling, drop a single inline `<script>` that advances a CSS class on each row at 1.8s intervals — the total render budget is ~10s so three ticks is usually all you need. This is cosmetic; the real state is on the server.

### "Show N more" sources
Requires zero JS: render the first 3 and the rest inside a `<details>` element, using the "Show N more" row as the `<summary>`. Style the summary to look like the card row described above. When expanded, the summary row hides (replace with nothing, or flip to "Show fewer" — designer preference; first version can just hide).

### Light/dark theme switching
The HTML must respond to `prefers-color-scheme`. Implement via CSS custom properties switched in a `@media (prefers-color-scheme: dark)` block. Do not render two separate templates. Instagram's in-app browser respects the device theme.

---

## Claude JSON schema (consumed by the template)

The backend's Claude call should return this shape. The template maps fields as noted.

```json
{
  "verdict": "false" | "mostly_false" | "mostly_accurate" | "accurate" | "unverifiable",
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

Template mapping:
- `label` → verdict word (titlecased in display: "False", "Mostly false", "Mostly accurate", "Accurate", "Can't verify")
- `confidence` → ring fill + "NN%" number. If `verdict == "unverifiable"`, render `—` and empty ring.
- `verdict` → banner accent color + sources accent color (see table)
- `claim` → italic claim text
- `tldr` → "What we found" body
- `transcript_excerpt` → transcript card (omit card entirely if null/empty)
- `sources[]` → sources rows

### Picking the right verdict bucket

The 5-bucket scheme is deliberate. Guidance for Claude's prompt:
- **FALSE** — the core claim is wrong. No meaningful truth inside it.
- **MOSTLY FALSE** — the claim is broadly wrong but contains a kernel of truth, OR the headline is wrong but a narrow reading could be defended.
- **MOSTLY ACCURATE** — the claim is broadly right but overstates, misses caveats, or has a small factual error.
- **ACCURATE** — the claim is correct as stated.
- **CAN'T VERIFY** — not enough public information to determine. Use sparingly; prefer a hedged "MOSTLY" bucket where possible.

---

## Files in this bundle

- `Fact Check - Prototype.html` — live React prototype. Open directly in a browser; the on-page "Tweaks" panel (toggle in the toolbar) switches direction / theme / verdict state. All 5 verdict variants are reachable.
- `Fact Check - Design Canvas.html` — all 3 directions × both themes × all screens laid out side-by-side for reference. Direction C is the one to implement.
- `direction-c.jsx` — the source of the chosen direction. Contains every style value as JSX inline styles, plus the `IGBrowserChrome` component — treat as the source of truth for any measurement missing from this README.
- `screens.jsx` — shared fixtures (`SAMPLE`), color tokens (`PAGE.C`, `TONES.C`), and page-chrome components. The `TONES.C` object is the authoritative color table.
- `direction-a.jsx` / `direction-b.jsx` — the two unselected directions, included for reference only.
- `design-canvas.jsx` / `ios-frame.jsx` — scaffolding for the prototype/canvas only. Not part of the real UI.

---

## Assets

No bitmap assets. All iconography is inline SVG:
- Checkmark (done step) — 13×13 viewBox, 2px stroke, rounded caps/joins
- Spinner (active step) — CSS-only: border trick with `@keyframes dirC_spin`
- External-link glyph (source rows) — 14×14 viewBox
- Error icon — 32×32 viewBox, circle + vertical bar + dot
- Confidence ring — inline SVG, two concentric `<circle>` elements (track + arc), the arc uses `stroke-dasharray` + `stroke-dashoffset` to render `confidence%`

Copy these SVG paths directly from `direction-c.jsx`.

---

## Implementation notes

- **Inline the CSS** in the template (`<style>` block in `<head>`). Instagram's in-app WebView has been flaky with external CSS fetches.
- **System font stack only.** No Google Fonts. iOS has SF Pro natively.
- **Test in the actual Instagram in-app browser** on-device — not Safari, not mobile Chrome. The WebView has subtle differences (including the top/bottom chrome occluding content).
- **Reserve safe areas.** ~108pt top, ~80pt bottom inside the viewport are owned by Instagram's chrome. Either pad the body, or make the content a flex column with `min-height: 100vh` and appropriate padding.
- **No scroll-anchoring** or `position: fixed` — the in-app WebView scrolling is finicky with both.
- **Keep the document under ~100KB.** Transcript + 3–5 sources + tldr fit comfortably.
