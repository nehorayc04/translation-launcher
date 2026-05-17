// "הורדות ועדכונים" — system updates + translation updates with a live
// HTML/CSS progress bar driven by Python's update_download_progress push.
// The list itself is SWR-cached: instant first paint from the on-disk
// snapshot, then quietly refreshed in the background.
import { useEffect, useMemo, useState } from "react";
import { api, type UpdateItem } from "../lib/eel";
import { useDownloadProgress } from "../lib/useDownloadProgress";
import { useSWRSource } from "../lib/useSWRSource";

interface Props {
  /** Bumped by App whenever the sidebar refresh button completes — forces
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

  return (
    <div className="h-full overflow-y-auto px-8 py-6 animate-fade-in">
      <div className="mb-6 flex items-center justify-between">
        <span className="text-xs text-slate-500">
          {loading ? "טוען..." : `${items.length} פריטים זמינים`}
        </span>
        <h1 className="text-3xl font-extrabold text-white">הורדות ועדכונים</h1>
      </div>

      {loading ? (
        <Loader />
      ) : items.length === 0 ? (
        <Empty />
      ) : (
        <div className="space-y-8">
          <Section title="עדכוני מערכת"     accent="#fff700" items={system}       progress={progress} />
          <Section title="עדכוני תרגומים"  accent="#00ffe0" items={translations} progress={progress} />
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
        <h2 className="text-xl font-bold text-white">{title}</h2>
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
          {item.size_mb.toFixed(1)} MB
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
                           bg-emerald-500/20 text-emerald-200 ring-1 ring-emerald-400/30">
            מותקן
          </span>
        ) : failed ? (
          <button
            onClick={handleDownload}
            className="text-[12px] font-bold px-4 py-1.5 rounded-lg
                       bg-rose-500/15 text-rose-200 hover:bg-rose-500/30 transition"
          >
            נסה שוב
          </button>
        ) : (
          <button
            onClick={handleDownload}
            className="text-[12px] font-bold px-4 py-1.5 rounded-lg
                       bg-brand-yellow hover:bg-yellow-300 text-brand-ink transition
                       shadow-[0_4px_12px_-4px_rgba(255,247,0,0.5)]"
          >
            הורד ועדכן
          </button>
        )}
      </div>

      {/* Progress bar — appears only while running or just finished */}
      {(running || done || failed) && (
        <div className="mt-4">
          <div className="flex justify-between text-[10px] mb-1">
            <span dir="ltr" className="text-slate-300 font-mono">
              {speed || (done ? "100%" : "—")}
            </span>
            <span className="text-slate-400">{pct.toFixed(1)}%</span>
          </div>
          <div className="h-1.5 bg-white/5 rounded-full overflow-hidden ring-1 ring-white/5">
            <div
              className="h-full rounded-full"
              style={{
                width: `${pct}%`,
                background: failed ? "#ef4444"
                           : done   ? "#22c55e"
                                    : `linear-gradient(90deg, ${accent}, #fff)`,
                transition: "width 0.2s linear, background-color 0.2s ease",
                boxShadow: failed ? "none" : `0 0 12px ${accent}80`,
              }}
            />
          </div>
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
    <div className="glass-soft rounded-2xl p-10 text-center text-slate-400">
      אין עדכונים זמינים כרגע.
    </div>
  );
}
