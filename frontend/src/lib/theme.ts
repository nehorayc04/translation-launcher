// Per-game cover gradient + accent. Mirrors the website's theme tokens.
export const CARD_GRADIENTS: Record<string, [string, string]> = {
  cyberpunk:  ["#070710", "#1a0d40"],
  tsushima:   ["#0a0303", "#3a0a0a"],
  alanwake:   ["#050807", "#0a1a14"],
  rdr:        ["#1a1108", "#3a2008"],
  hogwarts:   ["#070818", "#0a164a"],
  default:    ["#0a0a14", "#101830"],
  gta:        ["#0a0a14", "#101830"],
  elden:      ["#1a1108", "#3a2008"],
  witcher:    ["#0a0303", "#3a0a0a"],
  bg3:        ["#070818", "#0a164a"],
};

export const CARD_ACCENTS: Record<string, string> = {
  cyberpunk:  "#fff700",
  tsushima:   "#c10916",
  alanwake:   "#a8c4a2",
  rdr:        "#c7791e",
  hogwarts:   "#d4af37",
  default:    "#88ccff",
  gta:        "#88ccff",
  elden:      "#c7791e",
  witcher:    "#c10916",
  bg3:        "#d4af37",
};

export function gradientFor(theme_key: string): [string, string] {
  return CARD_GRADIENTS[theme_key] ?? CARD_GRADIENTS.default;
}

export function accentFor(theme_key: string): string {
  return CARD_ACCENTS[theme_key] ?? CARD_ACCENTS.default;
}

// Pretty Hebrew label for availability state
import type { Availability, ModState } from "./types";

// Chip tone: solid near-black background + colored border/text. This keeps the
// chip readable regardless of what cover color sits underneath it (otherwise
// e.g. amber "בעבודה" disappears on Cyberpunk's yellow cover).
export function availabilityLabel(a: Availability): { text: string; tone: string } {
  const base = "bg-black/75 backdrop-blur-md ring-1";
  switch (a) {
    case "available":   return { text: "זמין",    tone: `${base} text-emerald-300 ring-emerald-400/40` };
    case "in-progress": return { text: "בעבודה",  tone: `${base} text-amber-200   ring-amber-400/40` };
    case "coming-soon": return { text: "בקרוב",   tone: `${base} text-sky-200     ring-sky-400/40` };
    case "planned":     return { text: "מתוכנן",  tone: `${base} text-slate-200   ring-slate-300/40` };
  }
}

export function modStateLabel(s: ModState): { text: string; tone: string } {
  const base = "bg-black/75 backdrop-blur-md ring-1";
  switch (s) {
    case "ACTIVE":        return { text: "תרגום פעיל",       tone: `${base} text-emerald-300 ring-emerald-400/40` };
    case "DISABLED":      return { text: "תרגום מושבת",      tone: `${base} text-amber-200   ring-amber-400/40` };
    case "NOT_INSTALLED": return { text: "מוכן להתקנה",      tone: `${base} text-sky-200     ring-sky-400/40` };
    case "NOT_AVAILABLE": return { text: "תרגום לא זמין",    tone: `${base} text-slate-300   ring-slate-300/30` };
    case "UNKNOWN":       return { text: "—",                tone: `${base} text-slate-400   ring-slate-400/30` };
  }
}
