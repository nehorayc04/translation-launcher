// List-density segmented control (1 / 2 / 3 game-rows per line) for the library +
// software views, shown only in LIST view (the grid view has CardSizePicker).
// Glyphs show 1, 2, or 3 columns of stacked rows.
import type { ReactNode } from "react";
import { LIST_COLS, type ListCols } from "../lib/cardSize";
import SegmentedControl from "./SegmentedControl";

const bars = (cols: number): ReactNode => {
  const w = cols === 1 ? 18 : cols === 2 ? 8.5 : 5.5;   // per-column width
  const gap = cols === 1 ? 0 : cols === 2 ? 3 : 2.75;
  const xs = Array.from({ length: cols }, (_, i) => 3 + i * (w + gap));
  const ys = [4, 10.5, 17];
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
      {xs.map((x) => ys.map((y) => (
        <rect key={`${x}-${y}`} x={x} y={y} width={w} height="3" rx="1.3" />
      )))}
    </svg>
  );
};

const GLYPH: Record<ListCols, ReactNode> = { "1": bars(1), "2": bars(2), "3": bars(3) };

export default function ListLayoutPicker({
  value, onChange, accent,
}: {
  value: ListCols;
  onChange: (c: ListCols) => void;
  /** Match the host view's toggle colour (AppsView passes its accent). */
  accent?: string;
}) {
  // Shared SegmentedControl - same slide + glass as every other picker.
  return (
    <SegmentedControl<ListCols>
      ariaLabel="צפיפות רשימה"
      value={value}
      onChange={onChange}
      size="sm"
      accent={accent}
      showHints={false}
      options={LIST_COLS.map((c) => ({ value: c.key, icon: GLYPH[c.key], title: c.label }))}
    />
  );
}
