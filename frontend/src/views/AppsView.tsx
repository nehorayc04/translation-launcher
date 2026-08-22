// Software library. Software rows come from the SAME catalog as games
// (flagged isSoftware) and carry the FULL game shape - so this view is the
// games library with the software slice: identical GameCard, identical
// state-grouped sections, identical sort + grid/list toolbar. Only the
// header/scan-button palette is cyan instead of gold.
//
// Opening a card hands the row to the very same GameDetailPanel a game uses.
import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../lib/eel";
import type { Game } from "../lib/types";
import GameCard from "../components/GameCard";
import EmptyState from "../components/EmptyState";
import SmartImage from "../components/SmartImage";
import { availabilityLabel, availabilityRank, modStateLabel } from "../lib/theme";
import { resolveCoverUrl } from "../lib/coverUrl";
import { formatVersion } from "../lib/formatVersion";
import { usePersisted } from "../lib/usePersisted";
import { useFlipGrid } from "../lib/useFlipGrid";
import { gridCols, listGridCls, type CardSize, type ListCols } from "../lib/cardSize";
import CardSizePicker from "../components/CardSizePicker";
import SegmentedControl from "../components/SegmentedControl";
import ListLayoutPicker from "../components/ListLayoutPicker";
import { IconOptBtnScanSoftware, IconOptHdrSoftwareLibrary } from "../components/UiIcons";

type ReportStatus = (text: string, warn?: boolean) => void;
type ViewMode = "grid" | "list";
type SortMode = "state" | "name" | "version" | "status";

interface Props {
  /** Supplied by App - fetched ONCE at boot (and kept live by the SWR push), so
   *  opening "תוכנות" paints instantly instead of fetching on every mount. */
  software?: Game[];
  reportStatus?: ReportStatus;
  refreshNonce?: number;
  onOpenSoftware?: (g: Game) => void;
  onNavigateToDownloads?: () => void;
}

const ACCENT = "#00c2ff";   // the software library's palette (cyan/blue)

// api.getAllSoftware() does a NETWORK fetch and this view remounts on every nav
// to "תוכנות", so it showed "טוען…" for seconds each time. Cache the last list
// (localStorage → survives restarts): repeat visits render INSTANTLY from cache
// and only refresh in the background.
const SOFTWARE_CACHE_KEY = "softwareList:v1";
function readSoftwareCache(): Game[] | null {
  try { const s = localStorage.getItem(SOFTWARE_CACHE_KEY); return s ? (JSON.parse(s) as Game[]) : null; }
  catch { return null; }
}
function writeSoftwareCache(g: Game[]) {
  try { localStorage.setItem(SOFTWARE_CACHE_KEY, JSON.stringify(g)); } catch { /* ignore */ }
}

export default function AppsView({ software, reportStatus, refreshNonce = 0, onOpenSoftware }: Props) {
  // Paint IMMEDIATELY: prefer App's boot-fetched list, else the localStorage
  // cache. "טוען…" now only ever shows on a truly cold first run.
  const [items, setItems] = useState<Game[] | null>(
    () => (software && software.length ? software : readSoftwareCache()),
  );
  const [scanning, setScanning] = useState(false);
  // Persisted so the choice survives leaving + returning to the view.
  const [viewMode, setViewMode] = usePersisted<ViewMode>("appsViewMode", "grid");
  const [sortMode, setSortMode] = usePersisted<SortMode>("appsSortMode", "state");
  const [cardSize, setCardSize] = usePersisted<CardSize>("appsCardSize", "md");
  const [listCols, setListCols] = usePersisted<ListCols>("appsListCols", "1");

  // Adopt App's list whenever it lands/updates (boot fetch + live SWR pushes).
  useEffect(() => {
    if (software && software.length) {
      setItems(software);
      writeSoftwareCache(software);
    }
  }, [software]);

  // Fetch ourselves ONLY as a fallback (App has nothing yet - e.g. its boot
  // fetch failed). Never blanks an existing list.
  useEffect(() => {
    if (software && software.length) return;
    let alive = true;
    (async () => {
      try {
        const data = await api.getAllSoftware();
        if (alive) {
          const arr = Array.isArray(data) ? data : [];
          setItems(arr);
          writeSoftwareCache(arr);
        }
      } catch {
        if (alive) setItems((prev) => prev ?? []);
      }
    })();
    return () => { alive = false; };
  }, [refreshNonce, software]);

  const runScan = async () => {
    if (scanning) return;
    setScanning(true);
    reportStatus?.("סורק תוכנות מותקנות…");
    try {
      const r = await api.scanSoftware();
      const list = Array.isArray(r.software) ? r.software : [];
      setItems(list);
      const found = list.filter((x) => x.is_installed).length;
      reportStatus?.(`הסריקה הושלמה - ${found} מתוך ${list.length} מותקנות`);
    } catch (e) {
      reportStatus?.(String(e), true);
    } finally {
      setScanning(false);
    }
  };

  const list = items ?? [];

  // Same four buckets the games library uses.
  const sections = useMemo(() => {
    const withMod   = list.filter((g) => g.is_installed && g.mod_state === "ACTIVE");
    const withModD  = list.filter((g) => g.is_installed && g.mod_state === "DISABLED");
    const installed = list.filter((g) =>
      g.is_installed && g.mod_state !== "ACTIVE" && g.mod_state !== "DISABLED");
    const missing   = list.filter((g) => !g.is_installed);
    return [
      { key: "mod",       title: "מותקנות - תרגום פעיל",  items: withMod,   accent: "#22c55e" },
      { key: "moddis",    title: "מותקנות - תרגום מושבת", items: withModD,  accent: "#f59e0b" },
      { key: "installed", title: "מותקנות ללא תרגום",     items: installed, accent: "#a0a7b3" },
      { key: "missing",   title: "לא נמצאו במחשב",        items: missing,   accent: "#5a627a" },
    ].filter((s) => s.items.length > 0);
  }, [list]);

  // "לפי זמינות" - grouped by mod/availability status (distinct from "התקנה" above).
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
    for (const g of list) {
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
  }, [list]);

  const flat = useMemo(() => {
    const arr = [...list];
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
  }, [list, sortMode]);

  const open = (g: Game) => onOpenSoftware?.(g);

  // FLIP layout animation - cards deal into place + the category separators slide
  // when sort / view / size / category changes (like the website). `flip()` runs
  // right before each such state change.
  const bodyRef = useRef<HTMLDivElement>(null);
  // Card-DEAL FLIP on sort / view / size / category changes (see LibraryView).
  const flip = useFlipGrid(bodyRef, [sortMode, viewMode, cardSize, listCols]);

  const renderItems = (arr: Game[]) =>
    viewMode === "grid" ? (
      // Same fluid grid as the games library - card size picks the min tile
      // width, the window width decides the column count.
      <div className="grid gap-3 justify-evenly" style={{ gridTemplateColumns: gridCols(cardSize) }}>
        {arr.map((g) => (
          <div key={g.id} data-flip-id={`card-${g.id}`} className="min-w-0">
            <GameCard game={g} onClick={open} size="fluid" />
          </div>
        ))}
      </div>
    ) : (
      <div className={listGridCls(listCols)}>
        {arr.map((g) => (
          <div key={g.id} data-flip-id={`card-${g.id}`} className="min-w-0">
            <SoftwareRow game={g} onClick={open} />
          </div>
        ))}
      </div>
    );

  return (
    <div className="h-full overflow-y-auto px-8 py-6 animate-fade-in">
      {/* Header - identical geometry to the games library; cyan palette. */}
      <div className="flex items-center justify-between mb-7 animate-rise">
        <div className="text-right">
          <h1 className="text-3xl font-extrabold inline-flex items-center gap-1.5">
            <IconOptHdrSoftwareLibrary width={22} className="shrink-0 opacity-90" style={{ color: "#00c2ff" }} />
            <span
              style={{
                background: `linear-gradient(90deg, #ffffff 0%, ${ACCENT} 100%)`,
                WebkitBackgroundClip: "text",
                backgroundClip: "text",
                color: "transparent",
              }}
            >
              ספריית התוכנות
            </span>
          </h1>
          <p className="text-slate-400 text-xs mt-1">
            {items === null ? "טוען…" : `${list.length} תוכנות בקטלוג`}
          </p>
        </div>
        <button
          type="button"
          disabled={scanning}
          onClick={runScan}
          className="group relative overflow-hidden px-5 py-2.5 rounded-xl hover:brightness-110
                     text-brand-ink text-sm font-bold disabled:opacity-50 transition
                     flex items-center gap-2"
          style={{ background: ACCENT, boxShadow: `0 8px 20px -8px ${ACCENT}99` }}
        >
          <span className="sheen-layer" aria-hidden />
          {scanning ? (
            <>
              <span className="w-4 h-4 border-2 border-brand-ink border-t-transparent
                               rounded-full animate-spin" />
              סורק תוכנות…
            </>
          ) : (
            <><IconOptBtnScanSoftware width={18} className="shrink-0 opacity-90" />סריקת תוכנות מלאה</>
          )}
        </button>
      </div>

      {/* Toolbar - sort + view toggle (identical to the games library) */}
      {sections.length > 0 && (
        <div className="flex items-center justify-start gap-3 mb-6 -mt-2">
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <span>מיון</span>
            <SegmentedControl<SortMode>
              ariaLabel="מיון"
              value={sortMode}
              onChange={(v) => { flip(); setSortMode(v); }}
              size="sm"
              accent={ACCENT}
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
            accent={ACCENT}
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

          {/* Density picker (3 choices) - on the LEFT: card size in grid, rows-per-line in list. */}
          {viewMode === "grid"
            ? <CardSizePicker value={cardSize} onChange={(v) => { flip(); setCardSize(v); }} accent={ACCENT} />
            : <ListLayoutPicker value={listCols} onChange={(v) => { flip(); setListCols(v); }} accent={ACCENT} />}
        </div>
      )}

      {items === null && (
        <div className="grid gap-3 justify-start" style={{ gridTemplateColumns: gridCols(cardSize) }}>
          {[0, 1, 2].map((i) => (
            <div key={i} className="skeleton rounded-2xl aspect-[2/3] w-full" />
          ))}
        </div>
      )}

      {items !== null && sections.length === 0 && (
        <EmptyState
          title="לא נמצאו תוכנות"
          hint="עדיין לא זוהו תוכנות נתמכות במחשב. הרץ סריקת תוכנות כדי לאתר התקנות."
          accent={ACCENT}
          action={{ label: "סריקת תוכנות מלאה", onClick: runScan }}
          icon={
            <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
              <circle cx="11" cy="11" r="7" /><path d="m21 21-4.3-4.3" />
            </svg>
          }
        />
      )}

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

/* ── Compact list row - mirrors LibraryView's GameRow ──────────────── */
function SoftwareRow({ game, onClick }: { game: Game; onClick: (g: Game) => void }) {
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
      style={{ direction: "rtl", ["--tw-ring-color" as string]: `${ACCENT}55` }}
    >
      {/* Same as the games list: the SLOT is tinted, so it is never an empty
          hole - while loading (the skeleton inherits --skeleton-* from here)
          and after a cover that never arrives. */}
      <div className="relative w-12 h-16 rounded-lg overflow-hidden shrink-0 ring-1 ring-white/10"
           style={{
             background: `linear-gradient(160deg, ${ACCENT}22, ${ACCENT}08)`,
             ["--skeleton-tint" as string]: `${ACCENT}1a`,
             ["--skeleton-sheen" as string]: `${ACCENT}30`,
           }}>
        <SmartImage src={cover} alt={game.titleEn} draggable={false}
             className="absolute inset-0 w-full h-full object-cover"
             onError={(e) => { (e.currentTarget as HTMLImageElement).style.visibility = "hidden"; }} />
        {active && <span className="absolute top-1 left-1 w-2 h-2 rounded-full" style={{ background: "#22c55e", boxShadow: "0 0 8px #22c55e" }} />}
      </div>
      <div className="flex-1 min-w-0">
        <div className="font-bold truncate" style={{ color: ACCENT }}>
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
