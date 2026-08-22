/* Mock of ../frontend/src/lib/eel.ts — swapped in by a Vite alias ONLY inside
 * the designer's /preview page, so the REAL launcher App renders 1:1 with
 * believable sample data instead of needing the Qt/Eel backend.
 *
 * Must export the SAME named surface as the real eel.ts:
 *   jsLog, isReady, onModProgress, onLauncherUpdateProgress,
 *   onCatalogRefreshComplete, api, safeReportCrash
 * (a missing export → runtime "undefined is not a function" in some view).
 *
 * Getters return sample data; actions resolve to harmless results. */

export function jsLog(_message: string): void { /* no-op */ }
export function isReady(): boolean { return true; }

export function onModProgress(_cb: (p: any) => void): () => void { return () => {}; }
export function onLauncherUpdateProgress(_cb: (p: any) => void): () => void { return () => {}; }
export function onCatalogRefreshComplete(_cb: (p: any) => void): () => void { return () => {}; }
export async function safeReportCrash(..._a: any[]): Promise<void> { /* no-op */ }
// Must mirror EVERY export of frontend/src/lib/eel.ts: the designer swaps this
// module in wholesale, so a missing name is a hard ES-module load error that
// blanks the whole preview (this one silently broke the harness).
export async function safeReportEvent(..._a: any[]): Promise<void> { /* no-op */ }

const COVER = (id: string) => `https://hebrew-translation-hub.com/covers/${id}.webp`;

const GAMES: any[] = [
  { id: "cyberpunk", titleEn: "Cyberpunk 2077", titleHe: "סייברפאנק 2077", version: "1.0.0-beta.3",
    theme_key: "cyberpunk", availability: "available", tagline: "נייט סיטי בעברית מלאה",
    description: "תרגום עברי מלא — ממשק + כתוביות.", progress: null, install_path: "C:/Games/Cyberpunk 2077",
    is_installed: true, has_mod_support: true, mod_state: "ACTIVE", featured: true, sortOrder: 1,
    cover: COVER("cyberpunk"), currentLanguage: "hebrew", releaseStage: "beta", changelog: "1,275 תיקוני QA." },
  { id: "spiderman2", titleEn: "Marvel's Spider-Man 2", titleHe: "ספיידרמן 2", version: "1.0.0-beta.6",
    theme_key: "spiderman2", availability: "available", tagline: "ממשק + כתוביות בעברית",
    description: "תרגום עברי מלא ל-Spider-Man 2.", progress: null, install_path: "C:/Games/Spider-Man 2",
    is_installed: true, has_mod_support: true, mod_state: "NOT_INSTALLED", featured: true, sortOrder: 2,
    cover: COVER("spiderman2"), currentLanguage: "english", releaseStage: "beta" },
  { id: "anno1800", titleEn: "Anno 1800", titleHe: "אנו 1800", version: "1.0.0-beta.1",
    theme_key: "default", availability: "available", tagline: "ממשק מלא בעברית",
    description: "תרגום עברי לכל ממשק המשחק.", progress: null, install_path: null,
    is_installed: false, has_mod_support: true, mod_state: "NOT_INSTALLED", featured: false, sortOrder: 3,
    cover: COVER("anno1800"), currentLanguage: null, releaseStage: "beta" },
  { id: "watchdogs2", titleEn: "Watch Dogs 2", titleHe: "ווטש דוגס 2", version: "1.0.0-beta.2",
    theme_key: "default", availability: "available", tagline: "ממשק + כתוביות",
    description: "תרגום עברי מלא.", progress: null, install_path: null,
    is_installed: false, has_mod_support: true, mod_state: "NOT_INSTALLED", featured: false, sortOrder: 4,
    cover: COVER("watchdogs2"), currentLanguage: null, releaseStage: "beta" },
  { id: "gtav", titleEn: "Grand Theft Auto V", titleHe: "GTA V", version: "1.0.0-beta.2",
    theme_key: "default", availability: "available", tagline: "תרגום מלא לעברית",
    description: "ממשק + עלילה בעברית.", progress: null, install_path: "F:/Games/Grand Theft Auto V Legacy",
    is_installed: true, has_mod_support: true, mod_state: "NOT_INSTALLED", featured: false, sortOrder: 5,
    cover: COVER("gtav"), currentLanguage: "english", releaseStage: "beta" },
];

const NEWS: any[] = [
  { id: "n1", title: "ספיידרמן 2 — גרסת בטא 6 שוחררה", body: "שמות בעברית קנונית + תיקוני RTL.", date: "2026-06-25", tag: "עדכון" },
  { id: "n2", title: "Anno 1800 זמין לרכישה", body: "תרגום עברי מלא לממשק המשחק.", date: "2026-06-22", tag: "חדש" },
];

const USER: any = { id: "u1", email: "demo@example.com", fullName: "משתמש לדוגמה",
  name: "משתמש לדוגמה", avatarUrl: "" };

const PREFS: any = { closeBehavior: "minimize", startWithOs: false };
const APPINFO: any = { version: "1.0.0", channel: "dev", devBuild: 7, display: "v1.0.0-dev.7" };

const modState = (g: any): any => ({
  state: g.mod_state, installed: g.mod_state === "ACTIVE",
  version: g.version, hasUpdate: false, latestVersion: g.version,
  modSlug: g.has_mod_support ? `${g.id}-hebrew` : null,
  priceCents: g.id === "anno1800" || g.id === "gtav" ? 5300 : 0,
  owned: true, hasPath: !!g.install_path, installPath: g.install_path,
});

const ok = (extra: any = {}) => Promise.resolve({ ok: true, ...extra });

const _apiImpl: any = {
  ready: () => true,
  getAllGames: () => Promise.resolve(GAMES),
  getGame: (id: string) => Promise.resolve(GAMES.find((g) => g.id === id) || GAMES[0]),
  getNews: () => Promise.resolve(NEWS),
  refreshCatalog: () => Promise.resolve({ ok: true, games: GAMES, news: NEWS, catalog_source: "mock", news_source: "mock" }),
  scanQuick: () => Promise.resolve({ games: GAMES, found: GAMES.length }),
  scanDeep: () => Promise.resolve({ games: GAMES, found: GAMES.length }),
  setCustomPath: (id: string) => api.getGame(id),
  clearCustomPath: (id: string) => api.getGame(id),
  enableMod: () => ok(), disableMod: () => ok(), uninstallMod: () => ok(),
  launchGame: () => ok(), openFolder: () => ok(),
  applySteamTranslation: () => ok({ steam_dir: "C:/Program Files (x86)/Steam" }),
  getSteamModState: () => Promise.resolve({ installed: false, enabled: false, cached: false, version: null }),
  setSteamModEnabled: () => ok(), clearSteamModCache: () => ok(),
  getGameModState: (id: string) => Promise.resolve(modState(GAMES.find((g) => g.id === id) || GAMES[0])),
  downloadAndInstallGameMod: () => ok(), setGameModInstalled: () => ok(), clearGameModCache: () => ok(),
  openPurchasePage: () => ok(),
  checkGameModUpdate: () => Promise.resolve({ hasUpdate: false, latestVersion: null, currentVersion: null }),
  getModUpdates: () => Promise.resolve([]),
  getUpdatePrefs: () => Promise.resolve({ betaChannel: false, modBetaOverrides: {} }),
  setUpdatePrefs: () => ok(), setModBetaOverride: () => ok(),
  notifyOs: () => ok(),
  getAppInfo: () => Promise.resolve(APPINFO),
  getGtavModState: () => Promise.resolve({ scenario: "ready", hasPath: true, installPath: "F:/Games/GTA V",
    available: true, vanillaAvailable: true, backupAvailable: false, hasMods: true, loaderConnected: true,
    installed: false, priceCents: 5300, owned: true, version: "1.0.0-beta.2" }),
  installGtavMod: () => ok({ started: true }), removeGtavMod: () => ok({ started: true }),
  restoreGtavBackup: () => ok({ started: true }),
  getGameLanguage: () => Promise.resolve({ supported: true, mode: "hebrew", interface: "hebrew", subtitles: "hebrew", original: "english" }),
  setGameLanguage: () => ok(), restoreGameLanguage: () => ok(),
  listUpdates: () => Promise.resolve([]),
  getLauncherUpdateInfo: () => Promise.resolve({ updateAvailable: false, version: APPINFO.version, channel: "dev" }),
  startLauncherUpdate: () => ok(), cancelLauncherUpdate: () => Promise.resolve({ ok: true }),
  getAllSoftware: () => Promise.resolve([]),
  scanSoftware: () => Promise.resolve({ software: [] }),
  clearSoftwarePath: () => Promise.resolve({ software: [] }),
  getLauncherPrefs: () => Promise.resolve(PREFS),
  setCloseBehavior: (b: any) => Promise.resolve({ ok: true, closeBehavior: b, startWithOs: PREFS.startWithOs }),
  setStartWithOs: (e: any) => Promise.resolve({ ok: true, startWithOs: e, closeBehavior: PREFS.closeBehavior }),
  getLiveProgress: () => Promise.resolve(null),
  startDownload: () => ok(), cancelDownload: () => ok(),
  authLogin: () => ok({ user: USER }),
  authMe: () => Promise.resolve(USER),
  authLogout: () => ok(),
  authConsumeTakeover: () => Promise.resolve(false),
  authOwnsGame: () => Promise.resolve(true),
  authGetMyPurchases: () => Promise.resolve({ purchases: [] }),
  authGetMyVotes: () => Promise.resolve([]),
  authAbortLogin: () => ok({ aborted: true }),
  authGetAuthorizeUrl: () => Promise.resolve(null),
  authGetAccessToken: () => Promise.resolve(null),
  authSignInPassword: () => ok({ user: USER }),
  authSignUpPassword: () => ok({ user: USER }),
  reportCrash: () => ok(),
  getCrashOptIn: () => Promise.resolve(false),
  setCrashOptIn: () => Promise.resolve(true),
};

// The launcher's real `api` grows constantly; this mock always trails it, and a
// missing method used to blow up the WHOLE preview with
// "api.<x> is not a function" (which is exactly how the harness silently rotted).
// A Proxy makes any un-mocked call resolve to a harmless default instead, so the
// designer keeps rendering the real UI and only the un-mocked DATA is empty.
export const api: any = new Proxy(_apiImpl, {
  get(target, prop: string) {
    if (prop in target) return target[prop];
    return (..._a: any[]) => {
      // Booleans the shell asks for at boot must not be undefined.
      if (/^(windowIsFrameless|getCustomTitlebar)$/.test(prop)) return Promise.resolve(false);
      if (/^(get|is|has|check|fetch|load|list|scan|auth|open|set|apply|install|remove|clear)/.test(prop)) {
        return Promise.resolve(null);
      }
      return Promise.resolve(undefined);
    };
  },
});
