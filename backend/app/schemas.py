"""Pydantic response schemas for CropLens Agent.

These mirror the TypeScript types used by the frontend (src/types.ts).
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class QualityMeasure(BaseModel):
    sharpness: float = Field(..., description="Variance of Laplacian (focus proxy)")
    sharpness_flag: Literal["ok", "poor_focus"]
    brightness: float = Field(..., description="Mean brightness 0-255")
    brightness_flag: Literal["ok", "underexposed", "overexposed"]
    leaf_coverage: float = Field(..., description="Fraction of frame that is green-leaf candidate 0-1")
    leaf_coverage_flag: Literal["ok", "no_leaf", "low_coverage"]


class RegionMeasure(BaseModel):
    label: str
    area_px: int
    area_pct: float = Field(..., description="Fraction of leaf area, 0-1")
    bbox: list[int] = Field(..., description="[x, y, w, h]")
    mean_color_hsv: list[float]
    severity: Literal["low", "moderate", "high"]


class PassResult(BaseModel):
    pass_id: int
    trigger: str
    parameters: dict[str, Any]
    quality: QualityMeasure
    leaf_area_px: int
    anomaly_area_px: int
    anomaly_area_pct: float
    regions: list[RegionMeasure]
    annotated_b64: Optional[str] = None
    leaf_mask_b64: Optional[str] = None
    anomaly_mask_b64: Optional[str] = None
    notes: list[str] = Field(default_factory=list)


class TraceEvent(BaseModel):
    step: str
    branch: str
    reason: str
    data: dict[str, Any] = Field(default_factory=dict)


class AnalysisResponse(BaseModel):
    ok: bool
    opencv_version: str
    runtime: str
    source_kind: Literal["image", "video_frame"]
    frame_index: Optional[int] = None
    total_frames_sampled: int = 1
    quality: QualityMeasure
    leaf_area_px: int
    anomaly_area_px: int
    anomaly_area_pct: float
    regions: list[RegionMeasure]
    annotated_b64: Optional[str] = None
    leaf_mask_b64: Optional[str] = None
    anomaly_mask_b64: Optional[str] = None
    passes: list[PassResult]
    trace: list[TraceEvent]
    final_action: Literal["accept", "request_recapture", "request_human_review", "no_leaf_found"]
    confidence: Literal["low", "moderate", "high"]
    next_action_label: str
    next_action_detail: str
    limitations: list[str]


class HealthResponse(BaseModel):
    status: Literal["ok"]
    opencv_version: str
    runtime: str
    service: str
    version: str
