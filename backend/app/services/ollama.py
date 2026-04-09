"""Reusable async client for Ollama (local LLM) with Redis caching."""

import hashlib
import json
import logging

import httpx
import redis

from app.config import get_settings

logger = logging.getLogger(__name__)

# Lazy Redis connection
_redis: redis.Redis | None = None


def _get_redis() -> redis.Redis | None:
    global _redis
    if _redis is None:
        try:
            settings = get_settings()
            _redis = redis.from_url(settings.redis_url, decode_responses=True)
            _redis.ping()
        except Exception:
            logger.info("Redis not available for LLM cache")
            _redis = None
    return _redis


def _cache_key(prompt: str, system: str | None) -> str:
    settings = get_settings()
    raw = json.dumps({"model": settings.ollama_model, "system": system, "prompt": prompt}, sort_keys=True)
    return f"ollama:{hashlib.sha256(raw.encode()).hexdigest()[:16]}"


CACHE_TTL = 60 * 60 * 24 * 7  # 7 days


async def ollama_generate(
    prompt: str,
    system: str | None = None,
) -> str | None:
    """Call Ollama generate API with Redis caching. Returns text or None on failure."""
    settings = get_settings()
    cache_k = _cache_key(prompt, system)

    # Check cache first
    r = _get_redis()
    if r:
        try:
            cached = r.get(cache_k)
            if cached:
                logger.debug("Ollama cache hit: %s", cache_k)
                return cached
        except Exception:
            pass

    # If LLM is disabled (cache-only mode), don't make a live call.
    # Callers handle None by falling back to rule-based output.
    if not settings.llm_enabled:
        logger.debug("LLM disabled; returning None for cache miss")
        return None

    # Call Ollama
    url = f"{settings.ollama_url}/api/generate"
    body: dict = {
        "model": settings.ollama_model,
        "prompt": prompt,
        "stream": False,
    }
    if system:
        body["system"] = system

    logger.info("Ollama prompt:\n%s", prompt)

    timeout = httpx.Timeout(settings.ollama_timeout, connect=3.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=body)
            resp.raise_for_status()
            data = resp.json()
            text = data.get("response", "").strip()
            if not text:
                logger.warning("Ollama returned empty response")
                return None

            # Cache the result
            if r:
                try:
                    r.setex(cache_k, CACHE_TTL, text)
                except Exception:
                    pass

            return text
    except httpx.ConnectError:
        logger.info("Ollama not reachable at %s", settings.ollama_url)
        return None
    except httpx.TimeoutException:
        logger.warning("Ollama request timed out after %ds", settings.ollama_timeout)
        return None
    except Exception:
        logger.warning("Ollama request failed", exc_info=True)
        return None
