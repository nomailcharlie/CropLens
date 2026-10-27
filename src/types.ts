// Shared types matching the backend Pydantic schemas (backend/app/schemas.py)

export type Flag = 'ok' | 'poor_focus' | 'underexposed' | 'overexposed' | 'no_leaf' | 'low_coverage';
export type FinalAction = 'accept' | 'request_recapture' | 'request_human_review' | 'no_leaf_found';
export type Confidence = 'low' | 'moderate' | 'high';
export type Severity = 'low' | 'moderate' | 'high';
export type SourceKind = 'image' | 'video_frame';

export interface QualityMeasure {
  sharpness: number;
  sharpness_flag: Exclude<Flag, 'underexposed' | 'overexposed' | 'no_leaf' | 'low_coverage'>;
  brightness: number;
  brightness_flag: Exclude<Flag, 'poor_focus' | 'no_leaf' | 'low_coverage'>;
  leaf_coverage: number;
  leaf_coverage_flag: Exclude<Flag, 'poor_focus' | 'underexposed' | 'overexposed'>;
}

export interface RegionMeasure {
  label: string;
  area_px: number;
  area_pct: number;
  bbox: [number, number, number, number];
  mean_color_hsv: [number, number, number];
  severity: Severity;
}

export interface PassResult {
  pass_id: number;
  trigger: string;
  parameters: Record<string, number | boolean>;
  quality: QualityMeasure;
  leaf_area_px: number;
  anomaly_area_px: number;
  anomaly_area_pct: number;
  regions: RegionMeasure[];
  annotated_b64: string | null;
  leaf_mask_b64: string | null;
  anomaly_mask_b64: string | null;
  notes: string[];
}

export interface TraceEvent {
  step: string;
  branch: string;
  reason: string;
  data: Record<string, number | string | boolean>;
}

export interface AnalysisResponse {
  ok: boolean;
  opencv_version: string;
  runtime: string;
  source_kind: SourceKind;
  frame_index: number | null;
  total_frames_sampled: number;
  quality: QualityMeasure;
  leaf_area_px: number;
  anomaly_area_px: number;
  anomaly_area_pct: number;
  regions: RegionMeasure[];
  annotated_b64: string | null;
  leaf_mask_b64: string | null;
  anomaly_mask_b64: string | null;
  passes: PassResult[];
  trace: TraceEvent[];
  final_action: FinalAction;
  confidence: Confidence;
  next_action_label: string;
  next_action_detail: string;
  limitations: string[];
}

export interface HealthResponse {
  status: string;
  opencv_version: string;
  runtime: string;
  service: string;
  version: string;
}

export interface SampleItem {
  id: string;
  label: string;
  severity: string;
}

export type ConnectionStatus = 'checking' | 'online' | 'offline' | 'unknown';
