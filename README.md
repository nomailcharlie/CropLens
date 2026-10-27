# CropLens Agent

**Explainable crop-leaf visual anomaly screening** powered by real OpenCV 5
computer vision and a deterministic, inspectable agentic loop.

CropLens Agent is a competition-ready tool for farmers and agronomists. It
detects visible color/texture anomalies on leaves and flags image-quality
problems — and it is explicit that it **screens, it does not diagnose**.

---

## What it does

- Accepts **JPG, PNG, and MP4** uploads (drag-and-drop or sample mode).
- Runs **real OpenCV image processing** on a Python FastAPI backend:
  sharpness (variance of Laplacian), brightness, HSV green-leaf masks,
  connected components, yellow/brown anomaly candidates, morphological
  filtering, and contour measurement.
- Runs a **deterministic agentic state machine**: measure quality → branch on
  quality/coverage → optionally re-analyze with adjusted parameters → decide.
  Every step is recorded in a decision trace.
- Returns annotated images (leaf mask + anomaly contours), image-quality
  indicators, anomaly-area percentage, severity per region, a recommended next
  action, and explicit limitations.
- Includes a **reproducible evaluation suite** with synthetic leaves that have
  known anomaly masks, plus a failure-case gallery.
- Deploys to **AWS Lambda as a container image** with OpenCV 5 inside.

## Architecture

```
React (Vite + TS + Tailwind)  ──HTTP──▶  FastAPI (Python)  ──▶  OpenCV 5
  drag-drop upload                      agentic loop         real CV
  before/after compare                  decision trace       masks + contours
  evaluation panel                      quality + limits      annotation
        │                                                      │
        │              AWS Lambda container image              │
        └────────────  (Python 3.12 + opencv-headless 5) ─────┘
```

See `docs/ARCHITECTURE.md` for the full Mermaid diagram source and component
breakdown.

## Quick start (local)

### 1. Backend (Python + OpenCV 5)

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

Verify OpenCV 5:
```bash
python3 -c "import cv2; assert cv2.__version__.startswith('5'); print(cv2.__version__)"
```

### 2. Frontend (React + Vite)

```bash
# from project root
npm install
npm run dev
```

The dev server proxies `/api → http://localhost:8080` (see `vite.config.ts`),
so leave `VITE_API_BASE_URL` blank for local development. To point at a
deployed backend instead, set it in `.env`:

```bash
cp .env.example .env
# edit .env:  VITE_API_BASE_URL=https://your-lambda-url.on.aws
```

Open the app — the header shows the live OpenCV version and connection status.

## Using the app

1. **Upload** a leaf photo (or short MP4) via drag-and-drop, or click a
   **sample** synthetic leaf.
2. Watch the **analysis progress** — the backend runs the agentic loop.
3. Compare your original with the **annotated result** using the slider.
4. Switch between **Annotated / Leaf mask / Anomaly mask** overlays.
5. Check **image-quality indicators** (focus, exposure, leaf coverage).
6. Read the **anomaly-area percentage** and per-region severity.
7. Open the **decision trace** to see which branch the agent took and why.
8. Read the **recommended next action** and **limitations**.
9. Open the **Evaluation panel** and run the synthetic suite for measured
   precision/recall/IoU numbers (CSV download available).

## Evaluation

The evaluation harness generates synthetic leaves with known anomaly masks at
four severity levels (none/mild/moderate/severe) and four degradation types
(clean/noise/blur/dark), then runs the real pipeline and compares the computed
anomaly mask against the ground-truth mask.

```bash
cd backend
PYTHONPATH=. python3 -m app.evaluate --out results
# -> results/evaluation.json + results/evaluation.csv
```

From the UI: open the **Evaluation panel** → **Run synthetic suite** →
**CSV** to download.

> All evaluation cases are **synthetic** and labeled separately from real
> photographs. Metrics are computed from real OpenCV runs — no numbers are
> invented.

### Testing real photos

1. Upload a real leaf photo through the dashboard.
2. The annotated result, quality flags, and decision trace show what the
   pipeline measured.
3. For ground truth, manually outline anomalous regions in an image editor,
   save as a white-on-black mask, and compare against the `anomaly_mask_b64`
   using the same IoU computation in `app/evaluate.py`.

## Backend tests

```bash
cd backend
PYTHONPATH=. python3 -m pytest -q
```

## Deploy to AWS

See **`DEPLOY_AWS.md`** for exact commands (ECR push, Lambda create, Function
URL, CORS, logs). Do not consider AWS deployment complete until you have
configured credentials and a live endpoint.

## Tech stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, lucide-react |
| Backend | Python 3.12, FastAPI, OpenCV 5 (`opencv-python-headless==5.0.0.93`), numpy |
| AWS | Lambda container image (Python 3.12 base), ECR, Function URL |
| Tests | pytest (backend), `npm run build` + `typecheck` (frontend) |

## Project layout

```
.
├── src/                      React frontend
│   ├── App.tsx               dashboard (upload, results, eval)
│   ├── api.ts                backend client (VITE_API_BASE_URL)
│   ├── types.ts              shared types (mirror Pydantic schemas)
│   ├── hooks.ts              connection health, abortable fetch
│   └── components/           Banner, BeforeAfter, DecisionTrace, UploadZone, EvaluationPanel
├── backend/
│   ├── app/
│   │   ├── main.py           FastAPI app + Lambda handler (Mangum)
│   │   ├── vision.py         OpenCV pipeline (real measurements)
│   │   ├── agent.py          deterministic agentic state machine
│   │   ├── evaluate.py       synthetic evaluation harness
│   │   ├── samples.py        synthetic sample-leaf generator
│   │   └── schemas.py        Pydantic models
│   ├── tests/                pytest suite
│   ├── Dockerfile            AWS Lambda container image
│   └── requirements.txt      pinned deps (OpenCV 5)
├── docs/
│   ├── ARCHITECTURE.md       Mermaid diagram + component breakdown
│   ├── TECHNICAL_REPORT.md   impact, users, OpenCV 5, AWS, eval, privacy
│   └── DEMO_GUIDE.md         step-by-step demo script
├── DEPLOY_AWS.md             exact AWS deployment commands
└── README.md                 this file
```

## Responsible use

CropLens Agent is a **screening aid**, not a diagnostic or a treatment
recommender. Yellow/brown flags can be caused by disease, nutrient stress,
senescence, water damage, or capture artifacts. Always confirm flagged regions
with a qualified agronomist or lab test. Do not use as the sole basis for
crop-management decisions. By default no images are stored.
