// A single, shared segmented control: one rounded GLASS row with a thumb that
// SLIDES between the options - the same motion language as switching menus.
// Used by every multi-choice setting (sidebar mode, animation level, ...), so
// they all look and move identically instead of each rolling its own row.
//
// Three things this gets right that a naive implementation does not:
//
//  1. GEOMETRY COMES FROM offsetLeft/offsetWidth, NOT getBoundingClientRect.
//     getBoundingClientRect reports the TRANSFORMED box, and the settings screen
//     mounts inside `.view-transition`, which animates scale(0.976) → 1. Measuring
//     mid-animation returned scaled coords that were then applied INSIDE that same
//     scaled context - so the thumb sat visibly off ("escapes left") and only
//     corrected itself when something forced a re-measure later. offsetLeft is
//     untransformed layout geometry, and it is already relative to the offsetParent's
//     PADDING box - exactly the box an absolutely-positioned thumb is laid out
//     against. (This is why the sidebar's indicator, which uses offsetTop, never
//     had the bug.)
//
//  2. THE OBSERVER IS CREATED ONCE. ResizeObserver fires a callback IMMEDIATELY on
//     observe(). Re-creating it on every value change meant: click → slide starts →
//     observer re-attaches → instant callback → snap → the slide was killed. Hence
//     "moving between options does no transition".
//
//  3. SLIDE on a value change, SNAP on a layout change. The thumb must glide when
//     you pick an option, but when the SIDEBAR expands/collapses or the window is
//     resized the row's geometry moves underneath it, and that same transition
//     turns into a visible lag dragging behind the layout.
import { useCallback, useEffect, useLayoutEffect, useRef, type ReactNode } from "react";

export interface SegOption<T extends string> {
  value: T;
  /** Text label. Omit for an icon-only option (card size / list layout). */
  label?: string;
  /** Small second line under the label. */
  hint?: string;
  /** Glyph shown before the label, or alone when there is no label. */
  icon?: ReactNode;
  /** Native tooltip. */
  title?: string;
}

interface Props<T extends string> {
  value: T;
  options: SegOption<T>[];
  onChange: (v: T) => void;
  ariaLabel?: string;
  showHints?: boolean;
  /** Greys the row out and blocks changes (e.g. a language switch mid-write). */
  disabled?: boolean;
  /** "md" = a settings row. "sm" = a compact toolbar control. */
  size?: "md" | "sm";
  /** Selection colour. Defaults to the app's brand cyan. */
  accent?: string;
  className?: string;
}

export default function SegmentedControl<T extends string>({
  value, options, onChange, ariaLabel, showHints = true,
  disabled = false, size = "md", accent, className,
}: Props<T>) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const thumbRef = useRef<HTMLSpanElement>(null);
  const btnRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const prevValue = useRef<T | null>(null);

  const activeIdx = Math.max(0, options.findIndex((o) => o.value === value));

  /** Put the thumb on the active option. `instant` = no transition (layout). */
  const place = useCallback((instant: boolean) => {
    const th = thumbRef.current;
    const el = btnRefs.current[activeIdx];
    if (!th || !el) return;
    // Untransformed, padding-box-relative - see note 1 above.
    const x = el.offsetLeft;
    const w = el.offsetWidth;
    if (!w) return;                      // not laid out yet; the observer will call us
    if (instant) th.style.transition = "none";
    th.style.transform = `translateX(${x}px)`;
    th.style.width = `${w}px`;
    th.style.opacity = "1";
    if (instant) {
      void th.offsetWidth;               // force reflow → this write is not animated
      th.style.transition = "";          // hand control back to the stylesheet
    }
  }, [activeIdx]);

  // Keep the observers pointed at the newest `place` without re-creating them.
  const placeRef = useRef(place);
  placeRef.current = place;

  // While a slide is in flight, a layout tick must RETARGET it - not snap it.
  // A ResizeObserver can fire for all sorts of incidental reasons right after a
  // click, and snapping there killed the animation outright ("sometimes it just
  // jumps to the choice with no transition").
  const slidingUntil = useRef(0);

  // Value change → SLIDE. First mount → snap.
  useLayoutEffect(() => {
    const isValueChange = prevValue.current !== null && prevValue.current !== value;
    prevValue.current = value;
    if (isValueChange) slidingUntil.current = Date.now() + 500;   // ~the .44s curve
    place(!isValueChange);
  }, [value, place]);

  // Layout changes → SNAP. Created ONCE (note 2).
  useEffect(() => {
    // Snap only when NOT mid-slide; during a slide, re-place with the transition
    // still on so the thumb smoothly re-aims at the new geometry.
    const onLayout = () => placeRef.current(Date.now() >= slidingUntil.current);
    let ro: ResizeObserver | null = null;
    try {
      // Observing the wrapper AND the buttons catches the sidebar's width
      // transition (which fires no window resize event at all) and a text-scale
      // change, frame by frame - so the thumb tracks instead of lagging.
      ro = new ResizeObserver(onLayout);
      if (wrapRef.current) ro.observe(wrapRef.current);
      btnRefs.current.forEach((b) => b && ro?.observe(b));
    } catch { /* no ResizeObserver */ }
    window.addEventListener("resize", onLayout);
    // Re-place on the NEXT frame: at mount the row is often not finally laid out
    // (fonts/grid still settling), so the first measure can be tens of px out and
    // would otherwise sit wrong until something else happened to trigger a
    // re-measure. Same guard the sidebar's indicator already uses.
    const raf = requestAnimationFrame(() => placeRef.current(true));
    // The screen mounts inside `.view-transition`; re-place once its entrance
    // animation ends, in case anything settled differently.
    const wrap = wrapRef.current;
    const onAnimEnd = () => placeRef.current(true);
    wrap?.closest(".view-transition")?.addEventListener("animationend", onAnimEnd);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", onLayout);
      wrap?.closest(".view-transition")?.removeEventListener("animationend", onAnimEnd);
      ro?.disconnect();
    };
  }, []);

  return (
    <div
      ref={wrapRef}
      role="radiogroup"
      aria-label={ariaLabel}
      className={`seg-glass ${size === "sm" ? "seg-sm" : ""} ${disabled ? "seg-disabled" : ""} ${className || ""}`}
      data-nav-menu
      style={accent ? ({ ["--seg-accent" as string]: accent }) : undefined}
    >
      {/* Starts at opacity:0 so it is never seen at x=0 before the first measure. */}
      <span ref={thumbRef} aria-hidden="true" className="seg-thumb" style={{ opacity: 0 }} />
      {options.map((o, i) => {
        const active = o.value === value;
        return (
          <button
            key={o.value}
            ref={(el) => { btnRefs.current[i] = el; }}
            type="button"
            role="radio"
            aria-checked={active}
            disabled={disabled}
            title={o.title}
            aria-label={o.label ? undefined : o.title}
            onClick={() => onChange(o.value)}
            className={`seg-opt ${active ? "seg-opt-on" : ""}`}
            data-noglass
          >
            {o.icon && <span className="seg-icon">{o.icon}</span>}
            {o.label && <span className="seg-label">{o.label}</span>}
            {showHints && o.hint && <span className="seg-hint">{o.hint}</span>}
          </button>
        );
      })}
    </div>
  );
}
