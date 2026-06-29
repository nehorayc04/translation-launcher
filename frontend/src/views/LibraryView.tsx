// Library: default = grouped by mod state (with section headers); plus a
// grid/list view toggle and a sort menu (state / name / version). Refresh
// buttons for deep scan.
import type { Game } from "../lib/types";
import GameCard from "../components/GameCard";
import EmptyState from "../components/EmptyState";
import { accentFor, availabilityLabel, modStateLabel } from "../lib/theme";
import { resolveCoverUrl } from "../lib/coverUrl";
import { formatVersion } from "../lib/formatVersion";
import { useMemo, useState } from "react";

interface Props {
  games: Game[];
  onOpenGame:  (g: Game) => void;
  onScanDeep:  () => Promise<void>;
}

type ViewMode = "grid" | "list";
type SortMode = "state" | "name" | "version";

export default function LibraryView({ games, onOpenGame, onScanDeep }: Props) {
  const [busy, setBusy] = useState<"deep" | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>("grid");
  const [sortMode, setSortMode] = useState<SortMode>("state");

  const sections = useMemo(() => {
    const withMod   = games.filter((g) => g.is_installed && g.mod_state === "ACTIVE");
    const withModD  = games.filter((g) => g.is_installed && g.mod_state === "DISABLED");
    const installed = games.filter((g) =>
      g.is_installed && g.mod_state !== "ACTIVE" && g.mod_state !== "DISABLED"
    );
    const missing   = games.filter((g) => !g.is_installed);
    return [
      { key: "mod",       title: "מותקנים — תרגום פעיל",   items: withMod,   accent: "#22c55e" },
      { key: "moddis",    title: "מותקנים — תרגום מושבת",  items: withModD,  accent: "#f59e0b" },
      { key: "installed", title: "מותקנים ללא תרגום",      items: installed, accent: "#a0a7b3" },
      { key: "missing",   title: "לא נמצאו במחשב",         items: missing,   accent: "#5a627a" },
    ].filter((s) => s.items.length > 0);
  }, [games]);

  // Flat sorted list used when sort != "state".
  const flat = useMemo(() => {
    const arr = [...games];
    if (sortMode === "name") {
      arr.sort((a, b) => (a.titleHe || a.titleEn).localeCompare(b.titleHe || b.titleEn, "he"));
    } else if (sortMode === "version") {
      arr.sort((a, b) => (b.version || "").localeCompare(a.version || "", undefined, { numeric: true }));
    }
    return arr;
  }, [games, sortMode]);

  const runDeep = async () => {
    setBusy("deep");
    try { await onScanDeep(); } finally { setBusy(null); }
  };

  const total = useMemo(() => games.length, [games]);

  const renderItems = (items: Game[]) =>
    viewMode === "grid" ? (
      <div className="grid grid-cols-[repeat(auto-fill,minmax(180px,1fr))] gap-5">
        {items.map((g) => (
          <div key={g.id} className="flex justify-center">
            <GameCard game={g} onClick={onOpenGame} />
          </div>
        ))}
      </div>
    ) : (
      <div className="flex flex-col gap-2">
        {items.map((g) => <GameRow key={g.id} game={g} onClick={onOpenGame} />)}
      </div>
    );

  return (
    <div className="h-full overflow-y-auto px-8 py-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between mb-7 animate-rise">
        <button
          disabled={busy !== null}
          onClick={runDeep}
          className="group relative overflow-hidden px-5 py-2.5 rounded-xl bg-brand-yellow hover:brightness-110
                     text-brand-ink text-sm font-bold disabled:opacity-50 transition
                     shadow-[0_8px_20px_-8px_rgba(255,247,0,0.6)]
                     flex items-center gap-2"
        >
          <span className="sheen-layer" aria-hidden />
          {busy === "deep" ? (
            <>
              <span className="w-4 h-4 border-2 border-brand-ink border-t-transparent
                               rounded-full animate-spin" />
              סורק את כל הכוננים…
            </>
          ) : (
            <>🔎 סריקת כוננים מלאה</>
          )}
        </button>
        <div className="text-right">
          <h1 className="text-3xl font-extrabold">
            <span className="text-gradient">ספריית המשחקים</span>
          </h1>
          <p className="text-slate-400 text-xs mt-1">{total} כותרים בקטלוג</p>
        </div>
      </div>

      {/* Toolbar — sort + view toggle (RTL: controls on the right) */}
      {sections.length > 0 && (
        <div className="flex items-center justify-end gap-3 mb-6 -mt-2">
          {/* Sort */}
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <span>מיון</span>
            <div className="flex rounded-lg overflow-hidden border border-white/10">
              {([
                ["state", "לפי מצב"],
                ["name", "לפי שם"],
                ["version", "לפי גרסה"],
              ] as [SortMode, string][]).map(([k, label]) => (
                <button
                  key={k}
                  type="button"
                  onClick={() => setSortMode(k)}
                  className={[
                    "px-3 py-1.5 transition",
                    sortMode === k
                      ? "bg-brand-cyan/15 text-brand-cyan font-semibold"
                      : "text-slate-400 hover:bg-white/5",
                  ].join(" ")}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          {/* Grid / list */}
          <div className="flex rounded-lg overflow-hidden border border-white/10">
            <button
              type="button"
              onClick={() => setViewMode("grid")}
              title="תצוגת רשת"
              aria-label="תצוגת רשת"
              className={["px-3 py-1.5 grid place-items-center transition",
                viewMode === "grid" ? "bg-brand-cyan/15 text-brand-cyan" : "text-slate-400 hover:bg-white/5"].join(" ")}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
                <rect x="3" y="3" width="8" height="8" rx="1.5" /><rect x="13" y="3" width="8" height="8" rx="1.5" />
                <rect x="3" y="13" width="8" height="8" rx="1.5" /><rect x="13" y="13" width="8" height="8" rx="1.5" />
              </svg>
            </button>
            <button
              type="button"
              onClick={() => setViewMode("list")}
              title="תצוגת רשימה"
              aria-label="תצוגת רשימה"
              className={["px-3 py-1.5 grid place-items-center transition",
                viewMode === "list" ? "bg-brand-cyan/15 text-brand-cyan" : "text-slate-400 hover:bg-white/5"].join(" ")}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
                <rect x="3" y="4" width="18" height="3" rx="1.5" /><rect x="3" y="10.5" width="18" height="3" rx="1.5" />
                <rect x="3" y="17" width="18" height="3" rx="1.5" />
              </svg>
            </button>
          </div>
        </div>
      )}

      {/* Empty state */}
      {sections.length === 0 && (
        <EmptyState
          title="לא נמצאו משחקים"
          hint="עדיין לא זוהו משחקים נתמכים במחשב. הרץ סריקת כוננים מלאה כדי לאתר התקנות בכל הכוננים."
          accent="#fff700"
          action={{ label: "🔎 סריקת כוננים מלאה", onClick: runDeep }}
          icon={
            <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
              <circle cx="11" cy="11" r="7" /><path d="m21 21-4.3-4.3" />
            </svg>
          }
        />
      )}

      {/* Body — grouped (default) or flat sorted */}
      {sections.length > 0 && sortMode === "state" ? (
        sections.map((sec) => (
          <section key={sec.key} className="mb-10 animate-rise">
            <div className="flex items-center gap-3 mb-4">
              <span
                className="text-[11px] font-bold px-2 py-0.5 rounded-full ring-1 tabular-nums"
                style={{ color: sec.accent, background: `${sec.accent}1a`, ["--tw-ring-color" as string]: `${sec.accent}40` }}
              >
                {sec.items.length}
              </span>
              <h2 className="flex items-center gap-2.5 text-xl font-bold text-white whitespace-nowrap">
                <span className="h-5 w-1.5 rounded-full" style={{ background: sec.accent, boxShadow: `0 0 12px ${sec.accent}99` }} />
                {sec.title}
              </h2>
              <span
                className="h-px flex-1 rounded-full opacity-40"
                style={{ background: `linear-gradient(to left, ${sec.accent}, transparent)` }}
              />
            </div>
            {renderItems(sec.items)}
          </section>
        ))
      ) : sections.length > 0 ? (
        <section className="mb-10 animate-rise">{renderItems(flat)}</section>
      ) : null}
    </div>
  );
}

/* ── Compact list row (list view) ──────────────────────────────────── */
function GameRow({ game, onClick }: { game: Game; onClick: (g: Game) => void }) {
  const accent = accentFor(game.theme_key);
  const avail  = availabilityLabel(game.availability);
  const modBadge = game.has_mod_support ? modStateLabel(game.mod_state) : null;
  const active = game.mod_state === "ACTIVE";
  const cover  = resolveCoverUrl(game.cover, game.id);

  return (
    <button
      type="button"
      onClick={() => onClick(game)}
      className="group glass-soft lift rounded-2xl p-2.5 flex items-center gap-4 text-right
                 border border-white/5 hover:border-white/10"
      style={{ direction: "rtl", ["--tw-ring-color" as string]: `${accent}55` }}
    >
      <div className="relative w-12 h-16 rounded-lg overflow-hidden shrink-0 ring-1 ring-white/10">
        <img src={cover} alt={game.titleEn} draggable={false}
             className="w-full h-full object-cover"
             onError={(e) => { (e.currentTarget as HTMLImageElement).style.visibility = "hidden"; }} />
        {active && <span className="absolute top-1 left-1 w-2 h-2 rounded-full" style={{ background: "#22c55e", boxShadow: "0 0 8px #22c55e" }} />}
      </div>
      <div className="flex-1 min-w-0">
        <div className="font-bold text-white truncate" style={{ color: accent }}>
          {game.titleHe || game.titleEn}
        </div>
        <div className="text-[11px] text-slate-400 mt-0.5 truncate" dir="ltr">
          {formatVersion(game.version)}
        </div>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        {modBadge && (
          <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${modBadge.tone}`}>{modBadge.text}</span>
        )}
        <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${avail.tone}`}>{avail.text}</span>
      </div>
    </button>
  );
}
