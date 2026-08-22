// Universal live-progress card for the launcher's home view.
//
// Pulls /api/progress?game=<inProgressId> via the Python Eel bridge
// (`get_live_progress`) so the launcher reflects the exact same numbers
// the public website does. Phase labels come from phaseLabels.ts; admin
// can override per-game via `phaseLabelHe` on the row.
//
// Visual language matches the existing launcher: dark glass, brand
// yellow + cyan accents.
import type { Game } from "../lib/types";
import { useLiveGameProgress } from "../lib/useLiveGameProgress";
import LiquidWave from "./LiquidWave";
import {
  resolvePhaseHeadline,
  resolvePhaseDoneLabel,
  resolvePhaseRemainingLabel,
  resolvePhaseRateLabel,
} from "../lib/phaseLabels";

interface Props {
  game: Game;
  /** Bumped by App's sidebar refresh - re-pulls progress without remounting. */
  refreshNonce?: number;
}

const POLL_MS = 60_000;          // chatty enough to feel live, gentle on the API

export default function ProgressDashboard({ game, refreshNonce = 0 }: Props) {
  const { snap, loaded } = useLiveGameProgress(game.id, {
    refreshNonce,
    pollMs: POLL_MS,
  });

  const showDashboard = snap?.showDashboard ?? true;
  if (!showDashboard) return null;

  const updatedAt = snap?.updatedAt ?? null;

  // First-paint protection: render the whole card at zeros while the
  // initial fetch is in flight - better than briefly flashing the
  // stale static `game.progress`.
  const phase     = snap?.phase ?? "translation";
  const headline  = !loaded ? "טוען נתונים..." : resolvePhaseHeadline(phase, snap?.phaseLabelHe);
  const doneLabel = resolvePhaseDoneLabel(phase);
  const remLabel  = resolvePhaseRemainingLabel(phase);
  const rateLabel = resolvePhaseRateLabel(phase);
  const total     = snap?.total ?? 0;
  const processed = snap?.processed ?? 0;
  const remaining = Math.max(0, total - processed);
  const pct       = !loaded ? 0 : (total > 0 ? (processed / total) * 100 : 0);
  const unit      = snap?.unit ?? "";

  return (
    <section className="glass rounded-2xl p-6 mt-6" dir="rtl">
      <div className="flex items-baseline justify-between mb-4 flex-wrap gap-3">
        <div>
          <div className="text-[10px] tracking-[0.35em] text-brand-cyan opacity-70 mb-1 font-display">
            לוח בקרה · בייצור פעיל
          </div>
          <h2 className="text-xl font-bold text-white" dir="ltr">{game.titleEn}</h2>
        </div>
        {(snap?.aiModel || snap?.gpuModel) && (
          <div className="text-[11px] font-mono text-slate-400 tracking-wider">
            {[snap?.aiModel, snap?.gpuModel].filter(Boolean).join(" · ")}
          </div>
        )}
      </div>

      <div className="mb-1 flex items-center justify-between">
        <span className="text-sm font-bold text-brand-yellow">{headline}</span>
        <span className="font-mono text-base font-bold text-brand-yellow tabular-nums">
          {pct.toFixed(1)}%
        </span>
      </div>
      {/* Flowing "liquid wave" fill - the SAME rate-driven wave as the website's
          home progress dashboard (ported verbatim). The leading edge (RTL = left)
          rises/falls with the live rate and the surface follows it. */}
      <LiquidWave
        pct={pct}
        ratePerMin={(snap?.ratePerHour ?? 0) / 60}
        primary="#fff700"
        secondary="#00ffe0"
        glow="rgba(255,247,0,0.45)"
        height={72}
      />

      <div className="mt-4 grid grid-cols-3 gap-3">
        <Stat label={doneLabel} value={processed} accent="#fff700" />
        <Stat label={remLabel}  value={remaining} accent="#00ffe0" />
        <Stat label={rateLabel} value={snap?.ratePerHour ?? 0} accent="#fff700" suffix={unit} />
      </div>

      <div className="mt-3 flex items-center gap-2 text-[11px] text-slate-400">
        <span
          className="inline-block w-1.5 h-1.5 rounded-full"
          style={{
            background: snap ? "#22c55e" : "rgba(255,255,255,0.35)",
            boxShadow: snap ? "0 0 8px #22c55e" : "none",
          }}
        />
        <span title={updatedAt ? new Date(updatedAt).toLocaleString("he-IL") : undefined}>
          {!loaded
            ? "טוען נתוני התקדמות..."
            : snap
              ? `עודכן לאחרונה: ${hebrewRelative(updatedAt ?? Date.now())}`
              : "אין נתונים מהשרת"}
        </span>
      </div>
    </section>
  );
}

const RTF = new Intl.RelativeTimeFormat("he", { numeric: "auto" });
function hebrewRelative(ts: number): string {
  const diffSec = Math.round((ts - Date.now()) / 1000);
  const abs = Math.abs(diffSec);
  if (abs < 60)    return RTF.format(diffSec, "second");
  if (abs < 3600)  return RTF.format(Math.round(diffSec / 60), "minute");
  if (abs < 86400) return RTF.format(Math.round(diffSec / 3600), "hour");
  return RTF.format(Math.round(diffSec / 86400), "day");
}

function Stat({
  label, value, accent, suffix,
}: { label: string; value: number; accent: string; suffix?: string }) {
  return (
    <div className="glass-soft rounded-xl p-3 text-right">
      <div className="text-[10px] tracking-[0.25em] uppercase text-slate-400 mb-1">{label}</div>
      <div
        className="font-display text-2xl font-extrabold tabular-nums"
        style={{ color: accent, textShadow: `0 0 22px ${accent}55` }}
      >
        {value.toLocaleString("he-IL")}
        {suffix && (
          <span className="text-[10px] font-normal text-slate-400 ms-1.5">{suffix}</span>
        )}
      </div>
    </div>
  );
}

