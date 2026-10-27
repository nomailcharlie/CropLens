"""Deterministic, inspectable agentic loop for CropLens Agent.

The state machine is NOT a fixed explanation generator. Each pass's *measured*
output determines the next branch:

  PASS 1 — measure quality + leaf coverage
    - no_leaf  -> STOP, final_action = no_leaf_found
    - poor focus / exposure -> STOP, request_recapture
    - ok quality -> run anomaly detection

  PASS 2 (conditional) — if pass-1 anomaly result is uncertain
    (very few tiny regions, or anomaly_area_pct in a grey zone), re-run with
    CLADE illumination normalization and slightly relaxed thresholds on the
    primary-leaf crop. Pick the pass with the stronger leaf coverage.

  FINAL — choose final_action:
    - no leaf            -> no_leaf_found
    - poor quality       -> request_recapture
    - anomaly_area_pct >= REVIEW_THRESHOLD -> request_human_review
    - otherwise          -> accept

Every step is recorded in `trace`.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import cv2
import numpy as np

from .vision import (
    VisionParams,
    VisionOutput,
    analyze_frame,
    overlay_mask_on,
    _bgr_to_hsv,
    _encode_jpeg_b64,
)

# Thresholds (deterministic; not tuned per-image)
REVIEW_THRESHOLD = 0.05  # 5% of leaf area flagged -> human review
RECAPTURE_SHARPNESS = 60.0
RECAPTURE_BRIGHTNESS_LOW = 35.0
RECAPTURE_BRIGHTNESS_HIGH = 215.0
UNCERTAIN_LOW = 0.005  # below this -> "essentially clean but uncertain"
UNCERTAIN_HIGH = 0.03  # above this -> clearly anomalous


@dataclass
class TraceEvent:
    step: str
    branch: str
    reason: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResult:
    quality: VisionOutput
    final_action: str
    confidence: str
    next_action_label: str
    next_action_detail: str
    passes: list[dict[str, Any]]
    trace: list[TraceEvent]


def _pass_to_dict(pid: int, trigger: str, params: VisionParams, out: VisionOutput) -> dict[str, Any]:
    return {
        "pass_id": pid,
        "trigger": trigger,
        "parameters": _params_public(params),
        "quality": _quality_public(out.quality),
        "leaf_area_px": out.leaf_area_px,
        "anomaly_area_px": out.anomaly_area_px,
        "anomaly_area_pct": out.anomaly_area_pct,
        "regions": [_region_public(r) for r in out.regions],
        "annotated_b64": _encode_jpeg_b64(out.annotated) if out.annotated is not None else None,
        "leaf_mask_b64": _mask_b64(out.leaf_mask) if out.leaf_mask is not None else None,
        "anomaly_mask_b64": _mask_b64(out.anomaly_mask) if out.anomaly_mask is not None else None,
        "notes": list(out.notes),
    }


def _mask_b64(mask: np.ndarray) -> str:
    if mask is None:
        return ""
    vis = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
    return _encode_jpeg_b64(vis)


def _params_public(p: VisionParams) -> dict[str, Any]:
    return {
        "sharpness_threshold": p.sharpness_threshold,
        "brightness_low": p.brightness_low,
        "brightness_high": p.brightness_high,
        "green_h_low": p.green_h_low,
        "green_h_high": p.green_h_high,
        "yellow_h_low": p.yellow_h_low,
        "yellow_h_high": p.yellow_h_high,
        "brown_h_low": p.brown_h_low,
        "brown_h_high": p.brown_h_high,
        "normalize_illumination": p.normalize_illumination,
        "min_region_frac": p.min_region_frac,
    }


def _quality_public(q) -> dict[str, Any]:
    return {
        "sharpness": round(q.sharpness, 2),
        "sharpness_flag": q.sharpness_flag,
        "brightness": round(q.brightness, 2),
        "brightness_flag": q.brightness_flag,
        "leaf_coverage": round(q.leaf_coverage, 4),
        "leaf_coverage_flag": q.leaf_coverage_flag,
    }


def _region_public(r) -> dict[str, Any]:
    return {
        "label": r.label,
        "area_px": r.area_px,
        "area_pct": round(r.area_pct, 5),
        "bbox": r.bbox,
        "mean_color_hsv": [round(r.mean_color_hsv[0], 1), round(r.mean_color_hsv[1], 1), round(r.mean_color_hsv[2], 1)],
        "severity": r.severity,
    }


def _quality_ok(out: VisionOutput, p: VisionParams) -> bool:
    q = out.quality
    if q.sharpness_flag == "poor_focus" and q.sharpness < RECAPTURE_SHARPNESS:
        return False
    if q.brightness_flag == "underexposed" and q.brightness < RECAPTURE_BRIGHTNESS_LOW:
        return False
    if q.brightness_flag == "overexposed" and q.brightness > RECAPTURE_BRIGHTNESS_HIGH:
        return False
    return True


def _uncertain(out: VisionOutput) -> bool:
    return UNCERTAIN_LOW <= out.anomaly_area_pct <= UNCERTAIN_HIGH and len(out.regions) <= 2


def run_agent(bgr: np.ndarray) -> AgentResult:
    """Run the deterministic agentic loop on a single BGR frame."""
    trace: list[TraceEvent] = []
    passes: list[dict[str, Any]] = []

    # --- PASS 1 -----------------------------------------------------------
    p1 = VisionParams()
    trace.append(TraceEvent("pass_1", "measure", "Measure image quality and leaf coverage.", {
        "sharpness_threshold": p1.sharpness_threshold,
    }))
    out1 = analyze_frame(bgr, p1)
    passes.append(_pass_to_dict(1, "initial", p1, out1))

    q = out1.quality

    # Branch: no leaf
    if q.leaf_coverage_flag == "no_leaf":
        trace.append(TraceEvent("branch", "no_leaf", "Leaf coverage below 1%; cannot screen.", {
            "leaf_coverage": q.leaf_coverage,
        }))
        return _finalize(out1, passes, trace, "no_leaf_found", "low",
                         "No leaf detected", "Capture a closer, well-lit photo of a single leaf on a neutral background.")

    # Branch: poor quality -> recapture (unless very mild)
    if not _quality_ok(out1, p1):
        trace.append(TraceEvent("branch", "recapture", "Image quality inadequate for reliable screening.", {
            "sharpness": q.sharpness,
            "brightness": q.brightness,
            "sharpness_flag": q.sharpness_flag,
            "brightness_flag": q.brightness_flag,
        }))
        return _finalize(out1, passes, trace, "request_recapture", "low",
                         "Recapture recommended", "Image is too blurry or poorly exposed. Retake in good light, hold the camera steady, and fill the frame with the leaf.")

    # Branch: low coverage but not zero -> still run, but flag
    if q.leaf_coverage_flag == "low_coverage":
        trace.append(TraceEvent("branch", "low_coverage", "Leaf coverage 1-5%; proceeding with caution.", {
            "leaf_coverage": q.leaf_coverage,
        }))

    # --- PASS 2 (conditional) ---------------------------------------------
    out_final = out1
    p_final = p1
    if _uncertain(out1):
        trace.append(TraceEvent("pass_2", "reanalyze", "Pass-1 result uncertain; re-running with illumination normalization and a targeted crop.", {
            "reason": "anomaly_area_pct in grey zone",
            "pass1_anomaly_pct": out1.anomaly_area_pct,
        }))
        p2 = VisionParams(
            normalize_illumination=True,
            min_region_frac=max(0.001, p1.min_region_frac * 0.7),
            yellow_h_low=max(0, p1.yellow_h_low - 4),
            brown_h_high=min(35, p1.brown_h_high + 4),
        )
        out2 = analyze_frame(bgr, p2)
        passes.append(_pass_to_dict(2, "uncertain_reanalysis", p2, out2))
        # Choose the pass with the higher leaf coverage (more reliable mask)
        if out2.quality.leaf_coverage > out1.quality.leaf_coverage:
            out_final = out2
            p_final = p2
            trace.append(TraceEvent("branch", "adopt_pass_2", "Adopted pass-2 result (better leaf coverage).", {
                "pass1_coverage": out1.quality.leaf_coverage,
                "pass2_coverage": out2.quality.leaf_coverage,
            }))
        else:
            trace.append(TraceEvent("branch", "keep_pass_1", "Kept pass-1 result (pass-2 did not improve leaf coverage).", {
                "pass1_coverage": out1.quality.leaf_coverage,
                "pass2_coverage": out2.quality.leaf_coverage,
            }))
    else:
        trace.append(TraceEvent("branch", "accept_pass_1", "Pass-1 quality adequate and result not uncertain; no second pass needed.", {
            "anomaly_area_pct": out1.anomaly_area_pct,
        }))

    # --- FINAL decision ----------------------------------------------------
    if out_final.anomaly_area_pct >= REVIEW_THRESHOLD:
        action = "request_human_review"
        conf = "high" if out_final.anomaly_area_pct >= 0.10 else "moderate"
        label = "Human review recommended"
        detail = (f"{out_final.anomaly_area_pct*100:.2f}% of the leaf area shows visible color/texture anomalies. "
                  "This is a screening flag, not a diagnosis. Confirm with a qualified agronomist or lab test.")
        trace.append(TraceEvent("final", "human_review", "Anomaly area at/above review threshold.", {
            "anomaly_area_pct": out_final.anomaly_area_pct,
            "threshold": REVIEW_THRESHOLD,
        }))
    else:
        action = "accept"
        conf = "high" if out_final.anomaly_area_pct < UNCERTAIN_LOW else "moderate"
        label = "No significant anomalies"
        detail = (f"{out_final.anomaly_area_pct*100:.2f}% of the leaf area was flagged. "
                  "No visually significant anomalies detected in this image. Continue routine monitoring.")
        trace.append(TraceEvent("final", "accept", "Anomaly area below review threshold.", {
            "anomaly_area_pct": out_final.anomaly_area_pct,
            "threshold": REVIEW_THRESHOLD,
        }))

    return _finalize(out_final, passes, trace, action, conf, label, detail)


def _finalize(out: VisionOutput, passes: list[dict[str, Any]], trace: list[TraceEvent],
              action: str, conf: str, label: str, detail: str) -> AgentResult:
    return AgentResult(
        quality=out,
        final_action=action,
        confidence=conf,
        next_action_label=label,
        next_action_detail=detail,
        passes=passes,
        trace=trace,
    )


LIMITATIONS = [
    "CropLens Agent performs visual anomaly screening only; it does not diagnose disease, identify pathogens, or recommend treatment.",
    "Results depend on image quality, lighting, and framing. Poor focus or exposure can cause false negatives or false positives.",
    "Yellow/brown flags may be caused by disease, nutrient stress, senescence, water damage, or capture artifacts. Confirmation requires expert inspection.",
    "Do not use as the sole basis for crop-management decisions.",
    "No images are stored permanently by default; analysis is stateless.",
]
