"""OpenCV-generated synthetic sample leaves for the demo / sample-image mode.

These are clearly synthetic (procedural shapes, no real plant photos). They are
used by the frontend's "Try a sample" feature so the app is usable without a
user upload. The real evaluation generator lives in `evaluation/`.
"""
from __future__ import annotations

import base64
import math
import random

import cv2
import numpy as np


def _leaf_shape(h: int, w: int) -> np.ndarray:
    """Draw a roughly leaf-shaped filled ellipse with a serrated edge."""
    cx, cy = w // 2, h // 2
    leaf_mask = np.zeros((h, w), np.uint8)
    cv2.ellipse(leaf_mask, (cx, cy), (int(w * 0.36), int(h * 0.42)), 20, 0, 360, 255, -1)
    # pointed tips
    cv2.fillConvexPoly(leaf_mask, np.array([[cx, 4], [cx - 40, cy - 80], [cx + 40, cy - 80]]), 255)
    cv2.fillConvexPoly(leaf_mask, np.array([[cx, h - 4], [cx - 40, cy + 80], [cx + 40, cy + 80]]), 255)
    return leaf_mask


def _veins(img: np.ndarray, mask: np.ndarray) -> None:
    h, w = img.shape[:2]
    cx, cy = w // 2, h // 2
    darker = (40, 90, 55)
    cv2.line(img, (cx, 10), (cx, h - 10), darker, 2, cv2.LINE_AA)
    for frac in (-0.30, -0.15, 0.15, 0.30):
        y = int(cy + frac * h)
        cv2.line(img, (cx, y), (int(cx + w * 0.30), y + int(40 * (1 if frac < 0 else -1))), darker, 1, cv2.LINE_AA)
        cv2.line(img, (cx, y), (int(cx - w * 0.30), y + int(40 * (1 if frac < 0 else -1))), darker, 1, cv2.LINE_AA)
    img[mask == 0] = 0


def _add_anomaly(img: np.ndarray, mask: np.ndarray, severity: str, rng: random.Random) -> None:
    h, w = img.shape[:2]
    if severity == "none":
        return
    n_spots = {"mild": 2, "moderate": 4, "severe": 7}[severity]
    radius_range = {"mild": (12, 22), "moderate": (18, 34), "severe": (24, 48)}[severity]
    ys, xs = np.where(mask > 0)
    if len(xs) == 0:
        return
    for _ in range(n_spots):
        i = rng.randrange(len(xs))
        cx, cy = int(xs[i]), int(ys[i])
        r = rng.randint(*radius_range)
        col_choice = rng.random()
        if col_choice < 0.5:
            color = (40, 120, 200)  # brown BGR
        else:
            color = (40, 210, 220)  # yellow BGR
        cv2.circle(img, (cx, cy), r, color, -1, cv2.LINE_AA)
        # soft edge
        cv2.circle(img, (cx, cy), r + 4, color, 2, cv2.LINE_AA)


def make_sample(severity: str = "mild", seed: int | None = None, h: int = 480, w: int = 480) -> bytes:
    """Return JPEG bytes of a synthetic leaf with a known anomaly severity."""
    rng = random.Random(seed)
    mask = _leaf_shape(h, w)
    # base healthy green with subtle variation
    img = np.full((h, w, 3), (60, 130, 70), np.uint8)  # BGR
    noise = (np.random.RandomState(seed).rand(h, w, 3) * 20 - 10).astype(np.int16)
    img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    img[mask == 0] = (238, 230, 218)  # warm neutral background
    _veins(img, mask)
    _add_anomaly(img, mask, severity, rng)
    # mild shading
    overlay = img.copy()
    cv2.circle(overlay, (w // 2, h // 3), int(w * 0.5), (255, 255, 255), -1)
    cv2.addWeighted(overlay, 0.08, img, 0.92, 0, dst=img)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 88])
    if not ok:
        raise RuntimeError("sample encode failed")
    return buf.tobytes()


def make_sample_b64(severity: str = "mild", seed: int = 1) -> str:
    return base64.b64encode(make_sample(severity, seed)).decode("ascii")


SAMPLE_CATALOG = [
    {"id": "healthy", "label": "Healthy leaf", "severity": "none", "seed": 11},
    {"id": "mild", "label": "Mild anomaly", "severity": "mild", "seed": 21},
    {"id": "moderate", "label": "Moderate anomaly", "severity": "moderate", "seed": 31},
    {"id": "severe", "label": "Severe anomaly", "severity": "severe", "seed": 41},
    {"id": "blurry", "label": "Poor focus (blurry)", "severity": "moderate", "seed": 51, "blur": True},
    {"id": "dark", "label": "Poor exposure (dark)", "severity": "mild", "seed": 61, "dark": True},
]


def make_sample_by_id(sample_id: str) -> bytes:
    entry = next((s for s in SAMPLE_CATALOG if s["id"] == sample_id), SAMPLE_CATALOG[1])
    data = make_sample(entry["severity"], entry.get("seed", 1))
    arr = np.frombuffer(data, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if entry.get("blur"):
        img = cv2.GaussianBlur(img, (31, 31), 8)
    if entry.get("dark"):
        img = (img.astype(np.float32) * 0.35).clip(0, 255).astype(np.uint8)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 86])
    return buf.tobytes()
