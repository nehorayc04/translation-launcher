// Dynamic news list shown on the Home screen.
// Backed by Python's SWR cache: the first read returns the last-known-good
// list instantly (from ~/.translation_manager/cache.json), and any live
// update from the server is pushed to us via `cache_refreshed("news", …)`.
import { useEffect } from "react";
import { api, type NewsItem } from "../lib/eel";
import { useSWRSource } from "../lib/useSWRSource";
import type { Game } from "../lib/types";
import { IconOptHdrNews } from "./UiIcons";

interface Props {
  /** Clicking a news item with `link: <game_id>` opens that game's detail panel. */
  onOpenGame: (g: Game) => void;
  /** Resolve a game-id to a full Game for the click handler. */
  games: Game[];
  /** Bumped by App's sidebar refresh - forces a fresh fetch even if the
   *  SWR layer thinks the cache is hot. */
  refreshNonce?: number;
}

export default function NewsSection({ onOpenGame, games, refreshNonce = 0 }: Props) {
  const { data, loading, refetch } = useSWRSource<NewsItem[]>("news", api.getNews);
  // Show only the latest 10 on the home screen (the feed can grow large).
  const items = (data ?? []).slice(0, 10);

  // Manual refresh button → invalidate and re-pull immediately.
  useEffect(() => {
    if (refreshNonce > 0) refetch();
  }, [refreshNonce, refetch]);

  const handleClick = (n: NewsItem) => {
    if (!n.link) return;
    const g = games.find((x) => x.id === n.link);
    if (g) onOpenGame(g);
  };

  return (
    <section className="mt-8">
      <div className="flex items-baseline justify-between mb-4">
        <h2 className="flex items-center gap-3 text-2xl font-bold text-white">
          <span className="h-6 w-1.5 rounded-full bg-brand-yellow shadow-[0_0_12px_rgba(255,247,0,0.6)]" />
          <IconOptHdrNews width={20} className="shrink-0 opacity-90" />חדשות ועדכונים
        </h2>
        <span className="text-xs text-slate-500">
          {loading
            ? "טוען..."
            : items.length === 1
              ? "עדכון אחרון"
              : `${items.length} עדכונים אחרונים`}
        </span>
      </div>

      {loading ? (
        <div className="glass-soft rounded-2xl p-6 grid place-items-center">
          <div className="w-6 h-6 border-2 border-brand-yellow border-t-transparent
                          rounded-full animate-spin" />
        </div>
      ) : items.length === 0 ? (
        <div className="glass-soft rounded-2xl p-6 text-center text-slate-400 text-sm">
          אין עדכונים זמינים כרגע.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {items.map((n) => (
            <NewsCard key={n.id} item={n} onClick={handleClick} />
          ))}
        </div>
      )}
    </section>
  );
}

function NewsCard({ item, onClick }: { item: NewsItem; onClick: (n: NewsItem) => void }) {
  const isClickable = !!item.link;
  const kindAccent  = item.kind === "mod" ? "#d4af37" : "#00ffe0";
  const kindLabel   = item.kind === "mod" ? "מוד"     : "מערכת";

  return (
    <button
      onClick={() => onClick(item)}
      disabled={!isClickable}
      className={[
        "glass rounded-2xl p-4 text-right transition-all duration-200",
        "border border-white/5 hover:border-white/15",
        isClickable ? "cursor-pointer hover:-translate-y-0.5" : "cursor-default",
      ].join(" ")}
    >
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex flex-wrap items-center gap-1.5">
          {item.badge && (
            <span className="text-[10px] font-bold px-2 py-0.5 rounded-md
                             bg-emerald-400/20 text-emerald-200 ring-1 ring-emerald-400/30">
              {item.badge}
            </span>
          )}
          <span
            className="text-[10px] font-display tracking-wider px-2 py-0.5 rounded-md
                       bg-black/40 ring-1"
            style={{ color: kindAccent, borderColor: `${kindAccent}40` }}
          >
            {kindLabel}
          </span>
        </div>
        <h3 className="text-white font-bold text-[15px] leading-tight flex-1">
          {item.title}
        </h3>
      </div>

      <p className="text-slate-300 text-[13px] leading-relaxed mb-2">
        {item.detail}
      </p>

      <div className="flex items-center justify-between">
        {isClickable && (
          <span className="text-brand-cyan text-[11px] hover:text-brand-yellow transition">
            פתח משחק ←
          </span>
        )}
        <span dir="ltr" className="text-slate-500 text-[10px] ml-auto">
          {item.date}
        </span>
      </div>
    </button>
  );
}
