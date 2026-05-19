"""In-memory job store + async background runner for audiobook generation."""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from .audio import concat_bytes_to_file, concat_files
from .chunk import estimate_cost_usd, split_text
from .config import COST_PER_MILLION_CHARS, settings
from .models import Book, GenerateOptions, JobStatus

log = logging.getLogger(__name__)


@dataclass
class JobState:
    job_id: str
    status: str = "queued"
    progress_pct: float = 0.0
    current_chapter: str | None = None
    chapters_total: int = 0
    chapters_done: int = 0
    chars_total: int = 0
    chars_done: int = 0
    est_cost_usd: float = 0.0
    cost_so_far_usd: float = 0.0
    started_at: float | None = None
    log: list[str] = field(default_factory=list)
    error: str | None = None
    output_path: Path | None = None
    chapter_paths: list[Path] = field(default_factory=list)

    def to_status(self) -> JobStatus:
        eta: float | None = None
        if self.started_at and 0 < self.progress_pct < 100:
            elapsed = time.time() - self.started_at
            eta = max(elapsed * (100 - self.progress_pct) / self.progress_pct, 0)
        return JobStatus(
            job_id=self.job_id,
            status=self.status,  # type: ignore[arg-type]
            progress_pct=round(self.progress_pct, 1),
            current_chapter=self.current_chapter,
            chapters_total=self.chapters_total,
            chapters_done=self.chapters_done,
            chars_total=self.chars_total,
            chars_done=self.chars_done,
            est_cost_usd=self.est_cost_usd,
            cost_so_far_usd=round(self.cost_so_far_usd, 4),
            eta_seconds=round(eta, 1) if eta is not None else None,
            log=list(self.log[-100:]),
            error=self.error,
        )


JOBS: dict[str, JobState] = {}
_LOCK = asyncio.Lock()


async def create_job(book: Book) -> JobState:
    async with _LOCK:
        job_id = uuid.uuid4().hex[:12]
        state = JobState(
            job_id=job_id,
            chapters_total=len(book.chapters),
            chars_total=book.total_chars,
            est_cost_usd=estimate_cost_usd(book.total_chars, COST_PER_MILLION_CHARS),
        )
        JOBS[job_id] = state
        return state


async def get_status(job_id: str) -> JobStatus | None:
    async with _LOCK:
        state = JOBS.get(job_id)
        return state.to_status() if state else None


def _output_dir(job_id: str) -> Path:
    return settings.outputs_dir / job_id


async def run_job(job_id: str, book: Book, options: GenerateOptions) -> None:
    """Background coroutine that processes the whole book."""
    from .tts import TTSError, synthesize  # local import keeps test imports light

    state = JOBS[job_id]
    state.status = "running"
    state.started_at = time.time()
    state.log.append(f"Starting job for '{book.title}' by {book.author or 'unknown'}")

    out_dir = _output_dir(job_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Build the unit list: in 'single' mode, fold all chapters into one unit.
    if options.mode == "single":
        full_text = "\n\n".join(
            f"{c.title}\n\n{c.text}" if c.title else c.text for c in book.chapters
        )
        units = [("audiobook", full_text)]
    else:
        units = [(c.title or f"Chapter {i + 1}", c.text) for i, c in enumerate(book.chapters)]

    total_chars = sum(len(t) for _, t in units) or 1
    processed_chars = 0

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
            for idx, (title, text) in enumerate(units, start=1):
                state.current_chapter = title
                state.log.append(f"[{idx}/{len(units)}] {title} ({len(text)} chars)")
                chunks = split_text(text)
                chunk_bytes: list[bytes] = []
                for c_idx, chunk in enumerate(chunks, start=1):
                    audio = await synthesize(
                        chunk,
                        voice_id=options.voice_id,
                        language=options.language,
                        client=client,
                    )
                    chunk_bytes.append(audio)
                    processed_chars += len(chunk)
                    state.chars_done = processed_chars
                    state.cost_so_far_usd = estimate_cost_usd(
                        processed_chars, COST_PER_MILLION_CHARS
                    )
                    state.progress_pct = processed_chars / total_chars * 100
                    state.log.append(
                        f"  chunk {c_idx}/{len(chunks)} done ({len(chunk)} chars)"
                    )

                chapter_path = out_dir / f"chapter_{idx:02d}.mp3"
                concat_bytes_to_file(chunk_bytes, chapter_path)
                state.chapter_paths.append(chapter_path)
                state.chapters_done = idx

            final_path = out_dir / "audiobook.mp3"
            concat_files(state.chapter_paths, final_path)
            state.output_path = final_path
            state.status = "done"
            state.progress_pct = 100.0
            state.current_chapter = None
            state.log.append(f"Finished. Total cost: ${state.cost_so_far_usd:.4f}")
    except TTSError as exc:
        state.status = "error"
        state.error = str(exc)
        state.log.append(f"ERROR: {exc}")
        log.exception("TTS job %s failed", job_id)
    except Exception as exc:  # noqa: BLE001 — surface any failure to the UI
        state.status = "error"
        state.error = f"Unexpected error: {exc}"
        state.log.append(state.error)
        log.exception("Job %s crashed", job_id)
