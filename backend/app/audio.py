"""MP3 byte-level concatenation.

All Grok TTS outputs are MP3 at 44.1 kHz, so naive frame-level concatenation
produces a playable file in every mainstream player. This is intentionally
dependency-free to avoid requiring FFmpeg in the MVP runtime.
"""
from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path


def concat_bytes_to_file(chunks: Iterable[bytes], dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as f:
        for chunk in chunks:
            f.write(chunk)
    return dest


def concat_files(sources: list[Path], dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as out:
        for src in sources:
            with src.open("rb") as f:
                while True:
                    buf = f.read(1024 * 1024)
                    if not buf:
                        break
                    out.write(buf)
    return dest
