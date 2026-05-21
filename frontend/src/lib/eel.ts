// Thin wrapper around window.eel that adds typings + promise interop.
// All Python @eel.expose functions are wrapped here.
import type { Game, OpResult, ScanResult, Software, LauncherPrefs } from "./types";

// Eel attaches functions to window.eel.<name>. Calling them returns a thunk
// that, when called with (), starts an async RPC; resolving requires
// awaiting eel's promise-style return.
declare global {
  interface Window {
    eel: any;
  }
}

// Mock for when running the React dev server WITHOUT the python backend
// (e.g. when iterating on UI alone). Returns sensible empty fallbacks so
// the app still renders.
function isEelReady(): boolean {
  return typeof window !== "undefined" && !!window.eel;
}

async function call<T>(name: string, ...args: unknown[]): Promise<T> {
  if (!isEelReady()) {
    console.warn(`[eel] not ready — call ${name} bypassed`);
    throw new Error(`eel unavailable: ${name}`);
  }
  const fn = window.eel[name];
  if (typeof fn !== "function") {
    throw new Error(`eel function not exposed: ${name}`);
  }
  return new Promise<T>((resolve, reject) => {
    try {
      fn(...args)((result: T) => resolve(result));
    } catch (e) {
      reject(e);
    }
  });
}

export type UpdateKind = "system" | "translation";
export type DownloadState = "running" | "done" | "cancelled" | "error";

export interface UpdateItem {
  id:        string;
  kind:      UpdateKind;
  title:     string;
  version:   string;
  size_mb:   number;
  notes:     string;
  url:       string | null;
  simulated: boolean;
}

export interface ProgressSnapshot {
  gameId:        string;
  phase:         string;
  phaseLabelHe:  string | null;
  processed:     number;
  total:         number;
  ratePerHour:   number;
  unit:          string;
  gpuModel:      string;
  aiModel:       string;
  meta:          unknown;
  updatedAt:     number | null;
  showDashboard?: boolean;
}

export interface NewsItem {
  id:     string;
  date:   string;        // ISO yyyy-mm-dd
  kind:   "system" | "mod" | string;
  badge:  string | null; // "חדש" / "מוד חדש" / null
  title:  string;
  detail: string;
  link:   string | null; // game id to deep-link to, or null
}

export interface LauncherUser {
  id:         string;
  email:      string;
  fullName:   string;
  avatarUrl:  string;
  provider:   string;
}

/** Shape returned by /auth/get_my_purchases. The nested `games` row
 *  follows the snake_case DB schema (NOT the camelCase /api/games
 *  output) because PostgREST embeds the raw columns. */
export interface MyPurchase {
  id:         string | number;
  game_id:    string;
  status:     string;
  created_at: string;
  games: {
    id:            string;
    title_en:      string;
    title_he:      string;
    cover_url:     string | null;
    version:       string;
    version_label: string;
    download_url:  string | null;
    price_cents:   number | null;
  } | null;
}

/** Local state of the Steam Hebrew mod — returned by get_steam_mod_state. */
export interface SteamModState {
  cached:  boolean;            // archive cached locally → no re-download needed
  enabled: boolean;            // currently applied to the live Steam install
  version: string | null;
}

/** One progress tick during a mod install / enable / disable.
 *  phase ∈ "download" | "verify" | "extract" | "apply". */
export interface ModProgress {
  phase:  string;
  pct:    number;
  detail: string;
}

// Subscribe to mod_install_progress events. The actual eel.expose lives
// in public/eel-bindings.js (window.__eelModHandlers) — same reason as
// the download-progress registry. Returns an unsubscribe fn.
export function onModProgress(cb: (p: ModProgress) => void): () => void {
  const w = window as unknown as {
    __eelModHandlers?: ((phase: string, pct: number, detail: string) => void)[];
  };
  if (!w.__eelModHandlers) w.__eelModHandlers = [];
  const handler = (phase: string, pct: number, detail: string) =>
    cb({ phase, pct, detail });
  w.__eelModHandlers.push(handler);
  return () => {
    const i = w.__eelModHandlers?.indexOf(handler) ?? -1;
    if (i >= 0) w.__eelModHandlers!.splice(i, 1);
  };
}

/** State of a download-distributed game mod (e.g. Cyberpunk 2077). */
export interface GameModState {
  cached:     boolean;   // mod payload present in the launcher cache
  installed:  boolean;   // mod files present in the game folder
  version:    string | null;
  owned:      boolean;   // true for free mods; auth-DRM result for paid
  priceCents: number;    // 0 = free
  modSlug:    string;    // "" = not a download-distributed mod
  hasPath:    boolean;   // the game's install folder is known
}

/** Result of any game-mod lifecycle action — always carries fresh state. */
export interface GameModResult {
  ok:        boolean;
  error?:    string;
  count?:    number;
  language?: { ok: boolean; previous?: Record<string, string> } | null;
  state:     GameModState;
}

/** Result of get_launcher_update_info — the self-update panel's state. */
export interface LauncherUpdateInfo {
  currentVersion:  string;
  latestVersion:   string;
  updateAvailable: boolean;
  downloadUrl:     string | null;
  sizeBytes:       number;
  sizeMb:          number;
  notes:           string;
  sha256:          string | null;
  error:           string | null;
}

/** One progress tick during the in-app launcher self-update.
 *  phase ∈ "download" | "verify" | "launch" | "error". */
export interface LauncherUpdateProgress {
  phase:  string;
  pct:    number;
  detail: string;
}

// Subscribe to launcher_update_progress events (eel.expose lives in
// public/eel-bindings.js → window.__eelLauncherUpdateHandlers).
export function onLauncherUpdateProgress(
  cb: (p: LauncherUpdateProgress) => void,
): () => void {
  const w = window as unknown as {
    __eelLauncherUpdateHandlers?: ((phase: string, pct: number, detail: string) => void)[];
  };
  if (!w.__eelLauncherUpdateHandlers) w.__eelLauncherUpdateHandlers = [];
  const handler = (phase: string, pct: number, detail: string) =>
    cb({ phase, pct, detail });
  w.__eelLauncherUpdateHandlers.push(handler);
  return () => {
    const i = w.__eelLauncherUpdateHandlers?.indexOf(handler) ?? -1;
    if (i >= 0) w.__eelLauncherUpdateHandlers!.splice(i, 1);
  };
}

export const api = {
  ready:            (): boolean => isEelReady(),
  getAllGames:      ()                          => call<Game[]>("get_all_games"),
  getGame:          (id: string)                => call<Game>("get_game", id),
  getNews:          ()                          => call<NewsItem[]>("get_news"),
  refreshCatalog:   ()                          => call<{games: Game[]; news: NewsItem[]; catalog_source: string; news_source: string}>("refresh_catalog"),
  scanQuick:        ()                          => call<ScanResult>("scan_quick"),
  scanDeep:         ()                          => call<ScanResult>("scan_deep"),
  setCustomPath:    (id: string, p: string)     => call<Game>("set_custom_path", id, p),
  clearCustomPath:  (id: string)                => call<Game>("clear_custom_path", id),
  enableMod:        (id: string)                => call<OpResult>("enable_mod_for", id),
  disableMod:       (id: string)                => call<OpResult>("disable_mod_for", id),
  uninstallMod:     (id: string)                => call<OpResult>("uninstall_mod_for", id),
  launchGame:       (id: string)                => call<OpResult>("launch_game", id),
  openFolder:       (p: string)                 => call<OpResult>("open_folder", p),
  applySteamTranslation: ()                     => call<OpResult & {steam_dir?: string}>("apply_steam_translation"),
  /** Local lifecycle for the Steam Hebrew mod. `getSteamModState`
   *  drives the AppsView Install/Enable/Disable button; the toggle and
   *  cache-clear are plain local file ops on the launcher's mod cache. */
  getSteamModState:   ()                        => call<SteamModState>("get_steam_mod_state"),
  setSteamModEnabled: (enabled: boolean)        => call<OpResult>("set_steam_mod_enabled", enabled),
  clearSteamModCache: ()                        => call<OpResult>("clear_steam_mod_cache"),

  // ── Download-distributed game mods (Cyberpunk 2077) ───────
  /** State of a game's downloadable mod — cached / installed / owned /
   *  price. Drives the GameDetailPanel CTA. modSlug="" → not distributed. */
  getGameModState:           (id: string) => call<GameModState>("get_game_mod_state", id),
  /** Kick off download (if needed) + install on a background thread.
   *  Returns at once; progress + a terminal done/error tick stream over
   *  the mod_install_progress channel (subscribe via onModProgress). */
  downloadAndInstallGameMod: (id: string) =>
                                call<{ ok: boolean; error?: string; started?: boolean }>(
                                  "download_and_install_game_mod", id),
  /** Toggle a cached mod: install/reinstall (true) or disable (false). */
  setGameModInstalled:       (id: string, installed: boolean) =>
                                call<GameModResult>("set_game_mod_installed", id, installed),
  /** Remove the mod from the game folder AND wipe the launcher cache. */
  clearGameModCache:         (id: string) => call<GameModResult>("clear_game_mod_cache", id),
  /** Open the website checkout in the browser for a paid game mod. */
  openPurchasePage:          (id: string) =>
                                call<{ ok: boolean; url?: string; error?: string }>("open_purchase_page", id),
  listUpdates:      ()                          => call<UpdateItem[]>("list_updates"),
  /** Launcher self-update: current-vs-latest check + the in-app
   *  download/verify/silent-install trigger. Progress streams back
   *  via onLauncherUpdateProgress(). */
  getLauncherUpdateInfo: ()                      => call<LauncherUpdateInfo>("get_launcher_update_info"),
  startLauncherUpdate:   ()                      => call<{ ok: boolean; error?: string }>("start_launcher_update"),
  /** Software catalog (Steam, etc.) — sister of getAllGames. Backend
   *  pulls /api/software with showOnLauncher filtering. */
  getAllSoftware:   ()                          => call<Software[]>("get_all_software"),
  /** Re-runs the local fingerprint sweep (registry + path checks)
   *  for every software entry. Also clears any "forgotten" software
   *  paths so they re-detect. Returns the refreshed catalog. */
  scanSoftware:     ()                          => call<{ software: Software[] }>("scan_software"),
  /** "Forget" a software's detected install path — it reports as
   *  not-installed until the next full scanSoftware(). */
  clearSoftwarePath: (id: string)               => call<{ software: Software[] }>("clear_software_path", id),

  // ── Launcher window/lifecycle prefs ───────────────────────
  /** Snapshot of close-behavior + autostart state. Frontend reads it
   *  on boot to know whether to show the first-launch close-behavior
   *  modal (closeBehavior === null). */
  getLauncherPrefs: ()                          => call<LauncherPrefs>("get_launcher_prefs"),
  /** Persist the close-behavior choice. Pass `null` to reset. */
  setCloseBehavior: (b: "minimize" | "close" | null) => call<{ ok: boolean; closeBehavior: LauncherPrefs["closeBehavior"]; startWithOs: boolean }>("set_close_behavior", b),
  /** Toggle the HKCU autostart Run-key entry. */
  setStartWithOs:   (enabled: boolean) => call<{ ok: boolean; error?: string; startWithOs: boolean; closeBehavior: LauncherPrefs["closeBehavior"] }>("set_start_with_os", enabled),
  getLiveProgress:  (id: string)                => call<ProgressSnapshot | null>("get_live_progress", id),
  startDownload:    (id: string)                => call<{ok: boolean; error?: string}>("start_download", id),
  cancelDownload:   (id: string)                => call<{ok: boolean; error?: string}>("cancel_download", id),

  // ── Auth (Supabase OAuth + DRM) ───────────────────────────
  authLogin:        ()                          => call<{ok: boolean; user?: LauncherUser; error?: string}>("auth_login"),
  authMe:           ()                          => call<LauncherUser | null>("auth_me"),
  authLogout:       ()                          => call<{ok: boolean; error?: string}>("auth_logout"),
  authOwnsGame:     (gameId: string)            => call<boolean>("auth_owns_game", gameId),
  /** All 'completed' purchases for the current user with the joined
   *  game catalog row inlined (Supabase resource embedding). Returns
   *  [] when signed out. */
  authGetMyPurchases: ()                        => call<MyPurchase[]>("auth_get_my_purchases"),
  /** Game-ids the current user has voted for. Returns [] when signed
   *  out. */
  authGetMyVotes:     ()                        => call<string[]>("auth_get_my_votes"),
  authAbortLogin:   ()                          => call<{ok: boolean; aborted?: boolean; error?: string}>("auth_abort_login"),
  /** URL of the currently-in-flight Google OAuth attempt, or null
   *  when no attempt is active. The AuthModal's "copy link" button
   *  uses this so the user can paste into a different browser
   *  profile if `webbrowser.open()` opened the wrong one. */
  authGetAuthorizeUrl: ()                       => call<string | null>("auth_get_authorize_url"),

  // ── Email/password (kept entirely inside the launcher UI) ──
  authSignInPassword: (email: string, password: string) =>
    call<{ok: boolean; user?: LauncherUser; error?: string}>("auth_signin_password", email, password),
  authSignUpPassword: (email: string, password: string, fullName: string) =>
    call<{ok: boolean; user?: LauncherUser & {confirmed?: boolean}; confirmed?: boolean; error?: string}>(
      "auth_signup_password", email, password, fullName,
    ),
};
