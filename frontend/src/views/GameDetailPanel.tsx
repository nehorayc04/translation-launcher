// "Big Picture" mode — page-2 layout: action buttons stacked top-RIGHT, the
// descriptive text + title/badges in the CENTER, the large cover on the LEFT,
// and ALL settings (path / language / cache / beta / stats) in a full-width
// COLLAPSIBLE drawer at the bottom. Rendered inside the main content area
// (NOT a separate window).
import { isInFlight, type Game } from "../lib/types";
import { accentFor, availabilityLabel, modStateLabel } from "../lib/theme";
import { resolveCoverUrl } from "../lib/coverUrl";
import { formatVersion } from "../lib/formatVersion";
import { StageBadge } from "../components/StageBadge";
import ChangelogModal from "../components/ChangelogModal";
import { api, onModProgress } from "../lib/eel";
import type { GameModState, GameLanguageState, SpiderMan2State, WatchDogs2State, GtavState, ModProgress } from "../lib/eel";
import { resolvePhaseHeadline } from "../lib/phaseLabels";
import { useLiveGameProgress } from "../lib/useLiveGameProgress";
import { useSetAccent } from "../lib/useAccent";
import { useCallback, useEffect, useState } from "react";

interface Props {
  game: Game;
  onBack:    () => void;
  onRefresh: () => Promise<void>;
  reportStatus: (text: string, warn?: boolean) => void;
  /** Bumped by App's sidebar refresh — re-pulls live progress on demand. */
  refreshNonce?: number;
}

export default function GameDetailPanel({ game, onBack, onRefresh, reportStatus, refreshNonce = 0 }: Props) {
  const accent = accentFor(game.theme_key);
  const avail  = availabilityLabel(game.availability);
  const mod    = modStateLabel(game.mod_state);

  // Paint the whole app background with this game's accent while the
  // detail panel is open; restore the neutral default on close.
  useSetAccent(accent);

  // "What's new" changelog modal.
  const [showChangelog, setShowChangelog] = useState(false);

  const [pathInput, setPathInput] = useState(game.install_path ?? "");
  const [busy, setBusy]           = useState<string | null>(null);
  // Bottom settings drawer — open by default (matches the page-2 design);
  // the user can collapse it for a clean cover + title + actions hero.
  const [settingsOpen, setSettingsOpen] = useState(true);

  // Live per-game progress — same /api/progress feed the home dashboard
  // uses. While the first fetch is in flight (`loaded === false`) we
  // render at 0% so the OLD static `game.progress` doesn't briefly
  // flash before the real number arrives.
  const { snap: liveProgress, loaded: liveLoaded } = useLiveGameProgress(game.id, {
    enabled:      isInFlight(game.availability),
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
      reportStatus(`נתיב נשמר: ${r.install_path ?? "—"}`);
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
  const [purchasePending, setPurchasePending] = useState(false);
  /** Burst-poll window after a known purchase trigger. While > 0 we
   *  re-fetch ownership every ~3s so the BUY → INSTALL CTA flips within
   *  seconds of a successful payment — without waiting for the 60s
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
  const [modUpd, setModUpd] = useState<{ updateAvailable?: boolean; latestVersion?: string | null } | null>(null);
  const refreshModUpd = useCallback(async () => {
    if (!gm?.modSlug || !gm.installed) { setModUpd(null); return; }
    try { setModUpd(await api.checkGameModUpdate(game.id)); }
    catch { setModUpd(null); }
  }, [game.id, gm?.modSlug, gm?.installed]);
  useEffect(() => { void refreshModUpd(); }, [refreshModUpd]);

  // ── Spider-Man 2 native applier (TOC patch — no Overstrike) ────────
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

  // ── Watch Dogs 2 native applier (FAT5 fat-redirect — no Overstrike) ──────
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

  // ── GTA V native OpenIV-free RPF7 applier — install + remove are BOTH async
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
  const [nativeUpd, setNativeUpd] = useState<{ updateAvailable?: boolean; latestVersion?: string | null } | null>(null);
  const nativeInstalled =
    (isSm2 && !!sm2?.installed) || (isWd2 && !!wd2?.installed) || (isGtav && !!gtav?.installed);
  const refreshNativeUpd = useCallback(async () => {
    if (!nativeInstalled) { setNativeUpd(null); return; }
    try { setNativeUpd(await api.checkGameModUpdate(game.id)); }
    catch { setNativeUpd(null); }
  }, [game.id, nativeInstalled]);
  useEffect(() => { void refreshNativeUpd(); }, [refreshNativeUpd]);

  // The version actually installed on disk (state.json), per game type, and
  // whether ANY newer version is available — drives the "גרסה מותקנת" stat row
  // + its highlight.
  const installedVersion =
    isSm2  ? (sm2?.version ?? null)
    : isWd2  ? (wd2?.version ?? null)
    : isGtav ? (gtav?.version ?? null)
    : (gm?.installed ? (gm?.version ?? null) : null);
  const anyUpdateAvailable = !!(modUpd?.updateAvailable || nativeUpd?.updateAvailable);

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
  // Re-pull when the mod's install state flips — 'auto' resolves off it.
  useEffect(() => { if (gm) void refreshLang(); }, [gm?.installed, refreshLang]);

  const langName = (n?: string | null) =>
    n === "hebrew" ? "עברית (ערבית)" : n === "english" ? "אנגלית"
      : n === "other" ? "שפה אחרת" : "—";

  // Friendly Hebrew for the backend's machine-readable language errors —
  // most commonly the game's settings file not existing yet (CP2077 writes
  // UserSettings.json only after its first launch).
  const langErr = (e?: string) => {
    if (!e) return "לא ידוע";
    if (e.includes("settings-file-missing") || e.includes("vars-not-found"))
      return "לא נמצאו הגדרות שפה — הפעל את המשחק פעם אחת ואז נסה שוב";
    if (e.includes("registry")) return "כתיבה להגדרות המשחק נכשלה";
    return e;
  };

  const handleSetLang = (mode: "auto" | "hebrew" | "english") => {
    if (langBusy) return;
    setLangBusy(true);
    void api.setGameLanguage(game.id, mode)
      .then((r) => {
        if (r.ok) reportStatus(`שפת המשחק עודכנה ל${langName(r.applied)} — ייכנס לתוקף בהפעלה הבאה`);
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

  // Burst poller — runs only when pollUntil > now. Stops as soon as
  // ownership flips true OR the window closes. Window is short (~90s)
  // and the interval is generous (3s) so we don't hammer the DB.
  useEffect(() => {
    if (pollUntil <= Date.now()) return;
    let cancelled = false;
    const onOwned = async () => {
      // Defensive double-check: confirm the purchase row is actually in the
      // user's purchases list. If not, the launcher caught a stale / sandbox /
      // cross-account positive — warn instead of silently flipping to "install".
      try {
        const p = await api.authGetMyPurchases();
        const found = p.rows.some((r) => r.game_id === game.id);
        reportStatus(found ? "✓ הרכישה אומתה — אפשר להתקין"
                           : "הרכישה זוהתה בשרת אך לא ברשימה האישית — נסה שוב בעוד דקה.", !found);
      } catch { /* swallow — UI already shows owned */ }
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
      const stillUnowned = isGtav ? (gtav && !gtav.owned) : (gm && !gm.owned);
      if (stillUnowned) {
        reportStatus("לא נמצאה רכישה. אם השלמת את התשלום, נסה שוב בעוד דקה.", true);
      }
    }, remaining);
    return () => window.clearTimeout(t);
  }, [pollUntil, gm, gtav, isGtav, reportStatus]);

  /** Kick the burst poller so the next 90s of refresh ticks happen
   *  automatically without the user clicking "already paid - refresh"
   *  repeatedly. Also used right after `openPurchasePage()` to catch a
   *  PayPal success the moment it lands. */
  const startPurchaseBurst = useCallback(() => {
    setPollUntil(Date.now() + 90_000);
  }, []);

  // Stream download/verify/install progress from the Python worker.
  // The worker emits a terminal "done" / "error" tick when the
  // background install thread finishes — that's what clears the bar
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
        void refreshGm();
        void refreshModUpd();
        void refreshSm2();
        void refreshWd2();
        void refreshGtav();
        void refreshNativeUpd();
        void onRefresh();
        reportStatus(p.detail || "התרגום הותקן והופעל");
      } else if (p.phase === "error") {
        setGmProgress(null);
        setGmBusy(false);
        setSm2Busy(false);
        setWd2Busy(false);
        setGtavBusy(false);
        void refreshGm();
        void refreshSm2();
        void refreshWd2();
        void refreshGtav();
        reportStatus(`שגיאה: ${p.detail}`, true);
      } else {
        setGmProgress(p);
      }
    });
  }, [refreshGm, refreshModUpd, refreshSm2, refreshWd2, refreshGtav, refreshNativeUpd, onRefresh, reportStatus]);

  const ils = (cents: number) => `${Math.round(cents / 100)} ₪`;

  const handleGmInstall = async () => {
    setGmBusy(true);
    setGmProgress({ phase: "download", pct: 0, detail: "מתחיל בהורדה…" });
    try {
      const r = await api.downloadAndInstallGameMod(game.id);
      // r resolves immediately — the install runs on a background
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
        r.ok ? (installed ? "התרגום הותקן מחדש" : "התרגום הושבת — הקבצים הועברו למטמון")
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
      "לנקות את מטמון התרגום? התרגום יוסר מתיקיית המשחק ומהמחשב — " +
      "התקנה מחדש תדרוש הורדה חוזרת."
    )) return;
    setGmBusy(true);
    try {
      const r = await api.clearGameModCache(game.id);
      setGm(r.state);
      reportStatus(r.ok ? "המטמון נוקה — התרגום הוסר מהמחשב" : `שגיאה: ${r.error}`, !r.ok);
      await onRefresh();
    } finally {
      setGmBusy(false);
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
      reportStatus("נפתח דף הרכישה בדפדפן — לאחר התשלום חזור לכאן והמוד יסונכרן");
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
        className="bg-brand-yellow hover:bg-yellow-300 text-brand-ink font-extrabold
                   px-8 py-3 rounded-xl text-lg transition
                   disabled:opacity-40 disabled:cursor-not-allowed
                   shadow-[0_10px_30px_-10px_rgba(255,247,0,0.6)]"
      >
        ▶ הפעל
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
      {isSm2 ? (
        /* Spider-Man 2 — native TOC patch (no Overstrike). The launcher
           ships the mod and applies/reverts it directly + flips the
           in-game language. */
        sm2 === null ? (
          <span className="self-center text-slate-400 text-sm">טוען מצב התרגום…</span>
        ) : !sm2.available ? (
          <span className="self-center text-amber-300/90 text-sm">חבילת התרגום אינה זמינה בגרסה זו</span>
        ) : !sm2.hasPath ? (
          <span className="self-center text-amber-300/90 text-sm">← הגדר תחילה את נתיב המשחק בהגדרות</span>
        ) : sm2.installed ? (
          <>
            {nativeUpd?.updateAvailable && (
              <button
                disabled={sm2Busy}
                onClick={handleSm2Install}
                className="font-bold px-6 py-3 rounded-xl text-brand-ink transition disabled:opacity-50"
                style={{ background: accent, boxShadow: `0 8px 20px -8px ${accent}` }}
              >
                {sm2Busy ? "מעדכן…" : `⬆ עדכן תרגום${nativeUpd.latestVersion ? ` → ${nativeUpd.latestVersion}` : ""}`}
              </button>
            )}
            <button
              disabled={sm2Busy}
              onClick={handleSm2Remove}
              className="bg-rose-500/25 hover:bg-rose-500/40 text-rose-200 font-bold
                         px-6 py-3 rounded-xl transition disabled:opacity-50 border border-rose-500/40"
            >
              {sm2Busy ? "מסיר…" : "הסרת התרגום"}
            </button>
          </>
        ) : (
          <button
            disabled={sm2Busy}
            onClick={handleSm2Install}
            className="bg-emerald-500/85 hover:bg-emerald-400 text-white font-bold
                       px-6 py-3 rounded-xl transition disabled:opacity-50"
          >
            {sm2Busy ? "מתקין…" : "התקנת תרגום"}
          </button>
        )
      ) : isWd2 ? (
        /* Watch Dogs 2 — native FAT5 fat-redirect (no Overstrike). The
           launcher ships the Hebrew files and redirects/reverts them
           directly. Activation is in-game (Written Language = Arabic). */
        wd2 === null ? (
          <span className="self-center text-slate-400 text-sm">טוען מצב התרגום…</span>
        ) : !wd2.available ? (
          <span className="self-center text-amber-300/90 text-sm">חבילת התרגום אינה זמינה בגרסה זו</span>
        ) : !wd2.hasPath ? (
          <span className="self-center text-amber-300/90 text-sm">← הגדר תחילה את נתיב המשחק בהגדרות</span>
        ) : wd2.installed ? (
          <>
            {nativeUpd?.updateAvailable && (
              <button
                disabled={wd2Busy}
                onClick={handleWd2Install}
                className="font-bold px-6 py-3 rounded-xl text-brand-ink transition disabled:opacity-50"
                style={{ background: accent, boxShadow: `0 8px 20px -8px ${accent}` }}
              >
                {wd2Busy ? "מעדכן…" : `⬆ עדכן תרגום${nativeUpd.latestVersion ? ` → ${nativeUpd.latestVersion}` : ""}`}
              </button>
            )}
            <button
              disabled={wd2Busy}
              onClick={handleWd2Remove}
              className="bg-rose-500/25 hover:bg-rose-500/40 text-rose-200 font-bold
                         px-6 py-3 rounded-xl transition disabled:opacity-50 border border-rose-500/40"
            >
              {wd2Busy ? "מסיר…" : "הסרת התרגום"}
            </button>
          </>
        ) : (
          <button
            disabled={wd2Busy}
            onClick={handleWd2Install}
            className="bg-emerald-500/85 hover:bg-emerald-400 text-white font-bold
                       px-6 py-3 rounded-xl transition disabled:opacity-50"
          >
            {wd2Busy ? "מתקין…" : "התקנת תרגום"}
          </button>
        )
      ) : isGtav ? (
        /* GTA V — native OpenIV-free RPF7 read-modify-write of the user's
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
              <button
                onClick={handlePurchase}
                className="self-start bg-brand-yellow hover:bg-yellow-300 text-brand-ink font-bold
                           px-6 py-3 rounded-xl transition"
              >
                רכישה — {ils(gtav.priceCents)}
              </button>
            )}
            <p className="text-sm text-amber-200/90 leading-relaxed max-w-md">
              אין תיקיית <b>mods</b>. ל-GTA המעודכן צריך את <b>OpenIV</b> פעם אחת ליצירת
              תיקיית המודים (בגלל הצפנת המשחק) — ואחרי זה התוכנה תנהל את התרגום לבד,
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
                {gtavBusy ? "מעדכן…" : `⬆ עדכן תרגום${nativeUpd.latestVersion ? ` → ${nativeUpd.latestVersion}` : ""}`}
              </button>
            )}
            <button
              disabled={gtavBusy}
              onClick={handleGtavRemove}
              className="bg-rose-500/25 hover:bg-rose-500/40 text-rose-200 font-bold
                         px-6 py-3 rounded-xl transition disabled:opacity-50 border border-rose-500/40"
            >
              {gtavBusy ? "מסיר…" : "הסרת התרגום"}
            </button>
          </>
        ) : (gtav.priceCents > 0 && !gtav.owned) ? (
          <>
            <button
              onClick={handlePurchase}
              className="bg-brand-yellow hover:bg-yellow-300 text-brand-ink font-bold
                         px-6 py-3 rounded-xl transition"
            >
              רכישה — {ils(gtav.priceCents)}
            </button>
            {purchasePending && (
              <button
                onClick={() => { startPurchaseBurst(); void refreshGtav(); }}
                className="bg-white/5 hover:bg-white/10 text-slate-200 font-bold
                           px-6 py-3 rounded-xl border border-white/10 transition"
                title={pollUntil > Date.now() ? "מחפש רכישה ברקע…" : undefined}
              >
                {pollUntil > Date.now() ? "בודק…" : "כבר שילמתי — רענן"}
              </button>
            )}
          </>
        ) : (
          <button
            disabled={gtavBusy}
            onClick={handleGtavInstall}
            className="bg-emerald-500/85 hover:bg-emerald-400 text-white font-bold
                       px-6 py-3 rounded-xl transition disabled:opacity-50"
          >
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
            <button
              disabled={gmBusy}
              onClick={handlePurchase}
              className="bg-brand-yellow hover:bg-yellow-300 text-brand-ink font-bold
                         px-6 py-3 rounded-xl transition disabled:opacity-50"
            >
              רכישה — {ils(gm.priceCents)}
            </button>
          )}
          {gm.priceCents > 0 && !gm.owned && purchasePending && (
            <button
              disabled={gmBusy}
              onClick={() => { startPurchaseBurst(); void refreshGm(); }}
              className="bg-white/5 hover:bg-white/10 text-slate-200 font-bold
                         px-6 py-3 rounded-xl border border-white/10 transition"
              title={pollUntil > Date.now() ? "מחפש רכישה ברקע…" : undefined}
            >
              {pollUntil > Date.now() ? "בודק…" : "כבר שילמתי — רענן"}
            </button>
          )}
          {gm.owned && !gm.installed && (
            <button
              disabled={gmBusy || !gm.hasPath}
              onClick={handleGmInstall}
              title={!gm.hasPath ? "הגדר תחילה את נתיב המשחק בהגדרות" : undefined}
              className="bg-emerald-500/85 hover:bg-emerald-400 text-white font-bold
                         px-6 py-3 rounded-xl transition disabled:opacity-50"
            >
              {gmBusy ? "מתקין…" : gm.cached ? "התקנה מחדש" : "הורד והתקן"}
            </button>
          )}
          {gm.owned && gm.installed && (
            <>
              {/* A newer mod version is on the server — re-download +
                  reinstall the latest (download_and_cache wipes the cache
                  first, so this pulls the fresh version). */}
              {modUpd?.updateAvailable && (
                <button
                  disabled={gmBusy}
                  onClick={handleGmInstall}
                  className="font-bold px-6 py-3 rounded-xl text-brand-ink transition
                             disabled:opacity-50"
                  style={{ background: accent, boxShadow: `0 8px 20px -8px ${accent}` }}
                >
                  {gmBusy ? "מעדכן…" : `⬆ עדכן תרגום${modUpd.latestVersion ? ` → ${modUpd.latestVersion}` : ""}`}
                </button>
              )}
              <button
                disabled={gmBusy}
                onClick={() => handleGmToggle(false)}
                className="bg-rose-500/25 hover:bg-rose-500/40 text-rose-200 font-bold
                           px-6 py-3 rounded-xl transition disabled:opacity-50 border border-rose-500/40"
              >
                הסרת התרגום
              </button>
              <button
                disabled={gmBusy}
                onClick={() => handleGmToggle(true)}
                className="bg-white/5 hover:bg-white/10 text-slate-200 font-bold
                           px-6 py-3 rounded-xl border border-white/10 transition
                           disabled:opacity-50"
              >
                התקנה מחדש
              </button>
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
              className="bg-emerald-500/85 hover:bg-emerald-400 text-white font-bold
                         px-6 py-3 rounded-xl transition disabled:opacity-50"
            >
              התקנת תרגום
            </button>
          )}
          {game.has_mod_support && game.is_installed && game.mod_state === "ACTIVE" && (
            <button
              disabled={busy !== null}
              onClick={handleDisable}
              className="bg-amber-500/85 hover:bg-amber-400 text-white font-bold
                         px-6 py-3 rounded-xl transition disabled:opacity-50"
            >
              השבתת תרגום
            </button>
          )}
          {/* "Remove" appears only when there are ACTUAL files on disk to remove */}
          {game.has_mod_support && game.is_installed &&
           (game.mod_state === "ACTIVE" || game.mod_state === "DISABLED") && (
            <button
              disabled={busy !== null}
              onClick={handleUninstall}
              className="bg-rose-500/25 hover:bg-rose-500/40 text-rose-200 font-bold
                         px-6 py-3 rounded-xl transition disabled:opacity-50
                         border border-rose-500/40"
            >
              הסרת התרגום
            </button>
          )}
        </>
      )}
    </>
  );

  // ── Settings rail body (path / language / cache / beta / stats) —
  //    a single neat vertical column for the fixed right-side panel. ──
  const settingsBody = (
    <div className="space-y-5">

      {/* install path + open folder + language */}
      <div className="space-y-4">
        <div>
          <label className="block text-xs text-slate-400 mb-1.5">נתיב התקנה</label>
          <input
            dir="ltr"
            value={pathInput}
            onChange={(e) => setPathInput(e.target.value)}
            placeholder="C:\Games\..."
            className="w-full bg-black/40 border border-white/10 focus:border-brand-yellow/50
                       rounded-lg px-3 py-2 text-sm text-slate-100 outline-none"
          />
          <div className="flex gap-2 mt-2">
            <button
              disabled={busy !== null}
              onClick={handleSavePath}
              className="flex-1 text-xs px-3 py-1.5 bg-brand-yellow text-brand-ink
                         font-bold rounded-lg hover:bg-yellow-300 disabled:opacity-50"
            >
              שמור
            </button>
            <button
              disabled={busy !== null}
              onClick={handleClearPath}
              className="flex-1 text-xs px-3 py-1.5 border border-white/10
                         text-slate-300 rounded-lg hover:bg-white/5 disabled:opacity-50"
            >
              נקה
            </button>
          </div>
        </div>

        <button
          disabled={!game.install_path}
          onClick={handleOpenFolder}
          className="w-full text-sm px-3 py-2 border border-white/10 text-slate-200
                     rounded-lg hover:border-brand-cyan/40 hover:bg-brand-cyan/5
                     disabled:opacity-40 disabled:cursor-not-allowed"
        >
          פתח תיקיית משחק
        </button>

        {/* In-game language switch — only for titles the launcher can
            flip (registry / settings-file). Lets the user play in Hebrew
            (Arabic slot) or English without editing anything by hand. */}
        {lang?.supported && (
          <div className="border-t border-white/5 pt-4">
            <label className="block text-xs text-slate-400 mb-2">שפת המשחק</label>
            <div className="flex gap-1.5">
              {([
                ["auto",    "אוטומטי"],
                ["hebrew",  "עברית"],
                ["english", "אנגלית"],
              ] as const).map(([m, label]) => {
                const active = (lang.mode ?? "auto") === m;
                return (
                  <button
                    key={m}
                    disabled={langBusy}
                    onClick={() => handleSetLang(m)}
                    title={
                      m === "auto"   ? "עברית כשהמוד פעיל, אחרת השפה שלפני המוד"
                      : m === "hebrew" ? "כפה עברית (סלוט ערבית)"
                      : "כפה אנגלית"
                    }
                    className={[
                      "flex-1 text-xs font-bold px-2 py-1.5 rounded-lg transition disabled:opacity-50",
                      active ? "text-brand-ink" : "bg-white/5 text-slate-300 hover:bg-white/10",
                    ].join(" ")}
                    style={active ? { background: accent } : undefined}
                  >
                    {label}
                  </button>
                );
              })}
            </div>
            <div className="flex items-center justify-between mt-2 text-[11px]">
              <button
                disabled={langBusy}
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
              {lang.current === "unknown"
                ? "המשחק עוד לא יצר קובץ הגדרות — הפעל אותו פעם אחת כדי שנוכל לקרוא ולהחליף את השפה. בחירת שפה כאן תיכנס לתוקף בהפעלה הבאה."
                : 'החלפת השפה נכנסת לתוקף בהפעלה הבאה של המשחק. "עברית" משתמש בסלוט הערבית של המשחק (כיווניות RTL מובנית).'}
            </p>
          </div>
        )}
      </div>

      {/* beta opt-in + cache control */}
      <div className="space-y-4">
        {/* Per-mod beta opt-in — only for GitHub-distributed mods (download
            mod or SM2), which can have pre-release versions. */}
        {(gm?.modSlug || isSm2) && <ModBetaToggle gameId={game.id} accent={accent} />}

        {/* Per-mod cache control — lives here in the game's own panel
            (not in global Settings). Removes the mod from the game
            folder AND wipes the launcher cache. */}
        {gm?.modSlug && (gm.cached || gm.installed) && (
          <button
            disabled={gmBusy}
            onClick={handleGmClearCache}
            className="w-full text-sm px-3 py-2 border border-rose-500/30 text-rose-200
                       rounded-lg hover:bg-rose-500/10
                       disabled:opacity-40 disabled:cursor-not-allowed"
          >
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
  const bannerSrc = game.bannerUrl || resolveCoverUrl(game.cover, game.id);

  return (
    <div className="h-full flex animate-scale-in">
      {/* ── FIXED right-side settings rail (RTL-first → appears on the RIGHT).
          Stays put, scrolls itself, never moves with the main content.
          Collapses to a thin ⚙ bar via the hide button. ──────────────────── */}
      {settingsOpen ? (
        <aside className="shrink-0 w-[330px] h-full flex flex-col glass border-l border-white/10">
          <div className="shrink-0 flex items-center justify-between px-4 py-3.5 border-b border-white/10">
            <button
              onClick={() => setSettingsOpen(false)}
              title="הסתר הגדרות"
              className="w-7 h-7 grid place-items-center rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition"
              aria-label="הסתר הגדרות"
            >⟩</button>
            <h3 className="text-white font-bold text-lg flex items-center gap-2">
              <span className="h-5 w-1.5 rounded-full" style={{ background: accent, boxShadow: `0 0 12px ${accent}99` }} />
              הגדרות
            </h3>
          </div>
          <div className="flex-1 min-h-0 overflow-y-auto p-4">{settingsBody}</div>
        </aside>
      ) : (
        <button
          onClick={() => setSettingsOpen(true)}
          title="הצג הגדרות"
          aria-label="הצג הגדרות"
          className="shrink-0 w-11 h-full glass border-l border-white/10 flex flex-col items-center justify-center gap-3
                     text-slate-300 hover:text-white hover:bg-white/5 transition"
        >
          <span className="text-xl" aria-hidden>⚙</span>
          <span className="text-xs font-bold [writing-mode:vertical-rl]">הגדרות</span>
        </button>
      )}

      {/* ── MAIN — scrollable content ─────────────────────────────────────── */}
      <div className="flex-1 min-w-0 h-full overflow-y-auto px-8 py-6">
      {/* ── CINEMATIC HERO BANNER (wide backdrop + logo, Steam-style) ──── */}
      <div className="relative -mx-8 -mt-6 mb-6 h-48 overflow-hidden">
        {/* Backdrop: banner_url, or a blurred/zoomed cover fallback. */}
        <img
          src={bannerSrc}
          alt=""
          aria-hidden
          draggable={false}
          className={`absolute inset-0 w-full h-full object-cover ${game.bannerUrl ? "" : "scale-110"}`}
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
            <img src={game.logoUrl} alt={game.titleEn} draggable={false}
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
      <div className="grid grid-cols-[minmax(220px,260px)_1fr_320px] gap-6 items-start">

        {/* Actions column — stacked top-right */}
        <div className="flex flex-col gap-3 self-start">
          {actionButtons}
        </div>

        {/* Info column — title, badges, text, progress, contextual notes.
            The banner above carries the English title/logo; here we show the
            Hebrew title (complementary, not a duplicate). */}
        <div className="flex flex-col">
          <h1 className="text-4xl font-extrabold leading-tight mb-3 text-right text-white">
            {game.titleHe || game.titleEn}
          </h1>

          {(() => {
            // Unified, game-agnostic status chips so EVERY game renders the
            // SAME set — CP2077's download mod, SM2's native patch, and any
            // future title. The old per-backend branches showed different
            // labels ("תרגום פעיל" vs "תרגום מותקן") and only added "נרכש"
            // for CP2077, so two purchased games looked different.
            const installed = isSm2
              ? !!sm2?.installed
              : isWd2
                ? !!wd2?.installed
                : isGtav
                  ? !!gtav?.installed
                  : gm?.modSlug ? gm.installed : game.mod_state === "ACTIVE";
            const cached  = !isSm2 && !isWd2 && !isGtav && !!gm?.cached;
            const paid    = (gm?.priceCents ?? 0) > 0;
            const owned   = !!gm?.owned;
            const ll      = lang?.current ?? game.currentLanguage;
            const stStyle = installed
              ? { color: "#86efac", background: "rgba(34,197,94,0.18)", borderColor: "rgba(34,197,94,0.45)" }
              : cached
                ? { color: "#fcd34d", background: "rgba(245,158,11,0.16)", borderColor: "rgba(245,158,11,0.4)" }
                : { color: "#cbd5e1", background: "rgba(148,163,184,0.18)", borderColor: "rgba(148,163,184,0.35)" };
            return (
              <div className="flex gap-2 mb-5 justify-start flex-wrap items-center">
                {/* availability — skip the redundant "זמין" on an available
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
                {ll && ll !== "unknown" && (
                  <span className="px-3 py-1 rounded-full text-xs font-semibold ring-1 ring-sky-400/30 bg-sky-500/15 text-sky-200">
                    שפה: {langName(ll)}
                  </span>
                )}
                {game.has_mod_support && (
                  <span className="px-3 py-1 rounded-full text-xs font-semibold ring-1" style={stStyle}>
                    {installed ? "תרגום מותקן" : cached ? "תרגום במטמון" : "תרגום לא מותקן"}
                  </span>
                )}
                {(modUpd?.updateAvailable || nativeUpd?.updateAvailable) && (
                  <span className="px-3 py-1 rounded-full text-xs font-semibold ring-1 animate-pulse"
                        style={{ color: accent, background: `${accent}22`, borderColor: `${accent}66` }}>
                    ⬆ עדכון זמין
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

          {/* Progress (in-progress games) — prefers the live /api/progress
              feed (current phase + processed/total) over the static
              `game.progress` catalog value. */}
          {isInFlight(game.availability) && (() => {
            const usingLive = liveProgress && liveProgress.total > 0;
            // First-paint protection: while the live fetch is in flight
            // (`!liveLoaded`) render 0% / a neutral label so the OLD
            // static value doesn't flash before the real one arrives.
            const pct = !liveLoaded
              ? 0
              : usingLive
                ? (liveProgress!.processed / liveProgress!.total) * 100
                : (game.progress ?? 0);
            const label = !liveLoaded
              ? "טוען נתונים..."
              : usingLive
                ? resolvePhaseHeadline(liveProgress!.phase, liveProgress!.phaseLabelHe)
                : "התקדמות תרגום";
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
                <div className="h-2 bg-white/5 rounded-full overflow-hidden">
                  <div
                    className="h-full transition-all duration-700"
                    style={{ width: `${pct}%`, background: accent }}
                  />
                </div>
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

          {/* Watch Dogs 2 — in-game activation reminder (Arabic slot). */}
          {isWd2 && wd2?.installed && (
            <p className="mt-2 text-xs text-amber-200/90 leading-relaxed bg-amber-500/10
                          border border-amber-500/25 rounded-xl p-3">
              להצגת העברית: במשחק היכנס ל-Settings → Written Language ובחר
              <span dir="ltr"> العربية (Arabic)</span>, והפעל את המשחק עם
              <span dir="ltr" className="font-mono"> -eac_launcher</span>.
              התרגום מכסה את ממשק המשחק והכתוביות; כיווניות RTL מובנית דרך סלוט הערבית.
            </p>
          )}

          {/* GTA V — installed: how it works + in-game activation. */}
          {isGtav && gtav?.installed && (
            <p className="mt-2 text-xs text-emerald-200/90 leading-relaxed bg-emerald-500/10
                          border border-emerald-500/25 rounded-xl p-3">
              הותקן ישירות לתיקיית ה-mods שלך — <b>בלי לפגוע במודים אחרים</b>. "הסרת התרגום"
              מחזירה רק את הטקסט לאנגלית ומשאירה את שאר המודים שלך. להצגת העברית: במשחק היכנס
              ל-Settings → Language ובחר <span dir="ltr"> American</span>.
            </p>
          )}

          {/* GTA V — separate, explicitly-warned full restore from the install-time
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

          {/* Download / install / patch progress (distributed mod OR SM2/WD2/GTA). */}
          {(gm?.modSlug || isSm2 || isWd2 || isGtav) && (gmBusy || sm2Busy || wd2Busy || gtavBusy || gmProgress) && (
            <div className="mt-4">
              <div className="flex justify-between text-[11px] mb-1.5">
                <span dir="ltr" className="font-mono text-slate-300">
                  {gmProgress?.detail || "…"}
                </span>
                <span className="font-bold" style={{ color: accent }}>
                  {gmProgress?.phase === "verify"  ? "מאמת…"
                    : gmProgress?.phase === "apply" ? "מתקין…"
                    : `${Math.min(100, Math.max(0, gmProgress?.pct ?? 0)).toFixed(0)}%`}
                </span>
              </div>
              <div className="h-2 bg-white/5 rounded-full overflow-hidden ring-1 ring-white/5">
                <div
                  className="h-full rounded-full transition-all duration-200"
                  style={{
                    width: `${Math.min(100, Math.max(0, gmProgress?.pct ?? 0))}%`,
                    background: accent,
                    boxShadow: `0 0 12px ${accent}80`,
                  }}
                />
              </div>
            </div>
          )}
        </div>

        {/* Cover — large, on the left */}
        <div className="self-start">
          <div className="aspect-[2/3] rounded-2xl overflow-hidden ring-1 ring-white/10
                          shadow-[0_25px_60px_-15px_rgba(0,0,0,0.8)]">
            <img
              src={resolveCoverUrl(game.cover, game.id)}
              alt={game.titleEn}
              className="w-full h-full object-cover"
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
        title={game.titleHe || game.titleEn}
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
  const [open, setOpen] = useState(false);
  useEffect(() => {
    let alive = true;
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
    })();
    return () => { alive = false; };
  }, [gameId]);

  if (!rows || rows.length === 0) return null;
  const shown = open ? rows : rows.slice(0, 3);

  return (
    <div className="glass rounded-2xl mt-6 overflow-hidden">
      <div className="px-5 py-3.5 flex items-center justify-between border-b border-white/5">
        <span className="text-xs text-slate-500">{rows.length} גרסאות</span>
        <h3 className="text-white font-bold text-lg flex items-center gap-2">
          <span className="h-5 w-1.5 rounded-full" style={{ background: accent, boxShadow: `0 0 12px ${accent}99` }} />
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
                className="w-full py-2.5 text-xs text-slate-400 hover:text-white hover:bg-white/5 transition border-t border-white/5">
          {open ? "הצג פחות ▲" : `הצג את כל ${rows.length} הגרסאות ▼`}
        </button>
      )}
    </div>
  );
}

function Row({ k, v, highlight = false }: { k: string; v: string; highlight?: boolean }) {
  return (
    <div className="flex items-center justify-between">
      <span className={highlight ? "text-amber-300 font-semibold" : "text-slate-200"}>{v}</span>
      <span className="text-slate-500">{k}</span>
    </div>
  );
}

/** Per-mod "receive beta versions" toggle. The effective value is the per-mod
 *  override if the user set one, otherwise the global Settings flag — shown
 *  explicitly so it's never ambiguous which is in effect. */
function ModBetaToggle({ gameId, accent }: { gameId: string; accent: string }) {
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
        <div className="text-sm font-semibold text-slate-200">קבל גרסאות בטא למשחק זה</div>
        <div className="text-xs text-slate-400 leading-relaxed">
          גרסאות מוקדמות — חדשות יותר אך עשויות להיות פחות יציבות.
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
