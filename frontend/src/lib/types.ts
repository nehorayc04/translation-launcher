// Game payload — mirrors `main_eel._game_payload()`.
// Fields come straight from CatalogGame dataclass + install/mod enrichment.
// All availability values the catalog API can return. Mirrors the
// website's union (src/data/games.ts). NOTE: this MUST stay in sync
// with `availabilityLabel()` in lib/theme.ts — when a new value is
// added on the website, add a matching case here AND in the switch.
// The switch also has a `default` fallback, so a missing case shows
// the value as-is instead of crashing the launcher.
export type Availability =
  | "available"
  | "in-progress"
  | "extracting"
  | "translating"
  | "packing"
  | "finalizing"
  | "qa"
  | "coming-soon"
  | "planned"
  | "paused"
  | "archived";
export type ModState     = "ACTIVE" | "DISABLED" | "NOT_INSTALLED" | "NOT_AVAILABLE" | "UNKNOWN";

/** "Actively in production" — generic 'in-progress' plus the admin-set
 *  pipeline-stage variants. Gates the live-progress UI in HomeView /
 *  GameDetailPanel; without this set those checks hardcoded
 *  `availability === "in-progress"` and the dashboard hid whenever
 *  the admin had picked a stage-specific label like "translating". */
const IN_FLIGHT_AVAILABILITIES = new Set<Availability>([
  "in-progress", "extracting", "translating", "packing", "finalizing", "qa",
]);
export function isInFlight(a: string): boolean {
  return IN_FLIGHT_AVAILABILITIES.has(a as Availability);
}

export interface Game {
  id: string;
  titleEn: string;
  titleHe: string;
  version: string;
  theme_key: string;
  availability: Availability;
  tagline: string;
  description: string;
  progress: number | null;
  install_path: string | null;
  is_installed: boolean;
  has_mod_support: boolean;
  mod_state: ModState;
  /** Pinned to the home "תרגומים מובילים" row by the admin panel. */
  featured?: boolean;
  /** Catalog-level sort order, lower = earlier. Used to order featured games. */
  sortOrder?: number;
  /** Admin-managed cover URL from the catalog (cover_url in DB).
   *  Preferred over the bundled /covers/<id>.jpg fallback so that
   *  newly-added games (whose art was never shipped with the launcher)
   *  still render their cover instead of a broken-image icon. */
  cover?: string | null;
  /** Live in-game TEXT language (interface + subtitles) the launcher read
   *  from the game during the scan: "hebrew" | "english" | "other" |
   *  "unknown", or null for titles whose language can't be read. */
  currentLanguage?: "hebrew" | "english" | "other" | "unknown" | null;
  /** Release maturity of the current mod version (alpha|beta|rc|stable) —
   *  drives the stage badge. Mirrors the website. */
  releaseStage?: "alpha" | "beta" | "rc" | "stable";
  /** Latest version "what's new" (HE), shown in the detail panel. */
  changelog?: string;
  /** Optional Steam-style art for the detail-panel hero. When absent the
   *  panel falls back to a blurred cover banner / the title as the logo.
   *  Populated from the catalog (banner_url / logo_url) when available. */
  bannerUrl?: string | null;
  logoUrl?: string | null;
}

export interface ScanResult {
  games: Game[];
  found: number;
}

/** Software catalog entry — sister of Game. Comes from /api/software
 *  filtered to entries flagged show_on_launcher. */
export interface Software {
  id:             string;
  titleEn:        string;
  titleHe:        string;
  version:        string;
  cover:          string | null;
  availability:   string;
  downloadUrl:    string | null;
  publisherUrl:   string | null;
  tagline:        string;
  description:    string;
  badge:          string;
  accentColor:    string;
  featured?:      boolean;
  showOnWebsite?: boolean;
  showOnLauncher?: boolean;
  /** Local-presence flags from software_detector. Present when the
   *  catalog feed has been enriched server-side; absent on plain
   *  catalog pulls (treat as "unknown" / not installed). */
  installed?:     boolean;
  installPath?:   string;
  installExe?:    string;
}

/** Launcher window/lifecycle prefs snapshot (eel.getLauncherPrefs). */
export interface LauncherPrefs {
  /** null = unset → first-launch modal needs to ask the user. */
  closeBehavior: "minimize" | "close" | null;
  startWithOs:   boolean;
  /** true = the user opted OUT of GPU acceleration (flicker workaround).
   *  Optional — older snapshots omit it; absent ⇒ GPU on (default). */
  disableGpu?:   boolean;
}

export interface OpResult {
  ok: boolean;
  error?: string;
  state?: ModState;
  count?: number;
  exe?: string;
  /** Cyberpunk-only side effect: result of flipping/restoring the
   *  game's Text + Subtitles locale to "ar-ar" (the Arabic-slot used
   *  by the Hebrew translation). Present only for enable/disable/
   *  uninstall of the cyberpunk catalog entry, null otherwise. */
  language?: LanguageOpResult | null;
}

export interface LanguageOpResult {
  ok: boolean;
  error?: string;
  /** Vars that were rewritten on this call (e.g. ["Text", "Subtitles"]). */
  changed?: string[];
  /** Vars that were restored from the backup (e.g. ["Text", "Subtitles"]). */
  restored?: string[];
  /** Backed-up originals at the moment of enable (e.g. {Text: "en-us", ...}). */
  previous?: Record<string, string>;
}
