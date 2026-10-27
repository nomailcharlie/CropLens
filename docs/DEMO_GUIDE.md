# CropLens Agent — Demo Guide

A step-by-step script for demonstrating CropLens Agent to a competition judge
or audience. Assumes the backend is running (locally or on AWS) and the
frontend is open.

## Setup (1 minute)

1. Confirm the header pill reads **"Online"** and shows **OpenCV 5.x**.
   - This proves the real OpenCV backend is connected.
   - If it shows "Offline", start the backend or set `VITE_API_BASE_URL`.
2. Point out the tagline: *"Explainable crop-leaf anomaly screening"* —
   screening, not diagnosis.

## Demo flow

### 1. Sample mode — healthy leaf (30 seconds)

- Click the **"Healthy leaf"** sample card.
- Watch the progress bar, then the results appear.
- **Result**: action = *No significant anomalies*, anomaly area ≈ 0%.
- Open the **Decision trace**: show pass 1 measured good quality, no second
  pass was needed, final = accept.
- Switch the image toggle to **Leaf mask** to show the green-leaf detection.

### 2. Sample mode — severe anomaly (45 seconds)

- Click the **"Severe anomaly"** sample card.
- **Result**: action = *Human review recommended*, anomaly area ≈ 6%.
- Use the **before/after slider** to compare the original synthetic leaf with
  the annotated one (orange anomaly contours + green leaf bbox).
- Switch to **Anomaly mask** to show the isolated yellow/brown regions.
- Show the **Detected regions** list with per-region severity.
- Open the **Decision trace**: show the final branch fired because anomaly area
  ≥ 5% (the review threshold).

### 3. Image-quality failure cases (45 seconds)

- Click the **"Poor focus (blurry)"** sample.
- **Result**: action = *Recapture recommended*. The quality bars show low
  sharpness; the "Focus" chip is amber.
- Trace shows the `recapture` branch — the agent refused to analyze a bad image
  rather than producing unreliable results.
- Click the **"Poor exposure (dark)"** sample → same recapture behavior, but
  triggered by brightness.

### 4. Upload a real photo (1 minute)

- Drag a real leaf photo (JPG/PNG) onto the upload zone.
- Walk through the same result panels on a real image.
- Emphasize: the annotated image, masks, measurements, and trace are all
  computed by OpenCV on the backend — nothing is hardcoded.

### 5. Video input (optional, 30 seconds)

- Drag a short MP4 of a leaf onto the upload zone.
- Note the result shows `Video frame N · M sampled` — OpenCV sampled frames
  server-side and analyzed a representative one.

### 6. Evaluation panel (1 minute)

- Scroll to the **Evaluation panel** → click **Run synthetic suite**.
- While it runs, explain: these are synthetic leaves with known anomaly masks;
  the harness compares the computed mask to ground truth.
- Show the summary cards (IoU, precision, recall, accept rate per severity)
  and the per-case table.
- Click **CSV** to download the machine-readable results.
- Emphasize the amber banner: synthetic cases are labeled separately from real
  photos, and the numbers are measured, not invented.

### 7. Limitations & responsible use (30 seconds)

- Open the **Limitations** section at the bottom of a result.
- Read the first bullet: *"visual anomaly screening only; it does not diagnose
  disease…"* — this is the responsible-use commitment.

## Talking points

- **Real OpenCV 5**: every measurement is computed from pixels — sharpness via
  Laplacian variance, leaf via HSV masking + morphology, anomalies via
  yellow/brown contours restricted to the leaf area.
- **Agentic, not fixed**: the second pass only runs when pass 1 is uncertain,
  and is only adopted if it improved leaf coverage. The trace proves this.
- **Deployable**: the same code runs locally on uvicorn and on AWS Lambda as a
  container image with OpenCV 5 inside.
- **Honest**: it says what it can't do, refuses bad images, and never claims a
  diagnosis.

## Q&A prep

- *"Is this AI/ML?"* — It's a deterministic computer-vision pipeline with an
  inspectable state machine. No model training; the "agentic" part is the
  conditional, measurement-driven control flow.
- *"How accurate is it?"* — Run the evaluation panel; the measured IoU/precision/
  recall numbers are shown. On synthetic leaves with clean capture, IoU is
  ~0.4. Real-photo accuracy requires a labeled dataset (instructions in README).
- *"Where does the image go?"* — Nowhere permanently. Decoded in memory,
  analyzed, returned in the response, discarded. No S3, no database by default.
- *"How do I deploy it?"* — See `DEPLOY_AWS.md`; it's a container image push to
  ECR + Lambda create + Function URL.
