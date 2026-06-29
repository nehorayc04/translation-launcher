// Tile shown in the library grid. 2:3 cover image, status chips overlaid,
// title gradient at bottom, hover = lift + per-game accent glow + cover zoom
// + a "פתח" reveal overlay (WeMod/Steam-grade).
import type { Game } from "../lib/types";
import { availabilityLabel, accentFor, gradientFor, modStateLabel } from "../lib/theme";
import { resolveCoverUrl } from "../lib/coverUrl";
import { formatVersion } from "../lib/formatVersion";
import { StageBadge } from "./StageBadge";
import { useState } from "react";

interface Props {
  game: Game;
  onClick: (g: Game) => void;
  size?: "lg" | "md";    // lg = featured (home), md = library tile
}

export default function GameCard({ game, onClick, size = "md" }: Props) {
  const [g1, g2] = gradientFor(game.theme_key);
  const accent   = accentFor(game.theme_key);
  const avail    = availabilityLabel(game.availability);
  const modBadge = game.has_mod_support ? modStateLabel(game.mod_state) : null;
  const active   = game.mod_state === "ACTIVE";
  // Normalise the catalog's `cover` field (which may be a full URL,
  // a root-relative path, or just a bare filename like "cyberpunk.jpg")
  // to a usable <img src>. See lib/coverUrl.ts for the resolution rules.
  const coverSrc = resolveCoverUrl(game.cover, game.id);
  const [imgError, setImgError] = useState(false);
  const [imgLoaded, setImgLoaded] = useState(false);
  const [hover, setHover]       = useState(false);

  const widthClass = size === "lg" ? "w-[230px]" : "w-[180px]";

  return (
    <button
      onClick={() => onClick(game)}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      className={`group ${widthClass} flex-shrink-0 text-right lift
                  focus:outline-none focus:ring-2 focus:ring-brand-yellow/40
                  rounded-2xl`}
      style={{ direction: "rtl" }}
    >
      {/* Cover — strict 2:3 aspect.
          `transform-gpu` + `isolation:isolate` + `translateZ(0)` give the
          card its own compositing layer up-front, so the rounded clip stays
          consistent when the inner <img> scales on hover. The hover glow is a
          per-game accent-tinted drop shadow (the WeMod look). */}
      <div
        className={`relative aspect-[2/3] rounded-2xl overflow-hidden
                   transition-[box-shadow,--tw-ring-color] duration-300
                   ${active ? "ring-2" : "ring-1"}`}
        style={{
          isolation: "isolate",
          // ring color: hover → accent; active (translation on) → green
          // border always; otherwise subtle white.
          ["--tw-ring-color" as string]: hover
            ? `${accent}aa`
            : active
              ? "rgba(34,197,94,0.85)"
              : "rgba(255,255,255,0.10)",
          boxShadow: hover
            ? `0 24px 55px -18px rgba(0,0,0,0.9), 0 0 32px -6px ${accent}80`
            : active
              ? "0 20px 40px -20px rgba(0,0,0,0.8), 0 0 22px -6px rgba(34,197,94,0.7)"
              : "0 20px 40px -20px rgba(0,0,0,0.8)",
          background: imgError ? `linear-gradient(160deg, ${g1}, ${g2})` : undefined,
        }}
      >
        {/* Skeleton shimmer while the cover loads. */}
        {!imgError && !imgLoaded && (
          <div className="skeleton absolute inset-0" aria-hidden />
        )}
        {!imgError && (
          <img
            src={coverSrc}
            alt={game.titleEn}
            onError={() => setImgError(true)}
            onLoad={() => setImgLoaded(true)}
            className={`absolute inset-0 w-full h-full object-cover
                       group-hover:scale-[1.06] transition-transform duration-[600ms] ease-out
                       ${imgLoaded ? "opacity-100" : "opacity-0"}`}
            loading="lazy"
            draggable={false}
          />
        )}

        {/* Accent wash that fades in on hover — ties the cover to the game color. */}
        <div
          className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none"
          style={{ background: `linear-gradient(to top, ${accent}22, transparent 55%)` }}
        />

        {/* Bottom gradient for legibility */}
        <div className="absolute inset-x-0 bottom-0 h-32
                        bg-gradient-to-t from-black/95 via-black/60 to-transparent" />

        {/* Top-right availability chip */}
        <div className={`absolute top-2 right-2 px-2 py-0.5 rounded-full text-[10px]
                        font-semibold ${avail.tone}`}>
          {avail.text}
        </div>

        {/* Top-left version chip + stage badge (אלפא/בטא/RC; none for stable) */}
        <div className="absolute top-2 left-2 flex items-center gap-1">
          <StageBadge releaseStage={game.releaseStage} version={game.version} />
          <span className="px-2 py-0.5 rounded-full text-[10px] font-medium text-slate-200
                           bg-black/90 ring-1 ring-white/15">
            {formatVersion(game.version)}
          </span>
        </div>

        {/* Active-mod glow dot — a small living indicator that the translation
            is currently applied (mirrors WeMod's "active" pip). */}
        {active && (
          <span
            className="absolute top-2 left-2 -translate-x-[2px] translate-y-7 w-2 h-2 rounded-full animate-pulse-dot"
            style={{ background: "#22c55e", boxShadow: "0 0 10px #22c55e" }}
            aria-hidden
          />
        )}

        {/* Hover reveal — a centered "פתח" pill over a soft veil. */}
        <div className="absolute inset-0 grid place-items-center opacity-0 group-hover:opacity-100
                        transition-opacity duration-300 pointer-events-none">
          <span
            className="px-5 py-2 rounded-full text-[13px] font-extrabold text-brand-ink
                       translate-y-2 group-hover:translate-y-0 transition-transform duration-300
                       shadow-[0_8px_24px_-6px_rgba(0,0,0,0.7)]"
            style={{ background: accent }}
          >
            ▸ פתח
          </span>
        </div>

        {/* Bottom block — mod chip + title stacked in normal flow. */}
        <div className="absolute inset-x-0 bottom-0 p-3 flex flex-col gap-1.5 items-start"
             dir="ltr">
          {modBadge && (
            <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${modBadge.tone}`}>
              {modBadge.text}
            </span>
          )}
          <span
            className="font-display font-extrabold tracking-wide leading-tight
                       drop-shadow-[0_2px_6px_rgba(0,0,0,0.95)] text-left
                       text-[15px] line-clamp-2"
            style={{ color: accent }}
          >
            {game.titleEn}
          </span>
        </div>
      </div>
      {/* No caption below the cover — the tagline lives in the detail panel.
          Dropping it keeps every card the exact same height (fixed width +
          strict 2:3 cover), so the grid is perfectly uniform. */}
    </button>
  );
}
