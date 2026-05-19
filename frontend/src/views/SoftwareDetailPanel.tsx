// Big-Picture detail panel for a software entry. Mirrors GameDetailPanel
// in shape (large cover left, info + actions middle, settings sidebar
// right) but simpler — software has no install path / mod state /
// per-title theme.
//
// Currently the only software with a built-in installer is Steam; the
// id→handler map in AppsView holds that wiring. Anything else opens
// its downloadUrl externally.
import { useState } from "react";
import { resolveCoverUrl } from "../lib/coverUrl";
import { api } from "../lib/eel";
import type { Software } from "../lib/types";

type ReportStatus = (text: string, warn?: boolean) => void;

interface Props {
  software: Software;
  onBack:    () => void;
  reportStatus?: ReportStatus;
}

// Same id→installer map as AppsView. Kept here too so the detail
// panel's "Install" button knows whether to call a native handler or
// fall back to the download URL.
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

export default function SoftwareDetailPanel({ software: s, onBack, reportStatus }: Props) {
  const accent = s.accentColor || "#66c0f4";
  const cover  = resolveCoverUrl(s.cover, s.id);
  const handler = INSTALL_HANDLERS[s.id];
  const [busy, setBusy] = useState(false);

  const onInstall = async () => {
    if (busy) return;
    if (handler) {
      setBusy(true);
      try { await handler(reportStatus); }
      finally { setBusy(false); }
      return;
    }
    if (s.downloadUrl) {
      window.open(s.downloadUrl, "_blank", "noopener,noreferrer");
    } else {
      reportStatus?.("לתוכנה זו אין עדיין קישור הורדה.", true);
    }
  };

  const onOpenPublisher = () => {
    if (s.publisherUrl) {
      window.open(s.publisherUrl, "_blank", "noopener,noreferrer");
    }
  };

  const availLabel = AVAILABILITY_LABEL[s.availability] ?? s.availability;
  const ctaLabel = handler
    ? (busy ? "מתקין…" : "התקן")
    : (s.downloadUrl ? "הורד" : "אין הורדה");

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
            style={{
              background: `radial-gradient(circle at 30% 30%, ${accent}33, #0a0e1a 70%)`,
            }}
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
            {s.badge && (
              <span
                className="px-3 py-1 rounded-full text-xs font-semibold"
                style={{
                  color:      "#0a0a14",
                  background: accent,
                  boxShadow:  `0 6px 16px -8px ${accent}aa`,
                }}
              >
                {s.badge}
              </span>
            )}
          </div>

          {s.tagline && (
            <p className="text-lg text-slate-200 mb-3 leading-relaxed">{s.tagline}</p>
          )}
          {s.description && (
            <p className="text-slate-400 leading-relaxed mb-6">{s.description}</p>
          )}

          {/* Big action buttons */}
          <div className="flex gap-3 flex-wrap justify-start mt-auto">
            <button
              disabled={busy || (!handler && !s.downloadUrl)}
              onClick={onInstall}
              className="font-extrabold px-8 py-3 rounded-xl text-lg transition
                         disabled:opacity-40 disabled:cursor-not-allowed
                         text-brand-ink hover:brightness-110"
              style={{
                background: accent,
                boxShadow:  `0 10px 30px -10px ${accent}aa`,
              }}
            >
              {ctaLabel}
            </button>

            {s.publisherUrl && (
              <button
                onClick={onOpenPublisher}
                className="bg-white/5 hover:bg-white/10 text-slate-200 font-bold
                           px-6 py-3 rounded-xl border border-white/10 transition"
              >
                מידע נוסף ↗
              </button>
            )}
          </div>
        </div>

        {/* Settings sidebar — kept structurally identical to GameDetailPanel
            so the layout stays uniform between the two surfaces. */}
        <div className="glass rounded-2xl p-5 self-start space-y-5">
          <h3 className="text-white font-bold text-lg">פרטים</h3>

          <div className="border-t border-white/5 pt-4 text-xs space-y-1.5">
            <Row k="זמינות"   v={availLabel} />
            <Row k="גרסה"     v={s.version || "—"} />
            {s.badge   && <Row k="תווית"  v={s.badge} />}
            {handler   && <Row k="מנגנון" v="התקנה אוטומטית" />}
          </div>

          {s.downloadUrl && (
            <a
              href={s.downloadUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="block w-full text-center text-xs px-3 py-2 rounded-lg
                         border border-white/10 text-slate-300 hover:bg-white/5 transition"
            >
              קישור הורדה ישיר ↗
            </a>
          )}
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
