// Thin wrapper around the Python ↔ JS RPC transport.
//
// Two transports are supported transparently:
//   • Qt shell  - window.bridge, populated by qwebchannel.js after the
//                 main page emits a 'bridge:ready' CustomEvent.
//   • Eel (legacy) - window.eel, attached asynchronously without firing
//                    'bridge:ready'.
//
// Views call `api.foo()` the same way regardless; this shim awaits
// whichever transport appears first, caches it, and dispatches the
// call in the right shape (bridge: trailing-callback; eel: thunk).
import type { Game, OpResult, ScanResult, LauncherPrefs, AppIconState, AppIconOption, MachineProfile } from "./types";

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

// Two-phase detection - resolves to the first transport that becomes
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

// A bridge call whose Python slot raises BEFORE invoking its QWebChannel
// callback would leave the returned Promise unsettled forever (a "loading
// spinner that never stops"). Every slot has a Python-side safety that
// eventually returns a value, so these ceilings only ever fire on a truly
// wedged call - a defensive net, NOT a UX timeout. The few slots that
// legitimately block a long time get a generous per-name ceiling.
const CALL_TIMEOUT_MS: Record<string, number> = {
  auth_login: 340_000,   // OAuth round-trip; Python login timeout 300s + safety 320s
  scan_deep:  960_000,   // full drive walk; Python off-thread cap 900s
  scan_quick: 180_000,   // registry probes; Python off-thread cap 120s
  // Native file/folder pickers are PACED BY A HUMAN browsing their disk - a
  // 2-min ceiling false-fires (and reports a crash) when the user just takes
  // their time. Match the Python pick_folder_blocking 600s cap.
  pick_exe:    660_000,
  pick_folder: 660_000,
};
const DEFAULT_CALL_TIMEOUT_MS = 120_000;

async function call<T>(name: string, ...args: unknown[]): Promise<T> {
  const t = await detectTransport();
  if (!t) {
    console.warn(`[bridge] no transport - call ${name} bypassed`);
    throw new Error(`bridge unavailable: ${name}`);
  }
  const fn = t.obj[name];
  if (typeof fn !== "function") {
    throw new Error(`${t.kind} function not exposed: ${name}`);
  }
  return new Promise<T>((resolve, reject) => {
    let settled = false;
    const timeoutMs = CALL_TIMEOUT_MS[name] ?? DEFAULT_CALL_TIMEOUT_MS;
    const timer = setTimeout(() => {
      if (settled) return;
      settled = true;
      reportCallFailure(name, `timeout after ${timeoutMs}ms`, "rpc_timeout");
      reject(new Error(`bridge call timed out after ${timeoutMs}ms: ${name}`));
    }, timeoutMs);
    const settle = (run: () => void) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      run();
    };
    try {
      const cb = (result: T) => settle(() => resolve(result));
      if (t.kind === "bridge") {
        // QWebChannel slot: trailing callback receives the return value.
        fn(...args, cb);
      } else {
        // Eel legacy thunk: fn(args) returns a callable taking the cb.
        fn(...args)(cb);
      }
    } catch (e) {
      reportCallFailure(name, String((e as Error)?.message ?? e), "rpc_throw");
      settle(() => reject(e));
    }
  });
}

// A silent handled-event report for an RPC that timed out or threw. Kept out
// of `call()`'s body so the reporter can never re-enter it for its OWN RPC
// (report_ui_event / report_crash), which would loop.
function reportCallFailure(name: string, message: string, code: string): void {
  if (name === "report_ui_event" || name === "report_crash") return;
  // safeReportEvent is a hoisted function declaration below; it runs only at
  // call-time (an RPC failed), by which point `api` is fully initialised.
  safeReportEvent("rpc_error", `${name}: ${message}`, "rpc", `${code}:${name}`, "warn");
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
    is_software?:  boolean | null;
  } | null;
}

/** Discriminated result the Personal Area uses to distinguish a
 *  genuinely-empty list from a signed-out / network-error state. */
export interface MyPurchasesResult {
  rows:   MyPurchase[];
  reason: "ok" | "signed-out" | "error";
  detail: string | null;
}

/** Local state of the Steam Hebrew mod - returned by get_steam_mod_state. */
export interface SteamModState {
  cached:  boolean;            // archive cached locally → no re-download needed
  enabled: boolean;            // currently applied to the live Steam install
  version: string | null;
}

/** VirtualDJ mod state - Steam's shape + the paid-mod DRM fields (it's a ₪15
 *  software mod, so the CTA must gate install on ownership like a paid game). */
export interface VirtualDjModState extends SteamModState {
  owned?:      boolean;
  priceCents?: number;
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

// ── Non-blocking native file/folder picker ──────────────────────────────
// The Qt bridge's pick_exe/pick_folder Slots are now NON-BLOCKING (a blocking
// getOpenFileName() froze QWebChannel → every polling RPC timed out and each
// reported a false crash). The Slot returns {started:true} at once and the real
// pick arrives later via the `file_pick_result` Signal, matched by a request id.
// The Eel dev build has no Signal channel, so its Slot returns {ok,path} directly.
export interface FilePickResult { ok: boolean; path: string; error?: string }
type _PickResolver = (r: FilePickResult) => void;
const _pickWaiters = new Map<string, _PickResolver>();
let _pickSignalWired = false;
let _pickSeq = 0;

function _wireFilePickSignal(): Promise<void> {
  if (_pickSignalWired) return Promise.resolve();
  return detectTransport().then((t) => {
    if (_pickSignalWired) return;
    if (t?.kind === "bridge") {
      const sig = t.obj.file_pick_result;
      if (sig?.connect) {
        sig.connect((reqId: string, res: FilePickResult) => {
          const w = _pickWaiters.get(reqId);
          if (w) {
            _pickWaiters.delete(reqId);
            w(res || { ok: false, path: "", error: "no-result" });
          }
        });
        _pickSignalWired = true;
      }
    }
  });
}

// Open a native picker and resolve with the user's choice. Waits for the
// Signal (Qt) up to `waitMs` (browsing is user-paced, so the ceiling is long);
// an orphaned/never-answered pick resolves as a benign cancel instead of leaking.
function pickFile(
  kind: "exe" | "folder",
  title: string,
  start: string,
  waitMs = 660_000,
): Promise<FilePickResult> {
  const reqId = `pk${++_pickSeq}-${Date.now()}`;
  const slot = kind === "exe" ? "pick_exe" : "pick_folder";
  return _wireFilePickSignal().then(
    () =>
      new Promise<FilePickResult>((resolve) => {
        let settled = false;
        const done = (r: FilePickResult) => {
          if (settled) return;
          settled = true;
          _pickWaiters.delete(reqId);
          resolve(r);
        };
        _pickWaiters.set(reqId, done);
        const timer = window.setTimeout(
          () => done({ ok: false, path: "", error: "pick-timeout" }),
          waitMs,
        );
        // The Slot returns fast: {started:true} on Qt (wait for the Signal) or
        // {ok,path} on the Eel build (resolve immediately, no Signal will come).
        call<{ ok?: boolean; started?: boolean; path?: string; error?: string }>(
          slot,
          reqId,
          title,
          start,
        )
          .then((r) => {
            if (r && r.started) return;              // Qt: wait for the Signal
            window.clearTimeout(timer);
            done({ ok: !!(r && r.ok), path: (r && r.path) || "", error: r?.error });
          })
          .catch((e) => {
            window.clearTimeout(timer);
            done({ ok: false, path: "", error: String(e) });
          });
      }),
  );
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

/** In-game TEXT-language switch state for a game (auto/Hebrew/English).
 *  `supported:false` → the launcher can't switch this game's language and
 *  the control is hidden. `mode` is the user's chosen switch position;
 *  `current` is the language live in the game right now. */
export interface GameLanguageState {
  supported:    boolean;
  kind?:        "registry" | "cp2077";
  mode?:        "auto" | "hebrew" | "english";
  current?:     "hebrew" | "english" | "other" | "unknown";
  currentCode?: number | string | null;
  original?:    number | string | null;
  originalName?: "hebrew" | "english" | "other" | null;
  error?:       string;
}

/** Result of a single game's mod update-check (manifest vs installed). */
export interface GameModUpdate {
  ok:               boolean;
  supported?:       boolean;
  installed?:       boolean;
  installedVersion?: string | null;
  latestVersion?:   string | null;
  updateAvailable?: boolean;
  /** "download" = installs via downloadAndInstallGameMod; "native" = SM2/WD2/GTAV
   *  applier (installs via its own install_* RPC). */
  kind?:            "download" | "native";
  /** Where the newer version comes from. "offline" = it is ALREADY on disk,
   *  carried by a pre-built offline package → applied with no internet, and the
   *  button says "עדכון אופליין" so the user knows it needs no connection. */
  updateSource?:    "network" | "offline" | "";
  error?:           string;
}

/** State of Marvel's Spider-Man 2's native (TOC-patch) Hebrew mod. */
export interface SpiderMan2State {
  hasPath:     boolean;   // the game install folder is known
  installed:   boolean;   // our mod is currently applied to the TOC
  available:   boolean;   // the mod payload is reachable (download or bundled)
  installPath: string | null;
  version?:    string | null;   // installed mod version (from GitHub Release)
  owned?:      boolean;         // see GowrState - the purchase gate
  priceCents?: number;
}

/** SM2 update-check result (separate network call). */
export interface SpiderMan2Update {
  updateAvailable:   boolean;
  installedVersion?: string | null;
  latestVersion?:    string | null;
}

/** State of Watch Dogs 2's native (FAT5 fat-redirect) Hebrew mod. The mod is
 *  bundled in the launcher, so `available` is true whenever the payload ships;
 *  activation is in-game (Settings → Written Language = Arabic). */
export interface WatchDogs2State {
  hasPath:     boolean;   // the game install folder is known
  installed:   boolean;   // our files are currently redirected into the archives
  available:   boolean;   // the bundled mod payload is present
  installPath: string | null;
  version?:    string | null;
  owned?:      boolean;   // see GowrState - the purchase gate
  priceCents?: number;
}

/** State of God of War: Ragnarök's native applier. Single-file swap of the
 *  Arabic-slot localization WAD (exec\wad\pc_le\r_lang_ar.wad) for the bundled
 *  Hebrew build; the original is backed up in the launcher cache (reversible).
 *  Activation is in-game (Settings → Text Language = Arabic). */
export interface GowrState {
  hasPath:     boolean;   // the game install folder is known
  installed:   boolean;   // the live WAD is our Hebrew build (backup held)
  available:   boolean;   // the bundled mod payload is present
  installPath: string | null;
  version?:    string | null;
  // The DRM gate. EVERY native applier reports these now (the panel draws the
  // buy button from priceCents>0 && !owned, and the "✓ נרכש" chip from
  // priceCents>0 && owned) - a title that is free today can be priced by an
  // admin tomorrow, and omitting them read as "free + owned". Still optional so
  // an older backend degrades to that same lenient default rather than crashing.
  owned?:      boolean;
  priceCents?: number;
}

/** State of GTA V's native OpenIV-free RPF7 applier. `scenario` decides the UX:
 *  'ready' = mods folder + loader present → one-click install/remove;
 *  'mods_no_loader' = mods folder exists but the OpenIV ASI isn't active;
 *  'clean' = no mods folder → guided one-time OpenIV setup;
 *  'no_game' = the game install folder isn't known. */
export interface GtavState {
  hasPath:         boolean;
  installPath:     string | null;
  available:       boolean;   // the bundled Hebrew payload is present
  hasMods:         boolean;   // an OPEN mods\update\update2.rpf+update.rpf exist
  loaderConnected: boolean;   // dinput8.dll (OpenIV ASI loader) present
  scenario:        "ready" | "mods_no_loader" | "clean" | "no_game";
  installed:       boolean;   // our Hebrew is currently applied (backup marker)
  vanillaAvailable:boolean;   // vanilla English payload bundled (for surgical remove)
  backupAvailable: boolean;   // an install-time full backup exists (for full restore)
  priceCents:      number;    // 0 = free; > 0 → buy gate
  owned:           boolean;   // free, or a completed purchase
  version?:        string | null;
}

/** Mod-update preferences (beta channel only - silent auto-update was
 *  removed; updates are always surfaced as an in-app + Windows notification). */
export interface UpdatePrefs {
  betaChannel:   boolean;                  // global opt-in to alpha/beta/rc updates
  betaOverrides: Record<string, boolean>;  // per-mod opt-in override
}

/** One installed translation mod that has a newer version available. */
export interface ModUpdate {
  gameId:           string;
  titleEn:          string;
  titleHe:          string;
  installedVersion: string | null;
  latestVersion:    string;
  /** "download" → update via downloadAndInstallGameMod; "native" → SM2/WD2/GTAV
   *  applier, update via its own install_* RPC. Older builds omit it (treat as download). */
  kind?:            "download" | "native";
  /** "offline" → the newer payload is already on disk (offline package). */
  updateSource?:    "network" | "offline" | "";
}

/** What a pre-built OFFLINE package on this machine carries. */
export interface OfflineAssets {
  available:  boolean;
  createdAt:  string | null;
  /** game ids whose mod is bundled in the package */
  games:      string[];
  path:       string | null;
  /** file:// base for the bundled cover/banner/logo mirror ("" = none) */
  imagesBase: string;
  /** bucket-relative paths the package carries (e.g. "banners/gtav.webp") */
  imageRels:  string[];
}

/** Result of any game-mod lifecycle action - always carries fresh state. */
export interface GameModResult {
  ok:        boolean;
  error?:    string;
  count?:    number;
  language?: { ok: boolean; previous?: Record<string, string> } | null;
  state:     GameModState;
}

/** Result of get_launcher_update_info - the self-update panel's state. */
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
  openExternal:     (url: string)               => call<OpResult>("open_external", url),
  applySteamTranslation: ()                     => call<OpResult & {steam_dir?: string}>("apply_steam_translation"),
  /** Local lifecycle for the Steam Hebrew mod. `getSteamModState`
   *  drives the AppsView Install/Enable/Disable button; the toggle and
   *  cache-clear are plain local file ops on the launcher's mod cache. */
  getSteamModState:   ()                        => call<SteamModState>("get_steam_mod_state"),
  setSteamModEnabled: (enabled: boolean)        => call<OpResult>("set_steam_mod_enabled", enabled),
  clearSteamModCache: ()                        => call<OpResult>("clear_steam_mod_cache"),

  /** VirtualDJ 2026 Hebrew - cloud-delivered, same 3-state lifecycle as Steam. */
  applyVirtualdjTranslation: ()                 => call<OpResult>("apply_virtualdj_translation"),
  getVirtualdjModState: ()                      => call<VirtualDjModState>("get_virtualdj_mod_state"),
  setVirtualdjModEnabled: (enabled: boolean)    => call<OpResult>("set_virtualdj_mod_enabled", enabled),
  clearVirtualdjModCache: ()                    => call<OpResult>("clear_virtualdj_mod_cache"),

  // Borderless Gaming (FREE software): interface + effect editor. Same state
  // shape as VirtualDJ, so the shared native-applier UI path covers it.
  applyBorderlessGamingTranslation: ()          => call<OpResult>("apply_borderless_gaming_translation"),
  getBorderlessGamingModState: ()               => call<VirtualDjModState>("get_borderless_gaming_mod_state"),
  setBorderlessGamingModEnabled: (enabled: boolean) => call<OpResult>("set_borderless_gaming_mod_enabled", enabled),
  clearBorderlessGamingModCache: ()             => call<OpResult>("clear_borderless_gaming_mod_cache"),

  // SignalRGB (₪15 software): 4 surfaces + registry locale, cloud-delivered.
  // Same {cached, enabled, version, owned, priceCents} state shape.
  applySignalrgbTranslation: ()                 => call<OpResult>("apply_signalrgb_translation"),
  getSignalrgbModState: ()                      => call<VirtualDjModState>("get_signalrgb_mod_state"),
  setSignalrgbModEnabled: (enabled: boolean)    => call<OpResult>("set_signalrgb_mod_enabled", enabled),
  clearSignalrgbModCache: ()                    => call<OpResult>("clear_signalrgb_mod_cache"),
  restartSignalrgb: ()                          => call<OpResult>("restart_signalrgb"),

  // ── Download-distributed game mods (Cyberpunk 2077) ───────
  /** State of a game's downloadable mod - cached / installed / owned /
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
  /** Clear-cache for the native appliers (SM2/WD2/GTAV/GoWR/HL/W3/PT/VirtualDJ):
   *  revert the mod from the game (if installed) then wipe the download cache. */
  clearNativeModCache:       (id: string) => call<OpResult>("clear_native_mod_cache", id),
  /** Open the website checkout in the browser for a paid game mod. */
  openPurchasePage:          (id: string) =>
                                call<{ ok: boolean; url?: string; error?: string }>("open_purchase_page", id),

  // ── Game-mod updates (manifest version vs installed) ──────
  /** Is a newer translation-mod version available for this game? Network
   *  manifest check (no archive), run off the GUI thread. */
  checkGameModUpdate:  (id: string) => call<GameModUpdate>("check_game_mod_update", id),
  getOfflineAssets:    () => call<OfflineAssets>("get_offline_assets"),
  /** All installed translation mods that have a newer version available -
   *  drives the Downloads/Updates screen's mod section. */
  getModUpdates:       ()           => call<ModUpdate[]>("get_mod_updates"),

  // ── mod update preferences (beta channel) ──
  getUpdatePrefs:    () => call<UpdatePrefs>("get_update_prefs"),
  setUpdatePrefs:    (betaChannel: boolean) =>
    call<UpdatePrefs>("set_update_prefs", betaChannel),
  setModBetaOverride: (gameId: string, enabled: boolean | null) =>
    call<UpdatePrefs>("set_mod_beta_override", gameId, enabled),
  /** Show a native Windows notification (tray toast). Used to surface an
   *  available translation update; no-op on the Eel dev build. */
  notifyOs:          (title: string, body: string) =>
    call<boolean>("notify_os", title, body),
  /** Tell the Qt shell the first screen is fully loaded (data + images) so it
   *  dismisses the native boot splash and reveals the finished app. Fire-and-
   *  forget; a no-op on the Eel dev build (no native splash there). */
  notifyAppReady:    () => { try { void call<void>("notify_app_ready"); } catch { /* dev/no-op */ } },
  /** Launcher identity. `display` is the FULL version (v1.0.0-dev.N) to render
   *  verbatim; version/channel/devBuild are the raw parts. */
  getAppInfo: () => call<{ version: string; channel: string; devBuild: number; display: string }>("get_app_info"),

  // ── Spider-Man 2 native applier (no Overstrike) ───────────
  getSpiderman2ModState: () => call<SpiderMan2State>("get_spiderman2_mod_state"),
  /** Apply the bundled Hebrew mod to the game's TOC on a worker; progress +
   *  a terminal done/error tick stream over onModProgress. */
  installSpiderman2Mod:  () => call<{ ok: boolean; error?: string; started?: boolean }>("install_spiderman2_mod"),
  /** Revert the mod (restore the TOC backup + delete our archives). */
  removeSpiderman2Mod:   () => call<{ ok: boolean; error?: string; state: SpiderMan2State }>("remove_spiderman2_mod"),
  /** Network check - is a newer SM2 version available on the server? */
  checkSpiderman2Update: () => call<SpiderMan2Update>("check_spiderman2_update"),

  // ── Watch Dogs 2 native applier (FAT5 fat-redirect, no Overstrike) ──
  getWatchdogs2ModState: () => call<WatchDogs2State>("get_watchdogs2_mod_state"),
  /** Apply the bundled Hebrew files to the game's FAT5 archives on a worker;
   *  progress + a terminal done/error tick stream over onModProgress. */
  installWatchdogs2Mod:  () => call<{ ok: boolean; error?: string; started?: boolean }>("install_watchdogs2_mod"),
  /** Revert the mod (restore the original archives + delete our backups). */
  removeWatchdogs2Mod:   () => call<{ ok: boolean; error?: string; state: WatchDogs2State }>("remove_watchdogs2_mod"),

  // ── God of War: Ragnarök native applier (single-file WAD swap) ─────
  getGowrModState: () => call<GowrState>("get_gowr_mod_state"),
  /** Back up + atomically swap in the bundled Hebrew WAD on a worker;
   *  progress + a terminal done/error tick stream over onModProgress. */
  installGowrMod:  () => call<{ ok: boolean; error?: string; started?: boolean }>("install_gowr_mod"),
  /** Revert the mod (restore the original WAD from our backup). */
  removeGowrMod:   () => call<{ ok: boolean; error?: string; state: GowrState }>("remove_gowr_mod"),

  // ── Hogwarts Legacy / The Witcher 3 / A Plague Tale: Requiem ──────
  // Download-only native appliers (fetch from the Worker + apply). Same state
  // shape as GowrState. install streams onModProgress; get/remove are quick.
  getHogwartsModState:   () => call<GowrState>("get_hogwarts_mod_state"),
  installHogwartsMod:    () => call<{ ok: boolean; error?: string; started?: boolean }>("install_hogwarts_mod"),
  removeHogwartsMod:     () => call<{ ok: boolean; error?: string; state: GowrState }>("remove_hogwarts_mod"),
  getWitcher3ModState:   () => call<GowrState>("get_witcher3_mod_state"),
  installWitcher3Mod:    () => call<{ ok: boolean; error?: string; started?: boolean }>("install_witcher3_mod"),
  removeWitcher3Mod:     () => call<{ ok: boolean; error?: string; state: GowrState }>("remove_witcher3_mod"),
  getPlagueTaleModState: () => call<GowrState>("get_plaguetale_mod_state"),
  installPlagueTaleMod:  () => call<{ ok: boolean; error?: string; started?: boolean }>("install_plaguetale_mod"),
  removePlagueTaleMod:   () => call<{ ok: boolean; error?: string; state: GowrState }>("remove_plaguetale_mod"),

  // ── GTA V native OpenIV-free RPF7 applier ──────────────────────────
  getGtavModState: () => call<GtavState>("get_gtav_mod_state"),
  /** Read-modify-write the Hebrew text+fonts into the OPEN mods RPFs on a worker
   *  (heavy, multi-GB); progress + a terminal done/error tick stream over onModProgress. */
  installGtavMod:  () => call<{ ok: boolean; error?: string; started?: boolean; state?: GtavState }>("install_gtav_mod"),
  /** SURGICAL remove - swap the Hebrew text+fonts back to vanilla English IN PLACE,
   *  preserving the user's other mods (does NOT use the stale install backup). Worker. */
  removeGtavMod:   () => call<{ ok: boolean; error?: string; started?: boolean }>("remove_gtav_mod"),
  /** Separate FULL restore from the install-time backup = exact pre-install state
   *  (⚠ discards changes made since install). Worker; progress streams. */
  restoreGtavBackup: () => call<{ ok: boolean; error?: string; started?: boolean }>("restore_gtav_backup"),

  // ── In-game text-language switch (auto / Hebrew[Arabic] / English) ──
  /** Current language-switch state. supported=false → hide the control. */
  getGameLanguage:     (id: string) => call<GameLanguageState>("get_game_language", id),
  /** Apply + persist a language mode. */
  setGameLanguage:     (id: string, mode: "auto" | "hebrew" | "english") =>
                          call<{ ok: boolean; supported?: boolean; mode?: string; applied?: string; error?: string }>(
                            "set_game_language", id, mode),
  /** Revert to the pre-mod language (the value before the launcher's first switch). */
  restoreGameLanguage: (id: string) =>
                          call<{ ok: boolean; supported?: boolean; restored?: string; error?: string }>(
                            "restore_game_language", id),
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
  // ── Custom frameless title bar (Qt build; safe no-ops on the Eel build) ──
  windowIsFrameless:    ()               => call<boolean>("window_is_frameless"),
  windowIsMaximized:    ()               => call<boolean>("window_is_maximized"),
  windowMinimize:       ()               => call<void>("window_minimize"),
  windowToggleMaximize: ()               => call<boolean>("window_toggle_maximize"),
  windowClose:          ()               => call<void>("window_close"),
  windowStartDrag:      ()               => call<void>("window_start_drag"),
  windowStartResize:    (edge: string)   => call<void>("window_start_resize", edge),
  // ── "ביג-לאנץ" console shell (separate 10ft UI) ──────────────────────────
  /** Put the window into / out of the borderless-fullscreen console state.
   *  The React side then swaps roots via the `#big` fragment + a reload, so
   *  the two shells never coexist. Safe no-op on the Eel build. */
  setBigLaunch:         (on: boolean)    => call<boolean>("set_big_launch", on),
  /** True when this process was started with `--big` (its own shortcut), so
   *  the shell knows the window is ALREADY fullscreen and skips re-applying. */
  bigLaunchRequested:   ()               => call<boolean>("big_launch_requested"),
  /** A real application exit (not "close to tray") - the console shell's
   *  power menu needs a genuine quit, not the close-behavior pref. */
  appQuit:              ()               => call<void>("app_quit"),
  /** Is BigLaunch.exe - the separate 10ft console shell - installed here? */
  bigLaunchAvailable:   ()               => call<boolean>("big_launch_available"),
  /** Start the console shell as its own process (Steam -> Big Picture).
   *  It outlives this launcher and hands back via the hebrewhub:// deep link. */
  openBigLaunch:        ()               => call<OpResult>("open_big_launch"),
  getCustomTitlebar:    ()               => call<boolean>("get_custom_titlebar"),
  /** Static host profile - drives the UI's auto-degrade on a weak machine. */
  getMachineProfile:    ()               => call<MachineProfile>("get_machine_profile"),
  setCustomTitlebar:    (on: boolean)    => call<boolean>("set_custom_titlebar", on),
  /** Switchable app icon (window / taskbar / tray + launch shortcut). */
  getAppIcon:           ()               => call<AppIconState>("get_app_icon"),
  /** Apply a variant LIVE (window/taskbar/tray) + repoint the shortcuts. */
  setAppIcon:           (variant: string) => call<{ ok: boolean; variant: string; options: AppIconOption[] }>("set_app_icon", variant),
  /** Relaunch the launcher and exit this instance. Backs the "restart now" button
   *  offered by settings that only apply at process start (hardware acceleration,
   *  the custom title bar). */
  restartApp:           ()               => call<boolean>("restart_app"),
  /** Software catalog (Steam, etc.) - sister of getAllGames. Backend
   *  pulls /api/software with showOnLauncher filtering. */
  getAllSoftware:   ()                          => call<Game[]>("get_all_software"),
  /** Re-runs the local fingerprint sweep (registry + path checks)
   *  for every software entry. Also clears any "forgotten" software
   *  paths so they re-detect. Returns the refreshed catalog. */
  scanSoftware:     ()                          => call<{ software: Game[] }>("scan_software"),
  /** "Forget" a software's detected install path - it reports as
   *  not-installed until the next full scanSoftware(). */
  clearSoftwarePath: (id: string)               => call<{ software: Game[] }>("clear_software_path", id),

  // ── Launcher window/lifecycle prefs ───────────────────────
  /** Snapshot of close-behavior + autostart state. Frontend reads it
   *  on boot to know whether to show the first-launch close-behavior
   *  modal (closeBehavior === null). */
  getLauncherPrefs: ()                          => call<LauncherPrefs>("get_launcher_prefs"),
  /** Persist the close-behavior choice. Pass `null` to reset. */
  setCloseBehavior: (b: "minimize" | "close" | null) => call<{ ok: boolean; closeBehavior: LauncherPrefs["closeBehavior"]; startWithOs: boolean }>("set_close_behavior", b),
  /** Toggle the HKCU autostart Run-key entry. */
  setStartWithOs:   (enabled: boolean) => call<{ ok: boolean; error?: string; startWithOs: boolean; closeBehavior: LauncherPrefs["closeBehavior"] }>("set_start_with_os", enabled),
  /** Toggle GPU hardware acceleration (compositing). Takes effect on next launch. */
  setGpuCompositing: (enabled: boolean) => call<{ ok: boolean; disableGpu: boolean; startWithOs: boolean; closeBehavior: LauncherPrefs["closeBehavior"] }>("set_gpu_compositing", enabled),
  getLiveProgress:  (id: string)                => call<ProgressSnapshot | null>("get_live_progress", id),
  startDownload:    (id: string)                => call<{ok: boolean; error?: string}>("start_download", id),
  cancelDownload:   (id: string)                => call<{ok: boolean; error?: string}>("cancel_download", id),

  // ── Auth (Supabase OAuth + DRM) ───────────────────────────
  //   `mfaRequired` = the account has 2FA (TOTP). No session is stored yet;
  //   the UI must collect the 6-digit code and call `authVerifyMfa`.
  authLogin:        ()                          => call<{ok: boolean; user?: LauncherUser; mfaRequired?: boolean; factorId?: string; email?: string; error?: string}>("auth_login"),
  authMe:           ()                          => call<LauncherUser | null>("auth_me"),
  authLogout:       ()                          => call<{ok: boolean; error?: string}>("auth_logout"),
  /** One-shot: true iff this install was just displaced by a sign-in on
   *  another device (single-session). Clears the marker server-side read. */
  authConsumeTakeover: ()                        => call<boolean>("auth_consume_takeover"),
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
  /** Native OS clipboard write via Python (Qt build) - QtWebEngine blocks
   *  JS clipboard access, so the "copy link" button uses this. Returns
   *  false in the Eel build (no QClipboard); caller then falls back to JS. */
  copyToClipboard:  (text: string)              => call<boolean>("copy_to_clipboard", text),
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
  //   May return {mfaRequired:true} - same as authLogin - when the account
  //   has a verified TOTP factor. Finish with authVerifyMfa.
  authSignInPassword: (email: string, password: string) =>
    call<{ok: boolean; user?: LauncherUser; mfaRequired?: boolean; factorId?: string; email?: string; error?: string}>("auth_signin_password", email, password),
  authSignUpPassword: (email: string, password: string, fullName: string) =>
    call<{ok: boolean; user?: LauncherUser & {confirmed?: boolean}; confirmed?: boolean; error?: string}>(
      "auth_signup_password", email, password, fullName,
    ),
  /** Complete a pending 2FA login with the 6-digit TOTP code. Returns
   *  {ok,user} on success, or {ok:false,error} on a wrong/expired code. */
  authVerifyMfa: (code: string) =>
    call<{ok: boolean; user?: LauncherUser; error?: string}>("auth_verify_mfa", code),
  /** Abandon a pending 2FA challenge (user closed the code screen). */
  authCancelMfa: () => call<{ok: boolean}>("auth_cancel_mfa"),

  // ── Crash / error reporting ──
  /** Forward a frontend crash to Python (PII-scrubbed + opt-in gated there,
   *  POSTed to /api/crash). Fire-and-forget; safe to call from error paths. */
  reportCrash: (errorType: string, message: string, traceback: string, screen: string) =>
    call<boolean>("report_crash", errorType, message, traceback, screen),
  getCrashOptIn: () => call<boolean>("get_crash_opt_in"),
  setCrashOptIn: (enabled: boolean) => call<boolean>("set_crash_opt_in", enabled),
  /** Report ONE handled, non-fatal UI event (an RPC that rejected, a button
   *  handler that threw, an unhandled JS error / promise rejection, a React
   *  render error). Anonymous + silent + opt-in-gated on the Python side.
   *  Never surfaces anything to the user. */
  reportEvent: (kind: string, message: string, source: string, code: string, severity: string) =>
    call<{ ok: boolean }>("report_ui_event", kind, message, source, code, severity),

  // ── Plugins (cloud add-ons) ──
  /** {entitled, plugins:[{id,name,tagline,description,icon,version,accent,kind,installed,enabled}]} */
  getPlugins: () => call<PluginsSnapshot>("get_plugins"),
  installPlugin: (id: string) => call<OpResult>("install_plugin", id),
  removePlugin: (id: string) => call<OpResult>("remove_plugin", id),
  setPluginEnabled: (id: string, on: boolean) => call<OpResult>("set_plugin_enabled", id, on),
  updatePlugin: (id: string) => call<OpResult & { version?: string; addedSettings?: string[] }>("update_plugin", id),
  refreshPlugins: () => call<PluginsSnapshot & { refreshed?: boolean }>("refresh_plugins"),
  getPluginConfig: (id: string) => call<SaveBackupConfig>("get_plugin_config", id),
  setPluginConfig: (id: string, cfg: SaveBackupConfig) => call<OpResult>("set_plugin_config", id, cfg),
  pluginsBoot: () => call<OpResult>("plugins_boot"),
  /** Native "choose a folder" dialog (Qt, non-blocking). Resolves {ok,path}
   *  regardless of how long the user browses; a cancelled/orphaned pick → ok:false. */
  pickFolder: (title = "בחר תיקייה", start = "") => pickFile("folder", title, start),
  /** Native "choose the game EXE" dialog (Qt, non-blocking). Re-opening cancels a
   *  stale dialog; the result applies to the game the caller started the pick from. */
  pickExe: (title = "בחר את קובץ ה-EXE של המשחק", start = "") => pickFile("exe", title, start),
  // save-backup specifics
  savebackupDetect: () => call<DetectedSave[]>("savebackup_detect"),
  savebackupRunNow: (id = "save-backup", name = "") => call<{ ok: boolean; backed_up: number; errors: unknown[] }>("savebackup_run_now", id, name),
  savebackupList: (id = "save-backup") => call<SaveBackupItem[]>("savebackup_list", id),
  savebackupRestore: (backupPath: string, target: string) =>
    call<{ ok: boolean; safety?: string | null; error?: string }>("savebackup_restore", backupPath, target),
  // ── generic declarative plugin surface (renders/drives ANY cloud plugin) ──
  /** {ui, state, meta}. ui=null → the caller falls back to a built-in panel. */
  pluginUi: (id: string) => call<PluginUiResult>("plugin_ui", id),
  /** Perform one audited primitive; returns fresh state for the renderer. */
  pluginAction: (id: string, action: string, args: Record<string, unknown> = {}) =>
    call<PluginActionResult>("plugin_action", id, action, args),
};

export interface PluginMeta {
  id: string; kind: string; name: string; tagline?: string; description?: string;
  icon?: string; version?: string; accent?: string;
  installed?: boolean; enabled?: boolean;
  free?: boolean;              // needs only an account - no game purchase
  usable?: boolean;            // this plugin's OWN gate, already evaluated by the engine
  installedVersion?: string | null;
  updateAvailable?: boolean;   // the catalog offers a newer version
}
export interface PluginsSnapshot {
  entitled: boolean; signedIn?: boolean; plugins: PluginMeta[]; error?: string;
}

export interface SaveBackupEntry {
  id: string; game_id: string; label: string; source: string; enabled?: boolean; auto?: boolean;
}
export interface SaveBackupConfig {
  destination?: string;
  schedule?: "manual" | "on_boot" | "on_launch" | "realtime" | "daily" | "weekly" | "monthly";
  keep?: number;
  entries?: SaveBackupEntry[];
  last?: Record<string, { at: number; fp: number[]; count: number }>;
}
export interface DetectedSaveCandidate { path: string; source: "known" | "heuristic"; confidence: number; label: string; }
export interface DetectedSave { game_id: string; title: string; candidates: DetectedSaveCandidate[]; }
export interface SaveBackupItem { label: string; when: string; at: number; path: string; files: number; size_mb: number; }

// ── declarative plugin manifest + engine state (generic renderer) ──
export interface PluginUiNode {
  type: string;                                   // grid2|section|box|row|text|input|button|list|field
  title?: string; icon?: string; text?: string; value?: string; bind?: string;
  label?: string; action?: string; args?: Record<string, unknown>; variant?: string;
  tone?: string; visibleWhen?: string; disabledWhen?: string; confirm?: string;
  control?: string; options?: { value: string; label: string }[]; optionsBind?: string;
  badge?: string; subtext?: string; empty?: string; muted?: boolean;
  busyLabel?: string; placeholder?: string; dir?: string;
  min?: number; max?: number; width?: string; flex?: number; maxHeight?: string;
  size?: "lg" | "xl";                             // a stat number, not body text
  subtitle?: string;                              // hero
  toggle?: { bind: string; action: string; onLabel?: string; offLabel?: string;
             disabledWhen?: string; blockedHint?: string };
  items?: { label?: string; value?: string; caption?: string; tone?: string }[];  // stats
  clearInput?: boolean;                           // button inside a card: wipe its field
  card?: {                                        // cards: one rich card per data row
    title?: string; note?: string; chip?: string; chipWhen?: string;
    input?: { bind: string; placeholder?: string; dir?: string; secret?: boolean };
    buttons?: PluginUiNode[];
    steps?: { bind: string; title?: string };
  };
  headerActions?: PluginUiNode[];
  header?: { text?: string; button?: PluginUiNode };
  then?: { setLocalFrom?: Record<string, string>; clearLocal?: string[] };
  children?: PluginUiNode[];
  item?: { text?: string; subtext?: string; subtextDir?: "ltr" | "rtl"; badge?: string;
           chip?: { text: string; whenTone?: string }; buttons?: PluginUiNode[];
           editableAction?: string };
}
export interface PluginUiResult {
  ok: boolean;
  ui: PluginUiNode[] | null;
  state: Record<string, unknown>;
  meta: { id?: string; name?: string; icon?: string; accent?: string; version?: string; kind?: string };
  error?: string;
}
export interface PluginActionResult {
  ok: boolean; state?: Record<string, unknown>; status?: string; error?: string; path?: string;
}

/** Best-effort crash report that never throws - for use inside error
 *  handlers / ErrorBoundary where a second exception must not cascade.
 *  No-op when the bridge isn't ready (e.g. very early boot). */
export async function safeReportCrash(
  errorType: string, message: string, traceback: string, screen = '',
): Promise<void> {
  try {
    if (!api.ready()) return;
    if (!(await api.getCrashOptIn().catch(() => false))) return;
    await api.reportCrash(errorType, message ?? '', traceback ?? '', screen);
  } catch { /* swallow - reporting must never crash the crash handler */ }
}

/** Best-effort SILENT handled-event report. Never throws, never shows anything
 *  to the user, no-op when the bridge isn't ready. Opt-in is enforced on the
 *  Python side (report_event checks the disclosed `crash_reporting` pref), so
 *  the caller doesn't gate - but we DO drop our own reporter RPC to avoid a
 *  recursion loop, and dedup within a short window to stay cheap. */
const _eventSeen = new Set<string>();
export function safeReportEvent(
  kind: string, message = '', source = 'ui', code = '', severity: 'error' | 'warn' = 'error',
): void {
  try {
    if (!api.ready()) return;
    if (code === 'report_ui_event' || kind === 'report_ui_event') return;
    const key = `${kind}:${code}`;
    if (_eventSeen.has(key)) return;
    _eventSeen.add(key);
    if (_eventSeen.size > 200) _eventSeen.clear();   // bound the set
    void api.reportEvent(kind, message ?? '', source, code, severity).catch(() => {});
  } catch { /* reporting must never affect the UI */ }
}
