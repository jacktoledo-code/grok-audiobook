"""EPUB parser using ebooklib + BeautifulSoup."""
from __future__ import annotations

import io
import logging
import tempfile
from pathlib import Path

from bs4 import BeautifulSoup
from ebooklib import ITEM_DOCUMENT, epub

from ..models import Book, Chapter

log = logging.getLogger(__name__)


def _item_title(item: epub.EpubItem, soup: BeautifulSoup, fallback: str) -> str:
    for tag in ("h1", "h2", "h3"):
        node = soup.find(tag)
        if node:
            text = node.get_text(" ", strip=True)
            if text:
                return text
    title = getattr(item, "title", "") or ""
    return title.strip() or fallback


def _meta_first(book: epub.EpubBook, namespace: str, name: str) -> str:
    values = book.get_metadata(namespace, name)
    if not values:
        return ""
    first = values[0]
    if isinstance(first, tuple) and first:
        return str(first[0] or "").strip()
    return str(first).strip()


def parse_epub(data: bytes, *, filename: str = "book.epub") -> Book:
    # ebooklib.read_epub requires a filesystem path.
    with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)

    try:
        book = epub.read_epub(str(tmp_path))
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass

    title = _meta_first(book, "DC", "title") or Path(filename).stem
    author = _meta_first(book, "DC", "creator")

    chapters: list[Chapter] = []
    for idx, item in enumerate(book.get_items_of_type(ITEM_DOCUMENT), start=1):
        try:
            raw = item.get_body_content() or item.get_content()
        except Exception:  # noqa: BLE001
            raw = item.get_content()
        if not raw:
            continue
        soup = BeautifulSoup(raw, "lxml")
        # Drop navigation / script / style noise.
        for bad in soup(["script", "style", "nav"]):
            bad.decompose()
        text = soup.get_text("\n", strip=True)
        if not text or len(text) < 30:
            continue
        ch_title = _item_title(item, soup, fallback=f"Chapter {idx}")
        chapters.append(Chapter(title=ch_title, text=text))

    if not chapters:
        # Fallback: some EPUBs ship everything in one doc.
        log.warning("No chapters extracted from %s; returning empty book", filename)
    return Book(title=title, author=author, chapters=chapters)


# Silence a pydocstyle-ish concern about io import retention for readers.
_ = io
