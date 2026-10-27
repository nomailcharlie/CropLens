"""CropLens Agent — FastAPI application + AWS Lambda adapter.

Run locally:
    uvicorn app.main:app --host 0.0.0.0 --port 8080

AWS Lambda (container image):
    The handler is `app.main.handler` (Mangum wraps the FastAPI app).
"""
from __future__ import annotations

import io
import os
import platform
import tempfile
from typing import Optional

import cv2
import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .agent import LIMITATIONS, run_agent
from .evaluate import run_suite, write_outputs
from .samples import SAMPLE_CATALOG, make_sample_by_id
from .schemas import AnalysisResponse, HealthResponse, PassResult, QualityMeasure, RegionMeasure, TraceEvent
from .vision import OPENCV_VERSION, decode_image, sample_frames

# Spec guard
assert OPENCV_VERSION.startswith("5"), f"Requires OpenCV 5; found {OPENCV_VERSION}"

# --- Config from environment ---
ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png"}
ALLOWED_VIDEO_EXT = {".mp4"}
MAX_IMAGE_BYTES = int(os.environ.get("CROPLENS_MAX_IMAGE_MB", "12")) * 1024 * 1024
MAX_VIDEO_BYTES = int(os.environ.get("CROPLENS_MAX_VIDEO_MB", "40")) * 1024 * 1024
MAX_VIDEO_FRAMES = int(os.environ.get("CROPLENS_MAX_VIDEO_FRAMES", "4"))
ENV_NAME = os.environ.get("CROPLENS_ENV", "local")
RUNTIME = f"{platform.system()} {platform.release()} / Python {platform.python_version()} / {ENV_NAME}"

app = FastAPI(
    title="CropLens Agent",
    version="1.0.0",
    description="Explainable crop-leaf visual anomaly screening (OpenCV 5).",
)

# CORS — two modes to avoid duplicate Access-Control-Allow-Origin headers:
#  "app"    (default, local dev): FastAPI CORSMiddleware handles all CORS.
#  "lambda" (AWS deployed):       Lambda Function URL CORS config handles
#           preflight + headers; the app middleware is SKIPPED so the browser
#           never sees two Access-Control-Allow-Origin values (which it rejects).
_CORS_MODE = os.environ.get("CROPLENS_CORS_MODE", "app")
if _CORS_MODE == "app":
    _origins = os.environ.get("CROPLENS_CORS_ORIGINS", "*")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in _origins.split(",") if o.strip()],
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-Client-Info", "Apikey"],
    )


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        opencv_version=OPENCV_VERSION,
        runtime=RUNTIME,
        service="croplens-agent",
        version="1.0.0",
    )


@app.options("/analyze")
def analyze_options() -> Response:
    # Fallback preflight. In "app" mode CORSMiddleware intercepts OPTIONS before
    # this route. In "lambda" mode the Function URL CORS config handles OPTIONS
    # without invoking the function. This route is a safety net only.
    return Response(status_code=204)


@app.get("/samples")
def list_samples() -> list[dict]:
    return [{"id": s["id"], "label": s["label"], "severity": s["severity"]} for s in SAMPLE_CATALOG]


@app.get("/samples/{sample_id}")
def get_sample(sample_id: str) -> Response:
    try:
        data = make_sample_by_id(sample_id)
    except Exception as e:
        raise HTTPException(404, f"Sample not found: {e}")
    return Response(content=data, media_type="image/jpeg")


@app.post("/samples/{sample_id}/analyze", response_model=AnalysisResponse)
def analyze_sample(sample_id: str) -> AnalysisResponse:
    data = make_sample_by_id(sample_id)
    bgr = decode_image(data)
    result = run_agent(bgr)
    return _to_response(result, source_kind="image", frame_index=None, total_frames=1)


@app.get("/evaluate")
def evaluate() -> dict:
    """Run the reproducible synthetic evaluation suite and return the report."""
    import tempfile
    report = run_suite()
    # also persist to a temp dir so it's machine-readable on disk
    with tempfile.TemporaryDirectory() as d:
        write_outputs(report, d)
    return report


@app.post("/analyze", response_model=AnalysisResponse)
async def analyze(file: UploadFile = File(...)) -> AnalysisResponse:
    name = (file.filename or "").lower()
    ext = "." + name.rsplit(".", 1)[-1] if "." in name else ""

    data = await file.read()
    if not data:
        raise HTTPException(400, "Empty file upload.")

    is_video = ext in ALLOWED_VIDEO_EXT
    is_image = ext in ALLOWED_IMAGE_EXT

    if not (is_video or is_image):
        raise HTTPException(
            415,
            f"Unsupported file type '{ext or '(none)'}'. Allowed: JPG, PNG, MP4.",
        )
    if is_image and len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(413, f"Image too large (max {MAX_IMAGE_BYTES//1024//1024} MB).")
    if is_video and len(data) > MAX_VIDEO_BYTES:
        raise HTTPException(413, f"Video too large (max {MAX_VIDEO_BYTES//1024//1024} MB).")

    if is_image:
        return _analyze_image(data, ext)
    return _analyze_video(data)


def _analyze_image(data: bytes, ext: str) -> AnalysisResponse:
    try:
        bgr = decode_image(data)
    except ValueError as e:
        raise HTTPException(400, str(e))

    result = run_agent(bgr)
    return _to_response(result, source_kind="image", frame_index=None, total_frames=1)


def _analyze_video(data: bytes) -> AnalysisResponse:
    # Write to a temp file for cv2.VideoCapture
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name
    try:
        cap = cv2.VideoCapture(tmp_path)
        if not cap.isOpened():
            raise HTTPException(400, "Could not open video. Ensure it is a valid MP4.")
        frames = sample_frames(cap, MAX_VIDEO_FRAMES)
        cap.release()
        if not frames:
            raise HTTPException(400, "No frames could be decoded from the video.")
        # Analyze the middle sampled frame as the representative; include count.
        idx = len(frames) // 2
        frame_index, bgr = frames[idx]
        result = run_agent(bgr)
        return _to_response(result, source_kind="video_frame", frame_index=int(frame_index),
                            total_frames=len(frames))
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


def _to_response(result, source_kind: str, frame_index: Optional[int], total_frames: int) -> AnalysisResponse:
    q = result.quality.quality
    passes = [
        PassResult(
            pass_id=p["pass_id"],
            trigger=p["trigger"],
            parameters=p["parameters"],
            quality=QualityMeasure(**p["quality"]),
            leaf_area_px=p["leaf_area_px"],
            anomaly_area_px=p["anomaly_area_px"],
            anomaly_area_pct=p["anomaly_area_pct"],
            regions=[RegionMeasure(**r) for r in p["regions"]],
            annotated_b64=p["annotated_b64"],
            leaf_mask_b64=p["leaf_mask_b64"],
            anomaly_mask_b64=p["anomaly_mask_b64"],
            notes=p["notes"],
        )
        for p in result.passes
    ]
    return AnalysisResponse(
        ok=True,
        opencv_version=OPENCV_VERSION,
        runtime=RUNTIME,
        source_kind=source_kind,
        frame_index=frame_index,
        total_frames_sampled=total_frames,
        quality=QualityMeasure(
            sharpness=q.sharpness,
            sharpness_flag=q.sharpness_flag,
            brightness=q.brightness,
            brightness_flag=q.brightness_flag,
            leaf_coverage=q.leaf_coverage,
            leaf_coverage_flag=q.leaf_coverage_flag,
        ),
        leaf_area_px=result.quality.leaf_area_px,
        anomaly_area_px=result.quality.anomaly_area_px,
        anomaly_area_pct=result.quality.anomaly_area_pct,
        regions=[RegionMeasure(**_region_clean(r)) for r in result.quality.regions],
        annotated_b64=passes[-1].annotated_b64,
        leaf_mask_b64=passes[-1].leaf_mask_b64,
        anomaly_mask_b64=passes[-1].anomaly_mask_b64,
        passes=passes,
        trace=[TraceEvent(step=t.step, branch=t.branch, reason=t.reason, data=t.data) for t in result.trace],
        final_action=result.final_action,  # type: ignore[arg-type]
        confidence=result.confidence,  # type: ignore[arg-type]
        next_action_label=result.next_action_label,
        next_action_detail=result.next_action_detail,
        limitations=LIMITATIONS,
    )


def _region_clean(r) -> dict:
    from dataclasses import asdict
    d = asdict(r)
    d["area_pct"] = round(d["area_pct"], 5)
    d["mean_color_hsv"] = [round(x, 1) for x in d["mean_color_hsv"]]
    return d


# --- AWS Lambda handler (Mangum) ---
try:
    from mangum import Mangum

    handler = Mangum(app, lifespan="off")
except Exception:  # pragma: no cover - mangum may be absent in local-only
    handler = None
