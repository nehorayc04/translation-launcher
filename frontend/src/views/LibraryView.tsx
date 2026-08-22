// Library: default = grouped by mod state (with section headers); plus a
// grid/list view toggle and a sort menu (state / name / version). Refresh
// buttons for deep scan.
import type { Game } from "../lib/types";
import GameCard from "../components/GameCard";
import EmptyState from "../components/EmptyState";
import SmartImage from "../components/SmartImage";
import { IconOptBtnScanDrives } from "../components/UiIcons";
import { LibraryIcon } from "../components/NavIcons";
import { accentFor, availabilityLabel, availabilityRank, modStateLabel } from "../lib/theme";
import { resolveCoverUrl } from "../lib/coverUrl";
import { formatVersion } from "../lib/formatVersion";
import { usePersisted } from "../lib/usePersisted";
import { useFlipGrid } from "../lib/useFlipGrid";
import { gridCols, listGridCls, type CardSize, type ListCols } from "../lib/cardSize";
import CardSizePicker from "../components/CardSizePicker";
import SegmentedControl from "../components/SegmentedControl";
import ListLayoutPicker from "../components/ListLayoutPicker";
import { useEffect, useMemo, useRef, useState } from "react";

interface Props {
  games: Game[];
  onOpenGame:  (g: Game) => void;
  onScanDeep:  () => Promise<void>;
}

type ViewMode = "grid" | "list";
type SortMode = "state" | "name" | "version" | "status";

export default function LibraryView({ games, onOpenGame, onScanDeep }: Props) {
  const [busy, setBusy] = useState<"deep" | null>(null);
  // Persisted so the choice survives leaving + returning to the view.
  const [viewMode, setViewMode] = usePersisted<ViewMode>("libViewMode", "grid");
  const [sortMode, setSortMode] = usePersisted<SortMode>("libSortMode", "state");
  const [cardSize, setCardSize] = usePersisted<CardSize>("libCardSize", "md");
  const [listCols, setListCols] = usePersisted<ListCols>("libListCols", "1");

  const sections = useMemo(() => {
    const withMod   = games.filter((g) => g.is_installed && g.mod_state === "ACTIVE");
    const withModD  = games.filter((g) => g.is_installed && g.mod_state === "DISABLED");
    const installed = games.filter((g) =>
      g.is_installed && g.mod_state !== "ACTIVE" && g.mod_state !== "DISABLED"
    );
    const missing   = games.filter((g) => !g.is_installed);
    return [
      { key: "mod",       title: "מותקנים - תרגום פעיל",   items: withMod,   accent: "#22c55e" },
      { key: "moddis",    title: "מותקנים - תרגום מושבת",  items: withModD,  accent: "#f59e0b" },
      { key: "installed", title: "מותקנים ללא תרגום",      items: installed, accent: "#a0a7b3" },
      { key: "missing",   title: "לא נמצאו במחשב",         items: missing,   accent: "#5a627a" },
    ].filter((s) => s.items.length > 0);
  }, [games]);

  // "לפי זמינות" - grouped by the mod/availability status (זמין / בעבודה / בקרוב /
  // מתוכנן / מושהה / בארכיון), each its own section, ordered by rank. Distinct from
  // "התקנה" above (which groups by whether the game is installed + has a mod).
  const statusSections = useMemo(() => {
    const RANK_META: Record<number, { title: string; accent: string }> = {
      0: { title: "זמין",         accent: "#22c55e" },
      1: { title: "בעבודה",       accent: "#f59e0b" },
      2: { title: "בבקרת איכות",  accent: "#a78bfa" },
      3: { title: "בקרוב",        accent: "#38bdf8" },
      4: { title: "מתוכנן",       accent: "#a0a7b3" },
      5: { title: "מושהה",        accent: "#8b93a7" },
      6: { title: "בארכיון",      accent: "#5a627a" },
      9: { title: "אחר",          accent: "#5a627a" },
    };
    const groups = new Map<number, Game[]>();
    for (const g of games) {
      const r = availabilityRank(g.availability);
      if (!groups.has(r)) groups.set(r, []);
      groups.get(r)!.push(g);
    }
    return [...groups.entries()]
      .sort((a, b) => a[0] - b[0])
      .map(([rank, items]) => ({
        key: `st-${rank}`,
        title:  (RANK_META[rank] ?? RANK_META[9]).title,
        accent: (RANK_META[rank] ?? RANK_META[9]).accent,
        items:  [...items].sort((x, y) => x.titleEn.localeCompare(y.titleEn, "en")),
      }));
  }, [games]);

  // Flat sorted list used when sort != "state".
  const flat = useMemo(() => {
    const arr = [...games];
    if (sortMode === "name") {
      arr.sort((a, b) => a.titleEn.localeCompare(b.titleEn, "en"));
    } else if (sortMode === "version") {
      arr.sort((a, b) => (b.version || "").localeCompare(a.version || "", undefined, { numeric: true }));
    } else if (sortMode === "status") {
      arr.sort((a, b) =>
        availabilityRank(a.availability) - availabilityRank(b.availability) ||
        a.titleEn.localeCompare(b.titleEn, "en"));
    }
    return arr;
  }, [games, sortMode]);

  // The Qt scan is FIRE-AND-FORGET (resolves immediately; the real results arrive
  // via a games-prop update), so we keep the "scanning" spinner running until the
  // list actually updates - that gives a real scan animation while the wheel stays
  // free - instead of clearing it the instant the call returns.
  const scanStartRef = useRef(0);
  const runDeep = async () => {
    setBusy("deep");
    scanStartRef.current = Date.now();
    try { await onScanDeep(); } catch { /* toast handled upstream */ }
  };
  // Clear the scan spinner when the games list updates (the scan's push landed).
  useEffect(() => {
    if (busy === "deep" && scanStartRef.current && Date.now() - scanStartRef.current > 1200) {
      setBusy(null);
    }
  }, [games]); // eslint-disable-line react-hooks/exhaustive-deps
  // Safety cap so the spinner can never spin forever.
  useEffect(() => {
    if (busy !== "deep") return;
    const t = setTimeout(() => setBusy(null), 120_000);
    return () => clearTimeout(t);
  }, [busy]);

  const total = useMemo(() => games.length, [games]);

  // FLIP layout animation: when the sort / view / size / category grouping changes,
  // the cards deal into their new spots and the category separators slide with them
  // (like the website). `flip()` is called RIGHT BEFORE each such state change.
  const bodyRef = useRef<HTMLDivElement>(null);
  // Card-DEAL FLIP: on a sort / view / size / category change the cards deal into
  // their new spots and the section separators slide. It runs ONLY on those
  // discrete changes (NOT on the sidebar open/close - that gets the continuous
  // space-evenly gap glide from the CSS grid). `flip()` is called right before
  // each state change. Earlier scatter/overlap was the removed EvenGrid changing
  // justify AFTER the FLIP captured positions; with the stable CSS grid it deals
  // cleanly.
  const flip = useFlipGrid(bodyRef, [sortMode, viewMode, cardSize, listCols]);

  const renderItems = (items: Game[]) =>
    viewMode === "grid" ? (
      // auto-fill + the chosen card size → the column count follows the window
      // width (≈3 on large / 4 on medium / 5-6 on small, more when wider), and
      // the fluid card FILLS its cell so it really resizes.
      <div className="grid gap-3 justify-evenly" style={{ gridTemplateColumns: gridCols(cardSize) }}>
        {items.map((g) => (
          <div key={g.id} data-flip-id={`card-${g.id}`} className="min-w-0">
            <GameCard game={g} onClick={onOpenGame} size="fluid" />
          </div>
        ))}
      </div>
    ) : (
      // List view: 1 / 2 / 3 game-rows per line (the rows fill their grid cell).
      <div className={listGridCls(listCols)}>
        {items.map((g) => (
          <div key={g.id} data-flip-id={`card-${g.id}`} className="min-w-0">
            <GameRow game={g} onClick={onOpenGame} />
          </div>
        ))}
      </div>
    );

  return (
    <div className="h-full overflow-y-auto px-8 py-6 animate-fade-in">
      {/* Header - title on the RIGHT (RTL start), scan button on the LEFT. */}
      <div className="flex items-center justify-between mb-7 animate-rise">
        <div className="text-right">
          <h1 className="text-3xl font-extrabold inline-flex items-center gap-1.5">
            {/* YELLOW → white (RTL), matching the games nav accent. */}
            <LibraryIcon width={22} height={22} className="shrink-0 opacity-90" style={{ color: "#fff700" }} />
            <span style={{ background: "linear-gradient(90deg, #ffffff 0%, #fff700 100%)", WebkitBackgroundClip: "text", backgroundClip: "text", color: "transparent" }}>ספריית המשחקים</span>
          </h1>
          <p className="text-slate-400 text-xs mt-1">{total} כותרים בקטלוג</p>
        </div>
        <button
          type="button"
          data-tour="scan"
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
            <><IconOptBtnScanDrives width={18} className="shrink-0 opacity-90" />סריקת כוננים מלאה</>
          )}
        </button>
      </div>

      {/* Toolbar - sort + view toggle, aligned to the RIGHT (RTL start) under
          the title. justify-start packs the cluster to the right edge. */}
      {sections.length > 0 && (
        <div className="flex items-center justify-start gap-3 mb-6 -mt-2">
          {/* Sort - the shared segmented control (slides + glasses like the rest). */}
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <span>מיון</span>
            <SegmentedControl<SortMode>
              ariaLabel="מיון"
              value={sortMode}
              onChange={(v) => { flip(); setSortMode(v); }}
              size="sm"
              showHints={false}
              options={[
                { value: "state",   label: "התקנה" },
                { value: "status",  label: "זמינות" },
                { value: "name",    label: "שם" },
                { value: "version", label: "גרסה" },
              ]}
            />
          </div>

          {/* Grid / list toggle (2 choices) - on the RIGHT (RTL start). */}
          <SegmentedControl<ViewMode>
            ariaLabel="תצוגה"
            value={viewMode}
            onChange={(v) => { flip(); setViewMode(v); }}
            size="sm"
            showHints={false}
            options={[
              { value: "grid", title: "תצוגת רשת", icon: (
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
                  <rect x="3" y="3" width="8" height="8" rx="1.5" /><rect x="13" y="3" width="8" height="8" rx="1.5" />
                  <rect x="3" y="13" width="8" height="8" rx="1.5" /><rect x="13" y="13" width="8" height="8" rx="1.5" />
                </svg>
              ) },
              { value: "list", title: "תצוגת רשימה", icon: (
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
                  <rect x="3" y="4" width="18" height="3" rx="1.5" /><rect x="3" y="10.5" width="18" height="3" rx="1.5" />
                  <rect x="3" y="17" width="18" height="3" rx="1.5" />
                </svg>
              ) },
            ]}
          />

          {/* Density picker (3 choices) - on the LEFT: card size in grid view,
              rows-per-line in list view. */}
          {viewMode === "grid"
            ? <CardSizePicker value={cardSize} onChange={(v) => { flip(); setCardSize(v); }} />
            : <ListLayoutPicker value={listCols} onChange={(v) => { flip(); setListCols(v); }} />}
        </div>
      )}

      {/* Empty state */}
      {sections.length === 0 && (
        <EmptyState
          title="לא נמצאו משחקים"
          hint="עדיין לא זוהו משחקים נתמכים במחשב. הרץ סריקת כוננים מלאה כדי לאתר התקנות בכל הכוננים."
          accent="#fff700"
          action={{ label: "סריקת כוננים מלאה", onClick: runDeep }}
          icon={
            <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
              <circle cx="11" cy="11" r="7" /><path d="m21 21-4.3-4.3" />
            </svg>
          }
        />
      )}

      {/* Body - grouped by install-state ("התקנה") or availability ("זמינות"),
          each into its own titled section; a flat list only for name / version. */}
      <div ref={bodyRef} className="relative">
      {sections.length > 0 && (sortMode === "state" || sortMode === "status") ? (
        (sortMode === "state" ? sections : statusSections).map((sec) => (
          <section key={sec.key} className="mb-10">
            <div data-flip-id={`hdr-${sec.key}`} className="flex items-center gap-3 mb-4">
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
        <section className="mb-10">{renderItems(flat)}</section>
      ) : null}
      </div>
    </div>
  );
}

/* ── Compact list row (list view) ──────────────────────────────────── */
function GameRow({ game, onClick }: { game: Game; onClick: (g: Game) => void }) {
  const accent = accentFor(game.theme_key);
  const avail  = availabilityLabel(game.availability);
  const modBadge = game.has_mod_support && game.mod_state !== "NOT_INSTALLED" ? modStateLabel(game.mod_state) : null;
  const active = game.mod_state === "ACTIVE";
  const cover  = resolveCoverUrl(game.cover, game.id);

  return (
    <button
      type="button"
      onClick={() => onClick(game)}
      className="group glass-soft lift rounded-2xl p-2.5 flex items-center gap-4 text-right w-full
                 border border-white/5 hover:border-white/10"
      style={{ direction: "rtl", ["--tw-ring-color" as string]: `${accent}55` }}
    >
      {/* The thumbnail SLOT carries the tint, not the image: that covers both
          states at once - the skeleton sweeps over it while the cover streams
          in (it inherits --skeleton-* from here), and a cover that never
          arrives leaves a tinted slot instead of an empty hole, because
          SmartImage hides a broken <img> and there is nothing behind it. */}
      <div className="relative w-12 h-16 rounded-lg overflow-hidden shrink-0 ring-1 ring-white/10"
           style={{
             background: `linear-gradient(160deg, ${accent}22, ${accent}08)`,
             ["--skeleton-tint" as string]: `${accent}1a`,
             ["--skeleton-sheen" as string]: `${accent}30`,
           }}>
        <SmartImage src={cover} alt={game.titleEn} draggable={false}
             className="absolute inset-0 w-full h-full object-cover"
             onError={(e) => { (e.currentTarget as HTMLImageElement).style.visibility = "hidden"; }} />
        {active && <span className="absolute top-1 left-1 w-2 h-2 rounded-full" style={{ background: "#22c55e", boxShadow: "0 0 8px #22c55e" }} />}
      </div>
      <div className="flex-1 min-w-0">
        <div className="font-bold text-white truncate" style={{ color: accent }}>
          {game.titleEn}
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
