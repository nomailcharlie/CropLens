import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Leaf, Activity, Wifi, WifiOff, RefreshCw, Image as ImageIcon, Layers,
  ShieldAlert, Sparkles, FileImage, AlertTriangle, CheckCircle2, XCircle,
  Camera, Eye, Gauge, Ruler, ListTree, ChevronDown, ChevronRight, Info,
} from 'lucide-react';
import type {
  AnalysisResponse, ConnectionStatus, SampleItem,
} from '@/types';
import { analyzeSample, analyzeUpload, imageUrl, listSamples } from '@/api';
import { b64ToDataUrl, useAbortable, useConnectionHealth } from '@/hooks';
import { Banner, Pill, QualityBar } from '@/components/Banner';
import { BeforeAfter } from '@/components/BeforeAfter';
import { DecisionTrace, FinalActionIcon } from '@/components/DecisionTrace';
import { UploadZone, isVideoName } from '@/components/UploadZone';
import { EvaluationPanel } from '@/components/EvaluationPanel';

type Stage = 'idle' | 'uploading' | 'analyzing' | 'done' | 'error';

interface UploadState {
  previewUrl: string;
  fileName: string;
  isVideo: boolean;
}

export default function App() {
  const { status, health, error: healthError, recheck } = useConnectionHealth();
  const { signal, abort } = useAbortable();
  const [stage, setStage] = useState<Stage>('idle');
  const [upload, setUpload] = useState<UploadState | null>(null);
  const [result, setResult] = useState<AnalysisResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [samples, setSamples] = useState<SampleItem[]>([]);
  const [progress, setProgress] = useState(0);
  const [showMasks, setShowMasks] = useState<'annotated' | 'leaf' | 'anomaly'>('annotated');
  const [showTrace, setShowTrace] = useState(true);
  const [showLimitations, setShowLimitations] = useState(false);

  useEffect(() => {
    listSamples().then(setSamples).catch(() => setSamples([]));
  }, []);

  useEffect(() => () => { if (upload?.previewUrl.startsWith('blob:')) URL.revokeObjectURL(upload.previewUrl); }, [upload]);

  const runAnalysis = useCallback(async (runner: (sig: AbortSignal) => Promise<AnalysisResponse>, preview: UploadState) => {
    abort();
    setStage('analyzing');
    setError(null);
    setResult(null);
    setProgress(8);
    const tick = window.setInterval(() => setProgress((p) => (p < 90 ? p + Math.random() * 8 : p)), 250);
    try {
      const r = await runner(signal());
      setProgress(100);
      setResult(r);
      setStage('done');
    } catch (e) {
      if ((e as Error).name === 'AbortError') {
        setStage('idle');
      } else {
        setError((e as Error).message || 'Analysis failed');
        setStage('error');
      }
    } finally {
      window.clearInterval(tick);
      window.setTimeout(() => setProgress(0), 600);
    }
  }, [abort, signal]);

  const handleFile = useCallback((file: File) => {
    const isVid = isVideoName(file.name);
    const previewUrl = isVid ? '' : URL.createObjectURL(file);
    const u: UploadState = { previewUrl, fileName: file.name, isVideo: isVid };
    setUpload(u);
    setStage('uploading');
    void runAnalysis((sig) => analyzeUpload(file, sig), u);
  }, [runAnalysis]);

  const handleSample = useCallback(async (s: SampleItem) => {
    const u: UploadState = { previewUrl: imageUrl(`/samples/${s.id}`), fileName: s.label, isVideo: false };
    setUpload(u);
    setStage('uploading');
    void runAnalysis((sig) => analyzeSample(s.id, sig), u);
  }, [runAnalysis]);

  const reset = useCallback(() => {
    abort();
    if (upload?.previewUrl.startsWith('blob:')) URL.revokeObjectURL(upload.previewUrl);
    setUpload(null);
    setResult(null);
    setError(null);
    setStage('idle');
  }, [abort, upload]);

  const resultImg = useMemo(() => {
    if (!result) return { annotated: '', leaf: '', anomaly: '' };
    return {
      annotated: b64ToDataUrl(result.annotated_b64),
      leaf: b64ToDataUrl(result.leaf_mask_b64),
      anomaly: b64ToDataUrl(result.anomaly_mask_b64),
    };
  }, [result]);

  const q = result?.quality;
  const isOffline = status === 'offline';

  return (
    <div className="min-h-screen">
      <Header status={status} health={health} healthError={healthError} onRecheck={recheck} />

      <main className="max-w-6xl mx-auto px-4 sm:px-6 pb-24 space-y-6">
        <Hero />

        {isOffline && (
          <Banner tone="error" title="Backend not reachable">
            The OpenCV analysis service is not responding. {healthError ? `(${healthError})` : ''} Start the Python backend (see README) or set <code className="font-mono text-xs">VITE_API_BASE_URL</code> to your deployed AWS endpoint. Sample mode and uploads will not work until it's online.
          </Banner>
        )}

        {/* Upload + samples */}
        <section className="grid lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2 card card-pad">
            <div className="flex items-center gap-2 mb-3">
              <Camera className="w-5 h-5 text-forest-600" />
              <h2 className="section-title">Capture or upload</h2>
            </div>
            <UploadZone onFile={handleFile} disabled={stage === 'analyzing'} />
            {upload && (
              <div className="mt-3 flex items-center gap-3 rounded-lg bg-forest-50/60 border border-forest-100 px-3 py-2">
                {upload.previewUrl ? (
                  <img src={upload.previewUrl} alt="preview" className="w-12 h-12 rounded object-cover" />
                ) : (
                  <div className="w-12 h-12 rounded bg-forest-100 flex items-center justify-center text-forest-500"><FileImage className="w-5 h-5" /></div>
                )}
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-forest-800 truncate">{upload.fileName}</p>
                  <p className="text-xs text-forest-500">{upload.isVideo ? 'Video — frames will be sampled' : 'Image'}</p>
                </div>
                {stage !== 'analyzing' && (
                  <button onClick={reset} className="btn-ghost text-xs">Clear</button>
                )}
              </div>
            )}
          </div>

          <div className="card card-pad">
            <div className="flex items-center gap-2 mb-3">
              <Sparkles className="w-5 h-5 text-clay-600" />
              <h2 className="section-title">Try a sample</h2>
            </div>
            <p className="text-xs text-forest-500 mb-3">Synthetic leaves generated with OpenCV — no upload needed.</p>
            <div className="grid grid-cols-2 gap-2">
              {samples.map((s) => (
                <button
                  key={s.id}
                  onClick={() => handleSample(s)}
                  disabled={stage === 'analyzing'}
                  className="group rounded-xl border border-forest-100 bg-white hover:border-forest-300 hover:bg-forest-50/50 transition-all p-2 text-left disabled:opacity-50"
                >
                  <div className="aspect-square rounded-lg overflow-hidden bg-forest-50 mb-1.5">
                    <img src={imageUrl(`/samples/${s.id}`)} alt={s.label} className="w-full h-full object-cover group-hover:scale-105 transition-transform" loading="lazy" />
                  </div>
                  <p className="text-xs font-medium text-forest-700 leading-tight">{s.label}</p>
                </button>
              ))}
              {samples.length === 0 && <p className="text-xs text-forest-400 col-span-2">Samples unavailable while backend is offline.</p>}
            </div>
          </div>
        </section>

        {/* Progress */}
        {stage === 'analyzing' && (
          <section className="card card-pad animate-fade-in">
            <div className="flex items-center gap-3">
              <RefreshCw className="w-5 h-5 text-forest-600 animate-spin-slow" />
              <div className="flex-1">
                <p className="text-sm font-medium text-forest-800">Running OpenCV analysis…</p>
                <div className="mt-2 h-2 rounded-full bg-forest-100 overflow-hidden">
                  <div className="h-full bg-forest-500 transition-all duration-300" style={{ width: `${progress}%` }} />
                </div>
              </div>
            </div>
          </section>
        )}

        {/* Error */}
        {stage === 'error' && error && (
          <Banner tone="error" title="Analysis failed">
            <p>{error}</p>
            <button onClick={reset} className="btn-secondary mt-2 text-xs">Try again</button>
          </Banner>
        )}

        {/* Results */}
        {result && stage === 'done' && (
          <ResultsView
            result={result}
            originalUrl={upload?.previewUrl ?? ''}
            resultImg={resultImg}
            showMasks={showMasks}
            setShowMasks={setShowMasks}
            showTrace={showTrace}
            setShowTrace={setShowTrace}
            showLimitations={showLimitations}
            setShowLimitations={setShowLimitations}
          />
        )}

        <EvaluationPanel />

        <Footer />
      </main>
    </div>
  );
}

function Header({ status, health, healthError, onRecheck }: {
  status: ConnectionStatus;
  health: { opencv_version: string; runtime: string } | null;
  healthError: string | null;
  onRecheck: () => void;
}) {
  return (
    <header className="sticky top-0 z-20 backdrop-blur-md bg-sand-50/85 border-b border-forest-100/60">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-xl bg-forest-600 text-white flex items-center justify-center shadow-sm">
            <Leaf className="w-5 h-5" />
          </div>
          <div>
            <h1 className="font-display text-lg font-bold text-forest-800 leading-none">CropLens Agent</h1>
            <p className="text-[11px] text-forest-500 leading-none mt-0.5">Explainable crop-leaf anomaly screening</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {health && (
            <span className="hidden sm:inline-flex chip bg-forest-50 border border-forest-100 text-forest-600">
              <Layers className="w-3 h-3" /> OpenCV {health.opencv_version}
            </span>
          )}
          <button
            onClick={onRecheck}
            className={`chip border ${status === 'online' ? 'bg-sage-50 border-sage-200 text-sage-700' : status === 'offline' ? 'bg-red-50 border-red-200 text-red-700' : 'bg-forest-50 border-forest-100 text-forest-500'}`}
            title={healthError ?? status}
          >
            {status === 'online' ? <Wifi className="w-3 h-3" /> : status === 'offline' ? <WifiOff className="w-3 h-3" /> : <RefreshCw className="w-3 h-3 animate-spin" />}
            {status === 'online' ? 'Online' : status === 'offline' ? 'Offline' : 'Checking…'}
          </button>
        </div>
      </div>
    </header>
  );
}

function Hero() {
  return (
    <section className="pt-8 sm:pt-12 pb-2 text-center">
      <div className="inline-flex items-center gap-1.5 chip bg-forest-50 border border-forest-100 text-forest-600 mb-4">
        <Activity className="w-3 h-3" /> OpenCV 5 · Agentic · AWS-ready
      </div>
      <h2 className="font-display text-3xl sm:text-5xl font-bold text-forest-800 text-balance max-w-3xl mx-auto">
        See what your leaves are telling you.
      </h2>
      <p className="mt-4 text-forest-600 max-w-xl mx-auto text-balance">
        Upload a leaf photo or short video. CropLens runs real OpenCV computer-vision analysis to flag color and texture anomalies, checks image quality, and explains every decision — clearly, responsibly, and without claiming a diagnosis.
      </p>
    </section>
  );
}

function ResultsView({ result, originalUrl, resultImg, showMasks, setShowMasks, showTrace, setShowTrace, showLimitations, setShowLimitations }: {
  result: AnalysisResponse;
  originalUrl: string;
  resultImg: { annotated: string; leaf: string; anomaly: string };
  showMasks: 'annotated' | 'leaf' | 'anomaly';
  setShowMasks: (v: 'annotated' | 'leaf' | 'anomaly') => void;
  showTrace: boolean;
  setShowTrace: (v: boolean) => void;
  showLimitations: boolean;
  setShowLimitations: (v: boolean) => void;
}) {
  const q = result.quality;
  const anomPct = (result.anomaly_area_pct * 100);
  const actionTone = result.final_action === 'accept' ? 'ok' : result.final_action === 'request_recapture' ? 'warn' : result.final_action === 'no_leaf_found' ? 'info' : 'review';

  return (
    <div className="space-y-5 animate-fade-in">
      {/* Top action banner */}
      <Banner tone={actionTone as 'ok' | 'warn' | 'info' | 'review'} title={result.next_action_label}>
        <p>{result.next_action_detail}</p>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <Pill tone="info">Confidence: {result.confidence}</Pill>
          <Pill tone="info">Action: {result.final_action.replace(/_/g, ' ')}</Pill>
          {result.source_kind === 'video_frame' && <Pill tone="info">Video frame {result.frame_index} · {result.total_frames_sampled} sampled</Pill>}
        </div>
      </Banner>

      <div className="grid lg:grid-cols-5 gap-5">
        {/* Image comparison */}
        <section className="lg:col-span-3 card card-pad">
          <div className="flex items-center justify-between flex-wrap gap-2 mb-3">
            <div className="flex items-center gap-2">
              <Eye className="w-5 h-5 text-forest-600" />
              <h2 className="section-title">Visual comparison</h2>
            </div>
            <div className="inline-flex rounded-lg border border-forest-100 bg-forest-50/50 p-0.5 text-xs">
              {(['annotated', 'leaf', 'anomaly'] as const).map((m) => (
                <button
                  key={m}
                  onClick={() => setShowMasks(m)}
                  className={`px-2.5 py-1 rounded-md transition-colors ${showMasks === m ? 'bg-white text-forest-700 shadow-sm' : 'text-forest-500 hover:text-forest-700'}`}
                >
                  {m === 'annotated' ? 'Annotated' : m === 'leaf' ? 'Leaf mask' : 'Anomaly mask'}
                </button>
              ))}
            </div>
          </div>

          {showMasks === 'annotated' ? (
            <BeforeAfter beforeSrc={originalUrl} afterSrc={resultImg.annotated} className="aspect-[4/3]" />
          ) : (
            <div className="rounded-xl overflow-hidden bg-forest-900 aspect-[4/3] flex items-center justify-center">
              <img src={showMasks === 'leaf' ? resultImg.leaf : resultImg.anomaly} alt={showMasks} className="max-h-full max-w-full object-contain" />
            </div>
          )}
          <p className="mt-2 text-xs text-forest-500">
            {showMasks === 'annotated' ? 'Drag the slider to compare your original with the annotated result.' : 'Grayscale mask produced by the OpenCV pipeline.'}
          </p>
        </section>

        {/* Quality + metrics */}
        <section className="lg:col-span-2 space-y-4">
          <div className="card card-pad">
            <div className="flex items-center gap-2 mb-3">
              <Gauge className="w-5 h-5 text-forest-600" />
              <h2 className="section-title">Image quality</h2>
            </div>
            <div className="space-y-3">
              <QualityBar label="Sharpness (Laplacian variance)" value={q.sharpness} max={500} tone={q.sharpness_flag === 'ok' ? 'bg-sage-400' : 'bg-amber-400'} />
              <QualityBar label="Brightness (0-255)" value={q.brightness} max={255} tone={q.brightness_flag === 'ok' ? 'bg-sage-400' : 'bg-amber-400'} />
              <QualityBar label="Leaf coverage (%)" value={q.leaf_coverage * 100} max={100} tone={q.leaf_coverage_flag === 'ok' ? 'bg-sage-400' : 'bg-amber-400'} />
            </div>
            <div className="mt-3 flex flex-wrap gap-1.5">
              <FlagChip ok={q.sharpness_flag === 'ok'} label="Focus" />
              <FlagChip ok={q.brightness_flag === 'ok'} label="Exposure" />
              <FlagChip ok={q.leaf_coverage_flag === 'ok'} label="Leaf" />
            </div>
          </div>

          <div className="card card-pad">
            <div className="flex items-center gap-2 mb-3">
              <Ruler className="w-5 h-5 text-forest-600" />
              <h2 className="section-title">Anomaly measurements</h2>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Metric label="Anomaly area" value={`${anomPct.toFixed(2)}%`} sub="of leaf area" />
              <Metric label="Regions found" value={String(result.regions.length)} sub="distinct contours" />
              <Metric label="Leaf area" value={result.leaf_area_px.toLocaleString()} sub="pixels" />
              <Metric label="Anomaly pixels" value={result.anomaly_area_px.toLocaleString()} sub="pixels" />
            </div>
            {result.regions.length > 0 && (
              <div className="mt-3 space-y-1.5">
                <p className="label-mono">Detected regions</p>
                {result.regions.slice(0, 6).map((r, i) => (
                  <div key={i} className="flex items-center justify-between rounded-lg bg-forest-50/50 px-3 py-1.5 text-xs">
                    <span className="text-forest-700 font-medium">{r.label}</span>
                    <span className="flex items-center gap-2">
                      <span className="font-mono text-forest-600">{(r.area_pct * 100).toFixed(2)}%</span>
                      <span className={`chip ${r.severity === 'high' ? 'bg-red-100 text-red-700' : r.severity === 'moderate' ? 'bg-clay-100 text-clay-700' : 'bg-amber-100 text-amber-700'}`}>{r.severity}</span>
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>
      </div>

      {/* Decision trace */}
      <section className="card card-pad">
        <button onClick={() => setShowTrace(!showTrace)} className="flex items-center gap-2 w-full">
          {showTrace ? <ChevronDown className="w-4 h-4 text-forest-600" /> : <ChevronRight className="w-4 h-4 text-forest-600" />}
          <ListTree className="w-5 h-5 text-forest-600" />
          <h2 className="section-title">Decision trace (agentic loop)</h2>
          <span className="ml-auto chip bg-forest-50 text-forest-500">{result.passes.length} pass{result.passes.length > 1 ? 'es' : ''}</span>
        </button>
        {showTrace && (
          <div className="mt-4 grid lg:grid-cols-2 gap-5">
            <div>
              <p className="label-mono mb-2">Passes</p>
              <div className="space-y-2">
                {result.passes.map((p) => (
                  <div key={p.pass_id} className="rounded-lg border border-forest-100 bg-forest-50/30 p-3">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold text-forest-700">Pass {p.pass_id}: {p.trigger.replace(/_/g, ' ')}</span>
                      <span className="font-mono text-[11px] text-forest-500">anom {p.anomaly_area_pct ? (p.anomaly_area_pct * 100).toFixed(2) : '0.00'}%</span>
                    </div>
                    {Object.keys(p.parameters).length > 0 && (
                      <dl className="mt-1.5 grid grid-cols-2 gap-x-3 gap-y-0.5 text-[11px] font-mono text-forest-500">
                        {Object.entries(p.parameters).slice(0, 6).map(([k, v]) => (
                          <div key={k} className="contents"><dt>{k}</dt><dd className="text-forest-700">{String(v)}</dd></div>
                        ))}
                      </dl>
                    )}
                    {p.notes.length > 0 && <p className="mt-1 text-xs text-amber-700">{p.notes.join(' ')}</p>}
                  </div>
                ))}
              </div>
            </div>
            <div>
              <p className="label-mono mb-2">Trace</p>
              <DecisionTrace trace={result.trace} />
            </div>
          </div>
        )}
      </section>

      {/* Limitations */}
      <section className="card card-pad">
        <button onClick={() => setShowLimitations(!showLimitations)} className="flex items-center gap-2 w-full">
          {showLimitations ? <ChevronDown className="w-4 h-4 text-forest-600" /> : <ChevronRight className="w-4 h-4 text-forest-600" />}
          <ShieldAlert className="w-5 h-5 text-clay-600" />
          <h2 className="section-title">Limitations &amp; responsible use</h2>
        </button>
        {showLimitations && (
          <ul className="mt-3 space-y-1.5 text-sm text-forest-700/90">
            {result.limitations.map((l, i) => (
              <li key={i} className="flex items-start gap-2">
                <Info className="w-4 h-4 text-clay-500 flex-shrink-0 mt-0.5" />
                <span>{l}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function Metric({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div className="rounded-lg bg-forest-50/40 border border-forest-50 p-3">
      <p className="label-mono">{label}</p>
      <p className="text-xl font-display font-bold text-forest-800 mt-0.5">{value}</p>
      <p className="text-[11px] text-forest-400">{sub}</p>
    </div>
  );
}

function FlagChip({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span className={`chip ${ok ? 'bg-sage-50 text-sage-700' : 'bg-amber-50 text-amber-700'}`}>
      {ok ? <CheckCircle2 className="w-3 h-3" /> : <AlertTriangle className="w-3 h-3" />} {label}
    </span>
  );
}

function Footer() {
  return (
    <footer className="pt-10 text-center text-xs text-forest-400 space-y-1">
      <p>CropLens Agent — visual anomaly screening, not disease diagnosis.</p>
      <p>OpenCV {`5.x`} real image analysis · No images stored by default.</p>
    </footer>
  );
}
