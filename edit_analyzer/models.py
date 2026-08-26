"""
Data models for Edit Analyzer.
Single source of truth for all modules in edit_analyzer.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class Shot(BaseModel):
    index: int = Field(..., description="0-based index of the shot in the video")
    start_time: float = Field(..., description="Start timestamp in seconds")
    end_time: float = Field(..., description="End timestamp in seconds")
    cut_type: str = Field(
        ...,
        description='Cut transition type: "hard" | "fade" | "dissolve" | "unknown"',
    )
    cut_type_confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0"
    )
    dominant_colors: List[str] = Field(
        default_factory=list,
        description="Hex color codes (e.g. '#FF0000') ordered by pixel proportion",
    )
    thumbnail_path: Optional[str] = Field(
        default=None, description="Relative path to shot thumbnail image if available"
    )
    possible_speed_ramp: bool = Field(
        default=False, description="Possible speed ramp detected via optical flow slope"
    )
    speed_ramp_confidence: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Confidence score for speed ramp"
    )
    possible_stylized_rotoscope: bool = Field(
        default=False,
        description="Possible stylized rotoscoping detected via edge map instability",
    )
    stylized_rotoscope_confidence: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Confidence score for stylized rotoscoping"
    )
    compositing_seam_flag: bool = Field(
        default=False,
        description="Possible rough compositing seam / edge halo artifact detected",
    )



class TranscriptSegment(BaseModel):
    start_time: float = Field(..., description="Segment start timestamp in seconds")
    end_time: float = Field(..., description="Segment end timestamp in seconds")
    text: str = Field(..., description="Transcribed spoken text")


class AnalysisResult(BaseModel):
    job_id: str = Field(..., description="Unique job identifier")
    source_filename: str = Field(..., description="Original video file name")
    duration_seconds: float = Field(..., description="Total video duration in seconds")
    generated_at: str = Field(..., description="ISO 8601 timestamp of analysis completion")
    shots: List[Shot] = Field(default_factory=list, description="Ordered list of analyzed shots")
    transcript: List[TranscriptSegment] = Field(
        default_factory=list, description="Ordered speech transcript segments"
    )
    topic_summary: str = Field(..., description="High-level topic summary derived from transcript")
    style_summary: str = Field(
        ..., description="Plain-English summary of pacing, color palette, and mood"
    )
