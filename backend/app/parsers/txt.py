"""Structured TXT parser.

Expected (optional) layout::

    Title: The Book
    Author: Some Person

    # Capítulo 1
    ...
    # Capítulo 2
    ...

Without `Title:` / `Author:` or `# ` markers, the whole file becomes a single
chapter titled after the filename.
"""
from __future__ import annotations

import re
from pathlib import Path

from ..models import Book, Chapter

_HEADER_RE = re.compile(r"^(Title|Author)\s*:\s*(.+?)\s*$", re.IGNORECASE)
_CHAPTER_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)


def _strip_headers(text: str) -> tuple[str, str, str]:
    title = ""
    author = ""
    lines = text.splitlines()
    body_start = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            if title or author:
                body_start = i + 1
                break
            continue
        m = _HEADER_RE.match(stripped)
        if not m:
            break
        key = m.group(1).lower()
        value = m.group(2)
        if key == "title":
            title = value
        elif key == "author":
            author = value
        body_start = i + 1
    return title, author, "\n".join(lines[body_start:]).lstrip("\n")


def parse_txt(text: str, *, filename: str = "book.txt") -> Book:
    title, author, body = _strip_headers(text)
    if not title:
        title = Path(filename).stem

    markers = list(_CHAPTER_RE.finditer(body))
    chapters: list[Chapter] = []
    if not markers:
        chapters.append(Chapter(title=title, text=body.strip()))
    else:
        for i, m in enumerate(markers):
            start = m.end()
            end = markers[i + 1].start() if i + 1 < len(markers) else len(body)
            chap_text = body[start:end].strip()
            if not chap_text:
                continue
            chapters.append(Chapter(title=m.group(1).strip(), text=chap_text))
        # Preserve any preamble text before the first marker as its own chapter.
        preamble = body[: markers[0].start()].strip()
        if preamble:
            chapters.insert(0, Chapter(title="Introdução", text=preamble))

    return Book(title=title, author=author, chapters=chapters)
