// User-facing appearance prefs (Appearance settings tab): animations on/off,
// UI density, and the neutral ambient accent color. Persisted to localStorage
// and applied to <html> so the choice survives navigation + restart. Kept
// framework-free so it can run before React mounts (initThemePrefs in App).

export type Density = "comfortable" | "compact";
// Surface backdrop style (Windows-like options). "glass" = glassmorphism (default).
export type Backdrop = "glass" | "acrylic" | "mica" | "tabbed" | "none";

const K_ANIMS    = "themeAnims";     // "0" | "1"  (default 1 = on)
const K_DENSITY  = "themeDensity";   // "comfortable" | "compact"
const K_ACCENT   = "themeAccent";    // hex; "" / absent → brand cyan default
const K_SOUNDS   = "themeSounds";    // "0" | "1"  (default 0 = off — opt-in)
const K_BACKDROP = "themeBackdrop";  // glass | acrylic | mica | tabbed | none (default glass)
const K_RAINBOW  = "themeRainbow";   // "0" | "1"  (default 0 = single accent)

export const DEFAULT_ACCENT = "#00ffe0";

function ls(key: string): string | null {
  try { return localStorage.getItem(key); } catch { return null; }
}
function lsSet(key: string, v: string) {
  try { localStorage.setItem(key, v); } catch { /* ignore */ }
}

export function getAnims(): boolean { return ls(K_ANIMS) !== "0"; }
export function getDensity(): Density { return ls(K_DENSITY) === "compact" ? "compact" : "comfortable"; }
export function getAccent(): string { return ls(K_ACCENT) || DEFAULT_ACCENT; }
export function getSounds(): boolean { return ls(K_SOUNDS) === "1"; }
export function setSounds(on: boolean) { lsSet(K_SOUNDS, on ? "1" : "0"); }
export function getBackdrop(): Backdrop {
  const v = ls(K_BACKDROP);
  return (v === "acrylic" || v === "mica" || v === "tabbed" || v === "none") ? v : "glass";
}
export function getRainbow(): boolean { return ls(K_RAINBOW) === "1"; }

export function applyAnims(on: boolean) {
  document.documentElement.classList.toggle("reduce-anims", !on);
}
export function applyDensity(d: Density) {
  document.documentElement.setAttribute("data-density", d);
}
export function applyBackdrop(b: Backdrop) {
  document.documentElement.setAttribute("data-backdrop", b);
}
export function applyRainbow(on: boolean) {
  document.documentElement.classList.toggle("ambient-rainbow", on);
}

export function setAnims(on: boolean)   { lsSet(K_ANIMS, on ? "1" : "0"); applyAnims(on); }
export function setDensity(d: Density)   { lsSet(K_DENSITY, d); applyDensity(d); }
export function setAccentPref(hex: string) { lsSet(K_ACCENT, hex); }
export function setBackdrop(b: Backdrop) { lsSet(K_BACKDROP, b); applyBackdrop(b); }
export function setRainbow(on: boolean) { lsSet(K_RAINBOW, on ? "1" : "0"); applyRainbow(on); }

// Sidebar display mode — chosen in Settings, consumed live by the Sidebar.
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
 *  now, per request) — the picker was removed. */
export function initThemePrefs() {
  applyAnims(getAnims());
  applyDensity(getDensity());
  applyBackdrop("glass");
  applyRainbow(getRainbow());
}
