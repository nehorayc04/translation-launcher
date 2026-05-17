// Landing screen — hero pitch + featured games row + quick stats.
import type { Game } from "../lib/types";
import GameCard from "../components/GameCard";
import NewsSection from "../components/NewsSection";
import ProgressDashboard from "../components/ProgressDashboard";
import { useSiteConfig } from "../lib/useSiteConfig";

interface Props {
  games: Game[];
  onOpenGame:  (g: Game) => void;
  onOpenLibrary: () => void;
  /** Bumped by App's refresh button — forwarded to NewsSection so it
   *  re-pulls without waiting for an unmount/remount cycle. */
  refreshNonce?: number;
}

export default function HomeView({ games, onOpenGame, onOpenLibrary, refreshNonce }: Props) {
  const cfg = useSiteConfig();
  const vis = cfg.sections?.visible ?? {};
  // Featured games are curated from /admin → games → "מוצג ב'תרגומים מובילים'".
  // Order by the catalog-level sortOrder (lower = earlier) so the admin can
  // rearrange the row without touching code. If nothing is flagged yet
  // (e.g. before the DB migration ran), fall back to a sensible default
  // so the home page never looks empty.
  const FALLBACK_IDS = ["cyberpunk", "gowragnarok", "tsushima", "rdr1", "rdr2", "gtav", "hogwarts"];
  const flagged = games.filter((g) => g.featured);
  const featured = (flagged.length > 0
    ? [...flagged].sort((a, b) => (a.sortOrder ?? 1000) - (b.sortOrder ?? 1000))
    : FALLBACK_IDS
        .map((id) => games.find((g) => g.id === id))
        .filter((g): g is Game => Boolean(g))
  );

  const installed = games.filter((g) => g.is_installed).length;
  const withMods  = games.filter((g) => g.mod_state === "ACTIVE").length;
  const inProg    = games.filter((g) => g.availability === "in-progress").length;
  // Live progress card mounts only when there's a game in production —
  // hides itself completely otherwise.
  const inProgGame = games.find((g) => g.availability === "in-progress");

  return (
    <div className="h-full overflow-y-auto px-8 py-6 animate-fade-in">
      {/* HERO */}
      <section className="glass rounded-3xl px-10 py-12 relative overflow-hidden">
        <div className="absolute -top-20 -left-20 w-96 h-96 rounded-full
                        bg-brand-yellow/10 blur-3xl pointer-events-none" />
        <div className="absolute -bottom-20 -right-20 w-96 h-96 rounded-full
                        bg-brand-cyan/10 blur-3xl pointer-events-none" />

        <div className="relative">
          <div className="font-display text-[11px] tracking-[0.3em] text-brand-yellow mb-3">
            P R O J E C T &nbsp; T R A N S L A T I O N
          </div>
          <h1 className="text-5xl font-extrabold leading-tight text-white mb-3">
            מנהל התרגומים הרשמי
          </h1>
          <p className="text-slate-300 text-lg max-w-2xl leading-relaxed mb-6">
            הדור הבא של הגיימינג בעברית. המרכז החכם שלך לניהול והתקנת תרגומים —
            מאובטח, מהיר, ומעוצב בסטנדרט הגבוה ביותר.
          </p>
          <div className="flex gap-3 justify-end">
            <button
              onClick={onOpenLibrary}
              className="bg-brand-yellow hover:bg-yellow-300 text-brand-ink font-bold
                         px-6 py-2.5 rounded-xl transition-all
                         shadow-[0_8px_20px_-8px_rgba(255,247,0,0.5)]
                         hover:shadow-[0_10px_25px_-5px_rgba(255,247,0,0.6)]"
            >
              עיין בספרייה
            </button>
            <a
              href="https://hebrew-translation-hub.vercel.app/"
              target="_blank"
              rel="noopener noreferrer"
              className="border border-white/15 hover:border-brand-cyan/50
                         hover:bg-brand-cyan/5 text-slate-100 font-semibold
                         px-6 py-2.5 rounded-xl transition-all"
            >
              ביקור באתר הרשמי
            </a>
          </div>
        </div>
      </section>

      {/* STATS */}
      <section className="grid grid-cols-3 gap-4 mt-6">
        <Stat label="משחקים בקטלוג" value={games.length} accent="#fff700" />
        <Stat label="מותקנים במחשב"    value={installed}   accent="#22c55e" />
        <Stat label="בעבודה"            value={inProg}      accent="#00ffe0" />
      </section>

      {/* LIVE PROGRESS — only renders when there's an in-progress game */}
      {(vis['dashboard'] ?? true) && inProgGame && (
        <ProgressDashboard game={inProgGame} refreshNonce={refreshNonce} />
      )}

      {/* FEATURED ROW */}
      {(vis['grid'] ?? true) && (
        <section className="mt-8">
          <div className="flex items-baseline justify-between mb-4">
            <button
              onClick={onOpenLibrary}
              className="text-brand-cyan hover:text-brand-yellow text-sm transition-colors"
            >
              לכל הספרייה ←
            </button>
            <h2 className="text-2xl font-bold text-white">תרגומים מובילים</h2>
          </div>
          <div className="flex gap-5 overflow-x-auto pb-3 -mx-2 px-2">
            {featured.map((g) => (
              <GameCard
                key={g.id}
                game={g}
                onClick={onOpenGame}
                size="lg"
              />
            ))}
          </div>
          <div className="text-xs text-slate-500 mt-2 text-right">
            {withMods === 1 && "מוד אחד פעיל כרגע"}
            {withMods  >  1 && `${withMods} מודים פעילים כרגע`}
          </div>
        </section>
      )}

      {/* NEWS — dynamic, fetched from backend (remote → local fallback) */}
      {(vis['news'] ?? true) && (
        <NewsSection games={games} onOpenGame={onOpenGame} refreshNonce={refreshNonce} />
      )}
    </div>
  );
}

function Stat({ label, value, accent }: { label: string; value: number; accent: string }) {
  return (
    <div className="glass-soft rounded-2xl p-5 text-right">
      <div className="text-[11px] text-slate-400 mb-1">{label}</div>
      <div
        className="font-display text-4xl font-extrabold"
        style={{ color: accent, textShadow: `0 0 30px ${accent}40` }}
      >
        {value}
      </div>
    </div>
  );
}
