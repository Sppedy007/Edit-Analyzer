"""
Dominant color palette extraction per shot using frame sampling and k-means clustering.
"""

from typing import List
import cv2
import numpy as np
from sklearn.cluster import KMeans


def extract_shot_palette(
    video_path: str,
    start_time: float,
    end_time: float,
    num_samples: int = 4,
    num_colors: int = 5,
) -> List[str]:
    """
    Extract dominant color hex codes for a shot by sampling evenly spaced frames.
    Downscales frames (~100px width) before clustering for performance.
    Returns list of Hex strings (e.g. ['#1F2E3D', '#E5A13B']) ordered by pixel proportion.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return []

    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        cap.release()
        return []

    start_frame = int(start_time * fps)
    end_frame = int(end_time * fps)
    total_shot_frames = max(1, end_frame - start_frame)

    # Determine frame indices to sample evenly within the shot
    if total_shot_frames <= num_samples:
        sample_indices = list(range(start_frame, end_frame + 1))
    else:
        step = total_shot_frames / (num_samples + 1)
        sample_indices = [
            int(start_frame + step * (i + 1)) for i in range(num_samples)
        ]

    pixel_data = []

    for frame_idx in sample_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret or frame is None:
            continue

        # Downscale frame to ~100px width for fast clustering
        h, w = frame.shape[:2]
        target_w = 100
        target_h = max(1, int(h * (target_w / float(w))))
        small_frame = cv2.resize(frame, (target_w, target_h), interpolation=cv2.INTER_AREA)

        # Convert BGR (OpenCV format) to RGB
        rgb_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
        pixels = rgb_frame.reshape(-1, 3)
        pixel_data.append(pixels)

    cap.release()

    if not pixel_data:
        return []

    all_pixels = np.vstack(pixel_data)
    if len(all_pixels) == 0:
        return []

    # Adjust n_clusters if total pixels are fewer than requested colors
    k = min(num_colors, len(all_pixels))
    if k <= 0:
        return []

    kmeans = KMeans(n_clusters=k, random_state=42, n_init=3)
    kmeans.fit(all_pixels)

    labels, counts = np.unique(kmeans.labels_, return_counts=True)
    # Sort cluster indices by pixel proportion descending
    sorted_indices = np.argsort(-counts)

    hex_colors = []
    for idx in sorted_indices:
        centroid = kmeans.cluster_centers_[idx].astype(int)
        r, g, b = [max(0, min(255, c)) for c in centroid]
        hex_code = f"#{r:02X}{g:02X}{b:02X}"
        hex_colors.append(hex_code)

    return hex_colors
