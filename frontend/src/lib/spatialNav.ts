// Console-style spatial navigation: arrow keys / D-pad / left-stick move focus
// to the nearest focusable in that direction; A activates; B goes back; Start
// toggles Big Picture. One document keydown handler + ONE gamepad poll loop
// (only while a pad is connected). Returns a teardown fn.
//
// Design notes (what makes it feel smooth + stable on PS4/PS5/Xbox pads):
//   • Typematic auto-repeat: a press moves ONCE immediately, then waits
//     HOLD_DELAY before auto-repeating every REPEAT_INT - so a single flick =
//     a single move (no double-jump) and a held direction scrolls steadily.
//   • Stick hysteresis (ENGAGE/RELEASE) + a latched per-axis state so a stick
//     resting slightly off-centre never flickers, and the dominant axis wins
//     (a diagonal push doesn't get stuck always-vertical).
//   • Focus moves use INSTANT scroll (not smooth) - stacked smooth-scroll
//     animations on rapid repeats were the main source of the "jank".
//   • A `using-spatial-nav` <body> class forces the focus RING to show for
//     CONTROLLER focus too (programmatic .focus() often doesn't match
//     :focus-visible, so the user couldn't see where they were = "unstable").
//   • The poll is wrapped in try/catch so one bad frame can never kill it.
//
// Safe: never hijacks typing (input/textarea/contenteditable); arrow keys only
// preventDefault() when focus actually moved (so scrolling still works).

import { getGamepadMap, getGamepadCapture, type GpAction } from "./gamepadMap";

type Dir = "up" | "down" | "left" | "right";

const FOCUSABLE =
  'button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

function isTyping(el: Element | null): boolean {
  if (!el) return false;
  const t = el as HTMLElement;
  const tag = t.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || t.isContentEditable;
}

function visibleFocusables(): HTMLElement[] {
  const out: HTMLElement[] = [];
  document.querySelectorAll<HTMLElement>(FOCUSABLE).forEach((el) => {
    if (el.offsetParent === null && el.getClientRects().length === 0) return; // hidden
    // Skip elements that are invisible via opacity:0 / visibility:hidden - even
    // through an ancestor (e.g. the sidebar's "יציאה" button while collapsed),
    // so the ring never lands on something the user can't see.
    const cv = (el as unknown as { checkVisibility?: (o: object) => boolean }).checkVisibility;
    if (typeof cv === "function" && !cv.call(el, { opacityProperty: true, visibilityProperty: true })) return;
    const r = el.getBoundingClientRect();
    if (r.width <= 0 || r.height <= 0) return;
    if (r.bottom < 0 || r.top > window.innerHeight || r.right < 0 || r.left > window.innerWidth) return;
    out.push(el);
  });
  return out;
}

function center(r: DOMRect) { return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; }

function isScrollableY(el: HTMLElement): boolean {
  if (el.scrollHeight <= el.clientHeight + 2) return false;
  const oy = getComputedStyle(el).overflowY;
  return oy === "auto" || oy === "scroll";
}

/** The scroll container the right stick should drive: the nearest scrollable
 *  ancestor of the focused element, else the largest scrollable pane on screen. */
function findScrollable(): HTMLElement | null {
  let el = document.activeElement as HTMLElement | null;
  while (el && el !== document.body) {
    if (isScrollableY(el)) return el;
    el = el.parentElement;
  }
  let best: HTMLElement | null = null, bestExtra = 0;
  document.querySelectorAll<HTMLElement>("main, section, aside, div").forEach((e) => {
    const extra = e.scrollHeight - e.clientHeight;
    if (extra > bestExtra && e.clientHeight > 140 && isScrollableY(e)) { bestExtra = extra; best = e; }
  });
  return best;
}

// A "nav scope" groups focusables navigated as one column/list (the sidebar as
// a whole, or a settings tablist). Up/down stays inside the scope so it can't
// drift sideways into the main content mid-list.
function navScope(el: Element | null): Element | null {
  return (el as HTMLElement | null)?.closest?.("[data-sidebar],[data-nav-menu]") ?? null;
}

/** Pick the best focusable in `dir` from the active element. */
function pick(dir: Dir): HTMLElement | null {
  const active = document.activeElement as HTMLElement | null;
  const items = visibleFocusables();
  if (items.length === 0) return null;
  if (!active || active === document.body || !items.includes(active)) {
    return items[0]; // nothing focused → grab the first
  }
  const aRect = active.getBoundingClientRect();
  const a = center(aRect);
  const scope = navScope(active);

  const scan = (restrictToScope: boolean): HTMLElement | null => {
    let best: HTMLElement | null = null;
    let bestScore = Infinity;
    for (const el of items) {
      if (el === active) continue;
      if (restrictToScope && navScope(el) !== scope) continue;
      const r = el.getBoundingClientRect();
      const c = center(r);
      const dx = c.x - a.x, dy = c.y - a.y;
      // Cross-axis distance measured by RECTANGLE GAP, not centre offset, so a
      // full-width control (e.g. a slider that spans the panel) directly below a
      // corner toggle is correctly picked as "down" - its column overlaps, so
      // the gap is 0. (Centre-to-centre made wide rows fail the direction gate
      // and the nav skipped them.)
      const gapX = Math.max(0, aRect.left - r.right, r.left - aRect.right);
      const gapY = Math.max(0, aRect.top - r.bottom, r.top - aRect.bottom);
      let primary = 0, cross = 0, ok = false;
      switch (dir) {
        case "up":    ok = dy < -4 && r.top    < aRect.top;    primary = -dy; cross = gapX; break;
        case "down":  ok = dy >  4 && r.bottom > aRect.bottom; primary =  dy; cross = gapX; break;
        case "left":  ok = dx < -4 && r.left   < aRect.left;   primary = -dx; cross = gapY; break;
        case "right": ok = dx >  4 && r.right  > aRect.right;  primary =  dx; cross = gapY; break;
      }
      if (!ok) continue;
      const score = primary + cross * 3; // overlap (cross 0) strongly preferred
      if (score < bestScore) { bestScore = score; best = el; }
    }
    return best;
  };

  // Prefer staying inside the active element's nav scope (so moving down the
  // sidebar reaches the avatar + settings, not a content tile beside it). Only
  // when nothing is in-scope in that direction do we allow leaving it.
  if (scope) { const inScope = scan(true); if (inScope) return inScope; }
  return scan(false);
}

/** Mark that navigation is happening via keyboard/controller so the focus
 *  ring is guaranteed visible (see index.css `body.using-spatial-nav`).
 *  Cleared again on the next pointer interaction. */
function markNavActive() {
  document.body.classList.add("using-spatial-nav");
}

// React-safe write to a controlled <input> value (uses the native setter so
// React's onChange fires), then dispatch input+change.
function setReactInputValue(el: HTMLInputElement, value: string) {
  const proto = Object.getPrototypeOf(el);
  const setter = Object.getOwnPropertyDescriptor(proto, "value")?.set;
  if (setter) setter.call(el, value); else el.value = value;
  el.dispatchEvent(new Event("input", { bubbles: true }));
  el.dispatchEvent(new Event("change", { bubbles: true }));
}

/** If a range slider is focused, nudge its value toward max/min (L1/R1 on the
 *  pad). Returns true if a slider was focused (so the button is consumed). */
function stepFocusedSlider(towardMax: boolean): boolean {
  const el = document.activeElement as HTMLElement | null;
  if (!(el instanceof HTMLInputElement) || el.type !== "range" || el.disabled) return false;
  const step = Number(el.step) || 1;
  const min = el.min !== "" ? Number(el.min) : 0;
  const max = el.max !== "" ? Number(el.max) : 100;
  const next = Math.min(max, Math.max(min, Number(el.value) + (towardMax ? step : -step)));
  if (next !== Number(el.value)) { markNavActive(); setReactInputValue(el, String(next)); }
  return true;
}

function move(dir: Dir): boolean {
  const target = pick(dir);
  if (!target) return false;
  markNavActive();
  target.focus({ preventScroll: true });
  // INSTANT scroll (not smooth) - rapid repeats must not stack animations.
  target.scrollIntoView({ block: "nearest", inline: "nearest", behavior: "auto" });
  // "Live" row menus (settings tabs / sidebar nav, marked `data-nav-menu`):
  // moving up/down should SWITCH the selection, not only move the ring - so we
  // activate the row we land on, the way a console settings menu works.
  if (target.closest("[data-nav-menu]")) target.click();
  return true;
}

const KEY_DIR: Record<string, Dir> = {
  ArrowUp: "up", ArrowDown: "down", ArrowLeft: "left", ArrowRight: "right",
};

export function initSpatialNav(): () => void {
  // ── Keyboard ──────────────────────────────────────────────────────────
  const onKey = (e: KeyboardEvent) => {
    if (e.ctrlKey || e.altKey || e.metaKey) return;
    if (isTyping(document.activeElement)) return;
    const dir = KEY_DIR[e.key];
    if (dir) {
      if (move(dir)) e.preventDefault();  // only consume if focus moved
      return;
    }
    if (e.key === "Backspace") {
      e.preventDefault();
      window.dispatchEvent(new CustomEvent("nav-back"));
    }
  };
  document.addEventListener("keydown", onKey);

  // A pointer interaction means "I'm using the mouse" → drop the forced ring.
  const onPointer = () => document.body.classList.remove("using-spatial-nav");
  window.addEventListener("pointerdown", onPointer, true);
  window.addEventListener("mousemove", onPointer, true);

  // ── Gamepad ───────────────────────────────────────────────────────────
  // Poll ONLY while a pad is connected (a permanent rAF taxed the CPU).
  let raf = 0;
  const HOLD_DELAY = 380;   // ms a direction must be held before it auto-repeats
  const REPEAT_INT = 120;   // ms between auto-repeats while held
  const ENGAGE = 0.5, RELEASE = 0.32;   // stick hysteresis thresholds
  const now = () => performance.now();

  // latched per-axis stick state (-1/0/1) with hysteresis
  let sx = 0, sy = 0;
  let heldDir: Dir | null = null;
  let heldSince = 0, lastRepeat = 0;
  let scrollTarget: HTMLElement | null = null;   // right-stick scroll container
  let lastSlider = 0;                            // L1/R1 slider-step rate gate
  const prevBtn: boolean[] = [];

  // Live, user-remappable button bindings (Settings → controller).
  let map = getGamepadMap();
  const onMap = () => { map = getGamepadMap(); };
  window.addEventListener("gamepadmap", onMap);

  // Dispatch the action bound to a button, edge-triggered.
  const ACTION_EVENT: Record<GpAction, string | null> = {
    activate: null, // special-cased (clicks the focused element)
    back: "nav-back", home: "nav-home", settings: "nav-settings", sidebar: "nav-sidebar",
    library: "nav-library", downloads: "nav-downloads", personal: "nav-personal", refresh: "nav-refresh",
  };
  const ALL_ACTIONS: GpAction[] = [
    "activate", "back", "home", "settings", "sidebar",
    "library", "downloads", "personal", "refresh",
  ];

  const readDir = (gp: Gamepad): Dir | null => {
    const b = gp.buttons;
    const pressed = (i: number) => !!b[i]?.pressed;
    const ax = gp.axes[0] ?? 0, ay = gp.axes[1] ?? 0;

    // hysteresis: engage past ENGAGE, only release below RELEASE
    if (Math.abs(ax) < RELEASE) sx = 0; else if (ax >= ENGAGE) sx = 1; else if (ax <= -ENGAGE) sx = -1;
    if (Math.abs(ay) < RELEASE) sy = 0; else if (ay >= ENGAGE) sy = 1; else if (ay <= -ENGAGE) sy = -1;

    const dx = (pressed(14) ? -1 : 0) + (pressed(15) ? 1 : 0) + sx;
    const dy = (pressed(12) ? -1 : 0) + (pressed(13) ? 1 : 0) + sy;
    if (dx === 0 && dy === 0) return null;

    // Dominant axis: prefer the one pushed harder on the stick; D-pad ties → vertical.
    const wantV = dy !== 0, wantH = dx !== 0;
    if (wantV && (!wantH || Math.abs(ay) >= Math.abs(ax))) return dy < 0 ? "up" : "down";
    if (wantH) return dx < 0 ? "left" : "right";
    return null;
  };

  const poll = () => {
    try {
      const pads = navigator.getGamepads ? navigator.getGamepads() : [];
      const gp = pads && Array.from(pads).find(Boolean);
      if (gp) {
        const b = gp.buttons;

        // ── Capture mode (Settings edit-mode) ─────────────────────────────
        // Report the next pressed button to the Settings callback and swallow
        // ALL other input so nothing navigates/activates while remapping.
        const cap = getGamepadCapture();
        if (cap) {
          for (let i = 0; i < b.length; i++) {
            const p = !!b[i]?.pressed;
            if (p && !prevBtn[i]) cap(i);
            prevBtn[i] = p;
          }
          heldDir = null;            // reset nav state while captured
          raf = requestAnimationFrame(poll);
          return;
        }

        const dir = readDir(gp);
        const t = now();
        if (dir !== heldDir) {
          // direction changed (incl. → null): move once on a fresh press, then arm repeat
          heldDir = dir;
          if (dir) { move(dir); heldSince = t; lastRepeat = t; }
        } else if (dir) {
          // same direction still held → typematic auto-repeat
          if (t - heldSince >= HOLD_DELAY && t - lastRepeat >= REPEAT_INT) {
            move(dir); lastRepeat = t;
          }
        }
        // Right stick (axis 3) = scroll the focused scroll area up/down.
        // Quadratic response → fine control near centre, fast at full tilt.
        const ry = gp.axes[3] ?? 0;
        if (Math.abs(ry) > 0.15) {
          if (!scrollTarget) scrollTarget = findScrollable();
          scrollTarget?.scrollBy({ top: Math.sign(ry) * ry * ry * 34, behavior: "auto" });
        } else {
          scrollTarget = null;   // re-pick the target on the next push
        }

        // L1 (4) / R1 (5) nudge a FOCUSED slider - continuous while held. L1 =
        // toward min, R1 = toward max. Left/right stay free for navigation.
        const l1 = !!b[4]?.pressed, r1 = !!b[5]?.pressed;
        const onSlider = document.activeElement instanceof HTMLInputElement
          && (document.activeElement as HTMLInputElement).type === "range";
        if (onSlider && l1 !== r1) {
          if (t - lastSlider >= 85) { stepFocusedSlider(r1); lastSlider = t; }
          prevBtn[4] = l1; prevBtn[5] = r1;   // consume so a mapped action can't also fire
        } else if (!l1 && !r1) {
          lastSlider = 0;                      // released → next press steps immediately
        }

        // Remappable action buttons - edge-triggered, driven by the live map.
        const fire = (action: GpAction) => {
          const idx = map[action];
          if (idx < 0) return;
          const p = !!b[idx]?.pressed;
          if (p && !prevBtn[idx]) {
            markNavActive();
            if (action === "activate") (document.activeElement as HTMLElement)?.click?.();
            else window.dispatchEvent(new CustomEvent(ACTION_EVENT[action]!));
          }
        };
        for (const a of ALL_ACTIONS) fire(a);
        // Latch every mapped button's state for the next edge check.
        for (const a of ALL_ACTIONS) {
          const idx = map[a]; if (idx >= 0) prevBtn[idx] = !!b[idx]?.pressed;
        }
      }
    } catch { /* never let one bad frame kill the loop */ }
    raf = requestAnimationFrame(poll);
  };

  const anyPad = () => {
    const pads = navigator.getGamepads ? navigator.getGamepads() : [];
    return !!(pads && Array.from(pads).find(Boolean));
  };
  const startPoll = () => { if (!raf) raf = requestAnimationFrame(poll); };
  const stopPoll  = () => { if (raf) { cancelAnimationFrame(raf); raf = 0; } };
  const onConnect = () => startPoll();
  const onDisconnect = () => { if (!anyPad()) stopPoll(); };
  window.addEventListener("gamepadconnected", onConnect);
  window.addEventListener("gamepaddisconnected", onDisconnect);
  if (anyPad()) startPoll();

  // Robustness watcher (1 Hz): `gamepadconnected` does NOT reliably fire for a
  // pad in native mode (e.g. a DualSense not emulated) - the Gamepad API only
  // surfaces it after a button press while the window is focused, and tools
  // like DSX hot-swapping modes can skip the event entirely. So we also re-poll
  // getGamepads() once a second and start/stop the rAF loop accordingly - the
  // moment the pad becomes visible it just works, no reconnect dance needed.
  const watch = window.setInterval(() => {
    if (anyPad()) startPoll(); else stopPoll();
  }, 1000);

  return () => {
    document.removeEventListener("keydown", onKey);
    window.removeEventListener("pointerdown", onPointer, true);
    window.removeEventListener("mousemove", onPointer, true);
    window.removeEventListener("gamepadconnected", onConnect);
    window.removeEventListener("gamepaddisconnected", onDisconnect);
    window.removeEventListener("gamepadmap", onMap);
    window.clearInterval(watch);
    stopPoll();
  };
}
