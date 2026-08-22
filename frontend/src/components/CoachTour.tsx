// Anchored coach-mark product tour - highlights the REAL UI elements (the
// sidebar buttons, the scan button, a game card, …) and explains what each one
// does, step by step, the way big-company apps onboard you. A spotlight darkens
// everything except the current target; a tooltip card sits beside it with
// Next / Back / Skip. Steps can navigate the app first (nav event) and the tour
// waits for the target to mount. Anchors are `data-tour="…"` attributes.
import { useCallback, useEffect, useLayoutEffect, useRef, useState, type CSSProperties } from "react";
import { getSidebarMode } from "../lib/themePrefs";
import { IconOptBtnTourBack, IconOptLinkTourSkip } from "./UiIcons";

type Placement = "right" | "left" | "top" | "bottom" | "center";

interface Step {
  sel?: string;        // CSS selector of the target; omit → a centered card
  title: string;
  body: string;
  placement?: Placement;
  nav?: string;        // window event dispatched before the step (e.g. "nav-library")
}

const STEPS: Step[] = [
  { title: "סיור קצר בתוכנה",
    body: "אראה לך בקצרה מה עושה כל חלק בתוכנה, שלב-שלב. אפשר לדלג בכל רגע, ותמיד לפתוח את הסיור שוב מ'הגדרות → כללי'.",
    placement: "center", nav: "nav-home" },
  { sel: '[data-tour="nav-home"]', placement: "left", nav: "nav-home",
    title: "דף הבית",
    body: "מסך הפתיחה: תרגומים מובילים, חדשות ועדכונים וסטטיסטיקות. נקודת המוצא שלך." },
  { sel: '[data-tour="nav-games"]', placement: "left", nav: "nav-library",
    title: "משחקים",
    body: "כל המשחקים הנתמכים. כאן מאתרים משחק, סורקים כוננים ופותחים את עמוד המשחק." },
  { sel: '[data-tour="scan"]', placement: "bottom",
    title: "סריקת כוננים מלאה",
    body: "לא רואה את המשחק שלך? לחיצה כאן סורקת את כל הכוננים ומאתרת התקנות אוטומטית. אפשר גם להזין נתיב ידני בתוך כרטיס המשחק." },
  { sel: '[data-tour="game-card"]', placement: "top",
    title: "כרטיס משחק",
    body: "לחיצה על משחק פותחת את עמודו: שם מתקינים את התרגום, בוחרים שפה, ומנהלים גרסאות והגדרות." },
  { sel: '[data-tour="nav-software"]', placement: "left", nav: "nav-software",
    title: "תוכנות",
    body: "לא רק משחקים - כאן התרגומים לתוכנות (כמו VirtualDJ). ההתקנה והשימוש זהים לגמרי למשחק." },
  { sel: '[data-tour="nav-plugins"]', placement: "left", nav: "nav-plugins",
    title: "תוספים",
    body: "תוספים שמרחיבים את התוכנה ומגיעים מהענן - בלי להתקין מחדש. כאן נמצא 'גיבוי שמירות משחקים אוטומטי': הוא מאתר לבד את תיקיות השמירה, מגבה לפי תזמון, ומאפשר לשחזר בלחיצה." },
  { sel: '[data-tour="nav-downloads"]', placement: "left", nav: "nav-downloads",
    title: "הורדות ועדכונים",
    body: "עדכוני התוכנה + עדכונים לתרגומים המותקנים. רואים כאן את הגרסה המותקנת מול הזמינה, ומעדכנים בלחיצה אחת." },
  { sel: '[data-tour="notifications"]', placement: "left",
    title: "התראות",
    body: "פעמון ההתראות: הודעות על עדכוני תרגום וחדשות, ומעקב אחרי פעולות שרצות ברקע. נקודה אדומה = יש חדש. אפשר להשתיק הכול מתוך החלון." },
  { sel: '[data-tour="profile"]', placement: "left",
    title: "האזור האישי",
    body: "התחברות/הרשמה והפרופיל שלך - רכישות, מועדפים והגדרות חשבון. לחיצה על הפרופיל פותחת את האזור האישי." },
  { sel: '[data-tour="nav-settings"]', placement: "left",
    title: "הגדרות",
    body: "הפעלה עם Windows, מגש מערכת, שלט, פרטיות ונתיבים. ב'מראה' אפשר להחליף את אייקון התוכנה (עיגול/ריבוע), וב'יומן שינויים' רואים בדיוק מה השתנה בכל גרסה. גם הסיור הזה נפתח שוב מכאן." },
];

const PAD = 8;      // spotlight padding around the target
const GAP = 14;     // tooltip gap from the target
const CARD_W = 320;
const MARGIN = 12;  // min distance the card keeps from the window edge

interface Rect { x: number; y: number; w: number; h: number }

const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(v, hi));

const OPPOSITE: Partial<Record<Placement, Placement>> =
  { left: "right", right: "left", top: "bottom", bottom: "top" };

/** Position the tooltip BESIDE the target.
 *
 * Two hard rules, both of which the old guess-the-height math broke:
 *  1. The card must NEVER cover the element it explains. Every candidate sits
 *     fully outside the target on the main axis, and we clamp only along the
 *     CROSS axis - so clamping can't slide the card back over the target.
 *  2. The card must NEVER spill outside the app window. We test each side with
 *     the card's REAL measured size and keep the first side where it fits
 *     entirely; only if no side fits (tiny window) do we centre it.
 * Sides are tried preferred → opposite → the rest. */
function placeBeside(r: Rect, preferred: Placement, w: number, h: number,
                     vw: number, vh: number): CSSProperties {
  const cand = (side: Placement) => {
    switch (side) {
      case "left":  return { left: r.x - w - GAP,         top: r.y + r.h / 2 - h / 2 };
      case "right": return { left: r.x + r.w + GAP,       top: r.y + r.h / 2 - h / 2 };
      case "top":   return { left: r.x + r.w / 2 - w / 2, top: r.y - h - GAP };
      default:      return { left: r.x + r.w / 2 - w / 2, top: r.y + r.h + GAP };
    }
  };
  const order: Placement[] = [];
  const push = (s?: Placement) => { if (s && s !== "center" && !order.includes(s)) order.push(s); };
  push(preferred);
  push(OPPOSITE[preferred]);
  (["left", "right", "bottom", "top"] as Placement[]).forEach(push);

  for (const side of order) {
    let { left, top } = cand(side);
    if (side === "left" || side === "right") top = clamp(top, MARGIN, vh - h - MARGIN);
    else                                     left = clamp(left, MARGIN, vw - w - MARGIN);
    const fits = left >= MARGIN && top >= MARGIN
              && left + w <= vw - MARGIN && top + h <= vh - MARGIN;
    if (fits) return { left, top };
  }
  return {   // nothing fits beside it - centre, still inside the window
    left: clamp(vw / 2 - w / 2, MARGIN, Math.max(MARGIN, vw - w - MARGIN)),
    top:  clamp(vh / 2 - h / 2, MARGIN, Math.max(MARGIN, vh - h - MARGIN)),
  };
}

export default function CoachTour({ onClose }: { onClose: () => void }) {
  const [i, setI] = useState(0);
  const [rect, setRect] = useState<Rect | null>(null);   // null → centered card
  const restoreSidebar = useRef<string | null>(null);
  const step = STEPS[i];
  const last = i === STEPS.length - 1;

  // The card's REAL size + the live window size drive the placement. Guessing
  // the height (the old code) is what put the card on top of the target and let
  // long cards run off the bottom edge.
  const cardRef = useRef<HTMLDivElement>(null);
  const [cardH, setCardH] = useState(210);
  const [vp, setVp] = useState({ w: window.innerWidth, h: window.innerHeight });

  useLayoutEffect(() => {
    const el = cardRef.current;
    if (!el) return;
    const h = el.getBoundingClientRect().height;
    if (h > 0 && Math.abs(h - cardH) > 1) setCardH(h);
  });

  useEffect(() => {
    const onR = () => setVp({ w: window.innerWidth, h: window.innerHeight });
    window.addEventListener("resize", onR);
    return () => window.removeEventListener("resize", onR);
  }, []);

  const finish = useCallback(() => {
    // Restore the sidebar to the user's chosen mode before closing.
    if (restoreSidebar.current) {
      window.dispatchEvent(new CustomEvent("sidebarmode", { detail: restoreSidebar.current }));
      restoreSidebar.current = null;
    }
    onClose();
  }, [onClose]);

  // Force the sidebar OPEN for the duration of the tour so the nav buttons are
  // fully visible while highlighted (restored on close).
  useEffect(() => {
    restoreSidebar.current = getSidebarMode();
    window.dispatchEvent(new CustomEvent("sidebarmode", { detail: "wide" }));
    return () => {
      if (restoreSidebar.current) {
        window.dispatchEvent(new CustomEvent("sidebarmode", { detail: restoreSidebar.current }));
        restoreSidebar.current = null;
      }
    };
  }, []);

  // Resolve the current step's target: fire its nav event, then poll for the
  // element to mount (up to ~1s), measure it. No selector → centered card.
  useEffect(() => {
    let alive = true;
    let raf = 0;
    let tries = 0;
    if (step.nav) window.dispatchEvent(new CustomEvent(step.nav));

    const measure = () => {
      if (!alive) return;
      if (!step.sel) { setRect(null); return; }
      const el = document.querySelector(step.sel) as HTMLElement | null;
      if (!el) {
        if (tries++ < 60) { raf = requestAnimationFrame(measure); return; }
        setRect(null);   // target never mounted (e.g. no games installed) → centered
        return;
      }
      const r = el.getBoundingClientRect();
      // If the element exists but has no size yet (mid-transition), retry.
      if ((r.width === 0 || r.height === 0) && tries++ < 60) {
        raf = requestAnimationFrame(measure); return;
      }
      setRect({ x: r.left, y: r.top, w: r.width, h: r.height });
    };
    // Give a nav switch a beat to mount before the first measure.
    raf = requestAnimationFrame(() => requestAnimationFrame(measure));
    return () => { alive = false; cancelAnimationFrame(raf); };
  }, [step]);

  // Keep the spotlight aligned if the window resizes.
  useEffect(() => {
    const onResize = () => {
      if (!step.sel) return;
      const el = document.querySelector(step.sel) as HTMLElement | null;
      if (el) { const r = el.getBoundingClientRect(); setRect({ x: r.left, y: r.top, w: r.width, h: r.height }); }
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [step]);

  // Keyboard: Esc skips, ←/Enter next, → back.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") { e.preventDefault(); finish(); }
      else if (e.key === "ArrowLeft" || e.key === "Enter") { e.preventDefault(); setI((x) => (x === STEPS.length - 1 ? x : x + 1)); }
      else if (e.key === "ArrowRight") { e.preventDefault(); setI((x) => Math.max(0, x - 1)); }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [finish]);

  const next = () => (last ? finish() : setI((x) => x + 1));
  const back = () => setI((x) => Math.max(0, x - 1));

  // ── Tooltip position: beside the target, always inside the window ──
  const place: Placement = rect ? (step.placement ?? "bottom") : "center";
  const cardStyle: CSSProperties =
    (!rect || place === "center")
      ? { left: clamp(vp.w / 2 - CARD_W / 2, MARGIN, Math.max(MARGIN, vp.w - CARD_W - MARGIN)),
          top:  clamp(vp.h / 2 - cardH / 2,  MARGIN, Math.max(MARGIN, vp.h - cardH - MARGIN)) }
      : placeBeside(rect, place, CARD_W, cardH, vp.w, vp.h);

  return (
    <div className="fixed inset-0 z-[200]" style={{ direction: "rtl" }}>
      {/* Spotlight - a transparent hole over the target, everything else dimmed
          by a huge box-shadow. Full-screen dim when there's no target. */}
      {rect ? (
        <div
          className="absolute rounded-xl pointer-events-none transition-all duration-300"
          style={{
            left: rect.x - PAD, top: rect.y - PAD,
            width: rect.w + PAD * 2, height: rect.h + PAD * 2,
            boxShadow: "0 0 0 9999px rgba(4,4,12,0.74)",
            outline: "2px solid rgba(0,255,224,0.9)",
            outlineOffset: 2,
          }}
        />
      ) : (
        <div className="absolute inset-0" style={{ background: "rgba(4,4,12,0.74)" }} />
      )}

      {/* Click-catcher: clicking the dim area advances (but not on the card). */}
      <div className="absolute inset-0" onClick={next} />

      {/* Tooltip card */}
      <div
        ref={cardRef}
        className="absolute rounded-2xl border border-white/10 bg-slate-900/95 backdrop-blur-2xl
                   shadow-[0_30px_70px_-20px_rgba(0,0,0,0.85)] p-5 animate-scale-in"
        style={{ width: CARD_W, ...cardStyle }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-white font-extrabold text-[15px]">{step.title}</h3>
          <span className="text-[11px] font-mono text-slate-500">{i + 1} / {STEPS.length}</span>
        </div>
        <p className="text-slate-300 text-[13px] leading-relaxed mb-4">{step.body}</p>

        {/* progress dots */}
        <div className="flex gap-1.5 mb-4">
          {STEPS.map((_, k) => (
            <span key={k} className="h-1 rounded-full transition-all duration-300"
                  style={{ width: k === i ? 20 : 6, background: k === i ? "#00ffe0" : "rgba(255,255,255,0.25)" }} />
          ))}
        </div>

        <div className="flex items-center justify-between">
          <button type="button" onClick={finish}
                  className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200 transition"><IconOptLinkTourSkip width={18} className="shrink-0 opacity-90" />דלג על הסיור</button>
          <div className="flex gap-2">
            {i > 0 && (
              <button type="button" onClick={back}
                      className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-white/5 border border-white/10 text-slate-200 hover:bg-white/10 text-xs font-semibold transition">
                <IconOptBtnTourBack width={18} className="shrink-0 opacity-90" />
                הקודם
              </button>
            )}
            <button type="button" onClick={next}
                    className="group relative overflow-hidden px-4 py-1.5 rounded-lg bg-brand-cyan text-brand-ink text-xs font-bold transition hover:brightness-110">
              <span className="sheen-layer" aria-hidden />
              {last ? "סיום ▸" : "הבא"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
