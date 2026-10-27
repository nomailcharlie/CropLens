"""Reproducible evaluation harness for CropLens Agent.

Generates controlled synthetic leaf images with KNOWN anomaly masks at multiple
severity levels, plus degraded variants (noise, blur, poor exposure). Runs the
real OpenCV pipeline against each, compares the computed anomaly mask against
the known mask (IoU + precision/recall), and writes machine-readable
CSV + JSON results.

Used by:
  - backend endpoint POST /evaluate  (drives the Evaluation panel in the UI)
  - CLI:  python -m app.evaluate --out results/

Synthetic test images are clearly labeled separately from real photographs.
No benchmark numbers are invented — every metric is computed from actual runs.
"""
from __future__ import annotations

import argparse
import base64
import csv
import json
import os
import random
from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np

from .vision import OPENCV_VERSION, VisionParams, analyze_frame


@dataclass
class SyntheticCase:
    case_id: str
    severity: str          # none | mild | moderate | severe
    degradation: str       # clean | noise | blur | dark
    seed: int
    image_b64: str
    known_mask_b64: str
    known_area_pct: float


@dataclass
class EvalResult:
    case_id: str
    severity: str
    degradation: str
    seed: int
    opencv_version: str
    known_area_pct: float
    predicted_area_pct: float
    iou: float
    precision: float
    recall: float
    final_action: str
    confidence: str
    leaf_coverage: float
    sharpness: float
    brightness: float
    accepted: bool
    notes: list[str] = field(default_factory=list)


def _leaf_mask(h: int, w: int) -> np.ndarray:
    m = np.zeros((h, w), np.uint8)
    cx, cy = w // 2, h // 2
    cv2.ellipse(m, (cx, cy), (int(w * 0.36), int(h * 0.42)), 20, 0, 360, 255, -1)
    cv2.fillConvexPoly(m, np.array([[cx, 4], [cx - 40, cy - 80], [cx + 40, cy - 80]]), 255)
    cv2.fillConvexPoly(m, np.array([[cx, h - 4], [cx - 40, cy + 80], [cx + 40, cy + 80]]), 255)
    return m


def _enc(img: np.ndarray) -> str:
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not ok:
        return ""
    return base64.b64encode(buf.tobytes()).decode("ascii")


def generate_case(severity: str, degradation: str, seed: int, h: int = 480, w: int = 480) -> SyntheticCase:
    """Build a synthetic leaf with a known anomaly mask (the ground truth)."""
    rng = random.Random(seed)
    nprng = np.random.RandomState(seed)
    mask = _leaf_mask(h, w)
    img = np.full((h, w, 3), (60, 130, 70), np.uint8)
    noise = (nprng.rand(h, w, 3) * 16 - 8).astype(np.int16)
    img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    img[mask == 0] = (238, 230, 218)

    gt_mask = np.zeros((h, w), np.uint8)
    ys, xs = np.where(mask > 0)
    if severity != "none" and len(xs):
        n_spots = {"mild": 2, "moderate": 4, "severe": 7}[severity]
        radius_range = {"mild": (12, 22), "moderate": (18, 34), "severe": (24, 48)}[severity]
        for _ in range(n_spots):
            i = rng.randrange(len(xs))
            cx, cy = int(xs[i]), int(ys[i])
            r = rng.randint(*radius_range)
            color = (40, 120, 200) if rng.random() < 0.5 else (40, 210, 220)
            cv2.circle(img, (cx, cy), r, color, -1, cv2.LINE_AA)
            cv2.circle(gt_mask, (cx, cy), r, 255, -1)
    gt_mask = cv2.bitwise_and(gt_mask, mask)

    # vein lines
    darker = (40, 90, 55)
    cv2.line(img, (w // 2, 10), (w // 2, h - 10), darker, 2, cv2.LINE_AA)
    img[mask == 0] = (238, 230, 218)

    if degradation == "blur":
        img = cv2.GaussianBlur(img, (25, 25), 6)
    elif degradation == "dark":
        img = (img.astype(np.float32) * 0.4).clip(0, 255).astype(np.uint8)
    elif degradation == "noise":
        n = (nprng.rand(h, w, 3) * 50 - 25).astype(np.int16)
        img = np.clip(img.astype(np.int16) + n, 0, 255).astype(np.uint8)

    known_area_pct = float(gt_mask.sum() / max(mask.sum(), 1) / 255.0)
    return SyntheticCase(
        case_id=f"{severity}_{degradation}_{seed}",
        severity=severity,
        degradation=degradation,
        seed=seed,
        image_b64=_enc(img),
        known_mask_b64=_enc(cv2.cvtColor(gt_mask, cv2.COLOR_GRAY2BGR)),
        known_area_pct=known_area_pct,
    )


def _iou(pred: np.ndarray, gt: np.ndarray) -> tuple[float, float, float]:
    p = pred > 0
    g = gt > 0
    inter = np.logical_and(p, g).sum()
    union = np.logical_or(p, g).sum()
    iou = float(inter / union) if union else 0.0
    precision = float(inter / p.sum()) if p.any() else 0.0
    recall = float(inter / g.sum()) if g.any() else 0.0
    return iou, precision, recall


def evaluate_case(c: SyntheticCase, params: VisionParams | None = None) -> EvalResult:
    from .agent import run_agent  # local import to avoid cycle
    arr = np.frombuffer(base64.b64decode(c.image_b64), np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    result = run_agent(img)
    # Reconstruct predicted anomaly mask from the final pass for IoU
    pred_mask = np.zeros(img.shape[:2], np.uint8)
    if result.passes:
        last = result.passes[-1]
        # We don't ship the raw mask in the agent result; recompute via vision for IoU
    # Recompute mask directly for metric (single source of truth)
    out = analyze_frame(img, params or VisionParams())
    pred_mask = out.anomaly_mask if out.anomaly_mask is not None else pred_mask
    gt_arr = np.frombuffer(base64.b64decode(c.known_mask_b64), np.uint8)
    gt = cv2.imdecode(gt_arr, cv2.IMREAD_GRAYSCALE)

    iou, prec, rec = _iou(pred_mask, gt)
    return EvalResult(
        case_id=c.case_id,
        severity=c.severity,
        degradation=c.degradation,
        seed=c.seed,
        opencv_version=OPENCV_VERSION,
        known_area_pct=c.known_area_pct,
        predicted_area_pct=out.anomaly_area_pct,
        iou=round(iou, 4),
        precision=round(prec, 4),
        recall=round(rec, 4),
        final_action=result.final_action,
        confidence=result.confidence,
        leaf_coverage=out.quality.leaf_coverage,
        sharpness=round(out.quality.sharpness, 2),
        brightness=round(out.quality.brightness, 2),
        accepted=result.final_action == "accept",
        notes=list(out.notes),
    )


def run_suite(seeds: list[int] | None = None) -> dict[str, Any]:
    severities = ["none", "mild", "moderate", "severe"]
    degradations = ["clean", "noise", "blur", "dark"]
    seeds = seeds or [101, 202, 303]
    cases: list[SyntheticCase] = []
    results: list[EvalResult] = []
    for sev in severities:
        for deg in degradations:
            for s in seeds:
                c = generate_case(sev, deg, s)
                cases.append(c)
                results.append(evaluate_case(c))
    return _summarize(cases, results)


def _summarize(cases: list[SyntheticCase], results: list[EvalResult]) -> dict[str, Any]:
    rows = [r.__dict__ for r in results]
    by_sev: dict[str, list[EvalResult]] = {}
    for r in results:
        by_sev.setdefault(r.severity, []).append(r)
    summary = {}
    for sev, rs in by_sev.items():
        iou = [r.iou for r in rs if r.severity != "none"]
        summary[sev] = {
            "n": len(rs),
            "mean_iou": round(float(np.mean(iou)), 4) if iou else None,
            "mean_precision": round(float(np.mean([r.precision for r in rs if r.severity != "none"])), 4) if any(rr.severity != "none" for rr in rs) else None,
            "mean_recall": round(float(np.mean([r.precision for r in rs if r.severity != "none"])), 4) if any(rr.severity != "none" for rr in rs) else None,
            "accept_rate": round(sum(1 for r in rs if r.accepted) / len(rs), 3),
        }
    return {
        "opencv_version": OPENCV_VERSION,
        "n_cases": len(cases),
        "synthetic_label": "All cases are SYNTHETIC generated leaves, not real photographs.",
        "summary_by_severity": summary,
        "results": rows,
    }


def write_outputs(report: dict[str, Any], out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "evaluation.json"), "w") as f:
        json.dump(report, f, indent=2)
    with open(os.path.join(out_dir, "evaluation.csv"), "w", newline="") as f:
        if not report["results"]:
            return
        w = csv.DictWriter(f, fieldnames=list(report["results"][0].keys()))
        w.writeheader()
        for r in report["results"]:
            r2 = dict(r)
            r2["notes"] = "; ".join(r["notes"])
            w.writerow(r2)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Run CropLens evaluation suite.")
    p.add_argument("--out", default="results", help="Output directory for CSV/JSON.")
    args = p.parse_args()
    report = run_suite()
    write_outputs(report, args.out)
    print(f"Wrote {args.out}/evaluation.json and .csv  (n={report['n_cases']}, OpenCV {report['opencv_version']})")
    for sev, s in report["summary_by_severity"].items():
        print(f"  {sev:8s} n={s['n']} accept_rate={s['accept_rate']} mean_iou={s['mean_iou']}")
