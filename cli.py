"""
Phase 1 CLI entry point for Edit Analyzer.
Runs the complete video analysis pipeline and saves result.json to data/<job_id>/.
"""

import sys
import os
import json
import uuid
from datetime import datetime, timezone
import argparse

from edit_analyzer import check_ffmpeg_installed
from edit_analyzer.ingest import get_video_info, extract_audio
from edit_analyzer.scenes import detect_shots
from edit_analyzer.color import extract_shot_palette
from edit_analyzer.motion import analyze_shot_motion
from edit_analyzer.transcribe import transcribe_audio
from edit_analyzer.summarize import generate_topic_summary, generate_style_summary
from edit_analyzer.report import render_report
from edit_analyzer.models import AnalysisResult


def run_pipeline(
    video_path: str, output_base_dir: str = "data", generate_report: bool = True
) -> AnalysisResult:
    """
    Run the end-to-end video analysis pipeline synchronously for a single video file.
    Writes result.json and report.html to output_base_dir/<job_id>/.
    """
    if not check_ffmpeg_installed():
        raise RuntimeError("System check failed: ffmpeg is not available.")

    print(f"\n[1/7] Validating input video: {video_path}")
    info = get_video_info(video_path)
    duration = info["duration_seconds"]
    print(f"      Duration: {duration:.2f}s | Resolution: {info['width']}x{info['height']} @ {info['fps']:.2f} fps")

    # Generate unique job ID
    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    short_id = uuid.uuid4().hex[:6]
    job_id = f"job_{timestamp_str}_{short_id}"

    job_dir = os.path.join(output_base_dir, job_id)
    os.makedirs(job_dir, exist_ok=True)
    print(f"      Created job directory: {job_dir}")

    # Extract audio
    print(f"\n[2/7] Extracting audio track...")
    audio_path = os.path.join(job_dir, "audio.wav")
    has_audio = extract_audio(video_path, audio_path)
    if has_audio:
        print(f"      Audio extracted to {audio_path}")
    else:
        print(f"      No audio track found or extraction failed.")

    # Scene detection & transition classification
    print(f"\n[3/7] Detecting scene boundaries & classifying cut transitions...")
    shots = detect_shots(video_path)
    print(f"      Detected {len(shots)} shots.")

    # Palette & Motion extraction
    print(f"\n[4/7] Extracting dominant color palettes & motion signals per shot...")
    for i, shot in enumerate(shots):
        colors = extract_shot_palette(video_path, shot.start_time, shot.end_time)
        shot.dominant_colors = colors

        # Analyze motion signals (speed ramp, stylized rotoscope, compositing seam)
        motion_res = analyze_shot_motion(video_path, shot.start_time, shot.end_time)
        shot.possible_speed_ramp = motion_res["possible_speed_ramp"]
        shot.speed_ramp_confidence = motion_res["speed_ramp_confidence"]
        shot.possible_stylized_rotoscope = motion_res["possible_stylized_rotoscope"]
        shot.stylized_rotoscope_confidence = motion_res["stylized_rotoscope_confidence"]
        shot.compositing_seam_flag = motion_res["compositing_seam_flag"]

        print(f"      Shot {i+1}/{len(shots)} [{shot.start_time:.1f}s - {shot.end_time:.1f}s] cut={shot.cut_type} ramp={shot.possible_speed_ramp} roto={shot.possible_stylized_rotoscope} seam={shot.compositing_seam_flag}")


    # Audio transcription
    print(f"\n[5/7] Transcribing speech from audio track...")
    if has_audio and os.path.exists(audio_path):
        transcript = transcribe_audio(audio_path)
        print(f"      Transcribed {len(transcript)} text segments.")
    else:
        transcript = []
        print(f"      Skipped transcription (no audio).")

    # Summarization
    print(f"\n[6/7] Generating topic & style summaries...")
    topic_summary = generate_topic_summary(transcript)
    style_summary = generate_style_summary(shots, duration)

    # Build result model
    result = AnalysisResult(
        job_id=job_id,
        source_filename=os.path.basename(video_path),
        duration_seconds=duration,
        generated_at=datetime.now(timezone.utc).isoformat(),
        shots=shots,
        transcript=transcript,
        topic_summary=topic_summary,
        style_summary=style_summary,
    )

    # Save result.json
    result_path = os.path.join(job_dir, "result.json")
    with open(result_path, "w", encoding="utf-8") as f:
        f.write(result.model_dump_json(indent=2))

    # Render HTML report
    report_path = None
    if generate_report:
        print(f"\n[7/7] Rendering HTML report...")
        report_path = os.path.join(job_dir, "report.html")
        render_report(result, report_path)
        print(f"      Rendered report to {report_path}")

    print(f"\n=======================================================")
    print(f" Analysis complete!")
    print(f" Result JSON : {result_path}")
    if report_path:
        print(f" HTML Report : {report_path}")
    print(f" Topic Summary: {topic_summary}")
    print(f" Style Summary: {style_summary}")
    print(f"=======================================================\n")

    return result


def main():
    parser = argparse.ArgumentParser(description="Edit Analyzer - Video editing analysis CLI")
    parser.add_argument("video_path", help="Path to input video file")
    parser.add_argument("--output-dir", default="data", help="Output directory for job results (default: data)")
    parser.add_argument("--no-report", action="store_true", help="Skip rendering HTML report")

    args = parser.parse_args()

    try:
        run_pipeline(args.video_path, args.output_dir, generate_report=not args.no_report)
    except Exception as e:
        sys.stderr.write(f"\nPipeline Error: {e}\n")
        sys.exit(1)



if __name__ == "__main__":
    main()
