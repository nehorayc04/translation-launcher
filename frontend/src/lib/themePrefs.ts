// User-facing appearance prefs (Appearance settings tab): animations on/off,
// UI density, and the neutral ambient accent color. Persisted to localStorage
// and applied to <html> so the choice survives navigation + restart. Kept
// framework-free so it can run before React mounts (initThemePrefs in App).

export type Density = "comfortable" | "compact";

const K_ANIMS   = "themeAnims";     // "0" | "1"  (default 1 = on)
const K_DENSITY = "themeDensity";   // "comfortable" | "compact"
const K_ACCENT  = "themeAccent";    // hex; "" / absent → brand cyan default
const K_SOUNDS  = "themeSounds";    // "0" | "1"  (default 0 = off — opt-in)

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

export function applyAnims(on: boolean) {
  document.documentElement.classList.toggle("reduce-anims", !on);
}
export function applyDensity(d: Density) {
  document.documentElement.setAttribute("data-density", d);
}

export function setAnims(on: boolean)   { lsSet(K_ANIMS, on ? "1" : "0"); applyAnims(on); }
export function setDensity(d: Density)   { lsSet(K_DENSITY, d); applyDensity(d); }
export function setAccentPref(hex: string) { lsSet(K_ACCENT, hex); }

/** Apply persisted appearance prefs to <html> before React mounts. */
export function initThemePrefs() {
  applyAnims(getAnims());
  applyDensity(getDensity());
}
