"""
Video & audio ingestion utilities using OpenCV and ffmpeg.
"""

import os
import subprocess
import cv2
from edit_analyzer import get_ffmpeg_cmd


def get_video_info(video_path: str) -> dict:
    """
    Validate the video file and extract basic metadata (duration, fps, frame count, width, height).
    Raises FileNotFoundError or ValueError if video file is missing or invalid.
    """
    if not os.path.isfile(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Unable to open video file (corrupted or unsupported format): {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()

    if fps <= 0 or frame_count <= 0:
        raise ValueError(f"Invalid video metadata for file: {video_path}")

    duration = frame_count / fps

    return {
        "duration_seconds": round(duration, 3),
        "fps": fps,
        "frame_count": int(frame_count),
        "width": width,
        "height": height,
    }


def extract_audio(video_path: str, output_wav_path: str) -> bool:
    """
    Extract audio from video file to 16kHz mono WAV format (ideal for faster-whisper).
    Returns True if audio track was extracted, False if no audio stream exists or extraction failed.
    """
    ffmpeg_cmd = get_ffmpeg_cmd()
    os.makedirs(os.path.dirname(os.path.abspath(output_wav_path)), exist_ok=True)

    cmd = [
        ffmpeg_cmd,
        "-y",                   # overwrite output file if exists
        "-i", video_path,       # input file
        "-vn",                  # disable video recording
        "-acodec", "pcm_s16le", # PCM 16-bit little-endian audio codec
        "-ar", "16000",         # 16kHz sample rate
        "-ac", "1",             # mono channel
        output_wav_path,
    ]

    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if res.returncode == 0 and os.path.exists(output_wav_path) and os.path.getsize(output_wav_path) > 0:
        return True
    
    return False
