// Root shell: video bg + sidebar + main content. No bottom bar — the previous
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
import SoftwareDetailPanel from "./views/SoftwareDetailPanel";
import CloseBehaviorModal from "./components/CloseBehaviorModal";
import { api, onModProgress, onCatalogRefreshComplete } from "./lib/eel";
import type { Game, Software, LauncherPrefs } from "./lib/types";
import { SiteConfigProvider } from "./lib/useSiteConfig";
import { LauncherAuthProvider } from "./lib/useLauncherAuth";

export const APP_VERSION = "v1.1.0";

export default function App() {
  const [view,     setView]     = useState<NavKey>("home");
  const [games,    setGames]    = useState<Game[]>([]);
  const [selected, setSelected] = useState<Game | null>(null);
  /** Currently-opened software card (parallel to `selected` for games).
   *  When non-null we render <SoftwareDetailPanel/> in place of the
   *  software grid, matching how a selected game replaces the library. */
  const [selectedSoftware, setSelectedSoftware] = useState<Software | null>(null);
  const [status,   setStatus]   = useState<string | undefined>(undefined);
  const [loading,  setLoading]  = useState(true);
  /** Launcher window/lifecycle prefs. `null` while we haven't loaded
   *  yet (don't show the modal during the brief pre-load window). */
  const [launcherPrefs, setLauncherPrefs] = useState<LauncherPrefs | null>(null);
  /** True while the close-behavior modal is open — driven exclusively
   *  by the X-click `beforeunload` interceptor below. NEVER shown on
   *  app startup. */
  const [showCloseModal, setShowCloseModal] = useState(false);
  /** Latch set once the user has resolved the close modal so the
   *  re-fired beforeunload (from window.close()) doesn't loop. */
  const closingRef = useRef(false);
  // Bumped every time the sidebar refresh button completes successfully.
  // Views that fetch their own slice of data (NewsSection, DownloadsView)
  // include this in their effect deps so they re-pull instead of waiting
  // for the next unmount/remount.
  const [refreshNonce, setRefreshNonce] = useState(0);

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

  // ── X-click interceptor ─────────────────────────────────────
  // Fires when the user clicks the window's X (or anything that
  // triggers a page unload — Alt+F4, taskbar close, etc.). The first
  // time this happens we cancel the close, pop the modal, and let the
  // user pick. After they pick we set closingRef and call
  // window.close() so the next unload sails through.
  //
  // If a preference is already persisted ("minimize" | "close") we
  // don't intercept — Eel's close_callback handles the action in
  // Python according to the saved choice.
  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (closingRef.current) return;                 // already resolved → let it through
      if (!launcherPrefs) return;                     // prefs still loading → don't block
      if (launcherPrefs.closeBehavior) return;        // user already picked → silent path
      // No saved choice — prompt. preventDefault keeps the window alive
      // long enough for the modal to render and the user to choose.
      e.preventDefault();
      // returnValue is the legacy contract — must be assigned to a non-
      // empty string for Chrome to honour the cancel intent.
      e.returnValue = "";
      setShowCloseModal(true);
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [launcherPrefs]);

  // Modal's resolve handler — persists the choice (if requested),
  // then attempts to close the window so Eel's close_callback can
  // honour the choice on the Python side.
  const handleCloseModalResolved = useCallback((next: LauncherPrefs) => {
    setLauncherPrefs(next);
    setShowCloseModal(false);
    closingRef.current = true;
    // Give React a tick to commit the unmount before triggering the
    // real close — otherwise the modal can flash on its way out.
    setTimeout(() => {
      try { window.close(); } catch { /* swallowed — close_callback handles fallbacks */ }
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
  // and the "done" / "error" tick has no listener — the next time they
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
  // Merge those quiet updates into existing state — no spinner, no re-mount.
  // Effectively gives the app live updates without polling.
  useEffect(() => {
    const w = window as unknown as { __eelCacheHandlers?: ((k: string, d: unknown, s: string | null) => void)[] };
    if (!w.__eelCacheHandlers) w.__eelCacheHandlers = [];
    const handler = (kind: string, data: unknown, _subKey: string | null) => {
      if (kind !== "games" || !Array.isArray(data)) return;
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

  // Floating status toast — top-center for ~4 sec, then fades.
  const reportStatus = useCallback((text: string, warn = false) => {
    setStatus(warn ? `⚠ ${text}` : text);
    setTimeout(() => setStatus(undefined), 4500);
  }, []);

  const handleNavigate = (key: NavKey) => {
    setSelected(null);
    setSelectedSoftware(null);
    setView(key);
  };
  const handleOpenGame = (g: Game) => {
    setSelected(g);
    setView("games");
  };
  const handleOpenSoftware = (s: Software) => {
    setSelectedSoftware(s);
    setView("apps");
  };

  const gamesCountHe = (n: number) =>
    n === 0 ? "לא נמצאו משחקים"
    : n === 1 ? "משחק אחד"
    : `${n} משחקים`;

  const handleScanDeep = useCallback(async () => {
    reportStatus("סורק את כל הכוננים — זה עשוי לקחת דקה...");
    try {
      const r = await api.scanDeep();
      setGames(r.games);
      reportStatus(`הסריקה הושלמה — ${gamesCountHe(r.found)}`);
    } catch (e) {
      reportStatus(String(e), true);
    }
  }, [reportStatus]);

  // Sidebar refresh button — fire-and-forget on the Qt shell. The
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
        reportStatus(fromRemote ? "עודכן מהשרת" : "אין חיבור — נטען מקבצים מקומיים", !fromRemote);
      }
      // Qt-shell path: {ok, pending:true}. Toast + nonce-bump live in
      // the onCatalogRefreshComplete effect below.
    } catch (e) {
      reportStatus(String(e), true);
    }
  }, [reportStatus]);

  // Qt-shell fire-and-forget completion. Updates the toast + bumps
  // refreshNonce so per-view effects (live progress, etc.) re-run.
  // Games themselves arrive via the cache_refreshed handler above
  // before this fires.
  useEffect(() => {
    return onCatalogRefreshComplete((catalog, news, _updates) => {
      setRefreshNonce((n) => n + 1);
      const fromRemote = catalog === "remote" || news === "remote";
      reportStatus(fromRemote ? "עודכן מהשרת" : "אין חיבור — נטען מקבצים מקומיים", !fromRemote);
    });
  }, [reportStatus]);

  return (
    <ErrorBoundary>
    <SiteConfigProvider>
    <LauncherAuthProvider>
    <div className="h-screen w-screen text-slate-200 overflow-hidden relative">
      <VideoBackground />

      <div className="h-full w-full flex p-4 gap-3 no-select relative"
           style={{ zIndex: 10 }}>
        <main className="flex-1 min-w-0 glass rounded-3xl overflow-hidden">
          {loading ? (
            <LoadingShade />
          ) : selected ? (
            <GameDetailPanel
              game={selected}
              onBack={() => setSelected(null)}
              onRefresh={refresh}
              reportStatus={reportStatus}
              refreshNonce={refreshNonce}
            />
          ) : selectedSoftware ? (
            <SoftwareDetailPanel
              software={selectedSoftware}
              onBack={() => setSelectedSoftware(null)}
              reportStatus={reportStatus}
              onNavigateToDownloads={() => {
                setSelectedSoftware(null);
                setView("downloads");
              }}
            />
          ) : view === "home" ? (
            <HomeView
              games={games}
              onOpenGame={handleOpenGame}
              onOpenLibrary={() => setView("games")}
              refreshNonce={refreshNonce}
            />
          ) : view === "games" ? (
            <LibraryView
              games={games}
              onOpenGame={handleOpenGame}
              onScanDeep={handleScanDeep}
            />
          ) : view === "apps" ? (
            <AppsView
              reportStatus={reportStatus}
              refreshNonce={refreshNonce}
              onOpenSoftware={handleOpenSoftware}
              onNavigateToDownloads={() => setView("downloads")}
            />
          ) : view === "downloads" ? (
            <DownloadsView refreshNonce={refreshNonce} />
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
              version={APP_VERSION}
              launcherPrefs={launcherPrefs}
              onPrefsChange={setLauncherPrefs}
            />
          )}
        </main>

        <Sidebar
          current={view}
          onNavigate={handleNavigate}
          onRefresh={handleRefreshFromServer}
          version={APP_VERSION}
        />
      </div>

      {/* Close-behavior modal — NEVER on startup. Only renders when
          the beforeunload interceptor has caught an X-click AND no
          saved preference exists yet. handleCloseModalResolved
          persists the choice + calls window.close() so Eel's
          close_callback executes the action. */}
      {showCloseModal && (
        <CloseBehaviorModal onResolved={handleCloseModalResolved} />
      )}

      {/* Floating status toast — top-center, replaces the heavy bottom bar */}
      {status && (
        <div className="fixed top-6 left-1/2 -translate-x-1/2 z-50
                        glass-strong rounded-full px-5 py-2 text-sm
                        text-slate-100 animate-fade-in
                        shadow-[0_10px_30px_-10px_rgba(0,0,0,0.7)]">
          {status}
        </div>
      )}

    </div>
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
