"""Firestore-backed job state for the async fact-check pipeline.

Each job tracks: status (processing/complete/error), active_step, media_type,
and the final verdict or error reason. TTL handled via cleanup job or manual
inspection (Firestore doesn't auto-delete; fine for our scale).

Fail-open: if Firestore is unavailable, functions silently no-op and return
None so the service still works (though async polling won't).
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any

log = logging.getLogger("fact_check.jobs")

COLLECTION = "fact_check_jobs"
JOB_TTL_SECONDS = 600  # 10 min; older jobs return None from get()

_client = None


def _enabled() -> bool:
    return bool(os.environ.get("GOOGLE_CLOUD_PROJECT"))


def _db():
    global _client
    if _client is not None:
        return _client
    if not _enabled():
        return None
    try:
        from google.cloud import firestore  # type: ignore[import-not-found]
    except ImportError:
        log.warning("google-cloud-firestore not installed; jobs disabled")
        return None
    try:
        _client = firestore.Client(project=os.environ["GOOGLE_CLOUD_PROJECT"])
        return _client
    except Exception as e:
        log.warning("firestore init failed; jobs disabled: %s", e)
        return None


def create(job_id: str, url: str, shortcode: str) -> None:
    db = _db()
    if db is None:
        return
    try:
        db.collection(COLLECTION).document(job_id).set({
            "status": "processing",
            "url": url,
            "shortcode": shortcode,
            "active_step": 0,
            "media_type": "reel",  # optimistic default until pipeline reports
            "created_at": time.time(),
        })
    except Exception as e:
        log.warning("jobs.create failed for %s: %s", job_id, e)


def update_stage(job_id: str, step: int, media_type: str | None = None) -> None:
    db = _db()
    if db is None:
        return
    try:
        updates: dict[str, Any] = {"active_step": step}
        if media_type in ("reel", "post", "video", "image"):
            # pipeline uses "video"/"image"; template uses "reel"/"post"
            updates["media_type"] = "reel" if media_type in ("reel", "video") else "post"
        db.collection(COLLECTION).document(job_id).update(updates)
    except Exception as e:
        log.warning("jobs.update_stage failed for %s: %s", job_id, e)


def mark_complete(job_id: str, verdict: dict[str, Any]) -> None:
    db = _db()
    if db is None:
        return
    try:
        db.collection(COLLECTION).document(job_id).update({
            "status": "complete",
            "verdict": verdict,
            "completed_at": time.time(),
        })
    except Exception as e:
        log.warning("jobs.mark_complete failed for %s: %s", job_id, e)


def mark_error(job_id: str, error_reason: str, error_copy: str) -> None:
    db = _db()
    if db is None:
        return
    try:
        db.collection(COLLECTION).document(job_id).update({
            "status": "error",
            "error_reason": error_reason,
            "error_copy": error_copy,
            "completed_at": time.time(),
        })
    except Exception as e:
        log.warning("jobs.mark_error failed for %s: %s", job_id, e)


def get(job_id: str) -> dict[str, Any] | None:
    db = _db()
    if db is None:
        return None
    try:
        snap = db.collection(COLLECTION).document(job_id).get()
        if not snap.exists:
            return None
        data = snap.to_dict() or {}
        created = data.get("created_at", 0)
        if time.time() - created > JOB_TTL_SECONDS and data.get("status") == "processing":
            # Stale processing job (crashed?); treat as error
            return {
                "status": "error",
                "error_reason": "timeout",
                "error_copy": "Took too long. Try again in a moment.",
            }
        return data
    except Exception as e:
        log.warning("jobs.get failed for %s: %s", job_id, e)
        return None
