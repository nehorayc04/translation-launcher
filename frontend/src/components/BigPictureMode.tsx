// "Big Picture" — a full-screen, console-familiar mode. A cinematic centered
// spotlight + a bottom cover strip, driven by ←/→ (or D-pad / left-stick),
// Enter/A to open, Esc/B to exit. Designed for couch + controller use.
import { useCallback, useEffect, useRef, useState } from "react";
import type { Game } from "../lib/types";
import { accentFor } from "../lib/theme";
import { resolveCoverUrl } from "../lib/coverUrl";
import { formatVersion } from "../lib/formatVersion";
import { availabilityLabel } from "../lib/theme";

export default function BigPictureMode({
  games, onOpenGame, onExit,
}: {
  games: Game[];
  onOpenGame: (g: Game) => void;
  onExit: () => void;
}) {
  const [sel, setSel] = useState(0);
  const stripRef = useRef<HTMLDivElement>(null);
  const n = games.length;
  const clamp = (i: number) => Math.max(0, Math.min(n - 1, i));

  // Keep the selected cover centered in the strip.
  useEffect(() => {
    const strip = stripRef.current;
    if (!strip) return;
    const el = strip.children[sel] as HTMLElement | undefined;
    if (el) el.scrollIntoView({ inline: "center", block: "nearest", behavior: "smooth" });
  }, [sel]);

  // Own the keyboard while open (capture + stopImmediatePropagation so the
  // global spatial-nav doesn't double-handle). B (controller) → nav-back below.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      switch (e.key) {
        case "ArrowRight": e.preventDefault(); e.stopImmediatePropagation(); setSel((i) => clamp(i + 1)); break;
        case "ArrowLeft":  e.preventDefault(); e.stopImmediatePropagation(); setSel((i) => clamp(i - 1)); break;
        case "Enter": case " ":
          e.preventDefault(); e.stopImmediatePropagation();
          if (games[sel]) onOpenGame(games[sel]);
          break;
        case "Escape": case "Backspace":
          e.preventDefault(); e.stopImmediatePropagation(); onExit(); break;
      }
    };
    document.addEventListener("keydown", onKey, true);
    return () => document.removeEventListener("keydown", onKey, true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [games, sel]);

  // Controller "B" back (dispatched by spatialNav's gamepad loop) → exit BP.
  // (The Start/toggle event is owned by App, which unmounts this on toggle.)
  useEffect(() => {
    const back = () => onExit();
    window.addEventListener("nav-back", back);
    return () => window.removeEventListener("nav-back", back);
  }, [onExit]);

  const onWheel = useCallback((e: React.WheelEvent) => {
    if (Math.abs(e.deltaY) > Math.abs(e.deltaX)) setSel((i) => clamp(i + (e.deltaY > 0 ? 1 : -1)));
  }, [n]);

  if (n === 0) {
    return (
      <div className="fixed inset-0 z-[180] grid place-items-center" style={{ background: "#04040c", direction: "rtl" }}>
        <div className="text-center">
          <p className="text-slate-300 mb-4">אין משחקים להצגה.</p>
          <button type="button" onClick={onExit} className="px-5 py-2 rounded-xl bg-white/10 text-white">יציאה</button>
        </div>
      </div>
    );
  }

  const g = games[clamp(sel)];
  const accent = accentFor(g.theme_key);
  const avail = availabilityLabel(g.availability);

  return (
    <div className="fixed inset-0 z-[180] overflow-hidden" style={{ background: "#04040c", direction: "rtl" }}
         onWheel={onWheel}>
      {/* Cinematic blurred backdrop of the selected game. */}
      <img key={g.id} src={resolveCoverUrl(g.cover, g.id)} alt="" aria-hidden draggable={false}
           className="absolute inset-0 w-full h-full object-cover scale-125 blur-2xl opacity-40 transition-opacity duration-500"
           onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = "none"; }} />
      <div className="absolute inset-0" aria-hidden style={{
        background: `linear-gradient(to top, #04040c 12%, rgba(4,4,12,0.6) 55%, rgba(4,4,12,0.4)), radial-gradient(60% 80% at 80% 30%, ${accent}24, transparent 70%)`,
      }} />

      {/* Top bar */}
      <div className="relative z-10 flex items-center justify-between px-10 pt-7">
        <button type="button" onClick={onExit}
                className="px-4 py-2 rounded-xl text-sm text-slate-200 bg-black/40 hover:bg-black/70
                           backdrop-blur-md border border-white/10 transition flex items-center gap-2">
          ✕ יציאה <span className="text-[10px] text-slate-400">(Esc)</span>
        </button>
        <div className="text-right">
          <div className="font-display text-[10px] tracking-[0.3em] text-brand-cyan">B I G &nbsp; P I C T U R E</div>
          <div className="text-white font-bold">מנהל התרגומים</div>
        </div>
      </div>

      {/* Centered spotlight */}
      <div className="relative z-10 flex items-center gap-10 px-14 mt-6" style={{ height: "46vh" }}>
        <div className="flex-1 text-right animate-fade-in" key={`info-${g.id}`}>
          <div className="font-display text-xs tracking-[0.3em] mb-3" style={{ color: accent }}>★ &nbsp;מומלץ</div>
          <h1 className="text-6xl font-extrabold text-white leading-none mb-4 drop-shadow-[0_3px_18px_rgba(0,0,0,0.9)]">
            {g.titleHe || g.titleEn}
          </h1>
          <div className="flex items-center gap-2 justify-start mb-4 flex-wrap" dir="rtl">
            <span className="px-3 py-1 rounded-full text-xs bg-black/60 text-slate-200 ring-1 ring-white/15">{formatVersion(g.version)}</span>
            {g.availability !== "available" && (
              <span className={`px-3 py-1 rounded-full text-xs font-semibold ${avail.tone}`}>{avail.text}</span>
            )}
            {g.mod_state === "ACTIVE" && (
              <span className="px-3 py-1 rounded-full text-xs font-semibold ring-1 ring-emerald-400/40 bg-emerald-500/20 text-emerald-200">תרגום פעיל</span>
            )}
          </div>
          {g.tagline && <p className="text-slate-300 text-lg max-w-xl leading-relaxed mb-7">{g.tagline}</p>}
          <button type="button" onClick={() => onOpenGame(g)}
                  className="group relative overflow-hidden px-9 py-4 rounded-2xl font-extrabold text-brand-ink text-lg
                             shadow-[0_16px_40px_-12px_rgba(0,0,0,0.7)]"
                  style={{ background: accent }}>
            <span className="sheen-layer" aria-hidden />
            ▸ פתח &nbsp; <span className="text-sm opacity-70">(Enter)</span>
          </button>
        </div>

        {/* Big cover of the selected game. */}
        <div key={`cover-${g.id}`} className="shrink-0 animate-scale-in">
          <div className="w-[260px] aspect-[2/3] rounded-3xl overflow-hidden ring-2"
               style={{ ["--tw-ring-color" as string]: `${accent}cc`, boxShadow: `0 30px 80px -20px #000, 0 0 50px -10px ${accent}80` }}>
            <img src={resolveCoverUrl(g.cover, g.id)} alt={g.titleEn} draggable={false}
                 className="w-full h-full object-cover"
                 onError={(e) => { (e.currentTarget as HTMLImageElement).style.visibility = "hidden"; }} />
          </div>
        </div>
      </div>

      {/* Bottom cover strip (the carousel). */}
      <div className="absolute bottom-0 inset-x-0 z-10 pb-8 pt-4">
        <div ref={stripRef} className="flex gap-4 overflow-x-auto scroll-x px-14 items-end">
          {games.map((gg, i) => {
            const a = accentFor(gg.theme_key);
            const on = i === sel;
            return (
              <button key={gg.id} type="button"
                      onClick={() => (i === sel ? onOpenGame(gg) : setSel(i))}
                      className="shrink-0 rounded-xl overflow-hidden transition-all duration-300"
                      style={{
                        width: on ? 132 : 96,
                        outline: on ? `3px solid ${a}` : "1px solid rgba(255,255,255,0.12)",
                        boxShadow: on ? `0 14px 34px -10px #000, 0 0 26px -6px ${a}` : "none",
                        opacity: on ? 1 : 0.6,
                      }}>
                <div className="aspect-[2/3]">
                  <img src={resolveCoverUrl(gg.cover, gg.id)} alt={gg.titleEn} draggable={false}
                       className="w-full h-full object-cover"
                       onError={(e) => { (e.currentTarget as HTMLImageElement).style.visibility = "hidden"; }} />
                </div>
              </button>
            );
          })}
        </div>
        <div className="text-center text-[11px] text-slate-500 mt-3" dir="rtl">
          ←/→ או D-pad לניווט · Enter / A לפתיחה · Esc / B ליציאה
        </div>
      </div>
    </div>
  );
}
