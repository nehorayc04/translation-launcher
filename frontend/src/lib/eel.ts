// Thin wrapper around the Python ↔ JS RPC transport.
//
// Two transports are supported transparently:
//   • Qt shell  — window.bridge, populated by qwebchannel.js after the
//                 main page emits a 'bridge:ready' CustomEvent.
//   • Eel (legacy) — window.eel, attached asynchronously without firing
//                    'bridge:ready'.
//
// Views call `api.foo()` the same way regardless; this shim awaits
// whichever transport appears first, caches it, and dispatches the
// call in the right shape (bridge: trailing-callback; eel: thunk).
import type { Game, OpResult, ScanResult, Software, LauncherPrefs } from "./types";

declare global {
  interface Window {
    eel?:    any;
    bridge?: any;
  }
}

type Transport =
  | { kind: "bridge"; obj: any }
  | { kind: "eel";    obj: any }
  | null;

let _transportPromise: Promise<Transport> | null = null;

// Two-phase detection — resolves to the first transport that becomes
// available, then memoises the result so subsequent RPC calls are cheap.
function detectTransport(): Promise<Transport> {
  if (_transportPromise) return _transportPromise;
  _transportPromise = new Promise<Transport>((resolve) => {
    if (typeof window === "undefined") return resolve(null);
    if (window.bridge) return resolve({ kind: "bridge", obj: window.bridge });

    let settled = false;
    const finish = (t: Transport) => {
      if (settled) return;
      settled = true;
      window.removeEventListener("bridge:ready", onReady);
      window.clearInterval(iv);
      resolve(t);
    };
    const onReady = () => {
      if (window.bridge)   return finish({ kind: "bridge", obj: window.bridge });
      if (window.eel)      return finish({ kind: "eel",    obj: window.eel    });
      return finish(null);
    };
    window.addEventListener("bridge:ready", onReady);

    // Poll for the legacy Eel attach (no event to subscribe to) AND give
    // the Qt bridge a brief window before giving up. ~600ms total.
    let ticks = 0;
    const iv = window.setInterval(() => {
      ticks++;
      if (window.bridge) return; // onReady will fire on the channel callback
      if (window.eel)    return finish({ kind: "eel", obj: window.eel });
      if (ticks > 20)    return finish(null);
    }, 30);
  });
  return _transportPromise;
}

/** Forward a JS message to launcher.log via the bridge - useful when
 *  DevTools is unreachable in production (main.tsx disables the global
 *  right-click context menu so 'Inspect element' never surfaces).
 *  Fire-and-forget, swallows errors so a logging miss can't break the
 *  caller's hot path. */
export function jsLog(message: string): void {
  try {
    const w = window as { bridge?: { js_log?: (m: string) => void } };
    w.bridge?.js_log?.(message);
  } catch { /* ignored */ }
}

export function isReady(): boolean {
  if (typeof window === "undefined") return false;
  return Boolean(window.bridge || window.eel);
}

async function call<T>(name: string, ...args: unknown[]): Promise<T> {
  const t = await detectTransport();
  if (!t) {
    console.warn(`[bridge] no transport — call ${name} bypassed`);
    throw new Error(`bridge unavailable: ${name}`);
  }
  const fn = t.obj[name];
  if (typeof fn !== "function") {
    throw new Error(`${t.kind} function not exposed: ${name}`);
  }
  return new Promise<T>((resolve, reject) => {
    try {
      if (t.kind === "bridge") {
        // QWebChannel slot: trailing callback receives the return value.
        fn(...args, (result: T) => resolve(result));
      } else {
        // Eel legacy thunk: fn(args) returns a callable taking the cb.
        fn(...args)((result: T) => resolve(result));
      }
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

/** Discriminated result the Personal Area uses to distinguish a
 *  genuinely-empty list from a signed-out / network-error state. */
export interface MyPurchasesResult {
  rows:   MyPurchase[];
  reason: "ok" | "signed-out" | "error";
  detail: string | null;
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

// Subscribe to mod_install_progress events. Bridge path connects to the
// matching Qt Signal directly; Eel path keeps the legacy
// window.__eelModHandlers registry so public/eel-bindings.js works
// unchanged. Returns an unsubscribe fn (idempotent).
export function onModProgress(cb: (p: ModProgress) => void): () => void {
  const handler = (phase: string, pct: number, detail: string) =>
    cb({ phase, pct, detail });
  let unsub: (() => void) | null = null;
  let disposed = false;
  detectTransport().then((t) => {
    if (disposed || !t) return;
    if (t.kind === "bridge") {
      const sig = t.obj.mod_install_progress;
      if (sig?.connect) {
        sig.connect(handler);
        unsub = () => { try { sig.disconnect(handler); } catch { /* ignored */ } };
      }
    } else {
      const w = window as unknown as {
        __eelModHandlers?: ((phase: string, pct: number, detail: string) => void)[];
      };
      if (!w.__eelModHandlers) w.__eelModHandlers = [];
      w.__eelModHandlers.push(handler);
      unsub = () => {
        const i = w.__eelModHandlers?.indexOf(handler) ?? -1;
        if (i >= 0) w.__eelModHandlers!.splice(i, 1);
      };
    }
  });
  return () => {
    disposed = true;
    if (unsub) unsub();
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

// Subscribe to launcher_update_progress events. Same dual-transport
// pattern as onModProgress above.
export function onLauncherUpdateProgress(
  cb: (p: LauncherUpdateProgress) => void,
): () => void {
  const handler = (phase: string, pct: number, detail: string) =>
    cb({ phase, pct, detail });
  let unsub: (() => void) | null = null;
  let disposed = false;
  detectTransport().then((t) => {
    if (disposed || !t) return;
    if (t.kind === "bridge") {
      const sig = t.obj.launcher_update_progress;
      if (sig?.connect) {
        sig.connect(handler);
        unsub = () => { try { sig.disconnect(handler); } catch { /* ignored */ } };
      }
    } else {
      const w = window as unknown as {
        __eelLauncherUpdateHandlers?: ((phase: string, pct: number, detail: string) => void)[];
      };
      if (!w.__eelLauncherUpdateHandlers) w.__eelLauncherUpdateHandlers = [];
      w.__eelLauncherUpdateHandlers.push(handler);
      unsub = () => {
        const i = w.__eelLauncherUpdateHandlers?.indexOf(handler) ?? -1;
        if (i >= 0) w.__eelLauncherUpdateHandlers!.splice(i, 1);
      };
    }
  });
  return () => {
    disposed = true;
    if (unsub) unsub();
  };
}

/** Subscribe to the fire-and-forget refresh_catalog completion signal
 *  from the Qt shell. Fires once after all 3 backend HTTP fetches
 *  finish; the args are the per-source labels ('remote' | 'cache' |
 *  'none') the toast renders. On the legacy Eel build this Signal
 *  never fires - callers should be tolerant of that and use the
 *  refreshCatalog Promise return value as the completion signal there. */
export function onCatalogRefreshComplete(
  cb: (catalog: string, news: string, updates: string) => void,
): () => void {
  const handler = (c: string, n: string, u: string) => cb(c, n, u);
  let unsub: (() => void) | null = null;
  let disposed = false;
  detectTransport().then((t) => {
    if (disposed || !t || t.kind !== "bridge") return;
    const sig = t.obj.catalog_refresh_complete;
    if (sig?.connect) {
      sig.connect(handler);
      unsub = () => { try { sig.disconnect(handler); } catch { /* ignored */ } };
    }
  });
  return () => {
    disposed = true;
    if (unsub) unsub();
  };
}

export const api = {
  ready:            (): boolean => isReady(),
  getAllGames:      ()                          => call<Game[]>("get_all_games"),
  getGame:          (id: string)                => call<Game>("get_game", id),
  getNews:          ()                          => call<NewsItem[]>("get_news"),
  /** Fire-and-forget. Returns immediately with {ok, pending: true} on
   *  the Qt shell - actual catalog/news/updates arrive progressively via
   *  cache_refreshed signals, and the per-source toast labels arrive via
   *  onCatalogRefreshComplete (below). On the legacy Eel build the slot
   *  still returns synchronously with the full payload; we accept both
   *  shapes here. */
  refreshCatalog:   ()                          => call<{ok?: boolean; pending?: boolean; games?: Game[]; news?: NewsItem[]; catalog_source?: string; news_source?: string}>("refresh_catalog"),
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
  /** Signal the in-flight self-update to abort. Effective during the
   *  download/verify phases; once the installer has been launched the
   *  call is a no-op (the install is the installer's job to finish). */
  cancelLauncherUpdate:  ()                      => call<{ ok: boolean }>("cancel_launcher_update"),
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
   *  game catalog row inlined (Supabase resource embedding). Returns a
   *  discriminated result so the personal area can tell "0 purchases"
   *  apart from "signed out" / "expired token" / "network error". */
  authGetMyPurchases: ()                        => call<MyPurchasesResult>("auth_get_my_purchases"),
  /** Game-ids the current user has voted for. Returns [] when signed
   *  out. */
  authGetMyVotes:     ()                        => call<string[]>("auth_get_my_votes"),
  authAbortLogin:   ()                          => call<{ok: boolean; aborted?: boolean; error?: string}>("auth_abort_login"),
  /** URL of the currently-in-flight Google OAuth attempt, or null
   *  when no attempt is active. The AuthModal's "copy link" button
   *  uses this so the user can paste into a different browser
   *  profile if `webbrowser.open()` opened the wrong one. */
  authGetAuthorizeUrl: ()                       => call<string | null>("auth_get_authorize_url"),

  /** Current Supabase access token (refreshed on expiry by the Python
   *  side). Returns null when signed out. Used by the in-launcher
   *  PayPal Smart Buttons to authenticate against /api/paypal. */
  authGetAccessToken: () => call<string | null>("auth_get_access_token"),

  // ── Email/password (kept entirely inside the launcher UI) ──
  authSignInPassword: (email: string, password: string) =>
    call<{ok: boolean; user?: LauncherUser; error?: string}>("auth_signin_password", email, password),
  authSignUpPassword: (email: string, password: string, fullName: string) =>
    call<{ok: boolean; user?: LauncherUser & {confirmed?: boolean}; confirmed?: boolean; error?: string}>(
      "auth_signup_password", email, password, fullName,
    ),
};
