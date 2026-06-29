// Global click-ripple. One document-level pointerdown listener spawns a
// short-lived .ripple-ink span inside any <button> that isn't opted out
// (data-noripple) and isn't disabled. Non-invasive: no per-button wiring.
// Returns a teardown fn.
export function initRipple(): () => void {
  const onDown = (e: PointerEvent) => {
    if (e.button !== 0) return; // primary click only
    const target = e.target as Element | null;
    const btn = target?.closest?.("button") as HTMLButtonElement | null;
    if (!btn) return;
    if (btn.disabled || btn.hasAttribute("data-noripple")) return;

    const rect = btn.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) return;

    // The host must clip + be a positioning context. Most of our buttons
    // are rounded; force overflow hidden + relative without disturbing layout.
    const cs = getComputedStyle(btn);
    if (cs.position === "static") btn.style.position = "relative";
    if (cs.overflow === "visible") btn.style.overflow = "hidden";

    const size = Math.max(rect.width, rect.height);
    const ink = document.createElement("span");
    ink.className = "ripple-ink";
    ink.style.width = ink.style.height = `${size}px`;
    ink.style.left = `${e.clientX - rect.left - size / 2}px`;
    ink.style.top = `${e.clientY - rect.top - size / 2}px`;
    btn.appendChild(ink);
    ink.addEventListener("animationend", () => ink.remove(), { once: true });
    // Safety net if animationend never fires.
    setTimeout(() => ink.remove(), 800);
  };

  document.addEventListener("pointerdown", onDown, true);
  return () => document.removeEventListener("pointerdown", onDown, true);
}
