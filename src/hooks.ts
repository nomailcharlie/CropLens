import { useCallback, useEffect, useRef, useState } from 'react';
import type { ConnectionStatus, HealthResponse } from '@/types';
import { getHealth } from '@/api';

export function useConnectionHealth(pollMs = 30000) {
  const [status, setStatus] = useState<ConnectionStatus>('checking');
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const check = useCallback(async () => {
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setStatus('checking');
    try {
      const h = await getHealth(ctrl.signal);
      setHealth(h);
      setStatus('online');
      setError(null);
    } catch (e) {
      if ((e as Error).name === 'AbortError') return;
      setStatus('offline');
      setError((e as Error).message || 'Cannot reach backend');
    }
  }, []);

  useEffect(() => {
    check();
    const id = window.setInterval(check, pollMs);
    return () => {
      window.clearInterval(id);
      abortRef.current?.abort();
    };
  }, [check, pollMs]);

  return { status, health, error, recheck: check };
}

export function useAbortable() {
  const ctrlRef = useRef<AbortController | null>(null);
  const abort = useCallback(() => {
    ctrlRef.current?.abort();
    ctrlRef.current = null;
  }, []);
  const signal = useCallback(() => {
    ctrlRef.current?.abort();
    const c = new AbortController();
    ctrlRef.current = c;
    return c.signal;
  }, []);
  return { signal, abort };
}

export function b64ToDataUrl(b64: string | null | undefined, mime = 'image/jpeg'): string {
  if (!b64) return '';
  return `data:${mime};base64,${b64}`;
}
