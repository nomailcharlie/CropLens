import type {
  AnalysisResponse,
  HealthResponse,
  SampleItem,
} from '@/types';

// VITE_API_BASE_URL is the deployed backend root (e.g. https://abc.lambda-url.us-east-1.on.aws).
// When unset, use the relative '/api' prefix so Vite's dev proxy forwards to
// the local FastAPI server (vite.config.ts proxies /api -> http://localhost:8080).
const RAW_BASE = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '') ?? '';
const BASE = RAW_BASE || '/api';

export function url(path: string): string {
  return `${BASE}${path}`;
}

export function imageUrl(path: string): string {
  return `${BASE}${path}`;
}

export async function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const res = await fetch(url('/health'), { signal });
  if (!res.ok) throw new Error(`Health ${res.status}`);
  return (await res.json()) as HealthResponse;
}

export async function listSamples(signal?: AbortSignal): Promise<SampleItem[]> {
  const res = await fetch(url('/samples'), { signal });
  if (!res.ok) throw new Error(`Samples ${res.status}`);
  return (await res.json()) as SampleItem[];
}

export async function analyzeUpload(file: File, signal?: AbortSignal): Promise<AnalysisResponse> {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(url('/analyze'), {
    method: 'POST',
    body: form,
    signal,
  });
  if (!res.ok) {
    let detail = `Analysis failed (${res.status})`;
    try {
      const j = await res.json();
      if (j?.detail) detail = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail);
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return (await res.json()) as AnalysisResponse;
}

export async function analyzeSample(sampleId: string, signal?: AbortSignal): Promise<AnalysisResponse> {
  const res = await fetch(url(`/samples/${encodeURIComponent(sampleId)}/analyze`), {
    method: 'POST',
    signal,
  });
  if (!res.ok) throw new Error(`Sample analysis failed (${res.status})`);
  return (await res.json()) as AnalysisResponse;
}
