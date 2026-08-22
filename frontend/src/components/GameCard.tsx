// Tile shown in the library grid. 2:3 cover image, status chips overlaid,
// title gradient at bottom, hover = lift + per-game accent glow + cover zoom
// + a "פתח" reveal overlay (WeMod/Steam-grade).
import type { Game } from "../lib/types";
import { availabilityLabel, accentFor, gradientFor, modStateLabel } from "../lib/theme";
import { resolveCoverUrl } from "../lib/coverUrl";
import { formatVersion } from "../lib/formatVersion";
import { IconAppOpenTrianglePlay } from "./UiIcons";
import { useState, useEffect, useRef } from "react";

interface Props {
  game: Game;
  onClick: (g: Game) => void;
  // lg = featured (home horizontal scroller - MUST stay a fixed width so it can
  // overflow-scroll), md = legacy fixed library tile, fluid = FILLS its grid
  // cell so the library/apps grid can size cards (small/medium/large) and the
  // column count adapts to the window. The 2:3 cover keeps the proportions.
  size?: "lg" | "md" | "fluid";
}

export default function GameCard({ game, onClick, size = "md" }: Props) {
  const [g1, g2] = gradientFor(game.theme_key);
  const accent   = accentFor(game.theme_key);
  const avail    = availabilityLabel(game.availability);
  const modBadge = game.has_mod_support && game.mod_state !== "NOT_INSTALLED" ? modStateLabel(game.mod_state) : null;
  const active   = game.mod_state === "ACTIVE";
  // Normalise the catalog's `cover` field (which may be a full URL,
  // a root-relative path, or just a bare filename like "cyberpunk.jpg")
  // to a usable <img src>. See lib/coverUrl.ts for the resolution rules.
  const coverSrc = resolveCoverUrl(game.cover, game.id);
  const [imgError, setImgError] = useState(false);   // the load genuinely FAILED
  const [imgLoaded, setImgLoaded] = useState(false); // the picture is painted
  // The placeholder stopped waiting: drop the shimmer and show the themed
  // gradient. Deliberately SEPARATE from imgError - it never hides or unmounts
  // the <img>, so a cover that arrives later (a lazy card scrolled into view
  // long after mount) still fades in over it.
  const [settled, setSettled]   = useState(false);
  const [hover, setHover]       = useState(false);
  const imgRef = useRef<HTMLImageElement>(null);
  // Reset the load/error latch when the cover URL changes on a persisted card
  // (grid cards are keyed by game.id; an SWR push can hand the same id a new
  // cover). Without this a once-failed cover stays a gradient forever - and the
  // <img> is unmounted while imgError, so it never even retries the new URL.
  //
  // THE "covers vanish after a drive scan" bug: rebuilding the list (scan, menu
  // switch, software tab) re-renders the cards with the SAME already-CACHED
  // cover URL. A cached <img> can be `complete` before React attaches onLoad, so
  // onLoad never fires and the cover stays at opacity-0 until the view is
  // remounted (leave + return "fixes" it). So check `complete` synchronously
  // after commit instead of waiting for an event that won't come.
  useEffect(() => {
    setSettled(false);
    const el = imgRef.current;
    if (el && el.complete && el.naturalWidth > 0) {
      setImgError(false); setImgLoaded(true);     // cached + decoded
    } else if (el && el.complete && el.naturalWidth === 0 && el.getAttribute("src")) {
      setImgError(true); setImgLoaded(false);      // cached broken
    } else {
      setImgError(false); setImgLoaded(false);     // genuinely loading
    }
  }, [coverSrc]);
  // STUCK-LOAD safety net: a request that never fires onLoad/onError would
  // otherwise leave the skeleton shimmering forever, which reads as a permanent
  // black box. It only SETTLES the placeholder into the themed gradient.
  //
  // 🔴 It must never disable the image. This clock starts at MOUNT, but a
  // `loading="lazy"` cover below the fold does not start fetching until it is
  // scrolled near - so the budget can be spent before the request even begins.
  // The first version set imgError (which unmounted the <img>), so the home
  // "תרגומים מובילים" row - which is below the fold - lost its covers ~12s in
  // and could never load them; only leaving the view and coming back rebuilt
  // the elements. Settling is cosmetic, so firing early is harmless.
  useEffect(() => {
    if (imgLoaded || imgError || settled) return;
    const t = window.setTimeout(() => setSettled(true), 12000);
    return () => window.clearTimeout(t);
  }, [coverSrc, imgLoaded, imgError, settled]);

  // fluid = fill the grid cell (the grid's minmax decides the real size);
  // lg/md keep their fixed widths + flex-shrink-0 for the horizontal scroller.
  const widthClass = size === "fluid" ? "w-full" : size === "lg" ? "w-[230px] flex-shrink-0" : "w-[180px] flex-shrink-0";

  return (
    <button
      type="button"
      data-tour="game-card"
      onClick={() => onClick(game)}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      className={`group ${widthClass} text-right lift
                  focus:outline-none focus:ring-2 focus:ring-brand-yellow/40
                  rounded-2xl`}
      style={{ direction: "rtl" }}
    >
      {/* Cover - strict 2:3 aspect.
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
          // No cover at all (failed / never arrived): the themed gradient alone
          // is near-black for every theme (#0a0a14 → #101830 by default), which
          // reads as a BROKEN card rather than a deliberate one. A soft wash of
          // the game's own accent over it makes it look like intended art.
          background: imgError || settled
            ? `radial-gradient(120% 85% at 50% 12%, ${accent}1f, transparent 68%),
               linear-gradient(160deg, ${g1}, ${g2})`
            : undefined,
        }}
      >
        {/* Placeholder + sweep while the cover streams in. Tinted with this
            game's accent (the CSS falls back to a neutral wash without it), so
            a card that is still loading is never an empty black rectangle. */}
        {!imgError && !imgLoaded && !settled && (
          <div
            className="skeleton absolute inset-0"
            style={{
              ["--skeleton-tint" as string]: `${accent}1a`,
              ["--skeleton-sheen" as string]: `${accent}30`,
            }}
            aria-hidden
          />
        )}
        {/* ALWAYS mounted - never gate this on imgError. An <img> that is not in
            the DOM can never load, so unmounting it turns any fallback into a
            permanent one. It sits at opacity-0 until it paints, so a broken
            cover is invisible regardless.
            loading: the home featured row (lg) is below the fold but is exactly
            the set the splash preloader already warmed, so lazy there only
            delays an image we already hold; the library grid (fluid, ~46 cards)
            keeps lazy. */}
        <img
          ref={imgRef}
          src={coverSrc}
          alt={game.titleEn}
          onError={() => setImgError(true)}
          onLoad={() => { setImgLoaded(true); setImgError(false); }}
          className={`absolute inset-0 w-full h-full object-cover
                     group-hover:scale-[1.06] transition-transform duration-[600ms] ease-out
                     ${imgLoaded ? "opacity-100" : "opacity-0"}`}
          loading={size === "lg" ? "eager" : "lazy"}
          draggable={false}
        />


        {/* Accent wash that fades in on hover - ties the cover to the game color. */}
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

        {/* Top-left version chip. The stage badge (אלפא/בטא/RC) is deliberately
            NOT shown on the card - it lives only inside the game/software detail
            panel; the card stays clean with just the version. */}
        <div className="absolute top-2 left-2 flex items-center gap-1">
          <span className="px-2 py-0.5 rounded-full text-[10px] font-medium text-slate-200
                           bg-black/90 ring-1 ring-white/15">
            {formatVersion(game.version)}
          </span>
        </div>

        {/* Active-mod glow dot - a small living indicator that the translation
            is currently applied (mirrors WeMod's "active" pip). */}
        {active && (
          <span
            className="absolute top-2 left-2 -translate-x-[2px] translate-y-7 w-2 h-2 rounded-full animate-pulse-dot"
            style={{ background: "#22c55e", boxShadow: "0 0 10px #22c55e" }}
            aria-hidden
          />
        )}

        {/* Hover reveal - a centered "פתח" pill over a soft veil. */}
        <div className="absolute inset-0 grid place-items-center opacity-0 group-hover:opacity-100
                        transition-opacity duration-300 pointer-events-none">
          <span
            className="inline-flex items-center gap-1 px-5 py-2 rounded-full text-[13px] font-extrabold text-brand-ink
                       translate-y-2 group-hover:translate-y-0 transition-transform duration-300
                       shadow-[0_8px_24px_-6px_rgba(0,0,0,0.7)]"
            style={{ background: accent }}
          >
            <IconAppOpenTrianglePlay width={15} className="shrink-0 opacity-90" />
            פתח
          </span>
        </div>

        {/* Bottom block - mod chip + title stacked in normal flow. */}
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
      {/* No caption below the cover - the tagline lives in the detail panel.
          Dropping it keeps every card the exact same height (fixed width +
          strict 2:3 cover), so the grid is perfectly uniform. */}
    </button>
  );
}
