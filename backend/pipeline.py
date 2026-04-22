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


@dataclass
class IGMedia:
    shortcode: str
    media_type: Literal["image", "video"]
    caption: str
    username: str
    full_name: str
    duration_seconds: int | None
    media_url: str  # video MP4 or image URL


# ── IG fetch + metadata parse ───────────────────────────────────────────────
def extract_shortcode(url: str) -> str:
    m = SHORTCODE_RE.search(url)
    if not m:
        raise IGFetchError(f"Not a valid Instagram post/reel URL: {url}")
    return m.group(1)


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


def fetch_ig_metadata(url: str) -> IGMedia:
    """Fetch the IG page anonymously and extract structured metadata."""
    shortcode = extract_shortcode(url)
    canonical = f"https://www.instagram.com/p/{shortcode}/"

    try:
        with httpx.Client(timeout=15, follow_redirects=True) as client:
            resp = client.get(canonical, headers={
                "User-Agent": BROWSER_UA,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9",
                "Accept-Language": "en-US,en;q=0.5",
            })
    except httpx.RequestError as e:
        raise IGFetchError(f"Network error fetching IG: {e}") from e

    if resp.status_code != 200:
        raise IGFetchError(f"IG returned HTTP {resp.status_code}")

    html = resp.text
    if shortcode not in html:
        # Private accounts / deleted posts typically don't include the shortcode in JSON
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
        raise IGFetchError("Could not locate media metadata in IG page")

    media_type_code = media.get("media_type")
    if media_type_code == 1:
        media_type: Literal["image", "video"] = "image"
        versions = media.get("image_versions2", {}).get("candidates", [])
        if not versions:
            raise MediaExtractionError("No image versions found")
        media_url = versions[0]["url"]
    elif media_type_code == 2:
        media_type = "video"
        versions = media.get("video_versions") or []
        if not versions:
            raise MediaExtractionError("No video versions found")
        media_url = versions[0]["url"]
    else:
        # media_type 8 = carousel; not supported in v1
        raise MediaExtractionError(f"Unsupported media_type: {media_type_code}")

    caption_obj = media.get("caption") or {}
    user_obj = media.get("user") or {}

    return IGMedia(
        shortcode=shortcode,
        media_type=media_type,
        caption=(caption_obj.get("text") or "").strip(),
        username=user_obj.get("username") or "",
        full_name=user_obj.get("full_name") or "",
        duration_seconds=int(media["video_duration"]) if media.get("video_duration") else None,
        media_url=media_url,
    )


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


def _image_block(path: Path) -> dict[str, Any]:
    data = base64.standard_b64encode(path.read_bytes()).decode("utf-8")
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": "image/jpeg", "data": data},
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
            _download(media.media_url, video_path, MAX_VIDEO_BYTES)
            frame_paths, audio_path = extract_frames_and_audio(video_path, tmp)
            if audio_path:
                stage(2)
                transcript = transcribe(audio_path)
            claude_start = 3  # Searching the web
        else:
            img_path = tmp / "image.jpg"
            _download(media.media_url, img_path, MAX_VIDEO_BYTES)
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
    else:
        verdict["kind"] = "Post · Image"
    verdict["transcript_excerpt"] = transcript

    return verdict
