// Software catalog — sister to LibraryView (games). Hosts non-game
// desktop software the launcher can install/manage. Data is pulled
// live from /api/software via the eel backend (so admin edits in the
// website dashboard surface here without redeploying the launcher).
//
// Known software with a built-in install action (currently just
// Steam) keeps its "Install" button; everything else opens the
// download URL externally.
import { useEffect, useState } from "react";
import { api, onModProgress } from "../lib/eel";
import type { SteamModState, ModProgress } from "../lib/eel";
import { resolveCoverUrl } from "../lib/coverUrl";
import type { Software } from "../lib/types";

type ReportStatus = (text: string, warn?: boolean) => void;

interface Props {
  reportStatus?: ReportStatus;
  refreshNonce?: number;
  /** Click on a card → caller opens the full-screen detail panel. */
  onOpenSoftware?: (s: Software) => void;
  /** CTA fallback when no built-in install handler exists for a card.
   *  Navigates the launcher's main view to the "הורדות" tab — used to
   *  be window.open(s.downloadUrl) which leaked the user to a browser. */
  onNavigateToDownloads?: () => void;
}

export default function AppsView({ reportStatus, refreshNonce = 0, onOpenSoftware, onNavigateToDownloads }: Props) {
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
              onNavigateToDownloads={onNavigateToDownloads}
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
  s, reportStatus, onOpen, onNavigateToDownloads,
}: {
  s: Software;
  reportStatus?: ReportStatus;
  onOpen?: (s: Software) => void;
  onNavigateToDownloads?: () => void;
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

  // paused / archived software isn't installable — CTA reads "לא זמין".
  const unavailable = s.availability === "paused" || s.availability === "archived";

  const onCtaClick = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (busy || unavailable) return;
    if (handler) {
      setBusy(true);
      try { await handler(reportStatus); }
      finally { setBusy(false); }
      return;
    }
    // No built-in handler → bring the user to the launcher's own
    // הורדות tab instead of opening an external publisher link.
    onNavigateToDownloads?.();
  };

  const ctaLabel = unavailable
    ? "לא זמין"
    : handler
      ? (busy ? "מתקין…" : "התקן")
      : "פתח הורדות";

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
                       tracking-wider"
            style={{
              background: s.installed ? "rgba(10,28,16,0.92)" : "rgba(18,22,32,0.92)",
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

      {/* CTA — Steam has the full install/enable/disable lifecycle; every
          other software keeps the generic button. */}
      {s.id === "steam" ? (
        <SteamCardCta accent={accent} reportStatus={reportStatus} availability={s.availability} />
      ) : (
        <button
          onClick={onCtaClick}
          disabled={busy || unavailable || (!handler && !onNavigateToDownloads)}
          className={`w-full py-2.5 rounded-xl text-sm font-bold transition
                     disabled:opacity-60 disabled:cursor-not-allowed
                     ${unavailable
                       ? "bg-white/5 text-slate-400 border border-white/10"
                       : "text-brand-ink hover:brightness-110"}`}
          style={unavailable ? undefined : { background: accent }}
        >
          {ctaLabel}
        </button>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- handlers

// Software entries with a built-in install action (vs. an external
// download link). Steam is NOT here — it has the richer install/
// enable/disable lifecycle in <SteamCardCta> below. Add other simple
// one-shot software installers to this map.
type InstallHandler = (rs?: ReportStatus) => Promise<void>;

const INSTALL_HANDLERS: Partial<Record<string, InstallHandler>> = {};

// ---------------------------------------------------------- Steam lifecycle

// Install-phase → Hebrew label. Only "apply" fires in the local-cache
// flow; download/verify/extract arrive once the GitHub proxy is wired.
const PHASE_HE: Record<string, string> = {
  download: "מוריד",
  verify:   "מאמת",
  extract:  "מחלץ",
  apply:    "מתקין",
};

/** CTA for the Steam card — a 3-state machine:
 *    not cached      → "התקן"  (download + enable)
 *    cached, enabled → "השבת"  (revert Steam to its originals)
 *    cached, off     → "הפעל"  (re-apply from the local cache)
 *  While an op runs it shows a phase-aware progress bar fed by
 *  `mod_install_progress` events. */
function SteamCardCta({
  accent, reportStatus, availability,
}: {
  accent: string;
  reportStatus?: ReportStatus;
  /** Catalog availability — 'paused' / 'archived' disable the CTA. */
  availability?: string;
}) {
  const [state, setState]       = useState<SteamModState | null>(null);
  const [busy, setBusy]         = useState(false);
  const [progress, setProgress] = useState<ModProgress | null>(null);

  // When the software is paused/archived in the catalog the install
  // pipeline is intentionally on hold — the CTA reads "לא זמין".
  const unavailable = availability === "paused" || availability === "archived";

  const refresh = async () => {
    try {
      setState(await api.getSteamModState());
    } catch {
      setState({ cached: false, enabled: false, version: null });
    }
  };
  useEffect(() => { void refresh(); }, []);

  // Subscribe to progress ticks only while an operation is in flight.
  useEffect(() => {
    if (!busy) return;
    const off = onModProgress(setProgress);
    return () => { off(); setProgress(null); };
  }, [busy]);

  const run = async (action: "install" | "enable" | "disable", e: React.MouseEvent) => {
    e.stopPropagation();                       // don't also open the detail panel
    if (busy) return;
    setBusy(true);
    try {
      const r = action === "install"
        ? await api.applySteamTranslation()
        : await api.setSteamModEnabled(action === "enable");
      if (r.ok) {
        reportStatus?.(action === "disable"
          ? "התרגום הושבת — Steam חזר לשפת המקור"
          : "✓ בוצע. הפעל מחדש את Steam עם שפה: العربية");
        // Derive the new state DIRECTLY from the operation outcome.
        // A successful install/enable means cached+enabled; disable
        // means cached+disabled. The post-op refresh() below can't be
        // relied on alone — its eel round-trip races right after a long
        // applySteamTranslation() call (the button-stuck-on-התקן bug).
        setState((prev) => ({
          cached:  true,
          enabled: action !== "disable",
          version: prev?.version ?? null,
        }));
      } else {
        reportStatus?.(r.error || "שגיאה לא ידועה", true);
      }
    } catch (err) {
      reportStatus?.(`כשל בקריאה לשרת: ${String(err)}`, true);
    } finally {
      setBusy(false);
      void refresh();                          // reconcile (version string etc.)
    }
  };

  // Paused / archived → flat disabled "לא זמין", no state machine.
  if (unavailable) {
    return (
      <button
        disabled
        onClick={(e) => e.stopPropagation()}
        className="w-full py-2.5 rounded-xl text-sm font-bold transition
                   bg-white/5 text-slate-400 border border-white/10 cursor-not-allowed"
      >
        לא זמין
      </button>
    );
  }

  // In-flight → phase-aware progress bar.
  if (busy) {
    const phase = progress ? (PHASE_HE[progress.phase] ?? progress.phase) : "מתחיל";
    const pct   = progress?.pct ?? 0;
    return (
      <div
        className="w-full rounded-xl px-3 py-2"
        style={{ background: `${accent}22`, border: `1px solid ${accent}55` }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between text-[11px] font-bold mb-1.5">
          <span className="text-slate-300">{Math.round(pct)}%</span>
          <span className="text-white">{phase}…</span>
        </div>
        <div className="h-1.5 rounded-full bg-black/30 overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-200"
            style={{ width: `${Math.max(4, pct)}%`, background: accent }}
          />
        </div>
      </div>
    );
  }

  // Idle → state-machine button.
  let label = "טוען…";
  let action: "install" | "enable" | "disable" | null = null;
  if (state) {
    if (!state.cached)      { label = "התקן"; action = "install"; }
    else if (state.enabled) { label = "השבת"; action = "disable"; }
    else                    { label = "הפעל"; action = "enable";  }
  }

  return (
    <button
      onClick={(e) => { if (action) void run(action, e); }}
      disabled={action === null}
      className="w-full py-2.5 rounded-xl text-sm font-bold transition
                 disabled:opacity-60 disabled:cursor-wait
                 text-brand-ink hover:brightness-110"
      style={{ background: accent }}
    >
      {label}
    </button>
  );
}
