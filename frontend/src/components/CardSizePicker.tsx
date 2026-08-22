// Card-size segmented control (small / medium / large) for the library +
// software grids. Sits next to the grid/list toggle and only makes sense in
// grid view, so the parent renders it only then. Icons are three nested-square
// glyphs whose density mirrors "more per row" → "fewer per row".
import type { ReactNode } from "react";
import { CARD_SIZES, type CardSize } from "../lib/cardSize";
import SegmentedControl from "./SegmentedControl";

const GLYPH: Record<CardSize, ReactNode> = {
  // many small squares
  sm: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
      <rect x="3" y="3" width="4.5" height="4.5" rx="1" /><rect x="9.75" y="3" width="4.5" height="4.5" rx="1" /><rect x="16.5" y="3" width="4.5" height="4.5" rx="1" />
      <rect x="3" y="9.75" width="4.5" height="4.5" rx="1" /><rect x="9.75" y="9.75" width="4.5" height="4.5" rx="1" /><rect x="16.5" y="9.75" width="4.5" height="4.5" rx="1" />
      <rect x="3" y="16.5" width="4.5" height="4.5" rx="1" /><rect x="9.75" y="16.5" width="4.5" height="4.5" rx="1" /><rect x="16.5" y="16.5" width="4.5" height="4.5" rx="1" />
    </svg>
  ),
  // 2x2 medium squares
  md: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
      <rect x="3" y="3" width="8" height="8" rx="1.5" /><rect x="13" y="3" width="8" height="8" rx="1.5" />
      <rect x="3" y="13" width="8" height="8" rx="1.5" /><rect x="13" y="13" width="8" height="8" rx="1.5" />
    </svg>
  ),
  // one big square
  lg: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
      <rect x="3" y="3" width="18" height="18" rx="2.5" />
    </svg>
  ),
};

export default function CardSizePicker({
  value, onChange, accent,
}: {
  value: CardSize;
  onChange: (s: CardSize) => void;
  /** Match the host view's toggle colour (AppsView uses its own accent;
   *  LibraryView uses brand-cyan when omitted). */
  accent?: string;
}) {
  // Built on the shared SegmentedControl so it slides + glasses exactly like
  // every other multi-choice control in the app (settings, sidebar, language).
  return (
    <SegmentedControl<CardSize>
      ariaLabel="גודל כרטיסים"
      value={value}
      onChange={onChange}
      size="sm"
      accent={accent}
      showHints={false}
      options={CARD_SIZES.map((s) => ({ value: s.key, icon: GLYPH[s.key], title: s.label }))}
    />
  );
}
