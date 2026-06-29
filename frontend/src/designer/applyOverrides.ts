/* Apply a saved launcher-designer design to the REAL launcher.
 *
 * The designer ("edit the real app" mode) exports `design-overrides.json` — a
 * map of stable CSS selectors → { style, text, hidden }. Drop that export into
 * THIS folder (replace design-overrides.json) and rebuild the launcher; the
 * design then becomes the actual UI.
 *
 * CSS-property + hidden overrides are applied via a single injected <style>
 * (survives React re-renders). Text overrides are best-effort: applied once +
 * re-applied on DOM mutations (React may overwrite on re-render).
 *
 * Default file is `{}` → initDesignOverrides() is a guaranteed no-op, so the
 * shipping launcher is byte-identical until a real design is dropped in. */
import overridesData from "./design-overrides.json";

interface ElOverride { style?: Record<string, string>; text?: string; hidden?: boolean; }
type Overrides = Record<string, ElOverride>;

const kebab = (k: string) => k.replace(/[A-Z]/g, (m) => "-" + m.toLowerCase());
const STYLE_ID = "design-overrides";

function buildCss(o: Overrides): string {
  const rules: string[] = [];
  for (const [sel, ov] of Object.entries(o)) {
    if (ov.hidden) { rules.push(`${sel}{display:none!important}`); continue; }
    const decls: string[] = [];
    for (const [k, v] of Object.entries(ov.style || {})) {
      if (v === "" || v == null) continue;
      decls.push(`${kebab(k)}:${v}!important`);
    }
    if (decls.length) rules.push(`${sel}{${decls.join(";")}}`);
  }
  return rules.join("\n");
}

let textObserver: MutationObserver | null = null;

function applyText(o: Overrides): void {
  for (const [sel, ov] of Object.entries(o)) {
    if (typeof ov.text !== "string") continue;
    try { const n = document.querySelector(sel); if (n && n.textContent !== ov.text) n.textContent = ov.text; }
    catch { /* invalid selector */ }
  }
}

export function applyDesignOverrides(o: Overrides): void {
  if (!o || typeof o !== "object") return;
  let style = document.getElementById(STYLE_ID) as HTMLStyleElement | null;
  if (!style) { style = document.createElement("style"); style.id = STYLE_ID; document.head.appendChild(style); }
  style.textContent = buildCss(o);

  const hasText = Object.values(o).some((v) => typeof v.text === "string");
  if (hasText) {
    applyText(o);
    if (!textObserver) {
      let raf = 0;
      textObserver = new MutationObserver(() => {
        if (raf) return;
        raf = requestAnimationFrame(() => { raf = 0; applyText(o); });
      });
      textObserver.observe(document.body, { childList: true, subtree: true, characterData: true });
    }
  }
}

/** Call once on boot. No-op when design-overrides.json is empty. */
export function initDesignOverrides(): void {
  const o = overridesData as Overrides;
  if (!o || Object.keys(o).length === 0) return;
  if (document.body) applyDesignOverrides(o);
  else window.addEventListener("DOMContentLoaded", () => applyDesignOverrides(o), { once: true });
}
