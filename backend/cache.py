"""Firestore-backed verdict cache. Keyed by IG shortcode, 7-day TTL.

Disabled automatically when GOOGLE_CLOUD_PROJECT is not set (local dev without
Firestore auth). Any Firestore error is swallowed — cache is an optimization,
not a dependency; on failure we fall through to the real pipeline.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any

log = logging.getLogger("fact_check.cache")

TTL_SECONDS = 7 * 24 * 3600
COLLECTION = "fact_check_cache"

# Circuit breaker: when IG rate-limits us, we stop calling IG entirely for
# this long. Retrying during the cooldown extends IG's flag on our IP —
# doing nothing shortens it. 30 min chosen as a middle ground between
# "user perception of 'broken'" and "IG's 'please wait a few minutes'".
RATE_LIMIT_COOLDOWN_SECONDS = 30 * 60
_RATE_LIMIT_DOC = "_ig_rate_limit"

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
        log.warning("google-cloud-firestore not installed; cache disabled")
        return None
    try:
        _client = firestore.Client(project=os.environ["GOOGLE_CLOUD_PROJECT"])
        return _client
    except Exception as e:
        log.warning("firestore init failed; cache disabled: %s", e)
        return None


def get(shortcode: str) -> dict[str, Any] | None:
    """Return cached verdict dict if fresh, else None."""
    db = _db()
    if db is None:
        return None
    try:
        snap = db.collection(COLLECTION).document(shortcode).get()
        if not snap.exists:
            return None
        data = snap.to_dict() or {}
        cached_at = data.get("cached_at", 0)
        if time.time() - cached_at > TTL_SECONDS:
            return None
        verdict = data.get("verdict")
        if isinstance(verdict, dict):
            log.info("cache HIT %s (age %ds)", shortcode, int(time.time() - cached_at))
            return verdict
        return None
    except Exception as e:
        log.warning("cache get failed for %s: %s", shortcode, e)
        return None


def put(shortcode: str, verdict: dict[str, Any]) -> None:
    """Write verdict with current timestamp. Silently no-ops if disabled/failing."""
    db = _db()
    if db is None:
        return
    try:
        db.collection(COLLECTION).document(shortcode).set({
            "verdict": verdict,
            "cached_at": time.time(),
        })
        log.info("cache PUT %s", shortcode)
    except Exception as e:
        log.warning("cache put failed for %s: %s", shortcode, e)


# ── IG rate-limit circuit breaker ───────────────────────────────────────────
def ig_cooldown_remaining() -> int:
    """Seconds left on IG's timeout, or 0 if we're free to call IG."""
    db = _db()
    if db is None:
        return 0
    try:
        snap = db.collection(COLLECTION).document(_RATE_LIMIT_DOC).get()
        if not snap.exists:
            return 0
        until = (snap.to_dict() or {}).get("until", 0)
        remaining = int(until - time.time())
        return remaining if remaining > 0 else 0
    except Exception as e:
        log.warning("cooldown read failed: %s", e)
        return 0


def mark_ig_rate_limited(cooldown_seconds: int = RATE_LIMIT_COOLDOWN_SECONDS) -> None:
    """Flip the circuit breaker. Subsequent calls to IG skipped for this long."""
    db = _db()
    if db is None:
        return
    try:
        db.collection(COLLECTION).document(_RATE_LIMIT_DOC).set({
            "until": time.time() + cooldown_seconds,
            "tripped_at": time.time(),
        })
        log.warning("IG rate-limit circuit breaker TRIPPED for %ds", cooldown_seconds)
    except Exception as e:
        log.warning("cooldown write failed: %s", e)
