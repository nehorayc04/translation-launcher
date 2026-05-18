// "Big Picture" mode — large cover left, descriptive text + actions, right
// settings sidebar (install path + mod toggles). Rendered inside the main
// content area (NOT a separate window).
import type { Game } from "../lib/types";
import { accentFor, availabilityLabel, modStateLabel } from "../lib/theme";
import { resolveCoverUrl } from "../lib/coverUrl";
import { api } from "../lib/eel";
import { resolvePhaseHeadline } from "../lib/phaseLabels";
import { useLiveGameProgress } from "../lib/useLiveGameProgress";
import { useState } from "react";

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
    enabled:      game.availability === "in-progress",
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

  const handleEnable    = () => wrap("mod", async () => {
    const r = await api.enableMod(game.id);
    reportStatus(r.ok ? `התרגום הופעל (${filesHe(r.count)})` : `שגיאה: ${r.error}`, !r.ok);
  });
  const handleDisable   = () => wrap("mod", async () => {
    const r = await api.disableMod(game.id);
    reportStatus(r.ok ? `התרגום הושבת (${filesHe(r.count)})` : `שגיאה: ${r.error}`, !r.ok);
  });
  const handleUninstall = () => wrap("mod", async () => {
    if (!confirm("האם להסיר לצמיתות את התרגום העברי מתיקיית המשחק?")) return;
    const r = await api.uninstallMod(game.id);
    reportStatus(r.ok ? `התרגום הוסר (${filesHe(r.count)})` : `שגיאה: ${r.error}`, !r.ok);
  });

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

          <div className="flex gap-2 mb-5 justify-end">
            <span className={`px-3 py-1 rounded-full text-xs font-semibold ${avail.tone}`}>
              {avail.text}
            </span>
            <span className="px-3 py-1 rounded-full text-xs bg-black/75 backdrop-blur-md
                             text-slate-200 ring-1 ring-white/15">
              {game.version}
            </span>
            {game.has_mod_support && (
              <span className={`px-3 py-1 rounded-full text-xs font-semibold ${mod.tone}`}>
                {mod.text}
              </span>
            )}
          </div>

          <p className="text-lg text-slate-200 mb-3 leading-relaxed">{game.tagline}</p>
          <p className="text-slate-400 leading-relaxed mb-6">{game.description}</p>

          {/* Progress (in-progress games) — prefers the live /api/progress
              feed (current phase + processed/total) over the static
              `game.progress` catalog value. */}
          {game.availability === "in-progress" && (() => {
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

            {/* Translation actions — only when the game is installed AND a
                mod package exists. NOT_AVAILABLE titles get a disabled chip. */}
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
          </div>
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
