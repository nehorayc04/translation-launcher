// Console-style spatial navigation: arrow keys / D-pad / left-stick move focus
// to the nearest focusable element in that direction; A activates; B goes back.
// One document-level handler + a gamepad polling loop. Returns a teardown fn.
//
// Safe: never hijacks typing (inputs/textarea/contenteditable), and for arrow
// keys it only preventDefault()s when it actually moves focus (so scrolling
// still works when there's no candidate in that direction).

type Dir = "up" | "down" | "left" | "right";

const FOCUSABLE =
  'button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

function isTyping(el: Element | null): boolean {
  if (!el) return false;
  const t = (el as HTMLElement);
  const tag = t.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || t.isContentEditable;
}

function visibleFocusables(): HTMLElement[] {
  const out: HTMLElement[] = [];
  document.querySelectorAll<HTMLElement>(FOCUSABLE).forEach((el) => {
    if (el.offsetParent === null && el.getClientRects().length === 0) return; // hidden
    const r = el.getBoundingClientRect();
    if (r.width <= 0 || r.height <= 0) return;
    if (r.bottom < 0 || r.top > window.innerHeight || r.right < 0 || r.left > window.innerWidth) return;
    out.push(el);
  });
  return out;
}

function center(r: DOMRect) { return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; }

/** Pick the best focusable in `dir` from the active element. */
function pick(dir: Dir): HTMLElement | null {
  const active = document.activeElement as HTMLElement | null;
  const items = visibleFocusables();
  if (items.length === 0) return null;
  if (!active || active === document.body || !items.includes(active)) {
    return items[0]; // nothing focused → grab the first
  }
  const a = center(active.getBoundingClientRect());
  let best: HTMLElement | null = null;
  let bestScore = Infinity;
  for (const el of items) {
    if (el === active) continue;
    const c = center(el.getBoundingClientRect());
    const dx = c.x - a.x, dy = c.y - a.y;
    // Direction gate (primary axis must dominate).
    let primary = 0, cross = 0, ok = false;
    switch (dir) {
      case "up":    ok = dy < -2 && Math.abs(dy) >= Math.abs(dx) * 0.6; primary = -dy; cross = Math.abs(dx); break;
      case "down":  ok = dy >  2 && Math.abs(dy) >= Math.abs(dx) * 0.6; primary =  dy; cross = Math.abs(dx); break;
      case "left":  ok = dx < -2 && Math.abs(dx) >= Math.abs(dy) * 0.6; primary = -dx; cross = Math.abs(dy); break;
      case "right": ok = dx >  2 && Math.abs(dx) >= Math.abs(dy) * 0.6; primary =  dx; cross = Math.abs(dy); break;
    }
    if (!ok) continue;
    const score = primary + cross * 2; // prefer aligned + close
    if (score < bestScore) { bestScore = score; best = el; }
  }
  return best;
}

function move(dir: Dir): boolean {
  const target = pick(dir);
  if (!target) return false;
  target.focus({ preventScroll: false });
  target.scrollIntoView({ block: "nearest", inline: "nearest", behavior: "smooth" });
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
      // Only consume the key if we actually moved focus (else allow scroll).
      if (move(dir)) e.preventDefault();
      return;
    }
    // B-equivalent: Backspace goes "back" (Escape is owned by modals).
    if (e.key === "Backspace") {
      e.preventDefault();
      window.dispatchEvent(new CustomEvent("nav-back"));
    }
  };
  document.addEventListener("keydown", onKey);

  // ── Gamepad ───────────────────────────────────────────────────────────
  // PERF: poll ONLY while a controller is actually connected. A permanent
  // requestAnimationFrame loop (60fps) running even with no gamepad taxed the
  // CPU continuously and made the launcher feel sluggish. We start the loop on
  // `gamepadconnected` and stop it once the last pad disconnects.
  let raf = 0;
  const REPEAT_MS = 170;
  const last: Record<string, number> = {};
  const prevBtn: boolean[] = [];

  const now = () => performance.now();
  const canRepeat = (k: string) => {
    const t = now();
    if (!last[k] || t - last[k] > REPEAT_MS) { last[k] = t; return true; }
    return false;
  };

  const anyPad = () => {
    const pads = navigator.getGamepads ? navigator.getGamepads() : [];
    return !!(pads && Array.from(pads).find(Boolean));
  };

  const poll = () => {
    const pads = navigator.getGamepads ? navigator.getGamepads() : [];
    const gp = pads && Array.from(pads).find(Boolean);
    if (gp) {
      const ax = gp.axes[0] ?? 0, ay = gp.axes[1] ?? 0;
      const b = gp.buttons;
      const pressed = (i: number) => !!b[i]?.pressed;
      // D-pad (12-15) + left-stick → directional moves (rate-limited).
      if ((pressed(12) || ay < -0.55) && canRepeat("up")) move("up");
      else if ((pressed(13) || ay > 0.55) && canRepeat("down")) move("down");
      else if ((pressed(14) || ax < -0.55) && canRepeat("left")) move("left");
      else if ((pressed(15) || ax > 0.55) && canRepeat("right")) move("right");
      else if (Math.abs(ax) < 0.3 && Math.abs(ay) < 0.3) {
        // recenter the repeat clocks when the stick returns to neutral
        delete last.up; delete last.down; delete last.left; delete last.right;
      }
      // A (0) = activate; B (1) = back. Edge-triggered.
      const a0 = pressed(0), b1 = pressed(1), start = pressed(9);
      if (a0 && !prevBtn[0]) (document.activeElement as HTMLElement)?.click?.();
      if (b1 && !prevBtn[1]) window.dispatchEvent(new CustomEvent("nav-back"));
      if (start && !prevBtn[9]) window.dispatchEvent(new CustomEvent("toggle-bigpicture"));
      prevBtn[0] = a0; prevBtn[1] = b1; prevBtn[9] = start;
    }
    raf = requestAnimationFrame(poll);
  };

  const startPoll = () => { if (!raf) raf = requestAnimationFrame(poll); };
  const stopPoll  = () => { if (raf) { cancelAnimationFrame(raf); raf = 0; } };
  const onConnect = () => startPoll();
  const onDisconnect = () => { if (!anyPad()) stopPoll(); };
  window.addEventListener("gamepadconnected", onConnect);
  window.addEventListener("gamepaddisconnected", onDisconnect);
  if (anyPad()) startPoll();   // a pad already connected at init

  return () => {
    document.removeEventListener("keydown", onKey);
    window.removeEventListener("gamepadconnected", onConnect);
    window.removeEventListener("gamepaddisconnected", onDisconnect);
    stopPoll();
  };
}
