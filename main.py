"""
Sales Pace — FastAPI backend.

Single endpoint: POST /analyze
  - Accepts an uploaded Excel file (the sales vs target report).
  - Runs the analyzer + summarizer.
  - Returns the full result as JSON.

The frontend (index.html) is served from the app/static/ folder.
"""

import os
import shutil
import uuid
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.analyzer import analyze_report
from app.summarizer import summarize

# Folder where uploaded files are temporarily stored.
UPLOAD_DIR = Path("app/data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Sales Pace", version="1.0")

# Serve the frontend from app/static/
STATIC_DIR = Path("app/static")
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def serve_frontend():
    """Serve the main HTML page."""
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Frontend not found.")
    return FileResponse(index_path)


@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    """
    Accept an uploaded Excel report, run analysis, return results as JSON.

    Steps:
      1. Save the uploaded file to a temp path with a unique name.
      2. Run analyzer.analyze_report() on it.
      3. Run summarizer.summarize() on the analysis.
      4. Delete the temp file.
      5. Return combined result.
    """
    # Validate file type.
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(
            status_code=400,
            detail="Only .xlsx or .xls files are accepted."
        )

    # Save to a unique temp path so concurrent uploads don't collide.
    temp_path = UPLOAD_DIR / f"{uuid.uuid4().hex}_{file.filename}"

    try:
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        analysis = analyze_report(temp_path)
        summary = summarize(analysis)

    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
    finally:
        # Always delete the temp file — never store client data on disk.
        if temp_path.exists():
            temp_path.unlink()

    return {
        "period": analysis["period"],
        "overall": analysis["overall"],
        "by_segment": analysis["by_segment"],
        "by_route": analysis["by_route"],
        "by_mde": analysis["by_mde"],
        "by_flavour": analysis["by_flavour"],
        "zero_sale_with_target": analysis["zero_sale_with_target"],
        "summary": summary,
    }


@app.get("/health")
def health():
    return {"status": "ok"}