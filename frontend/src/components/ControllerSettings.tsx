// Settings → "שלט": remap the controller's buttons, in-game style. Click "שנה"
// on an action → edit mode → the next button you press on the pad becomes that
// action's binding. Auto-detects the connected pad (PS5 / PS4 / Xbox) and shows
// ITS realistic controller icon + the matching button glyphs. Plus a "reset to
// defaults". Directional nav (D-pad / left stick) and scrolling (right stick)
// are fixed.
import { useEffect, useState, type ReactNode } from "react";
import {
  GP_ACTIONS, getGamepadMap, setGamepadBinding, resetGamepadMap, gpButtonName,
  beginGamepadCapture, endGamepadCapture, getConnectedController,
  type GpAction, type ControllerType,
} from "../lib/gamepadMap";
import { IconOptHdrControllerMapping, IconOptBtnControllerReset, IconOptBtnControllerRemap } from "./UiIcons";
import { CONTROLLER_IMG } from "../lib/controllerIcons";

// ── Per-controller icons ────────────────────────────────────────────────
// The PS4 / PS5 / Xbox controllers are the user's own PNG artwork, embedded as
// data URIs (controllerIcons.ts) and drawn as a CSS **mask** rather than an
// <img>: the PNGs are solid black, so an <img> would render black-on-black. As a
// mask, `backgroundColor: currentColor` fills the glyph, so each pad still picks
// up its accent color (PS blue / Xbox green) from the parent span exactly like
// the old inline SVGs did.
function maskIcon(uri: string) {
  return function ControllerImg({ className }: { className?: string }) {
    return (
      <span
        className={className}
        aria-hidden
        style={{
          display: "inline-block", width: 58, height: 41,
          backgroundColor: "currentColor",
          WebkitMaskImage: `url(${uri})`, maskImage: `url(${uri})`,
          WebkitMaskRepeat: "no-repeat", maskRepeat: "no-repeat",
          WebkitMaskSize: "contain", maskSize: "contain",
          WebkitMaskPosition: "center", maskPosition: "center",
        }}
      />
    );
  };
}
const PlayStationIcon = maskIcon(CONTROLLER_IMG.ps4);   // PS4  - DualShock-style artwork
const DualSense5Icon  = maskIcon(CONTROLLER_IMG.ps5);   // PS5  - DualSense-style artwork
const XboxIcon        = maskIcon(CONTROLLER_IMG.xbox);  // Xbox - Xbox artwork
// Generic pad - face-buttons cluster (✕ ◯ □ △), the user's icon-manager pick.
function GamepadIcon({ className }: { className?: string }) {
  return (
    <svg className={className} width={41} height={41} viewBox="0 0 24 24" fill="none"
         stroke="currentColor" strokeWidth={1.4} aria-hidden>
      <circle cx="12" cy="4.6" r="3.4" /><path d="M10.6 3.2 12 5.9 13.4 3.2" />
      <circle cx="19.4" cy="12" r="3.4" /><circle cx="19.4" cy="12" r="1.2" />
      <circle cx="12" cy="19.4" r="3.4" /><path d="M10.7 18.1 13.3 20.7M13.3 18.1 10.7 20.7" />
      <circle cx="4.6" cy="12" r="3.4" /><rect x="3.2" y="10.6" width="2.8" height="2.8" rx="0.4" />
    </svg>
  );
}
const TYPE_ICON: Record<ControllerType, (p: { className?: string }) => ReactNode> = {
  ps5: DualSense5Icon, ps4: PlayStationIcon, xbox: XboxIcon, generic: GamepadIcon,
};
const TYPE_ACCENT: Record<ControllerType, string> = {
  ps5: "#0070d1", ps4: "#0070d1", xbox: "#107c10", generic: "#00ffe0",
};

export default function ControllerSettings({ reportStatus }: { reportStatus?: (m: string) => void }) {
  const [map, setMap] = useState(getGamepadMap());
  const [capturing, setCapturing] = useState<GpAction | null>(null);
  const [pad, setPad] = useState(() => getConnectedController());

  useEffect(() => {
    const onMap = () => setMap(getGamepadMap());
    const refreshPad = () => setPad(getConnectedController());
    window.addEventListener("gamepadmap", onMap);
    window.addEventListener("gamepadconnected", refreshPad);
    window.addEventListener("gamepaddisconnected", refreshPad);
    // The Gamepad API only surfaces a pad AFTER its first button press while the
    // window is focused (Chromium privacy gate) - so a DualSense in native mode
    // can read as "not connected" until pressed. Poll so the banner updates the
    // moment it becomes available, without relying on the connect event firing.
    const poll = window.setInterval(refreshPad, 700);
    return () => {
      window.removeEventListener("gamepadmap", onMap);
      window.removeEventListener("gamepadconnected", refreshPad);
      window.removeEventListener("gamepaddisconnected", refreshPad);
      window.clearInterval(poll);
    };
  }, []);

  // Cancel capture on Esc or when the tab unmounts.
  useEffect(() => {
    if (!capturing) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") cancel(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [capturing]);
  useEffect(() => () => endGamepadCapture(), []);

  const type: ControllerType = pad?.type ?? "generic";
  const padOn = !!pad;
  const Icon = TYPE_ICON[type];
  const accent = TYPE_ACCENT[type];

  const cancel = () => { endGamepadCapture(); setCapturing(null); };
  const start = (action: GpAction) => {
    if (!padOn) return;
    setCapturing(action);
    beginGamepadCapture((index) => {
      setGamepadBinding(action, index);
      endGamepadCapture();
      setCapturing(null);
      reportStatus?.(`"${GP_ACTIONS.find((a) => a.action === action)?.label}" → ${gpButtonName(index, type)}`);
    });
  };
  const onReset = () => { resetGamepadMap(); reportStatus?.("מיפוי השלט אופס לברירת המחדל"); };

  return (
    <section className="glass rounded-2xl p-6">
      {/* Connected-controller banner */}
      <div className="flex items-center gap-4 mb-5 rounded-xl px-4 py-3 border"
           style={{ borderColor: `${accent}55`, background: `${accent}12` }}>
        <span className="shrink-0" style={{ color: accent }}><Icon /></span>
        <div className="flex-1 text-right">
          <div className="text-white font-bold text-[15px]">
            {padOn ? pad!.label : "לא מחובר שלט"}
          </div>
          <div className="text-slate-400 text-xs mt-0.5">
            {padOn
              ? "מזוהה ומחובר - אפשר למפות כפתורים"
              : "חבר שלט (PS4/PS5/Xbox). לחץ כפתור כלשהו עליו כשהחלון בפוקוס. אם משתמש ב-DSX/DualSenseX - סגור אותו (הוא מסתיר את השלט הפיזי)."}
          </div>
        </div>
        <span className="text-[11px] font-semibold px-2 py-1 rounded-full whitespace-nowrap"
              style={{ color: accent, background: `${accent}1f`, boxShadow: padOn ? `0 0 10px -2px ${accent}` : undefined }}>
          {padOn ? "● מחובר" : "○ מנותק"}
        </span>
      </div>

      <div className="flex items-start justify-between mb-3 gap-4">
        <h2 className="text-base font-bold text-white text-right inline-flex items-center gap-1.5"><IconOptHdrControllerMapping width={20} className="shrink-0 opacity-90" />מיפוי כפתורים</h2>
        <button
          type="button"
          onClick={onReset}
          className="shrink-0 inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-lg border border-white/10
                     text-slate-300 hover:text-white hover:bg-white/5 transition"
        >
          <IconOptBtnControllerReset width={18} className="shrink-0 opacity-90" />איפוס לברירת מחדל
        </button>
      </div>

      <div className="flex flex-col gap-2">
        {GP_ACTIONS.map(({ action, label, desc }) => {
          const editing = capturing === action;
          return (
            <div
              key={action}
              className={[
                "flex items-center gap-4 rounded-xl px-4 py-3 border transition",
                editing ? "border-brand-cyan/60 bg-brand-cyan/[0.06]" : "border-white/5 bg-white/[0.02]",
              ].join(" ")}
            >
              <div className="flex-1 min-w-0 text-right">
                <div className="text-white font-semibold text-[14px]">{label}</div>
                <div className="text-slate-400 text-xs mt-0.5">{desc}</div>
              </div>
              {editing ? (
                <div className="flex items-center gap-2">
                  <span className="text-brand-cyan text-sm font-semibold animate-pulse whitespace-nowrap">
                    לחץ כפתור בשלט…
                  </span>
                  <button type="button" onClick={cancel}
                    className="text-xs px-2.5 py-1.5 rounded-lg border border-white/10 text-slate-300 hover:bg-white/5">
                    ביטול
                  </button>
                </div>
              ) : (
                <div className="flex items-center gap-3">
                  <span dir="ltr"
                    className="text-sm font-mono text-slate-100 bg-black/40 border border-white/10
                               rounded-lg px-3 py-1.5 min-w-[120px] text-center">
                    {gpButtonName(map[action], type)}
                  </span>
                  <button type="button" onClick={() => start(action)} disabled={!padOn}
                    className="inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-lg border border-brand-cyan/30
                               text-brand-cyan hover:bg-brand-cyan/10 transition disabled:opacity-40
                               disabled:cursor-not-allowed">
                    <IconOptBtnControllerRemap width={18} className="shrink-0 opacity-90" />שנה
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className="mt-5 pt-4 border-t border-white/5 text-right">
        <div className="text-slate-400 text-xs font-semibold mb-2">קבוע (לא ניתן לשינוי):</div>
        <ul className="text-slate-400 text-xs space-y-1">
          <li>סטיק שמאלי / כיווניות (D-pad) - ניווט בין הפריטים</li>
          <li>סטיק ימני (למעלה/למטה) - גלילה</li>
        </ul>
      </div>
    </section>
  );
}
