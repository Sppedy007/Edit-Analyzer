"""
Phase 3 FastAPI Web Application for Edit Analyzer.
Provides video upload endpoint and local job browser.
"""

import os
import json
import shutil
import uuid
from typing import List, Dict, Any
from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader

from cli import run_pipeline
from edit_analyzer.report import render_report


app = FastAPI(title="Edit Analyzer Web Wrapper", version="1.0.0")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
UPLOADS_DIR = os.path.join(DATA_DIR, "uploads")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)

jinja_env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=True)


def get_past_jobs() -> List[Dict[str, Any]]:
    """
    Scan data/ directory for past job runs containing result.json.
    Returns list of job summary dicts ordered by generated timestamp descending.
    """
    jobs = []
    if not os.path.exists(DATA_DIR):
        return []

    for item in os.listdir(DATA_DIR):
        job_dir = os.path.join(DATA_DIR, item)
        if os.path.isdir(job_dir) and item.startswith("job_"):
            result_json_path = os.path.join(job_dir, "result.json")
            if os.path.isfile(result_json_path):
                try:
                    with open(result_json_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    
                    jobs.append({
                        "job_id": data.get("job_id", item),
                        "source_filename": data.get("source_filename", "Unknown"),
                        "duration_seconds": data.get("duration_seconds", 0.0),
                        "shots_count": len(data.get("shots", [])),
                        "generated_at": data.get("generated_at", ""),
                    })
                except Exception:
                    pass

    # Sort by generated_at timestamp descending
    jobs.sort(key=lambda x: x["generated_at"], reverse=True)
    return jobs


@app.get("/", response_class=HTMLResponse)
async def index_page(request: Request):
    """
    Dashboard page listing upload dropzone and past job reports.
    """
    jobs = get_past_jobs()
    template = jinja_env.get_template("index.html.j2")
    html_content = template.render(jobs=jobs)
    return HTMLResponse(content=html_content)


@app.post("/analyze")
async def analyze_video(file: UploadFile = File(...)):
    """
    Upload a video file, execute the edit analysis pipeline, and return report URL.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file selected.")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in [".mp4", ".mov", ".avi", ".mkv", ".webm"]:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format '{ext}'. Please upload an MP4, MOV, AVI, or MKV video.",
        )

    # Save uploaded file to temp uploads directory
    temp_filename = f"upload_{uuid.uuid4().hex[:8]}{ext}"
    temp_path = os.path.join(UPLOADS_DIR, temp_filename)

    try:
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Run pipeline
        result = run_pipeline(temp_path, output_base_dir=DATA_DIR, generate_report=True)
        job_id = result.job_id

        return JSONResponse({
            "status": "success",
            "job_id": job_id,
            "report_url": f"/jobs/{job_id}",
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        # Clean up temporary uploaded file
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


@app.get("/jobs/{job_id}", response_class=HTMLResponse)
async def view_report(job_id: str):
    """
    Serve the HTML report for a job ID.
    """
    job_dir = os.path.join(DATA_DIR, job_id)
    if not os.path.isdir(job_dir):
        raise HTTPException(status_code=404, detail="Job directory not found.")

    report_path = os.path.join(job_dir, "report.html")
    result_path = os.path.join(job_dir, "result.json")

    # Render report on the fly if missing but result.json is present
    if not os.path.isfile(report_path):
        if os.path.isfile(result_path):
            render_report(result_path, report_path)
        else:
            raise HTTPException(status_code=404, detail="Report not found.")

    with open(report_path, "r", encoding="utf-8") as f:
        content = f.read()

    return HTMLResponse(content=content)


@app.get("/jobs/{job_id}/json")
async def get_job_json(job_id: str):
    """
    Serve result.json for a job ID.
    """
    job_dir = os.path.join(DATA_DIR, job_id)
    result_path = os.path.join(job_dir, "result.json")
    if not os.path.isfile(result_path):
        raise HTTPException(status_code=404, detail="JSON result not found.")
    return FileResponse(result_path, media_type="application/json")


@app.get("/jobs/{job_id}/audio")
async def get_job_audio(job_id: str):
    """
    Serve audio.wav for a job ID if present.
    """
    audio_path = os.path.join(DATA_DIR, job_id, "audio.wav")
    if not os.path.isfile(audio_path):
        raise HTTPException(status_code=404, detail="Audio file not found.")
    return FileResponse(audio_path, media_type="audio/wav")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("web:app", host="127.0.0.1", port=8000, reload=True)
