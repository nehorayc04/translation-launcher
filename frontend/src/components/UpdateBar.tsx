// Bottom status / news ticker. Live pulse dot on the right.
import { useEffect, useState } from "react";

const NEWS = [
  "תרגום Cyberpunk 2077 — 72% הושלמו",
  "פרויקט האתר עודכן עם 6 סצנות תלת-ממדיות",
  "תוספת תמיכה במשחקים: Witcher 3, BG3, Elden Ring",
];

export default function UpdateBar({ status }: { status?: string }) {
  const [idx, setIdx] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setIdx((i) => (i + 1) % NEWS.length), 4500);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="glass-strong rounded-2xl flex items-center px-4 h-12 flex-shrink-0">
      {/* RIGHT (RTL start): title + pulse */}
      <div className="flex items-center gap-2 order-1 mr-0 ml-auto">
        <span className="font-semibold text-slate-100 text-[13px]">עדכוני מערכת</span>
        <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse-dot
                         shadow-[0_0_10px_rgba(52,211,153,0.7)]" />
      </div>

      {/* CENTER: ticker (or status override) */}
      <div className="flex-1 text-center text-brand-cyan text-[12px] truncate order-2 px-4">
        {status ?? NEWS[idx]}
      </div>

      {/* LEFT: version */}
      <div className="text-[11px] text-slate-500 order-3">
        גרסה אחרונה: v1.0.0
      </div>
    </div>
  );
}
