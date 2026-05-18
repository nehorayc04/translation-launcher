// Root shell: video bg + sidebar + main content. No bottom bar — the previous
// heavy chrome row was replaced with a transient status toast and a tiny
// muted version label in the corner.
import { useCallback, useEffect, useState } from "react";
import VideoBackground   from "./components/VideoBackground";
import Sidebar           from "./components/Sidebar";
import type { NavKey }   from "./components/Sidebar";
import HomeView          from "./views/HomeView";
import LibraryView       from "./views/LibraryView";
import SettingsView      from "./views/SettingsView";
import DownloadsView     from "./views/DownloadsView";
import GameDetailPanel   from "./views/GameDetailPanel";
import { api }           from "./lib/eel";
import type { Game }     from "./lib/types";
import { SiteConfigProvider } from "./lib/useSiteConfig";
import { LauncherAuthProvider } from "./lib/useLauncherAuth";

export const APP_VERSION = "v1.0.4";

export default function App() {
  const [view,     setView]     = useState<NavKey>("home");
  const [games,    setGames]    = useState<Game[]>([]);
  const [selected, setSelected] = useState<Game | null>(null);
  const [status,   setStatus]   = useState<string | undefined>(undefined);
  const [loading,  setLoading]  = useState(true);
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

  useEffect(() => {
    let attempts = 0;
    const tryBoot = async () => {
      if (api.ready()) { await refresh(); return; }
      if (++attempts > 50) { setLoading(false); return; }
      setTimeout(tryBoot, 100);
    };
    tryBoot();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
    setView(key);
  };
  const handleOpenGame = (g: Game) => {
    setSelected(g);
    setView("library");
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

  // Sidebar refresh button — forces the Python backend to bypass its 30s
  // in-process cache and re-fetch games + news + updates from the server.
  const handleRefreshFromServer = useCallback(async () => {
    reportStatus("מרענן מהשרת...");
    try {
      const r = await api.refreshCatalog();
      setGames(r.games);
      setRefreshNonce((n) => n + 1);   // re-run fetch effects in child views
      const fromRemote =
        r.catalog_source === "remote" ||
        r.news_source    === "remote";
      reportStatus(fromRemote ? "עודכן מהשרת" : "אין חיבור — נטען מקבצים מקומיים", !fromRemote);
    } catch (e) {
      reportStatus(String(e), true);
    }
  }, [reportStatus]);

  return (
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
          ) : view === "home" ? (
            <HomeView
              games={games}
              onOpenGame={handleOpenGame}
              onOpenLibrary={() => setView("library")}
              refreshNonce={refreshNonce}
            />
          ) : view === "library" ? (
            <LibraryView
              games={games}
              onOpenGame={handleOpenGame}
              onScanDeep={handleScanDeep}
            />
          ) : view === "downloads" ? (
            <DownloadsView refreshNonce={refreshNonce} />
          ) : (
            <SettingsView
              games={games}
              reportStatus={reportStatus}
              onRefresh={refresh}
              version={APP_VERSION}
            />
          )}
        </main>

        <Sidebar
          current={view}
          onNavigate={handleNavigate}
          onRefresh={handleRefreshFromServer}
        />
      </div>

      {/* Floating status toast — top-center, replaces the heavy bottom bar */}
      {status && (
        <div className="fixed top-6 left-1/2 -translate-x-1/2 z-50
                        glass-strong rounded-full px-5 py-2 text-sm
                        text-slate-100 animate-fade-in
                        shadow-[0_10px_30px_-10px_rgba(0,0,0,0.7)]">
          {status}
        </div>
      )}

      {/* Tiny corner version — non-obtrusive */}
      <div className="fixed bottom-2 right-3 text-[10px] text-slate-500/60
                      font-mono pointer-events-none select-none"
           style={{ zIndex: 5 }}>
        {APP_VERSION}
      </div>
    </div>
    </LauncherAuthProvider>
    </SiteConfigProvider>
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
