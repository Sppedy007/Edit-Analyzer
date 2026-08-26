# Edit Analyzer

A tool that looks at a video and reports back how it was edited: where the
cuts are, what colors dominate each shot, a rough guess at cut type (hard
cut / fade / dissolve), a transcript, what the video is about, and a
plain-English description of its editing style (pacing, palette, mood).

Built as a personal research project — one video in, one HTML report out.

## What it does

- Detects shot boundaries and rough cut type
- Extracts a dominant color palette per shot
- Transcribes speech and summarizes the topic
- Generates a plain-English style summary (pacing, color mood, cut rate)
- Renders everything into a single, readable HTML report

## What it deliberately does *not* do

This tool describes patterns it can actually measure. It does **not**
claim to identify:
- The exact LUT, plugin, or software used for color grading
- Named effects (whip pans, VHS filters, light leaks, speed ramps, etc.)

Recovering those from an already-rendered video is an unreliable inverse
problem, and a tool that guesses confidently and is often wrong is worse
than one that's upfront about what it can and can't tell you. See
[`docs/prd.md`](docs/prd.md) for the full reasoning.

## Status

Early / personal project. Currently supports local video files only (no
YouTube/TikTok URL ingestion). See [`docs/phases.md`](docs/phases.md) for
what's built vs. planned.

## Setup

Requirements:
- Python 3.11+
- [ffmpeg](https://ffmpeg.org/) installed and on your `PATH`
- An API key for the LLM provider used in `edit_analyzer/summarize.py`

```bash
git clone https://github.com/<your-username>/edit-analyzer.git
cd edit-analyzer
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env       # then fill in your API key
```

**Note on test footage**: no sample video is included in this repo — the
one used during development was copyrighted broadcast footage and isn't
redistributable. Supply your own short video clip (10-30 seconds, a few
cuts, some speech works best) to try the pipeline.

## Usage

```bash
python cli.py path/to/your/video.mp4
```

This produces a `result.json` and a `report.html` under `data/<job_id>/`.
Open `report.html` in a browser to view the breakdown.

## Project docs

Deeper design and planning docs live in [`docs/`](docs/):
- [`docs/prd.md`](docs/prd.md) — goals, non-goals, scope
- [`docs/architecture.md`](docs/architecture.md) — components and data flow
- [`docs/design.md`](docs/design.md) — data models and algorithm details
- [`docs/phases.md`](docs/phases.md) — build order and current status

## License

MIT — see [`LICENSE`](LICENSE).
