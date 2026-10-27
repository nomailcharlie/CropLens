# CropLens Agent — Backend (Python / FastAPI / AWS Lambda)

Explainable crop-leaf visual anomaly screening powered by **OpenCV 5** (`opencv-python-headless==5.0.0.93`).

The vision pipeline runs **real OpenCV image processing** (sharpness, brightness, HSV leaf masks, connected components, yellow/brown candidate regions, morphology, contours) inside a deterministic, inspectable agentic state machine. No results are hardcoded.

## Run locally

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 -c "import cv2; assert cv2.__version__.startswith('5'), cv2.__version__; print('OpenCV', cv2.__version__)"
uvicorn app.main:app --host 0.0.0.0 --port 8080
# Health: http://localhost:8080/health
# Analyze: POST http://localhost:8080/analyze  (multipart file)
```

Set the frontend `VITE_API_BASE_URL` to `http://localhost:8080` (or leave blank to use the Vite dev proxy `/api -> localhost:8080`).

## AWS deployment (Lambda container image)

See `DEPLOY_AWS.md` in the project root for exact commands, Function URL setup, CORS, timeouts, and log inspection.

## Layout

```
backend/
  app/
    main.py            FastAPI app + Lambda adapter (Mangum-style)
    vision.py          OpenCV pipeline (sharpness, masks, contours, annotation)
    agent.py           Deterministic agentic state machine + decision trace
    schemas.py         Pydantic models for request/response
    samples.py         Optional bundled sample-image generator (OpenCV synthetic)
  requirements.txt     Pinned dependencies (OpenCV 5)
  Dockerfile           AWS Lambda container image (Python 3.12)
  tests/               Pytest: pipeline + agentic loop + API
```

## Limitations (also returned by every analysis)

CropLens Agent is a **visual anomaly screening tool**, not a disease diagnostic.
It flags color/texture regions that differ from healthy green leaf tissue and
reports image-quality problems. It cannot identify pathogens, nutrient causes,
or recommend treatment. Always confirm flagged regions with a qualified
agronomist or lab diagnosis.
