// Landing screen — clean premium brand hero (no spotlight game) + quick stats
// + featured games row + live progress + news. Styled to a WeMod/Steam grade.
import { isInFlight, type Game } from "../lib/types";
import GameCard from "../components/GameCard";
import NewsSection from "../components/NewsSection";
import ProgressDashboard from "../components/ProgressDashboard";
import { useSiteConfig } from "../lib/useSiteConfig";
import { accentFor } from "../lib/theme";
import { resolveCoverUrl } from "../lib/coverUrl";
import { useEffect, useState, type ComponentType, type SVGProps } from "react";

interface Props {
  games: Game[];
  onOpenGame:  (g: Game) => void;
  onOpenLibrary: () => void;
  onBigPicture?: () => void;
  /** Bumped by App's refresh button — forwarded to NewsSection so it
   *  re-pulls without waiting for an unmount/remount cycle. */
  refreshNonce?: number;
}

export default function HomeView({ games, onOpenGame, onOpenLibrary, onBigPicture, refreshNonce }: Props) {
  const cfg = useSiteConfig();
  const vis = cfg.sections?.visible ?? {};
  // Featured games are curated from /admin → games → "מוצג ב'תרגומים מובילים'".
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
  const inProg    = games.filter((g) => isInFlight(g.availability)).length;
  // Live progress card mounts only when there's a game in production.
  const inProgGame = games.find((g) => isInFlight(g.availability));

  return (
    <div className="h-full overflow-y-auto px-8 py-6 animate-fade-in">
      {/* ── BRAND HERO (no featured game) ──────────────────────────── */}
      <section className="glass rounded-3xl relative overflow-hidden animate-rise">
        <div className="aurora" aria-hidden />
        <div className="absolute inset-0 grid-texture pointer-events-none" aria-hidden />
        {/* Ambient glow — a STATIC radial gradient (no filter:blur / no animation).
            The old blur-3xl + animate-glow-pulse blobs were a continuous CPU-blur
            under --disable-gpu-compositing → the main FPS killer. A gradient looks
            the same for free. */}
        <div className="absolute inset-0 pointer-events-none" aria-hidden style={{
          background:
            "radial-gradient(46% 70% at 50% -10%, rgba(255,247,0,0.12), transparent 70%)," +
            "radial-gradient(40% 60% at 92% 115%, rgba(0,255,224,0.10), transparent 70%)," +
            "radial-gradient(36% 55% at 8% 115%, rgba(255,247,0,0.06), transparent 70%)",
        }} />

        <div className="relative px-10 py-14 flex flex-col items-center text-center">
          <div className="font-display text-[11px] tracking-[0.32em] text-brand-yellow mb-4">
            P R O J E C T &nbsp; T R A N S L A T I O N
          </div>
          <h1 className="text-[3rem] leading-[1.05] font-extrabold mb-4">
            <span className="text-gradient">מנהל התרגומים הרשמי</span>
          </h1>
          <p className="text-slate-300/90 text-[1.05rem] max-w-2xl leading-relaxed mb-8">
            הדור הבא של הגיימינג בעברית. המרכז החכם שלך לניהול והתקנת תרגומים —
            מאובטח, מהיר, ומעוצב בסטנדרט הגבוה ביותר.
          </p>
          <div className="flex gap-3 justify-center flex-wrap">
            <button
              onClick={onOpenLibrary}
              className="group relative overflow-hidden bg-brand-yellow hover:brightness-110
                         text-brand-ink font-extrabold px-8 py-3 rounded-xl transition-all
                         shadow-[0_12px_30px_-10px_rgba(255,247,0,0.6)]"
            >
              <span className="sheen-layer" aria-hidden />
              ▸ עיין בספרייה
            </button>
            {onBigPicture && (
              <button
                type="button"
                onClick={onBigPicture}
                className="border border-brand-cyan/40 hover:border-brand-cyan/70
                           hover:bg-brand-cyan/10 text-brand-cyan font-semibold
                           px-6 py-3 rounded-xl transition-all"
                title="מצב מסך-מלא לניווט בשלט/מקלדת מהספה"
              >
                🖥 מצב מסך-מלא
              </button>
            )}
            <a
              href="https://hebrew-translation-hub.com/"
              target="_blank"
              rel="noopener noreferrer"
              className="border border-white/15 hover:border-brand-cyan/50
                         hover:bg-brand-cyan/5 text-slate-100 font-semibold
                         px-6 py-3 rounded-xl transition-all"
            >
              האתר הרשמי ↗
            </a>
          </div>
        </div>
      </section>

      {/* ── RECOMMENDED SPOTLIGHT (rotating carousel) ──────────────── */}
      {(vis['grid'] ?? true) && featured.length > 0 && (
        <FeaturedCarousel games={featured.slice(0, 6)} onOpenGame={onOpenGame} />
      )}

      {/* ── STATS ──────────────────────────────────────────────────── */}
      <section className="grid grid-cols-3 gap-4 mt-6 stagger">
        <Stat label="משחקים בקטלוג" value={games.length} accent="#fff700" Icon={IconCatalog} />
        <Stat label="מותקנים במחשב"  value={installed}     accent="#22c55e" Icon={IconInstalled} />
        <Stat label="בעבודה"          value={inProg}        accent="#00ffe0" Icon={IconProgress} />
      </section>

      {/* LIVE PROGRESS — only renders when there's an in-progress game */}
      {(vis['dashboard'] ?? true) && inProgGame && (
        <ProgressDashboard game={inProgGame} refreshNonce={refreshNonce} />
      )}

      {/* ── FEATURED ROW ───────────────────────────────────────────── */}
      {(vis['grid'] ?? true) && (
        <section className="mt-8">
          <div className="flex items-center justify-between mb-4">
            <button
              onClick={onOpenLibrary}
              className="text-brand-cyan hover:text-brand-yellow text-sm font-semibold transition-colors"
            >
              לכל הספרייה ←
            </button>
            <h2 className="flex items-center gap-3 text-2xl font-bold text-white">
              <span className="h-6 w-1.5 rounded-full bg-brand-yellow shadow-[0_0_12px_rgba(255,247,0,0.6)]" />
              תרגומים מובילים
            </h2>
          </div>
          <div className="flex gap-5 overflow-x-auto scroll-x pb-3 -mx-2 px-2">
            {featured.map((g) => (
              <GameCard key={g.id} game={g} onClick={onOpenGame} size="lg" />
            ))}
          </div>
          {withMods > 0 && (
            <div className="text-xs text-slate-500 mt-2 text-right flex items-center gap-2 justify-end">
              {withMods === 1 ? "מוד אחד פעיל כרגע" : `${withMods} מודים פעילים כרגע`}
              <span className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-400 shadow-[0_0_8px_#22c55e] animate-pulse-dot" />
            </div>
          )}
        </section>
      )}

      {/* NEWS — dynamic, fetched from backend (remote → local fallback) */}
      {(vis['news'] ?? true) && (
        <NewsSection games={games} onOpenGame={onOpenGame} refreshNonce={refreshNonce} />
      )}
    </div>
  );
}

/* ── Rotating recommended spotlight ──────────────────────────────────
   A contained, well-masked spotlight card (NOT a full-bleed backdrop, so
   nothing looks "cut off"): the game's cover fills the LEFT (LTR side),
   fading into the glass on the text side; title + tagline + open button on
   the RIGHT (RTL). Auto-advances; dots + arrows to navigate. */
function FeaturedCarousel({
  games, onOpenGame,
}: {
  games: Game[];
  onOpenGame: (g: Game) => void;
}) {
  const [idx, setIdx] = useState(0);
  const [paused, setPaused] = useState(false);
  const n = games.length;

  // Clamp if the featured list shrinks.
  useEffect(() => { if (idx >= n) setIdx(0); }, [n, idx]);

  // Auto-advance every 6s unless hovered.
  useEffect(() => {
    if (paused || n <= 1) return;
    const t = setInterval(() => setIdx((i) => (i + 1) % n), 6000);
    return () => clearInterval(t);
  }, [paused, n]);

  if (n === 0) return null;

  return (
    <section
      className="mt-6 animate-rise"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
    >
      <div className="relative h-[230px] rounded-3xl overflow-hidden glass">
        {games.map((g, i) => {
          const accent = accentFor(g.theme_key);
          const cover = resolveCoverUrl(g.cover, g.id);
          const on = i === idx;
          return (
            <button
              key={g.id}
              type="button"
              onClick={() => onOpenGame(g)}
              tabIndex={on ? 0 : -1}
              className="absolute inset-0 text-right transition-opacity duration-700 ease-out"
              style={{ opacity: on ? 1 : 0, pointerEvents: on ? "auto" : "none" }}
            >
              {/* Wide per-game BANNER fills the whole card (it's a wide image, so
                  it never looks cropped like a vertical cover did). Falls back to a
                  masked cover only when a game has no banner yet. */}
              {g.bannerUrl ? (
                <img
                  src={g.bannerUrl}
                  alt={g.titleEn}
                  draggable={false}
                  className="absolute inset-0 w-full h-full object-cover"
                  onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = "none"; }}
                />
              ) : (
                /* No banner → a blurred, zoomed cover backdrop — identical to the
                   game-menu top banner ("if there's no image, a blurred background"). */
                <img
                  src={cover}
                  alt={g.titleEn}
                  draggable={false}
                  className="absolute inset-0 w-full h-full object-cover scale-110 blur-2xl"
                  onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = "none"; }}
                />
              )}
              {/* Readability scrim — darkens the text (right/RTL) side. */}
              <div className="absolute inset-0" style={{
                background: `linear-gradient(to left, rgba(7,7,18,0.92) 24%, rgba(7,7,18,0.5) 54%, rgba(7,7,18,0.12)), radial-gradient(60% 100% at 100% 50%, ${accent}1f, transparent 70%)`,
              }} aria-hidden />
              {/* Text block (RTL right). Uses the transparent LOGO when present. */}
              <div className="relative h-full flex flex-col justify-center items-end gap-3 pr-9 pl-[42%]">
                <div className="font-display text-[10px] tracking-[0.3em]" style={{ color: accent }}>
                  ★ &nbsp; M U M L A T Z
                </div>
                {g.logoUrl ? (
                  <img
                    src={g.logoUrl}
                    alt={g.titleEn}
                    draggable={false}
                    className="max-h-16 max-w-[70%] object-contain drop-shadow-[0_3px_14px_rgba(0,0,0,0.9)]"
                    onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = "none"; }}
                  />
                ) : (
                  <h3 className="text-3xl font-extrabold text-white leading-tight drop-shadow-[0_2px_10px_rgba(0,0,0,0.8)]">
                    {g.titleHe || g.titleEn}
                  </h3>
                )}
                {g.tagline && (
                  <p className="text-slate-300 text-sm max-w-md leading-relaxed line-clamp-2">
                    {g.tagline}
                  </p>
                )}
                <span
                  className="mt-1 inline-flex items-center gap-2 px-6 py-2.5 rounded-xl font-extrabold text-brand-ink
                             shadow-[0_10px_26px_-8px_rgba(0,0,0,0.7)]"
                  style={{ background: accent }}
                >
                  ▸ פתח
                </span>
              </div>
            </button>
          );
        })}

        {/* Prev / next arrows (LTR positions; subtle). */}
        {n > 1 && (
          <>
            <button
              type="button"
              aria-label="הקודם"
              onClick={() => setIdx((i) => (i - 1 + n) % n)}
              className="absolute left-3 top-1/2 -translate-y-1/2 z-10 w-9 h-9 rounded-full grid place-items-center
                         bg-black/70 hover:bg-black/85 text-white border border-white/10 transition"
            >
              {/* outward = points LEFT (toward the left edge) */}
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.4} strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M15 18l-6-6 6-6" /></svg>
            </button>
            <button
              type="button"
              aria-label="הבא"
              onClick={() => setIdx((i) => (i + 1) % n)}
              className="absolute right-3 top-1/2 -translate-y-1/2 z-10 w-9 h-9 rounded-full grid place-items-center
                         bg-black/70 hover:bg-black/85 text-white border border-white/10 transition"
            >
              {/* outward = points RIGHT (toward the right edge) */}
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.4} strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M9 18l6-6-6-6" /></svg>
            </button>
          </>
        )}

        {/* Dots */}
        {n > 1 && (
          <div className="absolute bottom-3 left-1/2 -translate-x-1/2 z-10 flex gap-2">
            {games.map((g, i) => (
              <button
                key={g.id}
                type="button"
                aria-label={`עבור לכרטיס ${i + 1}`}
                onClick={() => setIdx(i)}
                className="h-1.5 rounded-full transition-all duration-300"
                style={{
                  width: i === idx ? 22 : 7,
                  background: i === idx ? "#fff" : "rgba(255,255,255,0.4)",
                }}
              />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

function Stat({
  label, value, accent, Icon,
}: {
  label: string;
  value: number;
  accent: string;
  Icon: ComponentType<SVGProps<SVGSVGElement>>;
}) {
  return (
    <div
      className="group glass-soft lift rounded-2xl p-5 relative overflow-hidden border border-white/5
                 hover:border-white/10"
      style={{ direction: "rtl" }}
    >
      {/* accent corner glow — static radial gradient (no filter:blur → cheap to paint) */}
      <div className="absolute -top-10 -left-10 w-32 h-32 rounded-full opacity-40
                      group-hover:opacity-70 transition-opacity pointer-events-none"
           style={{ background: `radial-gradient(circle, ${accent}55, transparent 70%)` }} aria-hidden />
      <div className="relative flex items-center justify-between">
        <div
          className="w-11 h-11 rounded-xl grid place-items-center shrink-0 ring-1"
          style={{ background: `${accent}1f`, color: accent, ["--tw-ring-color" as string]: `${accent}55` }}
        >
          <Icon width={22} height={22} />
        </div>
        <div className="text-right">
          <div className="text-[11px] text-slate-400 mb-0.5">{label}</div>
          <div className="font-display text-4xl font-extrabold leading-none tabular-nums"
               style={{ color: accent, textShadow: `0 0 30px ${accent}40` }}>
            {value}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── inline stat icons (stroke = currentColor) ──────────────────── */
function IconCatalog(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}
         strokeLinecap="round" strokeLinejoin="round" {...props}>
      <rect x="3" y="3" width="7" height="7" rx="1.5" />
      <rect x="14" y="3" width="7" height="7" rx="1.5" />
      <rect x="3" y="14" width="7" height="7" rx="1.5" />
      <rect x="14" y="14" width="7" height="7" rx="1.5" />
    </svg>
  );
}
function IconInstalled(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}
         strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-7" />
      <path d="M12 3v12" />
      <path d="m8 11 4 4 4-4" />
    </svg>
  );
}
function IconProgress(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}
         strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M12 3a9 9 0 1 0 9 9" />
      <path d="M12 7v5l3 2" />
    </svg>
  );
}
