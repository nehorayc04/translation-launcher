// Click-and-DRAG horizontal scrolling for a container (the home "תרגומים מובילים"
// row). A SHORT click passes through untouched, so a child card's onClick still
// opens the game; a DRAG (pointer moved past a small threshold) scrolls the row
// and SUPPRESSES the click so the drag never also opens a game.
//
// Pointer capture is taken ONLY once a real drag begins, so a plain tap never
// captures and its click reaches the card normally. Works in RTL (the scroll is
// relative "grab + pull", direction-agnostic).
import { useEffect, useRef } from "react";

const THRESHOLD = 6; // px of movement before it counts as a drag (not a click)

export function useDragScroll<T extends HTMLElement>() {
  const ref = useRef<T | null>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    let down = false;
    let dragging = false;
    let startX = 0;
    let startLeft = 0;
    let pointerId = -1;

    const onDown = (e: PointerEvent) => {
      if (e.button !== 0) return;          // left button / primary touch only
      down = true;
      dragging = false;
      startX = e.clientX;
      startLeft = el.scrollLeft;
      pointerId = e.pointerId;
    };

    const onMove = (e: PointerEvent) => {
      if (!down) return;
      const dx = e.clientX - startX;
      if (!dragging) {
        if (Math.abs(dx) < THRESHOLD) return;   // still a tap - let it be a click
        dragging = true;
        try { el.setPointerCapture(pointerId); } catch { /* ignore */ }
        el.style.cursor = "grabbing";
        el.style.userSelect = "none";
      }
      el.scrollLeft = startLeft - dx;   // grab + pull (relative → RTL-safe)
      e.preventDefault();
    };

    const endDrag = () => {
      if (!down) return;
      down = false;
      el.style.cursor = "";
      el.style.userSelect = "";
      try { el.releasePointerCapture(pointerId); } catch { /* ignore */ }
      if (dragging) {
        // A drag just ended → swallow the click it would otherwise synthesize on
        // the card underneath (capture-phase, once), so dragging never opens a game.
        const kill = (ev: Event) => { ev.stopPropagation(); ev.preventDefault(); };
        el.addEventListener("click", kill, { capture: true, once: true } as AddEventListenerOptions);
        // If no click fires (e.g. released outside a card), drop the guard shortly after.
        window.setTimeout(() => el.removeEventListener("click", kill, { capture: true } as EventListenerOptions), 350);
      }
      dragging = false;
    };

    el.addEventListener("pointerdown", onDown);
    el.addEventListener("pointermove", onMove);
    el.addEventListener("pointerup", endDrag);
    el.addEventListener("pointercancel", endDrag);
    return () => {
      el.removeEventListener("pointerdown", onDown);
      el.removeEventListener("pointermove", onMove);
      el.removeEventListener("pointerup", endDrag);
      el.removeEventListener("pointercancel", endDrag);
    };
  }, []);

  return ref;
}
