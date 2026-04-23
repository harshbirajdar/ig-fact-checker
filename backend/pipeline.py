"""Fact Check pipeline: IG URL → metadata + media → Claude verdict JSON.

All network + media work lives here. Each stage raises a typed exception so
main.py can map failures to the correct error screen (PRD §5.7).

No authentication against Instagram: we fetch the anonymous public page (same
pathway IG serves to non-logged-in browsers) and parse the embedded JSON.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal

import httpx
from anthropic import Anthropic

# on_stage signature: (step_index: int, media_type_or_none: str | None)
StageCallback = Callable[[int, "str | None"], None]

log = logging.getLogger("fact_check")


# ── Exceptions (map to error screens) ───────────────────────────────────────
class PipelineError(Exception):
    """Base for all pipeline failures. error_reason attribute maps to error copy."""
    error_reason: str = "backend_error"


class IGFetchError(PipelineError):
    """IG page unreachable, empty, or content inaccessible (private/deleted)."""
    error_reason = "private_or_deleted"


class IGRateLimitError(PipelineError):
    """IG is rate-limiting us. User should retry in a few minutes.
    We deliberately do NOT retry aggressively to avoid escalation."""
    error_reason = "rate_limited"


class MediaExtractionError(PipelineError):
    """Found metadata but couldn't download/process the media."""
    error_reason = "backend_error"


class ClaudeError(PipelineError):
    """Anthropic API failure or malformed response."""
    error_reason = "backend_error"


# Transcription failures are non-fatal; we continue with no transcript.


# ── Config ──────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
GROQ_WHISPER_MODEL = os.environ.get("GROQ_WHISPER_MODEL", "whisper-large-v3-turbo")
MAX_VIDEO_BYTES = int(os.environ.get("MAX_VIDEO_BYTES", "15000000"))

BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
)

SHORTCODE_RE = re.compile(r"instagram\.com/(?:[^/]+/)?(?:p|reel|tv)/([A-Za-z0-9_-]+)")
SCRIPT_JSON_RE = re.compile(
    r'<script type="application/json"[^>]*>(.*?)</script>', re.DOTALL
)

# Cap carousel items to bound Claude vision cost + request latency.
MAX_CAROUSEL_ITEMS = 5

MediaKind = Literal["image", "video", "carousel"]


@dataclass
class IGMedia:
    shortcode: str
    media_type: MediaKind
    caption: str
    username: str
    full_name: str
    duration_seconds: int | None
    # "image"/"video" → single URL in media_urls[0].
    # "carousel" → up to MAX_CAROUSEL_ITEMS image URLs (videos inside a carousel
    # use their thumbnail, so all entries here are images).
    media_urls: list[str]


# ── IG fetch (hybrid: HTML first, instaloader fallback) ─────────────────────
#
# ┌─ DEV WARNING — READ BEFORE EDITING fetch_ig_metadata ──────────────────┐
# │ DO NOT batch-test this function against real IG URLs.                  │
# │                                                                        │
# │ We talk to Instagram via TWO endpoints, with very different rate-limit │
# │ behavior from datacenter IPs (Cloud Run):                              │
# │                                                                        │
# │   HTML endpoint  (/p/<shortcode>/)       — gentle, rarely throttles    │
# │   GraphQL        (/graphql/query, inst.) — TIGHT, throttles aggressively│
# │                                                                        │
# │ We deliberately hit HTML first to stay under GraphQL's radar. A        │
# │ batch-test that forces the GraphQL fallback path (e.g. repeatedly      │
# │ fetching SPA-shell posts) is the fastest way to trip IG's cooldown —   │
# │ and once tripped, it takes hours (sometimes a full day) to clear.      │
# │                                                                        │
# │ INCIDENT 2026-04-23: 26-URL instaloader verification + Cloud Run       │
# │ smoke test + user traffic all in one afternoon locked our IP out of    │
# │ IG's GraphQL for ~half a day. The fix was to move HTML to primary and  │
# │ make GraphQL a last-resort fallback (this file). Do not regress.       │
# │                                                                        │
# │ For changes needing broader coverage: use fixture IGMedia snapshots    │
# │ (dataclass values), NOT real URLs. Test ONE real URL per push, max.    │
# │                                                                        │
# │ See PRD §5.3 (hybrid strategy) and §5.6 (rate-limit posture + breaker).│
# └────────────────────────────────────────────────────────────────────────┘
def extract_shortcode(url: str) -> str:
    m = SHORTCODE_RE.search(url)
    if not m:
        raise IGFetchError(f"Not a valid Instagram post/reel URL: {url}")
    return m.group(1)


def _loader() -> "object":
    """Build a fresh Instaloader context per request.

    We cap connection attempts to keep total wall time under Cloud Run's async
    worker budget AND to avoid looking like a hammering bot to IG. If IG throws
    a sustained 403/429, we surface a `rate_limited` error to the user rather
    than aggressive retries (PRD §5.6 — TOS posture: polite anonymous only).
    """
    import instaloader
    return instaloader.Instaloader(
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
        quiet=True,
        max_connection_attempts=2,  # 1 retry max; fail fast on rate-limit
        request_timeout=15.0,
    )


class _HtmlParseMiss(Exception):
    """Internal signal: HTML endpoint returned OK but no media metadata was found.

    Raised by _fetch_via_html when IG served the SPA-shell variant of the page
    (media data loaded client-side via XHR, not embedded). We catch this in
    fetch_ig_metadata and fall back to instaloader's GraphQL call.

    Not exposed to callers; never escapes this module.
    """


def fetch_ig_metadata(url: str) -> IGMedia:
    """Resolve an IG URL to structured metadata.

    HYBRID STRATEGY (2026-04-23):
      1. Try the HTML endpoint first — /p/<shortcode>/. This is what IG serves
         to crawlers/datacenter IPs and it's the lenient rate-limit path. Most
         requests are handled here without ever touching GraphQL.
      2. Only if HTML has no embedded media metadata (new-scheme SPA shell),
         fall back to instaloader's GraphQL lookup. GraphQL is the tight
         rate-limit path; the circuit breaker guards against hammering when
         IG is angry.

    Why this split exists: on 2026-04-23 pure instaloader usage tripped IG's
    GraphQL-endpoint rate-limit and locked the service out for hours. Testing
    on Cloud Run showed the HTML endpoint was still happily serving data to
    our IP at the same time. Using HTML primarily reduces GraphQL traffic by
    ~95%+, which keeps IG's per-endpoint flag dormant.
    """
    shortcode = extract_shortcode(url)

    # Path A: HTML endpoint (gentle). Handles ~most posts from datacenter IPs.
    try:
        return _fetch_via_html(shortcode)
    except _HtmlParseMiss as miss:
        log.info("HTML parse miss for %s (%s); falling back to instaloader", shortcode, miss)

    # Path B: instaloader / GraphQL (fallback only — tight rate-limit).
    return _fetch_via_instaloader(shortcode)


# ── Path A: HTML endpoint ────────────────────────────────────────────────────
def _fetch_via_html(shortcode: str) -> IGMedia:
    """Fetch and parse /p/<shortcode>/ HTML. Raises _HtmlParseMiss when the page
    is served in SPA-shell form (no embedded media JSON) so fetch_ig_metadata
    can fall back. Raises IGFetchError for genuine errors (private/deleted/404)."""
    canonical = f"https://www.instagram.com/p/{shortcode}/"
    try:
        with httpx.Client(timeout=15, follow_redirects=True) as client:
            resp = client.get(canonical, headers={
                "User-Agent": BROWSER_UA,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9",
                "Accept-Language": "en-US,en;q=0.5",
            })
    except httpx.RequestError as e:
        # Transient network error — treat as miss so we try instaloader path.
        raise _HtmlParseMiss(f"network: {e}") from e

    if resp.status_code in (403, 429):
        # HTML path is rate-limited (rare — it's the gentle endpoint). Let the
        # instaloader fallback try; if it's also blocked the breaker trips.
        raise _HtmlParseMiss(f"HTTP {resp.status_code}")

    if resp.status_code == 404:
        raise IGFetchError(f"Post not found (HTTP 404): {shortcode}")

    if resp.status_code != 200:
        raise _HtmlParseMiss(f"HTTP {resp.status_code}")

    html = resp.text
    if shortcode not in html:
        # Neither SPA shell nor pre-rendered; post is private/deleted/blocked.
        raise IGFetchError("Post is private, deleted, or inaccessible")

    media = None
    for script_body in SCRIPT_JSON_RE.findall(html):
        if shortcode not in script_body:
            continue
        try:
            data = json.loads(script_body)
        except json.JSONDecodeError:
            continue
        media = _deep_find_media(data, shortcode)
        if media:
            break

    if not media:
        # HTML was served but contains no media metadata — new-scheme SPA.
        # Signal fallback to instaloader.
        raise _HtmlParseMiss("no media metadata in HTML (SPA shell)")

    return _html_media_to_igmedia(shortcode, media)


def _deep_find_media(obj: Any, shortcode: str) -> dict[str, Any] | None:
    """Walk nested JSON looking for the media item whose `code` matches."""
    if isinstance(obj, dict):
        if obj.get("code") == shortcode and "media_type" in obj:
            return obj
        for v in obj.values():
            found = _deep_find_media(v, shortcode)
            if found:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _deep_find_media(item, shortcode)
            if found:
                return found
    return None


def _html_media_to_igmedia(shortcode: str, media: dict[str, Any]) -> IGMedia:
    """Convert IG's embedded JSON media object to our IGMedia dataclass."""
    caption_obj = media.get("caption") or {}
    user_obj = media.get("user") or {}
    caption = (caption_obj.get("text") or "").strip()
    username = user_obj.get("username") or ""
    full_name = user_obj.get("full_name") or ""
    mt = media.get("media_type")

    if mt == 1:  # image
        versions = media.get("image_versions2", {}).get("candidates", [])
        if not versions:
            raise MediaExtractionError("HTML: image has no versions")
        return IGMedia(
            shortcode=shortcode, media_type="image",
            caption=caption, username=username, full_name=full_name,
            duration_seconds=None, media_urls=[versions[0]["url"]],
        )

    if mt == 2:  # video (reel)
        versions = media.get("video_versions") or []
        if not versions:
            raise MediaExtractionError("HTML: video has no versions")
        duration = int(media["video_duration"]) if media.get("video_duration") else None
        return IGMedia(
            shortcode=shortcode, media_type="video",
            caption=caption, username=username, full_name=full_name,
            duration_seconds=duration, media_urls=[versions[0]["url"]],
        )

    if mt == 8:  # carousel
        items = media.get("carousel_media") or []
        if not items:
            raise MediaExtractionError("HTML: empty carousel")
        urls: list[str] = []
        for item in items[:MAX_CAROUSEL_ITEMS]:
            versions = item.get("image_versions2", {}).get("candidates", [])
            if versions:
                urls.append(versions[0]["url"])
        if not urls:
            raise MediaExtractionError("HTML: carousel has no image versions")
        return IGMedia(
            shortcode=shortcode, media_type="carousel",
            caption=caption, username=username, full_name=full_name,
            duration_seconds=None, media_urls=urls,
        )

    raise MediaExtractionError(f"HTML: unsupported media_type: {mt}")


# ── Path B: instaloader (GraphQL) fallback ───────────────────────────────────
def _fetch_via_instaloader(shortcode: str) -> IGMedia:
    """Fallback fetcher using instaloader (GraphQL endpoint). Guarded by the
    circuit breaker: if we're in cooldown, we skip the call entirely and raise
    IGRateLimitError so the cooldown drains rather than extends (PRD §5.6)."""
    import cache  # local import: avoid circular with main.py at import time
    import instaloader
    from instaloader.exceptions import (
        BadResponseException,
        ConnectionException,
        LoginRequiredException,
        QueryReturnedBadRequestException,
        QueryReturnedNotFoundException,
    )

    remaining = cache.ig_cooldown_remaining()
    if remaining > 0:
        log.info("IG circuit breaker OPEN; %ds remaining, skipping instaloader fetch for %s",
                 remaining, shortcode)
        raise IGRateLimitError(f"In IG cooldown for {remaining}s more")

    L = _loader()

    try:
        post = instaloader.Post.from_shortcode(L.context, shortcode)
    except QueryReturnedNotFoundException as e:
        raise IGFetchError(f"Post not found or deleted: {shortcode}") from e
    except LoginRequiredException as e:
        raise IGFetchError(f"Post requires login (private/restricted): {shortcode}") from e
    except (QueryReturnedBadRequestException, BadResponseException) as e:
        msg = str(e).lower()
        if any(s in msg for s in ("401", "403", "rate", "bad response")):
            cache.mark_ig_rate_limited()
            raise IGRateLimitError(f"IG rate-limited or refused: {e}") from e
        raise IGFetchError(f"IG returned bad response: {e}") from e
    except ConnectionException as e:
        cache.mark_ig_rate_limited()
        raise IGRateLimitError(f"IG connection exhausted: {e}") from e

    caption = (post.caption or "").strip()
    username = post.owner_username or ""
    try:
        full_name = post.owner_profile.full_name or ""
    except Exception:
        full_name = ""

    typename = post.typename  # GraphImage / GraphVideo / GraphSidecar

    if typename == "GraphImage":
        return IGMedia(
            shortcode=shortcode, media_type="image",
            caption=caption, username=username, full_name=full_name,
            duration_seconds=None, media_urls=[post.url],
        )
    if typename == "GraphVideo":
        if not post.video_url:
            raise MediaExtractionError("No video URL on GraphVideo post")
        dur = int(post.video_duration) if post.video_duration else None
        return IGMedia(
            shortcode=shortcode, media_type="video",
            caption=caption, username=username, full_name=full_name,
            duration_seconds=dur, media_urls=[post.video_url],
        )
    if typename == "GraphSidecar":
        try:
            nodes = list(post.get_sidecar_nodes())
        except Exception as e:
            raise MediaExtractionError(f"Could not read carousel nodes: {e}") from e
        if not nodes:
            raise MediaExtractionError("Empty carousel")
        urls = [node.display_url for node in nodes[:MAX_CAROUSEL_ITEMS]]
        return IGMedia(
            shortcode=shortcode, media_type="carousel",
            caption=caption, username=username, full_name=full_name,
            duration_seconds=None, media_urls=urls,
        )

    raise MediaExtractionError(f"Unsupported post typename: {typename}")


# ── Media download + ffmpeg ─────────────────────────────────────────────────
def _download(url: str, dest: Path, max_bytes: int) -> None:
    try:
        with httpx.stream("GET", url, timeout=30, follow_redirects=True,
                          headers={"User-Agent": BROWSER_UA}) as resp:
            if resp.status_code != 200:
                raise MediaExtractionError(f"Media fetch HTTP {resp.status_code}")
            total = 0
            with dest.open("wb") as f:
                for chunk in resp.iter_bytes(chunk_size=65536):
                    total += len(chunk)
                    if total > max_bytes:
                        raise MediaExtractionError(f"Media exceeds {max_bytes} bytes")
                    f.write(chunk)
    except httpx.RequestError as e:
        raise MediaExtractionError(f"Media download error: {e}") from e


def _ffmpeg(args: list[str]) -> None:
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", *args],
            check=True, timeout=20,
            capture_output=True,
        )
    except FileNotFoundError:
        raise MediaExtractionError("ffmpeg not installed")
    except subprocess.CalledProcessError as e:
        raise MediaExtractionError(f"ffmpeg failed: {e.stderr.decode(errors='replace')[:200]}")
    except subprocess.TimeoutExpired:
        raise MediaExtractionError("ffmpeg timed out")


def extract_frames_and_audio(video_path: Path, out_dir: Path) -> tuple[list[Path], Path | None]:
    """From MP4, produce 5 frames at t=0,1,2,3,4 (bound by video length) + mp3 audio."""
    frame_paths = [out_dir / f"frame_{i}.jpg" for i in range(5)]
    # Single ffmpeg pass: extract exactly 5 frames at 1 fps, capped at 5 sec
    _ffmpeg([
        "-i", str(video_path),
        "-vf", "fps=1,scale=720:-2",
        "-frames:v", "5",
        "-q:v", "4",
        str(out_dir / "frame_%d.jpg"),
    ])
    # ffmpeg numbers from 1 — rename so indices 0-4
    produced: list[Path] = []
    for i in range(1, 6):
        src = out_dir / f"frame_{i}.jpg"
        if src.exists():
            dst = out_dir / f"f{i - 1}.jpg"
            src.rename(dst)
            produced.append(dst)
    if not produced:
        raise MediaExtractionError("ffmpeg produced no frames")

    audio_path = out_dir / "audio.mp3"
    try:
        _ffmpeg([
            "-i", str(video_path),
            "-vn", "-acodec", "libmp3lame", "-b:a", "64k",
            "-t", "60",
            str(audio_path),
        ])
    except MediaExtractionError:
        log.warning("audio extraction failed; continuing without transcript")
        audio_path = None  # type: ignore[assignment]

    return produced, audio_path


# ── Groq Whisper transcription (non-fatal) ──────────────────────────────────
def transcribe(audio_path: Path) -> str | None:
    if not GROQ_API_KEY:
        return None
    try:
        with audio_path.open("rb") as f:
            resp = httpx.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                files={"file": (audio_path.name, f, "audio/mpeg")},
                data={
                    "model": GROQ_WHISPER_MODEL,
                    "response_format": "json",
                    "language": "en",
                },
                timeout=30,
            )
        if resp.status_code != 200:
            log.warning("Groq transcription %s: %s", resp.status_code, resp.text[:200])
            return None
        return (resp.json().get("text") or "").strip() or None
    except Exception as e:
        log.warning("Groq transcription failed: %s", e)
        return None


# ── Claude verdict ──────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a clinical, factual fact-checker for Instagram content. Given a post's caption, author, optional audio transcript, and image frames, identify the single most important factual claim being made and verify it using web_search.

SOURCING
- Use web_search to find authoritative sources (scientific bodies, government sites, university/.edu, major fact-checkers, reputable news).
- Prefer 3-5 high-quality sources over many low-quality ones.

VERDICT SELECTION — COMMIT TO A SIDE. DO NOT HEDGE.
- "true" (ACCURATE): core claim is correct. Minor wording imprecision, unstated caveats, or peripheral inaccuracies do NOT downgrade it.
- "mostly_true" (MOSTLY ACCURATE): core claim is correct but has a meaningful, substantive caveat — wrong scope ("only X" when it's "X among several"), outdated figure, over-simplified mechanism. Right in spirit, materially off in detail.
- "mostly_false" (MOSTLY FALSE): core claim is wrong, but some surrounding context, numbers, or named entities are real. Classic shape: the person/event/study exists, but the described cause, outcome, or mechanism is wrong.
- "false" (FALSE): core claim is wrong and authoritative sources directly contradict it.
- "unverifiable" (CAN'T VERIFY): no specific testable claim (aesthetic/music/opinion/personal-experience), or no authoritative sources exist on the topic. Return confidence null and empty sources.

ANTI-HEDGING RULE (CRITICAL)
The "mostly_*" tiers are NOT a safe middle. If you are tempted to pick one because you are unsure, re-read the claim and decide: broadly right → "true"; broadly wrong → "false"; not a factual claim → "unverifiable". Only use "mostly_true" / "mostly_false" when the claim is genuinely half-right IN SUBSTANCE (not in wording). A prior version of this system returned the middle tier ~99% of the time; that is a failure mode.

WORKED EXAMPLES
- "Octopuses have three hearts, blue copper-based blood" → "true" (all substantive parts correct).
- "Einstein failed math as a student" → "mostly_false" (person is real; core claim wrong — grading-scale misread).
- "The Great Wall is the only man-made structure visible from space" → "mostly_true" (visible under ideal conditions: yes; only: no).
- "Celery juice cures autoimmune disease" → "false" (sources directly contradict).
- "I've never felt better since taking these supplements" → "unverifiable" (personal experience, no testable claim).

OUTPUT CONSTRAINTS
- Keep tldr under 40 words. Plain-language. No hedging phrases ("it's possible that").
- confidence is YOUR certainty in the verdict (0-100), not the claim's likelihood of being true. Only use null for unverifiable.
- Claim should be a plain-text restatement of what's being asserted, not a quote.

OUTPUT FORMAT
Respond with ONLY a valid JSON object (no prose, no code fences), exactly matching this schema:
{
  "verdict": "false" | "mostly_false" | "mostly_true" | "true" | "unverifiable",
  "label": "FALSE" | "MOSTLY FALSE" | "MOSTLY ACCURATE" | "ACCURATE" | "CAN'T VERIFY",
  "confidence": <integer 0-100, or null for unverifiable>,
  "claim": "<plain-text claim>",
  "tldr": "<under 40 words>",
  "sources": [{"title": "<title>", "url": "<url>", "domain": "<domain only>"}]
}
Mapping: false→FALSE, mostly_false→MOSTLY FALSE, mostly_true→MOSTLY ACCURATE, true→ACCURATE, unverifiable→CAN'T VERIFY.
"""


WEB_SEARCH_TOOL = {
    "type": "web_search_20250305",
    "name": "web_search",
    "max_uses": 5,
}


def _sniff_image_mime(raw: bytes) -> str:
    """Detect image MIME from magic bytes. Claude accepts jpeg/png/webp/gif."""
    if raw.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "image/webp"
    if raw[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    # Unknown — default to jpeg and let Claude tell us if it's wrong.
    return "image/jpeg"


def _image_block(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    mime = _sniff_image_mime(raw[:16])
    data = base64.standard_b64encode(raw).decode("utf-8")
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": mime, "data": data},
    }


def _extract_json(text: str) -> dict[str, Any]:
    """Parse JSON from model output, tolerating code fences and prose around it."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass
    # Fallback: extract first balanced {...} block
    start = text.find("{")
    if start == -1:
        raise ClaudeError("No JSON found in Claude response")
    depth = 0
    for i in range(start, len(text)):
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : i + 1])
                except json.JSONDecodeError as e:
                    raise ClaudeError(f"Malformed JSON in Claude response: {e}")
    raise ClaudeError("Unbalanced JSON in Claude response")


def run_claude(media: IGMedia, image_paths: list[Path], transcript: str | None) -> dict[str, Any]:
    if not ANTHROPIC_API_KEY:
        raise ClaudeError("ANTHROPIC_API_KEY not set")

    client = Anthropic(api_key=ANTHROPIC_API_KEY)

    kind_label = "Reel" if media.media_type == "video" else "Photo post"
    header = (
        f"Instagram {kind_label} from @{media.username}"
        f"{f' ({media.full_name})' if media.full_name else ''}"
    )
    caption_block = f"CAPTION:\n{media.caption or '(no caption)'}"
    transcript_block = (
        f"AUDIO TRANSCRIPT:\n{transcript}" if transcript else "AUDIO TRANSCRIPT: (none available)"
    )

    user_content: list[dict[str, Any]] = [
        {"type": "text", "text": f"{header}\n\n{caption_block}\n\n{transcript_block}"},
    ]
    for p in image_paths:
        user_content.append(_image_block(p))
    user_content.append({"type": "text", "text": "Return the JSON verdict now."})

    try:
        resp = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            tools=[WEB_SEARCH_TOOL],  # type: ignore[arg-type]
            messages=[{"role": "user", "content": user_content}],
        )
    except Exception as e:
        raise ClaudeError(f"Anthropic API call failed: {e}") from e

    text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
    if not text.strip():
        raise ClaudeError("Claude returned no text content")

    verdict = _extract_json(text)
    _validate_verdict(verdict)
    return verdict


def _validate_verdict(v: dict[str, Any]) -> None:
    required = {"verdict", "label", "confidence", "claim", "tldr", "sources"}
    missing = required - v.keys()
    if missing:
        raise ClaudeError(f"Verdict JSON missing keys: {missing}")
    if v["verdict"] not in ("false", "mostly_false", "mostly_true", "true", "unverifiable"):
        raise ClaudeError(f"Unknown verdict value: {v['verdict']}")
    if v["verdict"] == "unverifiable":
        v["confidence"] = None
    elif not isinstance(v["confidence"], int):
        try:
            v["confidence"] = int(v["confidence"])
        except (TypeError, ValueError):
            raise ClaudeError("confidence not convertible to int")
    # ensure sources is a list of dicts with domain
    clean_sources = []
    for s in v.get("sources") or []:
        if not isinstance(s, dict):
            continue
        title = str(s.get("title", "")).strip()
        url = str(s.get("url", "")).strip()
        domain = str(s.get("domain", "")).strip()
        if not domain and url:
            # derive domain if missing
            m = re.match(r"https?://([^/]+)", url)
            if m:
                domain = m.group(1).removeprefix("www.")
        if title and (url or domain):
            clean_sources.append({"title": title, "url": url, "domain": domain})
    v["sources"] = clean_sources


# ── Entry point used by main.py ─────────────────────────────────────────────
def run_pipeline(url: str, on_stage: StageCallback | None = None) -> dict[str, Any]:
    """IG URL → full verdict dict (matches template's expected context shape).

    Adds `author` and `kind` fields that the template uses for the chips row.
    Raises PipelineError subclasses on failure.

    Reel step indices (for on_stage):
        0 Fetching post data · 1 Extracting frames · 2 Transcribing audio
        3 Searching the web · 4 Cross-referencing sources · 5 Writing verdict

    Post step indices:
        0 Fetching post data · 1 Searching the web
        2 Cross-referencing sources · 3 Writing verdict
    """
    def stage(step: int, media_type: str | None = None) -> None:
        if on_stage is not None:
            try:
                on_stage(step, media_type)
            except Exception as e:  # pragma: no cover - never let stage cb break pipeline
                log.warning("on_stage callback failed: %s", e)

    stage(0)
    media = fetch_ig_metadata(url)
    stage(0, media.media_type)  # surface media_type so UI can switch to post-steps

    with tempfile.TemporaryDirectory() as tmpstr:
        tmp = Path(tmpstr)
        transcript: str | None = None

        if media.media_type == "video":
            stage(1)
            video_path = tmp / "video.mp4"
            _download(media.media_urls[0], video_path, MAX_VIDEO_BYTES)
            frame_paths, audio_path = extract_frames_and_audio(video_path, tmp)
            if audio_path:
                stage(2)
                transcript = transcribe(audio_path)
            claude_start = 3  # Searching the web
        elif media.media_type == "carousel":
            # Download each carousel item as-is; Claude accepts jpeg/png/webp.
            # _sniff_image_mime picks the right content-type when building
            # the image block, so no pre-conversion needed.
            frame_paths = []
            for i, img_url in enumerate(media.media_urls):
                p = tmp / f"carousel_{i}.img"
                _download(img_url, p, MAX_VIDEO_BYTES)
                frame_paths.append(p)
            claude_start = 1  # Posts/carousels: 0=fetch, 1=search, 2=cross-ref, 3=writing
        else:  # image
            img_path = tmp / "image.img"
            _download(media.media_urls[0], img_path, MAX_VIDEO_BYTES)
            frame_paths = [img_path]
            claude_start = 1  # Posts: 0=fetch, 1=search, 2=cross-ref, 3=writing

        # Claude call spans steps N, N+1, N+2. Real stage N; N+1 and N+2
        # advance via timers (Claude is a single API call we can't introspect).
        stage(claude_start)
        t1 = threading.Timer(5.0, stage, args=(claude_start + 1,))
        t2 = threading.Timer(10.0, stage, args=(claude_start + 2,))
        t1.daemon = True; t2.daemon = True
        t1.start(); t2.start()
        try:
            verdict = run_claude(media, frame_paths, transcript)
        finally:
            t1.cancel()
            t2.cancel()

    # Enrich with chip fields for the template
    verdict["author"] = f"@{media.username}" if media.username else ""
    if media.media_type == "video":
        duration = f" · {media.duration_seconds} sec" if media.duration_seconds else ""
        verdict["kind"] = f"Reel{duration}"
    elif media.media_type == "carousel":
        verdict["kind"] = f"Post · Carousel · {len(media.media_urls)} images"
    else:
        verdict["kind"] = "Post · Image"
    verdict["transcript_excerpt"] = transcript

    return verdict
