"""Real OpenCV vision pipeline for CropLens Agent.

No hardcoded results. Every measurement is computed from the input pixels with
OpenCV 5 (`opencv-python-headless==5.0.0.93`).

Pipeline steps per frame/image:
  1. Sharpness   -> variance of Laplacian
  2. Brightness  -> mean V channel
  3. Leaf mask   -> HSV green candidate + morphology
  4. Connected components on leaf mask -> leaf coverage, largest component bbox
  5. Anomaly candidates -> yellow/brown HSV ranges *inside* leaf mask,
     morphological open/close to suppress isolated noise
  6. Contours on anomaly mask -> measurable regions (area, bbox, mean HSV)
  7. Annotation -> draw contours + bbox + text on a copy of the frame
"""
from __future__ import annotations

import base64
from dataclasses import dataclass, field
from typing import Optional

import cv2
import numpy as np

# Guard: spec requires OpenCV 5.
assert cv2.__version__.startswith("5"), (
    f"CropLens Agent requires OpenCV 5.x; found {cv2.__version__}. "
    "Install opencv-python-headless==5.0.0.93."
)

OPENCV_VERSION: str = cv2.__version__


# ---- Tunable parameters (the agent adjusts these between passes) -------------

@dataclass
class VisionParams:
    """Parameters that may change between agentic passes."""
    # Sharpness threshold for "in focus" (variance of Laplacian)
    sharpness_threshold: float = 100.0
    # Brightness bounds
    brightness_low: float = 45.0
    brightness_high: float = 210.0
    # HSV green-leaf range (H: 0-179 in OpenCV)
    green_h_low: int = 25
    green_h_high: int = 90
    green_s_low: int = 35
    green_v_low: int = 35
    # Morphology kernel size (px)
    leaf_kernel: int = 7
    anomaly_kernel: int = 5
    # Minimum region area to keep (as fraction of leaf area)
    min_region_frac: float = 0.002
    # Whether to apply CLAHE illumination normalization before detection
    normalize_illumination: bool = False
    # Anomaly HSV ranges (yellow/brown/necrotic)
    yellow_h_low: int = 18
    yellow_h_high: int = 32
    yellow_s_low: int = 60
    brown_h_low: int = 8
    brown_h_high: int = 22
    brown_s_low: int = 50
    brown_v_high: int = 170


@dataclass
class QualityResult:
    sharpness: float
    brightness: float
    leaf_coverage: float
    sharpness_flag: str
    brightness_flag: str
    leaf_coverage_flag: str


@dataclass
class Region:
    label: str
    area_px: int
    area_pct: float
    bbox: list[int]
    mean_color_hsv: list[float]
    severity: str


@dataclass
class VisionOutput:
    quality: QualityResult
    leaf_area_px: int
    anomaly_area_px: int
    anomaly_area_pct: float
    regions: list[Region] = field(default_factory=list)
    annotated: Optional[np.ndarray] = None
    leaf_mask: Optional[np.ndarray] = None
    anomaly_mask: Optional[np.ndarray] = None
    notes: list[str] = field(default_factory=list)


# ---- Helpers ----------------------------------------------------------------

def _bgr_to_hsv(img: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(img, cv2.COLOR_BGR2HSV)


def _claque_normalize(img: np.ndarray) -> np.ndarray:
    """CLAHE on L channel of LAB to reduce illumination variation."""
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l = clahe.apply(l)
    return cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)


def _mask_blobs(mask: np.ndarray, kernel: int, open_iters: int = 1, close_iters: int = 2) -> np.ndarray:
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel, kernel))
    m = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k, iterations=open_iters)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, k, iterations=close_iters)
    return m


def _encode_jpeg_b64(img: np.ndarray, max_dim: int = 1024) -> str:
    """Resize for transport, JPEG-encode, base64."""
    if img is None:
        return ""
    h, w = img.shape[:2]
    scale = min(1.0, max_dim / max(h, w))
    if scale < 1.0:
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 82])
    if not ok:
        return ""
    return base64.b64encode(buf.tobytes()).decode("ascii")


def overlay_mask_on(image: np.ndarray, mask: np.ndarray, color: tuple[int, int, int], alpha: float = 0.45) -> np.ndarray:
    """Tint `image` where `mask` is non-zero."""
    if mask is None or image is None:
        return image
    color_layer = np.zeros_like(image)
    color_layer[mask > 0] = color
    return cv2.addWeighted(image, 1.0, color_layer, alpha, 0.0)


# ---- Core analysis ----------------------------------------------------------

def analyze_frame(bgr: np.ndarray, params: VisionParams) -> VisionOutput:
    """Run the full OpenCV pipeline on a single BGR frame."""
    if bgr is None or bgr.size == 0:
        raise ValueError("Empty frame passed to analyze_frame")

    notes: list[str] = []

    work = bgr.copy()
    if params.normalize_illumination:
        work = _claque_normalize(work)

    # 1. Sharpness — variance of Laplacian on grayscale
    gray = cv2.cvtColor(work, cv2.COLOR_BGR2GRAY)
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())

    # 2. Brightness — mean of V channel
    hsv = _bgr_to_hsv(work)
    brightness = float(hsv[:, :, 2].mean())

    # 3. Leaf mask — green candidate in HSV
    green_lower = np.array([params.green_h_low, params.green_s_low, params.green_v_low], np.uint8)
    green_upper = np.array([params.green_h_high, 255, 255], np.uint8)
    leaf_raw = cv2.inRange(hsv, green_lower, green_upper)
    leaf_mask = _mask_blobs(leaf_raw, params.leaf_kernel, open_iters=1, close_iters=2)

    # 4. Connected components on leaf mask
    n_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(leaf_mask, connectivity=8)
    leaf_area_px = int(leaf_mask.sum() // 255)
    total_px = leaf_mask.shape[0] * leaf_mask.shape[1]
    leaf_coverage = leaf_area_px / total_px if total_px else 0.0

    # Pick the largest non-background component as the primary leaf bbox
    primary_bbox: list[int] = [0, 0, 0, 0]
    if n_labels > 1:
        comp_idx = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        primary_bbox = [
            int(stats[comp_idx, cv2.CC_STAT_LEFT]),
            int(stats[comp_idx, cv2.CC_STAT_TOP]),
            int(stats[comp_idx, cv2.CC_STAT_WIDTH]),
            int(stats[comp_idx, cv2.CC_STAT_HEIGHT]),
        ]

    # 5. Anomaly candidates — yellow + brown inside leaf mask
    yellow_lower = np.array([params.yellow_h_low, params.yellow_s_low, 60], np.uint8)
    yellow_upper = np.array([params.yellow_h_high, 255, 255], np.uint8)
    yellow = cv2.inRange(hsv, yellow_lower, yellow_upper)

    brown_lower = np.array([params.brown_h_low, params.brown_s_low, 30], np.uint8)
    brown_upper = np.array([params.brown_h_high, 255, params.brown_v_high], np.uint8)
    brown = cv2.inRange(hsv, brown_lower, brown_upper)

    anomaly_raw = cv2.bitwise_or(yellow, brown)
    # Restrict to leaf area only
    anomaly_raw = cv2.bitwise_and(anomaly_raw, leaf_mask)
    anomaly_mask = _mask_blobs(anomaly_raw, params.anomaly_kernel, open_iters=1, close_iters=1)
    anomaly_mask = cv2.bitwise_and(anomaly_mask, leaf_mask)

    # 6. Contours -> measurable regions
    regions: list[Region] = []
    min_area = max(15.0, params.min_region_frac * max(leaf_area_px, 1))
    contours, _ = cv2.findContours(anomaly_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    # Sort largest first
    contours = sorted(contours, key=lambda c: cv2.contourArea(c), reverse=True)

    anomaly_area_px = 0
    for cnt in contours:
        area = float(cv2.contourArea(cnt))
        if area < min_area:
            continue
        x, y, w, h = cv2.boundingRect(cnt)
        # mean HSV inside the contour region (within leaf)
        mask_slice = np.zeros(anomaly_mask.shape[:2], np.uint8)
        cv2.drawContours(mask_slice, [cnt], -1, 255, -1)
        mean_h = float(np.mean(hsv[:, :, 0][mask_slice > 0])) if mask_slice.any() else 0.0
        mean_s = float(np.mean(hsv[:, :, 1][mask_slice > 0])) if mask_slice.any() else 0.0
        mean_v = float(np.mean(hsv[:, :, 2][mask_slice > 0])) if mask_slice.any() else 0.0
        area_pct = area / max(leaf_area_px, 1)
        # Severity from area fraction + saturation (browner/darker => higher)
        sev = _severity(area_pct, mean_s, mean_v)
        label = _label_for_hsv(mean_h, mean_s, mean_v)
        regions.append(Region(
            label=label,
            area_px=int(area),
            area_pct=area_pct,
            bbox=[int(x), int(y), int(w), int(h)],
            mean_color_hsv=[mean_h, mean_s, mean_v],
            severity=sev,
        ))
        anomaly_area_px += int(area)

    anomaly_area_pct = anomaly_area_px / max(leaf_area_px, 1)

    # 7. Annotated image
    annotated = bgr.copy()
    # leaf overlay (green tint)
    annotated = overlay_mask_on(annotated, leaf_mask, (62, 118, 80), 0.25)
    # anomaly overlay (orange/red tint)
    annotated = overlay_mask_on(annotated, anomaly_mask, (0, 60, 200), 0.55)
    # contour outlines
    cv2.drawContours(annotated, [c for c in contours if cv2.contourArea(c) >= min_area], -1,
                     (0, 80, 230), 2, cv2.LINE_AA)
    # primary leaf bbox
    if primary_bbox[2] > 0 and primary_bbox[3] > 0:
        x, y, w, h = primary_bbox
        cv2.rectangle(annotated, (x, y), (x + w, y + h), (62, 118, 80), 2, cv2.LINE_AA)
        cv2.putText(annotated, "leaf", (x + 4, y + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                    (62, 118, 80), 1, cv2.LINE_AA)
    # HUD text
    cv2.putText(annotated, f"sharp={sharpness:.0f} bright={brightness:.0f} coverage={leaf_coverage*100:.1f}%",
                (10, annotated.shape[0] - 14), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                (20, 30, 20), 1, cv2.LINE_AA)
    cv2.putText(annotated, f"anomaly={anomaly_area_pct*100:.2f}% regions={len(regions)}",
                (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 60, 200), 1, cv2.LINE_AA)

    # Flags
    sharpness_flag = "ok" if sharpness >= params.sharpness_threshold else "poor_focus"
    if brightness < params.brightness_low:
        brightness_flag = "underexposed"
    elif brightness > params.brightness_high:
        brightness_flag = "overexposed"
    else:
        brightness_flag = "ok"
    if leaf_coverage < 0.01:
        leaf_flag = "no_leaf"
    elif leaf_coverage < 0.05:
        leaf_flag = "low_coverage"
    else:
        leaf_flag = "ok"

    quality = QualityResult(
        sharpness=sharpness,
        brightness=brightness,
        leaf_coverage=leaf_coverage,
        sharpness_flag=sharpness_flag,
        brightness_flag=brightness_flag,
        leaf_coverage_flag=leaf_flag,
    )

    if leaf_coverage < 0.01:
        notes.append("No identifiable green leaf tissue detected.")
    if sharpness_flag == "poor_focus":
        notes.append("Image may be out of focus; variance of Laplacian below threshold.")
    if brightness_flag != "ok":
        notes.append(f"Exposure flagged as {brightness_flag}.")

    return VisionOutput(
        quality=quality,
        leaf_area_px=leaf_area_px,
        anomaly_area_px=anomaly_area_px,
        anomaly_area_pct=anomaly_area_pct,
        regions=regions[:12],  # cap transport
        annotated=annotated,
        leaf_mask=leaf_mask,
        anomaly_mask=anomaly_mask,
        notes=notes,
    )


def _severity(area_pct: float, sat: float, val: float) -> str:
    score = area_pct * 100.0 + (sat / 255.0) * 10.0 + (1 - val / 255.0) * 10.0
    if score > 8.0:
        return "high"
    if score > 2.5:
        return "moderate"
    return "low"


def _label_for_hsv(h: float, s: float, v: float) -> str:
    if h < 16 and s > 60 and v < 170:
        return "brown/necrotic"
    if h < 33:
        return "yellow/chlorotic"
    return "discolored"


# ---- Video frame sampling ---------------------------------------------------

def sample_frames(cap: cv2.VideoCapture, max_frames: int = 4) -> list[tuple[int, np.ndarray]]:
    """Evenly sample up to `max_frames` frames from a video capture."""
    frames: list[tuple[int, np.ndarray]] = []
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total <= 0:
        # Fallback: read sequentially up to max
        idx = 0
        while len(frames) < max_frames:
            ok, f = cap.read()
            if not ok:
                break
            frames.append((idx, f))
            idx += 1
        return frames
    step = max(1, total // max_frames)
    for i in range(0, total, step):
        if len(frames) >= max_frames:
            break
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ok, f = cap.read()
        if ok and f is not None:
            frames.append((i, f))
    if not frames:
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        ok, f = cap.read()
        if ok and f is not None:
            frames.append((0, f))
    return frames


def decode_image(data: bytes) -> np.ndarray:
    """Decode raw bytes -> BGR ndarray via OpenCV (no file needed)."""
    arr = np.frombuffer(data, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode image. Supported: JPG, PNG.")
    return img
