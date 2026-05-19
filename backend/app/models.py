from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field

from .config import DEFAULT_LANGUAGE, DEFAULT_VOICE


@dataclass
class Chapter:
    title: str
    text: str

    @property
    def chars(self) -> int:
        return len(self.text)


@dataclass
class Book:
    title: str
    author: str
    chapters: list[Chapter] = field(default_factory=list)

    @property
    def total_chars(self) -> int:
        return sum(c.chars for c in self.chapters)


class GenerateOptions(BaseModel):
    voice_id: str = DEFAULT_VOICE
    language: str = DEFAULT_LANGUAGE
    mode: Literal["chapter", "single"] = "chapter"


class ChapterInfo(BaseModel):
    index: int
    title: str
    chars: int


class EstimateResponse(BaseModel):
    title: str
    author: str
    chapters: list[ChapterInfo]
    total_chars: int
    estimated_cost_usd: float


class JobStatus(BaseModel):
    job_id: str
    status: Literal["queued", "running", "done", "error"]
    progress_pct: float = 0.0
    current_chapter: str | None = None
    chapters_total: int = 0
    chapters_done: int = 0
    chars_total: int = 0
    chars_done: int = 0
    est_cost_usd: float = 0.0
    cost_so_far_usd: float = 0.0
    eta_seconds: float | None = None
    log: list[str] = Field(default_factory=list)
    error: str | None = None


class GenerateResponse(BaseModel):
    job_id: str
