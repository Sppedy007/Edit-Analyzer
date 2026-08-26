"""
Scene detection and transition classification using PySceneDetect and OpenCV frame-diff analysis.
"""

from typing import List, Tuple
import cv2
import numpy as np
from scenedetect import detect, ContentDetector, SceneManager, open_video
from edit_analyzer.models import Shot


def classify_transition(
    video_path: str, cut_timestamp: float, window_frames: int = 5
) -> Tuple[str, float]:
    """
    Classify the transition cut type across a boundary timestamp using frame-to-frame pixel differences.
    Returns (cut_type, confidence), where cut_type is one of: "hard", "fade", "dissolve", "unknown".
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return "unknown", 0.0

    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        cap.release()
        return "unknown", 0.0

    cut_frame = int(cut_timestamp * fps)
    start_frame = max(0, cut_frame - window_frames)
    end_frame = cut_frame + window_frames

    frames = []
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    for _ in range(start_frame, end_frame + 1):
        ret, frame = cap.read()
        if not ret or frame is None:
            break
        # Convert to small grayscale for fast frame-diff analysis
        small = cv2.resize(frame, (160, 120))
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        frames.append(gray)

    cap.release()

    if len(frames) < 3:
        return "unknown", 0.2

    # Compute adjacent frame-to-frame mean absolute differences
    diffs = [
        float(np.mean(cv2.absdiff(frames[i], frames[i + 1])))
        for i in range(len(frames) - 1)
    ]

    max_diff_idx = int(np.argmax(diffs))
    max_diff = diffs[max_diff_idx]
    avg_diff = float(np.mean(diffs))

    # Check for sharp 1-frame spike (Hard Cut)
    if max_diff > 25.0 and (max_diff > 3.0 * avg_diff or avg_diff < 5.0):
        return "hard", 0.90

    # Compute mean brightness of frames around boundary for fade detection
    brightness = [float(np.mean(f)) for f in frames]
    min_brightness = min(brightness)

    # Check if transition passes through black or white (Fade in / Fade out)
    if min_brightness < 15.0 or min_brightness > 240.0:
        return "fade", 0.75

    # Check if multiple consecutive diffs are elevated (Gradual dissolve)
    elevated_diffs = [d for d in diffs if d > 10.0]
    if len(elevated_diffs) >= 3:
        return "dissolve", 0.65

    # Default to honest unknown when uncertain
    return "unknown", 0.30


def detect_shots(video_path: str, threshold: float = 27.0) -> List[Shot]:
    """
    Detect shot boundaries in video using PySceneDetect and classify cut types.
    Returns list of Shot models.
    """
    video = open_video(video_path)
    scene_manager = SceneManager()
    scene_manager.add_detector(ContentDetector(threshold=threshold))

    # Perform scene detection
    scene_manager.detect_scenes(video)
    scene_list = scene_manager.get_scene_list()

    duration = video.duration.get_seconds()

    # Edge case: No cuts detected or video too short -> single shot
    if not scene_list:
        return [
            Shot(
                index=0,
                start_time=0.0,
                end_time=round(duration, 3),
                cut_type="unknown",
                cut_type_confidence=1.0,
                dominant_colors=[],
            )
        ]

    shots: List[Shot] = []

    for i, scene in enumerate(scene_list):
        start_sec = round(scene[0].get_seconds(), 3)
        end_sec = round(scene[1].get_seconds(), 3)

        # For the first shot, cut_type is 'hard' boundary from start of video
        if i == 0:
            cut_type = "hard"
            confidence = 1.0
        else:
            cut_type, confidence = classify_transition(video_path, start_sec)

        shots.append(
            Shot(
                index=i,
                start_time=start_sec,
                end_time=end_sec,
                cut_type=cut_type,
                cut_type_confidence=round(confidence, 2),
                dominant_colors=[],
            )
        )

    return shots
