// Tile shown in the library grid. 2:3 cover image, status chips overlaid,
// title gradient at bottom, hover = scale-up + glow.
import type { Game } from "../lib/types";
import { availabilityLabel, accentFor, gradientFor, modStateLabel } from "../lib/theme";
import { resolveCoverUrl } from "../lib/coverUrl";
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
  // Normalise the catalog's `cover` field (which may be a full URL,
  // a root-relative path, or just a bare filename like "cyberpunk.jpg")
  // to a usable <img src>. See lib/coverUrl.ts for the resolution rules.
  const coverSrc = resolveCoverUrl(game.cover, game.id);
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


      </div>

      {/* Caption — tagline below cover */}
      <div className="px-1 pt-2 text-[11px] text-slate-300 line-clamp-2 leading-snug">
        {game.tagline}
      </div>
    </button>
  );
}
