"""
Speech-to-text transcription module using faster-whisper.
"""

from typing import List
import os
from faster_whisper import WhisperModel
from edit_analyzer.models import TranscriptSegment


def transcribe_audio(
    audio_path: str,
    model_size: str = "small",
    compute_type: str = "int8",
    initial_prompt: str | None = None,
) -> List[TranscriptSegment]:
    """
    Transcribe spoken audio from a WAV file using faster-whisper.
    Returns list of TranscriptSegment models.
    Handles silent audio files cleanly without raising exceptions.
    """

    if not os.path.isfile(audio_path) or os.path.getsize(audio_path) == 0:
        return []

    try:
        # Load CPU-friendly faster-whisper model
        model = WhisperModel(model_size, device="cpu", compute_type=compute_type)

        kwargs = {
            "beam_size": 5,
            "word_timestamps": False,
            "vad_filter": True,
        }
        if initial_prompt:
            kwargs["initial_prompt"] = initial_prompt

        segments_generator, info = model.transcribe(audio_path, **kwargs)


        segments: List[TranscriptSegment] = []
        for segment in segments_generator:
            text = segment.text.strip()
            if text:
                segments.append(
                    TranscriptSegment(
                        start_time=round(float(segment.start), 3),
                        end_time=round(float(segment.end), 3),
                        text=text,
                    )
                )

        return segments

    except Exception as e:
        # Return empty list on failure / corrupted audio rather than crashing pipeline
        print(f"Warning: Audio transcription skipped due to error: {e}")
        return []
