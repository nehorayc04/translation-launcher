// The notifications bell (sits above the avatar in the sidebar) + a small
// FLOATING window anchored next to it. Shows admin-controlled system
// notifications + updates AND the live background activity (the launcher
// self-update download / mod installs) so a download in progress is always
// visible, never "disappears". The bell glyph reflects the state:
//   • muted  → bell with a slash
//   • has    → bell with a dot (unread / an active download)
//   • none   → plain bell
// (All three glyphs are customizable via icon-manager.html → group "התראות".)
import { useEffect, useRef, useState } from "react";
import type { SVGProps } from "react";
import {
  useNotifications, setMuted, dismiss, clearAllNotifs, markAllRead,
  type Activity, type Notif,
} from "../lib/notifications";
import { api } from "../lib/eel";

// ── the 3 bell-state glyphs (defaults; user-restylable) ──
function BellNone(p: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" {...p}>
      <path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" /><path d="M13.73 21a2 2 0 0 1-3.46 0" />
    </svg>
  );
}
function BellMuted(p: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" {...p}>
      <path d="M18 8a6 6 0 0 0-9.9-5.7" /><path d="M6 8c0 7-3 9-3 9h13" /><path d="M13.73 21a2 2 0 0 1-3.46 0" />
      <line x1="3" y1="3" x2="21" y2="21" />
    </svg>
  );
}

// In-window line icons (match the icon-manager "התראות" slots; NOT emojis).
function MuteGlyph(p: SVGProps<SVGSVGElement>) {   // notify-mute-btn muted (speaker-x)
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" {...p}>
      <path d="M11 5 6 9H2v6h4l5 4z" /><line x1="22" y1="9" x2="16" y2="15" /><line x1="16" y1="9" x2="22" y2="15" />
    </svg>
  );
}
function VolumeGlyph(p: SVGProps<SVGSVGElement>) { // notify-mute-btn active (speaker + sound waves)
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" {...p}>
      <path d="M11 5 6 9H2v6h4l5 4z" /><path d="M15.54 8.46a5 5 0 0 1 0 7.07" /><path d="M19.07 4.93a10 10 0 0 1 0 14.14" />
    </svg>
  );
}
function InboxGlyph(p: SVGProps<SVGSVGElement>) {   // notify-empty (inbox)
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round" {...p}>
      <path d="M22 12h-6l-2 3h-4l-2-3H2" /><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z" />
    </svg>
  );
}

const PHASE_HE: Record<string, string> = {
  download: "מוריד…", verify: "מאמת…", apply: "מתקין…", launch: "מפעיל מתקין…",
  done: "הושלם", error: "שגיאה", cancelled: "בוטל",
};

export default function NotificationsBell({ exp }: { exp: boolean }) {
  const snap = useNotifications();
  // Blur-ramp fix lives on the panel <div> style (see the big comment there): the
  // surface is always mounted AND its closed clip-path keeps a ~2px NON-zero nub
  // (never 0x0) so QtWebEngine never tears down + rebuilds the backdrop-filter
  // layer -> no ~0.5s warm-up on open, transparent fill kept. `open` just drives
  // the clip-path wipe.
  const [open, setOpen] = useState(false);
  const btnRef   = useRef<HTMLButtonElement | null>(null);
  const panelRef = useRef<HTMLDivElement | null>(null);
  const [pos, setPos] = useState<{ top: number; left: number; maxH: number }>({ top: 100, left: 90, maxH: 460 });

  // Base glyph reflects only the MUTE state; the "you have unread" signal is a
  // separate RED dot (shown even when muted → "muted just shows a dot").
  const Icon = snap.muted ? BellMuted : BellNone;
  const accent = "#94a3b8";           // neutral bell body; the red dot is the only accent
  const hasUnread = snap.unread > 0;

  // Anchor RIGHT beside the sidebar (sidebar sits on the LEFT), at the exact
  // edge where the content column (home / games) begins. VERTICALLY it is
  // CENTERED on the bell button - so a small (few-notifications) window hugs
  // the button; as it grows its bottom slides down and PINS to the content's
  // bottom edge, so ONLY a tall/max window lands on the bottom-left corner of
  // the home/games content. Needs the live panel height → measured via a ref.
  const PANEL_W = 340;
  useEffect(() => {
    const place = () => {
      const btn = btnRef.current;
      const sb  = btn?.closest("[data-sidebar]")?.getBoundingClientRect();
      const br  = btn?.getBoundingClientRect();
      if (!sb || !br) return;
      const GAP = 12;   // the flex gap between the sidebar and the content column
      const left = Math.max(12, Math.min(window.innerWidth - PANEL_W - 12, sb.right + GAP));
      const contentTop = sb.top, contentBottom = sb.bottom;
      const maxH = Math.max(160, contentBottom - contentTop);
      const h = Math.min(maxH, panelRef.current?.offsetHeight || 200);
      const center = br.top + br.height / 2;
      let top = center - h / 2;                              // center on the button
      if (top + h > contentBottom) top = contentBottom - h; // pin bottom to content bottom
      if (top < contentTop) top = contentTop;               // cap at content top
      setPos({ top, left, maxH });
    };
    place();
    window.addEventListener("resize", place);
    // Re-measure on the panel's OWN height change (notifications load / cap) and
    // on the sidebar's rail↔wide width animation, so it stays glued + centered.
    const roP = panelRef.current && typeof ResizeObserver !== "undefined" ? new ResizeObserver(place) : null;
    if (roP && panelRef.current) roP.observe(panelRef.current);
    const sbEl = btnRef.current?.closest("[data-sidebar]");
    const roS = sbEl && typeof ResizeObserver !== "undefined" ? new ResizeObserver(place) : null;
    if (roS && sbEl) roS.observe(sbEl);
    return () => { window.removeEventListener("resize", place); roP?.disconnect(); roS?.disconnect(); };
  }, [open]);

  // Open / close = a clip-path wipe over the always-mounted (already-blurred)
  // surface. No mount/unmount → no blur ramp.
  const openPanel  = () => { markAllRead(); setOpen(true); };
  const closePanel = () => { setOpen(false); };
  const toggle = () => { (open ? closePanel : openPanel)(); };

  // Close on Escape.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") closePanel(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <>
      {/* Same single-structure layout as a NavRow: label reveal on the RIGHT,
          icon in a fixed 48px box on the LEFT (so it reads like משחקים / הורדות). */}
      <button
        ref={btnRef}
        type="button"
        data-tour="notifications"
        onClick={toggle}
        title={!exp ? "התראות" : undefined}
        className={[
          "group relative flex items-center w-full rounded-xl py-2.5 transition-colors duration-150",
          open ? "bg-white/[0.06] text-white" : "text-slate-400 hover:bg-white/[0.04] hover:text-slate-200",
        ].join(" ")}
      >
        <span
          className="relative z-[1] text-[14px] font-medium"
          style={{
            flex: "1 1 0%", minWidth: 0, overflow: "hidden", whiteSpace: "nowrap", textAlign: "right",
            opacity: exp ? 1 : 0, paddingRight: exp ? 12 : 0,
            transition: "opacity .26s ease, padding-right .26s ease",
          }}
        >
          התראות{snap.muted ? " (מושתק)" : ""}
        </span>
        <span className="relative z-[1] grid place-items-center" style={{ flex: "0 0 48px" }}>
          <span className="relative grid place-items-center" style={{ color: accent }}>
            <Icon width={20} height={20} />
            {/* RED unread dot - shown whenever there's an unread notification,
                including while muted (then it's the ONLY indicator). */}
            {hasUnread && (
              <span
                className="absolute -top-1.5 -left-1.5 grid place-items-center rounded-full text-[9px] font-extrabold text-white"
                style={{ background: "#ef4444", minWidth: 15, height: 15, padding: "0 3px", boxShadow: "0 0 8px rgba(239,68,68,0.8)" }}
              >
                {snap.unread > 9 ? "9+" : snap.unread}
              </span>
            )}
          </span>
        </span>
      </button>

      {/* click-away backdrop - only while open */}
      {open && (
        <div
          className="fixed inset-0 z-[140]"
          onMouseDown={closePanel}
          aria-hidden
        />
      )}
      {/* ONE frosted-glass surface, TRANSPARENT fill. The frost is stable from
          frame 1 by keeping its backdrop-filter compositing LAYER WARM: in
          QtWebEngine (--disable-gpu-compositing) a backdrop blur ramps over ~0.5s
          every time its compositing node is (re-)created. A closed clip of ZERO
          area (the old `inset(50% 100% 50% 0)` = 0x0) paints nothing, so Chromium
          DESTROYS the node on close and REBUILDS it on open -> the ramp. Fixes:
          (1) the CLOSED clip keeps a ~2px non-zero nub at the bell edge so the
          node is NEVER torn down (layer stays warm across open/close); (2) static
          `willChange: backdrop-filter` pins it on its own composited layer; (3)
          ALWAYS MOUNTED, opacity:1, NO transform (a transform/opacity animation
          re-triggers the ramp), open/close is a clip-path wipe only. With the
          layer warm the fill stays genuinely transparent - no opaque mask needed.
          Corner radius 24px == the home / games content panels. */}
      <div
        ref={panelRef}
        className="fixed z-[141] overflow-hidden flex flex-col"
        style={{
          top: pos.top, left: pos.left, width: PANEL_W, maxWidth: "92vw",
          maxHeight: pos.maxH,   // centered on the button, grows both ways, capped
          borderRadius: 24,      // == the home/games content panel (rounded-3xl)
          // User's choice: LIGHT blur + a SUBTLE tint. The tint (~0.5) hides the
          // sharp content DURING QtWebEngine's unavoidable ~0.5s blur warm-up (the
          // ramp can't be removed in CSS), while still reading as see-through
          // frosted glass; the lighter blur(6px) keeps it airy, not milky.
          background: "linear-gradient(180deg, rgba(18,22,44,0.50), rgba(10,12,26,0.62))",
          border: "1px solid rgba(255,255,255,0.20)",
          boxShadow: "inset 0 1px 0 rgba(255,255,255,0.18), 0 26px 70px -22px rgba(0,0,0,0.8)",
          backdropFilter: "blur(6px)",
          WebkitBackdropFilter: "blur(6px)",
          // Keep the backdrop-filter layer on its own composited surface so it is
          // never dropped and rebuilt between opens (kills the blur ramp).
          willChange: "backdrop-filter",
          // CLOSED = a ~2px non-zero nub at the bell edge (invisible + un-clickable
          // but NON-zero so the blur layer stays warm); OPEN = wipes to full panel.
          // Never collapse to 0x0 area - that tears down the layer and re-runs the
          // ~0.5s blur warm-up on every open.
          clipPath: open
            ? "inset(0 0 0 0 round 24px)"
            : "inset(calc(50% - 1px) calc(100% - 2px) calc(50% - 1px) 0 round 24px)",
          pointerEvents: open ? "auto" : "none",
          transition: open
            ? "clip-path .42s cubic-bezier(.34,1.3,.5,1)"
            : "clip-path .24s cubic-bezier(.4,0,.7,.2)",
        }}
        dir="rtl"
        onMouseDown={(e) => e.stopPropagation()}
      >
            {/* header (fixed - never scrolls) */}
            <div className="shrink-0 flex items-center gap-2 px-4 py-3 border-b border-white/10">
              {/* header icon = the SAME bell as the sidebar button (BellNone) */}
              <span className="text-[#00ffe0]"><BellNone width={17} height={17} /></span>
              <h3 className="font-bold text-white text-sm flex-1">התראות</h3>
              <button
                type="button"
                onClick={() => setMuted(!snap.muted)}
                title={snap.muted ? "בטל השתקה" : "השתק התראות"}
                className={["text-[11px] px-2 py-1 rounded-lg border transition flex items-center gap-1.5",
                  // muted → gold + speaker-x; active (not muted) → gray + sound-waves
                  snap.muted ? "border-amber-400/50 bg-amber-400/15 text-amber-300"
                             : "border-white/10 bg-white/5 text-slate-300 hover:bg-white/10"].join(" ")}
              >
                {snap.muted ? <MuteGlyph width={13} height={13} /> : <VolumeGlyph width={13} height={13} />}
                {snap.muted ? "מושתק" : "השתק"}
              </button>
            </div>

            <div className="notif-scroll flex-1 min-h-0 overflow-y-auto">
              {/* live background activities (the download that used to "disappear") */}
              {snap.activities.length > 0 && (
                <div className="px-3 pt-3">
                  <div className="text-[10px] tracking-[0.25em] text-slate-500 mb-1.5 px-1">פעילות ברקע</div>
                  {snap.activities.map((a) => <ActivityRow key={a.id} a={a} />)}
                </div>
              )}

              {/* notifications */}
              <div className="px-3 py-3">
                {snap.notifs.length === 0 && snap.activities.length === 0 ? (
                  <div className="text-center py-10 text-slate-500 text-sm">
                    <div className="grid place-items-center mb-2 text-slate-600"><InboxGlyph width={34} height={34} /></div>
                    אין התראות חדשות.
                  </div>
                ) : (
                  <>
                    {snap.notifs.length > 0 && (
                      <div className="flex items-center justify-between mb-1.5 px-1">
                        <div className="text-[10px] tracking-[0.25em] text-slate-500">הודעות מערכת ועדכונים</div>
                        <button type="button" onClick={clearAllNotifs}
                          className="text-[11px] text-slate-400 hover:text-rose-300">נקה הכל</button>
                      </div>
                    )}
                    {snap.notifs.map((n) => <NotifRow key={n.id} n={n} onClose={closePanel} />)}
                  </>
                )}
              </div>
            </div>
      </div>
    </>
  );
}

function ActivityRow({ a }: { a: Activity }) {
  const pct = Math.min(100, Math.max(0, a.pct || 0));
  const color = a.error ? "#ff5e7a" : a.active ? "#00ffe0" : "#22c55e";
  return (
    <div className="rounded-xl border border-white/12 p-2.5 mb-1.5"
         style={{
           background: "rgba(255,255,255,0.11)",
           // a touch MORE blurred/frosted than the panel window behind it
           backdropFilter: "blur(6px)", WebkitBackdropFilter: "blur(6px)",
           boxShadow: "inset 0 1px 0 rgba(255,255,255,0.12), 0 4px 14px -6px rgba(0,0,0,0.5)",
         }}>
      <div className="flex items-center justify-between gap-2">
        <span className="text-[12.5px] font-semibold text-slate-100 truncate">{a.title}</span>
        <span className="text-[11px] font-mono shrink-0" style={{ color }}>
          {a.error ? "שגיאה" : a.active ? `${pct.toFixed(0)}%` : (PHASE_HE[a.phase] ?? "הושלם")}
        </span>
      </div>
      {a.active && (
        <div className="h-1.5 mt-1.5 bg-white/8 rounded-full overflow-hidden">
          <div className="h-full rounded-full transition-[width] duration-300"
               style={{ width: `${pct}%`, background: "linear-gradient(90deg,#00ffe0,#fff700)" }} />
        </div>
      )}
      {a.detail && <div className="text-[10.5px] text-slate-500 mt-1 truncate" dir="ltr">{a.detail}</div>}
    </div>
  );
}

function NotifRow({ n, onClose }: { n: Notif; onClose: () => void }) {
  const when = (() => {
    try {
      const d = Date.now() - n.ts;
      if (d < 60_000) return "עכשיו";
      if (d < 3_600_000) return `לפני ${Math.round(d / 60_000)} דק׳`;
      if (d < 86_400_000) return `לפני ${Math.round(d / 3_600_000)} שע׳`;
      return new Date(n.ts).toLocaleDateString("he-IL", { day: "2-digit", month: "2-digit" });
    } catch { return ""; }
  })();
  const go = () => {
    if (!n.link) return;
    // A link set in the admin can be a full URL (open in the browser) OR a game
    // id (deep-link into the game panel).
    if (/^https?:\/\//i.test(n.link)) { void api.openExternal(n.link).catch(() => {}); }
    else { window.dispatchEvent(new CustomEvent("deep-link-game", { detail: { id: n.link } })); }
    onClose();
  };
  return (
    <div
      className={["group rounded-xl border p-2.5 mb-1.5 transition-colors duration-200",
        // A touch MORE frosted than the panel window; LESS transparent on hover.
        n.read ? "bg-white/[0.07] hover:bg-white/[0.16] border-white/10"
               : "bg-[#00ffe0]/[0.11] hover:bg-[#00ffe0]/[0.20] border-[#00ffe0]/30",
        n.link ? "cursor-pointer hover:border-white/25" : ""].join(" ")}
      style={{
        backdropFilter: "blur(6px)", WebkitBackdropFilter: "blur(6px)",
        boxShadow: "inset 0 1px 0 rgba(255,255,255,0.12), 0 4px 14px -6px rgba(0,0,0,0.5)",
      }}
      onClick={go}
    >
      <div className="flex items-start gap-2">
        {!n.read && <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-[#00ffe0] shrink-0" aria-hidden />}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-[12.5px] font-semibold text-slate-100 flex-1 truncate">{n.title}</span>
            <span className="text-[10px] text-slate-500 shrink-0">{when}</span>
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); dismiss(n.id); }}
              className="text-slate-500 hover:text-rose-300 text-sm leading-none shrink-0 opacity-0 group-hover:opacity-100"
              title="הסר"
            >×</button>
          </div>
          {n.body && <div className="text-[11.5px] text-slate-400 mt-0.5 leading-relaxed whitespace-pre-line">{n.body}</div>}
        </div>
      </div>
    </div>
  );
}
