import type { ReactNode } from 'react';
import { AlertTriangle, CheckCircle2, Info, XCircle, ShieldAlert } from 'lucide-react';

type Tone = 'ok' | 'warn' | 'error' | 'info' | 'review';

const TONE: Record<Tone, { bg: string; border: string; text: string; icon: ReactNode }> = {
  ok: { bg: 'bg-sage-50', border: 'border-sage-200', text: 'text-sage-700', icon: <CheckCircle2 className="w-4 h-4" /> },
  warn: { bg: 'bg-amber-50', border: 'border-amber-200', text: 'text-amber-600', icon: <AlertTriangle className="w-4 h-4" /> },
  error: { bg: 'bg-red-50', border: 'border-red-200', text: 'text-red-700', icon: <XCircle className="w-4 h-4" /> },
  info: { bg: 'bg-forest-50', border: 'border-forest-200', text: 'text-forest-700', icon: <Info className="w-4 h-4" /> },
  review: { bg: 'bg-clay-50', border: 'border-clay-200', text: 'text-clay-700', icon: <ShieldAlert className="w-4 h-4" /> },
};

export function Banner({ tone, title, children }: { tone: Tone; title: string; children?: ReactNode }) {
  const t = TONE[tone];
  return (
    <div className={`flex items-start gap-3 rounded-xl border ${t.bg} ${t.border} px-4 py-3 animate-fade-in`}>
      <span className={t.text}>{t.icon}</span>
      <div className="flex-1">
        <p className={`text-sm font-semibold ${t.text}`}>{title}</p>
        {children && <div className="text-sm text-forest-700/90 mt-1">{children}</div>}
      </div>
    </div>
  );
}

export function Pill({ tone = 'info', children }: { tone?: Tone; children: ReactNode }) {
  const t = TONE[tone];
  return (
    <span className={`chip ${t.bg} ${t.border} ${t.text} border`}>
      {children}
    </span>
  );
}

export function QualityBar({ value, max, label, tone }: { value: number; max: number; label: string; tone: string }) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  return (
    <div>
      <div className="flex justify-between text-xs mb-1">
        <span className="text-forest-600">{label}</span>
        <span className="font-mono text-forest-700">{value.toFixed(1)}</span>
      </div>
      <div className="h-2 rounded-full bg-forest-100 overflow-hidden">
        <div className={`h-full rounded-full ${tone} transition-all duration-500`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
