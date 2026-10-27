import { useEffect, useRef, useState } from 'react';
import { MoveHorizontal } from 'lucide-react';

interface Props {
  beforeSrc: string;
  afterSrc: string;
  beforeLabel?: string;
  afterLabel?: string;
  className?: string;
}

export function BeforeAfter({ beforeSrc, afterSrc, beforeLabel = 'Original', afterLabel = 'Annotated', className }: Props) {
  const [pos, setPos] = useState(50);
  const ref = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);

  useEffect(() => {
    const move = (clientX: number) => {
      const el = ref.current;
      if (!el) return;
      const rect = el.getBoundingClientRect();
      const x = clientX - rect.left;
      setPos(Math.max(0, Math.min(100, (x / rect.width) * 100)));
    };
    const onMove = (e: MouseEvent) => dragging.current && move(e.clientX);
    const onTouch = (e: TouchEvent) => dragging.current && move(e.touches[0].clientX);
    const onUp = () => (dragging.current = false);
    window.addEventListener('mousemove', onMove);
    window.addEventListener('touchmove', onTouch);
    window.addEventListener('mouseup', onUp);
    window.addEventListener('touchend', onUp);
    return () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('touchmove', onTouch);
      window.removeEventListener('mouseup', onUp);
      window.removeEventListener('touchend', onUp);
    };
  }, []);

  if (!beforeSrc && !afterSrc) return null;

  return (
    <div
      ref={ref}
      className={`relative select-none overflow-hidden rounded-xl bg-forest-900 ${className ?? ''}`}
      onMouseDown={(e) => { dragging.current = true; (e.target as HTMLElement).dispatchEvent(new MouseEvent('mousemove', { clientX: e.clientX })); }}
      onTouchStart={(e) => { dragging.current = true; }}
    >
      {afterSrc && (
        <img src={afterSrc} alt={afterLabel} className="block w-full h-full object-contain" draggable={false} />
      )}
      {beforeSrc && (
        <div className="absolute inset-0 overflow-hidden" style={{ width: `${pos}%` }}>
          <img
            src={beforeSrc}
            alt={beforeLabel}
            className="block h-full object-contain"
            style={{ width: ref.current?.clientWidth ?? '100%', maxWidth: 'none' }}
            draggable={false}
          />
          <span className="absolute top-2 left-2 chip bg-black/50 text-white">{beforeLabel}</span>
        </div>
      )}
      {afterSrc && <span className="absolute top-2 right-2 chip bg-black/50 text-white">{afterLabel}</span>}
      <div
        className="absolute top-0 bottom-0 w-1 bg-white/80 shadow-md cursor-ew-resize"
        style={{ left: `${pos}%`, transform: 'translateX(-50%)' }}
      >
        <div className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 left-1/2 w-8 h-8 rounded-full bg-white shadow-lg flex items-center justify-center text-forest-700">
          <MoveHorizontal className="w-4 h-4" />
        </div>
      </div>
    </div>
  );
}
