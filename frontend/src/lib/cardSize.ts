// Card-size choice for the library / software grids.
//
// The grid uses a FIXED tile width over `auto-fill`, paired with
// `justify-content: space-evenly` (see the grids in LibraryView/AppsView).
//
// - FIXED width (not `minmax(min, 1fr)`): with `1fr` the cards STRETCH to fill,
//   so any width change - opening/closing the side rail - makes a column drop and
//   every card JUMP in size. A fixed width means a resize only re-distributes the
//   GAPS, not the card size.
// - `auto-FILL` (not `auto-fit`): auto-fill KEEPS the empty trailing tracks, so
//   EVERY section (3-card, 23-card, …) lays its cards on the SAME column-track
//   positions. A partial row of a few cards therefore fills the RIGHTMOST tracks,
//   perfectly aligned with the full rows above it - same gaps, same columns, all
//   pinned to the reading-start (right, under RTL) - instead of each section
//   spreading its own cards independently (which `auto-fit` does by collapsing
//   the empty tracks).
// - `space-evenly` distributes the leftover width as EQUAL gaps between the cards
//   and at both edges. As the sidebar animates its width, that leftover changes
//   every frame, so all the gaps glide together in real time - the cards actually
//   move (an animation) instead of sitting frozen until a column snaps.
export type CardSize = "sm" | "md" | "lg";

const MIN: Record<CardSize, string> = {
  sm: "128px",   // small cards  → most per row
  md: "176px",   // medium (default, matches the previous fixed 180px tile)
  lg: "244px",   // large cards  → fewest per row
};

/** grid-template-columns for a card size (fixed width; pair with justify-evenly). */
export function gridCols(size: CardSize): string {
  return `repeat(auto-fill, ${MIN[size] ?? MIN.md})`;
}

export const CARD_SIZES: { key: CardSize; label: string }[] = [
  { key: "sm", label: "כרטיסים קטנים" },
  { key: "md", label: "כרטיסים בינוניים" },
  { key: "lg", label: "כרטיסים גדולים" },
];

// ── LIST view density: how many game ROWS sit side by side ──
// "1" = one row per game (the classic list), "2"/"3" = that many rows per line
// (collapses to fewer columns on a narrow window so a row never gets squished).
export type ListCols = "1" | "2" | "3";

const LIST_GRID: Record<ListCols, string> = {
  "1": "grid-cols-1",
  "2": "grid-cols-1 sm:grid-cols-2",
  "3": "grid-cols-1 sm:grid-cols-2 xl:grid-cols-3",
};

/** Tailwind class for the list container at a given column count. */
export function listGridCls(cols: ListCols): string {
  return `grid ${LIST_GRID[cols] ?? LIST_GRID["1"]} gap-2`;
}

export const LIST_COLS: { key: ListCols; label: string }[] = [
  { key: "1", label: "שורה לכל משחק" },
  { key: "2", label: "שני משחקים בשורה" },
  { key: "3", label: "שלושה משחקים בשורה" },
];
