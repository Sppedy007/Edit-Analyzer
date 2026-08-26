# Architecture

## System overview (MVP)

```
[local video file]
        │
        ▼
 ┌─────────────────┐
 │  Ingest          │  ffmpeg: extract frames + audio track
 └──────┬──────────┘
        ▼
 ┌─────────────────┐
 │  Scene Detector  │  PySceneDetect → list of shot boundaries (timestamps)
 └──────┬──────────┘
        ▼
 ┌─────────────────┐
 │  Color Analyzer  │  per shot: sample frames → k-means → palette
 └──────┬──────────┘
        ▼
 ┌─────────────────┐
 │  Motion Analyzer │  per shot: optical flow → speed ramp / rotoscope /
 │                  │  compositing-seam flags (see design.md — each has
 │                  │  real limits, none are certainties)
 └──────┬──────────┘
        ▼
 ┌─────────────────┐
 │  Transcriber     │  faster-whisper: audio → text with timestamps
 └──────┬──────────┘
        ▼
 ┌─────────────────┐
 │  Summarizer      │  LLM call: transcript + shot stats → topic + style text
 └──────┬──────────┘
        ▼
 ┌─────────────────┐
 │  Report Renderer │  assemble everything → single static HTML file
 └─────────────────┘
```

For the MVP, this entire pipeline runs **synchronously, in one process, for
one video at a time.** No task queue, no workers, no async orchestration.
Do not introduce Celery/RQ/background workers until there's an actual reason
(i.e., Phase 4+, if this ever needs to process many videos unattended).

## Components

### 1. Pipeline core (Python package, e.g. `edit_analyzer/`)
Pure functions/modules, no web framework dependency. This should be fully
runnable as a CLI script with no UI at all — that's Phase 1. The web layer
(Phase 3) is a thin wrapper around this, not the other way around.

- `ingest.py` — wraps ffmpeg calls (frame extraction, audio extraction)
- `scenes.py` — wraps PySceneDetect, returns list of `Shot` objects
- `color.py` — per-shot palette extraction (k-means)
- `motion.py` — optical-flow-based speed ramp detection, stylized-rotoscope
  flag, and compositing-seam-artifact flag. See `design.md` for exactly
  what each can and cannot reliably detect — this is the module most at
  risk of overclaiming if extended carelessly.
- `transcribe.py` — wraps faster-whisper
- `summarize.py` — builds the LLM prompt and parses the response
- `report.py` — renders the final `AnalysisResult` to HTML

### 2. Storage (MVP)
- Input videos and extracted frames: local filesystem, a `data/<job_id>/`
  folder per run.
- Job metadata / results: a single JSON file per job (`result.json`) is
  enough. Do not add a database (SQLite or otherwise) until Phase 3's web UI
  actually needs to list past jobs — and even then, SQLite is sufficient.
  There is no case in this project's lifetime that needs Postgres.

### 3. Web layer (Phase 3, not MVP core)
- FastAPI, one route to upload a file and kick off the pipeline, one route
  to view a report. Reasoning: FastAPI over Flask/Django because it's
  lightweight, has good async support if ever needed, and auto-generates
  docs — useful when an agent is iterating on it. Not a strong opinion;
  Flask would also be fine. Django is overkill (no auth/admin/multi-model
  needs here).
- No auth. This runs locally for one user.

### 4. External dependencies
- **ffmpeg** — must be installed on the system (not a pip package). Check
  for it at startup and fail with a clear error if missing.
- **PySceneDetect** — pip-installable, handles scene detection.
- **faster-whisper** — pip-installable, CPU-friendly reimplementation of
  Whisper. Use the `base` or `small` model by default; `large` is
  overkill for topic summarization and much slower on CPU.
- **LLM API** — for topic + style summarization. Any provider works; keep
  the prompt/response handling in one module (`summarize.py`) so swapping
  providers later is a one-file change.

## Tricky integration points (read before building)

- **ffmpeg is a system dependency, not pip-installable.** The setup script
  or README must check `ffmpeg -version` works before running anything.
- **faster-whisper model download** happens on first run and can be slow/
  large depending on model size — don't let this silently hang with no
  progress indication.
- **Cut-type classification is a heuristic, not a certainty.** Frame-diff
  shape can distinguish "hard cut" from "gradual fade" reasonably well, but
  anything more exotic should be labeled `unknown` rather than guessed.
  This is a design decision, not just an implementation detail — see
  `design.md`.
- **LLM prompt must be constrained** to only describe what was actually
  measured (palette, cut rate, contrast) — not to invent named techniques,
  plugins, or LUTs it has no evidence for. This needs to be enforced in the
  prompt itself, not left to the model's judgment.
- **Video file size / length**: no explicit limit is enforced in MVP, but
  processing time scales with video length (transcription especially).
  Fine for personal use on short clips; don't be surprised if a 2-hour
  video takes a long time on CPU-only transcription.

## Repo structure

```
edit-analyzer/
├── edit_analyzer/
│   ├── __init__.py
│   ├── ingest.py
│   ├── scenes.py
│   ├── color.py
│   ├── motion.py
│   ├── transcribe.py
│   ├── summarize.py
│   ├── report.py
│   └── models.py          # shared dataclasses / schema (see design.md)
├── templates/
│   └── report.html.j2     # Jinja2 template for the report
├── data/                  # gitignored — per-job working files
├── cli.py                 # Phase 1 entry point: python cli.py <video path>
├── web.py                 # Phase 3 entry point: FastAPI app
├── requirements.txt
├── prd.md
├── architecture.md
├── design.md
├── phases.md
└── .cursorrules
```
