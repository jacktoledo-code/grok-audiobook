from __future__ import annotations

import logging
from pathlib import Path

import httpx
from fastapi import (
    BackgroundTasks,
    FastAPI,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from .chunk import estimate_cost_usd
from .config import (
    ALLOWED_MODES,
    ALLOWED_VOICES,
    COST_PER_MILLION_CHARS,
    DEFAULT_LANGUAGE,
    DEFAULT_VOICE,
    MAX_TTS_CHARS,
    settings,
)
from .jobs import JOBS, create_job, get_status, run_job
from .models import (
    ChapterInfo,
    EstimateResponse,
    GenerateOptions,
    GenerateResponse,
    JobStatus,
)
from .parsers import UnsupportedFormatError, parse_book
from .tts import TTSError, synthesize

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("audiobook")

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(title="Grok Audiobook Maker", version="1.0.0")

if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )


async def _read_upload(file: UploadFile) -> bytes:
    data = await file.read()
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large (> {settings.max_upload_mb} MB).",
        )
    if not data:
        raise HTTPException(status_code=400, detail="Empty file.")
    return data


def _validate_options(voice_id: str, mode: str) -> None:
    if voice_id not in ALLOWED_VOICES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid voice_id. Allowed: {sorted(ALLOWED_VOICES)}",
        )
    if mode not in ALLOWED_MODES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid mode. Allowed: {sorted(ALLOWED_MODES)}",
        )


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", "xai_configured": bool(settings.xai_api_key)}


@app.post("/api/estimate", response_model=EstimateResponse)
async def estimate(file: UploadFile = File(...)) -> EstimateResponse:
    data = await _read_upload(file)
    try:
        book = parse_book(data, filename=file.filename or "book")
    except UnsupportedFormatError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not book.chapters:
        raise HTTPException(status_code=400, detail="No readable content found.")

    return EstimateResponse(
        title=book.title,
        author=book.author,
        chapters=[
            ChapterInfo(index=i + 1, title=c.title, chars=c.chars)
            for i, c in enumerate(book.chapters)
        ],
        total_chars=book.total_chars,
        estimated_cost_usd=estimate_cost_usd(
            book.total_chars, COST_PER_MILLION_CHARS
        ),
    )


@app.post("/api/generate", response_model=GenerateResponse)
async def generate(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    voice_id: str = Form(DEFAULT_VOICE),
    language: str = Form(DEFAULT_LANGUAGE),
    mode: str = Form("chapter"),
) -> GenerateResponse:
    if not settings.xai_api_key:
        raise HTTPException(
            status_code=503,
            detail="XAI_API_KEY is not configured on the server.",
        )
    _validate_options(voice_id, mode)
    data = await _read_upload(file)
    try:
        book = parse_book(data, filename=file.filename or "book")
    except UnsupportedFormatError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not book.chapters:
        raise HTTPException(status_code=400, detail="No readable content found.")

    options = GenerateOptions(voice_id=voice_id, language=language, mode=mode)  # type: ignore[arg-type]
    state = await create_job(book)
    background_tasks.add_task(run_job, state.job_id, book, options)
    return GenerateResponse(job_id=state.job_id)


@app.post("/api/speak")
async def speak(
    text: str = Form(...),
    voice_id: str = Form(DEFAULT_VOICE),
    language: str = Form(DEFAULT_LANGUAGE),
) -> Response:
    if not settings.xai_api_key:
        raise HTTPException(
            status_code=503,
            detail="XAI_API_KEY is not configured on the server.",
        )
    if not text.strip():
        raise HTTPException(status_code=400, detail="Text is empty.")
    if len(text) > MAX_TTS_CHARS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Text too long ({len(text)} chars). Max {MAX_TTS_CHARS}. "
                "Use the book uploader for longer content."
            ),
        )
    if voice_id not in ALLOWED_VOICES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid voice_id. Allowed: {sorted(ALLOWED_VOICES)}",
        )

    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
        try:
            audio = await synthesize(
                text, voice_id=voice_id, language=language, client=client
            )
        except TTSError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    return Response(content=audio, media_type="audio/mpeg")


@app.get("/api/status/{job_id}", response_model=JobStatus)
async def status(job_id: str) -> JobStatus:
    js = await get_status(job_id)
    if js is None:
        raise HTTPException(status_code=404, detail="Unknown job_id")
    return js


@app.get("/api/download/{job_id}")
async def download(job_id: str) -> FileResponse:
    state = JOBS.get(job_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Unknown job_id")
    if state.status != "done" or state.output_path is None:
        raise HTTPException(status_code=409, detail=f"Job is {state.status}")
    return FileResponse(
        state.output_path,
        media_type="audio/mpeg",
        filename=f"audiobook-{job_id}.mp3",
    )


@app.get("/api/download/{job_id}/chapter/{n}")
async def download_chapter(job_id: str, n: int) -> FileResponse:
    state = JOBS.get(job_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Unknown job_id")
    if n < 1 or n > len(state.chapter_paths):
        raise HTTPException(status_code=404, detail="Chapter out of range")
    path = state.chapter_paths[n - 1]
    return FileResponse(
        path, media_type="audio/mpeg", filename=f"{job_id}-chapter-{n:02d}.mp3"
    )


@app.exception_handler(Exception)
async def _unhandled(_req, exc: Exception) -> JSONResponse:  # noqa: ANN001
    log.exception("Unhandled error")
    return JSONResponse(status_code=500, content={"detail": str(exc)})


if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
