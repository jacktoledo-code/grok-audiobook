"""Async client for the xAI Grok TTS API."""
from __future__ import annotations

import asyncio
import logging

import httpx

from .config import settings

log = logging.getLogger(__name__)

RETRY_STATUSES = {429, 500, 502, 503, 504}


class TTSError(RuntimeError):
    pass


async def synthesize(
    text: str,
    *,
    voice_id: str,
    language: str,
    client: httpx.AsyncClient,
    max_retries: int = 3,
) -> bytes:
    """POST to Grok TTS and return MP3 bytes.

    Retries with exponential backoff on 429/5xx and transient network errors.
    """
    if not settings.xai_api_key:
        raise TTSError("XAI_API_KEY is not configured.")

    payload = {
        "text": text,
        "voice_id": voice_id,
        "language": language,
        "format": "mp3",
    }
    headers = {
        "Authorization": f"Bearer {settings.xai_api_key}",
        "Content-Type": "application/json",
    }

    delay = 1.0
    last_err: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = await client.post(
                settings.grok_tts_url, json=payload, headers=headers
            )
        except (httpx.TransportError, httpx.TimeoutException) as exc:
            last_err = exc
            log.warning("TTS transport error (attempt %d): %s", attempt, exc)
            if attempt == max_retries:
                break
            await asyncio.sleep(delay)
            delay *= 2
            continue

        if resp.status_code == 200:
            return resp.content
        if resp.status_code in RETRY_STATUSES and attempt < max_retries:
            log.warning(
                "TTS retriable status %d (attempt %d/%d)",
                resp.status_code,
                attempt,
                max_retries,
            )
            await asyncio.sleep(delay)
            delay *= 2
            continue

        body = resp.text[:500]
        raise TTSError(f"Grok TTS returned {resp.status_code}: {body}")

    raise TTSError(f"Grok TTS failed after {max_retries} attempts: {last_err}")
