// "What's new" - a large floating card over a dark backdrop, shown ONCE on the
// first launch after the app updates to a new version.
//
// It deliberately shows ONLY the newest version's changes (CHANGELOG[0]); the
// full per-version history lives in Settings → "יומן שינויים" (linked at the
// bottom). Gated by localStorage `lastSeenVersion`, so it never nags twice.
import { useEffect } from "react";
import { CHANGELOG } from "../lib/changelog";

const LS_KEY = "lastSeenVersion";

/** The version whose notes the What's-New card would show. */
export function currentChangelogVersion(): string {
  return CHANGELOG[0]?.version ?? "";
}

/** True when this build is NEWER than whatever the user last saw the card for.
 *  A brand-new install has no key: the caller decides (we skip it there and just
 *  record the version, so a first-run user gets the guided tour, not both). */
export function hasUnseenVersion(): boolean {
  try {
    const seen = localStorage.getItem(LS_KEY);
    return !!currentChangelogVersion() && seen !== currentChangelogVersion();
  } catch { return false; }
}

/** Remember that the user has seen this version's notes (also used to silence
 *  the card on a first-ever install). */
export function markVersionSeen(): void {
  try { localStorage.setItem(LS_KEY, currentChangelogVersion()); } catch { /* ignore */ }
}

export default function WhatsNewModal({ onClose }: { onClose: () => void }) {
  const entry = CHANGELOG[0];

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") { e.preventDefault(); onClose(); } };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  if (!entry) return null;

  const fmtDate = (iso: string) => {
    try {
      return new Date(iso + "T00:00:00").toLocaleDateString("he-IL",
        { day: "numeric", month: "long", year: "numeric" });
    } catch { return iso; }
  };

  return (
    <div
      className="fixed inset-0 z-[190] grid place-items-center p-6 animate-fade-in"
      style={{ direction: "rtl", background: "rgba(4,4,12,0.82)" }}
      onMouseDown={onClose}
    >
      <div
        className="w-full max-w-2xl max-h-[86vh] flex flex-col rounded-2xl border border-white/10
                   bg-slate-900/95 shadow-[0_40px_90px_-20px_rgba(0,0,0,0.9)] overflow-hidden animate-scale-in"
        onMouseDown={(e) => e.stopPropagation()}
      >
        {/* header */}
        <div className="relative px-7 pt-7 pb-5 shrink-0">
          <div className="absolute -top-16 left-1/2 -translate-x-1/2 w-72 h-40 rounded-full bg-brand-cyan/15 blur-3xl" aria-hidden />
          <div className="relative">
            <div className="flex items-center gap-2.5 flex-wrap mb-2">
              <span className="text-2xl">🎉</span>
              <h2 className="text-white font-extrabold text-2xl">מה חדש בגרסה {entry.version}</h2>
              <span className="text-[11px] font-bold px-2 py-0.5 rounded-md
                               bg-emerald-500/15 text-emerald-200 ring-1 ring-emerald-400/30">
                עודכן זה עתה
              </span>
              <span className="text-slate-500 text-[12px] mr-auto">{fmtDate(entry.date)}</span>
            </div>
            {entry.headline && (
              <p className="text-slate-300 text-[14px] leading-relaxed font-semibold">{entry.headline}</p>
            )}
          </div>
        </div>

        {/* body - only THIS version's changes */}
        <div className="flex-1 min-h-0 overflow-y-auto px-7 pb-2">
          <div className="flex flex-col gap-5">
            {entry.groups.map((g) => (
              <div key={g.label}>
                <div className="text-white text-[15px] font-bold text-right mb-2 inline-flex items-center gap-2">
                  <span className="w-1 h-4 rounded-full bg-brand-cyan shadow-[0_0_10px_#00ffe0]" aria-hidden />
                  {g.label}
                </div>
                <ul className="space-y-2">
                  {g.items.map((it, k) => (
                    <li key={k} className="text-slate-300 text-[13.5px] leading-relaxed text-right flex gap-2.5">
                      <span className="text-[#00ffe0] shrink-0 mt-[2px]">•</span>
                      <span className="flex-1">{it}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>

        {/* footer */}
        <div className="px-7 py-5 border-t border-white/5 flex items-center justify-between gap-3 shrink-0">
          <span className="text-slate-500 text-[12px]">
            את ההיסטוריה המלאה של כל הגרסאות תמצא ב'הגדרות → יומן שינויים'.
          </span>
          <button
            type="button"
            onClick={onClose}
            className="group relative overflow-hidden px-6 py-2.5 rounded-xl bg-brand-cyan text-brand-ink
                       text-sm font-bold transition hover:brightness-110 shrink-0"
          >
            <span className="sheen-layer" aria-hidden />
            הבנתי, קדימה
          </button>
        </div>
      </div>
    </div>
  );
}
