// Software catalog — sister to LibraryView (games). Hosts non-game
// desktop software the launcher can install/manage. Data is pulled
// live from /api/software via the eel backend (so admin edits in the
// website dashboard surface here without redeploying the launcher).
//
// Known software with a built-in install action (currently just
// Steam) keeps its "Install" button; everything else opens the
// download URL externally.
import { useEffect, useState } from "react";
import { api } from "../lib/eel";
import { resolveCoverUrl } from "../lib/coverUrl";
import type { Software } from "../lib/types";

type ReportStatus = (text: string, warn?: boolean) => void;

interface Props {
  reportStatus?: ReportStatus;
  refreshNonce?: number;
  /** Click on a card → caller opens the full-screen detail panel. */
  onOpenSoftware?: (s: Software) => void;
}

export default function AppsView({ reportStatus, refreshNonce = 0, onOpenSoftware }: Props) {
  const [items, setItems] = useState<Software[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const data = await api.getAllSoftware();
        if (!alive) return;
        setItems(data);
      } catch (e) {
        if (!alive) return;
        setError(String(e));
        setItems([]);
      }
    })();
    return () => { alive = false; };
  }, [refreshNonce]);

  const [scanning, setScanning] = useState(false);
  const runScan = async () => {
    if (scanning) return;
    setScanning(true);
    reportStatus?.("סורק תוכנות מותקנות…");
    try {
      const r = await api.scanSoftware();
      setItems(r.software);
      const found = r.software.filter((x) => x.installed).length;
      reportStatus?.(`הסריקה הושלמה — ${found} מתוך ${r.software.length} מותקנות`);
    } catch (e) {
      reportStatus?.(String(e), true);
    } finally {
      setScanning(false);
    }
  };

  return (
    <div className="h-full overflow-y-auto px-8 py-6 animate-fade-in">
      <div className="flex items-center justify-between gap-3 mb-6 flex-wrap">
        <button
          disabled={scanning}
          onClick={runScan}
          className="px-5 py-2.5 rounded-xl bg-brand-yellow hover:bg-yellow-300
                     text-brand-ink text-sm font-bold disabled:opacity-50 transition
                     shadow-[0_6px_15px_-6px_rgba(255,247,0,0.5)]
                     flex items-center gap-2"
        >
          {scanning ? (
            <>
              <span className="w-4 h-4 border-2 border-brand-ink border-t-transparent rounded-full animate-spin" />
              סורק…
            </>
          ) : (
            "סרוק תוכנות"
          )}
        </button>
        <span className="text-slate-400 text-sm">
          {items === null ? "טוען..." : `${items.length} ${items.length === 1 ? "תוכנה" : "תוכנות"}`}
        </span>
        <h1 className="text-3xl font-extrabold text-white">תוכנות</h1>
      </div>

      {error && (
        <div className="rounded-xl border border-rose-500/30 bg-rose-500/[0.05] p-4 text-rose-200 text-sm mb-6">
          שגיאה בטעינת התוכנות: {error}
        </div>
      )}

      {items === null && !error && (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-5">
          {[0, 1].map((i) => (
            <div key={i} className="glass rounded-2xl h-72 animate-pulse" />
          ))}
        </div>
      )}

      {items !== null && items.length === 0 && !error && (
        <div className="text-center py-16">
          <div className="text-5xl mb-3" aria-hidden>🧰</div>
          <p className="text-slate-500 text-sm">
            אין תוכנות זמינות כרגע.
          </p>
        </div>
      )}

      {items !== null && items.length > 0 && (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-5">
          {items.map((s) => (
            <SoftwareCard
              key={s.id}
              s={s}
              reportStatus={reportStatus}
              onOpen={onOpenSoftware}
            />
          ))}
        </div>
      )}

      <p className="text-slate-500 text-xs text-center mt-10">
        תוכנות נוספות יתווספו בעדכונים הקרובים.
      </p>
    </div>
  );
}

// ---------------------------------------------------------------- card

function SoftwareCard({
  s, reportStatus, onOpen,
}: {
  s: Software;
  reportStatus?: ReportStatus;
  onOpen?: (s: Software) => void;
}) {
  const [busy, setBusy] = useState(false);
  const accent = s.accentColor || "#66c0f4";
  const cover  = resolveCoverUrl(s.cover, s.id);
  const handler = INSTALL_HANDLERS[s.id];

  // Card body click → open the detail panel (parity with how
  // LibraryView's GameCard opens GameDetailPanel). The bottom CTA
  // button stops propagation so the install action doesn't double-fire
  // with the open-panel action.
  const onCardClick = () => {
    if (onOpen) onOpen(s);
  };

  const onCtaClick = async (e: React.MouseEvent) => {
    e.stopPropagation();
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

  const ctaLabel = handler
    ? (busy ? "מתקין…" : "התקן")
    : (s.downloadUrl ? "הורד" : "בקרוב");

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onCardClick}
      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") onCardClick(); }}
      className="glass rounded-2xl p-5 flex flex-col gap-4 transition cursor-pointer
                 hover:scale-[1.015] hover:shadow-[0_18px_40px_-18px_rgba(0,0,0,0.6)]
                 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/40"
      style={{ borderTop: `2px solid ${accent}55` }}
    >
      {/* Cover plate */}
      <div
        className="h-32 rounded-xl relative overflow-hidden grid place-items-center"
        style={{
          background: cover
            ? "transparent"
            : `radial-gradient(circle at 30% 30%, ${accent}33, #0a0e1a 70%)`,
        }}
      >
        {cover && (
          <img
            src={cover}
            alt={s.titleEn}
            className="absolute inset-0 w-full h-full object-cover"
          />
        )}
        {!cover && (
          <div
            className="text-white font-extrabold text-2xl tracking-wide select-none"
            style={{ letterSpacing: "0.04em", textShadow: `0 2px 12px ${accent}88` }}
          >
            {s.titleEn}
          </div>
        )}

        {/* Local-presence chip (top-left of the plate). Only rendered
            after a scan/load actually filled the `installed` field — the
            absence of the chip means we don't know either way. */}
        {typeof s.installed === "boolean" && (
          <span
            className="absolute top-2 left-2 text-[10px] font-bold px-2 py-0.5 rounded-full
                       backdrop-blur-md tracking-wider"
            style={{
              background: s.installed ? "rgba(34,197,94,0.18)" : "rgba(148,163,184,0.18)",
              color:      s.installed ? "#86efac" : "#cbd5e1",
              border:     `1px solid ${s.installed ? "rgba(34,197,94,0.45)" : "rgba(148,163,184,0.35)"}`,
            }}
          >
            {s.installed ? "מותקן" : "לא מותקן"}
          </span>
        )}
      </div>

      {/* Title row */}
      <div className="flex items-start justify-between gap-3">
        {s.badge && (
          <span
            className="text-[10px] font-bold px-2 py-1 rounded-md uppercase tracking-wider whitespace-nowrap"
            style={{
              background: `${accent}22`,
              color:      accent,
              border:     `1px solid ${accent}55`,
            }}
          >
            {s.badge}
          </span>
        )}
        <div className="text-right min-w-0 flex-1">
          <div className="text-white font-bold text-lg leading-tight truncate">{s.titleEn}</div>
          {s.tagline && (
            <div className="text-slate-400 text-xs mt-0.5 truncate">{s.tagline}</div>
          )}
        </div>
      </div>

      {/* CTA */}
      <button
        onClick={onCtaClick}
        disabled={busy || (!handler && !s.downloadUrl)}
        className="w-full py-2.5 rounded-xl text-sm font-bold transition
                   disabled:opacity-60 disabled:cursor-wait
                   text-brand-ink hover:brightness-110"
        style={{ background: accent }}
      >
        {ctaLabel}
      </button>
    </div>
  );
}

// ---------------------------------------------------------------- handlers

// Software entries with a built-in install action (vs. just an
// external download link). The catalog row's `id` is the key — the
// admin can introduce new entries without touching the launcher,
// but actually wiring an installer is still a code change here.
type InstallHandler = (rs?: ReportStatus) => Promise<void>;

const INSTALL_HANDLERS: Partial<Record<string, InstallHandler>> = {
  steam: installSteamTranslation,
};

// Copies the compiled Hebrew translation files (steam_hebrew_output/*)
// from the launcher's repo into the user's live Steam install. The
// AppCard awaits this promise to drive the "מתקין…" spinner; the
// top-center toast (reportStatus) communicates final success/failure.
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
