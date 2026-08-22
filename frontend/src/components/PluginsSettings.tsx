// Settings → "תוספים" - the cloud add-on manager.
//
// Plugins are optional features delivered from the cloud (nothing bundled in the
// installer) that a signed-in user who has bought at least one GAME can turn on
// without reinstalling the app. The first plugin is the automatic game-save
// backup, which gets a full config panel here (auto-detect saves, add a folder,
// schedule, back up now, history + restore).
import { useCallback, useEffect, useState } from "react";
import {
  api,
  type PluginMeta, type SaveBackupConfig, type SaveBackupEntry,
  type DetectedSave, type SaveBackupItem, type PluginUiResult,
} from "../lib/eel";
import {
  IconNavPlugins, IconOptEmptyNoPlugins,
  IconOptBtnPluginDownload, IconOptSectionBackedSaves, IconOptBtnBrowseFolder,
  IconOptBtnAddDetected, IconOptBtnRemoveEntry, IconOptSectionBackupHistory,
  IconOptBtnRestoreBackup,
  IconAppPluginsBtnOpenFolder, IconAppPluginsBtnBackupNow,
  IconAppPluginsBtnAutodetect, IconAppPluginsStateLockedLock,
  IconOptBtnControllerReset,
} from "./UiIcons";
import GenericPluginRenderer from "./GenericPluginRenderer";
import ErrorBoundary from "./ErrorBoundary";
import { shortName } from "../lib/pluginName";

type Report = (text: string, warn?: boolean) => void;

// api.getPlugins() does NETWORK work (entitlement check + cloud catalog fetch),
// and this view remounts on every nav to "תוספים" - so without a cache it showed
// "טוען תוספים…" for seconds EACH time. Cache the last snapshot (localStorage, so
// it survives restarts) → repeat visits render the plugins INSTANTLY from cache
// and only refresh in the background.
const PLUGINS_CACHE_KEY = "pluginsSnap:v1";
type PluginsSnap = { entitled: boolean; signedIn?: boolean; plugins: PluginMeta[] };
function readPluginsCache(): PluginsSnap | null {
  try { const s = localStorage.getItem(PLUGINS_CACHE_KEY); return s ? (JSON.parse(s) as PluginsSnap) : null; }
  catch { return null; }
}
function writePluginsCache(s: PluginsSnap) {
  try { localStorage.setItem(PLUGINS_CACHE_KEY, JSON.stringify(s)); } catch { /* ignore */ }
}

export default function PluginsSettings(
  { reportStatus, onOpenPlugin }:
  { reportStatus?: Report; onOpenPlugin?: (id: string) => void },
) {
  // Seed from cache so a repeat visit paints immediately (null only on the very
  // first ever load, which is the only time the "טוען" screen shows).
  const [entitled, setEntitled] = useState<boolean | null>(() => readPluginsCache()?.entitled ?? null);
  const [signedIn, setSignedIn] = useState<boolean>(() => !!readPluginsCache()?.signedIn);
  const [plugins, setPlugins] = useState<PluginMeta[]>(() => readPluginsCache()?.plugins ?? []);
  const [busy, setBusy] = useState<string | null>(null);
  // A FREE plugin is gated on an account only. `usable` is decided by the engine
  // per plugin; the `free && signedIn` fallback covers an older cached snapshot.
  const canUse = (p: PluginMeta) => p.usable ?? (p.free ? signedIn : !!entitled);
  const freeAvailable = plugins.some((p) => p.free && canUse(p));

  const load = useCallback(async () => {
    try {
      const snap = await api.getPlugins();
      const e = !!snap.entitled;
      const s = !!snap.signedIn;
      const p = Array.isArray(snap.plugins) ? snap.plugins : [];
      setEntitled(e);
      setSignedIn(s);
      setPlugins(p);
      writePluginsCache({ entitled: e, signedIn: s, plugins: p });
      // A plugin's own page listens for this, so a toggle made here (or there)
      // is reflected on both screens without a reload.
      window.dispatchEvent(new CustomEvent("pluginschanged"));
    } catch {
      // On a fetch failure KEEP the cached list (don't blank it); only fall back
      // to "locked/empty" if we truly have nothing cached yet.
      setEntitled((prev) => (prev === null ? false : prev));
    }
  }, []);
  useEffect(() => { void load(); }, [load]);

  // Force a catalog read NOW instead of waiting out the 300s cache - this is what
  // makes "the admin added/removed/updated a plugin" observable on demand.
  const refresh = async () => {
    setBusy("__refresh");
    try {
      const snap = await api.refreshPlugins();
      const e = !!snap.entitled, s = !!snap.signedIn;
      const p = Array.isArray(snap.plugins) ? snap.plugins : [];
      setEntitled(e); setSignedIn(s); setPlugins(p);
      writePluginsCache({ entitled: e, signedIn: s, plugins: p });
      window.dispatchEvent(new CustomEvent("pluginschanged"));
      reportStatus?.(snap.refreshed ? "רשימת התוספים עודכנה" : "אין קשר לשרת - מוצגת הרשימה השמורה",
        !snap.refreshed);
    } catch { reportStatus?.("רענון נכשל", true); }
    finally { setBusy(null); }
  };

  const update = async (p: PluginMeta) => {
    setBusy(p.id);
    try {
      const r = await api.updatePlugin(p.id);
      reportStatus?.(r.ok ? `"${shortName(p.name)}" עודכן לגרסה ${r.version ?? ""}` : "העדכון נכשל", !r.ok);
      await load();
    } finally { setBusy(null); }
  };

  const toggle = async (p: PluginMeta) => {
    setBusy(p.id);
    try {
      const on = !p.enabled;
      const r = await api.setPluginEnabled(p.id, on);
      if (!r.ok) {
        reportStatus?.(r.error !== "not-entitled" ? "הפעולה נכשלה"
          : p.free ? "התוסף הזה זמין לכל משתמש מחובר - התחברו לחשבון."
          : "התוספים זמינים למי שרכש לפחות משחק אחד.", true);
      } else {
        reportStatus?.(on ? `התוסף "${p.name}" הופעל` : `התוסף "${p.name}" כובה`);
      }
      await load();
    } finally { setBusy(null); }
  };

  if (entitled === null) {
    return <div className="h-full grid place-items-center text-slate-400 text-sm animate-pulse">טוען תוספים…</div>;
  }

  return (
    // SAME container geometry as the other views (games/software/downloads):
    // full-width `px-8 py-6`, NO max-w/mx-auto centering (that made the plugins
    // gutters look different).
    <div className="h-full overflow-y-auto px-8 py-6 animate-fade-in">
    <section className="space-y-5">
      <header className="mb-6 animate-rise text-right flex items-start gap-3 flex-wrap">
        <div className="flex-1 min-w-0">
          {/* Big gradient title - identical size/shape to the other views; PURPLE
              accent (the plugins nav colour) fading to white, RTL. */}
          <h1 className="text-3xl font-extrabold inline-flex items-center gap-1.5">
            <IconNavPlugins width={22} className="shrink-0 opacity-90" style={{ color: "#a78bfa" }} />
            <span style={{ background: "linear-gradient(90deg, #ffffff 0%, #a78bfa 100%)", WebkitBackgroundClip: "text", backgroundClip: "text", color: "transparent" }}>
              תוספים
            </span>
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            יכולות נוספות שמורדות מהענן ומתווספות לתוכנה - בלי להתקין מחדש.
          </p>
        </div>
        <button type="button" disabled={busy !== null} onClick={() => void refresh()}
          title="בדיקה מיידית של תוספים חדשים / עדכונים"
          className="shrink-0 text-xs px-3 py-1.5 rounded-lg bg-white/[0.06] hover:bg-white/[0.1] text-slate-200 disabled:opacity-40 inline-flex items-center gap-1.5">
          <IconOptBtnControllerReset width={15} className="shrink-0 opacity-90" />
          {busy === "__refresh" ? "בודק…" : "בדיקת עדכונים"}
        </button>
      </header>

      {/* The banner must not say "locked" when a FREE plugin on this very screen
          is open to the user - that reads as if nothing here works. */}
      {!entitled && (
        <div className="rounded-2xl border border-amber-400/30 bg-amber-400/[0.06] p-5">
          <div className="flex items-start gap-3">
            <IconAppPluginsStateLockedLock width={26} className="shrink-0 opacity-90 text-amber-300" />
            <div className="flex-1">
              <div className="font-bold text-amber-200">
                {freeAvailable ? "חלק מהתוספים נעולים" : "התוספים נעולים"}
              </div>
              <p className="text-sm text-slate-300 mt-1">
                {freeAvailable
                  ? "תוספים בתשלום דורשים רכישה של לפחות משחק אחד. התוספים המסומנים «חינם» פתוחים לכל משתמש מחובר."
                  : signedIn
                    ? "כדי להשתמש בתוספים בתשלום צריך לרכוש לפחות משחק אחד (לא תוכנה)."
                    : "כדי להשתמש בתוספים צריך להיות מחובר לחשבון."}
              </p>
              <button
                type="button"
                onClick={() => void api.openExternal("https://hebrew-translation-hub.com/games")}
                className="mt-3 text-sm font-semibold text-amber-200 hover:text-amber-100 underline"
              >
                לרכישת משחק ←
              </button>
            </div>
          </div>
        </div>
      )}

      {plugins.length === 0 && entitled && (
        <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-6 text-center text-slate-500 flex flex-col items-center gap-2">
          <IconOptEmptyNoPlugins width={30} className="opacity-70" />
          אין תוספים זמינים כרגע.
        </div>
      )}

      {/* A GRID of cards - 3 per row - exactly like the games/software library:
          the manager lists what exists, and a click opens that plugin's OWN page.
          (The old design expanded every plugin's settings inline, so the list got
          longer the more plugins you had and each one was buried under the rest.) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
        {plugins.map((p) => {
          const accent = p.accent ?? "#00ffe0";
          const open = () => { if (p.installed) onOpenPlugin?.(p.id); };
          return (
            <div
              key={p.id}
              role={p.installed ? "button" : undefined}
              tabIndex={p.installed ? 0 : undefined}
              onClick={open}
              onKeyDown={(e) => { if (p.installed && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); open(); } }}
              className={[
                "group relative flex flex-col rounded-2xl border border-white/10 bg-slate-900/50 p-5 transition",
                p.installed ? "cursor-pointer hover:border-white/20 hover:bg-slate-900/70 lift" : "",
              ].join(" ")}
              style={p.installed ? ({ ["--ic" as string]: accent }) : undefined}
            >
              <div className="flex items-start gap-3">
                <div className="grid place-items-center w-12 h-12 rounded-xl text-2xl shrink-0"
                  style={{ background: `${accent}22`, border: `1px solid ${accent}55` }}>
                  {p.icon ?? "🧩"}
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="font-bold text-white truncate" title={p.name}>{shortName(p.name)}</h3>
                  <div className="flex items-center gap-2 mt-0.5 flex-wrap">
                    {p.version && <span className="text-[11px] text-slate-500">v{p.version}</span>}
                    {p.free && !p.installed && (
                      <span className="text-[11px] px-2 py-0.5 rounded-full font-semibold text-emerald-300"
                        style={{ border: "1px solid #86efac55" }}>חינם</span>
                    )}
                    {p.installed && (
                      <span className="text-[11px] px-2 py-0.5 rounded-full font-semibold"
                        style={{ color: p.enabled ? "#86efac" : "#94a3b8",
                                 border: `1px solid ${p.enabled ? "#86efac55" : "#94a3b855"}` }}>
                        {p.enabled ? "פעיל" : "כבוי"}
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {p.tagline && <p className="text-[13px] text-slate-400 mt-3 leading-relaxed line-clamp-3">{p.tagline}</p>}

              <div className="mt-auto pt-4 flex items-center gap-2 flex-wrap">
                {p.installed && p.updateAvailable && (
                  <button
                    type="button"
                    disabled={busy === p.id}
                    onClick={(e) => { e.stopPropagation(); void update(p); }}
                    className="inline-flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold text-emerald-200 border border-emerald-400/40 hover:bg-emerald-400/10 disabled:opacity-40"
                  >
                    <IconOptBtnPluginDownload width={15} className="shrink-0 opacity-90" />
                    {busy === p.id ? "…" : `עדכון ל-${p.version}`}
                  </button>
                )}
                {p.installed ? (
                  <span className="text-xs font-semibold inline-flex items-center gap-1" style={{ color: accent }}>
                    פתיחה ←
                  </span>
                ) : (
                  <button
                    type="button"
                    disabled={busy === p.id || !canUse(p)}
                    onClick={(e) => { e.stopPropagation(); void toggle(p); }}
                    className="inline-flex items-center justify-center gap-1.5 px-4 py-2 rounded-xl text-sm font-bold transition disabled:opacity-40"
                    style={{ background: `${accent}26`, border: `1px solid ${accent}66`, color: accent }}
                  >
                    <IconOptBtnPluginDownload width={18} className="shrink-0 opacity-90" />
                    {busy === p.id ? "…" : "התקנה"}
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>

    </section>
    </div>
  );
}

// ───────────────────────────────────────────────────────────────
// Plugin body: a cloud plugin ships a declarative `ui` manifest rendered by
// GenericPluginRenderer, so its whole UI is cloud-editable with NO app rebuild.
// A manifest-less plugin falls back to the built-in save-backup panel.
// ───────────────────────────────────────────────────────────────
export function DeclarativePluginBody({ plugin, reportStatus }: { plugin: PluginMeta; reportStatus?: Report }) {
  const [data, setData] = useState<PluginUiResult | null>(null);
  useEffect(() => {
    let alive = true;
    void api.pluginUi(plugin.id)
      .then((r) => { if (alive) setData(r); })
      .catch(() => { if (alive) setData({ ok: false, ui: null, state: {}, meta: {} }); });
    return () => { alive = false; };
  }, [plugin.id]);
  if (!data) return <div className="px-5 pb-5 text-sm text-slate-500">טוען הגדרות…</div>;
  if (data.ui && data.ui.length > 0) {
    // A plugin's ui manifest is CLOUD-CONTROLLED (site_config.plugins), so a bad
    // admin edit can crash GenericPluginRenderer's render. Without a LOCAL
    // boundary that bubbles to the one app-wide ErrorBoundary and blanks the
    // entire launcher for every user with this panel open - contain it here
    // instead, so a broken plugin shows a small inline notice and everything
    // else (other plugins, the rest of the app) keeps working.
    return (
      <ErrorBoundary localReset fallback={(reset) => (
        <div dir="rtl" className="mx-5 mb-5 rounded-xl border border-amber-500/30 bg-amber-500/5 px-4 py-3">
          <p className="text-sm text-amber-200 font-semibold">⚠️ תקלה בטעינת התוסף</p>
          <p className="text-xs text-slate-400 mt-1">שאר התוכנה ממשיכה לפעול כרגיל.</p>
          <button type="button" onClick={reset}
            className="mt-2 text-xs px-3 py-1.5 rounded-lg bg-amber-500/15 border border-amber-500/40 text-amber-200 hover:bg-amber-500/25">
            נסה שוב
          </button>
        </div>
      )}>
        <GenericPluginRenderer pluginId={plugin.id} ui={data.ui} state={data.state}
          accent={plugin.accent ?? "#22c55e"} reportStatus={reportStatus} />
      </ErrorBoundary>
    );
  }
  if (plugin.kind === "save_backup") {
    return <SaveBackupPanel pluginId={plugin.id} accent={plugin.accent ?? "#22c55e"} reportStatus={reportStatus} />;
  }
  return null;
}

// ───────────────────────────────────────────────────────────────
// The save-backup config panel (built-in fallback for a manifest-less plugin)
// ───────────────────────────────────────────────────────────────
const SCHEDULE_LABELS: Record<string, string> = {
  manual:   "ידני בלבד",
  on_boot:  "בכל הפעלת מחשב",
  on_launch:"בכל פתיחת משחק",
  realtime: "תוך כדי משחק (רציף)",
  daily:    "כל יום",
  weekly:   "כל שבוע",
  monthly:  "כל חודש",
};

function SaveBackupPanel({ pluginId, accent, reportStatus }: {
  pluginId: string; accent: string; reportStatus?: Report;
}) {
  const [cfg, setCfg] = useState<SaveBackupConfig | null>(null);
  const [detected, setDetected] = useState<DetectedSave[] | null>(null);
  const [backups, setBackups] = useState<SaveBackupItem[]>([]);
  const [scanning, setScanning] = useState(false);
  const [working, setWorking] = useState(false);
  const [manualPath, setManualPath] = useState("");
  const [manualLabel, setManualLabel] = useState("");
  const [snapName, setSnapName] = useState("");

  const loadCfg = useCallback(async () => {
    try { setCfg(await api.getPluginConfig(pluginId)); } catch { /* ignore */ }
  }, [pluginId]);
  const loadBackups = useCallback(async () => {
    try { setBackups(await api.savebackupList(pluginId)); } catch { /* ignore */ }
  }, [pluginId]);
  useEffect(() => { void loadCfg(); void loadBackups(); }, [loadCfg, loadBackups]);

  const save = async (next: SaveBackupConfig) => {
    setCfg(next);
    try { await api.setPluginConfig(pluginId, next); } catch { /* ignore */ }
  };

  const detect = async () => {
    setScanning(true);
    reportStatus?.("מאתר תיקיות שמירה…");
    try {
      const d = await api.savebackupDetect();
      setDetected(Array.isArray(d) ? d : []);
      reportStatus?.(`נמצאו שמירות ל-${d.length} משחקים`);
    } catch { reportStatus?.("האיתור נכשל", true); }
    finally { setScanning(false); }
  };

  const addEntry = async (e: SaveBackupEntry) => {
    if (!cfg) return;
    const entries = cfg.entries ?? [];
    if (entries.some((x) => x.source.toLowerCase() === e.source.toLowerCase())) {
      reportStatus?.("התיקייה כבר קיימת ברשימה", true);
      return;
    }
    await save({ ...cfg, entries: [...entries, e] });
    reportStatus?.(`נוסף לגיבוי: ${e.label}`);
  };

  // Add every auto-detected candidate in one save (a loop of addEntry would read
  // a stale cfg from the closure and overwrite itself). Dedups by source path -
  // both against the existing list and within the batch.
  const addAll = async () => {
    if (!cfg || !detected) return;
    const existing = cfg.entries ?? [];
    const seen = new Set(existing.map((x) => x.source.toLowerCase()));
    const additions: SaveBackupEntry[] = [];
    detected.forEach((d, di) => {
      const c = d.candidates[0];
      if (!c) return;
      const key = c.path.toLowerCase();
      if (seen.has(key)) return;
      seen.add(key);
      additions.push({
        id: `d_${d.game_id}_${di}_${Date.now().toString(36)}`,
        game_id: d.game_id, label: c.label || d.title, source: c.path, enabled: true, auto: true,
      });
    });
    if (additions.length === 0) { reportStatus?.("כל התיקיות שנמצאו כבר ברשימה"); return; }
    await save({ ...cfg, entries: [...existing, ...additions] });
    reportStatus?.(`נוספו ${additions.length} תיקיות לגיבוי`);
  };

  const removeEntry = async (id: string) => {
    if (!cfg) return;
    await save({ ...cfg, entries: (cfg.entries ?? []).filter((x) => x.id !== id) });
  };

  const browse = async () => {
    try {
      const r = await api.pickFolder("בחר תיקיית שמירות");
      if (r.ok && r.path) setManualPath(r.path);
    } catch { /* fall back to typing */ }
  };

  const addManual = async () => {
    const path = manualPath.trim();
    if (!path) return;
    await addEntry({
      id: `m_${Date.now().toString(36)}`,
      game_id: "manual",
      label: manualLabel.trim() || path.split(/[\\/]/).filter(Boolean).pop() || "שמירה",
      source: path, enabled: true, auto: false,
    });
    setManualPath(""); setManualLabel("");
  };

  const runNow = async () => {
    setWorking(true);
    reportStatus?.("מגבה עכשיו…");
    try {
      const r = await api.savebackupRunNow(pluginId, snapName.trim());
      reportStatus?.(r.backed_up > 0
        ? `גובו ${r.backed_up} שמירות${snapName.trim() ? ` ("${snapName.trim()}")` : ""}`
        : "אין שמירות לגבות");
      setSnapName("");
      await loadBackups();
    } catch { reportStatus?.("הגיבוי נכשל", true); }
    finally { setWorking(false); }
  };

  const restore = async (b: SaveBackupItem, target: string) => {
    if (!confirm(`לשחזר את הגיבוי מ-${b.when} אל "${b.label}"?\nהמצב הנוכחי יגובה קודם למקרה חירום.`)) return;
    setWorking(true);
    try {
      const r = await api.savebackupRestore(b.path, target);
      reportStatus?.(r.ok ? "השחזור הושלם (המצב הקודם נשמר לגיבוי חירום)" : "השחזור נכשל", !r.ok);
    } catch { reportStatus?.("השחזור נכשל", true); }
    finally { setWorking(false); }
  };

  if (!cfg) return <div className="px-5 pb-5 text-sm text-slate-500">טוען הגדרות…</div>;

  const entries = cfg.entries ?? [];
  const sourceByLabel = new Map(entries.map((e) => [e.label, e.source]));

  return (
    <div className="border-t border-white/5 px-5 py-4 space-y-5" style={{ background: `${accent}08` }}>
      {/* Schedule + keep-count */}
      <div className="grid sm:grid-cols-2 gap-3">
        <label className="block">
          <span className="text-xs text-slate-400">מתי לגבות</span>
          {/* appearance-none hides the faint native arrow; a BOLD accent chevron is
              pinned to the LEFT edge of the card (RTL end), with pl-9 so the text
              never overlaps it. */}
          <div className="relative mt-1">
            <select
              value={cfg.schedule ?? "daily"}
              onChange={(e) => void save({ ...cfg, schedule: e.target.value as SaveBackupConfig["schedule"] })}
              className="appearance-none w-full bg-black/40 border border-white/10 rounded-lg pr-3 pl-9 py-2 text-sm text-white cursor-pointer"
            >
              {Object.entries(SCHEDULE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
            <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2" style={{ color: accent }}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={3.2} strokeLinecap="round" strokeLinejoin="round"><path d="m6 9 6 6 6-6" /></svg>
            </span>
          </div>
        </label>
        <label className="block">
          <span className="text-xs text-slate-400">כמה גיבויים לשמור לכל משחק</span>
          <input
            type="number" min={1} max={100} value={cfg.keep ?? 10}
            onChange={(e) => void save({ ...cfg, keep: Math.max(1, Math.min(100, Number(e.target.value) || 10)) })}
            className="mt-1 w-full bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-sm text-white"
          />
        </label>
      </div>

      {/* What gets backed up */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-semibold text-slate-200 inline-flex items-center gap-1.5"><IconOptSectionBackedSaves width={20} className="shrink-0 opacity-90" />שמירות שמגובות ({entries.length})</span>
          <div className="flex gap-2 items-center flex-wrap">
            <input value={snapName} onChange={(e) => setSnapName(e.target.value)}
              placeholder="שם לגיבוי (לא חובה)" title="שם אופציונלי לגיבוי הידני - יסומן על התיקייה ולא יימחק אוטומטית"
              className="text-xs w-40 bg-black/40 border border-white/10 rounded-lg px-2.5 py-1.5 text-white" />
            <button type="button" disabled={scanning} onClick={() => void detect()}
              className="text-xs px-3 py-1.5 rounded-lg bg-white/[0.06] hover:bg-white/[0.1] text-slate-200 disabled:opacity-40 inline-flex items-center gap-1.5">
              {scanning ? "מאתר…" : <><IconAppPluginsBtnAutodetect width={15} className="shrink-0 opacity-90" />איתור אוטומטי</>}
            </button>
            <button type="button" disabled={working || entries.length === 0} onClick={() => void runNow()}
              className="text-xs px-3 py-1.5 rounded-lg font-bold disabled:opacity-40 inline-flex items-center gap-1.5"
              style={{ background: `${accent}22`, border: `1px solid ${accent}66`, color: accent }}>
              {working ? "…" : <><IconAppPluginsBtnBackupNow width={15} className="shrink-0 opacity-90" />גבה עכשיו</>}
            </button>
          </div>
        </div>

        {entries.length === 0 && (
          <p className="text-[13px] text-slate-500 py-2">
            עוד לא נבחרו שמירות. לחצו "איתור אוטומטי" כדי שהתוכנה תמצא לבד, או הוסיפו תיקייה ידנית למטה.
          </p>
        )}
        <ul className="space-y-1.5">
          {entries.map((e) => (
            <li key={e.id} className="flex items-center gap-2 rounded-lg bg-black/30 px-3 py-2">
              <span className="flex-1 min-w-0">
                <span className="text-sm text-white block truncate">{e.label}</span>
                <span className="text-[11px] text-slate-500 block truncate" dir="ltr">{e.source}</span>
              </span>
              <button type="button" onClick={() => void api.openFolder(e.source)}
                className="text-xs text-slate-400 hover:text-slate-200 shrink-0"><IconAppPluginsBtnOpenFolder width={15} className="opacity-90" /></button>
              <button type="button" onClick={() => void removeEntry(e.id)}
                className="text-xs text-rose-300/80 hover:text-rose-200 shrink-0 inline-flex items-center gap-1"><IconOptBtnRemoveEntry width={18} className="shrink-0 opacity-90" />הסר</button>
            </li>
          ))}
        </ul>
      </div>

      {/* Auto-detected candidates */}
      {detected && detected.length > 0 && (
        <div className="rounded-xl border border-white/10 bg-black/20 p-3">
          <div className="flex items-center justify-between gap-2 mb-2">
            <span className="text-xs font-semibold text-slate-300">נמצאו אוטומטית - לחצו "הוסף":</span>
            <button type="button" onClick={() => void addAll()}
              className="text-xs px-2.5 py-1 rounded-lg font-bold shrink-0 inline-flex items-center gap-1.5"
              style={{ background: `${accent}22`, border: `1px solid ${accent}66`, color: accent }}>
              <IconOptBtnAddDetected width={16} className="shrink-0 opacity-90" />הוסף הכל
            </button>
          </div>
          <ul className="space-y-1.5">
            {detected.map((d) => d.candidates.slice(0, 1).map((c) => (
              <li key={d.game_id} className="flex items-center gap-2">
                <span className="flex-1 min-w-0">
                  <span className="text-sm text-white block truncate">{d.title}</span>
                  <span className="text-[11px] text-slate-500 block truncate" dir="ltr">{c.path}</span>
                </span>
                <span className="text-[10px] text-slate-500 shrink-0">
                  {Math.round(c.confidence * 100)}% {c.source === "known" ? "· ודאי" : ""}
                </span>
                <button type="button"
                  // Use the CANDIDATE's label, not the bare game title: for a
                  // multi-account launcher (Ubisoft stores saves per account uuid)
                  // the candidate label carries the account, and the label is what
                  // becomes the backup's destination folder - sharing one label
                  // across two accounts would make them overwrite each other.
                  onClick={() => void addEntry({ id: `d_${d.game_id}_${Date.now().toString(36)}`,
                    game_id: d.game_id, label: c.label || d.title, source: c.path, enabled: true, auto: true })}
                  className="text-xs px-2.5 py-1 rounded-lg font-semibold shrink-0 inline-flex items-center gap-1.5"
                  style={{ background: `${accent}22`, border: `1px solid ${accent}55`, color: accent }}>
                  <IconOptBtnAddDetected width={18} className="shrink-0 opacity-90" />הוסף
                </button>
              </li>
            )))}
          </ul>
        </div>
      )}
      {detected && detected.length === 0 && (
        <p className="text-[13px] text-slate-500">לא נמצאו שמירות אוטומטית - אפשר להוסיף תיקייה ידנית.</p>
      )}

      {/* Manual add */}
      <div className="rounded-xl border border-white/10 bg-black/20 p-3">
        <div className="text-xs font-semibold text-slate-300 mb-2">הוספת תיקייה ידנית</div>
        <div className="flex gap-2 flex-wrap">
          <input value={manualLabel} onChange={(e) => setManualLabel(e.target.value)} placeholder="שם (למשל: Elden Ring)"
            className="flex-1 min-w-[120px] bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-sm text-white" />
          <input value={manualPath} onChange={(e) => setManualPath(e.target.value)} placeholder="נתיב תיקיית השמירות" dir="ltr"
            className="flex-[2] min-w-[180px] bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-sm text-white" />
          <button type="button" onClick={() => void browse()}
            className="text-xs px-3 py-2 rounded-lg bg-white/[0.06] hover:bg-white/[0.1] text-slate-200 inline-flex items-center gap-1.5"><IconOptBtnBrowseFolder width={18} className="shrink-0 opacity-90" />עיון…</button>
          <button type="button" onClick={() => void addManual()} disabled={!manualPath.trim()}
            className="text-xs px-3 py-2 rounded-lg font-bold disabled:opacity-40"
            style={{ background: `${accent}22`, border: `1px solid ${accent}66`, color: accent }}>הוסף</button>
        </div>
      </div>

      {/* Backup history */}
      {backups.length > 0 && (
        <div>
          <div className="text-sm font-semibold text-slate-200 mb-2 inline-flex items-center gap-1.5"><IconOptSectionBackupHistory width={20} className="shrink-0 opacity-90" />היסטוריית גיבויים ({backups.length})</div>
          <ul className="space-y-1.5 max-h-64 overflow-y-auto">
            {backups.map((b) => (
              <li key={b.path} className="flex items-center gap-2 rounded-lg bg-black/30 px-3 py-2">
                <span className="flex-1 min-w-0">
                  <span className="text-sm text-white">{b.label}</span>
                  <span className="text-[11px] text-slate-500 block" dir="ltr">
                    {b.when.replace(/_/g, " ")} · {b.files} קבצים · {b.size_mb} MB
                  </span>
                </span>
                <button type="button" onClick={() => void api.openFolder(b.path)}
                  className="text-xs text-slate-400 hover:text-slate-200 shrink-0"><IconAppPluginsBtnOpenFolder width={15} className="opacity-90" /></button>
                {sourceByLabel.get(b.label) && (
                  <button type="button" disabled={working}
                    onClick={() => void restore(b, sourceByLabel.get(b.label)!)}
                    className="text-xs px-2.5 py-1 rounded-lg font-semibold text-amber-200 border border-amber-400/40 hover:bg-amber-400/10 shrink-0 disabled:opacity-40 inline-flex items-center gap-1.5">
                    <IconOptBtnRestoreBackup width={18} className="shrink-0 opacity-90" />שחזר
                  </button>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
