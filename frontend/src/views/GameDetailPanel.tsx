// "Big Picture" mode - page-2 layout: action buttons stacked top-RIGHT, the
// descriptive text + title/badges in the CENTER, the large cover on the LEFT,
// and ALL settings (path / language / cache / beta / stats) in a full-width
// COLLAPSIBLE drawer at the bottom. Rendered inside the main content area
// (NOT a separate window).
import { showsTranslationProgress, type Game } from "../lib/types";
import { accentFor, availabilityLabel, modStateLabel } from "../lib/theme";
import { resolveCoverUrl, resolveAssetUrl } from "../lib/coverUrl";
import SmartImage from "../components/SmartImage";
import LiquidWave from "../components/LiquidWave";
import { formatVersion } from "../lib/formatVersion";
import { StageBadge } from "../components/StageBadge";
import ChangelogModal from "../components/ChangelogModal";
import { IconOptBtnPurchase, IconOptBtnRemoveTranslation, IconOptBtnDisableTranslation, IconOptBtnAlreadyPaidRefresh, IconOptBtnClearCache, IconOptBtnClearPath, IconOptHdrSettings, IconOptEmptyComingSoon, IconOptBtnSavePath, IconOptBtnOpenFolder, IconOptBtnDownloadInstall, IconOptBtnInstallTranslation, IconOptHdrVersionHistory, IconAppGamedetailVersionToggle, IconAppGamedetailPlay, IconAppGamedetailLock, IconOptHdrGameLanguage } from "../components/UiIcons";
import { api, onModProgress } from "../lib/eel";
import type { GameModState, GameLanguageState, SpiderMan2State, WatchDogs2State, GtavState, GowrState, VirtualDjModState, ModProgress } from "../lib/eel";
import { resolvePhaseHeadline } from "../lib/phaseLabels";
import { useSmoothProgress } from "../lib/useSmoothProgress";
import { useLiveGameProgress } from "../lib/useLiveGameProgress";
import { useSetAccent } from "../lib/useAccent";
import SegmentedControl from "../components/SegmentedControl";
import { useCallback, useEffect, useState } from "react";

// The settings drawer's open/closed state is remembered GLOBALLY (one flag for
// every game, not per-game) and defaults to OPEN. So collapsing it on one game
// keeps it collapsed the next time any game is opened, and vice-versa.
const DRAWER_KEY = "pth.gameSettingsOpen";
function readDrawerOpen(): boolean {
  try { const v = localStorage.getItem(DRAWER_KEY); return v === null ? true : v === "1"; }
  catch { return true; }
}
function writeDrawerOpen(open: boolean): void {
  try { localStorage.setItem(DRAWER_KEY, open ? "1" : "0"); } catch { /* ignore */ }
}

interface Props {
  game: Game;
  onBack:    () => void;
  onRefresh: () => Promise<void>;
  reportStatus: (text: string, warn?: boolean) => void;
  /** Bumped by App's sidebar refresh - re-pulls live progress on demand. */
  refreshNonce?: number;
}

export default function GameDetailPanel({ game, onBack, onRefresh, reportStatus, refreshNonce = 0 }: Props) {
  const accent = accentFor(game.theme_key);
  const avail  = availabilityLabel(game.availability);
  const mod    = modStateLabel(game.mod_state);
  // Software (VirtualDJ …) reuses this panel 1:1 - only the wording changes.
  const isSoftware = !!game.isSoftware;
  const noun       = isSoftware ? "התוכנה" : "המשחק";

  // Paint the whole app background with this game's accent while the
  // detail panel is open; restore the neutral default on close.
  useSetAccent(accent);

  // "What's new" changelog modal.
  const [showChangelog, setShowChangelog] = useState(false);

  const [pathInput, setPathInput] = useState(game.exe_path ?? game.install_path ?? "");
  const [busy, setBusy]           = useState<string | null>(null);
  // Settings drawer - open by default; the open/closed choice persists GLOBALLY
  // (see readDrawerOpen) so it's the same across every game and every reopen.
  const [settingsOpen, setSettingsOpen] = useState(readDrawerOpen);

  // Live per-game progress - same /api/progress feed the home dashboard
  // uses. While the first fetch is in flight (`loaded === false`) we
  // render at 0% so the OLD static `game.progress` doesn't briefly
  // flash before the real number arrives.
  const { snap: liveProgress, loaded: liveLoaded } = useLiveGameProgress(game.id, {
    enabled:      showsTranslationProgress(game.availability),
    refreshNonce,
  });

  const wrap = async (key: string, fn: () => Promise<unknown>) => {
    setBusy(key);
    try {
      await fn();
      await onRefresh();
    } finally {
      setBusy(null);
    }
  };

  const handleLaunch = () =>
    wrap("launch", async () => {
      const r = await api.launchGame(game.id);
      reportStatus(r.ok ? `הופעל: ${r.exe}` : `שגיאה: ${r.error ?? "לא ידוע"}`, !r.ok);
    });

  const handleSavePath = () =>
    wrap("path", async () => {
      const r = await api.setCustomPath(game.id, pathInput);
      setPathInput(r.exe_path ?? r.install_path ?? pathInput);
      reportStatus(`נתיב נשמר: ${r.exe_path ?? r.install_path ?? "-"}`);
    });

  // Floating native "choose file" dialog → pick the game's .exe → save it.
  const handlePickExe = () =>
    wrap("path", async () => {
      const r = await api.pickExe(
        isSoftware ? "בחר את קובץ ה-EXE של התוכנה" : "בחר את קובץ ה-EXE של המשחק",
        pathInput,
      );
      if (!r.ok || !r.path) {
        if (r.error && r.error !== "no-native-dialog")
          reportStatus(`בחירת קובץ נכשלה: ${r.error}`, true);
        return;
      }
      const saved = await api.setCustomPath(game.id, r.path);
      setPathInput(saved.exe_path ?? saved.install_path ?? r.path);
      reportStatus(`נתיב נשמר: ${saved.exe_path ?? saved.install_path ?? r.path}`);
    });

  const handleClearPath = () =>
    wrap("path", async () => {
      await api.clearCustomPath(game.id);
      setPathInput("");
      reportStatus("נתיב נמחק");
    });

  const handleOpenFolder = () => {
    if (!game.install_path) return;
    void api.openFolder(game.install_path).then((r) => {
      if (!r.ok) reportStatus(`לא הצלחתי לפתוח: ${r.error}`, true);
    });
  };

  // Hebrew agreement for file count
  const filesHe = (n: number | undefined) =>
    n === 1 ? "קובץ אחד" : `${n ?? 0} קבצים`;

  // Cyberpunk only: append a hint about the locale flip / restore that
  // happens automatically alongside the file operation. Other titles
  // get an undefined `language` payload and the suffix collapses away.
  const langSuffix = (r: { language?: { ok: boolean; previous?: Record<string, string> } | null }, mode: "enable" | "restore") => {
    const l = r.language;
    if (!l) return "";
    if (mode === "enable") {
      return l.ok ? " · השפה הוגדרה לערבית (סלוט עברי)" : " · עדכון שפה אוטומטי נכשל";
    }
    const prev = l.previous?.Text ?? l.previous?.Subtitles;
    return l.ok
      ? (prev ? ` · השפה שוחזרה ל-${prev}` : " · השפה שוחזרה")
      : " · שחזור שפה אוטומטי נכשל";
  };

  const handleEnable    = () => wrap("mod", async () => {
    const r = await api.enableMod(game.id);
    reportStatus(r.ok ? `התרגום הופעל (${filesHe(r.count)})${langSuffix(r, "enable")}` : `שגיאה: ${r.error}`, !r.ok);
  });
  const handleDisable   = () => wrap("mod", async () => {
    const r = await api.disableMod(game.id);
    reportStatus(r.ok ? `התרגום הושבת (${filesHe(r.count)})${langSuffix(r, "restore")}` : `שגיאה: ${r.error}`, !r.ok);
  });
  const handleUninstall = () => wrap("mod", async () => {
    if (!confirm("האם להסיר לצמיתות את התרגום העברי מתיקיית המשחק?")) return;
    const r = await api.uninstallMod(game.id);
    reportStatus(r.ok ? `התרגום הוסר (${filesHe(r.count)})${langSuffix(r, "restore")}` : `שגיאה: ${r.error}`, !r.ok);
  });

  // ── Download-distributed mod (Cyberpunk 2077) ──────────────────
  // A game whose backend GameConfig carries a `mod_slug` is fetched
  // through the Cloudflare Worker proxy and managed by game_mod.py.
  // `gm` is null until the first getGameModState resolves; gm.modSlug
  // being non-empty is what flips this panel to the download-backed CTA.
  const [gm, setGm]                   = useState<GameModState | null>(null);
  const [gmBusy, setGmBusy]           = useState(false);
  const [gmProgress, setGmProgress]   = useState<ModProgress | null>(null);
  // Smooth, always-flowing fill for the shared mod-install bar: while an
  // apply/verify stage sits on one percentage for a while (heaviest on the
  // multi-stage Witcher 3 applier), the shown value keeps creeping so it never
  // looks frozen. Applies to ALL mods (shared progress block below).
  const smoothInstallPct = useSmoothProgress(
    Math.min(100, Math.max(0, gmProgress?.pct ?? 0)),
    gmProgress?.phase === "apply" || gmProgress?.phase === "verify",
  );
  const [purchasePending, setPurchasePending] = useState(false);
  /** Burst-poll window after a known purchase trigger. While > 0 we
   *  re-fetch ownership every ~3s so the BUY → INSTALL CTA flips within
   *  seconds of a successful payment - without waiting for the 60s
   *  catalog poller or a manual view-change. */
  const [pollUntil, setPollUntil]     = useState<number>(0);

  const refreshGm = useCallback(async () => {
    try { setGm(await api.getGameModState(game.id)); }
    catch { setGm(null); }
  }, [game.id]);
  useEffect(() => { void refreshGm(); }, [refreshGm]);

  // Is a newer version of THIS game's translation mod available? A separate
  // (network) manifest check so getGameModState stays instant. Only runs for
  // an installed download-distributed mod; re-checked when install state flips.
  const [modUpd, setModUpd] = useState<{ updateAvailable?: boolean; latestVersion?: string | null;
                                       updateSource?: string } | null>(null);
  const refreshModUpd = useCallback(async () => {
    if (!gm?.modSlug || !gm.installed) { setModUpd(null); return; }
    try { setModUpd(await api.checkGameModUpdate(game.id)); }
    catch { setModUpd(null); }
  }, [game.id, gm?.modSlug, gm?.installed]);
  useEffect(() => { void refreshModUpd(); }, [refreshModUpd]);

  // ── Spider-Man 2 native applier (TOC patch - no Overstrike) ────────
  const isSm2 = game.id === "spiderman2";
  const [sm2, setSm2]       = useState<SpiderMan2State | null>(null);
  const [sm2Busy, setSm2Busy] = useState(false);
  const refreshSm2 = useCallback(async () => {
    if (!isSm2) { setSm2(null); return; }
    try { setSm2(await api.getSpiderman2ModState()); }
    catch { setSm2(null); }
  }, [isSm2]);
  useEffect(() => { void refreshSm2(); }, [refreshSm2]);

  const handleSm2Install = async () => {
    setSm2Busy(true);
    setGmProgress({ phase: "apply", pct: 0, detail: "מתחיל בהתקנה…" });
    try {
      const r = await api.installSpiderman2Mod();
      if (!r.ok) { setSm2Busy(false); setGmProgress(null); reportStatus(`שגיאה: ${r.error}`, true); }
    } catch (e) {
      setSm2Busy(false); setGmProgress(null); reportStatus(`שגיאה: ${String(e)}`, true);
    }
  };
  const handleSm2Remove = async () => {
    if (!confirm("להסיר את התרגום? ה-toc המקורי של המשחק ישוחזר וקבצי המוד יימחקו.")) return;
    setSm2Busy(true);
    try {
      const r = await api.removeSpiderman2Mod();
      setSm2(r.state);
      reportStatus(r.ok ? "התרגום הוסר והמשחק שוחזר" : `שגיאה: ${r.error}`, !r.ok);
      await onRefresh();
    } finally {
      setSm2Busy(false);
    }
  };

  // ── Watch Dogs 2 native applier (FAT5 fat-redirect - no Overstrike) ──────
  const isWd2 = game.id === "watchdogs2";
  const [wd2, setWd2]       = useState<WatchDogs2State | null>(null);
  const [wd2Busy, setWd2Busy] = useState(false);
  const refreshWd2 = useCallback(async () => {
    if (!isWd2) { setWd2(null); return; }
    try { setWd2(await api.getWatchdogs2ModState()); }
    catch { setWd2(null); }
  }, [isWd2]);
  useEffect(() => { void refreshWd2(); }, [refreshWd2]);

  const handleWd2Install = async () => {
    setWd2Busy(true);
    setGmProgress({ phase: "apply", pct: 0, detail: "מתחיל בהתקנה…" });
    try {
      const r = await api.installWatchdogs2Mod();
      if (!r.ok) { setWd2Busy(false); setGmProgress(null); reportStatus(`שגיאה: ${r.error}`, true); }
    } catch (e) {
      setWd2Busy(false); setGmProgress(null); reportStatus(`שגיאה: ${String(e)}`, true);
    }
  };
  const handleWd2Remove = async () => {
    if (!confirm("להסיר את התרגום? קבצי המשחק המקוריים ישוחזרו.")) return;
    setWd2Busy(true);
    try {
      const r = await api.removeWatchdogs2Mod();
      setWd2(r.state);
      reportStatus(r.ok ? "התרגום הוסר והמשחק שוחזר" : `שגיאה: ${r.error}`, !r.ok);
      await onRefresh();
    } finally {
      setWd2Busy(false);
    }
  };

  // ── God of War: Ragnarök native applier (single-file WAD swap) ──────────
  // Backs up the original localization WAD (outside the game) + atomically swaps
  // in the bundled Hebrew build; reversible. Install is async (worker) with the
  // terminal onModProgress tick resetting gowrBusy; remove is a direct restore.
  // GoWR + Hogwarts Legacy + The Witcher 3 + A Plague Tale: Requiem all share ONE
  // "single-flow native download applier" path (fetch the mod from the Worker +
  // apply, backup outside the game, reversible). An api dispatch by game.id covers
  // all four; the `gowr`/`gowrBusy` state + every reference below are shared, so
  // `isGowr` here means "is a single-flow native applier" (name kept to avoid churn).
  // `gated` = respect the server `game.availability` before offering install
  // (the 3 download-only games that aren't published yet → show "בקרוב").
  // GoWR ships a BUNDLED offline payload and is already published, so it is NOT
  // gated - its install must show even offline / before the live catalog loads
  // (its own state.available already guards the bundled-payload check).
  const NATIVE_DL_API: Record<string, {
    get: () => Promise<GowrState>;
    install: () => Promise<{ ok: boolean; error?: string; started?: boolean }>;
    remove: () => Promise<{ ok: boolean; error?: string; state: GowrState }>;
    note: string;
    gated: boolean;
  }> = {
    gowragnarok: { get: api.getGowrModState, install: api.installGowrMod, remove: api.removeGowrMod, gated: false,
      note: "התרגום פעיל. במשחק: הגדרות ← שפת טקסט (Text Language) = العربية (ערבית). שפת הדיבור יכולה להישאר כרצונך." },
    hogwarts: { get: api.getHogwartsModState, install: api.installHogwartsMod, remove: api.removeHogwartsMod, gated: true,
      note: "התרגום פעיל. במשחק: הגדרות ← שפת טקסט (Text Language) ← בחרו English כדי לראות את התרגום." },
    witcher3: { get: api.getWitcher3ModState, install: api.installWitcher3Mod, remove: api.removeWitcher3Mod, gated: true,
      note: "התרגום פעיל. במשחק: Options ← Language ← Text = Hebrew (עברית) - הבורר כבר מציג 'Hebrew'. שפת הדיבור נשארת כרצונך." },
    "plague-tale-requiem": { get: api.getPlagueTaleModState, install: api.installPlagueTaleMod, remove: api.removePlagueTaleMod, gated: true,
      note: "התרגום פעיל. במשחק: Options ← Text Language = العربية (ערבית). שפת הדיבור נשארת באנגלית." },
    // SOFTWARE (VirtualDJ) - same single-flow native applier, adapted from its
    // {cached, enabled, version} state to the shared GowrState shape.
    virtualdj: {
      get: async (): Promise<GowrState> => {
        const st = await api.getVirtualdjModState();
        return {
          hasPath: true, installed: st.enabled, available: true, installPath: null,
          version: st.version, owned: st.owned, priceCents: st.priceCents,
        };
      },
      install: () => api.applyVirtualdjTranslation(),
      remove: async () => {
        const r  = await api.setVirtualdjModEnabled(false);
        const st = await api.getVirtualdjModState()
          .catch(() => ({ cached: false, enabled: false, version: null } as VirtualDjModState));
        return {
          ok: r.ok,
          error: r.error,
          state: {
            hasPath: true, installed: st.enabled, available: true, installPath: null,
            version: st.version, owned: st.owned, priceCents: st.priceCents,
          } as GowrState,
        };
      },
      gated: false,
      note: 'התרגום פעיל. ב-VirtualDJ: Options ← Language ← "עברית" - כל הממשק יוצג בעברית מלאה.',
    },
    // SOFTWARE (Borderless Gaming) - free. Installs the added he-IL locale AND
    // patches the compiled effect cache, all inside %APPDATA%.
    "borderless-gaming": {
      get: async (): Promise<GowrState> => {
        const st = await api.getBorderlessGamingModState();
        return {
          hasPath: true, installed: st.enabled, available: true, installPath: null,
          version: st.version, owned: st.owned, priceCents: st.priceCents,
        };
      },
      install: () => api.applyBorderlessGamingTranslation(),
      remove: async () => {
        const r  = await api.setBorderlessGamingModEnabled(false);
        const st = await api.getBorderlessGamingModState()
          .catch(() => ({ cached: false, enabled: false, version: null } as VirtualDjModState));
        return {
          ok: r.ok,
          error: r.error,
          state: {
            hasPath: true, installed: st.enabled, available: true, installPath: null,
            version: st.version, owned: st.owned, priceCents: st.priceCents,
          } as GowrState,
        };
      },
      gated: false,
      note: "התרגום פעיל - הממשק ועורך האפקטים בעברית. אם עורך האפקטים עדיין באנגלית, הפעילו את התוכנה פעם אחת, סגרו אותה, ולחצו שוב על התקנה.",
    },
    // SOFTWARE (SignalRGB) - ₪15. Downloads + applies the exe .qm patch, the
    // Macroscripts, every device-plugin label, and the registry locale.
    signalrgb: {
      get: async (): Promise<GowrState> => {
        const st = await api.getSignalrgbModState();
        return {
          hasPath: true, installed: st.enabled, available: true, installPath: null,
          version: st.version, owned: st.owned, priceCents: st.priceCents,
        };
      },
      install: () => api.applySignalrgbTranslation(),
      remove: async () => {
        const r  = await api.setSignalrgbModEnabled(false);
        const st = await api.getSignalrgbModState()
          .catch(() => ({ cached: false, enabled: false, version: null } as VirtualDjModState));
        return {
          ok: r.ok,
          error: r.error,
          state: {
            hasPath: true, installed: st.enabled, available: true, installPath: null,
            version: st.version, owned: st.owned, priceCents: st.priceCents,
          } as GowrState,
        };
      },
      gated: false,
      note: "התרגום פעיל. הפעילו מחדש את SignalRGB - כל הממשק, עמוד המאקרו ועמודי ההתקנים בעברית מלאה.",
    },
  };
  const nativeDl = NATIVE_DL_API[game.id];
  const isGowr = !!nativeDl;
  const [gowr, setGowr]         = useState<GowrState | null>(null);
  const [gowrBusy, setGowrBusy] = useState(false);
  const refreshGowr = useCallback(async () => {
    const nd = NATIVE_DL_API[game.id];
    if (!nd) { setGowr(null); return; }
    try { setGowr(await nd.get()); }
    catch { setGowr(null); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [game.id]);
  useEffect(() => { void refreshGowr(); }, [refreshGowr]);

  const handleGowrInstall = async () => {
    if (!nativeDl) return;
    setGowrBusy(true);
    setGmProgress({ phase: "apply", pct: 0, detail: "מתחיל בהתקנה…" });
    try {
      const r = await nativeDl.install();
      if (!r.ok) { setGowrBusy(false); setGmProgress(null); reportStatus(`שגיאה: ${r.error}`, true); return; }
      // An applier that ran INLINE (no background worker → `started` unset) has
      // already finished by the time it answers, and no terminal "done" tick is
      // coming - so close the bar here. Otherwise the worker's done/error tick
      // does it (see the onModProgress effect).
      if (!r.started) {
        setGowrBusy(false);
        setGmProgress(null);
        await refreshGowr();
        await refreshNativeUpd();
        await onRefresh();
        reportStatus("התרגום הותקן והופעל");
      }
    } catch (e) {
      setGowrBusy(false); setGmProgress(null); reportStatus(`שגיאה: ${String(e)}`, true);
    }
  };
  const handleGowrRemove = async () => {
    if (!nativeDl) return;
    if (!confirm(isSoftware
      ? "להסיר את התרגום? קובץ השפה המקורי של התוכנה ישוחזר."
      : "להסיר את התרגום? קובץ המשחק המקורי ישוחזר.")) return;
    setGowrBusy(true);
    try {
      const r = await nativeDl.remove();
      setGowr(r.state);
      reportStatus(
        r.ok ? (isSoftware ? "התרגום הוסר והתוכנה שוחזרה" : "התרגום הוסר והמשחק שוחזר")
             : `שגיאה: ${r.error}`,
        !r.ok,
      );
      await onRefresh();
    } finally {
      setGowrBusy(false);
      setGmProgress(null);
    }
  };

  // ── GTA V native OpenIV-free RPF7 applier - install + remove are BOTH async
  // (multi-GB read-modify-write), progress-streamed; the terminal onModProgress
  // tick resets gtavBusy + refreshes the state. ───────────────────────────────
  const isGtav = game.id === "gtav";
  const [gtav, setGtav]       = useState<GtavState | null>(null);
  const [gtavBusy, setGtavBusy] = useState(false);
  const refreshGtav = useCallback(async () => {
    if (!isGtav) { setGtav(null); return; }
    try { setGtav(await api.getGtavModState()); }
    catch { setGtav(null); }
  }, [isGtav]);
  useEffect(() => { void refreshGtav(); }, [refreshGtav]);

  // ── Native-applier update check (SM2/WD2/GTAV) ─────────────────────
  // The same backend check_game_mod_update now also reports updates for native
  // appliers (SM2 vs its GitHub manifest; WD2/GTAV vs the bundled version). So
  // a native mod gets the SAME "⬆ עדכן תרגום" button + chip as a download mod.
  const [nativeUpd, setNativeUpd] = useState<{ updateAvailable?: boolean; latestVersion?: string | null;
                                             updateSource?: string } | null>(null);
  const nativeInstalled =
    (isSm2 && !!sm2?.installed) || (isWd2 && !!wd2?.installed) || (isGtav && !!gtav?.installed)
    || (isGowr && !!gowr?.installed);
  const refreshNativeUpd = useCallback(async () => {
    if (!nativeInstalled) { setNativeUpd(null); return; }
    try { setNativeUpd(await api.checkGameModUpdate(game.id)); }
    catch { setNativeUpd(null); }
  }, [game.id, nativeInstalled]);
  useEffect(() => { void refreshNativeUpd(); }, [refreshNativeUpd]);

  // The version actually installed on disk (state.json), per game type, and
  // whether ANY newer version is available - drives the "גרסה מותקנת" stat row
  // + its highlight.
  const installedVersion =
    isSm2  ? (sm2?.version ?? null)
    : isWd2  ? (wd2?.version ?? null)
    : isGtav ? (gtav?.version ?? null)
    : isGowr ? (gowr?.version ?? null)
    : (gm?.installed ? (gm?.version ?? null) : null);
  const anyUpdateAvailable = !!(modUpd?.updateAvailable || nativeUpd?.updateAvailable);
  // An update whose payload is ALREADY on disk (carried by a pre-built offline
  // package) applies with no internet - say so, otherwise the user cannot tell
  // it apart from one that needs a download.
  const updIsOffline = (nativeUpd?.updateSource || modUpd?.updateSource) === "offline";
  const updVerb      = updIsOffline ? "עדכון אופליין" : "עדכן תרגום";

  const handleGtavInstall = async () => {
    setGtavBusy(true);
    setGmProgress({ phase: "apply", pct: 0, detail: "מתחיל בהתקנה… (עלול לקחת מספר דקות)" });
    try {
      const r = await api.installGtavMod();
      if (!r.ok) { setGtavBusy(false); setGmProgress(null); reportStatus(`שגיאה: ${r.error}`, true); }
    } catch (e) {
      setGtavBusy(false); setGmProgress(null); reportStatus(`שגיאה: ${String(e)}`, true);
    }
  };
  const handleGtavRemove = async () => {
    if (!confirm("להסיר את התרגום? הטקסט יחזור לאנגלית המקורית והמודים האחרים שלך יישמרו.")) return;
    setGtavBusy(true);
    setGmProgress({ phase: "apply", pct: 0, detail: "מתחיל בהסרה…" });
    try {
      const r = await api.removeGtavMod();
      if (!r.ok) { setGtavBusy(false); setGmProgress(null); reportStatus(`שגיאה: ${r.error}`, true); }
    } catch (e) {
      setGtavBusy(false); setGmProgress(null); reportStatus(`שגיאה: ${String(e)}`, true);
    }
  };
  // Separate, explicitly-warned full restore from the install-time snapshot.
  const handleGtavRestoreBackup = async () => {
    if (!confirm("לשחזר את הגיבוי המלא מלפני ההתקנה?\n\n⚠ פעולה זו תדרוס כל שינוי שעשית בקבצים האלה מאז ההתקנה (כולל מודים חדשים). לרוב עדיף להשתמש ב\"הסרת התרגום\" הרגילה, ששומרת את שאר המודים שלך.")) return;
    setGtavBusy(true);
    setGmProgress({ phase: "apply", pct: 0, detail: "משחזר גיבוי מלא…" });
    try {
      const r = await api.restoreGtavBackup();
      if (!r.ok) { setGtavBusy(false); setGmProgress(null); reportStatus(`שגיאה: ${r.error}`, true); }
    } catch (e) {
      setGtavBusy(false); setGmProgress(null); reportStatus(`שגיאה: ${String(e)}`, true);
    }
  };
  const openOpenIV = () => { try { window.open("https://openiv.com/", "_blank"); } catch { /* */ } };

  // ── In-game language switch (auto / Hebrew[Arabic] / English) ──────
  // Independent of the file-level mod: it flips the game's own text-language
  // setting (a registry DWORD for Spider-Man 2, UserSettings.json for CP2077)
  // so the user can pick Hebrew or English without editing anything by hand.
  const [lang, setLang]       = useState<GameLanguageState | null>(null);
  const [langBusy, setLangBusy] = useState(false);
  const refreshLang = useCallback(async () => {
    try { setLang(await api.getGameLanguage(game.id)); }
    catch { setLang(null); }
  }, [game.id]);
  useEffect(() => { void refreshLang(); }, [refreshLang]);
  // Re-pull when the mod's install state flips - 'auto' resolves off it.
  useEffect(() => { if (gm) void refreshLang(); }, [gm?.installed, refreshLang]);

  const langName = (n?: string | null) =>
    n === "hebrew" ? "עברית (ערבית)" : n === "english" ? "אנגלית"
      : n === "other" ? "שפה אחרת" : "-";

  // Friendly Hebrew for the backend's machine-readable language errors -
  // most commonly the game's settings file not existing yet (CP2077 writes
  // UserSettings.json only after its first launch).
  const langErr = (e?: string) => {
    if (!e) return "לא ידוע";
    if (e.includes("not-purchased")) return "יש לרכוש את התרגום כדי לשנות שפה";
    // The game is OPEN: it holds its settings file (or we caught it mid-write).
    // Telling the user to "run the game once" here was the exact opposite of
    // what helps - and the game rewrites this file when it closes anyway, so a
    // change made now would be overwritten regardless.
    if (e.includes("settings-file-locked"))
      return `סגור את ${noun} ונסה שוב - ההגדרות נעולות בזמן שהוא פתוח (וגם נדרסות בסגירה)`;
    if (e.includes("settings-file-missing") || e.includes("vars-not-found"))
      return `לא נמצאו הגדרות שפה - הפעל את ${noun} פעם אחת, סגור, ואז נסה שוב`;
    if (e.includes("settings-file-unreadable")) return "קובץ ההגדרות של המשחק לא קריא";
    if (e.includes("language-tag-not-found")) return "לא נמצאה הגדרת שפה בקובץ ההגדרות";
    if (e.includes("registry") || e.includes("settings-write-failed"))
      return "כתיבה להגדרות נכשלה";
    return e;
  };

  const handleSetLang = (mode: "auto" | "hebrew" | "english") => {
    if (langBusy) return;
    setLangBusy(true);
    void api.setGameLanguage(game.id, mode)
      .then((r) => {
        if (r.ok) reportStatus(`שפת ${noun} עודכנה ל${langName(r.applied)} - ייכנס לתוקף בהפעלה הבאה`);
        else reportStatus(`שגיאה בעדכון שפה: ${langErr(r.error)}`, true);
      })
      .catch((e) => reportStatus(`שגיאה: ${String(e)}`, true))
      .finally(() => { setLangBusy(false); void refreshLang(); });
  };

  const handleRestoreLang = () => {
    if (langBusy) return;
    setLangBusy(true);
    void api.restoreGameLanguage(game.id)
      .then((r) => {
        if (r.ok) reportStatus(`השפה שוחזרה ל${langName(r.restored)} (כפי שהייתה לפני המוד)`);
        else reportStatus(`שחזור השפה נכשל: ${langErr(r.error)}`, true);
      })
      .catch((e) => reportStatus(`שגיאה: ${String(e)}`, true))
      .finally(() => { setLangBusy(false); void refreshLang(); });
  };

  // Burst poller - runs only when pollUntil > now. Stops as soon as
  // ownership flips true OR the window closes. Window is short (~90s)
  // and the interval is generous (3s) so we don't hammer the DB.
  useEffect(() => {
    if (pollUntil <= Date.now()) return;
    let cancelled = false;
    const onOwned = async () => {
      // Defensive double-check: confirm the purchase row is actually in the
      // user's purchases list. If not, the launcher caught a stale / sandbox /
      // cross-account positive - warn instead of silently flipping to "install".
      try {
        const p = await api.authGetMyPurchases();
        const found = p.rows.some((r) => r.game_id === game.id);
        reportStatus(found ? "✓ הרכישה אומתה - אפשר להתקין"
                           : "הרכישה זוהתה בשרת אך לא ברשימה האישית - נסה שוב בעוד דקה.", !found);
      } catch { /* swallow - UI already shows owned */ }
      setPollUntil(0);
      setPurchasePending(false);
    };
    const tick = async () => {
      if (cancelled) return;
      try {
        if (isGtav) {
          const s = await api.getGtavModState();
          if (cancelled) return;
          setGtav(s);
          if (s.owned) await onOwned();
        } else if (nativeDl) {
          // Paid single-flow applier (VirtualDJ) - its own state carries owned.
          const s = await nativeDl.get();
          if (cancelled) return;
          setGowr(s);
          if (s.owned) await onOwned();
        } else {
          const s = await api.getGameModState(game.id);
          if (cancelled) return;
          setGm(s);
          if (s.owned) await onOwned();
        }
      } catch {
        /* keep polling */
      }
    };
    const id = window.setInterval(tick, 3000);
    void tick();   // run one immediate so the first refresh isn't delayed by 3s
    return () => { cancelled = true; window.clearInterval(id); };
  }, [pollUntil, game.id, reportStatus]);

  // Stop the burst once the window expires.
  useEffect(() => {
    if (pollUntil <= 0) return;
    const remaining = pollUntil - Date.now();
    if (remaining <= 0) { setPollUntil(0); return; }
    const t = window.setTimeout(() => {
      setPollUntil(0);
      const stillUnowned = isGtav ? (gtav && !gtav.owned)
        : isGowr ? (gowr && (gowr.priceCents ?? 0) > 0 && !gowr.owned)
        : (gm && !gm.owned);
      if (stillUnowned) {
        reportStatus("לא נמצאה רכישה. אם השלמת את התשלום, נסה שוב בעוד דקה.", true);
      }
    }, remaining);
    return () => window.clearTimeout(t);
  }, [pollUntil, gm, gtav, gowr, isGtav, isGowr, reportStatus]);

  /** Kick the burst poller so the next 90s of refresh ticks happen
   *  automatically without the user clicking "already paid - refresh"
   *  repeatedly. Also used right after `openPurchasePage()` to catch a
   *  PayPal success the moment it lands. */
  const startPurchaseBurst = useCallback(() => {
    setPollUntil(Date.now() + 90_000);
  }, []);

  // Stream download/verify/install progress from the Python worker.
  // The worker emits a terminal "done" / "error" tick when the
  // background install thread finishes - that's what clears the bar
  // and refreshes the mod state (the install no longer blocks an eel
  // RPC, so the panel can't just await a result).
  useEffect(() => {
    return onModProgress((p) => {
      if (p.phase === "done") {
        setGmProgress(null);
        setGmBusy(false);
        setSm2Busy(false);
        setWd2Busy(false);
        setGtavBusy(false);
        setGowrBusy(false);
        const refreshAll = () => {
          void refreshGm();
          void refreshModUpd();
          void refreshSm2();
          void refreshWd2();
          void refreshGtav();
          void refreshGowr();
          void refreshNativeUpd();
          void onRefresh();
        };
        refreshAll();
        // Self-heal a race: the worker writes state.json THEN fires this "done"
        // tick, but on a slow disk the state read here can still catch the old
        // file, leaving a just-installed native mod (GoWR/SM2/WD2/GTAV) showing
        // "not installed". A second refresh a moment later always converges.
        window.setTimeout(refreshAll, 1500);
        reportStatus(p.detail || "התרגום הותקן והופעל");
        if (game.id === "signalrgb") {
          // The Hebrew .qm is read at SignalRGB startup, so a restart is
          // required for the translation to take effect. Offer to do it now.
          window.setTimeout(() => {
            if (window.confirm("SignalRGB צריך הפעלה מחדש כדי שהתרגום ייכנס לתוקף. להפעיל מחדש עכשיו?")) {
              void api.restartSignalrgb().then((r) => {
                if (r?.ok) reportStatus("SignalRGB מופעל מחדש בעברית…");
                else reportStatus(r?.error || "לא ניתן היה להפעיל מחדש את SignalRGB - סגרו ופתחו אותו ידנית.", true);
              });
            }
          }, 300);
        }
      } else if (p.phase === "error") {
        setGmProgress(null);
        setGmBusy(false);
        setSm2Busy(false);
        setWd2Busy(false);
        setGtavBusy(false);
        setGowrBusy(false);
        void refreshGm();
        void refreshSm2();
        void refreshWd2();
        void refreshGtav();
        void refreshGowr();
        reportStatus(`שגיאה: ${p.detail}`, true);
      } else {
        setGmProgress(p);
      }
    });
  }, [game.id, refreshGm, refreshModUpd, refreshSm2, refreshWd2, refreshGtav, refreshGowr, refreshNativeUpd, onRefresh, reportStatus]);

  // The purchase CTA is a SYSTEM action, not a themed one. It used to take the
  // per-game accent on native appliers and `bg-brand-yellow` on download mods -
  // so on a yellow-accented title (Anno / CP2077) it came out the SAME yellow as
  // "הפעל" and read as a different button from the cyan one every other game
  // showed. One fixed tone everywhere, distinct from the yellow primary.
  const BUY_BTN =
    "inline-flex items-center justify-center gap-1.5 font-bold px-6 py-3 rounded-xl " +
    "transition disabled:opacity-50 bg-sky-400 hover:bg-sky-300 text-brand-ink";

  // Match BuyModal.formatPrice + the actual charge: whole shekels show as an
  // integer, a fractional price shows agorot (Math.round would advertise a price
  // 0.50₪ off from what PayPal charges).
  const ils = (cents: number) => {
    const amt = cents / 100;
    return `${amt % 1 === 0 ? amt.toFixed(0) : amt.toFixed(2)} ₪`;
  };

  // ── PURCHASE LOCK (games AND software) ───────────────────────────────────
  // A PAID title that the user has not bought exposes no mod controls at all:
  // no language switch, no beta channel, no cache wipe. Only "רכישה" does
  // anything. The price/ownership come from whichever applier drives this
  // title; a free one reports priceCents 0 / owned true, so `locked` is false.
  const titlePrice =
    isGtav ? (gtav?.priceCents ?? 0)
    : isGowr ? (gowr?.priceCents ?? 0)
    : (gm?.priceCents ?? 0);
  const titleOwned =
    isGtav ? !!gtav?.owned
    : isGowr ? (gowr?.owned ?? true)
    : (gm?.owned ?? true);
  const locked = titlePrice > 0 && !titleOwned;

  // ── ONE PAINT, NOT THREE ─────────────────────────────────────────────────
  // Every region used to appear the moment its OWN fetch landed, so opening a
  // game visibly assembled itself: basics → then the action buttons → then the
  // language switch → then the version history. `hydrated` waits for the whole
  // first round of LOCAL (bridge) state so those land together; the version
  // history is a REMOTE call to the website and keeps its own reserved skeleton
  // instead of holding the panel back. The timeout is a safety net so a failed
  // fetch (which leaves its state null) can never strand the panel on skeletons.
  const nativeStateReady =
    isSm2 ? sm2 !== null
    : isWd2 ? wd2 !== null
    : isGtav ? gtav !== null
    : isGowr ? gowr !== null
    : true;
  const [hydrateDeadline, setHydrateDeadline] = useState(false);
  useEffect(() => {
    setHydrateDeadline(false);
    const t = window.setTimeout(() => setHydrateDeadline(true), 2500);
    return () => window.clearTimeout(t);
  }, [game.id]);
  const hydrated = (gm !== null && lang !== null && nativeStateReady) || hydrateDeadline;

  const handleGmInstall = async () => {
    setGmBusy(true);
    setGmProgress({ phase: "download", pct: 0, detail: "מתחיל בהורדה…" });
    try {
      const r = await api.downloadAndInstallGameMod(game.id);
      // r resolves immediately - the install runs on a background
      // thread. On a start failure (no path / not owned) clear here;
      // otherwise progress + the terminal tick arrive via onModProgress.
      if (!r.ok) {
        setGmBusy(false);
        setGmProgress(null);
        reportStatus(`שגיאה: ${r.error}`, true);
      }
    } catch (e) {
      setGmBusy(false);
      setGmProgress(null);
      reportStatus(`שגיאה: ${String(e)}`, true);
    }
  };

  const handleGmToggle = async (installed: boolean) => {
    setGmBusy(true);
    try {
      const r = await api.setGameModInstalled(game.id, installed);
      setGm(r.state);
      reportStatus(
        r.ok ? (installed ? "התרגום הותקן מחדש" : "התרגום הושבת - הקבצים הועברו למטמון")
             : `שגיאה: ${r.error}`,
        !r.ok,
      );
      await onRefresh();
    } finally {
      setGmBusy(false);
    }
  };

  const handleGmClearCache = async () => {
    if (!confirm(
      `לנקות את מטמון התרגום? התרגום יוסר מתיקיית ${noun} ומהמחשב - ` +
      "התקנה מחדש תדרוש הורדה חוזרת."
    )) return;
    setGmBusy(true);
    try {
      const r = await api.clearGameModCache(game.id);
      setGm(r.state);
      reportStatus(r.ok ? "המטמון נוקה - התרגום הוסר מהמחשב" : `שגיאה: ${r.error}`, !r.ok);
      await onRefresh();
    } finally {
      setGmBusy(false);
    }
  };

  // Clear-cache for the native appliers (SM2/WD2/GTAV/GoWR/HL/W3/PT/VirtualDJ) -
  // the consistency counterpart to handleGmClearCache for download mods: revert
  // from the game (if installed) then wipe the launcher download cache.
  const handleNativeClearCache = async () => {
    if (!confirm(
      `לנקות את מטמון התרגום? התרגום יוסר מ${noun} ומהמחשב - ` +
      "התקנה מחדש תדרוש הורדה חוזרת."
    )) return;
    setGowrBusy(true);
    try {
      const r = await api.clearNativeModCache(game.id);
      reportStatus(r.ok ? "המטמון נוקה - התרגום הוסר מהמחשב" : `שגיאה: ${r.error}`, !r.ok);
      await Promise.all([refreshSm2(), refreshWd2(), refreshGtav(), refreshGowr()]);
      await onRefresh();
    } finally {
      setGowrBusy(false);
    }
  };

  const handlePurchase = async () => {
    // Payment now happens ON THE WEBSITE (not in-app). Open the game's
    // purchase page in the user's default browser; they complete PayPal
    // there, and since both surfaces share the same user_purchases table,
    // the purchase syncs back here. We optimistically mark a pending
    // purchase and start the burst poller so the CTA flips to INSTALL as
    // soon as the shared table reflects the completed order.
    try {
      const r = await api.openPurchasePage(game.id);
      if (!r.ok) {
        reportStatus(r.error ?? "לא ניתן לפתוח את דף הרכישה", true);
        return;
      }
      setPurchasePending(true);
      startPurchaseBurst();
      reportStatus("נפתח דף הרכישה בדפדפן - לאחר התשלום חזור לכאן והמוד יסונכרן");
    } catch (e) {
      reportStatus(String(e), true);
    }
  };

  // ── Action buttons (PLAY + the per-game translation branch) ─────────
  // Extracted so they can sit in the top-right stack of the page-2 layout.
  const actionButtons = (
    <>
      <button
        disabled={!game.is_installed || busy !== null}
        onClick={handleLaunch}
        className="inline-flex items-center justify-center gap-1.5 bg-brand-yellow hover:bg-yellow-300 text-brand-ink font-extrabold
                   px-8 py-3 rounded-xl text-lg transition
                   disabled:opacity-40 disabled:cursor-not-allowed
                   shadow-[0_10px_30px_-10px_rgba(255,247,0,0.6)]"
      >
        <IconAppGamedetailPlay width={17} className="shrink-0 opacity-90" />
        הפעל
      </button>

      {/* Translation actions.
          gm === null         → still loading getGameModState; show
                                 a neutral placeholder so we DON'T
                                 fall into the legacy branch and
                                 flash the wrong button.
          gm.modSlug set      → download-distributed mod (CP2077):
                                 the buy / download+install /
                                 disable / reinstall flow.
          otherwise           → legacy on-disk enable/disable/remove. */}
      {!hydrated ? (
        /* Placeholder at the real button size, so the actions do not pop in
           and nothing below them shifts once the state lands. */
        <div className="h-[52px] rounded-xl skeleton" aria-hidden />
      ) : isSm2 ? (
        /* Spider-Man 2 - native TOC patch (no Overstrike). The launcher
           ships the mod and applies/reverts it directly + flips the
           in-game language. */
        sm2 === null ? (
          <span className="self-center text-slate-400 text-sm">טוען מצב התרגום…</span>
        ) : !sm2.available ? (
          <span className="self-center text-amber-300/90 text-sm">חבילת התרגום אינה זמינה בגרסה זו</span>
        ) : !sm2.hasPath ? (
          <span className="self-center text-amber-300/90 text-sm">← הגדר תחילה את נתיב המשחק בהגדרות</span>
        ) : (sm2.priceCents ?? 0) > 0 && !sm2.owned ? (
          /* Unowned PAID title. Note this is NOT gated on `!installed`: a mod
             already on disk must ALWAYS be removable, whoever is signed in -
             switching to an account without the purchase used to strand it. */
          <>
            <button onClick={handlePurchase} className={BUY_BTN}>
              <IconOptBtnPurchase width={18} className="shrink-0 opacity-90" />
              רכישה - {ils(sm2.priceCents ?? 0)}
            </button>
            {sm2.installed && (
              <button
                disabled={sm2Busy}
                onClick={handleSm2Remove}
                className="inline-flex items-center justify-center gap-1.5 bg-rose-500/25 hover:bg-rose-500/40 text-rose-200 font-bold
                           px-6 py-3 rounded-xl transition disabled:opacity-50 border border-rose-500/40"
              >
                <IconOptBtnRemoveTranslation width={18} className="shrink-0 opacity-90" />
                {sm2Busy ? "מסיר…" : "הסרת התרגום"}
              </button>
            )}
            {purchasePending && (
              <button
                onClick={() => { startPurchaseBurst(); void refreshSm2(); }}
                className="inline-flex items-center justify-center gap-1.5 bg-white/5 hover:bg-white/10 text-slate-200 font-bold
                           px-6 py-3 rounded-xl border border-white/10 transition"
              >
                <IconOptBtnAlreadyPaidRefresh width={18} className="shrink-0 opacity-90" />
                {pollUntil > Date.now() ? "בודק…" : "כבר שילמתי - רענן"}
              </button>
            )}
          </>
        ) : sm2.installed ? (
          <>
            {nativeUpd?.updateAvailable && (
              <button
                disabled={sm2Busy}
                onClick={handleSm2Install}
                className="font-bold px-6 py-3 rounded-xl text-brand-ink transition disabled:opacity-50"
                style={{ background: accent, boxShadow: `0 8px 20px -8px ${accent}` }}
              >
                {sm2Busy ? "מעדכן…" : `⬆ ${updVerb}${nativeUpd.latestVersion ? ` → ${nativeUpd.latestVersion}` : ""}`}
              </button>
            )}
            <button
              disabled={sm2Busy}
              onClick={handleSm2Remove}
              className="inline-flex items-center justify-center gap-1.5 bg-rose-500/25 hover:bg-rose-500/40 text-rose-200 font-bold
                         px-6 py-3 rounded-xl transition disabled:opacity-50 border border-rose-500/40"
            >
              <IconOptBtnRemoveTranslation width={18} className="shrink-0 opacity-90" />
              {sm2Busy ? "מסיר…" : "הסרת התרגום"}
            </button>
          </>
        ) : (
          <button
            disabled={sm2Busy}
            onClick={handleSm2Install}
            className="inline-flex items-center justify-center gap-1.5 bg-emerald-500/85 hover:bg-emerald-400 text-white font-bold
                       px-6 py-3 rounded-xl transition disabled:opacity-50"
          >
            <IconOptBtnInstallTranslation width={18} className="shrink-0 opacity-90" />
            {sm2Busy ? "מתקין…" : "התקנת תרגום"}
          </button>
        )
      ) : isWd2 ? (
        /* Watch Dogs 2 - native FAT5 fat-redirect (no Overstrike). The
           launcher ships the Hebrew files and redirects/reverts them
           directly. Activation is in-game (Written Language = Arabic). */
        wd2 === null ? (
          <span className="self-center text-slate-400 text-sm">טוען מצב התרגום…</span>
        ) : !wd2.available ? (
          <span className="self-center text-amber-300/90 text-sm">חבילת התרגום אינה זמינה בגרסה זו</span>
        ) : !wd2.hasPath ? (
          <span className="self-center text-amber-300/90 text-sm">← הגדר תחילה את נתיב המשחק בהגדרות</span>
        ) : (wd2.priceCents ?? 0) > 0 && !wd2.owned ? (
          /* See the SM2 branch - buy, and still allow removing what's on disk. */
          <>
            <button onClick={handlePurchase} className={BUY_BTN}>
              <IconOptBtnPurchase width={18} className="shrink-0 opacity-90" />
              רכישה - {ils(wd2.priceCents ?? 0)}
            </button>
            {wd2.installed && (
              <button
                disabled={wd2Busy}
                onClick={handleWd2Remove}
                className="inline-flex items-center justify-center gap-1.5 bg-rose-500/25 hover:bg-rose-500/40 text-rose-200 font-bold
                           px-6 py-3 rounded-xl transition disabled:opacity-50 border border-rose-500/40"
              >
                <IconOptBtnRemoveTranslation width={18} className="shrink-0 opacity-90" />
                {wd2Busy ? "מסיר…" : "הסרת התרגום"}
              </button>
            )}
            {purchasePending && (
              <button
                onClick={() => { startPurchaseBurst(); void refreshWd2(); }}
                className="inline-flex items-center justify-center gap-1.5 bg-white/5 hover:bg-white/10 text-slate-200 font-bold
                           px-6 py-3 rounded-xl border border-white/10 transition"
              >
                <IconOptBtnAlreadyPaidRefresh width={18} className="shrink-0 opacity-90" />
                {pollUntil > Date.now() ? "בודק…" : "כבר שילמתי - רענן"}
              </button>
            )}
          </>
        ) : wd2.installed ? (
          <>
            {nativeUpd?.updateAvailable && (
              <button
                disabled={wd2Busy}
                onClick={handleWd2Install}
                className="font-bold px-6 py-3 rounded-xl text-brand-ink transition disabled:opacity-50"
                style={{ background: accent, boxShadow: `0 8px 20px -8px ${accent}` }}
              >
                {wd2Busy ? "מעדכן…" : `⬆ ${updVerb}${nativeUpd.latestVersion ? ` → ${nativeUpd.latestVersion}` : ""}`}
              </button>
            )}
            <button
              disabled={wd2Busy}
              onClick={handleWd2Remove}
              className="inline-flex items-center justify-center gap-1.5 bg-rose-500/25 hover:bg-rose-500/40 text-rose-200 font-bold
                         px-6 py-3 rounded-xl transition disabled:opacity-50 border border-rose-500/40"
            >
              <IconOptBtnRemoveTranslation width={18} className="shrink-0 opacity-90" />
              {wd2Busy ? "מסיר…" : "הסרת התרגום"}
            </button>
          </>
        ) : (
          <button
            disabled={wd2Busy}
            onClick={handleWd2Install}
            className="inline-flex items-center justify-center gap-1.5 bg-emerald-500/85 hover:bg-emerald-400 text-white font-bold
                       px-6 py-3 rounded-xl transition disabled:opacity-50"
          >
            <IconOptBtnInstallTranslation width={18} className="shrink-0 opacity-90" />
            {wd2Busy ? "מתקין…" : "התקנת תרגום"}
          </button>
        )
      ) : isGowr ? (
        /* God of War: Ragnarök - native single-file WAD swap. The launcher ships
           the Hebrew WAD, backs up the original + swaps it in / reverts.
           Activation is in-game (Settings → Text Language = Arabic). */
        gowr === null ? (
          <span className="self-center text-slate-400 text-sm">טוען מצב התרגום…</span>
        ) : !gowr.available ? (
          <span className="self-center text-amber-300/90 text-sm">חבילת התרגום אינה זמינה בגרסה זו</span>
        ) : !gowr.hasPath ? (
          <span className="self-center text-amber-300/90 text-sm">
            {isSoftware ? "← הגדר תחילה את נתיב התוכנה בהגדרות" : "← הגדר תחילה את נתיב המשחק בהגדרות"}
          </span>
        ) : (gowr.priceCents ?? 0) > 0 && !gowr.owned ? (
          /* PAID native applier - buy on the website, the burst poller flips the
             CTA to install. Removal stays available for an already-applied mod. */
          <>
            <button onClick={handlePurchase} className={BUY_BTN}>
              <IconOptBtnPurchase width={18} className="shrink-0 opacity-90" />
              רכישה - {ils(gowr.priceCents ?? 0)}
            </button>
            {gowr.installed && (
              <button
                disabled={gowrBusy}
                onClick={handleGowrRemove}
                className="inline-flex items-center justify-center gap-1.5 bg-rose-500/25 hover:bg-rose-500/40 text-rose-200 font-bold
                           px-6 py-3 rounded-xl transition disabled:opacity-50 border border-rose-500/40"
              >
                <IconOptBtnRemoveTranslation width={18} className="shrink-0 opacity-90" />
                {gowrBusy ? "מסיר…" : "הסרת התרגום"}
              </button>
            )}
            {purchasePending && (
              <button
                onClick={() => { startPurchaseBurst(); void refreshGowr(); }}
                className="inline-flex items-center justify-center gap-1.5 bg-white/5 hover:bg-white/10 text-slate-200 font-bold
                           px-6 py-3 rounded-xl border border-white/10 transition"
                title={pollUntil > Date.now() ? "מחפש רכישה ברקע…" : undefined}
              >
                <IconOptBtnAlreadyPaidRefresh width={18} className="shrink-0 opacity-90" />
                {pollUntil > Date.now() ? "בודק…" : "כבר שילמתי - רענן"}
              </button>
            )}
          </>
        ) : gowr.installed ? (
          <>
            {nativeUpd?.updateAvailable && (
              <button
                disabled={gowrBusy}
                onClick={handleGowrInstall}
                className="font-bold px-6 py-3 rounded-xl text-brand-ink transition disabled:opacity-50"
                style={{ background: accent, boxShadow: `0 8px 20px -8px ${accent}` }}
              >
                {gowrBusy ? "מעדכן…" : `⬆ ${updVerb}${nativeUpd.latestVersion ? ` → ${nativeUpd.latestVersion}` : ""}`}
              </button>
            )}
            <button
              disabled={gowrBusy}
              onClick={handleGowrRemove}
              className="inline-flex items-center justify-center gap-1.5 bg-rose-500/25 hover:bg-rose-500/40 text-rose-200 font-bold
                         px-6 py-3 rounded-xl transition disabled:opacity-50 border border-rose-500/40"
            >
              <IconOptBtnRemoveTranslation width={18} className="shrink-0 opacity-90" />
              {gowrBusy ? "מסיר…" : "הסרת התרגום"}
            </button>
          </>
        ) : nativeDl?.gated && game.availability !== "available" ? (
          <span className="self-center inline-flex items-center gap-2 text-slate-400 text-sm">
            <IconOptEmptyComingSoon width={30} className="shrink-0 opacity-70" />
            התרגום עדיין בעבודה - בקרוב
          </span>
        ) : (
          <button
            disabled={gowrBusy}
            onClick={handleGowrInstall}
            className="inline-flex items-center justify-center gap-1.5 bg-emerald-500/85 hover:bg-emerald-400 text-white font-bold
                       px-6 py-3 rounded-xl transition disabled:opacity-50"
          >
            <IconOptBtnInstallTranslation width={18} className="shrink-0 opacity-90" />
            {gowrBusy ? "מתקין…" : "התקנת תרגום"}
          </button>
        )
      ) : isGtav ? (
        /* GTA V - native OpenIV-free RPF7 read-modify-write of the user's
           EXISTING mods folder (other mods byte-exact). A clean install
           (no mods folder) is GUIDED through a one-time OpenIV setup. */
        gtav === null ? (
          <span className="self-center text-slate-400 text-sm">טוען מצב התרגום…</span>
        ) : !gtav.available ? (
          <span className="self-center text-amber-300/90 text-sm">חבילת התרגום אינה זמינה בגרסה זו</span>
        ) : gtav.scenario === "no_game" ? (
          <span className="self-center text-amber-300/90 text-sm">← הגדר תחילה את נתיב המשחק בהגדרות</span>
        ) : gtav.scenario === "clean" ? (
          <div className="flex flex-col gap-2">
            {gtav.priceCents > 0 && !gtav.owned && (
              <button onClick={handlePurchase} className={`self-start ${BUY_BTN}`}>
                <IconOptBtnPurchase width={18} className="shrink-0 opacity-90" />
                רכישה - {ils(gtav.priceCents)}
              </button>
            )}
            <p className="text-sm text-amber-200/90 leading-relaxed max-w-md">
              אין תיקיית <b>mods</b>. ל-GTA המעודכן צריך את <b>OpenIV</b> פעם אחת ליצירת
              תיקיית המודים (בגלל הצפנת המשחק) - ואחרי זה התוכנה תנהל את התרגום לבד,
              בלי OpenIV, בלי לפגוע במודים אחרים.
            </p>
            <button
              onClick={openOpenIV}
              className="self-start bg-white/5 hover:bg-white/10 text-slate-200 font-bold
                         px-5 py-2.5 rounded-xl border border-white/10 transition"
            >
              פתח את אתר OpenIV ↗
            </button>
          </div>
        ) : gtav.installed ? (
          <>
            {nativeUpd?.updateAvailable && (
              <button
                disabled={gtavBusy}
                onClick={handleGtavInstall}
                className="font-bold px-6 py-3 rounded-xl text-brand-ink transition disabled:opacity-50"
                style={{ background: accent, boxShadow: `0 8px 20px -8px ${accent}` }}
              >
                {gtavBusy ? "מעדכן…" : `⬆ ${updVerb}${nativeUpd.latestVersion ? ` → ${nativeUpd.latestVersion}` : ""}`}
              </button>
            )}
            <button
              disabled={gtavBusy}
              onClick={handleGtavRemove}
              className="inline-flex items-center justify-center gap-1.5 bg-rose-500/25 hover:bg-rose-500/40 text-rose-200 font-bold
                         px-6 py-3 rounded-xl transition disabled:opacity-50 border border-rose-500/40"
            >
              <IconOptBtnRemoveTranslation width={18} className="shrink-0 opacity-90" />
              {gtavBusy ? "מסיר…" : "הסרת התרגום"}
            </button>
          </>
        ) : (gtav.priceCents > 0 && !gtav.owned) ? (
          <>
            <button onClick={handlePurchase} className={BUY_BTN}>
              <IconOptBtnPurchase width={18} className="shrink-0 opacity-90" />
              רכישה - {ils(gtav.priceCents)}
            </button>
            {purchasePending && (
              <button
                onClick={() => { startPurchaseBurst(); void refreshGtav(); }}
                className="inline-flex items-center justify-center gap-1.5 bg-white/5 hover:bg-white/10 text-slate-200 font-bold
                           px-6 py-3 rounded-xl border border-white/10 transition"
                title={pollUntil > Date.now() ? "מחפש רכישה ברקע…" : undefined}
              >
                <IconOptBtnAlreadyPaidRefresh width={18} className="shrink-0 opacity-90" />
                {pollUntil > Date.now() ? "בודק…" : "כבר שילמתי - רענן"}
              </button>
            )}
          </>
        ) : (
          <button
            disabled={gtavBusy}
            onClick={handleGtavInstall}
            className="inline-flex items-center justify-center gap-1.5 bg-emerald-500/85 hover:bg-emerald-400 text-white font-bold
                       px-6 py-3 rounded-xl transition disabled:opacity-50"
          >
            <IconOptBtnInstallTranslation width={18} className="shrink-0 opacity-90" />
            {gtavBusy ? "מתקין…" : "התקנת תרגום"}
          </button>
        )
      ) : gm === null ? (
        <span className="self-center text-slate-400 text-sm">
          טוען מצב התרגום…
        </span>
      ) : gm.modSlug ? (
        <>
          {gm.priceCents > 0 && !gm.owned && (
            <button disabled={gmBusy} onClick={handlePurchase} className={BUY_BTN}>
              <IconOptBtnPurchase width={18} className="shrink-0 opacity-90" />
              רכישה - {ils(gm.priceCents)}
            </button>
          )}
          {gm.priceCents > 0 && !gm.owned && purchasePending && (
            <button
              disabled={gmBusy}
              onClick={() => { startPurchaseBurst(); void refreshGm(); }}
              className="inline-flex items-center justify-center gap-1.5 bg-white/5 hover:bg-white/10 text-slate-200 font-bold
                         px-6 py-3 rounded-xl border border-white/10 transition"
              title={pollUntil > Date.now() ? "מחפש רכישה ברקע…" : undefined}
            >
              <IconOptBtnAlreadyPaidRefresh width={18} className="shrink-0 opacity-90" />
              {pollUntil > Date.now() ? "בודק…" : "כבר שילמתי - רענן"}
            </button>
          )}
          {gm.owned && !gm.installed && (
            <button
              disabled={gmBusy || !gm.hasPath}
              onClick={handleGmInstall}
              title={!gm.hasPath ? "הגדר תחילה את נתיב המשחק בהגדרות" : undefined}
              className="inline-flex items-center justify-center gap-1.5 bg-emerald-500/85 hover:bg-emerald-400 text-white font-bold
                         px-6 py-3 rounded-xl transition disabled:opacity-50"
            >
              <IconOptBtnDownloadInstall width={18} className="shrink-0 opacity-90" />
              {/* Cached but not installed is an INSTALL (from the local cache),
                  not a "reinstall" - the old wording was the last place that
                  phrase appeared, and it also told the user no download is
                  needed less clearly than "התקן" does. */}
              {gmBusy ? "מתקין…" : gm.cached ? "התקן" : "הורד והתקן"}
            </button>
          )}
          {/* NOT gated on `owned`: an installed mod must ALWAYS be removable.
              Signing into an account without the purchase used to leave the mod
              applied with no way to undo it - only a buy button. The UPDATE
              button below stays owner-only. */}
          {gm.installed && (
            <>
              {/* A newer mod version is on the server - re-download +
                  reinstall the latest (download_and_cache wipes the cache
                  first, so this pulls the fresh version). */}
              {gm.owned && modUpd?.updateAvailable && (
                <button
                  disabled={gmBusy}
                  onClick={handleGmInstall}
                  className="font-bold px-6 py-3 rounded-xl text-brand-ink transition
                             disabled:opacity-50"
                  style={{ background: accent, boxShadow: `0 8px 20px -8px ${accent}` }}
                >
                  {gmBusy ? "מעדכן…" : `⬆ ${updVerb}${modUpd.latestVersion ? ` → ${modUpd.latestVersion}` : ""}`}
                </button>
              )}
              <button
                disabled={gmBusy}
                onClick={() => handleGmToggle(false)}
                className="inline-flex items-center justify-center gap-1.5 bg-rose-500/25 hover:bg-rose-500/40 text-rose-200 font-bold
                           px-6 py-3 rounded-xl transition disabled:opacity-50 border border-rose-500/40"
              >
                <IconOptBtnRemoveTranslation width={18} className="shrink-0 opacity-90" />
                הסרת התרגום
              </button>
              {/* No "התקנה מחדש" button (user request, ALL games): with the mod
                  already installed it is redundant next to הסרת התרגום, and a
                  re-apply is reachable by removing and installing again. */}
            </>
          )}
          {gm.owned && !gm.hasPath && (
            <span className="self-center text-xs text-amber-300/90">
              ← הגדר תחילה את נתיב המשחק בהגדרות
            </span>
          )}
          {game.id === "anno1800" && (
            <p className="self-center w-full text-xs text-slate-400 leading-relaxed mt-1">
              לאחר ההתקנה התוכנה תגדיר שפת טקסט = English אוטומטית. הפעל את המשחק,
              ובהגדרות החלף שפה פעם אחת לתצוגת עברית מלאה.
            </p>
          )}
          {game.id === "rdr2" && (
            <p className="self-center w-full text-xs text-slate-400 leading-relaxed mt-1">
              אין צורך לשנות הגדרה - הפעל את המשחק והעברית מופיעה. מסכי האזהרה
              המשפטיים בפתיחה נשארים באנגלית בגרסה זו.
            </p>
          )}
          {game.id === "corsair-cove" && (
            <p className="self-center w-full text-xs text-slate-400 leading-relaxed mt-1">
              אין צורך לשנות הגדרה - העברית יושבת בסלוט השפה שכבר פעיל כברירת מחדל.
            </p>
          )}
        </>
      ) : (
        <>
          {/* NOT_AVAILABLE titles get a disabled chip. */}
          {game.is_installed && !game.has_mod_support && (
            <button
              disabled
              className="bg-white/5 text-slate-400 font-bold px-6 py-3 rounded-xl
                         border border-white/10 cursor-not-allowed"
              title="חבילת תרגום עוד לא הוכנה לכותר הזה"
            >
              התרגום עדיין לא זמין
            </button>
          )}

          {game.has_mod_support && game.is_installed &&
           (game.mod_state === "DISABLED" || game.mod_state === "NOT_INSTALLED") && (
            <button
              disabled={busy !== null}
              onClick={handleEnable}
              className="inline-flex items-center justify-center gap-1.5 bg-emerald-500/85 hover:bg-emerald-400 text-white font-bold
                         px-6 py-3 rounded-xl transition disabled:opacity-50"
            >
              <IconOptBtnInstallTranslation width={18} className="shrink-0 opacity-90" />
              התקנת תרגום
            </button>
          )}
          {game.has_mod_support && game.is_installed && game.mod_state === "ACTIVE" && (
            <button
              disabled={busy !== null}
              onClick={handleDisable}
              className="inline-flex items-center justify-center gap-1.5 bg-amber-500/85 hover:bg-amber-400 text-white font-bold
                         px-6 py-3 rounded-xl transition disabled:opacity-50"
            >
              <IconOptBtnDisableTranslation width={18} className="shrink-0 opacity-90" />
              השבתת תרגום
            </button>
          )}
          {/* "Remove" appears only when there are ACTUAL files on disk to remove */}
          {game.has_mod_support && game.is_installed &&
           (game.mod_state === "ACTIVE" || game.mod_state === "DISABLED") && (
            <button
              disabled={busy !== null}
              onClick={handleUninstall}
              className="inline-flex items-center justify-center gap-1.5 bg-rose-500/25 hover:bg-rose-500/40 text-rose-200 font-bold
                         px-6 py-3 rounded-xl transition disabled:opacity-50
                         border border-rose-500/40"
            >
              <IconOptBtnRemoveTranslation width={18} className="shrink-0 opacity-90" />
              הסרת התרגום
            </button>
          )}
        </>
      )}
    </>
  );

  // ── Settings rail body (path / language / cache / beta / stats) -
  //    a single neat vertical column for the fixed right-side panel. ──
  const settingsBody = (
    <div className="space-y-5">

      {/* install path + open folder + language */}
      <div className="space-y-4">
        <div>
          <label className="block text-xs text-slate-400 mb-1.5">
            {isSoftware ? "נתיב קובץ התוכנה (EXE)" : "נתיב קובץ המשחק (EXE)"}
          </label>
          <input
            dir="ltr"
            value={pathInput}
            onChange={(e) => setPathInput(e.target.value)}
            placeholder={"C:\\Games\\...\\Game.exe"}
            className="w-full bg-black/40 border border-white/10 focus:border-brand-yellow/50
                       rounded-lg px-3 py-2 text-sm text-slate-100 outline-none"
          />
          <button
            disabled={busy !== null}
            onClick={handlePickExe}
            className="w-full mt-2 inline-flex items-center justify-center gap-1.5 text-xs px-3 py-1.5 border border-brand-cyan/30
                       text-brand-cyan rounded-lg hover:bg-brand-cyan/10 disabled:opacity-50"
          >
            <IconOptBtnOpenFolder width={16} className="shrink-0 opacity-90" />
            בחר קובץ (EXE)…
          </button>
          <div className="flex gap-2 mt-2">
            <button
              disabled={busy !== null}
              onClick={handleSavePath}
              className="flex-1 inline-flex items-center justify-center gap-1.5 text-xs px-3 py-1.5 bg-brand-yellow text-brand-ink
                         font-bold rounded-lg hover:bg-yellow-300 disabled:opacity-50"
            >
              <IconOptBtnSavePath width={18} className="shrink-0 opacity-90" />
              שמור
            </button>
            <button
              disabled={busy !== null}
              onClick={handleClearPath}
              className="flex-1 inline-flex items-center justify-center gap-1.5 text-xs px-3 py-1.5 border border-white/10
                         text-slate-300 rounded-lg hover:bg-white/5 disabled:opacity-50"
            >
              <IconOptBtnClearPath width={18} className="shrink-0 opacity-90" />
              נקה
            </button>
          </div>
        </div>

        <button
          disabled={!game.install_path}
          onClick={handleOpenFolder}
          className="w-full flex items-center justify-center gap-1.5 text-sm px-3 py-2 border border-white/10 text-slate-200
                     rounded-lg hover:border-brand-cyan/40 hover:bg-brand-cyan/5
                     disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <IconOptBtnOpenFolder width={18} className="shrink-0 opacity-90" />
          {isSoftware ? "פתח תיקיית תוכנה" : "פתח תיקיית משחק"}
        </button>

        {/* In-game language switch - only for titles the launcher can
            flip (registry / settings-file). Lets the user play in Hebrew
            (Arabic slot) or English without editing anything by hand. */}
        {hydrated && lang?.supported && (
          <div className="border-t border-white/5 pt-4">
            <label className="inline-flex items-center gap-1.5 text-xs text-slate-400 mb-2">
              <IconOptHdrGameLanguage width={16} className="shrink-0 opacity-90" />
              {isSoftware ? "שפת התוכנה" : "שפת המשחק"}
            </label>
            {/* Same segmented control as every other 2+ choice in the app - one
                sliding, glass-capable row instead of three separate buttons. */}
            <SegmentedControl<"auto" | "hebrew" | "english">
              ariaLabel={isSoftware ? "שפת התוכנה" : "שפת המשחק"}
              value={(lang.mode ?? "auto") as "auto" | "hebrew" | "english"}
              onChange={handleSetLang}
              disabled={langBusy || locked}
              size="sm"
              accent={accent}
              showHints={false}
              options={[
                { value: "auto",    label: "אוטומטי", title: "עברית כשהמוד פעיל, אחרת השפה שלפני המוד" },
                { value: "hebrew",  label: "עברית",   title: "כפה עברית (סלוט ערבית)" },
                { value: "english", label: "אנגלית",  title: "כפה אנגלית" },
              ]}
            />
            <div className="flex items-center justify-between mt-2 text-[11px]">
              <button
                disabled={langBusy || locked}
                onClick={handleRestoreLang}
                className="text-slate-400 hover:text-brand-cyan transition disabled:opacity-50"
                title="החזר לשפה שהמשחק היה בה לפני התקנת המוד"
              >
                ↺ שחזר לשפה שלפני המוד
              </button>
              <span className="text-slate-500">
                {lang.current === "unknown"
                  ? "ממשק/כתוביות: טרם נקרא"
                  : `ממשק/כתוביות כעת: ${langName(lang.current)}`}
              </span>
            </div>
            <p className="text-[10px] text-slate-500 mt-1.5 leading-snug">
              {locked
                ? (
                  <>
                    <IconAppGamedetailLock width={15} className="shrink-0 opacity-90" />{" "}
                    {`החלפת השפה תיפתח לאחר רכישת התרגום ל${isSoftware ? "תוכנה" : "משחק"}.`}
                  </>
                )
                : lang.current === "unknown"
                ? `${isSoftware ? "התוכנה" : "המשחק"} עוד לא יצר קובץ הגדרות - הפעל אותו פעם אחת כדי שנוכל לקרוא ולהחליף את השפה. בחירת שפה כאן תיכנס לתוקף בהפעלה הבאה.`
                : `החלפת השפה נכנסת לתוקף בהפעלה הבאה של ${noun}. "עברית" משתמש בסלוט הערבית (כיווניות RTL מובנית).`}
            </p>
          </div>
        )}
      </div>

      {/* beta opt-in + cache control */}
      <div className="space-y-4">
        {/* Per-mod beta opt-in - only for GitHub-distributed mods (download
            mod or SM2), which can have pre-release versions. */}
        {/* Beta opt-in: download mods, SM2, AND the native download appliers
            (GoWR/HL/W3/PT/VirtualDJ) - they all now pull their version from the
            Worker manifest, so a per-title beta override is meaningful. */}
        {hydrated && (gm?.modSlug || isSm2 || isGowr) && !locked && (
          <ModBetaToggle gameId={game.id} accent={accent} isSoftware={isSoftware} />
        )}

        {/* Per-mod cache control - lives here in the game's own panel
            (not in global Settings). Removes the mod from the game
            folder AND wipes the launcher cache. Shown for BOTH download mods
            AND the native appliers (SM2/WD2/GTAV/GoWR/HL/W3/PT/VirtualDJ) so
            every title exposes the same control. */}
        {/* NOT gated on `locked`: this is a REMOVAL action, and the condition
            already requires something to be installed/cached. Hiding it from an
            unowned account left a mod on disk with no way to clear it. */}
        {hydrated && ((gm?.modSlug && (gm.cached || gm.installed)) || nativeInstalled) && (
          <button
            disabled={gmBusy || gowrBusy}
            onClick={gm?.modSlug ? handleGmClearCache : handleNativeClearCache}
            className="w-full flex items-center justify-center gap-1.5 text-sm px-3 py-2 border border-rose-500/30 text-rose-200
                       rounded-lg hover:bg-rose-500/10
                       disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <IconOptBtnClearCache width={18} className="shrink-0 opacity-90" />
            ניקוי מטמון התרגום
          </button>
        )}
      </div>

      {/* status summary */}
      <div className="text-xs space-y-1.5 border-t border-white/5 pt-4">
        <Row k="זמינות"     v={avail.text} />
        <Row k="גרסה זמינה" v={formatVersion(game.version)} />
        {installedVersion && (
          <Row k="גרסה מותקנת" v={formatVersion(installedVersion)} highlight={anyUpdateAvailable} />
        )}
        <Row k="התקנה"      v={game.is_installed ? "מותקן" : "לא נמצא"} />
        <Row k="תמיכת מוד"  v={game.has_mod_support ? "כן" : "לא"} />
        {game.has_mod_support && <Row k="סטטוס מוד" v={mod.text} />}
        {game.gameVersion && (
          <Row k={isSoftware ? "גרסת תוכנה תואמת" : "גרסת משחק תואמת"} v={game.gameVersion} />
        )}
        {anyUpdateAvailable && (
          <div className="flex items-center justify-end pt-1">
            <span className="text-[11px] font-semibold" style={{ color: accent }}>⬆ קיים עדכון חדש יותר</span>
          </div>
        )}
      </div>
    </div>
  );

  // Steam-style hero banner source: explicit banner_url override → else a
  // blurred, zoomed cover as the cinematic backdrop (the "hybrid" default).
  const bannerSrc = resolveAssetUrl(game.bannerUrl) || resolveCoverUrl(game.cover, game.id);

  return (
    <div className="h-full flex animate-scale-in relative">
      {/* ── Settings rail (RIGHT, RTL). ONE animated drawer: the wrapper width
          slides 0↔330 and the toggle below rides its inner edge. ─────────── */}
      <div
        className="shrink-0 h-full overflow-hidden glass border-l border-white/10"
        style={{ width: settingsOpen ? 330 : 0, transition: "width .46s cubic-bezier(.34, 1.35, .5, 1)" }}
      >
        {/* Liquid collapse/expand: the WIDTH itself springs (over-shoots ~40px then
            eases back, like the fleet-dashboard rail) - THAT is the liquid feel. The
            glass + border live on THIS wrapper, so the brief over-shoot past 330px is
            just more glass panel (never an empty gap or a torn layout), and the
            fixed-width content inside never reflows. */}
        <aside className="w-[330px] h-full flex flex-col">
          <div className="shrink-0 flex items-center px-4 py-3.5 border-b border-white/10">
            <h3 className="flex-1 text-white font-bold text-lg flex items-center gap-2 justify-end">
              <span className="h-5 w-1.5 rounded-full" style={{ background: accent, boxShadow: `0 0 12px ${accent}99` }} />
              <IconOptHdrSettings width={20} className="shrink-0 opacity-90" />
              הגדרות
            </h3>
          </div>
          <div className="flex-1 min-h-0 overflow-y-auto p-4">{settingsBody}</div>
        </aside>
      </div>

      {/* Single drawer toggle - rides the rail's inner edge (moves WITH the
          panel); the chevron rotates and the label collapses on one timeline. */}
      <button
        type="button"
        onClick={() => setSettingsOpen((o) => { const next = !o; writeDrawerOpen(next); return next; })}
        title={settingsOpen ? "הסתר הגדרות" : "הצג הגדרות"}
        aria-label={settingsOpen ? "הסתר הגדרות" : "הצג הגדרות"}
        className="absolute bottom-5 z-30 flex items-center justify-center rounded-xl
                   glass-strong border border-white/10 text-slate-200 hover:text-white
                   hover:border-brand-cyan/50 shadow-[0_12px_30px_-10px_rgba(0,0,0,0.75)]"
        style={{
          right: settingsOpen ? 346 : 16,
          gap: settingsOpen ? 0 : 8,
          paddingTop: 10, paddingBottom: 10,
          paddingLeft: settingsOpen ? 10 : 16, paddingRight: settingsOpen ? 10 : 16,
          transition: "right .46s cubic-bezier(.34, 1.35, .5, 1), padding .3s ease",
        }}
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor"
             strokeWidth={2.4} strokeLinecap="round" strokeLinejoin="round" aria-hidden
             style={{ transform: settingsOpen ? "rotate(180deg)" : "rotate(0deg)", transition: "transform .46s cubic-bezier(.34, 1.35, .5, 1)" }}>
          <path d="M15 6l-6 6 6 6" />
        </svg>
        {!settingsOpen && <span className="text-sm font-bold whitespace-nowrap">הגדרות</span>}
      </button>

      {/* ── MAIN - scrollable content ─────────────────────────────────────── */}
      <div className="flex-1 min-w-0 h-full overflow-y-auto px-8 py-6">
      {/* ── CINEMATIC HERO BANNER (wide backdrop + logo, Steam-style) ──── */}
      <div className="relative -mx-8 -mt-6 mb-6 h-48 overflow-hidden">
        {/* Backdrop: banner_url, or a blurred/zoomed cover fallback. */}
        <SmartImage
          src={bannerSrc}
          alt=""
          aria-hidden
          draggable={false}
          className={`absolute inset-0 w-full h-full object-cover ${game.bannerUrl ? "" : "scale-125 blur-2xl"}`}
          onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = "none"; }}
        />
        {/* Accent wash + bottom/edge scrims for legibility. */}
        <div className="absolute inset-0" aria-hidden style={{
          background: `linear-gradient(to top, rgba(7,7,18,0.98) 4%, rgba(7,7,18,0.45) 45%, rgba(7,7,18,0.25)), radial-gradient(70% 120% at 92% 30%, ${accent}26, transparent 70%)`,
        }} />
        {/* Back button (top-right, RTL). */}
        <button
          type="button"
          onClick={onBack}
          className="absolute top-4 right-4 z-10 px-3 py-1.5 rounded-lg text-sm text-slate-200
                     bg-black/70 hover:bg-black/85 border border-white/10
                     hover:text-brand-yellow transition flex items-center gap-2"
        >
          ← חזרה לספרייה
        </button>
        {/* Logo (logo_url) or the title as the "logo". */}
        <div className="absolute bottom-4 right-8 left-8 flex items-end justify-end">
          {game.logoUrl ? (
            <img src={resolveAssetUrl(game.logoUrl)} alt={game.titleEn} draggable={false}
                 className="max-h-24 max-w-[60%] object-contain drop-shadow-[0_4px_18px_rgba(0,0,0,0.9)]"
                 onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = "none"; }} />
          ) : (
            <h1 dir="ltr" className="font-display font-extrabold text-4xl text-left leading-none
                                     drop-shadow-[0_3px_14px_rgba(0,0,0,0.95)]"
                style={{ color: accent }}>
              {game.titleEn}
            </h1>
          )}
        </div>
      </div>

      {/* ── TOP: actions (right) · info (center) · cover (left) ─────────── */}
      <div className="grid gap-x-3 gap-y-3 items-start [grid-template-areas:'actions_cover'_'info_info'] [grid-template-columns:minmax(150px,190px)_minmax(140px,1fr)] xl:[grid-template-areas:'actions_info_cover'] xl:[grid-template-columns:minmax(160px,190px)_minmax(0,1fr)_minmax(180px,320px)]">

        {/* Actions column - stacked top-right (a touch narrower per request) */}
        <div className="flex flex-col gap-3 self-start [grid-area:actions] w-full max-w-[190px]">
          {actionButtons}
        </div>

        {/* Info column - title, badges, text, progress, contextual notes.
            The display name is the ENGLISH title (per request - matches how the
            game itself labels its menus), not the Hebrew transliteration. */}
        <div className="flex flex-col min-w-0 [grid-area:info]">
          <h1 dir="ltr" className="text-4xl font-extrabold leading-tight mb-3 text-right text-white">
            {game.titleEn}
          </h1>

          {(() => {
            // Unified, game-agnostic status chips so EVERY game renders the
            // SAME set - CP2077's download mod, SM2's native patch, and any
            // future title. The old per-backend branches showed different
            // labels ("תרגום פעיל" vs "תרגום מותקן") and only added "נרכש"
            // for CP2077, so two purchased games looked different.
            const installed = isSm2
              ? !!sm2?.installed
              : isWd2
                ? !!wd2?.installed
                : isGtav
                  ? !!gtav?.installed
                  : isGowr
                    ? !!gowr?.installed
                    : gm?.modSlug ? gm.installed : game.mod_state === "ACTIVE";
            const cached  = !isSm2 && !isWd2 && !isGtav && !isGowr && !!gm?.cached;
            const paid    = (gm?.priceCents ?? 0) > 0;
            const owned   = !!gm?.owned;
            const stStyle = installed
              ? { color: "#86efac", background: "rgba(34,197,94,0.18)", borderColor: "rgba(34,197,94,0.45)" }
              : cached
                ? { color: "#fcd34d", background: "rgba(245,158,11,0.16)", borderColor: "rgba(245,158,11,0.4)" }
                : { color: "#cbd5e1", background: "rgba(148,163,184,0.18)", borderColor: "rgba(148,163,184,0.35)" };
            return (
              <div className="flex gap-2 mb-5 justify-start flex-wrap items-center">
                {/* availability - skip the redundant "זמין" on an available
                    title; the install chip below carries the real state. */}
                {game.availability !== "available" && (
                  <span className={`px-3 py-1 rounded-full text-xs font-semibold ${avail.tone}`}>
                    {avail.text}
                  </span>
                )}
                <span className="px-3 py-1 rounded-full text-xs bg-black/90 text-slate-200 ring-1 ring-white/15">
                  {formatVersion(game.version)}
                </span>
                <StageBadge releaseStage={game.releaseStage} version={game.version} />
                {game.has_mod_support && (
                  <span className="px-3 py-1 rounded-full text-xs font-semibold ring-1" style={stStyle}>
                    {installed ? "תרגום מותקן" : cached ? "תרגום במטמון" : "תרגום לא מותקן"}
                  </span>
                )}
                {(modUpd?.updateAvailable || nativeUpd?.updateAvailable) && (
                  <span className="px-3 py-1 rounded-full text-xs font-semibold ring-1 animate-pulse"
                        style={{ color: accent, background: `${accent}22`, borderColor: `${accent}66` }}>
                    ⬆ {updIsOffline ? "עדכון אופליין זמין" : "עדכון זמין"}
                  </span>
                )}
                {paid && owned && (
                  <span className="px-3 py-1 rounded-full text-xs font-semibold ring-1 ring-emerald-400/40 bg-emerald-500/20 text-emerald-200">
                    ✓ נרכש
                  </span>
                )}
              </div>
            );
          })()}

          <p className="text-lg text-slate-200 mb-3 leading-relaxed">{game.tagline}</p>
          <p className="text-slate-400 leading-relaxed mb-4">{game.description}</p>

          {game.changelog && game.changelog.trim() && (
            <button
              type="button"
              onClick={() => setShowChangelog(true)}
              className="self-start mb-6 inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm
                         border border-white/10 text-slate-200 hover:bg-white/5 transition"
              style={{ ["--tw-ring-color" as string]: `${accent}55` }}
            >
              ✨ מה חדש בגרסה {formatVersion(game.version)}
            </button>
          )}

          {/* Progress - ONLY for a game the admin marked "בתהליך תרגום"
              (`translating`). Every other state, including the generic
              "בעבודה", shows the status chip and no bar. Prefers the live
              /api/progress feed over the static `game.progress` value. */}
          {showsTranslationProgress(game.availability) && (() => {
            const usingLive = liveProgress && liveProgress.total > 0;
            // First-paint protection: while the live fetch is in flight
            // (`!liveLoaded`) render 0% / a neutral label so the OLD
            // static value doesn't flash before the real one arrives.
            const pct = !liveLoaded
              ? 0
              : usingLive
                ? (liveProgress!.processed / liveProgress!.total) * 100
                : (game.progress ?? 0);
            let label = !liveLoaded
              ? "טוען נתונים..."
              : usingLive
                ? resolvePhaseHeadline(liveProgress!.phase, liveProgress!.phaseLabelHe)
                : "התקדמות תרגום";
            // A finished translation on a game that isn't RELEASED yet must not read
            // "הושלם" (that implies the mod is available) - it's done, pending publish.
            if (liveLoaded && pct >= 99.95 && game.availability !== "available")
              label = "התרגום הושלם - יפורסם בקרוב";
            return (
              <div className="mb-6">
                <div className="flex justify-between text-xs text-slate-400 mb-1.5">
                  <span className="font-mono tabular-nums">{pct.toFixed(1)}%</span>
                  <span className="flex items-center gap-2">
                    {usingLive && (
                      <span
                        className="inline-block w-1.5 h-1.5 rounded-full"
                        style={{ background: "#22c55e", boxShadow: "0 0 8px #22c55e" }}
                        title="חי מהשרת"
                      />
                    )}
                    {label}
                  </span>
                </div>
                <LiquidWave
                  pct={pct}
                  ratePerMin={usingLive ? (liveProgress!.ratePerHour ?? 0) / 60 : 24}
                  primary={accent}
                  secondary="#00ffe0"
                  glow={accent}
                  height={44}
                />
                {usingLive && (
                  <div className="flex justify-between text-[10px] text-slate-500 mt-1.5 font-mono" dir="ltr">
                    <span>
                      {liveProgress.processed.toLocaleString("he-IL")} /{" "}
                      {liveProgress.total.toLocaleString("he-IL")} {liveProgress.unit}
                    </span>
                    {liveProgress.ratePerHour > 0 && (
                      <span>{liveProgress.ratePerHour.toLocaleString("he-IL")} {liveProgress.unit}/h</span>
                    )}
                  </div>
                )}
              </div>
            );
          })()}

          {/* Watch Dogs 2 - in-game activation reminder (Arabic slot). */}
          {isWd2 && wd2?.installed && (
            <p className="mt-2 text-xs text-amber-200/90 leading-relaxed bg-amber-500/10
                          border border-amber-500/25 rounded-xl p-3">
              להצגת העברית: במשחק היכנסו ל-Settings → Written Language ובחרו "עברית",
              והפעילו את המשחק עם
              <span dir="ltr" className="font-mono"> -eac_launcher</span>.
              התרגום מכסה את ממשק המשחק והכתוביות; כיווניות RTL מובנית דרך סלוט הערבית.
            </p>
          )}

          {/* Native single-flow applier (GoWR etc.) - in-game activation reminder.
              VirtualDJ + Witcher 3 excluded per user request (their notes were redundant). */}
          {isGowr && gowr?.installed && game.id !== "virtualdj" && game.id !== "witcher3" && (
            <p className="mt-2 text-xs text-amber-200/90 leading-relaxed bg-amber-500/10
                          border border-amber-500/25 rounded-xl p-3">
              {nativeDl?.note} שאר {noun} לא נגעו בו, ו"הסרת התרגום" מבטלת את השינוי.
            </p>
          )}

          {/* GTA V - installed: how it works + in-game activation. */}
          {isGtav && gtav?.installed && (
            <p className="mt-2 text-xs text-emerald-200/90 leading-relaxed bg-emerald-500/10
                          border border-emerald-500/25 rounded-xl p-3">
              הותקן ישירות לתיקיית ה-mods שלך - <b>בלי לפגוע במודים אחרים</b>. "הסרת התרגום"
              מחזירה רק את הטקסט לאנגלית ומשאירה את שאר המודים שלך. להצגת העברית: במשחק היכנס
              ל-Settings → Language ובחר <span dir="ltr"> American</span>.
            </p>
          )}

          {/* GTA V - separate, explicitly-warned full restore from the install-time
              snapshot (the user's "different button" for the pre-install state). */}
          {isGtav && gtav?.installed && gtav?.backupAvailable && (
            <div className="mt-2 text-[11px] text-slate-400 flex items-center gap-2 flex-wrap">
              <span>רוצה לחזור למצב המדויק שלפני ההתקנה?</span>
              <button
                disabled={gtavBusy}
                onClick={handleGtavRestoreBackup}
                className="underline decoration-dotted hover:text-slate-200 disabled:opacity-50"
                title="משחזר את הגיבוי המלא; ⚠ דורס שינויים שעשית מאז ההתקנה"
              >
                שחזור גיבוי מלא (לפני ההתקנה) ⚠
              </button>
            </div>
          )}

          {/* Download / install / patch progress (distributed mod OR SM2/WD2/GTA/GoWR). */}
          {(gm?.modSlug || isSm2 || isWd2 || isGtav || isGowr) && (gmBusy || sm2Busy || wd2Busy || gtavBusy || gowrBusy || gmProgress) && (
            <div className="mt-4">
              <div className="flex justify-between text-[11px] mb-1.5">
                <span dir="ltr" className="font-mono text-slate-300">
                  {gmProgress?.detail || "…"}
                </span>
                <span className="font-bold" style={{ color: accent }}>
                  {gmProgress?.phase === "verify"  ? `מאמת… ${smoothInstallPct.toFixed(0)}%`
                    : gmProgress?.phase === "apply" ? `מתקין… ${smoothInstallPct.toFixed(0)}%`
                    : `${Math.min(100, Math.max(0, gmProgress?.pct ?? 0)).toFixed(0)}%`}
                </span>
              </div>
              <LiquidWave
                pct={gmProgress?.phase === "verify" || gmProgress?.phase === "apply"
                  ? smoothInstallPct
                  : Math.min(100, Math.max(0, gmProgress?.pct ?? 0))}
                ratePerMin={48}
                primary={accent}
                secondary="#00ffe0"
                glow={accent}
                height={42}
              />
            </div>
          )}
        </div>

        {/* Cover - capped width so it never balloons; can shrink, never grow past this. */}
        <div className="self-start justify-self-end [grid-area:cover] w-full max-w-[300px]">
          <div className="relative aspect-[2/3] rounded-2xl overflow-hidden ring-1 ring-white/10
                          shadow-[0_25px_60px_-15px_rgba(0,0,0,0.8)]">
            <SmartImage
              src={resolveCoverUrl(game.cover, game.id)}
              alt={game.titleEn}
              className="absolute inset-0 w-full h-full object-cover"
              draggable={false}
            />
          </div>
        </div>
      </div>

      {/* ── Version history (public timeline, like the website) ───────── */}
      <VersionHistory gameId={game.id} accent={accent} />
      </div>

      <ChangelogModal
        open={showChangelog}
        title={game.titleEn}
        version={formatVersion(game.version)}
        changelog={game.changelog ?? ""}
        accent={accent}
        onClose={() => setShowChangelog(false)}
      />

    </div>
  );
}

/* ── Public version timeline (mirrors the website's VersionTimeline) ──────
   Fetches the hub's public history API directly; renders nothing on
   error/empty/offline so it's a no-op for games without a timeline. */
interface HistoryRow { version: string; stage?: string; changelog?: string; publishedAt?: string; isCurrent?: boolean }
function VersionHistory({ gameId, accent }: { gameId: string; accent: string }) {
  const [rows, setRows] = useState<HistoryRow[] | null>(null);
  // Distinct from `rows === null`: the fetch is REMOTE (the website), so it
  // lands well after the panel's local state. Without a reserved placeholder the
  // whole section dropped in late and the panel grew under the user's eyes -
  // the last of the three "stages" that made opening a game feel like it was
  // still loading. `done` lets us tell "still fetching" (show a skeleton) from
  // "there is no timeline" (render nothing).
  const [done, setDone] = useState(false);
  const [open, setOpen] = useState(false);
  useEffect(() => {
    let alive = true;
    setDone(false);
    (async () => {
      try {
        const res = await fetch(
          `https://hebrew-translation-hub.com/api/games?action=history&game=${encodeURIComponent(gameId)}`,
          { signal: AbortSignal.timeout(7000) },
        );
        if (!res.ok) return;
        const data = await res.json();
        const list: HistoryRow[] = Array.isArray(data) ? data : (data.history ?? data.versions ?? []);
        if (alive && Array.isArray(list) && list.length > 0) setRows(list);
      } catch { /* offline / no timeline → render nothing */ }
      finally { if (alive) setDone(true); }
    })();
    return () => { alive = false; };
  }, [gameId]);

  if (!rows || rows.length === 0) {
    if (done) return null;                       // no timeline for this title
    return (
      <div className="glass rounded-2xl mt-6 overflow-hidden" aria-hidden>
        <div className="px-5 py-3.5 border-b border-white/5">
          <div className="h-5 w-40 rounded skeleton mr-auto" />
        </div>
        <div className="p-5 space-y-3">
          <div className="h-4 w-2/3 rounded skeleton mr-auto" />
          <div className="h-4 w-1/2 rounded skeleton mr-auto" />
        </div>
      </div>
    );
  }
  const shown = open ? rows : rows.slice(0, 3);

  return (
    <div className="glass rounded-2xl mt-6 overflow-hidden">
      <div className="px-5 py-3.5 flex items-center justify-between border-b border-white/5">
        <span className="text-xs text-slate-500">{rows.length} גרסאות</span>
        <h3 className="text-white font-bold text-lg flex items-center gap-2">
          <span className="h-5 w-1.5 rounded-full" style={{ background: accent, boxShadow: `0 0 12px ${accent}99` }} />
          <IconOptHdrVersionHistory width={20} className="shrink-0 opacity-90" />
          היסטוריית גרסאות
        </h3>
      </div>
      <ol className="p-5 space-y-4">
        {shown.map((r, i) => (
          <li key={`${r.version}-${i}`} className="relative pr-5 text-right">
            <span className="absolute right-0 top-1.5 w-2.5 h-2.5 rounded-full"
                  style={{ background: r.isCurrent ? accent : "rgba(255,255,255,0.25)",
                           boxShadow: r.isCurrent ? `0 0 10px ${accent}` : undefined }} aria-hidden />
            {i < shown.length - 1 && <span className="absolute right-[4px] top-5 bottom-[-1rem] w-px bg-white/10" aria-hidden />}
            <div className="flex items-center justify-end gap-2 flex-wrap">
              {r.isCurrent && (
                <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold ring-1"
                      style={{ color: accent, background: `${accent}1f`, borderColor: `${accent}55` }}>נוכחי</span>
              )}
              {r.stage && r.stage !== "stable" && (
                <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-900/40 text-amber-200 ring-1 ring-amber-600/40">{r.stage}</span>
              )}
              <span dir="ltr" className="font-mono text-sm text-white font-bold">{formatVersion(r.version)}</span>
              {r.publishedAt && <span className="text-[11px] text-slate-500" dir="ltr">{r.publishedAt.slice(0, 10)}</span>}
            </div>
            {r.changelog && <p className="text-slate-400 text-xs mt-1 leading-relaxed whitespace-pre-line">{r.changelog}</p>}
          </li>
        ))}
      </ol>
      {rows.length > 3 && (
        <button type="button" onClick={() => setOpen((o) => !o)}
                className="w-full py-2.5 text-xs text-slate-400 hover:text-white hover:bg-white/5 transition border-t border-white/5 inline-flex items-center justify-center gap-1.5">
          {open ? "הצג פחות" : `הצג את כל ${rows.length} הגרסאות`}
          <IconAppGamedetailVersionToggle width={14} className="shrink-0 opacity-90" style={{ transform: open ? "rotate(180deg)" : undefined, transition: "transform .2s" }} />
        </button>
      )}
    </div>
  );
}

function Row({ k, v, highlight = false }: { k: string; v: string; highlight?: boolean }) {
  // LABEL first → sits at the RTL start (RIGHT); VALUE second → RTL end (LEFT).
  // (User request: the "זמינות / גרסה זמינה / …" labels on the right, values on the left.)
  return (
    <div className="flex items-center justify-between">
      <span className="text-slate-500">{k}</span>
      <span className={highlight ? "text-amber-300 font-semibold" : "text-slate-200"}>{v}</span>
    </div>
  );
}

/** Per-mod "receive beta versions" toggle. The effective value is the per-mod
 *  override if the user set one, otherwise the global Settings flag - shown
 *  explicitly so it's never ambiguous which is in effect. */
function ModBetaToggle({ gameId, accent, isSoftware }:
                       { gameId: string; accent: string; isSoftware?: boolean }) {
  const [globalBeta, setGlobalBeta] = useState(false);
  const [override, setOverride]     = useState<boolean | undefined>(undefined);
  const [busy, setBusy]             = useState(false);

  useEffect(() => {
    let alive = true;
    void api.getUpdatePrefs().then((p) => {
      if (!alive) return;
      setGlobalBeta(p.betaChannel);
      setOverride(gameId in (p.betaOverrides || {}) ? p.betaOverrides[gameId] : undefined);
    }).catch(() => {});
    return () => { alive = false; };
  }, [gameId]);

  const effective = override ?? globalBeta;

  const toggle = async () => {
    setBusy(true);
    try {
      const p = await api.setModBetaOverride(gameId, !effective);
      setGlobalBeta(p.betaChannel);
      setOverride(gameId in (p.betaOverrides || {}) ? p.betaOverrides[gameId] : undefined);
    } catch { /* noop */ } finally { setBusy(false); }
  };

  return (
    <div className="flex items-start justify-end gap-3 text-right">
      <div className="max-w-md">
        <div className="text-sm font-semibold text-slate-200">
          {isSoftware ? "קבל גרסאות בטא לתוכנה זו" : "קבל גרסאות בטא למשחק זה"}
        </div>
        <div className="text-xs text-slate-400 leading-relaxed">
          גרסאות מוקדמות - חדשות יותר אך עשויות להיות פחות יציבות.
          {override === undefined && (
            <> ברירת המחדל (מההגדרות): <span className="text-slate-300">{globalBeta ? "מופעל" : "כבוי"}</span>.</>
          )}
        </div>
      </div>
      <button
        type="button"
        onClick={toggle}
        disabled={busy}
        role="switch"
        aria-checked={effective}
        className="relative w-11 h-6 rounded-full transition shrink-0 mt-0.5 disabled:opacity-50"
        style={{ background: effective ? accent : "rgba(255,255,255,0.15)" }}
      >
        <span className="absolute top-0.5 w-5 h-5 rounded-full bg-white transition-all"
              style={{ left: effective ? "2px" : "22px" }} />
      </button>
    </div>
  );
}
