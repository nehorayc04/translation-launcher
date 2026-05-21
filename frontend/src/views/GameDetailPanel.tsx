// "Big Picture" mode — large cover left, descriptive text + actions, right
// settings sidebar (install path + mod toggles). Rendered inside the main
// content area (NOT a separate window).
import { isInFlight, type Game } from "../lib/types";
import { accentFor, availabilityLabel, modStateLabel } from "../lib/theme";
import { resolveCoverUrl } from "../lib/coverUrl";
import { api, onModProgress } from "../lib/eel";
import type { GameModState, ModProgress } from "../lib/eel";
import { resolvePhaseHeadline } from "../lib/phaseLabels";
import { useLiveGameProgress } from "../lib/useLiveGameProgress";
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

  const [pathInput, setPathInput] = useState(game.install_path ?? "");
  const [busy, setBusy]           = useState<string | null>(null);

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

  const refreshGm = useCallback(async () => {
    try { setGm(await api.getGameModState(game.id)); }
    catch { setGm(null); }
  }, [game.id]);
  useEffect(() => { void refreshGm(); }, [refreshGm]);

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
        void refreshGm();
        void onRefresh();
        reportStatus("התרגום הותקן והופעל");
      } else if (p.phase === "error") {
        setGmProgress(null);
        setGmBusy(false);
        void refreshGm();
        reportStatus(`שגיאה: ${p.detail}`, true);
      } else {
        setGmProgress(p);
      }
    });
  }, [refreshGm, onRefresh, reportStatus]);

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
    await api.openPurchasePage(game.id);
    setPurchasePending(true);
    reportStatus("נפתח דף הרכישה בדפדפן — לאחר התשלום לחץ 'כבר שילמתי — רענן'");
  };

  return (
    <div className="h-full overflow-y-auto px-8 py-6 animate-scale-in">
      {/* Back */}
      <button
        onClick={onBack}
        className="mb-4 text-slate-300 hover:text-brand-yellow transition flex items-center gap-2"
      >
        ← חזרה לספרייה
      </button>

      <div className="grid grid-cols-[380px_1fr_300px] gap-6">
        {/* Cover */}
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

        {/* Info column */}
        <div className="flex flex-col">
          <h1
            dir="ltr"
            className="text-5xl font-display font-extrabold leading-tight mb-3 text-left"
            style={{ color: accent }}
          >
            {game.titleEn}
          </h1>

          <div className="flex gap-2 mb-5 justify-end flex-wrap">
            <span className={`px-3 py-1 rounded-full text-xs font-semibold ${avail.tone}`}>
              {avail.text}
            </span>
            <span className="px-3 py-1 rounded-full text-xs bg-black/75 backdrop-blur-md
                             text-slate-200 ring-1 ring-white/15">
              {game.version}
            </span>
            {gm?.modSlug ? (
              <>
                <span
                  className="px-3 py-1 rounded-full text-xs font-semibold ring-1"
                  style={{
                    color:      gm.installed ? "#86efac" : gm.cached ? "#fcd34d" : "#cbd5e1",
                    background: gm.installed ? "rgba(34,197,94,0.18)"
                              : gm.cached    ? "rgba(245,158,11,0.16)"
                                             : "rgba(148,163,184,0.18)",
                    borderColor: gm.installed ? "rgba(34,197,94,0.45)"
                               : gm.cached    ? "rgba(245,158,11,0.4)"
                                              : "rgba(148,163,184,0.35)",
                  }}
                >
                  {gm.installed ? "תרגום מותקן" : gm.cached ? "תרגום במטמון" : "תרגום לא מותקן"}
                </span>
                {gm.priceCents > 0 && gm.owned && (
                  <span className="px-3 py-1 rounded-full text-xs font-semibold ring-1
                                   ring-emerald-400/40 bg-emerald-500/20 text-emerald-200">
                    ✓ נרכש
                  </span>
                )}
              </>
            ) : (
              game.has_mod_support && (
                <span className={`px-3 py-1 rounded-full text-xs font-semibold ${mod.tone}`}>
                  {mod.text}
                </span>
              )
            )}
          </div>

          <p className="text-lg text-slate-200 mb-3 leading-relaxed">{game.tagline}</p>
          <p className="text-slate-400 leading-relaxed mb-6">{game.description}</p>

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

          {/* Big action buttons.
              RTL alignment: `justify-start` aligns to the flex *start*, which
              in RTL is the visual RIGHT side — i.e. closest to the cover art.
              PLAY is the first source element, so it ends up at the rightmost
              position. Translation actions follow to its left. */}
          <div className="flex gap-3 flex-wrap justify-start mt-auto">
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
                gm.modSlug set  → download-distributed mod (CP2077): the
                  buy / download+install / disable / reinstall flow.
                otherwise       → the legacy on-disk enable/disable/remove. */}
            {gm?.modSlug ? (
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
                    onClick={refreshGm}
                    className="bg-white/5 hover:bg-white/10 text-slate-200 font-bold
                               px-6 py-3 rounded-xl border border-white/10 transition"
                  >
                    כבר שילמתי — רענן
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
                    <button
                      disabled={gmBusy}
                      onClick={() => handleGmToggle(false)}
                      className="bg-amber-500/85 hover:bg-amber-400 text-white font-bold
                                 px-6 py-3 rounded-xl transition disabled:opacity-50"
                    >
                      השבתה
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
          </div>

          {/* Download / install progress for the distributed mod. */}
          {gm?.modSlug && (gmBusy || gmProgress) && (
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

        {/* Settings sidebar */}
        <div className="glass rounded-2xl p-5 self-start space-y-5">
          <h3 className="text-white font-bold text-lg">הגדרות</h3>

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

          {/* Status summary */}
          <div className="border-t border-white/5 pt-4 text-xs space-y-1.5">
            <Row k="זמינות"     v={avail.text} />
            <Row k="גרסה"       v={game.version} />
            <Row k="התקנה"      v={game.is_installed ? "מותקן" : "לא נמצא"} />
            <Row k="תמיכת מוד"  v={game.has_mod_support ? "כן" : "לא"} />
            {game.has_mod_support && <Row k="סטטוס מוד" v={mod.text} />}
          </div>
        </div>
      </div>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-slate-200">{v}</span>
      <span className="text-slate-500">{k}</span>
    </div>
  );
}
