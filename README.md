# Grok Audiobook Maker

I published a novel in Brazilian Portuguese and wanted to listen to it on long flights. So I built this: a small web tool that turns TXT, Markdown, or EPUB books into MP3 audiobooks using xAI's Grok TTS. A 60k-word novel costs about **$1.50** to narrate.

This is a portfolio project — the kind of thing I build when I'm experimenting with a new API and want a sharp, end-to-end example to point at. Brazilian Portuguese is the first-class language (Grok handles it beautifully); English, Spanish, French, German, Italian, and Japanese are one dropdown away. Inline expressive tags like `[pause]`, `<whisper>`, and `<emphasis>` pass through to the model.

**Live demo:** https://grok-audiobook.onrender.com

## Features

- Upload **TXT**, **Markdown** (`.md`/`.markdown`), or **EPUB** (up to 10 MB).
- Automatic chapter detection: `# Capítulo N` in TXT/Markdown, spine/ToC in EPUB.
- Markdown syntax (bold, italic, links, code fences, images, lists, block-quotes) is stripped before narration, so the TTS reads prose, not punctuation.
- Chapter-by-chapter or single-file processing.
- Smart chunking below the 15,000-char Grok TTS limit (paragraph → sentence → hard split), keeping balanced speech-tag spans atomic.
- Cost estimator before you spend a cent.
- Live progress: `%` done, current chapter, running cost, ETA, log.
- Download the full MP3 or individual chapter MP3s.
- Single Docker service — FastAPI serves both the API and the vanilla-JS UI.

## Quick start

```bash
git clone https://github.com/jacktoledo-code/grok-audiobook.git
cd grok-audiobook
cp .env.example .env
# edit .env — paste your XAI_API_KEY
```

### Local (Python 3.11+)

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Docker

```bash
docker compose up --build
```

Open <http://localhost:8000>.

## API

| Method | Path | Purpose |
|--------|------|---------|
| `GET`  | `/api/health` | Health + `XAI_API_KEY` configured flag |
| `POST` | `/api/estimate` | Upload a book, receive char count + cost (no TTS call) |
| `POST` | `/api/generate` | Upload + options → returns `{job_id}`, runs in background |
| `GET`  | `/api/status/{job_id}` | Poll progress (client uses 1.5 s) |
| `GET`  | `/api/download/{job_id}` | Full concatenated MP3 |
| `GET`  | `/api/download/{job_id}/chapter/{n}` | Individual chapter MP3 |

Interactive docs at `/docs`.

### `/api/generate` form fields

- `file` — the `.txt` or `.epub`
- `voice_id` — `ara` (default), `eve`, `rex`, `sal`, `leo`
- `language` — defaults to `pt-BR`
- `mode` — `chapter` (default) or `single`

## TXT book format

```
Title: Meu Livro
Author: Fulana de Tal

# Capítulo 1
Era uma vez um gato preguiçoso.

# Capítulo 2
Ele acordou e bebeu café.
```

The header block is optional. If no `# ` markers exist, the whole file is treated as a single chapter named after the filename.

## Architecture

```
┌──────────────────────────────┐
│     Browser (vanilla JS)     │
│  drag&drop · poll /status    │
└──────────────┬───────────────┘
               │ multipart/form-data + JSON polling
┌──────────────▼───────────────┐
│           FastAPI            │
│  /api/* + static mount "/"   │
│  in-memory JOBS + BackgroundTasks │
└──────┬───────────────┬───────┘
       │               │
┌──────▼───┐    ┌──────▼─────────┐
│  Grok    │    │ outputs/{job}/ │
│  TTS     │    │  chapter_NN.mp3│
│  (httpx) │    │  audiobook.mp3 │
└──────────┘    └────────────────┘
```

- `backend/app/chunk.py` — smart splitter (≤15k chars).
- `backend/app/tts.py` — async httpx client with retries.
- `backend/app/jobs.py` — in-memory job store + async runner.
- `backend/app/audio.py` — byte-level MP3 concatenation.
- `backend/app/parsers/{txt,epub}.py` — chapter extraction.
- `backend/static/` — `index.html`, `app.js`, `styles.css`.

## Tests

```bash
cd backend
pip install -r requirements-dev.txt
pytest -q
```

TTS calls are mocked with `respx` — no live network traffic in CI.

## Deploy

- **Render**: push to the repo and `render.yaml` picks up the Docker service. Set `XAI_API_KEY` in the dashboard.
- **Fly.io / Railway / any container host**: use `backend/Dockerfile`. Mount a volume at `/app/outputs` if you want audio to survive restarts.

## Out of scope (roadmap)

- M4B export with chapter markers.
- Redis or SQLite persistent job store.
- Auth and rate limiting.
- Cover art / full ID3 metadata embedding.
- Automatic TTL cleanup of old `outputs/` jobs.

## License

Portfolio / demo project.
