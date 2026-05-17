// Tile shown in the library grid. 2:3 cover image, status chips overlaid,
// title gradient at bottom, hover = scale-up + glow.
import type { Game } from "../lib/types";
import { availabilityLabel, accentFor, gradientFor, modStateLabel } from "../lib/theme";
import { useState } from "react";
import { useLiveGameProgress } from "../lib/useLiveGameProgress";

interface Props {
  game: Game;
  onClick: (g: Game) => void;
  size?: "lg" | "md";    // lg = featured (home), md = library tile
  /** Bumped by App's sidebar refresh button — re-pulls the live bar
   *  on in-progress tiles without remounting the card. */
  refreshNonce?: number;
}

export default function GameCard({ game, onClick, size = "md", refreshNonce = 0 }: Props) {
  // Pull live progress only for in-progress titles.
  //   loaded=false  → render the bar at 0% so the OLD static value never
  //                   briefly flashes before the live one arrives.
  //   loaded=true + snap=null → server has no row; fall back to static.
  //   loaded=true + snap      → use processed/total from /api/progress.
  const { snap: live, loaded } = useLiveGameProgress(game.id, {
    enabled:      game.availability === "in-progress",
    refreshNonce,
  });
  const usingLive = live !== null && live.total > 0;
  const livePct = !loaded
    ? 0
    : usingLive
      ? (live!.processed / live!.total) * 100
      : (game.progress ?? 0);
  const [g1, g2] = gradientFor(game.theme_key);
  const accent   = accentFor(game.theme_key);
  const avail    = availabilityLabel(game.availability);
  const modBadge = game.has_mod_support ? modStateLabel(game.mod_state) : null;
  const coverSrc = `/covers/${game.id}.jpg`;
  const [imgError, setImgError] = useState(false);

  const widthClass = size === "lg" ? "w-[230px]" : "w-[180px]";

  return (
    <button
      onClick={() => onClick(game)}
      className={`group ${widthClass} flex-shrink-0 text-right
                  transition-all duration-300 hover:-translate-y-1
                  focus:outline-none focus:ring-2 focus:ring-brand-yellow/40
                  rounded-2xl`}
      style={{ direction: "rtl" }}
    >
      {/* Cover — strict 2:3 aspect.
          `transform-gpu` + `isolation:isolate` + `translateZ(0)` give the
          card its own compositing layer up-front, so the rounded clip stays
          consistent when the inner <img> scales on hover (Chromium otherwise
          briefly drops the clip while building a new layer = "sharp corners
          for a frame"). We also keep the ring width constant — only the
          color/opacity animates — to avoid a 1px layout snap. */}
      <div
        className="relative aspect-[2/3] rounded-2xl overflow-hidden
                   transform-gpu will-change-transform
                   ring-1 ring-white/10
                   shadow-[0_20px_40px_-20px_rgba(0,0,0,0.8)]
                   group-hover:ring-white/30
                   group-hover:shadow-[0_25px_50px_-15px_rgba(0,0,0,0.9)]
                   transition-[box-shadow,--tw-ring-color] duration-300"
        style={{
          isolation: "isolate",
          transform: "translateZ(0)",
          background: imgError
            ? `linear-gradient(160deg, ${g1}, ${g2})`
            : undefined,
        }}
      >
        {!imgError && (
          <img
            src={coverSrc}
            alt={game.titleEn}
            onError={() => setImgError(true)}
            className="absolute inset-0 w-full h-full object-cover
                       group-hover:scale-[1.04] transition-transform duration-500"
            style={{ transform: "translateZ(0)", willChange: "transform" }}
            loading="lazy"
            draggable={false}
          />
        )}

        {/* Bottom gradient for legibility */}
        <div className="absolute inset-x-0 bottom-0 h-32
                        bg-gradient-to-t from-black/95 via-black/60 to-transparent" />

        {/* Top-right availability chip */}
        <div className={`absolute top-2 right-2 px-2 py-0.5 rounded-full text-[10px]
                        font-semibold ${avail.tone}`}>
          {avail.text}
        </div>

        {/* Top-left version chip */}
        <div className="absolute top-2 left-2 px-2 py-0.5 rounded-full text-[10px]
                        font-medium text-slate-200 bg-black/75 backdrop-blur-md
                        ring-1 ring-white/15">
          {game.version}
        </div>

        {/* Bottom block — mod chip + title stacked in normal flow.
            Previously the chip was absolute at bottom-2/left-2 and the
            title was absolute at bottom-0; with long titles like
            "Marvel's Spider-Man Remastered" the two collided. A flex
            column with a small gap guarantees no overlap. */}
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

        {/* Progress bar overlay (only in-progress) — prefers live data
            from /api/progress, falls back to static `game.progress`. */}
        {game.availability === "in-progress" && (
          <div className="absolute bottom-0 inset-x-0 h-1 bg-black/40">
            <div
              className="h-full transition-[width] duration-700"
              style={{
                width: `${livePct}%`,
                background: accent,
                boxShadow: usingLive ? `0 0 6px ${accent}aa` : undefined,
              }}
              title={usingLive
                ? `${live!.processed.toLocaleString("he-IL")} / ${live!.total.toLocaleString("he-IL")} ${live!.unit}`
                : `${livePct.toFixed(1)}%`}
            />
          </div>
        )}
      </div>

      {/* Caption — tagline below cover */}
      <div className="px-1 pt-2 text-[11px] text-slate-300 line-clamp-2 leading-snug">
        {game.tagline}
      </div>
    </button>
  );
}
