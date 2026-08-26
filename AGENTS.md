# AGENTS.md

## Read this first
Before writing any code, read in this order:
1. `docs/prd.md` — what this is, who it's for, what's explicitly out of scope
2. `docs/architecture.md` — components, data flow, tech choices and why
3. `docs/design.md` — data models and per-module algorithm decisions
4. `docs/phases.md` — the step-by-step build order with acceptance criteria

Then follow `docs/phases.md` sequentially. Don't jump to a later phase
before the current one's definition-of-done is met.

## One-paragraph summary
Edit Analyzer is a solo, personal-use tool: point it at a local video file
and it reports where the cuts are, what colors dominate each shot, a rough
guess at cut type (hard cut / fade / dissolve / unknown), a transcript, a
topic summary, and a plain-English style summary (pacing, palette, mood).
It deliberately does not attempt to identify exact LUTs, editing software,
or general masking use — those leave no reliable signal in a rendered
video when done competently, and claiming otherwise would make the tool's
output untrustworthy. It does attempt speed ramp detection (real signal,
via optical flow) and a narrow stylized-rotoscope flag (visible/animated
look only), both reported with confidence scores, never as flat claims.
See `docs/prd.md`'s non-goals section and `docs/design.md`'s motion.py
section for the full reasoning on what's attempted vs. deliberately
skipped and why.

## Ground rules
- No auth, no multi-user support, no cloud deployment — single local user.
- No task queue / background workers — the pipeline runs synchronously.
- No database beyond a JSON file per job until Phase 3, and SQLite (not
  Postgres) if one becomes necessary then.
- Never let generated text (report, LLM prompts, UI copy) claim a specific
  LUT, plugin, camera, or named editing technique unless the extracted
  data actually supports it. Hedge or say "unknown" instead.
- Prefer the simplest implementation that satisfies the current phase's
  acceptance criteria over general-purpose or "future-proof" abstractions.

## Where things live
See `docs/architecture.md`'s repo structure section for the expected file
layout. Pipeline logic lives in `edit_analyzer/`, is framework-agnostic,
and is driven by `cli.py` (Phase 1) and later `web.py` (Phase 3) — the web
layer wraps the pipeline, it never contains pipeline logic itself.
