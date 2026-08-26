"""
Motion, speed ramp, stylized rotoscope, and compositing seam artifact analysis.
"""

from typing import Dict, Any, List
import cv2
import numpy as np


def detect_speed_ramp(frames_gray: List[np.ndarray]) -> Dict[str, Any]:
    """
    Detect possible speed ramp by analyzing optical flow magnitude curves and frame duplication.
    """
    if len(frames_gray) < 6:
        return {"possible_speed_ramp": False, "speed_ramp_confidence": 0.0}

    # 1. Compute frame-to-frame optical flow magnitude
    magnitudes = []
    diffs = []
    
    prev = frames_gray[0]
    for curr in frames_gray[1:]:
        # Optical flow (Farneback)
        flow = cv2.calcOpticalFlowFarneback(
            prev, curr, None,
            pyr_scale=0.5, levels=3, winsize=15,
            iterations=3, poly_n=5, poly_sigma=1.2, flags=0
        )
        mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
        magnitudes.append(float(np.mean(mag)))

        # Frame difference for duplicate/blended frame detection
        abs_diff = float(np.mean(cv2.absdiff(prev, curr)))
        diffs.append(abs_diff)

        prev = curr

    if not magnitudes:
        return {"possible_speed_ramp": False, "speed_ramp_confidence": 0.0}

    # Signal A: Flow acceleration/deceleration curve (smooth change in rate of motion)
    m_array = np.array(magnitudes)
    n = len(m_array)
    x = np.arange(n)
    
    # Linear fit slope & R-squared
    slope, intercept = np.polyfit(x, m_array, 1)
    y_pred = slope * x + intercept
    ss_res = np.sum((m_array - y_pred) ** 2)
    ss_tot = np.sum((m_array - np.mean(m_array)) ** 2)
    r2 = 1.0 - (ss_res / max(1e-5, ss_tot)) if ss_tot > 1e-5 else 0.0

    # Acceleration signal: sustained slope with good curve fit
    motion_range = np.max(m_array) - np.min(m_array)
    flow_ramp_signal = bool(abs(slope) > 0.15 and motion_range > 1.5 and r2 > 0.50)

    # Signal B: Duplicate / blended frame detection (time-remapping artifact)
    duplicate_count = sum(1 for d in diffs if d < 1.2)
    duplicate_signal = bool(duplicate_count >= 2 and (duplicate_count / n) > 0.15)

    # Combine signals per design.md rules:
    # Two signals agreeing -> high confidence; either alone -> moderate/lower confidence
    if flow_ramp_signal and duplicate_signal:
        possible = True
        confidence = round(min(0.85, 0.60 + r2 * 0.25), 2)
    elif flow_ramp_signal:
        possible = True
        confidence = round(min(0.70, 0.45 + r2 * 0.25), 2)
    elif duplicate_signal:
        possible = True
        confidence = 0.50
    else:
        possible = False
        confidence = 0.0

    return {
        "possible_speed_ramp": possible,
        "speed_ramp_confidence": confidence,
    }


def detect_stylized_rotoscope(frames_gray: List[np.ndarray], frames_bgr: List[np.ndarray]) -> Dict[str, Any]:
    """
    Detect visible stylized rotoscoping (hand-traced outlines, edge flicker, color posterization).
    """
    if len(frames_gray) < 4:
        return {"possible_stylized_rotoscope": False, "stylized_rotoscope_confidence": 0.0}

    # Signal A: Frame-to-frame Canny edge instability / flicker
    edge_maps = [cv2.Canny(f, 50, 150) for f in frames_gray]
    edge_diffs = []
    for i in range(len(edge_maps) - 1):
        diff = float(np.mean(cv2.absdiff(edge_maps[i], edge_maps[i + 1])))
        edge_diffs.append(diff)

    edge_flicker = float(np.std(edge_diffs)) if edge_diffs else 0.0

    # Signal B: Color quantization / posterization (few unique color levels)
    quant_scores = []
    for bgr in frames_bgr:
        # Sample center region
        h, w = bgr.shape[:2]
        center = bgr[h//4:3*h//4, w//4:3*w//4]
        # Count unique color bins (quantized to 16 levels per channel)
        q = (center // 16) * 16
        unique_colors = len(np.unique(q.reshape(-1, 3), axis=0))
        quant_scores.append(unique_colors)

    avg_unique = float(np.mean(quant_scores)) if quant_scores else 500.0

    # Stylized rotoscope heuristic: elevated edge flicker + low unique color depth
    is_flickery = edge_flicker > 18.0
    is_posterized = avg_unique < 250.0

    if is_flickery and is_posterized:
        possible = True
        confidence = 0.70
    elif is_flickery or is_posterized:
        possible = True
        confidence = 0.45
    else:
        possible = False
        confidence = 0.0

    return {
        "possible_stylized_rotoscope": possible,
        "stylized_rotoscope_confidence": confidence,
    }


def detect_compositing_seam(frames_bgr: List[np.ndarray]) -> Dict[str, Any]:
    """
    Detect rough compositing seam give-away artifacts (edge halo, lighting/color mismatch, symmetric background).
    """
    if not frames_bgr:
        return {"compositing_seam_flag": False}

    seam_detected = False

    for bgr in frames_bgr[:3]:
        h, w = bgr.shape[:2]
        if h < 20 or w < 20:
            continue

        # 1. Subject (center) vs Background (outer margins)
        margin_h = max(1, h // 6)
        margin_w = max(1, w // 6)

        center_crop = bgr[margin_h:h-margin_h, margin_w:w-margin_w]
        
        bg_top = bgr[:margin_h, :]
        bg_bottom = bgr[h-margin_h:, :]
        bg_left = bgr[:, :margin_w]
        bg_right = bgr[:, w-margin_w:]
        bg_pixels = np.vstack([
            bg_top.reshape(-1, 3),
            bg_bottom.reshape(-1, 3),
            bg_left.reshape(-1, 3),
            bg_right.reshape(-1, 3)
        ])

        # Lighting & Color Temperature (mean B, G, R) Mismatch
        center_mean = np.mean(center_crop, axis=(0, 1))
        bg_mean = np.mean(bg_pixels, axis=0)

        # Color spill mismatch vector norm
        color_mismatch = float(np.linalg.norm(center_mean - bg_mean))

        # Edge halo / rim discontinuity check via Laplacian variance along border
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()

        # Two-toned / split background structure check (left vs right background half diff)
        bg_left_mean = np.mean(bg_left, axis=(0, 1))
        bg_right_mean = np.mean(bg_right, axis=(0, 1))
        bg_split_diff = float(np.linalg.norm(bg_left_mean - bg_right_mean))

        # Check combined giveaway artifact condition
        if color_mismatch > 65.0 and (laplacian_var > 350.0 or bg_split_diff > 50.0):
            seam_detected = True
            break

    return {
        "compositing_seam_flag": seam_detected,
    }


def analyze_shot_motion(
    video_path: str, start_time: float, end_time: float, max_samples: int = 12
) -> Dict[str, Any]:
    """
    Extract frames for a shot and run all three motion detectors:
    1. Speed ramp
    2. Stylized rotoscope
    3. Compositing seam artifact
    Returns combined dict of shot motion fields.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return {
            "possible_speed_ramp": False,
            "speed_ramp_confidence": 0.0,
            "possible_stylized_rotoscope": False,
            "stylized_rotoscope_confidence": 0.0,
            "compositing_seam_flag": False,
        }

    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        cap.release()
        return {
            "possible_speed_ramp": False,
            "speed_ramp_confidence": 0.0,
            "possible_stylized_rotoscope": False,
            "stylized_rotoscope_confidence": 0.0,
            "compositing_seam_flag": False,
        }

    start_frame = int(start_time * fps)
    end_frame = int(end_time * fps)
    total_frames = max(1, end_frame - start_frame)

    if total_frames <= max_samples:
        sample_indices = list(range(start_frame, end_frame + 1))
    else:
        step = total_frames / float(max_samples)
        sample_indices = [int(start_frame + step * i) for i in range(max_samples)]

    frames_gray = []
    frames_bgr = []

    for idx in sample_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if not ret or frame is None:
            continue
        
        # Downscale for performance
        small_bgr = cv2.resize(frame, (160, 120))
        small_gray = cv2.cvtColor(small_bgr, cv2.COLOR_BGR2GRAY)
        
        frames_bgr.append(small_bgr)
        frames_gray.append(small_gray)

    cap.release()

    if not frames_gray:
        return {
            "possible_speed_ramp": False,
            "speed_ramp_confidence": 0.0,
            "possible_stylized_rotoscope": False,
            "stylized_rotoscope_confidence": 0.0,
            "compositing_seam_flag": False,
        }

    ramp_res = detect_speed_ramp(frames_gray)
    roto_res = detect_stylized_rotoscope(frames_gray, frames_bgr)
    seam_res = detect_compositing_seam(frames_bgr)

    return {
        "possible_speed_ramp": ramp_res["possible_speed_ramp"],
        "speed_ramp_confidence": ramp_res["speed_ramp_confidence"],
        "possible_stylized_rotoscope": roto_res["possible_stylized_rotoscope"],
        "stylized_rotoscope_confidence": roto_res["stylized_rotoscope_confidence"],
        "compositing_seam_flag": seam_res["compositing_seam_flag"],
    }
