"""Smart text splitting for the Grok TTS 15k-char request limit.

Preference order: paragraph (\n\n) > sentence (. ! ? …) > word boundary > hard slice.
Balanced speech-tag spans like <whisper>…</whisper> are kept atomic when possible.
"""
from __future__ import annotations

import re

from .config import MAX_TTS_CHARS

_SENT_SPLIT_RE = re.compile(r"(?<=[.!?…])\s+")
_PARA_SPLIT_RE = re.compile(r"\n\s*\n")
# Balanced XML-ish tags: <whisper>...</whisper>, <emphasis>...</emphasis>, etc.
_TAG_SPAN_RE = re.compile(r"<([a-zA-Z][\w-]*)\b[^>]*>.*?</\1>", re.DOTALL)


def _protect_tag_spans(text: str) -> tuple[str, list[str]]:
    """Replace balanced tag spans with placeholders so we never split them."""
    spans: list[str] = []

    def _sub(match: re.Match[str]) -> str:
        spans.append(match.group(0))
        return f"\x00TAG{len(spans) - 1}\x00"

    protected = _TAG_SPAN_RE.sub(_sub, text)
    return protected, spans


def _restore_tag_spans(chunks: list[str], spans: list[str]) -> list[str]:
    if not spans:
        return chunks
    restored: list[str] = []
    for chunk in chunks:
        for i, span in enumerate(spans):
            chunk = chunk.replace(f"\x00TAG{i}\x00", span)
        restored.append(chunk)
    return restored


def _split_by(text: str, sep_pattern: re.Pattern[str]) -> list[str]:
    return [p for p in sep_pattern.split(text) if p.strip()]


def _pack(parts: list[str], joiner: str, max_chars: int) -> list[str]:
    """Greedily pack parts into chunks ≤ max_chars, joined by `joiner`."""
    chunks: list[str] = []
    buf = ""
    for part in parts:
        candidate = f"{buf}{joiner}{part}" if buf else part
        if len(candidate) <= max_chars:
            buf = candidate
        else:
            if buf:
                chunks.append(buf)
            buf = part
    if buf:
        chunks.append(buf)
    return chunks


def _hard_slice(text: str, max_chars: int) -> list[str]:
    """Final-resort slice on word boundary, falling back to raw cut."""
    chunks: list[str] = []
    remaining = text
    while len(remaining) > max_chars:
        cut = remaining.rfind(" ", 0, max_chars)
        if cut <= 0:
            cut = max_chars
        chunks.append(remaining[:cut].rstrip())
        remaining = remaining[cut:].lstrip()
    if remaining:
        chunks.append(remaining)
    return chunks


def split_text(text: str, max_chars: int = MAX_TTS_CHARS) -> list[str]:
    """Split `text` into TTS-friendly chunks ≤ max_chars."""
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    protected, spans = _protect_tag_spans(text)

    paragraphs = _split_by(protected, _PARA_SPLIT_RE)

    chunks: list[str] = []
    for para in paragraphs:
        if len(para) <= max_chars:
            chunks.append(para)
            continue
        sentences = _split_by(para, _SENT_SPLIT_RE)
        if sentences and all(len(s) <= max_chars for s in sentences):
            chunks.extend(_pack(sentences, " ", max_chars))
        else:
            for sent in sentences or [para]:
                if len(sent) <= max_chars:
                    chunks.append(sent)
                else:
                    chunks.extend(_hard_slice(sent, max_chars))

    # Merge adjacent small chunks back up to max_chars (paragraph-joined).
    packed = _pack(chunks, "\n\n", max_chars)
    return _restore_tag_spans(packed, spans)


def count_chars(text: str) -> int:
    """Character count used for cost estimation (raw length — Grok bills raw)."""
    return len(text)


def estimate_cost_usd(total_chars: int, rate_per_million: float = 4.20) -> float:
    return round(total_chars / 1_000_000 * rate_per_million, 4)
