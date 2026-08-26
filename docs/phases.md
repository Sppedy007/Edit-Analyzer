# Phases

Build these in order. Do not start a phase until the previous one's
acceptance criteria are met. Do not build anything listed under "explicitly
not doing" until phases.md is updated to move it in.

---

## Phase 0 — Environment setup

**Goal**: a working repo skeleton with dependencies installed and verified.

Tasks:
- [x] Create repo structure as defined in `architecture.md`
- [x] `requirements.txt` with: `scenedetect`, `opencv-python`, `faster-whisper`,
      `scikit-learn`, `jinja2`, plus whatever LLM SDK is being used
- [x] Verify `ffmpeg` is installed on the system (`ffmpeg -version`); if not,
      print a clear install instruction and exit — don't silently continue
- [x] `models.py` with the dataclasses/pydantic models from `design.md`
- [x] One sample short video (10-30 seconds, a few cuts, some speech) placed
      in `data/samples/` for testing throughout — real content, not
      synthetic, so results are actually inspectable

**Definition of done**: `python -c "import edit_analyzer"` works, ffmpeg
check passes, sample video is in place.

---

## Phase 1 — Core pipeline as a CLI script (no UI)

**Goal**: `python cli.py data/samples/sample.mp4` produces a `result.json`
matching the `AnalysisResult` schema. No web server, no HTML report yet —
just prove the pipeline works end to end.

Tasks:
- [x] `ingest.py`: extract frames + audio via ffmpeg
- [x] `scenes.py`: scene detection + cut-type heuristic (per `design.md`)
- [x] `color.py`: per-shot palette extraction
- [ ] `motion.py` (speed ramp only for now): optical-flow-based speed ramp
      detection per shot, per `design.md`. Leave `possible_stylized_rotoscope`
      and `compositing_seam_flag` as hardcoded `False`/`0.0` in this phase —
      build them in Phase 2 once the reliable parts of the pipeline are
      proven, so the noisiest detectors don't hold up the first working
      version. **NOT YET DONE — see antigravity_backfill_prompt.md**
- [x] `transcribe.py`: audio → transcript segments
- [x] `summarize.py`: transcript + stats → topic_summary + style_summary
      (both prompts, with the constraint language from `design.md` baked
      into the system prompt — verify by manually checking the output
      doesn't invent LUT/plugin names)
- [x] Wire it all together in `cli.py`, write `result.json` to `data/<job_id>/`

**Definition of done**: running the CLI against the sample video produces a
valid `result.json`. Manually inspect it — do the shot timestamps look
right when you scrub the video yourself? Does the topic summary match what
the video is actually about? Does the style summary avoid overclaiming?

---

## Phase 2 — Report renderer + remaining motion signals

**Goal**: turn `result.json` into a readable single-file HTML report, and
add the two noisier motion detectors now that the reliable core pipeline
is proven.

Tasks:
- [x] `templates/report.html.j2`: timeline bar, color swatches per shot,
      speed ramp flag, topic/style summary text, transcript
      **(built without the speed ramp flag — needs updating once motion.py
      exists)**
- [x] `report.py`: load `result.json`, render template, write `report.html`
- [x] Add a `--report` flag (or separate script) so Phase 1's CLI can
      optionally produce the HTML report in the same run
- [ ] `motion.py`: add stylized-rotoscope flag and compositing-seam-artifact
      flag, per `design.md`. Label both in the report exactly as what they
      are ("possible stylized rotoscope," "possible rough compositing
      seam") — never as "rotoscoping detected" or "masking detected"
      **NOT YET DONE — see antigravity_backfill_prompt.md**

**Definition of done**: opening `report.html` in a browser gives a genuinely
readable, useful breakdown of the sample video — this is the point where
you should actually judge "is this interesting/useful to me," per the
success criteria in `prd.md`. Specifically check: does the speed ramp flag
fire on shots you can visually confirm are ramped, and stay quiet on ones
that aren't? If it's noisy, that's worth knowing now before building more
on top of it.

---

## Phase 3 — Minimal local web wrapper

Only start this once Phase 1-2 have been run against a few different real
videos and felt useful. This phase adds convenience, not new capability.

**Goal**: upload a video through a browser instead of running a CLI command.

Tasks:
- [ ] `web.py`: FastAPI app, one upload route, one route to view a
      finished report
- [ ] Reuse the Phase 1-2 pipeline code directly — the web layer should
      call the same functions the CLI does, not duplicate logic
- [ ] Simple job list (even just listing folders under `data/`) so past
      reports are browsable — no database needed unless this gets
      genuinely annoying to do with the filesystem
- [ ] No auth, no multi-user handling, no deployment config — this runs on
      localhost for one person

**Definition of done**: you can drag a video into a browser page and get a
report link back, without touching a terminal.

---

## Phase 4 — Stretch goals (only if the above is genuinely useful)

Not committed to. Revisit `prd.md`'s non-goals before starting any of these
— they were excluded for specific reasons, not just deprioritized.

- [ ] yt-dlp-based URL ingestion (accept the breakage/ToS tradeoff
      knowingly if you do this)
- [ ] Thumbnail images per shot in the report
- [ ] Improved transition classification (still heuristic-based; don't
      jump straight to training a classifier without first checking if
      the heuristic approach is actually the bottleneck)
- [ ] Batch mode: process multiple videos, compare style summaries across
      them

**Explicitly out of scope even here**: named effect detection (glitch, VHS,
speed ramp, whip pan) and exact LUT/color-grade identification. These need
labeled training data this project doesn't have. Don't let an agent talk
itself into building a "confident-looking but unverified" classifier for
these — see `prd.md`'s non-goals.
