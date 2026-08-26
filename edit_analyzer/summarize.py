"""
LLM-based topic and style summarization with strict anti-overclaiming constraints.
"""

from typing import List
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from edit_analyzer.models import Shot, TranscriptSegment

# System instructions enforcing product constraints defined in design.md & prd.md
STYLE_SUMMARY_SYSTEM_INSTRUCTION = """
You are an expert video editing analyzer producing plain-English research notes on a video's edit style.
You are given STRICT STATISTICAL DATA extracted from video frames and cut boundaries:
- Shot count, total duration, average cut rate (shots/sec)
- Breakdown of transition cut types (hard cut, fade, dissolve, unknown)
- Dominant frame colors extracted per shot

CRITICAL CONSTRAINTS (YOU MUST FOLLOW WITHOUT EXCEPTION):
1. Rely ONLY on the numerical stats and color data provided. Do NOT invent, assume, or infer un-evidenced details.
2. NEVER name specific LUTs, color presets, plugins, camera models, or editing software (e.g. do NOT say 'Rec.709', 'Teal & Orange LUT', 'Premiere Pro', 'DaVinci Resolve', 'CapCut', etc.).
3. NEVER claim specific named editing techniques or visual effects not proven by the data (e.g. do NOT say 'whip pan', 'VHS filter', 'glitch effect', 'light leak', 'speed ramp').
4. Use hedged, honest, descriptive language (e.g. "appears fast-paced with frequent hard cuts," "palette features deep blues and high-contrast dark tones").
5. When transition data shows 'unknown' or low confidence, describe it as indeterminate rather than forcing a guess.
""".strip()


def _get_api_keys():
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or os.getenv("LLM_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    return gemini_key, openai_key


def generate_topic_summary(transcript: List[TranscriptSegment]) -> str:
    """
    Generate a high-level topic summary from the transcript segments.
    """
    if not transcript:
        return "No spoken speech detected in audio track; visual content and edit pacing analysis performed."

    full_text = " ".join([seg.text for seg in transcript])
    if not full_text.strip():
        return "No spoken speech detected in audio track; visual content and edit pacing analysis performed."

    # Check for available API key
    gemini_key, openai_key = _get_api_keys()


    if gemini_key:
        try:
            from google import genai
            client = genai.Client(api_key=gemini_key)
            prompt = f"Summarize the following video transcript in 1-2 concise sentences focusing on the topic:\n\n{full_text}"
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
            )
            if response and response.text:
                return response.text.strip()
        except Exception as e:
            print(f"Warning: Gemini topic summarization failed ({e}), using fallback.")

    elif openai_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=openai_key)
            prompt = f"Summarize the following video transcript in 1-2 concise sentences focusing on the topic:\n\n{full_text}"
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
            )
            if response.choices and response.choices[0].message.content:
                return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"Warning: OpenAI topic summarization failed ({e}), using fallback.")

    # Rule-based deterministic fallback when no LLM API key is present
    words = full_text.split()
    preview = " ".join(words[:30]) + ("..." if len(words) > 30 else "")
    return f"Transcript topic overview based on audio speech: \"{preview}\""


def generate_style_summary(shots: List[Shot], duration: float) -> str:
    """
    Generate plain-English editing style summary (pacing, color palette mood, cut breakdown).
    Uses LLM API if key is present; falls back to structured stats summary otherwise.
    """
    num_shots = len(shots)
    if num_shots == 0 or duration <= 0:
        return "Single continuous video sequence with no detected scene cuts."

    cut_rate = round(num_shots / duration, 2)
    avg_shot_length = round(duration / num_shots, 2)

    # Cut type breakdown
    cut_types = {}
    for s in shots:
        cut_types[s.cut_type] = cut_types.get(s.cut_type, 0) + 1

    # Dominant colors across all shots
    all_colors = []
    for s in shots:
        all_colors.extend(s.dominant_colors[:2])

    stats_summary = (
        f"- Total duration: {duration:.1f}s\n"
        f"- Total shots: {num_shots}\n"
        f"- Cut rate: {cut_rate} shots/sec (average shot duration: {avg_shot_length}s)\n"
        f"- Transition breakdown: {cut_types}\n"
        f"- Dominant shot colors sampled: {all_colors[:10]}"
    )

    gemini_key, openai_key = _get_api_keys()

    if gemini_key:
        try:
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=gemini_key)
            prompt = f"Based ONLY on the following editing statistics, provide a plain-English style summary (1 paragraph describing pacing, color palette mood, and transition types):\n\n{stats_summary}"
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=STYLE_SUMMARY_SYSTEM_INSTRUCTION
                ),
            )
            if response and response.text:
                return response.text.strip()
        except Exception as e:
            print(f"Warning: Gemini style summarization failed ({e}), using fallback.")

    elif openai_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=openai_key)
            prompt = f"Based ONLY on the following editing statistics, provide a plain-English style summary (1 paragraph describing pacing, color palette mood, and transition types):\n\n{stats_summary}"
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": STYLE_SUMMARY_SYSTEM_INSTRUCTION},
                    {"role": "user", "content": prompt},
                ],
            )
            if response.choices and response.choices[0].message.content:
                return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"Warning: OpenAI style summarization failed ({e}), using fallback.")

    # Rule-based fallback summary when no LLM API key is configured
    pacing_desc = "fast-paced" if avg_shot_length < 2.0 else ("moderate pacing" if avg_shot_length < 5.0 else "deliberate/slow pacing")
    cut_desc = ", ".join([f"{count} {kind}" for kind, count in cut_types.items()])

    return (
        f"This video features {num_shots} shots over {duration:.1f} seconds with an average shot duration of {avg_shot_length}s ({pacing_desc}). "
        f"Transitions observed include {cut_desc}. Dominant sampled frame colors include {', '.join(all_colors[:5])}."
    )
