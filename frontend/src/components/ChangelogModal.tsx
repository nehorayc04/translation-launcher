// "What's new" modal - a nice bulleted changelog window (per the design
// brief). Splits the changelog text into bullet points. Reusable.
import { useEffect } from "react";
import { IconOptBtnChangelogOk } from "./UiIcons";

interface Props {
  open: boolean;
  title: string;            // e.g. game title
  version?: string;         // e.g. "v1.0.0-beta.3"
  changelog: string;        // newline- or "•/-"-separated text
  accent?: string;
  onClose: () => void;
}

export default function ChangelogModal({ open, title, version, changelog, accent = "#00ffe0", onClose }: Props) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  // Bulletize: split on newlines / bullet glyphs / sentence " · " separators.
  const bullets = changelog
    .split(/\r?\n|(?:^|\s)[•\--]\s+|\s·\s/)
    .map((s) => s.trim())
    .filter(Boolean);

  return (
    <div
      className="fixed inset-0 z-[120] grid place-items-center p-4"
      style={{ direction: "rtl", background: "rgba(0,0,0,0.72)", backdropFilter: "blur(10px)" }}
      onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="w-full max-w-lg rounded-2xl border border-white/10 bg-slate-900/92 backdrop-blur-2xl
                      shadow-[0_30px_70px_-20px_rgba(0,0,0,0.85)] overflow-hidden animate-scale-in">
        {/* Header */}
        <div className="relative px-6 py-5 border-b border-white/5">
          <div className="absolute -top-10 -left-8 w-40 h-40 rounded-full blur-3xl pointer-events-none"
               style={{ background: `${accent}33` }} aria-hidden />
          <div className="relative flex items-center justify-between">
            <span dir="ltr" className="font-mono text-xs px-2 py-1 rounded-full bg-white/5 text-slate-300">{version}</span>
            <div className="text-right">
              <div className="text-[11px] font-display tracking-[0.2em]" style={{ color: accent }}>✨ &nbsp;מה חדש</div>
              <h3 className="text-white font-bold text-lg mt-0.5">{title}</h3>
            </div>
          </div>
        </div>
        {/* Bullets */}
        <div className="px-6 py-5 max-h-[55vh] overflow-y-auto">
          {bullets.length > 0 ? (
            <ul className="space-y-2.5">
              {bullets.map((b, i) => (
                <li key={i} className="flex items-start gap-3 text-right">
                  <span className="mt-2 w-1.5 h-1.5 rounded-full shrink-0" style={{ background: accent }} aria-hidden />
                  <span className="text-slate-200 text-sm leading-relaxed flex-1">{b}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-slate-400 text-sm text-center">אין פירוט שינויים לגרסה זו.</p>
          )}
        </div>
        {/* Footer */}
        <div className="px-6 py-4 border-t border-white/5 flex justify-start">
          <button
            type="button"
            onClick={onClose}
            className="inline-flex items-center gap-1.5 px-5 py-2 rounded-xl font-bold text-brand-ink transition hover:brightness-110"
            style={{ background: accent }}
          >
            <IconOptBtnChangelogOk width={18} className="shrink-0 opacity-90" />
            הבנתי
          </button>
        </div>
      </div>
    </div>
  );
}
