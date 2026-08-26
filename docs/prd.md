# PRD — Edit Analyzer

## What this is
A personal research tool that takes a video file and breaks down how it was
edited: where the cuts are, what colors dominate each shot, roughly how shots
transition into each other, what the video is about (topic), and a plain-English
description of its editing style (pacing, palette, mood).

This is a solo curiosity/research project. There is exactly one user (me).
No auth, no multi-tenancy, no monetization, no public deployment required.

## Why
Existing tools either *apply* color grading/transitions (CapCut, Colourlab AI,
Resolve) or *detect hard cuts* (PySceneDetect, Resolve's scene detection).
Nothing describes back, in plain language, what editing choices were already
made in a video someone else made. That's the gap this fills — as a
descriptive/approximate tool, not a forensic or exact-recreation tool.

## Explicit non-goals (read this before building anything)
- This does **not** recover the exact LUT, plugin, or preset used. Color
  grading recovery from an already-rendered video is an inverse problem —
  we can describe the *result* (palette, contrast, saturation) but never
  claim to know the *cause* (which tool/LUT/plugin produced it).
- This does **not** need to work on arbitrary YouTube/TikTok URLs for v1.
  Local file input only. URL ingestion is a later phase, if ever.
- This does **not** need a login system, multi-user support, or a database
  beyond simple local job records.
- This does **not** need real-time or batch processing at scale. One video
  at a time, processed synchronously, is fine.
- This is **not** a video editor. No timeline editing, no export, no undo.

## Users
Just me. Optimize for "fast to run against a video I'm curious about,"
not "polished product for strangers."

## Success criteria
I can point the tool at a video and get a report that:
1. Shows accurate cut timestamps (hard cuts especially — this should be
   reliable, it's a solved problem).
2. Shows a plausible dominant color palette per shot.
3. Gives a correct topic summary from the transcript.
4. Gives a style description that's honest about being descriptive, not
   an exact technical readout (e.g. "warm, high-contrast, fast cut rate"
   not "uses Rec.709 with a teal-orange LUT").
5. Takes less time to run than it would take me to eyeball the same video
   manually and take notes.

If the color/effect output turns out to be wrong often enough that I stop
trusting it, that's a real signal to shrink scope further, not push through.

## Feature scope

### P0 — must have for MVP
- Local video file input
- Hard-cut / scene-boundary detection with timestamps
- Per-shot dominant color palette (approximate, described as such)
- Audio transcript via speech-to-text
- Topic summary generated from transcript
- Style summary (plain-English description of pacing/palette/mood) generated
  from the extracted stats — not invented from thin air
- **Speed ramp detection** (per shot, via optical flow rate analysis) —
  this one has a real, measurable signal (see `design.md`), unlike most
  named-effect detection, so it's promoted to P0 rather than treated as
  a speculative extra
- Single-page HTML report as output

### P1 — nice to have if MVP proves useful
- Basic transition classification beyond hard cuts: fades and dissolves
  (detectable via frame-diff shape), explicitly labeled "uncertain" when
  the classifier isn't confident
- **Stylized rotoscope flag** — detects the visible/animated rotoscope
  look specifically (flicker, traced-edge instability). Does **not**
  detect rotoscoping used invisibly for clean compositing — there's no
  signal left in the final render for that case, so don't scope it in.
- **Compositing seam artifact flag** — detects visible edge halos/color
  fringing that suggest rough masking/compositing. This is deliberately
  narrower than "masking detection": it only fires on poorly executed
  work and will (correctly) stay silent on competent masking, which is
  most of what you'll encounter. See `design.md` for why general masking
  detection isn't attempted at all.
- Minimal local web UI (upload a file, see a report) instead of running
  a CLI script by hand
- Thumbnail image per shot in the report

### Explicitly not doing in MVP or P1 (revisit later, if ever)
- YouTube/TikTok URL downloading (yt-dlp) — legal/ToS friction and breakage
  risk not worth it until the core pipeline is proven useful
- **General masking detection.** Competent masking is invisible by design —
  there is no reliable signal in a rendered video that a mask was used
  when it was used well. Only the narrow "compositing seam artifact" flag
  above is attempted, and it explicitly does not claim to detect masking
  itself, only rough edge artifacts.
- Named effect detection beyond speed ramp / stylized rotoscope (glitch,
  VHS, light leaks, whip pans, etc.) — no reliable way to do this without
  labeled training data; anything shipped here will look confident and be
  wrong often
- Exact color grade / LUT identification
- Multi-video comparison or trend detection across a niche
- Any form of auth, multi-user support, or public hosting
