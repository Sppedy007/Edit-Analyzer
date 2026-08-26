# Design

## Data model

All modules pass data through these shapes. Define them as Python
dataclasses (or pydantic models, since FastAPI will want pydantic anyway) in
`edit_analyzer/models.py`. Keep this file as the single source of truth —
every other module imports from here, nothing redefines its own shape.

```python
class Shot:
    index: int
    start_time: float          # seconds
    end_time: float             # seconds
    cut_type: str               # "hard" | "fade" | "dissolve" | "unknown"
    cut_type_confidence: float  # 0.0-1.0, be honest when it's low
    dominant_colors: list[str]  # hex codes, ordered by proportion
    thumbnail_path: str | None  # relative path, optional for MVP
    possible_speed_ramp: bool
    speed_ramp_confidence: float        # 0.0-1.0
    possible_stylized_rotoscope: bool
    stylized_rotoscope_confidence: float # 0.0-1.0
    compositing_seam_flag: bool          # rough-edge artifact only, not "masking used"

class TranscriptSegment:
    start_time: float
    end_time: float
    text: str

class AnalysisResult:
    job_id: str
    source_filename: str
    duration_seconds: float
    generated_at: str           # ISO timestamp
    shots: list[Shot]
    transcript: list[TranscriptSegment]
    topic_summary: str
    style_summary: str
```

`result.json` for a given job is just this object serialized. The report
renderer reads this and nothing else — it should never re-derive data from
raw video/audio, keeping the renderer decoupled from the pipeline.

## Module-by-module design

### `scenes.py` — scene/cut detection
Use PySceneDetect's `ContentDetector` with its default threshold as a
starting point; expose the threshold as a parameter but don't build any UI
for tuning it in MVP — a constant at the top of the file is fine.
Output: list of `(start_time, end_time)` pairs, which become `Shot.index`,
`start_time`, `end_time`.

### Cut-type classification (still `scenes.py` or a sibling function)
This is a heuristic layered on top of scene detection, not a separate ML
model. Approach:
- Compute frame-to-frame pixel difference across the boundary.
- A sharp, single-frame jump → `hard`, high confidence.
- A gradual ramp over several frames → `fade` or `dissolve` depending on
  whether it passes through black/white (`fade`) or blends two shots
  (`dissolve`), moderate confidence.
- Anything that doesn't clearly match either pattern → `unknown`, low
  confidence. **Do not force a guess here.** An honest "unknown" is more
  useful than a wrong specific label, and this is the exact place where
  overclaiming will quietly poison the tool's usefulness for you later.

### `color.py` — palette extraction
- Sample 3-5 frames evenly spaced within each shot (not just the first
  frame — a shot can shift in lighting).
- Downscale frames before clustering (e.g. to ~100px wide) for speed —
  full resolution is unnecessary for a palette estimate.
- k-means with k=5, sort clusters by pixel proportion descending.
- Store as hex codes in `Shot.dominant_colors`.
- **Framing matters**: this is "the dominant colors present in this shot,"
  not "the color grade applied." Never let downstream text (report or LLM
  summary) phrase it as the latter.

### `transcribe.py` — speech-to-text
- faster-whisper, `base` model default (swap to `small` if accuracy is
  poor on your typical content, but don't reach for `large` unless base/
  small are clearly failing — the speed cost is significant on CPU).
- Handle the empty-transcript case explicitly (silent/music-only video):
  `topic_summary` should fall back to something like "no speech detected;
  topic inferred from visual pacing only" rather than an LLM call
  hallucinating a topic from nothing.

### `summarize.py` — LLM topic + style summary
Two things happen here, ideally as two distinct prompts (clearer to debug
and iterate on than one combined mega-prompt):

**Topic summary prompt** — input: transcript text. Straightforward
summarization, low risk.

**Style summary prompt** — input: structured stats only (shot count, cut
rate = shots/duration, dominant palette across all shots, cut-type
breakdown). The prompt must explicitly instruct the model to:
- Only describe what's in the provided stats (pacing, color mood, cut
  frequency).
- Never name specific LUTs, plugins, camera models, or editing software.
- Never claim a technique it wasn't given evidence for (e.g. don't say
  "uses a whip pan" if no transition data supports it).
- Prefer hedged, descriptive language ("appears warm-toned," "cuts
  frequently") over confident technical claims.

This constraint belongs in the prompt text itself — write it as an explicit
system instruction, not a comment for future-you to remember.

### `motion.py` — speed ramp and stylized-rotoscope signals

These are the three "advanced" pattern detectors this project cares about.
Read each one's honest capability before building it — this is the exact
place overclaiming will happen if you're not careful.

**Speed ramp detection (real, buildable)**
A speed ramp shows up as a change in *rate of visual change* within a
single continuous shot (no cut) that isn't explained by camera motion:
- Compute optical flow magnitude (e.g. `cv2.calcOpticalFlowFarneback`)
  frame-to-frame across the shot.
- Look for a sustained acceleration or deceleration in that magnitude
  over the shot's duration — a real speed ramp shows a smooth
  speed-up/slow-down curve, not noise.
- Also check for duplicate or blended frames (common artifact of
  time-remapping in editing software) as a secondary signal.
- Output: `Shot.possible_speed_ramp: bool` + `Shot.speed_ramp_confidence:
  float`. Two signals agreeing (flow-curve shape + frame duplication)
  should raise confidence; either alone should be treated as weaker.
- This can produce false positives on genuinely fast/slow real-world
  motion (whip pans, zooms) — the heuristic detects a *pattern*, not a
  certainty, and the report should phrase it as "possible speed ramp,"
  never a flat assertion.

**Stylized rotoscope flag (narrow, experimental)**
This only catches *visible* rotoscoping — traced/animated look, not
invisible masking used for clean compositing (see below for why that's
different).
- Signal: frame-to-frame instability in edge maps around a subject that's
  characteristic of hand-traced or per-frame-processed outlines (edges
  that shift/flicker in ways natural motion blur doesn't produce), often
  combined with visible color quantization/banding.
- Output: `Shot.possible_stylized_rotoscope: bool` with confidence. Expect
  this to be noisy — treat it as a "worth a manual look" flag, not a
  reliable classifier, and say so in the report UI copy.

**Masking — deliberately not a general detector**
Competently done masking (isolating a subject/region for compositing or
targeted effects) is designed to be invisible in the final render — that
is the whole point of the technique. There is no reliable signal to detect
"a mask was used" when it's done well; this project does not attempt it.

What *is* detectable is the opposite case: poorly done masking that leaves
visible artifacts. Concretely, check for:
- **Edge halo/rim discontinuity**: a thin band around the subject where
  the cutout edge doesn't blend with the background (compare pixel
  gradients right at the mask boundary vs. a few pixels further in).
- **Lighting/color-temperature mismatch**: sample the color temperature
  and brightness of the region immediately around the subject vs. the
  subject itself. A real environment casts consistent light and color
  spill onto whatever's in it; a composited subject often doesn't pick up
  any color cast from a dramatic background (e.g. a person standing in
  front of colored fireworks/explosions with no red/blue tint reflected
  on them is a strong tell).
- **Unnaturally symmetric or two-toned backgrounds**: a background split
  into distinct flat-colored halves or repeating/mirrored structure often
  means it's a composited or templated background rather than one
  continuous filmed environment. This is a signal about the *background*,
  not the subject edge, and worth checking independently.

Build this as `Shot.compositing_seam_flag: bool` with a confidence score,
and label it in the report as exactly what it is — "possible rough
compositing seam" — not "masking detected." It will correctly stay silent
on the majority of real-world (competent, photoreal) masking, and fire
mainly on stylized/templated graphics or amateur composites where these
specific mismatches are visible. That's the honest scope: it catches
*give-away artifacts*, not the technique itself.

### `report.py` — rendering
Single Jinja2 template, one HTML file per job, self-contained (inline CSS,
no external asset pipeline needed for a personal tool). Layout:
- Horizontal timeline bar with cut markers, colored by `cut_type`
- Below each shot: its color swatches (small colored blocks) + timestamp
- Topic summary and style summary as plain text blocks
- Full transcript, collapsible/scrollable, for reference

## Edge cases to handle explicitly (not "later," now)
- Video with zero detected cuts (e.g. a single continuous shot) — report
  should say so plainly, not error out.
- Video shorter than a few seconds — scene detection and color sampling
  should degrade gracefully (e.g. treat the whole thing as one shot).
- Corrupted or unsupported video file — fail with a clear error message
  before entering the pipeline, not halfway through.
- Non-English speech — faster-whisper supports multiple languages; don't
  hardcode an English-only assumption in `transcribe.py`.
