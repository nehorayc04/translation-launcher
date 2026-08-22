// Game payload - mirrors `main_eel._game_payload()`.
// Fields come straight from CatalogGame dataclass + install/mod enrichment.
// All availability values the catalog API can return. Mirrors the
// website's union (src/data/games.ts). NOTE: this MUST stay in sync
// with `availabilityLabel()` in lib/theme.ts - when a new value is
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

/** "Actively in production" - generic 'in-progress' plus the admin-set
 *  pipeline-stage variants. A broad "this game is somewhere in the
 *  pipeline" test; NOT the gate for the progress bar (see below). */
const IN_FLIGHT_AVAILABILITIES = new Set<Availability>([
  "in-progress", "extracting", "translating", "packing", "finalizing", "qa",
]);
export function isInFlight(a: string): boolean {
  return IN_FLIGHT_AVAILABILITIES.has(a as Availability);
}

/** Gates the live translation-progress bar in the game panel.
 *  Deliberately NARROWER than `isInFlight`: only a game the admin has
 *  explicitly marked "בתהליך תרגום" shows a bar, so the bar always means
 *  "a translation is running right now". A generic "בעבודה", a QA pass or
 *  any other stage shows the status chip alone - a half-filled bar next to
 *  a game nobody is actively translating reads as stalled progress. */
export function showsTranslationProgress(a: string): boolean {
  return a === "translating";
}

export interface Game {
  id: string;
  titleEn: string;
  titleHe: string;
  version: string;
  /** The game/software version the CURRENT mod was built/tested against, shown
   *  as "גרסת משחק/תוכנה תואמת" in the detail panel. '' → hidden. */
  gameVersion?: string;
  theme_key: string;
  availability: Availability;
  tagline: string;
  description: string;
  progress: number | null;
  install_path: string | null;
  /** Full path to the game EXE (user-picked or auto-derived), for the Settings
   *  field. Backend still keys installs on install_path (the folder). */
  exe_path?: string | null;
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
  /** Release maturity of the current mod version (alpha|beta|rc|stable) -
   *  drives the stage badge. Mirrors the website. */
  releaseStage?: "alpha" | "beta" | "rc" | "stable";
  /** Latest version "what's new" (HE), shown in the detail panel. */
  changelog?: string;
  /** Optional Steam-style art for the detail-panel hero. When absent the
   *  panel falls back to a blurred cover banner / the title as the logo.
   *  Populated from the catalog (banner_url / logo_url) when available. */
  bannerUrl?: string | null;
  logoUrl?: string | null;
  /** True for a SOFTWARE row (VirtualDJ …). Software lives in the same catalog
   *  and reuses the same card/panel - this only flips the wording ("תוכנה"
   *  instead of "משחק") and routes it to the תוכנות library tab. */
  isSoftware?: boolean;
}

export interface ScanResult {
  games: Game[];
  found: number;
}

/** Software catalog entry - sister of Game. Comes from /api/software
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
   *  Optional - older snapshots omit it; absent ⇒ GPU on (default). */
  disableGpu?:   boolean;
}

/** One selectable app-icon variant (eel.getAppIcon). `thumb` is a path under
 *  the web root (frontend/public/app_icons/<id>.png). */
export interface AppIconOption {
  id:     string;                 // e.g. "5g-circle-round"
  style:  string;                 // "5c" | "5e" | "5g"
  shape:  "circle" | "square";
  corner: "sharp" | "round";
  thumb:  string;
}

/** App-icon picker state: the current variant + the full option list. */
export interface AppIconState {
  variant: string;
  default: string;
  options: AppIconOption[];
}

/** Static host profile (sensed once by perf_manager) - the UI uses `tier` to
 *  auto-degrade its animation load on a weak machine. */
export interface MachineProfile {
  tier: "low" | "balanced" | "high";
  cores: number;
  ramTotalMb: number;
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
