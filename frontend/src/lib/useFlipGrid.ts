import { useCallback, useLayoutEffect, useRef } from "react";
import { gsap } from "gsap";
import { Flip } from "gsap/Flip";

gsap.registerPlugin(Flip);

type FlipState = ReturnType<typeof Flip.getState>;

/**
 * FLIP layout animation for a card grid / list (like the website's catalog).
 *
 * Returns a `capture()` that you MUST call SYNCHRONOUSLY, right BEFORE the state
 * change that alters the layout (sort mode, grid/list view, card size, or the
 * category grouping) - at that instant the DOM still holds the OLD positions, so
 * GSAP can record them. The hook then, in a useLayoutEffect keyed on `deps`, tweens
 * every `[data-flip-id]` element (cards AND the category separators) from its old
 * spot to its new one - the cards deal into place and the headers slide - and fades
 * elements that appear / disappear.
 *
 * Elements are matched across re-renders by their `data-flip-id`, so a card keeps
 * its identity even when it jumps from one category section to another.
 *
 * Honors the app's "reduce animations" setting (html.reduce-anims) - then it just
 * snaps with no motion.
 */
export function useFlipGrid<T extends HTMLElement>(
  containerRef: React.RefObject<T | null>,
  deps: unknown[],
): () => void {
  const stateRef = useRef<FlipState | null>(null);

  const capture = useCallback(() => {
    const el = containerRef.current;
    if (!el) return;
    const targets = el.querySelectorAll("[data-flip-id]");
    if (targets.length) stateRef.current = Flip.getState(targets);
  }, [containerRef]);

  useLayoutEffect(() => {
    const state = stateRef.current;
    stateRef.current = null;
    if (!state) return;
    // The FLIP card/separator animation runs ONLY at "full animation" (data-anim=
    // "high"); at normal / low / off the layout just snaps, like before.
    if (document.documentElement.getAttribute("data-anim") !== "high") return;

    // `absolute: true` lifts the moving cards + the entering/leaving headers out of
    // flow (so siblings don't jitter and a removed header can still be animated).
    // That collapses the container's height mid-tween → the page would jump; pin the
    // container's height for the duration and restore it on complete.
    const container = containerRef.current;
    const prevMinHeight = container ? container.style.minHeight : "";
    if (container) container.style.minHeight = `${container.offsetHeight}px`;
    const restore = () => { if (container) container.style.minHeight = prevMinHeight; };

    // 🔴 THE key for categorized↔flat: when the sort switches to/from a grouped view,
    // the cards' parent <section> changes, so React UNMOUNTS + REMOUNTS the card nodes.
    // `Flip.getState(nodeList)` captured the OLD (now-detached) nodes; if we let
    // `Flip.from(state)` default its targets to those, it tries to animate detached
    // nodes → nothing moves (which is exactly why grouped sorts didn't animate, while
    // flat↔flat - same nodes reordered - did). Passing the CURRENT elements as `targets`
    // makes GSAP match them to the captured state BY `data-flip-id` and FLIP them from
    // old→new, and correctly fade the section headers that enter/leave.
    const targets = container ? container.querySelectorAll("[data-flip-id]") : undefined;

    Flip.from(state, {
      targets,
      // NO stagger - every card moves to its new spot SIMULTANEOUSLY, so two cards
      // are never briefly stacked with one "remembering" to move later. One clean,
      // all-at-once deal.
      duration: 0.5,
      ease: "power3.inOut",
      absolute: true,
      onEnter: (els) =>
        gsap.fromTo(els, { opacity: 0, scale: 0.9 }, { opacity: 1, scale: 1, duration: 0.4, ease: "power2.out" }),
      onLeave: (els) =>
        gsap.to(els, { opacity: 0, scale: 0.9, duration: 0.3, ease: "power2.in" }),
      onComplete: restore,
      onInterrupt: restore,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return capture;
}
