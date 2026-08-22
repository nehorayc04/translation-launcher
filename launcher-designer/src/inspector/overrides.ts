/* Shared override model for the "edit the real app" designer.
 *
 * An override is keyed by a STABLE CSS selector (an nth-child path anchored at
 * the nearest id — i.e. `#root`), so the same element is targetable both in the
 * designer's preview iframe AND in the real launcher (same component tree →
 * same DOM structure). CSS-property overrides are applied by injecting a single
 * <style> element (rock-solid, survives React re-renders); text + hidden are a
 * best-effort DOM pass.
 *
 * This file is framework-free so the REAL launcher can reuse the exact same
 * buildCss/applyOverrides logic (see ../frontend/src/designer/applyOverrides.ts,
 * which is a copy kept in lockstep). */

export interface ElOverride {
  style?: Record<string, string>;  // CSS prop (camelCase or kebab) → value
  text?: string;                   // replace textContent (best-effort)
  hidden?: boolean;                // display:none
}
export type Overrides = Record<string, ElOverride>;

/** Editable style keys exposed in the properties panel. */
export const STYLE_KEYS = [
  "background", "color", "fontSize", "fontWeight", "padding", "margin",
  "borderRadius", "border", "width", "height", "opacity", "textAlign", "transform",
] as const;

const kebab = (k: string) => k.replace(/[A-Z]/g, (m) => "-" + m.toLowerCase());

/** A unique, structure-based selector for `el`, anchored at the nearest id
 * (normally `#root`). Deterministic across identical renders. */
export function cssPath(el: Element): string {
  const parts: string[] = [];
  let node: Element | null = el;
  while (node) {
    if (node.id) { parts.unshift("#" + cssEscape(node.id)); break; }
    const parent: Element | null = node.parentElement;
    if (!parent) { parts.unshift(node.tagName.toLowerCase()); break; }
    const idx = Array.prototype.indexOf.call(parent.children, node) + 1;
    parts.unshift(`${node.tagName.toLowerCase()}:nth-child(${idx})`);
    node = parent;
  }
  return parts.join(" > ");
}

function cssEscape(s: string): string {
  // CSS.escape isn't everywhere; ids here are simple ("root") so a basic guard suffices.
  return typeof CSS !== "undefined" && CSS.escape ? CSS.escape(s) : s.replace(/[^a-zA-Z0-9_-]/g, "\\$&");
}

/** Build a single CSS stylesheet string from the override map. */
export function buildCss(overrides: Overrides): string {
  const rules: string[] = [];
  for (const [sel, ov] of Object.entries(overrides)) {
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

const STYLE_ID = "design-overrides";

/** Inject/refresh the override stylesheet + run the text pass in a document. */
export function applyOverrides(doc: Document, overrides: Overrides): void {
  let style = doc.getElementById(STYLE_ID) as HTMLStyleElement | null;
  if (!style) {
    style = doc.createElement("style");
    style.id = STYLE_ID;
    doc.head.appendChild(style);
  }
  style.textContent = buildCss(overrides);
  // text overrides — best-effort (React may overwrite; re-runnable)
  for (const [sel, ov] of Object.entries(overrides)) {
    if (typeof ov.text !== "string") continue;
    try {
      const node = doc.querySelector(sel);
      if (node && node.textContent !== ov.text) node.textContent = ov.text;
    } catch { /* invalid selector — skip */ }
  }
}

export function serialize(overrides: Overrides): string {
  return JSON.stringify(overrides, null, 2);
}
export function parse(text: string): Overrides {
  const o = JSON.parse(text);
  return o && typeof o === "object" ? (o as Overrides) : {};
}
