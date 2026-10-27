import type { TraceEvent } from '@/types';
import { ChevronRight, GitBranch, Camera, Cpu, Flag, CheckCircle2, ShieldAlert, RefreshCw } from 'lucide-react';

const STEP_ICON: Record<string, typeof GitBranch> = {
  pass_1: Cpu,
  pass_2: Cpu,
  branch: GitBranch,
  final: Flag,
  measure: Camera,
};

function stepTone(step: string): string {
  if (step === 'final') return 'text-clay-600';
  if (step.startsWith('pass')) return 'text-forest-600';
  if (step === 'branch') return 'text-sage-600';
  return 'text-forest-600';
}

export function DecisionTrace({ trace }: { trace: TraceEvent[] }) {
  if (!trace.length) return null;
  return (
    <ol className="relative space-y-3 pl-6">
      <span className="absolute left-2 top-1 bottom-1 w-px bg-forest-200" />
      {trace.map((t, i) => {
        const Icon = STEP_ICON[t.step] ?? ChevronRight;
        return (
          <li key={i} className="relative animate-slide-up" style={{ animationDelay: `${i * 40}ms` }}>
            <span className={`absolute -left-6 top-0.5 w-4 h-4 rounded-full bg-white border border-forest-200 flex items-center justify-center ${stepTone(t.step)}`}>
              <Icon className="w-2.5 h-2.5" />
            </span>
            <div className="rounded-lg border border-forest-100 bg-forest-50/40 px-3 py-2">
              <div className="flex items-center gap-2 flex-wrap">
                <span className={`label-mono ${stepTone(t.step)}`}>{t.step}</span>
                <span className="text-xs font-semibold text-forest-700">{t.branch}</span>
              </div>
              <p className="text-sm text-forest-700/90 mt-0.5">{t.reason}</p>
              {Object.keys(t.data).length > 0 && (
                <dl className="mt-1.5 grid grid-cols-2 gap-x-3 gap-y-0.5 text-[11px] font-mono text-forest-600">
                  {Object.entries(t.data).map(([k, v]) => (
                    <div key={k} className="contents">
                      <dt className="text-forest-400">{k}</dt>
                      <dd className="text-forest-700">{typeof v === 'number' ? (Number.isInteger(v) ? v : v.toFixed(4)) : String(v)}</dd>
                    </div>
                  ))}
                </dl>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

export function FinalActionIcon({ action }: { action: string }) {
  if (action === 'accept') return <CheckCircle2 className="w-5 h-5 text-sage-600" />;
  if (action === 'request_recapture') return <RefreshCw className="w-5 h-5 text-amber-600" />;
  if (action === 'request_human_review') return <ShieldAlert className="w-5 h-5 text-clay-600" />;
  return <Flag className="w-5 h-5 text-forest-600" />;
}
