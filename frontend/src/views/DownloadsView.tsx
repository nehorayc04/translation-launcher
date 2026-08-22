// "הורדות ועדכונים" - system updates + translation updates with a live
// HTML/CSS progress bar driven by Python's update_download_progress push.
// The list itself is SWR-cached: instant first paint from the on-disk
// snapshot, then quietly refreshed in the background.
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  api,
  onModProgress,
  type UpdateItem,
  type LauncherUpdateInfo,
  type LauncherUpdateProgress,
  type ModUpdate,
  type ModProgress,
} from "../lib/eel";
import { useDownloadProgress } from "../lib/useDownloadProgress";
import { useActivity } from "../lib/notifications";
import { useSWRSource } from "../lib/useSWRSource";
import LiquidWave from "../components/LiquidWave";
import {
  IconOptHdrDownloads,
  IconOptHdrModUpdates,
  IconOptHdrSystemUpdates,
  IconOptHdrTranslationUpdates,
  IconOptBtnCheckAgain,
  IconOptBadgeInstalled,
  IconOptEmptyNoUpdates,
  IconOptBtnUpdateMod,
  IconOptBtnRetryDownload,
  IconOptBtnDownloadUpdate,
  IconOptBtnSelfUpdate,
  IconAppDownloadsSelfUpdateEmoji,
} from "../components/UiIcons";

interface Props {
  /** Bumped by App whenever the sidebar refresh button completes - forces
   *  this view to re-pull listUpdates() even if the SWR cache is hot. */
  refreshNonce?: number;
}

export default function DownloadsView({ refreshNonce = 0 }: Props) {
  const { data, loading, refetch } = useSWRSource<UpdateItem[]>("updates", api.listUpdates);
  const items    = data ?? [];
  const progress = useDownloadProgress();

  useEffect(() => {
    if (refreshNonce > 0) refetch();
  }, [refreshNonce, refetch]);

  const [system, translations] = useMemo(() => {
    const s = items.filter((u) => u.kind === "system");
    const t = items.filter((u) => u.kind === "translation");
    return [s, t];
  }, [items]);

  // ── Installed game-mod updates (newer version on the server) ──────
  // A separate live source from the static updates catalog - compares each
  // installed translation mod's version against its manifest.
  const [modUpdates, setModUpdates] = useState<ModUpdate[]>([]);
  const [updatingId, setUpdatingId] = useState<string | null>(null);
  const [muProgress, setMuProgress] = useState<ModProgress | null>(null);

  const loadModUpdates = useCallback(async () => {
    try { setModUpdates(await api.getModUpdates()); }
    catch { setModUpdates([]); }
  }, []);
  useEffect(() => { void loadModUpdates(); }, [loadModUpdates, refreshNonce]);

  // The mod download/install runs on a background worker and streams over the
  // shared mod_install_progress channel; refresh the list when it finishes.
  useEffect(() => {
    return onModProgress((p) => {
      if (p.phase === "done") {
        setUpdatingId(null);
        setMuProgress(null);
        void loadModUpdates();
      } else if (p.phase === "error") {
        setUpdatingId(null);
        setMuProgress(null);
      } else {
        setMuProgress(p);
      }
    });
  }, [loadModUpdates]);

  const updateMod = useCallback(async (gameId: string, kind?: "download" | "native") => {
    setUpdatingId(gameId);
    setMuProgress({ phase: "download", pct: 0, detail: "מתחיל…" });
    try {
      // Native appliers (SM2/WD2/GTAV) update by re-applying via their own
      // install RPC (re-install == update); download mods re-download + install.
      // All stream over the shared mod_install_progress channel.
      let r: { ok: boolean; error?: string };
      if (kind === "native") {
        r = gameId === "spiderman2" ? await api.installSpiderman2Mod()
          : gameId === "watchdogs2" ? await api.installWatchdogs2Mod()
          : gameId === "gtav"       ? await api.installGtavMod()
          : gameId === "gowragnarok" ? await api.installGowrMod()
          : gameId === "hogwarts"    ? await api.installHogwartsMod()
          : gameId === "witcher3"    ? await api.installWitcher3Mod()
          : gameId === "plague-tale-requiem" ? await api.installPlagueTaleMod()
          : gameId === "virtualdj"   ? await api.applyVirtualdjTranslation()
          : await api.downloadAndInstallGameMod(gameId);
      } else {
        r = await api.downloadAndInstallGameMod(gameId);
      }
      if (!r.ok) { setUpdatingId(null); setMuProgress(null); }
    } catch {
      setUpdatingId(null); setMuProgress(null);
    }
  }, []);

  const nothing = items.length === 0 && modUpdates.length === 0;

  return (
    <div className="h-full overflow-y-auto px-8 py-6 animate-fade-in">
      <div className="mb-6 animate-rise">
        <h1 className="text-3xl font-extrabold text-right inline-flex items-center gap-1.5"><IconOptHdrDownloads width={20} className="shrink-0 opacity-90" style={{ color: "#22c55e" }} /><span style={{ background: "linear-gradient(90deg, #ffffff 0%, #22c55e 100%)", WebkitBackgroundClip: "text", backgroundClip: "text", color: "transparent" }}>הורדות ועדכונים</span></h1>
      </div>

      {/* Persistent self-update panel - always on top, independent of
          the translation/system update list below. */}
      <SelfUpdatePanel />

      {loading ? (
        <Loader />
      ) : nothing ? (
        <Empty />
      ) : (
        <div className="space-y-8">
          <ModUpdatesSection
            updates={modUpdates}
            updatingId={updatingId}
            progress={muProgress}
            onUpdate={updateMod}
          />
          <Section title="עדכוני מערכת"     accent="#fff700" items={system}       progress={progress} />
          <Section title="עדכוני תרגומים"  accent="#00ffe0" items={translations} progress={progress} />
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Game-mod updates - installed translation mods with a newer version on
// the server. "עדכן" re-downloads + reinstalls the latest in place.
function ModUpdatesSection({
  updates, updatingId, progress, onUpdate,
}: {
  updates:    ModUpdate[];
  updatingId: string | null;
  progress:   ModProgress | null;
  onUpdate:   (gameId: string, kind?: "download" | "native") => void;
}) {
  if (updates.length === 0) return null;
  const accent = "#34d399";
  return (
    <section>
      <div className="flex items-center gap-3 mb-4">
        <span className="text-slate-400 text-sm">{updates.length}</span>
        <h2 className="text-xl font-bold text-white inline-flex items-center gap-1.5"><IconOptHdrModUpdates width={20} className="shrink-0 opacity-90" />עדכוני תרגום למשחקים</h2>
        <span className="h-[2px] flex-1 rounded-full opacity-30"
              style={{ background: `linear-gradient(to left, ${accent}, transparent)` }} />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {updates.map((u) => {
          const busy = updatingId === u.gameId;
          const anyBusy = updatingId !== null;
          const pct = Math.min(100, Math.max(0, progress?.pct ?? 0));
          return (
            <div key={u.gameId}
                 className="rounded-2xl p-4 border flex flex-col gap-3"
                 style={{ borderColor: `${accent}33`, background: `linear-gradient(135deg, ${accent}0e, transparent 70%), rgba(255,255,255,0.02)` }}>
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="font-bold text-white truncate">{u.titleEn}</div>
                  <div className="text-[12px] text-slate-400 mt-0.5" dir="ltr">
                    <span className="font-mono text-slate-300">v{u.installedVersion ?? "-"}</span>
                    {"  →  "}
                    <span className="font-mono" style={{ color: accent }}>v{u.latestVersion}</span>
                    {u.updateSource === "offline" && (
                      <span className="ms-2 text-[11px] text-slate-400" dir="rtl">
                        (מהחבילה האופליין - ללא אינטרנט)
                      </span>
                    )}
                  </div>
                </div>
                <button
                  disabled={anyBusy}
                  onClick={() => onUpdate(u.gameId, u.kind)}
                  className="shrink-0 px-4 py-2 rounded-xl text-sm font-bold text-brand-ink
                             transition hover:brightness-110 disabled:opacity-50
                             inline-flex items-center justify-center gap-1.5"
                  style={{ background: accent }}
                >
                  <IconOptBtnUpdateMod width={18} className="shrink-0 opacity-90" />
                  {busy ? "מעדכן…" : (u.updateSource === "offline" ? "עדכון אופליין" : "עדכן")}
                </button>
              </div>
              {busy && progress && (
                <div>
                  <div className="flex justify-between text-[11px] mb-1">
                    <span dir="ltr" className="font-mono text-slate-300 truncate">{progress.detail}</span>
                    <span className="font-bold" style={{ color: accent }}>
                      {progress.phase === "verify" ? "מאמת…" : progress.phase === "apply" ? "מתקין…" : `${pct.toFixed(0)}%`}
                    </span>
                  </div>
                  <LiquidWave
                    pct={progress.phase === "verify" || progress.phase === "apply" ? 100 : pct}
                    ratePerMin={48}
                    primary={accent}
                    secondary="#22c55e"
                    glow={accent}
                    height={42}
                  />

                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}

// ─────────────────────────────────────────────────────────────
// Self-update panel - checks the release feed, downloads the
// installer in-app (live progress), and runs it silently. No
// external installer window: the .exe runs with /VERYSILENT, its
// PrepareToInstall hook closes this process, and its [Run] entry
// relaunches the freshly-installed version.
function SelfUpdatePanel() {
  const [info, setInfo]         = useState<LauncherUpdateInfo | null>(null);
  const [checking, setChecking] = useState(true);
  // Brief LOCAL "starting" state for the gap between clicking and the first
  // progress event; once the GLOBAL store activity appears it takes over.
  const [starting, setStarting] = useState<LauncherUpdateProgress | null>(null);

  // ⭐ THE fix: the launcher-update progress lives in the GLOBAL notifications
  // store (subscribed once at App level), NOT this panel's local state - so
  // leaving this screen mid-download and coming back reflects the ONGOING
  // download instead of resetting to "עדכן עכשיו" while it silently finishes.
  const act = useActivity("launcher-update");
  const progress: LauncherUpdateProgress | null = act
    ? { phase: act.phase, pct: act.pct, detail: act.detail ?? "" }
    : starting;
  const updating = act ? act.active : !!starting;

  // Once the store activity exists, drop the local "starting" placeholder.
  useEffect(() => { if (act) setStarting(null); }, [act]);

  const check = useCallback(async () => {
    setChecking(true);
    setStarting(null);           // never clears the store activity (an ongoing DL survives)
    try {
      setInfo(await api.getLauncherUpdateInfo());
    } catch (e) {
      setInfo({
        currentVersion: "-", latestVersion: "-", updateAvailable: false,
        downloadUrl: null, sizeBytes: 0, sizeMb: 0, notes: "", sha256: null,
        error: String(e),
      });
    } finally {
      setChecking(false);
    }
  }, []);

  useEffect(() => { check(); }, [check]);

  const cancelUpdate = useCallback(async () => {
    try {
      await api.cancelLauncherUpdate();
    } catch (e) {
      console.error("[self-update] cancel failed", e);
    }
  }, []);

  const startUpdate = async () => {
    setStarting({ phase: "download", pct: 0, detail: "מתחיל בהורדה…" });
    try {
      const r = await api.startLauncherUpdate();
      if (!r.ok) {
        setStarting({ phase: "error", pct: 0, detail: r.error || "כשל בהפעלת העדכון" });
      }
    } catch (e) {
      setStarting({ phase: "error", pct: 0, detail: String(e) });
    }
  };

  const failed     = progress?.phase === "error";
  const cancelled  = progress?.phase === "cancelled";
  const launching  = progress?.phase === "launch";
  const verifying  = progress?.phase === "verify";
  const downloading = progress?.phase === "download";
  // The user can cancel during download/verify. Once the installer
  // process has been launched we no longer offer the button - the
  // install is the installer's job to finish or fail.
  const cancellable = updating && (downloading || verifying);
  const barPct      = Math.min(100, Math.max(0, progress?.pct ?? 0));
  const accent      = info?.updateAvailable ? "#fff700" : "#00ffe0";

  return (
    <div
      className="rounded-2xl p-5 mb-8 border relative overflow-hidden"
      style={{
        borderColor: `${accent}44`,
        background: `linear-gradient(135deg, ${accent}0e, transparent 70%), rgba(255,255,255,0.02)`,
      }}
    >
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <IconAppDownloadsSelfUpdateEmoji width={17} className="shrink-0 opacity-90" />
            <h2 className="text-lg font-bold text-white">עדכון התוכנה</h2>
          </div>
          <p className="text-[12px] text-slate-400 mt-1">
            גרסה מותקנת:{" "}
            <span className="font-mono text-slate-200" dir="ltr">
              v{info?.currentVersion ?? "-"}
            </span>
            {info && info.latestVersion !== info.currentVersion && (
              <>
                {"  ·  "}גרסה אחרונה:{" "}
                <span className="font-mono" style={{ color: accent }} dir="ltr">
                  v{info.latestVersion}
                </span>
              </>
            )}
            {/* Same version, different build - the in-app updater detected a
                re-released build via its build-id. No version delta to show,
                so spell out that an update is still waiting. */}
            {info?.updateAvailable && info.latestVersion === info.currentVersion && (
              <>
                {"  ·  "}
                <span className="font-bold" style={{ color: accent }}>
                  עדכון זמין - build חדש
                </span>
              </>
            )}
          </p>
        </div>

        {/* Right-side action / status */}
        {!updating && !checking && (
          info?.updateAvailable ? (
            <button
              onClick={startUpdate}
              className="px-5 py-2.5 rounded-xl text-sm font-bold transition
                         text-brand-ink hover:brightness-110 shrink-0
                         shadow-[0_6px_15px_-6px_rgba(255,247,0,0.5)]
                         inline-flex items-center justify-center gap-1.5"
              style={{ background: accent }}
            >
              <IconOptBtnSelfUpdate width={18} className="shrink-0 opacity-90" />
              עדכן עכשיו{info.sizeMb ? ` · ${info.sizeMb.toFixed(0)} MB` : ""}
            </button>
          ) : info?.error ? (
            <button
              onClick={check}
              className="px-4 py-2 rounded-xl text-sm font-bold transition shrink-0
                         border border-white/15 text-slate-200 hover:bg-white/5
                         inline-flex items-center justify-center gap-1.5"
            >
              <IconOptBtnCheckAgain width={18} className="shrink-0 opacity-90" />
              בדוק שוב
            </button>
          ) : (
            // Up to date - show the status badge with a manual re-check
            // button to its LEFT (dir=ltr → refresh is the left-most element
            // at the frame's left edge).
            <div className="flex items-center gap-2 shrink-0" dir="ltr">
              <button
                onClick={check}
                title="בדוק שוב אם יש עדכון"
                aria-label="בדוק שוב אם יש עדכון"
                className="w-9 h-9 grid place-items-center rounded-xl border border-white/15
                           text-slate-300 hover:bg-white/5 hover:text-white transition text-base leading-none"
              >
                ↻
              </button>
              <span className="text-[13px] font-bold px-4 py-2 rounded-xl
                               bg-emerald-500/15 text-emerald-200 ring-1 ring-emerald-400/30">
                ✓ התוכנה מעודכנת
              </span>
            </div>
          )
        )}
        {checking && (
          <span className="text-[12px] text-slate-400 flex items-center gap-2 shrink-0">
            <span className="w-4 h-4 border-2 border-slate-500 border-t-transparent rounded-full animate-spin" />
            בודק עדכונים…
          </span>
        )}
      </div>

      {/* Release notes for an available update */}
      {!updating && info?.updateAvailable && info.notes && (
        <p className="mt-3 text-[12px] leading-relaxed text-slate-300 border-t border-white/5 pt-3">
          {info.notes}
        </p>
      )}

      {/* Check-failed note */}
      {!updating && !checking && info?.error && (
        <p className="mt-3 text-[12px] text-amber-300/90 border-t border-white/5 pt-3">
          לא ניתן לבדוק עדכונים כרגע - בדוק את החיבור לאינטרנט ונסה שוב.
        </p>
      )}

      {/* Live progress while updating */}
      {(updating || failed || cancelled) && progress && (
        <div className="mt-4 border-t border-white/5 pt-4">
          <div className="flex justify-between items-center gap-3 text-[11px] mb-1.5">
            <span dir="ltr" className="font-mono text-slate-300 truncate flex-1">
              {progress.detail}
            </span>
            <div className="flex items-center gap-2 shrink-0">
              <span
                className="font-bold"
                style={{
                  color: failed     ? "#f87171"
                       : cancelled  ? "#94a3b8"
                       : accent,
                }}
              >
                {failed     ? "שגיאה"
                  : cancelled ? "בוטל"
                  : launching ? "מתקין…"
                  : verifying ? "מאמת…"
                  : `${barPct.toFixed(0)}%`}
              </span>
              {cancellable && (
                <button
                  onClick={cancelUpdate}
                  className="px-2.5 py-1 rounded-md text-[11px] font-bold transition
                             border border-rose-400/30 text-rose-200 hover:bg-rose-500/15"
                >
                  ביטול
                </button>
              )}
            </div>
          </div>
          {failed || cancelled ? (
            <div className="h-2 bg-white/5 rounded-full overflow-hidden ring-1 ring-white/5">
              <div
                className="h-full rounded-full transition-all duration-200"
                style={{ width: "100%", background: failed ? "#ef4444" : "#64748b" }}
              />
            </div>
          ) : (
            // Flowing liquid wave - identical to the site's live-progress bar.
            <LiquidWave
              pct={launching || verifying ? 100 : barPct}
              ratePerMin={48}
              primary={accent}
              secondary={accent === "#fff700" ? "#00ffe0" : "#22c55e"}
              glow={accent}
              height={46}
            />
          )}
          {(failed || cancelled) && (
            <button
              onClick={startUpdate}
              className="mt-3 px-4 py-1.5 rounded-lg text-[12px] font-bold transition
                         bg-rose-500/15 text-rose-200 hover:bg-rose-500/30"
            >
              {cancelled ? "התחל מחדש" : "נסה שוב"}
            </button>
          )}
          {launching && (
            <p className="mt-2 text-[11px] text-slate-400">
              האפליקציה תיסגר אוטומטית ותיפתח מחדש בגרסה החדשה - אין צורך לעשות דבר.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
function Section({
  title, accent, items, progress,
}: {
  title:    string;
  accent:   string;
  items:    UpdateItem[];
  progress: Map<string, { pct: number; speed: string; state: string }>;
}) {
  if (items.length === 0) return null;
  return (
    <section>
      <div className="flex items-center gap-3 mb-4">
        <span className="text-slate-400 text-sm">{items.length}</span>
        <h2 className="text-xl font-bold text-white inline-flex items-center gap-1.5">
          {title === "עדכוני מערכת" ? (
            <IconOptHdrSystemUpdates width={20} className="shrink-0 opacity-90" />
          ) : title === "עדכוני תרגומים" ? (
            <IconOptHdrTranslationUpdates width={20} className="shrink-0 opacity-90" />
          ) : null}
          {title}
        </h2>
        <span
          className="h-[2px] flex-1 rounded-full opacity-30"
          style={{ background: `linear-gradient(to left, ${accent}, transparent)` }}
        />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {items.map((u) => (
          <UpdateCard key={u.id} item={u} progress={progress.get(u.id)} accent={accent} />
        ))}
      </div>
    </section>
  );
}

// ─────────────────────────────────────────────────────────────
function UpdateCard({
  item, progress, accent,
}: {
  item:     UpdateItem;
  progress: { pct: number; speed: string; state: string } | undefined;
  accent:   string;
}) {
  const [busy, setBusy] = useState(false);
  const running = progress?.state === "running" || busy;
  const done    = progress?.state === "done";
  const failed  = progress?.state === "error";

  const handleDownload = async () => {
    setBusy(true);
    try {
      const r = await api.startDownload(item.id);
      if (!r.ok) console.warn("[downloads] start failed:", r.error);
    } finally {
      // Once Python emits a "running" event, busy state is no longer needed
      setTimeout(() => setBusy(false), 500);
    }
  };

  const handleCancel = async () => {
    await api.cancelDownload(item.id);
  };

  const pct        = Math.min(100, Math.max(0, progress?.pct ?? 0));
  const speed      = progress?.speed ?? "";

  return (
    <div className="glass rounded-2xl p-5">
      {/* Header */}
      <div className="flex items-start justify-between gap-3 mb-3">
        <span
          className="text-[10px] font-display tracking-wider px-2 py-0.5 rounded-md
                     bg-black/40 ring-1 self-start"
          style={{ color: accent, borderColor: `${accent}40` }}
        >
          {item.version}
        </span>
        <h3 className="text-white font-bold text-[15px] leading-tight flex-1 text-right">
          {item.title}
        </h3>
      </div>

      {/* Description */}
      <p className="text-slate-300 text-[12px] leading-relaxed mb-4 text-right">
        {item.notes}
      </p>

      {/* Size + action */}
      <div className="flex items-center justify-between gap-3">
        <div className="text-[11px] text-slate-500">
          {(item.size_mb ?? 0).toFixed(1)} MB
        </div>

        {running ? (
          <button
            onClick={handleCancel}
            className="text-[12px] font-bold px-4 py-1.5 rounded-lg
                       border border-rose-500/30 text-rose-200
                       hover:bg-rose-500/15 transition"
          >
            ביטול
          </button>
        ) : done ? (
          <span className="text-[12px] font-bold px-4 py-1.5 rounded-lg
                           bg-emerald-500/20 text-emerald-200 ring-1 ring-emerald-400/30
                           inline-flex items-center gap-1.5">
            <IconOptBadgeInstalled width={14} className="shrink-0 opacity-90" />
            מותקן
          </span>
        ) : failed ? (
          <button
            onClick={handleDownload}
            className="text-[12px] font-bold px-4 py-1.5 rounded-lg
                       bg-rose-500/15 text-rose-200 hover:bg-rose-500/30 transition
                       inline-flex items-center justify-center gap-1.5"
          >
            <IconOptBtnRetryDownload width={18} className="shrink-0 opacity-90" />
            נסה שוב
          </button>
        ) : (
          <button
            onClick={handleDownload}
            className="text-[12px] font-bold px-4 py-1.5 rounded-lg
                       bg-brand-yellow hover:bg-yellow-300 text-brand-ink transition
                       shadow-[0_4px_12px_-4px_rgba(255,247,0,0.5)]
                       inline-flex items-center justify-center gap-1.5"
          >
            <IconOptBtnDownloadUpdate width={18} className="shrink-0 opacity-90" />
            הורד ועדכן
          </button>
        )}
      </div>

      {/* Progress bar - appears only while running or just finished */}
      {(running || done || failed) && (
        <div className="mt-4">
          <div className="flex justify-between text-[10px] mb-1">
            <span dir="ltr" className="text-slate-300 font-mono">
              {speed || (done ? "100%" : "-")}
            </span>
            <span className="text-slate-400">{pct.toFixed(1)}%</span>
          </div>
          {running ? (
            // Flowing liquid wave - identical to the site's live-progress bar.
            <LiquidWave
              pct={pct}
              ratePerMin={48}
              primary={accent}
              secondary={accent === "#fff700" ? "#00ffe0" : "#22c55e"}
              glow={accent}
              height={40}
            />
          ) : (
            <div className="h-1.5 bg-white/5 rounded-full overflow-hidden ring-1 ring-white/5">
              <div
                className="h-full rounded-full"
                style={{ width: `${pct}%`, background: failed ? "#ef4444" : "#22c55e" }}
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Loader() {
  return (
    <div className="glass-soft rounded-2xl p-10 grid place-items-center">
      <div className="w-8 h-8 border-2 border-brand-yellow border-t-transparent
                      rounded-full animate-spin" />
    </div>
  );
}

function Empty() {
  return (
    <div className="glass-soft rounded-2xl p-10 text-center text-slate-400 flex flex-col items-center gap-2">
      <IconOptEmptyNoUpdates width={30} className="opacity-70" />
      אין עדכונים זמינים כרגע.
    </div>
  );
}
