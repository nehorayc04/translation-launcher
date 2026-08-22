// Root shell: video bg + sidebar + main content. No bottom bar - the previous
// heavy chrome row was replaced with a transient status toast and a tiny
// muted version label in the corner.
import { useCallback, useEffect, useRef, useState } from "react";
import VideoBackground   from "./components/VideoBackground";
import ErrorBoundary     from "./components/ErrorBoundary";
import Sidebar           from "./components/Sidebar";
import type { NavKey }   from "./components/Sidebar";
import HomeView          from "./views/HomeView";
import LibraryView       from "./views/LibraryView";
import AppsView          from "./views/AppsView";
import SettingsView      from "./views/SettingsView";
import DownloadsView     from "./views/DownloadsView";
import PersonalAreaView  from "./views/PersonalAreaView";
import GameDetailPanel   from "./views/GameDetailPanel";
import CloseBehaviorModal from "./components/CloseBehaviorModal";
import SplashScreen from "./components/SplashScreen";
import PluginsSettings from "./components/PluginsSettings";
import PluginPage from "./views/PluginPage";
import { ResizeHandles } from "./components/TitleBar";
import CoachTour from "./components/CoachTour";
import WhatsNewModal, { hasUnseenVersion, markVersionSeen } from "./components/WhatsNewModal";
import NotifToast from "./components/NotifToast";
import { api, onModProgress, onCatalogRefreshComplete, onLauncherUpdateProgress } from "./lib/eel";
import type { Game, LauncherPrefs } from "./lib/types";
import { SiteConfigProvider } from "./lib/useSiteConfig";
import { LauncherAuthProvider } from "./lib/useLauncherAuth";
import { AccentProvider } from "./lib/useAccent";
import { initRipple } from "./lib/ripple";
import { initSpatialNav } from "./lib/spatialNav";
import { initUiSounds } from "./lib/sound";
import { initThemePrefs, getSidebarMode, setMachineTier, applyAnims, getAnims, animsIsExplicit, applyBackdrop, autoBackdrop } from "./lib/themePrefs";
import { resolveCoverUrl, initOfflineImages } from "./lib/coverUrl";
import { initNotifications, pushNotif } from "./lib/notifications";

// Apply persisted appearance prefs (animations/density) before first paint.
initThemePrefs();

export const APP_VERSION = "v1.2.0";

// "ביג-לאנץ" is a SEPARATE PROGRAM, the Steam / Big-Picture shape: two shells,
// two executables (TranslationManager.exe + BigLaunch.exe), each with its own
// AppUserModelID so Windows gives them separate taskbar buttons.
//
// This is the ONLY launcher -> console direction, and the console has exactly
// ONE button back (in its Settings). There is deliberately NO in-process React
// console any more: a second implementation would drift from the native one and
// would carry a second way out, which is precisely what must not exist.
async function enterBigLaunch(report?: (msg: string) => void) {
  try {
    if (await api.bigLaunchAvailable()) {
      const r = await api.openBigLaunch();
      if (r?.ok) return;                       // the native shell took over
      report?.(r?.error || "לא ניתן לפתוח את ביג-לאנץ");
      return;
    }
  } catch { /* fall through to the honest error below */ }

  // Missing BigLaunch.exe means a damaged install, not an older build - the
  // installer ships it. Say so instead of opening a different-looking screen.
  report?.("ביג-לאנץ לא נמצא. התקן מחדש את התוכנה כדי לשחזר אותו.");
}

export default function App() {
  const [view,     setView]     = useState<NavKey>("home");
  // "ספרייה" sidebar group → two views: games (LibraryView) + software (AppsView).
  const [selectedSoft, setSelectedSoft] = useState<Game | null>(null);
  // Bumped once the offline image mirror is wired, to re-render every <img>
  // with its local src. The value itself is unused - the setState IS the point.
  const [, setImgEpoch] = useState(0);
  const [games,    setGames]    = useState<Game[]>([]);
  // SOFTWARE is fetched ONCE at boot (like games) and handed to AppsView as a
  // prop, so opening "תוכנות" paints INSTANTLY instead of re-fetching (and
  // showing "טוען…") on every single mount.
  const [software, setSoftware] = useState<Game[]>([]);
  const [selected, setSelected] = useState<Game | null>(null);
  const [status,   setStatus]   = useState<string | undefined>(undefined);
  // Actionable update banner (persists until clicked/dismissed) - distinct from
  // the transient `status` toast. gameId set → clicking opens that game's panel;
  // else → opens the Downloads/Updates screen.
  const [updateNotice, setUpdateNotice] = useState<{ body: string; gameId?: string } | null>(null);
  const [loading,  setLoading]  = useState(true);
  /** Launcher window/lifecycle prefs. `null` while we haven't loaded
   *  yet (don't show the modal during the brief pre-load window). */
  const [launcherPrefs, setLauncherPrefs] = useState<LauncherPrefs | null>(null);
  /** True while the close-behavior modal is open - driven exclusively
   *  by the X-click `beforeunload` interceptor below. NEVER shown on
   *  app startup. */
  const [showCloseModal, setShowCloseModal] = useState(false);
  /** Latch set once the user has resolved the close modal so the
   *  re-fired beforeunload (from window.close()) doesn't loop. */
  const closingRef = useRef(false);
  // Controller "sidebar focus" state: remembers the focus + sidebar mode from
  // before the GUIDE button jumped into the sidebar, so we can restore both.
  const sidebarFocusRef = useRef<{ prevFocus: HTMLElement | null; prevMode: string } | null>(null);
  // Where to return when the Options button toggles OUT of Settings.
  const settingsReturnRef = useRef<NavKey>("home");
  // Bumped every time the sidebar refresh button completes successfully.
  // Views that fetch their own slice of data (NewsSection, DownloadsView)
  // include this in their effect deps so they re-pull instead of waiting
  // for the next unmount/remount.
  const [refreshNonce, setRefreshNonce] = useState(0);
  // Full launcher version (v1.0.0-dev.N) from Python - single source of truth
  // so the sidebar footer + Settings show the same complete string.
  const [appVersion, setAppVersion] = useState(APP_VERSION);
  // Branded launch splash - shown once on boot, then unmounts.
  const [splashDone, setSplashDone] = useState(false);
  // The splash stays up until the first screen's images are cached, so the app
  // never "opens then fills in" a few seconds later. Preloading warms the
  // QtWebEngine disk cache, so the SECOND launch flips this true almost instantly.
  const [imagesReady, setImagesReady] = useState(false);
  // Self-update: when the installer is spawned (phase "launch") the app is about
  // to exit - show a branded full-screen overlay so the OLD window's LAST frame
  // is the loading splash, not a frozen progress panel (the new exe's native boot
  // splash then covers the fresh boot). No blank/frozen frame during the update.
  const [updating, setUpdating] = useState(false);
  useEffect(() => {
    const off = onLauncherUpdateProgress((p) => {
      if (p && (p as { phase?: string }).phase === "launch") setUpdating(true);
    });
    return typeof off === "function" ? off : undefined;
  }, []);
  // True once the first-screen image BYTES are actually decoded (not just
  // requested) - the DOM-ready gate below waits for this so the black splash
  // never lifts before the covers/banners are painted.
  const [mediaDecoded, setMediaDecoded] = useState(false);
  // First-run onboarding tour (shown after the splash, once ever).
  const [onboarded, setOnboarded] = useState<boolean>(() => {
    try { return localStorage.getItem("onboardingDone") === "1"; } catch { return true; }
  });
  const finishOnboarding = useCallback(() => {
    setOnboarded(true);
    try { localStorage.setItem("onboardingDone", "1"); } catch { /* ignore */ }
  }, []);
  // "What's new" - shown ONCE on the first launch after an update to a new
  // version (never on a brand-new install: there the guided tour runs instead,
  // and we just record the version so the card doesn't fire on the 2nd launch).
  const [showWhatsNew, setShowWhatsNew] = useState<boolean>(() => {
    const fresh = (() => { try { return localStorage.getItem("onboardingDone") !== "1"; } catch { return false; } })();
    if (fresh) { markVersionSeen(); return false; }
    return hasUnseenVersion();
  });
  const closeWhatsNew = useCallback(() => { setShowWhatsNew(false); markVersionSeen(); }, []);
  // Custom frameless title bar - off by default (native frame). When the pref
  // is on (Qt build), we draw our own title bar + resize handles and lay the
  // shell out as a column beneath it. Anything but true = the app is BYTE-
  // IDENTICAL to the native-frame layout (zero risk to the default).
  const [frameless, setFrameless] = useState(false);
  useEffect(() => { void api.windowIsFrameless().then((v) => setFrameless(!!v)).catch(() => {}); }, []);

  // ── boot: pull games as soon as eel is ready ─────────────────
  const refresh = useCallback(async () => {
    try {
      const data = await api.getAllGames();
      setGames(data);
      if (selected) {
        const fresh = data.find((g) => g.id === selected.id);
        if (fresh) setSelected(fresh);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [selected?.id]);

  // Preload the first screen's images (covers + banners) so they're PAINTED, not
  // streaming in, by the time the splash lifts. `new Image()` shares the browser
  // HTTP cache, so a warm 2nd launch resolves instantly. Runs once, and always
  // resolves (a 4.5s cap covers a slow/dead network so the splash can't hang).
  // WARM the browser cache with the first-screen images (featured banners +
  // covers). Pure cache warming - it does NOT gate the splash by itself; the
  // real gate is the DOM-images check below (waits for the ACTUALLY-rendered
  // images), which is why the old preload-only approach still let images
  // "pop in" after the splash lifted.
  const preloadedRef = useRef(false);
  useEffect(() => {
    if (preloadedRef.current || games.length === 0) return;
    preloadedRef.current = true;
    const FALLBACK_IDS = ["cyberpunk", "gowragnarok", "tsushima", "rdr1", "rdr2", "gtav", "hogwarts"];
    const flagged = games.filter((g) => g.featured);
    const featured = flagged.length > 0
      ? [...flagged].sort((a, b) => (a.sortOrder ?? 1000) - (b.sortOrder ?? 1000))
      : FALLBACK_IDS.map((id) => games.find((g) => g.id === id)).filter((g): g is Game => Boolean(g));
    const urls = new Set<string>();
    for (const g of featured.slice(0, 8)) { if (g.bannerUrl) urls.add(g.bannerUrl); urls.add(resolveCoverUrl(g.cover, g.id)); }
    for (const g of games.slice(0, 16)) urls.add(resolveCoverUrl(g.cover, g.id));
    // Decode the actual bytes and WAIT for them all - this gates the splash so
    // the black screen holds until every first-screen image is painted-ready.
    const list = [...urls].filter(Boolean);
    const proms = list.map((u) => {
      const img = new Image();
      img.src = u;
      return typeof img.decode === "function"
        ? img.decode().catch(() => {})
        : new Promise<void>((res) => { img.onload = () => res(); img.onerror = () => res(); });
    });
    let settled = false;
    const done = () => { if (!settled) { settled = true; setMediaDecoded(true); } };
    void Promise.allSettled(proms).then(done);
    const cap = window.setTimeout(done, 10000);   // hard ceiling so a dead network can't strand it
    return () => window.clearTimeout(cap);
  }, [games]);

  // ⭐ Hold the splash until the app's first-screen images (rendered BEHIND the
  // splash) have actually LOADED - not merely preloaded - so nothing "pops in"
  // after it lifts (this is the fix the preload-only versions kept missing).
  // Waits for every VISIBLE <img> in the DOM to be `complete`; off-screen
  // lazy images are ignored, a 1.2s grace covers a screen with no images, and
  // a 6s hard cap guarantees a dead network never strands the splash.
  useEffect(() => {
    // Wait for the first-screen image BYTES to be decoded FIRST (mediaDecoded),
    // then confirm every visible <img> in the DOM is `complete` before lifting -
    // so the black splash never reveals a half-loaded home.
    if (loading || games.length === 0 || !mediaDecoded) return;
    let done = false;
    let sawImages = false;
    let timer = 0;
    const t0 = Date.now();
    const finish = () => { if (!done) { done = true; setImagesReady(true); } };
    const inView = (im: HTMLImageElement) => {
      const r = im.getBoundingClientRect();
      return r.width > 0 && r.bottom > 0 && r.top < window.innerHeight;
    };
    const tick = () => {
      const imgs = (Array.from(document.querySelectorAll("img")) as HTMLImageElement[])
        .filter((im) => im.getAttribute("src") && inView(im));
      if (imgs.length) sawImages = true;
      const pending = imgs.filter((im) => !im.complete);   // an errored img is `complete` → never blocks
      if (sawImages && pending.length === 0) return finish();
      if (!sawImages && Date.now() - t0 > 800) return finish();
      timer = window.setTimeout(tick, 120);
    };
    const start = window.setTimeout(tick, 40);   // let the home view mount its images first
    const cap = window.setTimeout(finish, 3000); // (media already decoded → short)
    return () => { window.clearTimeout(start); window.clearTimeout(timer); window.clearTimeout(cap); };
  }, [loading, games.length, mediaDecoded]);


  // Full launcher version string (v1.0.0-dev.N) from the Python side, fetched
  // once on boot so every surface renders the exact same complete version.
  useEffect(() => {
    let alive = true;
    void api.getAppInfo()
      .then((i) => { if (alive && i?.display) setAppVersion(i.display); })
      .catch(() => {});
    return () => { alive = false; };
  }, []);

  // Notifications + background-activity store: subscribe ONCE to the launcher-
  // update / mod-install progress streams (so an in-flight download is tracked
  // app-wide and never "disappears" when a screen unmounts) + pull the admin
  // news feed as system notifications for the bell above the avatar.
  useEffect(() => { initNotifications(); }, []);

  // OFFLINE PACKAGE: point covers/banners/logos at the locally bundled mirror
  // when one exists. Covers are absolute server URLs, so on a machine with no
  // internet nothing renders without this. Runs once, fail-soft (no package =
  // the resolver just keeps returning the normal server URLs).
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const a = await api.getOfflineAssets();
        if (alive && a?.imagesBase && a.imageRels?.length) {
          initOfflineImages(a.imagesBase, a.imageRels);
          setImgEpoch((n) => n + 1);     // re-render <img>s with the local src
        }
      } catch { /* no bundle / older backend - keep server URLs */ }
    })();
    return () => { alive = false; };
  }, []);

  // AUTO-DEGRADE on a weak machine. initThemePrefs already decided from the GPU
  // probe + prefers-reduced-motion; the host TIER only arrives once the bridge
  // is up, so re-apply then. An EXPLICIT user choice is never overridden.
  useEffect(() => {
    let dead = false;
    void api.getMachineProfile().then((m) => {
      if (dead || !m?.tier) return;
      setMachineTier(m.tier);
      if (!animsIsExplicit()) applyAnims(getAnims());
      applyBackdrop(autoBackdrop());       // drop the CPU-blur on a weak host
    }).catch(() => {});
    return () => { dead = true; };
  }, []);

  // Global click-ripple on buttons (premium tactile feedback). One listener,
  // teardown on unmount.
  useEffect(() => initRipple(), []);

  // Console-style keyboard + controller spatial navigation.
  useEffect(() => initSpatialNav(), []);

  // Optional UI click sounds (off by default; gated by the Appearance pref).
  useEffect(() => initUiSounds(), []);

  // Controller GUIDE button (the centre PS/Xbox logo, `nav-sidebar` event) →
  // toggle "sidebar focus": expand the sidebar + move focus INTO it; press
  // again to collapse it back to the previous mode AND return focus exactly
  // where it was. The sidebar's saved preference is never overwritten - we
  // only push a transient live mode via the `sidebarmode` event.
  useEffect(() => {
    const onSidebar = () => {
      if (!sidebarFocusRef.current) {
        // enter: remember focus + the live mode, force-expand, focus 1st item
        sidebarFocusRef.current = {
          prevFocus: document.activeElement as HTMLElement | null,
          prevMode: getSidebarMode(),
        };
        window.dispatchEvent(new CustomEvent("sidebarmode", { detail: "wide" }));
        document.body.classList.add("using-spatial-nav");
        requestAnimationFrame(() => {
          document.querySelector<HTMLElement>("[data-sidebar] nav button")?.focus();
        });
      } else {
        // exit: restore the previous mode + the previous focus
        const { prevFocus, prevMode } = sidebarFocusRef.current;
        sidebarFocusRef.current = null;
        window.dispatchEvent(new CustomEvent("sidebarmode", { detail: prevMode ?? "auto" }));
        requestAnimationFrame(() => prevFocus?.focus?.());
      }
    };
    window.addEventListener("nav-sidebar", onSidebar);
    return () => window.removeEventListener("nav-sidebar", onSidebar);
  }, []);

  // Controller Share/Create/View → Home · Options/Menu → toggle Settings.
  // (Re-bound on `view` so the Settings toggle knows where to return.)
  useEffect(() => {
    const clearSidebarFocus = () => {
      if (sidebarFocusRef.current) {
        window.dispatchEvent(new CustomEvent("sidebarmode", { detail: sidebarFocusRef.current.prevMode }));
        sidebarFocusRef.current = null;
      }
    };
    const navTo = (key: NavKey) => { clearSidebarFocus(); setSelected(null); setView(key); };
    const goHome = () => navTo("home");
    const goLibrary = () => navTo("games");
    const goDownloads = () => navTo("downloads");
    const goPersonal = () => navTo("personal");
    const goSoftware = () => navTo("software");
    const goPlugins = () => navTo("plugins");
    const onRefresh = () => { void handleRefreshFromServer(); };
    const toggleSettings = () => {
      clearSidebarFocus();
      setSelected(null);
      if (view === "settings") { setView(settingsReturnRef.current); }
      else { settingsReturnRef.current = view; setView("settings"); }
    };
    window.addEventListener("nav-home", goHome);
    window.addEventListener("nav-library", goLibrary);
    window.addEventListener("nav-downloads", goDownloads);
    window.addEventListener("nav-personal", goPersonal);
    // The coach tour navigates to these screens before highlighting their button.
    window.addEventListener("nav-software", goSoftware);
    window.addEventListener("nav-plugins", goPlugins);
    const replayTour = () => setOnboarded(false);   // Settings → "הצג מדריך התחלה"
    window.addEventListener("nav-refresh", onRefresh);
    window.addEventListener("nav-settings", toggleSettings);
    window.addEventListener("open-onboarding", replayTour);
    return () => {
      window.removeEventListener("nav-home", goHome);
      window.removeEventListener("nav-library", goLibrary);
      window.removeEventListener("nav-downloads", goDownloads);
      window.removeEventListener("nav-personal", goPersonal);
      window.removeEventListener("nav-software", goSoftware);
      window.removeEventListener("nav-plugins", goPlugins);
      window.removeEventListener("nav-refresh", onRefresh);
      window.removeEventListener("nav-settings", toggleSettings);
      window.removeEventListener("open-onboarding", replayTour);
    };
  }, [view]);

  // ── X-click interceptor ─────────────────────────────────────
  // Fires when the user clicks the window's X (or anything that
  // triggers a page unload - Alt+F4, taskbar close, etc.). The first
  // time this happens we cancel the close, pop the modal, and let the
  // user pick. After they pick we set closingRef and call
  // window.close() so the next unload sails through.
  //
  // If a preference is already persisted ("minimize" | "close") we
  // don't intercept - Eel's close_callback handles the action in
  // Python according to the saved choice.
  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (closingRef.current) return;                 // already resolved → let it through
      if (!launcherPrefs) return;                     // prefs still loading → don't block
      if (launcherPrefs.closeBehavior) return;        // user already picked → silent path
      // No saved choice - prompt. preventDefault keeps the window alive
      // long enough for the modal to render and the user to choose.
      e.preventDefault();
      // returnValue is the legacy contract - must be assigned to a non-
      // empty string for Chrome to honour the cancel intent.
      e.returnValue = "";
      setShowCloseModal(true);
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [launcherPrefs]);

  // Modal's resolve handler - persists the choice (if requested),
  // then attempts to close the window so Eel's close_callback can
  // honour the choice on the Python side.
  const handleCloseModalResolved = useCallback((next: LauncherPrefs) => {
    setLauncherPrefs(next);
    setShowCloseModal(false);
    closingRef.current = true;
    // Give React a tick to commit the unmount before triggering the
    // real close - otherwise the modal can flash on its way out.
    setTimeout(() => {
      try { window.close(); } catch { /* swallowed - close_callback handles fallbacks */ }
    }, 60);
  }, []);

  useEffect(() => {
    let attempts = 0;
    const tryBoot = async () => {
      if (api.ready()) {
        // Pull catalog + launcher prefs in parallel so the
        // first-launch close-behavior modal can show as soon as we
        // know the user hasn't picked yet.
        await Promise.all([
          refresh(),
          api.getLauncherPrefs().then(setLauncherPrefs).catch((e) => console.error("[prefs]", e)),
          // Warm the software library at boot (parallel with games) so the
          // "תוכנות" view has its data ready before the user ever opens it.
          api.getAllSoftware().then((s) => setSoftware(Array.isArray(s) ? s : [])).catch(() => {}),
        ]);
        return;
      }
      if (++attempts > 50) { setLoading(false); return; }
      setTimeout(tryBoot, 100);
    };
    tryBoot();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Global mod-install terminal hook ─────────────────────────
  // GameDetailPanel subscribes to onModProgress for the live progress
  // bar, but if the user navigates AWAY mid-install the panel unmounts
  // and the "done" / "error" tick has no listener - the next time they
  // open the panel it shows stale state until something else refreshes
  // the games list. A second subscription here, never unmounted, calls
  // refresh() on terminal events so the panel-less side-effect lives
  // regardless of which view is on screen.
  useEffect(() => {
    return onModProgress((p) => {
      if (p.phase === "done" || p.phase === "error") {
        void refresh();
      }
    });
  }, [refresh]);

  // ── SWR push subscription ────────────────────────────────────
  // Python's background refresh (swr_cache.py) fires cache_refreshed("games", …)
  // whenever the server returns different data than what we last cached.
  // Merge those quiet updates into existing state - no spinner, no re-mount.
  // Effectively gives the app live updates without polling.
  useEffect(() => {
    const w = window as unknown as { __eelCacheHandlers?: ((k: string, d: unknown, s: string | null) => void)[] };
    if (!w.__eelCacheHandlers) w.__eelCacheHandlers = [];
    const handler = (kind: string, data: unknown, _subKey: string | null) => {
      if (!Array.isArray(data)) return;
      // The SWR layer pushes BOTH catalogs - keep software live too, so the
      // "תוכנות" view never has to re-fetch on mount.
      if (kind === "software") { setSoftware(data as Game[]); return; }
      if (kind !== "games") return;
      const fresh = data as Game[];
      setGames(fresh);
      setSelected((prev) =>
        prev ? (fresh.find((g) => g.id === prev.id) ?? prev) : null,
      );
    };
    w.__eelCacheHandlers.push(handler);
    return () => {
      if (!w.__eelCacheHandlers) return;
      const i = w.__eelCacheHandlers.indexOf(handler);
      if (i >= 0) w.__eelCacheHandlers.splice(i, 1);
    };
  }, []);

  // Floating status toast - top-center for ~4 sec, then fades.
  const reportStatus = useCallback((text: string, warn = false) => {
    setStatus(warn ? `⚠ ${text}` : text);
    setTimeout(() => setStatus(undefined), 4500);
  }, []);

  // ── Update NOTIFICATIONS (never silent) ──────────────────────
  // Silent auto-update was removed by request. Instead, ONCE per session after
  // the catalog loads, check for available translation-mod updates (getModUpdates
  // now covers BOTH download mods AND native appliers - SM2/WD2/GTAV). If any
  // exist, surface them TWO ways: a CLICKABLE in-app banner (routes straight to
  // the update - the game's panel for a single update, else the Downloads screen)
  // + a native Windows notification. Nothing installs on its own. Errors stay
  // silent (best-effort); the beta-channel gate is applied server-side.
  const updateNoticeRanRef = useRef(false);
  useEffect(() => {
    if (updateNoticeRanRef.current || loading || games.length === 0) return;
    updateNoticeRanRef.current = true;
    (async () => {
      try {
        const updates = await api.getModUpdates().catch(() => []);
        if (updates.length === 0) return;
        const titles = updates.map((u) => u.titleEn);
        const list = titles.join(", ");
        const body =
          updates.length === 1
            ? `עדכון תרגום זמין ל${list}.`
            : `עדכוני תרגום זמינים ל-${updates.length} משחקים: ${list}.`;
        // Clickable in-app banner…
        setUpdateNotice({ body, gameId: updates.length === 1 ? updates[0].gameId : undefined });
        // …and the notifications bell. pushNotif → "notif-pop" → the handler below
        // fires the ONE native Windows toast (mute-respecting). Do NOT also fire a
        // direct api.notifyOs here: that double-toasted AND ignored the mute state.
        pushNotif({
          id: "mod-updates:" + updates.map((u) => u.gameId).sort().join(","),
          title: "עדכון תרגום זמין",
          body,
          kind: "update",
          link: updates.length === 1 ? updates[0].gameId : undefined,
        });
      } catch { /* best-effort */ }
    })();
  }, [loading, games.length]);

  // ── Single-session takeover notice ───────────────────────────
  // useLauncherAuth (inside the provider subtree) dispatches "auth-takeover"
  // when this install is signed out because the same account signed in on
  // another device. Surface it via the existing top-center toast. (A native
  // Windows notification is fired from the provider in parallel.)
  useEffect(() => {
    const onTakeover = (e: Event) => {
      const msg = (e as CustomEvent).detail?.message;
      if (typeof msg === "string" && msg) reportStatus(msg, true);
    };
    window.addEventListener("auth-takeover", onTakeover);
    return () => window.removeEventListener("auth-takeover", onTakeover);
  }, [reportStatus]);

  // A NEW admin/system notification (not muted) "pops": the notifications store
  // dispatches "notif-pop" → the dedicated <NotifToast> glass card renders the
  // visual, and here we ALSO fire a native Windows notification. When muted the
  // store never dispatches (only the red bell dot appears).
  useEffect(() => {
    const onPop = (e: Event) => {
      const d = (e as CustomEvent).detail as { title?: string; body?: string } | undefined;
      const title = d?.title?.trim();
      if (!title) return;
      void api.notifyOs(title, d?.body || "").catch(() => {});
    };
    window.addEventListener("notif-pop", onPop);
    return () => window.removeEventListener("notif-pop", onPop);
  }, []);

  // Re-pull the catalog when the launcher regains focus (throttled ~45s) so
  // admin changes - notably which games are FEATURED on the home carousel -
  // appear shortly after returning to the app, without a manual refresh. The
  // featured list is derived live from `games`, so a fresh catalog updates it.
  useEffect(() => {
    let last = 0;
    const maybe = () => {
      const now = Date.now();
      if (now - last < 45_000) return;
      last = now;
      void refresh();
    };
    const onVis = () => { if (!document.hidden) maybe(); };
    window.addEventListener("focus", maybe);
    document.addEventListener("visibilitychange", onVis);
    return () => {
      window.removeEventListener("focus", maybe);
      document.removeEventListener("visibilitychange", onVis);
    };
  }, [refresh]);

  // Controller "B" / Backspace → contextual back: close an open game →
  // else return to home from a sub-view.
  useEffect(() => {
    const onBack = () => {
      if (selected) { setSelected(null); return; }
      if (view !== "home") setView("home");
    };
    window.addEventListener("nav-back", onBack);
    return () => window.removeEventListener("nav-back", onBack);
  }, [selected, view]);

  const handleNavigate = (key: NavKey) => {
    // If the controller had jumped focus into the sidebar, picking an item ends
    // that mode → restore the previous sidebar display mode (focus follows the
    // new view, so we don't restore the remembered focus here).
    if (sidebarFocusRef.current) {
      window.dispatchEvent(new CustomEvent("sidebarmode", { detail: sidebarFocusRef.current.prevMode }));
      sidebarFocusRef.current = null;
    }
    setSelected(null);
    setSelectedSoft(null);
    setView(key);
  };
  const handleOpenGame = (g: Game) => {
    setSelected(g);
    setView("games");
  };
  // Click the update banner → go straight to where the user can update: the
  // specific game's panel (single update) or the Downloads/Updates screen.
  const handleUpdateNoticeClick = () => {
    const n = updateNotice;
    setUpdateNotice(null);
    if (n?.gameId) {
      const g = games.find((x) => x.id === n.gameId);
      if (g) { setSelected(g); setView("games"); return; }
    }
    setSelected(null);
    setView("downloads");
  };

  // ── Deep link (hebrewhub://game/<id>) ────────────────────────
  // The Python shell opens the launcher straight to a game when the website's
  // "פתח בתוכנה" button fires the protocol. The id arrives either in the
  // initial URL hash (#game=<id>, cold start) or via a 'deep-link-game' window
  // event (an already-running instance re-invoked with the URI). We stash a
  // pending id and open it once the catalog has loaded.
  const [pendingGameId, setPendingGameId] = useState<string | null>(() => {
    const m = /[#&?]game=([^&]+)/.exec(window.location.hash || window.location.search);
    return m ? decodeURIComponent(m[1]) : null;
  });
  useEffect(() => {
    const onDeep = (e: Event) => {
      const id = (e as CustomEvent).detail?.id;
      if (typeof id === "string" && id) setPendingGameId(id);
    };
    window.addEventListener("deep-link-game", onDeep);
    return () => window.removeEventListener("deep-link-game", onDeep);
  }, []);
  useEffect(() => {
    if (!pendingGameId) return;
    // Search BOTH catalogs. A deep link carries a plain catalog id and the site
    // does not say which list it belongs to - a SOFTWARE title (is_software,
    // e.g. borderless-gaming) lives only in `software`, so searching `games`
    // alone silently dropped the id and the launcher just opened on whatever
    // view it was already showing.
    const g = games.find((x) => x.id === pendingGameId);
    if (g) { setSelectedSoft(null); setSelected(g); setView("games"); setPendingGameId(null); return; }
    const s = software.find((x) => x.id === pendingGameId);
    if (s) { setSelected(null); setSelectedSoft(s); setView("software"); setPendingGameId(null); return; }
    // Not found YET - keep the id pending while either catalog is still empty
    // (they load independently), and only give up once both have arrived.
    if (games.length > 0 && software.length > 0) setPendingGameId(null);
  }, [pendingGameId, games, software]);

  const gamesCountHe = (n: number) =>
    n === 0 ? "לא נמצאו משחקים"
    : n === 1 ? "משחק אחד"
    : `${n} משחקים`;

  const handleScanDeep = useCallback(async () => {
    reportStatus("סורק את כל הכוננים ברקע - זה עשוי לקחת דקה. הרשימה תתעדכן אוטומטית כשתסתיים.");
    try {
      const r = await api.scanDeep();
      if (r && Array.isArray(r.games)) {
        // Legacy Eel path: full payload returned synchronously.
        setGames(r.games);
        reportStatus(`הסריקה הושלמה - ${gamesCountHe(r.found)}`);
      }
      // Qt path: {ok, pending:true} - the scan runs off-thread (so mouse-wheel
      // scroll stays responsive), and the fresh games arrive via
      // cache_refreshed("games"), merged by the subscriber above.
    } catch (e) {
      reportStatus(String(e), true);
    }
  }, [reportStatus]);

  // Sidebar refresh button - fire-and-forget on the Qt shell. The
  // backend dispatches the 3 HTTP fetches to QThreadPool and returns
  // immediately with {ok, pending:true}; games/news/updates flow back
  // progressively via cache_refreshed signals (existing subscriber
  // above auto-merges them into state), and the per-source toast
  // labels arrive via onCatalogRefreshComplete (effect below). On the
  // legacy Eel build the slot blocks until completion and returns the
  // payload synchronously - we apply it inline as a fallback so both
  // transports still work from one button.
  const handleRefreshFromServer = useCallback(async () => {
    reportStatus("מרענן מהשרת...");
    try {
      const r = await api.refreshCatalog();
      if (r && Array.isArray(r.games)) {
        // Legacy Eel path: full payload arrived. Apply directly + toast now.
        setGames(r.games);
        setRefreshNonce((n) => n + 1);
        const fromRemote =
          r.catalog_source === "remote" ||
          r.news_source    === "remote";
        reportStatus(fromRemote ? "עודכן מהשרת" : "אין חיבור - נטען מקבצים מקומיים", !fromRemote);
      }
      // A REAL refresh = server catalog/news/updates (above) AND the local app
      // state: re-fetch getAllGames() so on-disk install detection + mod states
      // are current, and bump refreshNonce so every view's live data (progress,
      // updates, versions) re-runs. On the Qt shell the catalog itself streams
      // back via cache_refreshed; this makes the button ALSO reflect install/mod
      // changes on disk immediately, not just the server data.
      await refresh();
      setRefreshNonce((n) => n + 1);
      // Qt-shell path: {ok, pending:true}. Server-source toast lives in
      // the onCatalogRefreshComplete effect below.
    } catch (e) {
      reportStatus(String(e), true);
    }
  }, [reportStatus, refresh]);

  // Qt-shell fire-and-forget completion. Updates the toast + bumps
  // refreshNonce so per-view effects (live progress, etc.) re-run.
  // Games themselves arrive via the cache_refreshed handler above
  // before this fires.
  useEffect(() => {
    return onCatalogRefreshComplete((catalog, news, _updates) => {
      setRefreshNonce((n) => n + 1);
      const fromRemote = catalog === "remote" || news === "remote";
      reportStatus(fromRemote ? "עודכן מהשרת" : "אין חיבור - נטען מקבצים מקומיים", !fromRemote);
    });
  }, [reportStatus]);

  // Key for the view-transition wrapper: changes on every screen switch (view,
  // an open game, or an open software) so the wrapper REMOUNTS and replays the
  // `.view-transition` entrance animation - a smooth fade+rise between menus.
  const contentKey = loading
    ? "loading"
    : selected     ? `g:${selected.id}`
    : selectedSoft ? `s:${selectedSoft.id}`
    : `v:${view}`;

  return (
    <ErrorBoundary>
    <SiteConfigProvider>
    <LauncherAuthProvider>
    <AccentProvider>
    <div className="h-screen w-screen text-slate-200 overflow-hidden relative">
      <VideoBackground />
      {/* Per-game ambient tint - the selected game "paints the environment".
          Sits above the video, below the app shell. */}
      <div className="accent-bg" aria-hidden />

      {/* The custom frameless title bar is now a NATIVE Qt widget (drawn OUTSIDE
          the web view, above it), so it stays responsive even while the web UI
          is busy loading. The web content therefore fills its whole viewport
          (h-full) and no longer renders a React title bar. */}

      <div className="h-full w-full flex p-4 gap-3 no-select relative"
           style={{ zIndex: 10 }}>
        <main className="flex-1 min-w-0 glass rounded-3xl overflow-hidden">
          <div key={contentKey} className="h-full view-transition">
          {loading ? (
            <LoadingShade />
          ) : selected ? (
            <GameDetailPanel
              key={selected.id}
              game={selected}
              onBack={() => setSelected(null)}
              onRefresh={refresh}
              reportStatus={reportStatus}
              refreshNonce={refreshNonce}
            />
          ) : selectedSoft ? (
            // Software uses the EXACT same detail panel as a game - same hero
            // banner, same settings rail, same behaviour (only the accent differs).
            <GameDetailPanel
              key={selectedSoft.id}
              game={selectedSoft}
              onBack={() => setSelectedSoft(null)}
              onRefresh={refresh}
              reportStatus={reportStatus}
              refreshNonce={refreshNonce}
            />
          ) : view === "home" ? (
            <HomeView
              games={games}
              software={software}
              onOpenGame={handleOpenGame}
              onOpenLibrary={() => setView("games")}
              onBigLaunch={() => enterBigLaunch((m) => reportStatus(m, true))}
              refreshNonce={refreshNonce}
            />
          ) : view === "games" ? (
            <LibraryView
              games={games}
              onOpenGame={handleOpenGame}
              onScanDeep={handleScanDeep}
            />
          ) : view === "software" ? (
            <AppsView
              software={software}
              reportStatus={reportStatus}
              refreshNonce={refreshNonce}
              onOpenSoftware={(sw) => setSelectedSoft(sw)}
              onNavigateToDownloads={() => setView("downloads")}
            />
          ) : view === "downloads" ? (
            <DownloadsView refreshNonce={refreshNonce} />
          ) : view === "plugins" ? (
            <PluginsSettings
              reportStatus={reportStatus}
              onOpenPlugin={(id) => setView(`plugin:${id}` as NavKey)}
            />
          ) : view.startsWith("plugin:") ? (
            <PluginPage
              pluginId={view.slice("plugin:".length)}
              reportStatus={reportStatus}
              onOpenManager={() => setView("plugins")}
            />
          ) : view === "personal" ? (
            <PersonalAreaView
              refreshNonce={refreshNonce}
              onBack={() => setView("home")}
              webProfileUrl="https://hebrew-translation-hub.com/profile"
            />
          ) : (
            <SettingsView
              games={games}
              reportStatus={reportStatus}
              onRefresh={refresh}
              onRefreshFromServer={handleRefreshFromServer}
              version={appVersion}
              launcherPrefs={launcherPrefs}
              onPrefsChange={setLauncherPrefs}
            />
          )}
          </div>
        </main>

        <Sidebar
          current={view}
          onNavigate={handleNavigate}
          onRefresh={handleRefreshFromServer}
          version={appVersion}
        />
      </div>

      {/* App messages: a ROOT-LEVEL full-width `fixed` bar that FLEX-CENTERS the
          card. Centering is done by flexbox (justify-center) on this full-width
          wrapper - NOT by a `-translate-x-1/2` transform on the card, because the
          card's `animate-fade-in` sets its own `transform: translateY(...)` which
          OVERRIDES a translateX(-50%) and was leaving the card shifted right of
          centre (the real reason it never looked centred). No ancestor has a
          transform, so the wrapper spans the true window width → the card sits
          dead-centre of the WINDOW regardless of the sidebar width or window size.
          `top-12` (48px) clears the 36px custom title bar. The wrapper is click-
          through; only the card itself is interactive. */}
      {status && (
        <div className="fixed top-12 inset-x-0 z-[120] flex justify-center px-4 pointer-events-none">
          {/* dir="rtl" is REQUIRED: at root level the toast no longer inherits a
              view's RTL context, so a mixed string like "גודל הטקסט: 95%" would
              lay the number out on the wrong side ("escaped"). */}
          <div dir="rtl" className="glass-strong rounded-2xl px-6 py-3 text-sm text-center max-w-[85vw]
                          text-slate-100 animate-fade-in pointer-events-auto
                          shadow-[0_20px_60px_-15px_rgba(0,0,0,0.85)] ring-1 ring-white/10">
            {status}
          </div>
        </div>
      )}
      {updateNotice && (
        <div className="fixed top-12 inset-x-0 z-[118] flex justify-center px-4 pointer-events-none">
          <div dir="rtl" className="flex items-center gap-3
                          glass-strong rounded-2xl pl-3 pr-4 py-2.5 animate-fade-in max-w-[90vw] pointer-events-auto
                          ring-1 ring-emerald-400/40
                          shadow-[0_12px_36px_-10px_rgba(0,0,0,0.8)]">
            <button
              type="button"
              onClick={handleUpdateNoticeClick}
              className="flex items-center gap-2 text-sm font-bold text-emerald-200 hover:text-emerald-100"
            >
              <span className="text-base">⬆</span>
              <span>{updateNotice.body} <span className="underline">לחץ לעדכון</span></span>
            </button>
            <button
              type="button"
              onClick={() => setUpdateNotice(null)}
              className="text-slate-400 hover:text-slate-200 text-lg leading-none px-1"
              aria-label="סגור"
            >
              ×
            </button>
          </div>
        </div>
      )}

      {/* Close-behavior modal - NEVER on startup. Only renders when
          the beforeunload interceptor has caught an X-click AND no
          saved preference exists yet. handleCloseModalResolved
          persists the choice + calls window.close() so Eel's
          close_callback executes the action. */}
      {showCloseModal && (
        <CloseBehaviorModal onResolved={handleCloseModalResolved} />
      )}

      {/* New-notification pop-ups (top-right glass cards). */}
      <NotifToast />

      {/* The IN-APP loading splash (the only one - no native floating window).
          Holds until the first screen's images are decoded (`ready`), so nothing
          "pops in" after it lifts; a maxMs cap guarantees it never strands. */}
      {!splashDone && <SplashScreen onDone={() => setSplashDone(true)} ready={imagesReady} minMs={700} maxMs={14000} />}

      {/* Self-update: brand the OLD window's last frame while the installer runs
          + the app exits, so there is no frozen panel / blank before it reopens. */}
      {updating && (
        <div className="fixed inset-0 z-[300] grid place-items-center" style={{ background: "#050510" }}>
          <SplashScreen onDone={() => {}} ready={false} minMs={999999} maxMs={999999} />
          <div className="absolute bottom-24 text-[#9db4ff] text-sm">מתקין עדכון… התוכנה תיפתח מחדש</div>
        </div>
      )}
      {splashDone && !onboarded && <CoachTour onClose={finishOnboarding} />}

      {/* First launch after an update → the new version's notes (this version
          ONLY; the full history is in Settings → יומן שינויים). Never shown
          together with the first-run tour. */}
      {splashDone && onboarded && showWhatsNew && <WhatsNewModal onClose={closeWhatsNew} />}

      {/* Frameless-window edge resize handles (only when the custom title bar is on). */}
      {frameless && <ResizeHandles />}

    </div>
    </AccentProvider>
    </LauncherAuthProvider>
    </SiteConfigProvider>
    </ErrorBoundary>
  );
}

function LoadingShade() {
  return (
    <div className="h-full grid place-items-center">
      <div className="text-center">
        <div className="w-12 h-12 border-2 border-brand-yellow border-t-transparent
                        rounded-full animate-spin mb-4 mx-auto" />
        <div className="text-slate-300">טוען משחקים...</div>
      </div>
    </div>
  );
}

