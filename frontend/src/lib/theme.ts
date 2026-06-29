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
//
// IMPORTANT: the parameter is typed `string` (not the strict Availability
// union) AND the function always returns a result — never undefined. The
// website's catalog can introduce new availability values at any time
// (the admin form adds rows on the fly); when that happens the launcher
// must NOT crash. Unknown values fall back to a neutral chip showing the
// raw value, exactly like the website's <AvailabilityRibbon>. This was
// the root cause of the v1.0.5/v1.0.6 black-screen — a "translating"
// row from the new admin pipeline-stage options hit a non-exhaustive
// switch here and returned undefined, then GameCard accessed
// `.tone` on undefined and crashed the entire React tree.
export function availabilityLabel(a: string): { text: string; tone: string } {
  const base = "bg-black/90 ring-1";
  switch (a as Availability) {
    case "available":   return { text: "זמין",            tone: `${base} text-emerald-300 ring-emerald-400/40` };
    case "in-progress": return { text: "בעבודה",          tone: `${base} text-amber-200   ring-amber-400/40` };
    case "extracting":  return { text: "בתהליך שליפה",    tone: `${base} text-amber-200   ring-amber-400/40` };
    case "translating": return { text: "בתהליך תרגום",    tone: `${base} text-amber-200   ring-amber-400/40` };
    case "packing":     return { text: "בתהליך פריסה",    tone: `${base} text-amber-200   ring-amber-400/40` };
    case "finalizing":  return { text: "בתהליך השלמה",    tone: `${base} text-amber-200   ring-amber-400/40` };
    case "qa":          return { text: "בבקרת איכות",      tone: `${base} text-violet-200  ring-violet-400/40` };
    case "coming-soon": return { text: "בקרוב",           tone: `${base} text-sky-200     ring-sky-400/40` };
    case "planned":     return { text: "מתוכנן",          tone: `${base} text-slate-200   ring-slate-300/40` };
    case "paused":      return { text: "מושהה",           tone: `${base} text-slate-300   ring-slate-300/30` };
    case "archived":    return { text: "בארכיון",         tone: `${base} text-slate-400   ring-slate-400/30` };
  }
  // Fallback for any future availability value the website adds before
  // the launcher is rebuilt. Shows the raw token in a neutral chip so
  // the admin can still see "this game has *some* state" rather than
  // a crash or a missing chip.
  return { text: a || "—", tone: `${base} text-slate-300 ring-slate-300/30` };
}

export function modStateLabel(s: string): { text: string; tone: string } {
  const base = "bg-black/90 ring-1";
  switch (s as ModState) {
    case "ACTIVE":        return { text: "תרגום פעיל",       tone: `${base} text-emerald-300 ring-emerald-400/40` };
    case "DISABLED":      return { text: "תרגום מושבת",      tone: `${base} text-amber-200   ring-amber-400/40` };
    case "NOT_INSTALLED": return { text: "מוכן להתקנה",      tone: `${base} text-sky-200     ring-sky-400/40` };
    case "NOT_AVAILABLE": return { text: "תרגום לא זמין",    tone: `${base} text-slate-300   ring-slate-300/30` };
    case "UNKNOWN":       return { text: "—",                tone: `${base} text-slate-400   ring-slate-400/30` };
  }
  return { text: s || "—", tone: `${base} text-slate-400 ring-slate-400/30` };
}
