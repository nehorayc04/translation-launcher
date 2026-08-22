// User-remappable controller buttons. The set of discrete ACTIONS is fixed;
// the user chooses WHICH physical button fires each one (like a game's control
// settings). Directional nav (D-pad / left stick) and scrolling (right stick)
// are axis-based and stay fixed - only the face/system BUTTONS are remappable.
//
// Persisted to localStorage; a `gamepadmap` window event lets spatialNav re-read
// the binding live. A simple "capture" channel lets the Settings UI grab the
// next pressed button (spatialNav feeds it) for the in-game-style edit mode.

export type GpAction =
  | "activate" | "back" | "home" | "settings" | "sidebar"
  | "library" | "downloads" | "personal" | "refresh";

export const GP_ACTIONS: { action: GpAction; label: string; desc: string }[] = [
  { action: "activate",  label: "בחירה",       desc: "הפעלת הפריט המודגש" },
  { action: "back",      label: "חזרה",         desc: "חזרה אחורה / סגירת מסך" },
  { action: "home",      label: "דף הבית",      desc: "מעבר לדף הבית" },
  { action: "library",   label: "ספרייה",       desc: "מעבר למסך הספרייה" },
  { action: "downloads", label: "הורדות",       desc: "מעבר למסך ההורדות והעדכונים" },
  { action: "personal",  label: "אזור אישי",     desc: "מעבר לאזור האישי" },
  { action: "settings",  label: "הגדרות",       desc: "פתיחה/סגירה של ההגדרות" },
  { action: "sidebar",   label: "סרגל צד",       desc: "מעבר אל/מהסרגל הצדדי וחזרה" },
  { action: "refresh",   label: "רענון",         desc: "רענון הקטלוג מהשרת" },
];

// Core five bound by default; the extra navigation/refresh actions start
// UNBOUND (-1) so the user can assign spare buttons in the remap menu.
export const DEFAULT_GP_MAP: Record<GpAction, number> = {
  activate: 0, back: 1, home: 8, settings: 9, sidebar: 16,
  library: -1, downloads: -1, personal: -1, refresh: -1,
};

const KEY = "gamepadMap";

export function getGamepadMap(): Record<GpAction, number> {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) return { ...DEFAULT_GP_MAP, ...JSON.parse(raw) };
  } catch { /* ignore */ }
  return { ...DEFAULT_GP_MAP };
}

function persist(map: Record<GpAction, number>) {
  try { localStorage.setItem(KEY, JSON.stringify(map)); } catch { /* ignore */ }
  window.dispatchEvent(new CustomEvent("gamepadmap", { detail: map }));
}

/** Bind `action` to physical button `index`. No two actions share a button -
 *  any other action that held it is cleared (-1 = unbound). */
export function setGamepadBinding(action: GpAction, index: number) {
  const map = getGamepadMap();
  (Object.keys(map) as GpAction[]).forEach((a) => { if (map[a] === index) map[a] = -1; });
  map[action] = index;
  persist(map);
}

export function resetGamepadMap() { persist({ ...DEFAULT_GP_MAP }); }

// ── Capture channel (Settings edit-mode) ────────────────────────────────
// Settings registers a callback; spatialNav's poll calls it with the next
// pressed button index and swallows that input so nothing else reacts.
let captureCb: ((index: number) => void) | null = null;
export function beginGamepadCapture(cb: (index: number) => void) { captureCb = cb; }
export function endGamepadCapture() { captureCb = null; }
export function getGamepadCapture() { return captureCb; }

// ── Controller-type detection (from Gamepad.id) ─────────────────────────
export type ControllerType = "ps5" | "ps4" | "xbox" | "generic";

export function detectControllerType(id: string): ControllerType {
  const s = (id || "").toLowerCase();
  // Sony vendor 054c
  if (s.includes("054c") || s.includes("sony") || s.includes("dualsense") ||
      s.includes("dualshock") || s.includes("playstation") || s.includes("wireless controller")) {
    if (s.includes("dualsense") || s.includes("0ce6") || s.includes("0df2")) return "ps5";
    return "ps4";
  }
  // Microsoft vendor 045e / XInput
  if (s.includes("045e") || s.includes("xbox") || s.includes("xinput") || s.includes("microsoft")) {
    return "xbox";
  }
  return "generic";
}

const TYPE_LABEL: Record<ControllerType, string> = {
  ps5: "PlayStation 5 - DualSense",
  ps4: "PlayStation 4 - DualShock",
  xbox: "Xbox",
  generic: "שלט גנרי",
};
export function controllerTypeLabel(t: ControllerType): string { return TYPE_LABEL[t]; }

/** The first connected pad's {type, label, id}, or null if none. */
export function getConnectedController(): { type: ControllerType; label: string; id: string } | null {
  if (typeof navigator === "undefined" || !navigator.getGamepads) return null;
  const gp = Array.from(navigator.getGamepads()).find(Boolean);
  if (!gp) return null;
  const type = detectControllerType(gp.id);
  return { type, label: TYPE_LABEL[type], id: gp.id };
}

// Per-type button glyphs (standard mapping indices).
const PS_NAMES: Record<number, string> = {
  0: "✕", 1: "◯", 2: "□", 3: "△", 4: "L1", 5: "R1", 6: "L2", 7: "R2",
  8: "Share / Create", 9: "Options", 10: "L3", 11: "R3",
  12: "D-pad ↑", 13: "D-pad ↓", 14: "D-pad ←", 15: "D-pad →", 16: "כפתור PS", 17: "טאצ'פד",
};
const XBOX_NAMES: Record<number, string> = {
  0: "A", 1: "B", 2: "X", 3: "Y", 4: "LB", 5: "RB", 6: "LT", 7: "RT",
  8: "View ⧉", 9: "Menu ≡", 10: "LS", 11: "RS",
  12: "D-pad ↑", 13: "D-pad ↓", 14: "D-pad ←", 15: "D-pad →", 16: "כפתור Xbox",
};
const GENERIC_NAMES: Record<number, string> = {
  0: "A / ✕", 1: "B / ◯", 2: "X / □", 3: "Y / △", 4: "LB / L1", 5: "RB / R1",
  6: "LT / L2", 7: "RT / R2", 8: "Share / View", 9: "Options / Menu", 10: "L3", 11: "R3",
  12: "D-pad ↑", 13: "D-pad ↓", 14: "D-pad ←", 15: "D-pad →", 16: "לוגו מרכזי",
};
export function gpButtonName(index: number, type: ControllerType = "generic"): string {
  if (index == null || index < 0) return "- לא מוגדר";
  const table = type === "xbox" ? XBOX_NAMES : type === "generic" ? GENERIC_NAMES : PS_NAMES;
  return table[index] ?? `כפתור ${index}`;
}
