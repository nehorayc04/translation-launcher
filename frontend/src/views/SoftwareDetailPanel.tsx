// Big-Picture detail panel for a software entry. Mirrors GameDetailPanel
// in shape: large cover left, info + actions middle, settings sidebar
// right (with the installation-path block + folder open).
//
// Software entries don't link out to the publisher's website anymore —
// every catalog row's call-to-action funnels into the launcher's own
// "הורדות" tab where the localized installer / asset bundle lives.
import { useEffect, useState } from "react";
import { resolveCoverUrl } from "../lib/coverUrl";
import { api } from "../lib/eel";
import type { SteamModState } from "../lib/eel";
import type { Software } from "../lib/types";

type ReportStatus = (text: string, warn?: boolean) => void;

interface Props {
  software: Software;
  onBack:    () => void;
  reportStatus?: ReportStatus;
  /** Navigates the launcher's main view to the "הורדות" tab. The
   *  software card's primary CTA fires this instead of opening an
   *  external browser tab. */
  onNavigateToDownloads: () => void;
}

// Same id→installer map as AppsView.
type InstallHandler = (rs?: ReportStatus) => Promise<void>;
const INSTALL_HANDLERS: Partial<Record<string, InstallHandler>> = {
  steam: installSteamTranslation,
};

const AVAILABILITY_LABEL: Record<string, string> = {
  "available":   "זמין להורדה",
  "coming-soon": "בקרוב",
  "planned":     "מתוכנן",
  "paused":      "מושהה",
  "archived":    "בארכיון",
};

export default function SoftwareDetailPanel({
  software: s, onBack, reportStatus, onNavigateToDownloads,
}: Props) {
  const accent = s.accentColor || "#66c0f4";
  const cover  = resolveCoverUrl(s.cover, s.id);
  const handler = INSTALL_HANDLERS[s.id];

  const [busy, setBusy] = useState(false);
  // Local install state (path + exe) — initialised from the catalog
  // row (server-side detector enrichment) and refreshed on demand
  // via the explicit "סרוק שוב" button below.
  const [installPath, setInstallPath] = useState<string>(s.installPath ?? "");
  const [installed,   setInstalled]   = useState<boolean>(Boolean(s.installed));
  const [scanning,    setScanning]    = useState(false);

  // If a new snapshot of the software prop arrives (e.g. AppsView
  // re-fetched the catalog), pick up the fresh path/installed values
  // so the detail panel doesn't go stale while we're looking at it.
  useEffect(() => {
    setInstallPath(s.installPath ?? "");
    setInstalled(Boolean(s.installed));
  }, [s.installPath, s.installed]);

  // Steam mod cache — drives the per-mod "ניקוי מטמון" control in the
  // settings sidebar (moved here from the global Settings view).
  const [steamCache, setSteamCache] = useState<SteamModState | null>(null);
  useEffect(() => {
    if (s.id !== "steam") return;
    let alive = true;
    void api.getSteamModState()
      .then((st) => { if (alive) setSteamCache(st); })
      .catch(() => { /* ignore — button just stays hidden */ });
    return () => { alive = false; };
  }, [s.id]);

  const onClearCache = async () => {
    if (!confirm(
      "לנקות את מטמון התרגום? קבצי Steam ישוחזרו למצב המקורי — " +
      "התקנה מחדש תדרוש הורדה חוזרת."
    )) return;
    setBusy(true);
    try {
      const r = await api.clearSteamModCache();
      reportStatus?.(r.ok ? "המטמון נוקה וקבצי Steam שוחזרו" : (r.error ?? "שגיאה"), !r.ok);
      setSteamCache(await api.getSteamModState().catch(() => null));
    } finally {
      setBusy(false);
    }
  };

  const onInstall = async () => {
    if (busy) return;
    if (handler) {
      setBusy(true);
      try { await handler(reportStatus); }
      finally { setBusy(false); }
      return;
    }
    // Fallback for catalog entries without a built-in handler: take
    // the user to the downloads tab — that's where the localized
    // bundle (if any) is exposed.
    onNavigateToDownloads();
  };

  const onOpenInstallFolder = async () => {
    if (!installPath) return;
    const r = await api.openFolder(installPath);
    if (!r.ok) reportStatus?.(`לא הצלחתי לפתוח: ${r.error}`, true);
  };

  const onRescan = async () => {
    if (scanning) return;
    setScanning(true);
    reportStatus?.("מאתר התקנה במחשב…");
    try {
      const r = await api.scanSoftware();
      const fresh = r.software.find((x) => x.id === s.id);
      if (fresh) {
        setInstalled(Boolean(fresh.installed));
        setInstallPath(fresh.installPath ?? "");
        reportStatus?.(fresh.installed
          ? `נמצאה התקנה: ${fresh.installPath}`
          : "התוכנה לא מותקנת במחשב");
      }
    } catch (e) {
      reportStatus?.(String(e), true);
    } finally {
      setScanning(false);
    }
  };

  const availLabel = AVAILABILITY_LABEL[s.availability] ?? s.availability;
  // paused / archived → the install pipeline is on hold; CTA = "לא זמין".
  const unavailable = s.availability === "paused" || s.availability === "archived";
  const ctaLabel = unavailable
    ? "לא זמין"
    : handler
      ? (busy ? "מתקין…" : "התקן")
      : "פתח את הורדות";

  return (
    <div className="h-full overflow-y-auto px-8 py-6 animate-scale-in">
      <button
        onClick={onBack}
        className="mb-4 text-slate-300 hover:text-brand-yellow transition flex items-center gap-2"
      >
        ← חזרה לתוכנות
      </button>

      <div className="grid grid-cols-[380px_1fr_300px] gap-6">
        {/* Cover */}
        <div className="self-start">
          <div
            className="aspect-[3/4] rounded-2xl overflow-hidden ring-1 ring-white/10
                       shadow-[0_25px_60px_-15px_rgba(0,0,0,0.8)] relative"
            style={{ background: `radial-gradient(circle at 30% 30%, ${accent}33, #0a0e1a 70%)` }}
          >
            {cover ? (
              <img
                src={cover}
                alt={s.titleEn}
                className="w-full h-full object-cover"
                draggable={false}
              />
            ) : (
              <div
                className="w-full h-full grid place-items-center text-3xl font-extrabold"
                style={{ color: "#fff", textShadow: `0 2px 16px ${accent}88` }}
              >
                {s.titleEn}
              </div>
            )}
          </div>
        </div>

        {/* Info column */}
        <div className="flex flex-col">
          <h1
            dir="ltr"
            className="text-5xl font-display font-extrabold leading-tight mb-3 text-left"
            style={{ color: accent }}
          >
            {s.titleEn}
          </h1>

          <div className="flex gap-2 mb-5 justify-end">
            <span
              className="px-3 py-1 rounded-full text-xs font-semibold"
              style={{
                color:      accent,
                background: `${accent}1a`,
                border:     `1px solid ${accent}55`,
              }}
            >
              {availLabel}
            </span>
            {s.version && s.version !== "—" && (
              <span className="px-3 py-1 rounded-full text-xs bg-black/75 backdrop-blur-md
                               text-slate-200 ring-1 ring-white/15">
                {s.version}
              </span>
            )}
            <span
              className="px-3 py-1 rounded-full text-xs font-semibold"
              style={{
                color:      installed ? "#86efac" : "#cbd5e1",
                background: installed ? "rgba(34,197,94,0.18)" : "rgba(148,163,184,0.18)",
                border:     `1px solid ${installed ? "rgba(34,197,94,0.45)" : "rgba(148,163,184,0.35)"}`,
              }}
            >
              {installed ? "מותקן" : "לא מותקן"}
            </span>
          </div>

          {s.tagline && (
            <p className="text-lg text-slate-200 mb-3 leading-relaxed">{s.tagline}</p>
          )}
          {s.description && (
            <p className="text-slate-400 leading-relaxed mb-6">{s.description}</p>
          )}

          {/* Big action buttons — ONLY internal CTAs; no external links. */}
          <div className="flex gap-3 flex-wrap justify-start mt-auto">
            <button
              disabled={busy || unavailable}
              onClick={onInstall}
              className={`font-extrabold px-8 py-3 rounded-xl text-lg transition
                         disabled:cursor-not-allowed
                         ${unavailable
                           ? "bg-white/5 text-slate-400 border border-white/10 disabled:opacity-100"
                           : "text-brand-ink hover:brightness-110 disabled:opacity-40"}`}
              style={unavailable ? undefined : {
                background: accent,
                boxShadow:  `0 10px 30px -10px ${accent}aa`,
              }}
            >
              {ctaLabel}
            </button>

            <button
              onClick={onNavigateToDownloads}
              className="bg-white/5 hover:bg-white/10 text-slate-200 font-bold
                         px-6 py-3 rounded-xl border border-white/10 transition"
            >
              פתח את הורדות
            </button>
          </div>
        </div>

        {/* Settings sidebar — full parity with GameDetailPanel: install
            path field + folder open + status chips. The path here is
            auto-detected via registry/fingerprint scan, so the "browse"
            interaction is read-only display + "scan again" button (rather
            than free text — there's no per-software override store yet). */}
        <div className="glass rounded-2xl p-5 self-start space-y-5">
          <h3 className="text-white font-bold text-lg">הגדרות</h3>

          <div>
            <label className="block text-xs text-slate-400 mb-1.5">נתיב התקנה</label>
            <input
              dir="ltr"
              value={installPath}
              readOnly
              placeholder="C:\Program Files..."
              className="w-full bg-black/40 border border-white/10
                         rounded-lg px-3 py-2 text-sm text-slate-100 outline-none"
            />
            <div className="flex gap-2 mt-2">
              <button
                disabled={scanning}
                onClick={onRescan}
                className="flex-1 text-xs px-3 py-1.5 bg-brand-yellow text-brand-ink
                           font-bold rounded-lg hover:bg-yellow-300 disabled:opacity-50"
              >
                {scanning ? "סורק…" : "סרוק שוב"}
              </button>
              <button
                disabled={!installPath}
                onClick={onOpenInstallFolder}
                className="flex-1 text-xs px-3 py-1.5 border border-white/10
                           text-slate-300 rounded-lg hover:bg-white/5 disabled:opacity-40"
              >
                עיון
              </button>
            </div>
          </div>

          <button
            disabled={!installPath}
            onClick={onOpenInstallFolder}
            className="w-full text-sm px-3 py-2 border border-white/10 text-slate-200
                       rounded-lg hover:border-brand-cyan/40 hover:bg-brand-cyan/5
                       disabled:opacity-40 disabled:cursor-not-allowed"
          >
            פתח תיקיית התוכנה
          </button>

          {/* Per-mod cache control — lives here in the software's own
              panel (not in global Settings). */}
          {s.id === "steam" && steamCache?.cached && (
            <button
              disabled={busy}
              onClick={onClearCache}
              className="w-full text-sm px-3 py-2 border border-rose-500/30 text-rose-200
                         rounded-lg hover:bg-rose-500/10
                         disabled:opacity-40 disabled:cursor-not-allowed"
            >
              ניקוי מטמון התרגום
            </button>
          )}

          {/* Status summary */}
          <div className="border-t border-white/5 pt-4 text-xs space-y-1.5">
            <Row k="זמינות"    v={availLabel} />
            <Row k="גרסה"      v={s.version || "—"} />
            <Row k="התקנה"     v={installed ? "מותקן" : "לא נמצא"} />
            {s.badge   && <Row k="תווית"  v={s.badge} />}
            {handler   && <Row k="מנגנון" v="התקנה אוטומטית" />}
          </div>
        </div>
      </div>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-slate-200 truncate max-w-[180px]" dir="ltr">{v}</span>
      <span className="text-slate-500">{k}</span>
    </div>
  );
}

// ---------------------------------------------------------------- handlers

async function installSteamTranslation(reportStatus?: ReportStatus) {
  reportStatus?.("מתקין תרגום עברי ל-Steam — סגור את Steam לפני שתמשיך…");
  try {
    const r = await api.applySteamTranslation();
    if (r.ok) {
      const count = r.count ?? 0;
      reportStatus?.(`✓ הותקנו ${count} קבצים. הפעל מחדש את Steam עם שפה: العربية`);
    } else {
      reportStatus?.(r.error || "שגיאה לא ידועה בהתקנה", true);
    }
  } catch (e) {
    reportStatus?.(`כשל בקריאה לשרת: ${String(e)}`, true);
  }
}
