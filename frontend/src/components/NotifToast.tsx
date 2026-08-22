// A NEW admin/system notification "pops" as a floating glass card (top-right),
// the way the user asked: transparent by default, LESS transparent (more solid)
// on hover, honoring line breaks, sliding in/out, auto-dismissing, and clickable
// to deep-link a game. It is the visual half of the "notif-pop" flow (the native
// Windows notification is fired separately in App). MUTED never pops (the store
// simply doesn't dispatch "notif-pop" - only the red bell dot appears).
//
// NO backdrop-filter: QtWebEngine composites a backdrop blur in progressive
// stages ("gets milkier after ~1s"), so we use a fixed translucent fill only -
// it renders identically from frame 1 in the "very transparent" look.
import { useEffect, useRef, useState } from "react";
import { api } from "../lib/eel";

interface Pop { key: number; title: string; body?: string; link?: string | null }

let SEQ = 0;

export default function NotifToast() {
  const [pops, setPops] = useState<Pop[]>([]);

  // Listen for the store's "notif-pop" events. Cap to the 4 most-recent cards
  // so a burst can't cover the screen; newest is rendered on top.
  useEffect(() => {
    const onPop = (e: Event) => {
      const d = (e as CustomEvent).detail as { title?: string; body?: string; link?: string | null } | undefined;
      const title = d?.title?.trim();
      if (!title) return;
      setPops((cur) => [{ key: ++SEQ, title, body: d?.body, link: d?.link ?? null }, ...cur].slice(0, 4));
    };
    window.addEventListener("notif-pop", onPop);
    return () => window.removeEventListener("notif-pop", onPop);
  }, []);

  const remove = (key: number) => setPops((cur) => cur.filter((p) => p.key !== key));

  if (pops.length === 0) return null;
  return (
    <div className="fixed top-4 right-4 z-[190] flex flex-col gap-2.5 items-end pointer-events-none" dir="rtl">
      {pops.map((p) => <ToastCard key={p.key} pop={p} onDone={() => remove(p.key)} />)}
    </div>
  );
}

function ToastCard({ pop, onDone }: { pop: Pop; onDone: () => void }) {
  const [entered, setEntered] = useState(false);
  const [leaving, setLeaving] = useState(false);
  const [hover, setHover]   = useState(false);
  const timer = useRef<number | null>(null);

  const close = () => {
    if (leaving) return;
    setLeaving(true);
    window.setTimeout(onDone, 300);   // let the exit transition play, then unmount
  };
  const arm   = () => { if (timer.current) window.clearTimeout(timer.current); timer.current = window.setTimeout(close, 8000); };
  const clear = () => { if (timer.current) { window.clearTimeout(timer.current); timer.current = null; } };

  // Enter next frame; auto-dismiss after 8s (paused while hovered).
  useEffect(() => {
    const raf = requestAnimationFrame(() => setEntered(true));
    arm();
    return () => { cancelAnimationFrame(raf); clear(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const go = () => {
    if (pop.link) {
      if (/^https?:\/\//i.test(pop.link)) { void api.openExternal(pop.link).catch(() => {}); }
      else { window.dispatchEvent(new CustomEvent("deep-link-game", { detail: { id: pop.link } })); }
    }
    close();
  };

  const shown = entered && !leaving;
  return (
    <div
      className="pointer-events-auto rounded-2xl overflow-hidden"
      style={{
        width: 330, maxWidth: "88vw",
        // Solid-ish glass (the pop-ups were "too transparent") → a touch more
        // solid on hover.
        background: hover
          ? "linear-gradient(180deg, rgba(30,34,66,0.90), rgba(14,17,36,0.94))"
          : "linear-gradient(180deg, rgba(24,28,56,0.80), rgba(11,13,30,0.88))",
        border: `1px solid ${hover ? "rgba(255,255,255,0.34)" : "rgba(255,255,255,0.24)"}`,
        boxShadow: "inset 0 1px 0 rgba(255,255,255,0.18), 0 24px 60px -20px rgba(0,0,0,0.8)",
        opacity:   shown ? 1 : 0,
        transform: shown ? "translateX(0) scale(1)" : "translateX(26px) scale(0.96)",
        transition: leaving
          ? "opacity .26s ease, transform .26s cubic-bezier(.4,0,.7,.2)"
          : "opacity .3s ease, transform .42s cubic-bezier(.34,1.42,.5,1), background .2s ease, border-color .2s ease",
      }}
      onMouseEnter={() => { setHover(true); clear(); }}
      onMouseLeave={() => { setHover(false); arm(); }}
    >
      <div className="flex items-stretch">
        {/* accent rail */}
        <span className="w-1 shrink-0" style={{ background: "linear-gradient(180deg,#00ffe0,#fff700)" }} aria-hidden />
        <div className={"flex-1 min-w-0 p-3 " + (pop.link ? "cursor-pointer" : "")} onClick={pop.link ? go : undefined}>
          <div className="flex items-start gap-2">
            <span className="text-[#00ffe0] mt-0.5 shrink-0">
              <svg viewBox="0 0 24 24" width={16} height={16} fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                <path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" /><path d="M13.73 21a2 2 0 0 1-3.46 0" />
              </svg>
            </span>
            <div className="flex-1 min-w-0">
              <div className="text-[13px] font-bold text-white leading-snug">{pop.title}</div>
              {pop.body && (
                <div className="text-[11.5px] text-slate-300 mt-0.5 leading-relaxed whitespace-pre-line">{pop.body}</div>
              )}
              {pop.link && <div className="text-[11px] text-[#00ffe0] mt-1 font-semibold">לחץ לפתיחה ←</div>}
            </div>
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); close(); }}
              className="text-slate-400 hover:text-rose-300 text-base leading-none shrink-0 -mt-0.5"
              aria-label="סגור"
            >×</button>
          </div>
        </div>
      </div>
    </div>
  );
}
