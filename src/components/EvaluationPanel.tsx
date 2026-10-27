import { useState } from 'react';
import { FlaskConical, Play, Download, AlertCircle } from 'lucide-react';
import { url } from '@/api';

interface EvalRow {
  case_id: string;
  severity: string;
  degradation: string;
  seed: number;
  opencv_version: string;
  known_area_pct: number;
  predicted_area_pct: number;
  iou: number;
  precision: number;
  recall: number;
  final_action: string;
  confidence: string;
  leaf_coverage: number;
  sharpness: number;
  brightness: number;
  accepted: boolean;
  notes: string[];
}

interface EvalReport {
  opencv_version: string;
  n_cases: number;
  synthetic_label: string;
  summary_by_severity: Record<string, {
    n: number;
    mean_iou: number | null;
    mean_precision: number | null;
    mean_recall: number | null;
    accept_rate: number;
  }>;
  results: EvalRow[];
}

const sevColor: Record<string, string> = {
  none: 'bg-sage-100 text-sage-700',
  mild: 'bg-amber-100 text-amber-700',
  moderate: 'bg-clay-100 text-clay-700',
  severe: 'bg-red-100 text-red-700',
};

export function EvaluationPanel() {
  const [report, setReport] = useState<EvalReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(url('/evaluate'), { method: 'GET' });
      if (!res.ok) throw new Error(`Evaluation failed (${res.status})`);
      const j = (await res.json()) as EvalReport;
      setReport(j);
    } catch (e) {
      setError((e as Error).message || 'Evaluation failed');
    } finally {
      setLoading(false);
    }
  };

  const downloadCsv = () => {
    if (!report) return;
    const keys = Object.keys(report.results[0] ?? {});
    const lines = [keys.join(',')];
    for (const r of report.results) {
      lines.push(keys.map((k) => {
        const v = (r as unknown as Record<string, unknown>)[k];
        if (Array.isArray(v)) return `"${v.join('; ')}"`;
        return String(v);
      }).join(','));
    }
    const blob = new Blob([lines.join('\n')], { type: 'text/csv' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'croplens_evaluation.csv';
    a.click();
    URL.revokeObjectURL(a.href);
  };

  return (
    <section className="card card-pad">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2">
          <FlaskConical className="w-5 h-5 text-forest-600" />
          <h2 className="section-title">Evaluation panel</h2>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={run} disabled={loading} className="btn-primary">
            <Play className="w-4 h-4" /> {loading ? 'Running…' : 'Run synthetic suite'}
          </button>
          {report && (
            <button onClick={downloadCsv} className="btn-secondary">
              <Download className="w-4 h-4" /> CSV
            </button>
          )}
        </div>
      </div>

      <div className="mt-3 flex items-start gap-2 rounded-lg bg-amber-50 border border-amber-200 px-3 py-2 text-xs text-amber-700">
        <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
        <span>Synthetic test cases are generated with known anomaly masks and are labeled separately from real photographs. Metrics are computed from real OpenCV runs — not invented.</span>
      </div>

      {error && (
        <p className="mt-3 text-sm text-red-600">Couldn't run the evaluation: {error}. Make sure the backend is online.</p>
      )}

      {loading && (
        <div className="mt-4 space-y-2">
          {[0, 1, 2].map((i) => <div key={i} className="h-8 rounded-lg shimmer-bg animate-shimmer" />)}
        </div>
      )}

      {report && !loading && (
        <div className="mt-4 space-y-4 animate-fade-in">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
            {Object.entries(report.summary_by_severity).map(([sev, s]) => (
              <div key={sev} className="rounded-lg border border-forest-100 bg-forest-50/40 p-3">
                <div className="flex items-center justify-between">
                  <span className={`chip ${sevColor[sev] ?? 'bg-forest-100 text-forest-700'}`}>{sev}</span>
                  <span className="font-mono text-forest-500">n={s.n}</span>
                </div>
                <dl className="mt-2 space-y-0.5 font-mono text-forest-600">
                  <div className="flex justify-between"><dt>mean IoU</dt><dd>{s.mean_iou ?? '—'}</dd></div>
                  <div className="flex justify-between"><dt>precision</dt><dd>{s.mean_precision ?? '—'}</dd></div>
                  <div className="flex justify-between"><dt>recall</dt><dd>{s.mean_recall ?? '—'}</dd></div>
                  <div className="flex justify-between"><dt>accept rate</dt><dd>{s.accept_rate}</dd></div>
                </dl>
              </div>
            ))}
          </div>

          <div className="overflow-x-auto scrollbar-thin rounded-lg border border-forest-100">
            <table className="w-full text-xs">
              <thead className="bg-forest-50 text-forest-600">
                <tr>
                  {['case', 'sev', 'deg', 'known %', 'pred %', 'IoU', 'prec', 'rec', 'action', 'conf'].map((h) => (
                    <th key={h} className="px-2 py-2 text-left font-medium uppercase tracking-wider">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-forest-50">
                {report.results.map((r) => (
                  <tr key={r.case_id} className="hover:bg-forest-50/30">
                    <td className="px-2 py-1.5 font-mono text-forest-500">{r.case_id}</td>
                    <td className="px-2 py-1.5"><span className={`chip ${sevColor[r.severity] ?? ''}`}>{r.severity}</span></td>
                    <td className="px-2 py-1.5 text-forest-600">{r.degradation}</td>
                    <td className="px-2 py-1.5 font-mono text-forest-700">{(r.known_area_pct * 100).toFixed(2)}</td>
                    <td className="px-2 py-1.5 font-mono text-forest-700">{(r.predicted_area_pct * 100).toFixed(2)}</td>
                    <td className="px-2 py-1.5 font-mono text-forest-700">{r.iou.toFixed(3)}</td>
                    <td className="px-2 py-1.5 font-mono text-forest-700">{r.precision.toFixed(3)}</td>
                    <td className="px-2 py-1.5 font-mono text-forest-700">{r.recall.toFixed(3)}</td>
                    <td className="px-2 py-1.5 text-forest-600">{r.final_action.replace(/_/g, ' ')}</td>
                    <td className="px-2 py-1.5 text-forest-600">{r.confidence}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  );
}
