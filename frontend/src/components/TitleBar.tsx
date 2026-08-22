// Custom (frameless) title bar - rendered ONLY when the Qt window is frameless
// (Settings → פס כותרת מותאם). The window has no native frame; this bar draws
// the app title + minimize/maximize/close, drives the window MOVE via
// startSystemMove (bridge) on drag, and edge RESIZE via startSystemResize
// (the ResizeHandles below). Everything is a no-op on the Eel dev build.
import { useEffect, useState } from "react";
import type { PointerEvent as ReactPointerEvent } from "react";
import { api } from "../lib/eel";

// window-control glyphs (win-minimize / win-maximize / win-close defaults -
// customizable via icon-manager.html → group "פס חלון").
// window-control glyphs = Flaticon UICONS "minus" / "square" / "cross" (user's picks).
const IcoMin = () => (
  <svg width={13} height={13} viewBox="0 0 24 24" fill="currentColor"><path d="M2.87 11.13H21.2Q21.53 11.13 21.77 11.4Q22 11.67 22 12Q22 12.33 21.77 12.6Q21.53 12.87 21.2 12.87H2.87Q2.47 12.8 2.23 12.57Q2 12.33 2 12Q2 11.67 2.23 11.4Q2.47 11.13 2.8 11.13Z" /></svg>
);
const IcoMax = () => (
  <svg width={12} height={12} viewBox="0 0 24 24" fill="currentColor"><path d="M17.87 2H6.2Q5.07 2 4.1 2.57Q3.13 3.13 2.57 4.1Q2 5.07 2 6.2V17.8Q2 18.93 2.57 19.9Q3.13 20.87 4.1 21.43Q5.07 22 6.13 22H17.87Q18.93 22 19.9 21.43Q20.87 20.87 21.43 19.9Q22 18.93 22 17.8V6.13Q22 5.07 21.43 4.1Q20.87 3.13 19.9 2.57Q18.93 2 17.8 2ZM20.33 17.8Q20.33 18.87 19.6 19.6Q18.87 20.33 17.8 20.33H6.2Q5.13 20.33 4.4 19.6Q3.67 18.87 3.67 17.87V6.13Q3.67 5.13 4.4 4.4Q5.13 3.67 6.13 3.67H17.87Q18.87 3.67 19.6 4.4Q20.33 5.13 20.33 6.2Z" /></svg>
);
const IcoRestore = () => (
  <svg width={13} height={13} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round"><rect x="8" y="8" width="11" height="11" rx="2" /><path d="M5 16V6a2 2 0 0 1 2-2h10" /></svg>
);
const IcoClose = () => (
  <svg width={13} height={13} viewBox="0 0 24 24" fill="currentColor"><path d="M21.73 2.27Q21.53 2 21.17 2Q20.8 2 20.6 2.27L12 10.8L3.4 2.27Q3.2 2 2.83 2Q2.47 2 2.27 2.27Q2 2.47 2 2.83Q2 3.2 2.27 3.4L10.8 12L2.27 20.6Q2 20.8 2 21.17Q2 21.53 2.27 21.73Q2.47 22 2.83 22Q3.2 22 3.4 21.73L12 13.2L20.6 21.73Q20.8 22 21.17 22Q21.53 22 21.73 21.73Q22 21.53 22 21.17Q22 20.8 21.73 20.6L13.2 12L21.73 3.4Q22 3.2 22 2.83Q22 2.47 21.73 2.27Z" /></svg>
);

// 8 thin edge/corner drag zones → startSystemResize with the matching edge.
const EDGES: { e: string; cls: string }[] = [
  { e: "top",          cls: "top-0 left-3 right-3 h-[5px] cursor-ns-resize" },
  { e: "bottom",       cls: "bottom-0 left-3 right-3 h-[5px] cursor-ns-resize" },
  { e: "left",         cls: "left-0 top-3 bottom-3 w-[5px] cursor-ew-resize" },
  { e: "right",        cls: "right-0 top-3 bottom-3 w-[5px] cursor-ew-resize" },
  { e: "top-left",     cls: "top-0 left-0 w-3 h-3 cursor-nwse-resize" },
  { e: "top-right",    cls: "top-0 right-0 w-3 h-3 cursor-nesw-resize" },
  { e: "bottom-left",  cls: "bottom-0 left-0 w-3 h-3 cursor-nesw-resize" },
  { e: "bottom-right", cls: "bottom-0 right-0 w-3 h-3 cursor-nwse-resize" },
];

export function ResizeHandles() {
  return (
    <>
      {EDGES.map(({ e, cls }) => (
        <div
          key={e}
          className={"fixed z-[195] " + cls}
          onMouseDown={(ev) => { if (ev.button !== 0) return; ev.preventDefault(); void api.windowStartResize(e); }}
        />
      ))}
    </>
  );
}

export default function TitleBar() {
  const [max, setMax] = useState(false);
  // Keep the max/restore glyph in sync with the ACTUAL window state. The window
  // can be un-maximized WITHOUT the button - Aero Snap (drag a maximized window
  // down), the Win+Down shortcut, snap-layouts - and each of those resizes the
  // web content, so a debounced re-query on `resize` catches them all. Without
  // this the button was stuck on "restore" after a drag-restore.
  useEffect(() => {
    let t: number | undefined;
    const sync = () => { void api.windowIsMaximized().then(setMax).catch(() => {}); };
    const onResize = () => { window.clearTimeout(t); t = window.setTimeout(sync, 90); };
    sync();
    window.addEventListener("resize", onResize);
    window.addEventListener("focus", sync);
    return () => { window.clearTimeout(t); window.removeEventListener("resize", onResize); window.removeEventListener("focus", sync); };
  }, []);

  // Start the native window MOVE only AFTER the pointer actually moves past a
  // small threshold. A plain click on the bar - and the two stationary presses
  // of a double-click-to-maximize - must NOT enter Windows' modal move loop
  // (startSystemMove), or that loop swallows the release and the bar / maximize
  // "sticks". A genuine drag (pointer moves) still starts the move as before.
  const onBarPointerDown = (e: ReactPointerEvent) => {
    if (e.button !== 0) return;
    if ((e.target as HTMLElement).closest("[data-win-btn]")) return;   // not when pressing a control
    const sx = e.clientX, sy = e.clientY;
    let started = false;
    const onMove = (ev: PointerEvent) => {
      if (started) return;
      if (Math.abs(ev.clientX - sx) > 4 || Math.abs(ev.clientY - sy) > 4) {
        started = true;
        cleanup();
        void api.windowStartDrag();
      }
    };
    const cleanup = () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", cleanup);
      window.removeEventListener("pointercancel", cleanup);
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", cleanup);
    window.addEventListener("pointercancel", cleanup);
  };
  const toggleMax = async () => { try { setMax(await api.windowToggleMaximize()); } catch { /* ignore */ } };

  return (
    <div
      className="relative z-[190] h-9 shrink-0 flex items-center select-none"
      style={{
        // Frosted glass (not a solid dark bar). Always mounted → the blur is
        // composited once at startup (no open-animation ramp).
        background: "rgba(12,14,30,0.34)",
        backdropFilter: "blur(14px)", WebkitBackdropFilter: "blur(14px)",
        borderBottom: "1px solid rgba(255,255,255,0.08)",
      }}
      dir="ltr"
      onPointerDown={onBarPointerDown}
      onDoubleClick={toggleMax}
    >
      {/* empty drag region (the app icon + name were removed per request) */}
      <div className="flex-1 h-full" />
      {/* window controls - top-right (Windows convention). NO square hover box:
          the GLYPH itself recolors + glows on hover (X → red, min/max → brand glow).
          They fire on POINTER-DOWN (respond on press, not release) and the wrapper
          swallows mousedown/double-click so the bar's drag (startSystemMove) + the
          double-click-to-maximize never compete with a control press → no click lag. */}
      <div className="flex items-stretch h-full" data-win-btn
        onMouseDown={(e) => e.stopPropagation()} onDoubleClick={(e) => e.stopPropagation()}>
        <button type="button" data-win-btn title="מזעור"
          onPointerDown={(e) => { e.preventDefault(); e.stopPropagation(); void api.windowMinimize(); }}
          className="w-11 grid place-items-center text-slate-400 hover:text-[#00ffe0] hover:drop-shadow-[0_0_7px_#00ffe0e6] transition-[color,filter] duration-150">{IcoMin()}</button>
        <button type="button" data-win-btn title={max ? "שחזור" : "הגדלה"}
          onPointerDown={(e) => { e.preventDefault(); e.stopPropagation(); void toggleMax(); }}
          className="w-11 grid place-items-center text-slate-400 hover:text-[#fff700] hover:drop-shadow-[0_0_7px_#fff700d9] transition-[color,filter] duration-150">{max ? IcoRestore() : IcoMax()}</button>
        <button type="button" data-win-btn title="סגירה"
          onPointerDown={(e) => { e.preventDefault(); e.stopPropagation(); void api.windowClose(); }}
          className="w-11 grid place-items-center text-slate-400 hover:text-[#ff4d6d] hover:drop-shadow-[0_0_8px_#ff4d6df2] transition-[color,filter] duration-150">{IcoClose()}</button>
      </div>
    </div>
  );
}
