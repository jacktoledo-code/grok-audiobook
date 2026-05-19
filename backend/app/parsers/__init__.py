from __future__ import annotations

from pathlib import Path

from ..models import Book
from .epub import parse_epub
from .md import parse_md
from .txt import parse_txt


class UnsupportedFormatError(ValueError):
    pass


def parse_book(data: bytes, filename: str) -> Book:
    name = filename.lower()
    if name.endswith(".txt"):
        return parse_txt(data.decode("utf-8", errors="replace"), filename=filename)
    if name.endswith((".md", ".markdown")):
        return parse_md(data.decode("utf-8", errors="replace"), filename=filename)
    if name.endswith(".epub"):
        return parse_epub(data, filename=filename)
    raise UnsupportedFormatError(
        f"Unsupported file type: {Path(filename).suffix or '(none)'}"
    )


__all__ = [
    "UnsupportedFormatError",
    "parse_book",
    "parse_epub",
    "parse_md",
    "parse_txt",
]
