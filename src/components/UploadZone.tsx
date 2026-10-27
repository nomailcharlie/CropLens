import { useCallback, useRef, useState } from 'react';
import { UploadCloud, ImageIcon, FilmIcon } from 'lucide-react';

interface Props {
  onFile: (file: File) => void;
  disabled?: boolean;
}

const ACCEPT = '.jpg,.jpeg,.png,.mp4,image/jpeg,image/png,video/mp4';

export function UploadZone({ onFile, disabled }: Props) {
  const [over, setOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setOver(false);
    if (disabled) return;
    const f = e.dataTransfer.files?.[0];
    if (f) onFile(f);
  }, [onFile, disabled]);

  const isVideo = (name: string) => /\.mp4$/i.test(name);

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); if (!disabled) setOver(true); }}
      onDragLeave={() => setOver(false)}
      onDrop={handleDrop}
      onClick={() => !disabled && inputRef.current?.click()}
      className={[
        'group cursor-pointer rounded-2xl border-2 border-dashed p-8 text-center transition-all',
        over ? 'border-forest-500 bg-forest-50/70 scale-[1.01]' : 'border-forest-200 bg-white/60 hover:border-forest-300 hover:bg-forest-50/40',
        disabled ? 'opacity-50 pointer-events-none' : '',
      ].join(' ')}
    >
      <div className="mx-auto w-14 h-14 rounded-full bg-forest-100 flex items-center justify-center text-forest-600 group-hover:scale-110 transition-transform">
        <UploadCloud className="w-7 h-7" />
      </div>
      <p className="mt-3 font-semibold text-forest-800">Drag & drop a leaf photo or video</p>
      <p className="text-sm text-forest-500 mt-1">or click to browse — JPG, PNG (≤12 MB), MP4 (≤40 MB)</p>
      <div className="mt-4 flex items-center justify-center gap-4 text-xs text-forest-500">
        <span className="inline-flex items-center gap-1"><ImageIcon className="w-3.5 h-3.5" /> Photo</span>
        <span className="inline-flex items-center gap-1"><FilmIcon className="w-3.5 h-3.5" /> Video frame sampling</span>
      </div>
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT}
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onFile(f);
          e.currentTarget.value = '';
        }}
      />
    </div>
  );
}

export function isVideoName(name: string): boolean {
  return /\.mp4$/i.test(name);
}
