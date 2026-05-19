"""Markdown → plain text, then dispatch to the TXT parser.

Level-1 `# Heading` markers are preserved (the TXT parser uses them as
chapter anchors). Deeper headings (`##`, `###`, …) become plain text lines.
Balanced HTML/XML tags (speech tags like `<whisper>…</whisper>`) are left
alone so the chunker can keep them atomic.
"""
from __future__ import annotations

import re

from ..models import Book
from .txt import parse_txt

_FENCE_RE = re.compile(r"```[\w-]*\n.*?```", re.DOTALL)
_IMG_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_AUTOLINK_RE = re.compile(r"<(?:https?://|mailto:)[^>]+>")
_INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")
_BOLD_RE = re.compile(r"(\*\*|__)(.+?)\1", re.DOTALL)
_ITAL_RE = re.compile(r"(?<!\w)([*_])([^*_\s][^*_]*?)\1(?!\w)")
_STRIKE_RE = re.compile(r"~~(.+?)~~")
_HR_RE = re.compile(r"^\s*([-*_])\1{2,}\s*$", re.MULTILINE)
_BQ_RE = re.compile(r"^\s*>\s?", re.MULTILINE)
_UL_RE = re.compile(r"^\s*[-*+]\s+", re.MULTILINE)
_OL_RE = re.compile(r"^\s*\d+\.\s+", re.MULTILINE)
_DEEP_HEADING_RE = re.compile(r"^#{2,6}\s+", re.MULTILINE)
_BLANKS_RE = re.compile(r"\n{3,}")


def markdown_to_plain(text: str) -> str:
    text = _FENCE_RE.sub("", text)
    text = _IMG_RE.sub("", text)
    text = _LINK_RE.sub(r"\1", text)
    text = _AUTOLINK_RE.sub("", text)
    text = _INLINE_CODE_RE.sub(r"\1", text)
    text = _STRIKE_RE.sub(r"\1", text)
    text = _BOLD_RE.sub(r"\2", text)
    text = _ITAL_RE.sub(r"\2", text)
    text = _HR_RE.sub("", text)
    text = _BQ_RE.sub("", text)
    text = _UL_RE.sub("", text)
    text = _OL_RE.sub("", text)
    text = _DEEP_HEADING_RE.sub("", text)
    text = _BLANKS_RE.sub("\n\n", text)
    return text.strip()


def parse_md(text: str, *, filename: str = "book.md") -> Book:
    return parse_txt(markdown_to_plain(text), filename=filename)
