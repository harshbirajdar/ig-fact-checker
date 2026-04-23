"""Fact Check backend — FastAPI app rendering the single Jinja2 verdict template."""
from __future__ import annotations

import logging
import math
import os
import threading
import uuid
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv
from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

load_dotenv(Path(__file__).parent / ".env")

import cache  # noqa: E402
import jobs  # noqa: E402
from pipeline import PipelineError, extract_shortcode, run_pipeline  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("fact_check.app")

app = FastAPI(title="Fact Check")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

VERDICT_WORDS: dict[str, str] = {
    "false": "False",
    "mostly_false": "Mostly false",
    "mostly_true": "Mostly accurate",
    "true": "Accurate",
    "unverifiable": "Can't verify",
}

VERDICT_TONES: dict[str, str] = {
    "false": "false",
    "mostly_false": "mostly_false",
    "mostly_true": "mostly_accurate",
    "true": "accurate",
    "unverifiable": "unverified",
}

ERROR_COPY: dict[str, str] = {
    "private_or_deleted": "The post might be from a private account, deleted, or temporarily unreachable.",
    "rate_limited": "Instagram is rate-limiting us. Please try again in a few minutes.",
    "timeout": "Took too long. Try again in a moment.",
    "backend_error": "Something went wrong on our end.",
}

# Ring geometry (size=28, stroke=3)
_RING_R = (28 - 3) / 2
_RING_C = 2 * math.pi * _RING_R


def _ring_offset(confidence: int | None) -> float:
    if confidence is None:
        return _RING_C
    return _RING_C - (max(0, min(100, confidence)) / 100) * _RING_C


def _verdict_context(data: dict[str, Any]) -> dict[str, Any]:
    confidence = data.get("confidence")
    return {
        "screen_type": "verdict",
        "verdict": data["verdict"],
        "tone": VERDICT_TONES[data["verdict"]],
        "verdict_word": VERDICT_WORDS[data["verdict"]],
        "confidence": confidence,
        "claim": data["claim"],
        "tldr": data["tldr"],
        "transcript_excerpt": data.get("transcript_excerpt"),
        "sources": data.get("sources") or [],
        "author": data.get("author", ""),
        "kind": data.get("kind", ""),
        "ring_c": _RING_C,
        "ring_offset": _ring_offset(confidence),
    }


def _error_response(request: Request, error_reason: str) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "verdict.html",
        {"screen_type": "error", "error_copy": ERROR_COPY.get(error_reason, ERROR_COPY["backend_error"])},
        status_code=200,
    )


def _pipeline_worker(job_id: str, url: str, shortcode: str) -> None:
    """Runs the full pipeline in a background thread and updates Firestore."""
    def on_stage(step: int, media_type: str | None = None) -> None:
        jobs.update_stage(job_id, step, media_type)

    try:
        verdict = run_pipeline(url, on_stage=on_stage)
        # Grep-friendly distribution log: `gcloud logs ... | grep verdict_out`
        log.info("verdict_out verdict=%s confidence=%s shortcode=%s",
                 verdict.get("verdict"), verdict.get("confidence"), shortcode)
        cache.put(shortcode, verdict)
        jobs.mark_complete(job_id, verdict)
    except PipelineError as e:
        log.warning("pipeline failed (%s): %s", e.error_reason, e)
        jobs.mark_error(job_id, e.error_reason,
                        ERROR_COPY.get(e.error_reason, ERROR_COPY["backend_error"]))
    except Exception as e:  # noqa: BLE001
        log.exception("pipeline unexpected error: %s", e)
        jobs.mark_error(job_id, "backend_error", ERROR_COPY["backend_error"])


@app.get("/check", response_class=HTMLResponse)
async def check_get(url: str = Query(..., description="Instagram post/reel URL"),
                    request: Request = None) -> HTMLResponse:  # type: ignore[assignment]
    """Start an async fact-check. Returns the processing screen immediately;
    client-side JS polls /status/{job_id} until the verdict or error is ready.

    Cache hits bypass the job flow and render the verdict directly.
    """
    try:
        shortcode = extract_shortcode(url)
    except PipelineError as e:
        log.warning("invalid IG URL: %s", e)
        return _error_response(request, e.error_reason)

    cached = cache.get(shortcode)
    # Skip legacy cache entries from the 4-bucket era so they re-check under the
    # new 5-bucket prompt (PRD §5.5). Old "misleading" verdicts are the hedging
    # artifact we're trying to escape; re-running is correct behavior.
    if cached is not None and cached.get("verdict") in VERDICT_WORDS:
        return templates.TemplateResponse(request, "verdict.html", _verdict_context(cached))

    job_id = uuid.uuid4().hex[:12]
    jobs.create(job_id, url, shortcode)
    threading.Thread(
        target=_pipeline_worker,
        args=(job_id, url, shortcode),
        daemon=True,
    ).start()

    return templates.TemplateResponse(request, "verdict.html", {
        "screen_type": "processing",
        "media_type": "reel",
        "active_step": 0,
        "job_id": job_id,
    })


@app.get("/status/{job_id}")
async def status(job_id: str) -> JSONResponse:
    job = jobs.get(job_id)
    if not job:
        err_html = templates.get_template("verdict.html").render({
            "screen_type": "error",
            "error_copy": ERROR_COPY["backend_error"],
        })
        return JSONResponse({"status": "error", "html": err_html})

    if job["status"] == "complete":
        html = templates.get_template("verdict.html").render(_verdict_context(job["verdict"]))
        return JSONResponse({"status": "complete", "html": html})

    if job["status"] == "error":
        err_html = templates.get_template("verdict.html").render({
            "screen_type": "error",
            "error_copy": job.get("error_copy", ERROR_COPY["backend_error"]),
        })
        return JSONResponse({"status": "error", "html": err_html})

    return JSONResponse({
        "status": "processing",
        "active_step": job.get("active_step", 0),
        "media_type": job.get("media_type", "reel"),
    })


# ── Preview endpoints (design iteration / QA) ───────────────────────────────
_PreviewState = Literal[
    "processing_reel", "processing_post",
    "false", "mostly_false", "mostly_accurate", "accurate", "unverifiable",
    "error_private", "error_timeout", "error_backend",
]

_VERDICT_SAMPLES: dict[str, dict[str, Any]] = {
    "false": {
        "verdict": "false", "label": "FALSE", "confidence": 94,
        "claim": 'Drinking celery juice on an empty stomach cures autoimmune diseases by flushing "viral toxins" from the liver.',
        "tldr": "No peer-reviewed evidence supports celery juice curing any autoimmune condition. The \"viral toxins\" framing originates from a single non-medical author and is rejected by rheumatology and hepatology bodies.",
        "transcript_excerpt": "\"...and within two weeks of sixteen ounces of celery juice every single morning, my Hashimoto's was completely gone. Doctors don't want you to know this.\"",
        "author": "@wellness.daily", "kind": "Reel · 28 sec",
        "sources": [
            {"title": "Celery Juice: What the Evidence Says", "url": "https://mayoclinic.org", "domain": "mayoclinic.org"},
            {"title": "Detox Diets: Do They Work?", "url": "https://nih.gov", "domain": "nih.gov"},
            {"title": "Autoimmune Disease Management Guidelines", "url": "https://rheumatology.org", "domain": "rheumatology.org"},
            {"title": "Fact Check: Celery Juice Miracle Claims", "url": "https://healthfeedback.org", "domain": "healthfeedback.org"},
            {"title": "The Medical Medium Phenomenon", "url": "https://theatlantic.com", "domain": "theatlantic.com"},
        ],
    },
    "mostly_false": {
        "verdict": "mostly_false", "label": "MOSTLY FALSE", "confidence": 81,
        "claim": "Einstein failed math as a student before becoming a physicist.",
        "tldr": "Largely false. Einstein mastered calculus by age 15 and consistently excelled in mathematics. The myth stems from a misread Swiss grading scale where 6, not 1, was the highest mark. He did fail a single entrance exam in non-math subjects.",
        "transcript_excerpt": "\"Einstein literally failed math class — so next time someone tells you you're bad at math, remember that.\"",
        "author": "@big.brain.energy", "kind": "Reel · 18 sec",
        "sources": [
            {"title": "Einstein Myths: Did He Fail Math?", "url": "https://snopes.com", "domain": "snopes.com"},
            {"title": "Einstein Archives — Academic Record", "url": "https://albert-einstein.org", "domain": "albert-einstein.org"},
            {"title": "The Grading Scale Confusion", "url": "https://scientificamerican.com", "domain": "scientificamerican.com"},
            {"title": "Einstein: His Life and Universe", "url": "https://princeton.edu", "domain": "princeton.edu"},
        ],
    },
    "mostly_accurate": {
        "verdict": "mostly_true", "label": "MOSTLY ACCURATE", "confidence": 88,
        "claim": "The Great Wall of China is visible from space.",
        "tldr": "Mostly true with caveats. From low-Earth orbit the Wall is faintly visible under ideal lighting, alongside highways and cities. From the Moon, no man-made structure is visible — the common \"only\" framing is the part that doesn't hold.",
        "transcript_excerpt": None,
        "author": "@history.unfiltered", "kind": "Post · Image",
        "sources": [
            {"title": "Is the Great Wall Visible from Space?", "url": "https://nasa.gov", "domain": "nasa.gov"},
            {"title": "Chinese Astronaut Yang Liwei Comments", "url": "https://scientificamerican.com", "domain": "scientificamerican.com"},
            {"title": "Myths About Space Observation", "url": "https://esa.int", "domain": "esa.int"},
        ],
    },
    "accurate": {
        "verdict": "true", "label": "ACCURATE", "confidence": 97,
        "claim": "Octopuses have three hearts and blue, copper-based blood.",
        "tldr": "Confirmed. Octopuses possess two branchial hearts and one systemic heart, and their blood contains hemocyanin — a copper-based respiratory pigment that appears blue when oxygenated.",
        "transcript_excerpt": "\"Octopuses have three hearts — two pump blood through the gills, one pumps it through the rest of the body. Their blood is blue because it uses copper instead of iron.\"",
        "author": "@deep.sea.daily", "kind": "Reel · 14 sec",
        "sources": [
            {"title": "Cephalopod Circulatory Biology", "url": "https://nationalgeographic.com", "domain": "nationalgeographic.com"},
            {"title": "Hemocyanin in Marine Invertebrates", "url": "https://nih.gov", "domain": "nih.gov"},
            {"title": "Octopus Physiology Overview", "url": "https://mbari.org", "domain": "mbari.org"},
        ],
    },
    "unverifiable": {
        "verdict": "unverifiable", "label": "CAN'T VERIFY", "confidence": None,
        "claim": "A specific personal health outcome attributed to an unnamed supplement regimen.",
        "tldr": "No specific, testable claim was made. The reel describes a subjective personal experience without naming products, dosages, or measurable outcomes.",
        "transcript_excerpt": "\"I started taking these three things every morning and I've never felt better in my life, honestly you guys have to try it.\"",
        "author": "@morning.rituals", "kind": "Reel · 45 sec",
        "sources": [],
    },
}


@app.get("/preview/{state}", response_class=HTMLResponse)
async def preview(state: _PreviewState, request: Request) -> HTMLResponse:
    if state.startswith("processing_"):
        return templates.TemplateResponse(request, "verdict.html", {
            "screen_type": "processing",
            "media_type": "reel" if state == "processing_reel" else "post",
            "active_step": 2 if state == "processing_reel" else 1,
        })
    if state.startswith("error_"):
        key = {"error_private": "private_or_deleted", "error_timeout": "timeout", "error_backend": "backend_error"}[state]
        return _error_response(request, key)
    return templates.TemplateResponse(request, "verdict.html", _verdict_context(_VERDICT_SAMPLES[state]))
