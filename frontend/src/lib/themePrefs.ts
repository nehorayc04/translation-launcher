// User-facing appearance prefs (Appearance settings tab): animations on/off,
// UI density, and the neutral ambient accent color. Persisted to localStorage
// and applied to <html> so the choice survives navigation + restart. Kept
// framework-free so it can run before React mounts (initThemePrefs in App).

import { detectGpu } from "./gpuInfo";

// Surface backdrop style (Windows-like options). "glass" = glassmorphism (default).
export type Backdrop = "glass" | "acrylic" | "mica" | "tabbed" | "none";

const K_ANIMS     = "themeAnims";      // LEGACY "0" | "1" - migrated to K_ANIM_LEVEL
const K_ANIM_LEVEL = "themeAnimLevel"; // "high" | "normal" | "low" | "off"
const K_TEXTSCALE = "themeTextScale";  // root font-size px (default 16); scales all rem-based text
// 16px = 100%; clean 5% grid (0.8px = 5%/step, 100% default). The range is capped
// at 75%-125% (12-20px) on purpose: 50%/150% were too extreme and BROKE animations
// + buttons (fixed-slot chrome vs scaling text) - the user asked that nothing escape
// on shrink/enlarge, so min/max stay gentle. 11 marks: 75,80,…,100,…,125.
const TEXT_MIN = 12, TEXT_MAX = 20, TEXT_DEFAULT = 16;
const K_ACCENT   = "themeAccent";    // hex; "" / absent → brand cyan default
const K_ACCENT2  = "themeAccent2";   // hex; "" → same as primary (solid single-tone)
const K_SOUNDS   = "themeSounds";    // "0" | "1"  (default 0 = off - opt-in)
const K_BACKDROP = "themeBackdrop";  // glass | acrylic | mica | tabbed | none (default glass)
const K_RAINBOW  = "themeRainbow";   // "0" | "1"  (default 0 = single accent)

export const DEFAULT_ACCENT = "#00ffe0";

function ls(key: string): string | null {
  try { return localStorage.getItem(key); } catch { return null; }
}
function lsSet(key: string, v: string) {
  try { localStorage.setItem(key, v); } catch { /* ignore */ }
}

// ── Animation level (4 steps, replaces the old on/off toggle) ───────────
// high   - every effect, incl. the glass button treatment
// normal - the standard look (what "on" used to be)
// low    - motion trimmed to the essentials; ambient/looping effects stopped
// off    - no motion at all
export type AnimLevel = "high" | "normal" | "low" | "off";
export const ANIM_LEVELS: AnimLevel[] = ["high", "normal", "low", "off"];

/** Has the user made an EXPLICIT choice about animations? (incl. the legacy
 *  on/off pref, which is migrated rather than discarded) */
export function animsIsExplicit(): boolean {
  const lv = ls(K_ANIM_LEVEL);
  if (lv && (ANIM_LEVELS as string[]).includes(lv)) return true;
  const v = ls(K_ANIMS);
  return v === "0" || v === "1";
}

/** The effective level. Explicit choice wins; otherwise AUTO (a weak /
 *  software-rendered host, or an OS reduced-motion request → "low"). */
export function getAnimLevel(): AnimLevel {
  const lv = ls(K_ANIM_LEVEL);
  if (lv && (ANIM_LEVELS as string[]).includes(lv)) return lv as AnimLevel;
  // Migrate the legacy boolean toggle.
  const legacy = ls(K_ANIMS);
  if (legacy === "0") return "off";
  if (legacy === "1") return "normal";
  return shouldAutoReduce() ? "low" : "normal";
}

export function setAnimLevel(level: AnimLevel) {
  lsSet(K_ANIM_LEVEL, level);
  applyAnimLevel(level);
}

/** Drive the CSS from the level.
 *  `reduce-anims` (the existing kill-switch) is used ONLY for "off"; "low"
 *  gets its own class that stops the ambient/looping effects but keeps the
 *  short functional transitions, so the UI still feels responsive rather than
 *  dead. `data-anim` lets any component opt into the richer treatment. */
export function applyAnimLevel(level: AnimLevel) {
  const el = document.documentElement;
  el.setAttribute("data-anim", level);
  el.classList.toggle("reduce-anims", level === "off");
  el.classList.toggle("anims-low", level === "low");
}

/** Is this host too weak to afford the expensive VISUAL effects?
 *
 *  PERFORMANCE signals ONLY:
 *   1. Chromium is software-rendering (SwiftShader) → every blur/animation is
 *      rasterized on the CPU. We detected this already and only logged it.
 *   2. perf_manager says the host is "low" tier (≤2 cores / <6 GB).
 *  Deliberately NOT prefers-reduced-motion: that is a request about MOTION, not
 *  a statement about the machine - honouring it by stripping the glass took the
 *  frosted surfaces away from people who simply dislike animation. */
function _weakHost(): boolean {
  try {
    const g = (window as unknown as { __gpuAccelerated?: boolean }).__gpuAccelerated;
    if (g === false) return true;
  } catch { /* ignore */ }
  return _machineTier === "low";
}

/** True when animations should be reduced: a weak host, OR the user asked
 *  Windows for reduced motion (an accessibility setting we ignored outright).
 *  Cached - neither signal changes within a session. */
let _autoReduce: boolean | null = null;
export function shouldAutoReduce(): boolean {
  if (_autoReduce !== null) return _autoReduce;
  let reduce = _weakHost();
  if (!reduce) {
    try {
      reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    } catch { /* no matchMedia */ }
  }
  _autoReduce = reduce;
  return reduce;
}

// Set once at boot from the bridge (api.getMachineProfile). Unknown → balanced,
// i.e. exactly the behaviour before this existed.
let _machineTier: "low" | "balanced" | "high" = "balanced";
export function setMachineTier(t: "low" | "balanced" | "high") {
  _machineTier = t;
  _autoReduce = null;                       // re-derive with the new signal
}
export function getMachineTier() { return _machineTier; }

/** Legacy boolean view of the level - kept so existing callers still work. */
export function getAnims(): boolean {
  return getAnimLevel() !== "off";
}
export function getTextScale(): number {
  const n = parseFloat(ls(K_TEXTSCALE) || "");
  return Number.isFinite(n) ? Math.min(TEXT_MAX, Math.max(TEXT_MIN, n)) : TEXT_DEFAULT;
}
export function getAccent(): string { return ls(K_ACCENT) || DEFAULT_ACCENT; }
// Secondary ambient colour (for a two-tone wash). Empty → same as the primary
// (a solid single-colour ambient).
export function getAccent2(): string { return ls(K_ACCENT2) || getAccent(); }
export function setAccent2Pref(hex: string) { lsSet(K_ACCENT2, hex); }
export function getSounds(): boolean { return ls(K_SOUNDS) === "1"; }
export function setSounds(on: boolean) { lsSet(K_SOUNDS, on ? "1" : "0"); }
export function getBackdrop(): Backdrop {
  const v = ls(K_BACKDROP);
  return (v === "acrylic" || v === "mica" || v === "tabbed" || v === "none") ? v : "glass";
}
export function getRainbow(): boolean { return ls(K_RAINBOW) === "1"; }

export function applyAnims(on: boolean) {
  applyAnimLevel(on ? "normal" : "off");
}

/** The surface style this machine can actually afford.
 *
 *  `data-backdrop="glass"` layers `backdrop-filter: blur(18px)` on every glass
 *  surface. That is fine with GPU compositing ON (our default) - but when
 *  Chromium is software-rendering, or the host is a low-tier box, every one of
 *  those blurs is re-rasterized ON THE CPU each paint, which is precisely the
 *  "never smooth" report. `"none"` is the SOLID base look: identical layout,
 *  same dark surfaces, zero per-paint blur. `reduce-anims` never covered this -
 *  it only gates transitions/animations, not backdrop-filter.
 *
 *  Keyed on _weakHost() ONLY. The frosted glass IS the product's look; it must
 *  never be dropped because of an unknown GPU probe or a reduced-MOTION
 *  preference. Only a machine that genuinely cannot render it loses it. */
export function autoBackdrop(): Backdrop {
  return _weakHost() ? "none" : "glass";
}
export function applyTextScale(px: number) {
  document.documentElement.style.fontSize = px + "px";
}
export function applyBackdrop(b: Backdrop) {
  document.documentElement.setAttribute("data-backdrop", b);
}
export function applyRainbow(on: boolean) {
  document.documentElement.classList.toggle("ambient-rainbow", on);
}

export function setAnims(on: boolean)   { lsSet(K_ANIMS, on ? "1" : "0"); applyAnims(on); }
export function setTextScale(px: number)  { lsSet(K_TEXTSCALE, String(px)); applyTextScale(px); }
export function setAccentPref(hex: string) { lsSet(K_ACCENT, hex); }
export function setBackdrop(b: Backdrop) { lsSet(K_BACKDROP, b); applyBackdrop(b); }
export function setRainbow(on: boolean) { lsSet(K_RAINBOW, on ? "1" : "0"); applyRainbow(on); }

// Sidebar display mode - chosen in Settings, consumed live by the Sidebar.
export type SidebarMode = "auto" | "wide" | "narrow";
const K_SIDEBAR = "sidebarMode";
export function getSidebarMode(): SidebarMode {
  const v = ls(K_SIDEBAR); return v === "wide" || v === "narrow" ? v : "auto";
}
export function setSidebarMode(m: SidebarMode) {
  lsSet(K_SIDEBAR, m);
  try { window.dispatchEvent(new CustomEvent("sidebarmode", { detail: m })); } catch { /* ignore */ }
}

/** Apply persisted appearance prefs to <html> before React mounts.
 *  Surface style is FORCED to the glassmorphism we built (no user option for
 *  now, per request) - the picker was removed. */
export function initThemePrefs() {
  // Probe the GPU FIRST: shouldAutoReduce() needs to know whether Chromium is
  // software-rendering before we decide the animation load for this session.
  try { detectGpu(); } catch { /* ignore */ }
  applyAnimLevel(getAnimLevel());
  applyTextScale(getTextScale());
  applyBackdrop(autoBackdrop());
  applyRainbow(getRainbow());
  // Seed the ambient colour vars before React mounts so the first paint uses
  // the user's chosen accent (+ secondary for a two-tone wash).
  document.documentElement.style.setProperty("--accent", getAccent());
  document.documentElement.style.setProperty("--accent2", getAccent2());
}
