/* The designer shell — "edit the REAL launcher" mode.
 *
 * The center is an <iframe src="/preview.html"> running the ACTUAL launcher App
 * (with a mocked eel backend → sample data), so it looks 1:1. With "בחירה" on,
 * hovering the iframe highlights elements and clicking selects one; the right
 * panel edits that element's CSS / text / visibility. Edits are stored as
 * overrides keyed by a stable selector and injected live as a <style> in the
 * iframe — the SAME overrides the real launcher applies on boot
 * (../frontend/src/designer/applyOverrides.ts), so the design becomes the app.
 *
 * To change screen: turn בחירה OFF, click the real sidebar inside the preview,
 * then turn בחירה back ON. */
import { useCallback, useEffect, useRef, useState } from "react";
import {
  type Overrides, type ElOverride, STYLE_KEYS,
  cssPath, applyOverrides, serialize, parse,
} from "./inspector/overrides";

const LS_KEY = "launcher_designer.overrides.v1";
const HOVER_ID = "__dz_hover";
const SELECT_ID = "__dz_select";

export function App() {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [overrides, setOverrides] = useState<Overrides>({});
  const [selSel, setSelSel] = useState<string | null>(null);
  const [selInfo, setSelInfo] = useState<{ tag: string; isLeaf: boolean; text: string } | null>(null);
  const [inspect, setInspect] = useState(true);
  const [toast, setToast] = useState("");
  const ovRef = useRef(overrides);
  ovRef.current = overrides;
  const inspectRef = useRef(inspect);
  inspectRef.current = inspect;

  const flash = (m: string) => { setToast(m); setTimeout(() => setToast(""), 1600); };

  // load saved overrides once
  useEffect(() => {
    try { const raw = localStorage.getItem(LS_KEY); if (raw) setOverrides(parse(raw)); } catch { /* */ }
  }, []);

  const doc = () => iframeRef.current?.contentDocument || null;
  const win = () => iframeRef.current?.contentWindow || null;

  const overlay = (d: Document, id: string, color: string) => {
    let el = d.getElementById(id) as HTMLDivElement | null;
    if (!el) {
      el = d.createElement("div");
      el.id = id;
      el.style.cssText = `position:fixed;pointer-events:none;z-index:2147483646;border:2px solid ${color};border-radius:3px;transition:all .03s linear;display:none`;
      d.body.appendChild(el);
    }
    return el;
  };
  const place = (el: HTMLDivElement, r: DOMRect) => {
    el.style.display = "block";
    el.style.left = r.left + "px"; el.style.top = r.top + "px";
    el.style.width = r.width + "px"; el.style.height = r.height + "px";
  };

  const isOverlay = (n: Element | null) => !!n && (n.id === HOVER_ID || n.id === SELECT_ID);

  const reposSelect = useCallback(() => {
    const d = doc(); if (!d) return;
    const sel = overlay(d, SELECT_ID, "#3a6bff");
    if (!selSel) { sel.style.display = "none"; return; }
    try { const node = d.querySelector(selSel); if (node) place(sel, node.getBoundingClientRect()); else sel.style.display = "none"; }
    catch { sel.style.display = "none"; }
  }, [selSel]);

  // wire / rewire inspect listeners + apply overrides on the live doc
  const wire = useCallback(() => {
    const d = doc(); if (!d) return;
    applyOverrides(d, ovRef.current);
    overlay(d, HOVER_ID, "#5878d8");
    overlay(d, SELECT_ID, "#3a6bff");
    reposSelect();

    const onMove = (e: Event) => {
      if (!inspectRef.current) return;
      const t = e.target as Element;
      if (isOverlay(t)) return;
      const h = overlay(d, HOVER_ID, "#5878d8");
      if (t && t.getBoundingClientRect) place(h, t.getBoundingClientRect());
    };
    const onLeave = () => { const h = d.getElementById(HOVER_ID); if (h) h.style.display = "none"; };
    const onClick = (e: Event) => {
      if (!inspectRef.current) return;
      const t = e.target as Element;
      if (isOverlay(t)) return;
      e.preventDefault(); e.stopPropagation();
      const sel = cssPath(t);
      setSelSel(sel);
      setSelInfo({ tag: t.tagName.toLowerCase(), isLeaf: t.childElementCount === 0, text: t.textContent || "" });
    };
    d.addEventListener("mousemove", onMove, true);
    d.addEventListener("mouseleave", onLeave, true);
    d.addEventListener("click", onClick, true);
    (d as any).__dzCleanup = () => {
      d.removeEventListener("mousemove", onMove, true);
      d.removeEventListener("mouseleave", onLeave, true);
      d.removeEventListener("click", onClick, true);
    };
  }, [reposSelect]);

  const onIframeLoad = () => { wire(); };

  // re-apply overrides whenever they change + persist
  useEffect(() => {
    const d = doc(); if (d) applyOverrides(d, overrides);
    try { localStorage.setItem(LS_KEY, JSON.stringify(overrides)); } catch { /* */ }
  }, [overrides]);

  useEffect(() => { reposSelect(); }, [selSel, reposSelect]);

  // hide hover outline when inspect turns off
  useEffect(() => {
    const d = doc(); if (!d) return;
    if (!inspect) { const h = d.getElementById(HOVER_ID); if (h) h.style.display = "none"; }
  }, [inspect]);

  // ── edit helpers ──────────────────────────────────────────────
  const cur: ElOverride = (selSel && overrides[selSel]) || {};
  const computed = (prop: string): string => {
    const d = doc(), w = win(); if (!d || !w || !selSel) return "";
    try { const n = d.querySelector(selSel); return n ? (w.getComputedStyle(n) as any)[prop] || "" : ""; } catch { return ""; }
  };

  const setStyle = (k: string, v: string) => {
    if (!selSel) return;
    setOverrides((o) => {
      const e: ElOverride = { ...(o[selSel] || {}) };
      const st = { ...(e.style || {}) };
      if (v === "") delete st[k]; else st[k] = v;
      e.style = st;
      return { ...o, [selSel]: e };
    });
  };
  const setText = (v: string) => {
    if (!selSel) return;
    setOverrides((o) => ({ ...o, [selSel]: { ...(o[selSel] || {}), text: v } }));
  };
  const setHidden = (h: boolean) => {
    if (!selSel) return;
    setOverrides((o) => ({ ...o, [selSel]: { ...(o[selSel] || {}), hidden: h || undefined } }));
  };
  const resetEl = () => {
    if (!selSel) return;
    setOverrides((o) => { const n = { ...o }; delete n[selSel]; return n; });
  };

  // transform translate (free nudge) parse/format
  const parseT = (t: string): { x: number; y: number } => {
    const m = /translate\(\s*(-?\d+)px\s*,\s*(-?\d+)px\s*\)/.exec(t || "");
    return m ? { x: +m[1], y: +m[2] } : { x: 0, y: 0 };
  };
  const tVal = parseT(cur.style?.transform || "");
  const setT = (x: number, y: number) => setStyle("transform", (x || y) ? `translate(${x}px, ${y}px)` : "");

  // ── toolbar actions ───────────────────────────────────────────
  const save = () => { try { localStorage.setItem(LS_KEY, JSON.stringify(overrides)); } catch { /* */ } flash("נשמר ✓"); };
  const exportJson = () => {
    const blob = new Blob([serialize(overrides)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = "design-overrides.json"; a.click();
    URL.revokeObjectURL(a.href);
  };
  const importJson = (file: File) => {
    const r = new FileReader();
    r.onload = () => { try { setOverrides(parse(String(r.result))); flash("יובא ✓"); } catch { flash("קובץ לא תקין"); } };
    r.readAsText(file);
  };
  const resetAll = () => { if (confirm("לאפס את כל העיצוב?")) setOverrides({}); };
  const [iframeKey, setIframeKey] = useState(0);
  const refreshPreview = () => { setSelSel(null); setSelInfo(null); setIframeKey((k) => k + 1); };

  const count = Object.keys(overrides).length;

  return (
    <div className="shell">
      <div className="topbar">
        <span className="brand">🎨 מעצב התוכנה — עריכה חיה</span>
        <button className={"btn" + (inspect ? " primary" : "")} type="button" onClick={() => setInspect((v) => !v)}>
          {inspect ? "בחירה: פעיל" : "בחירה: כבוי (לניווט)"}
        </button>
        <span className="spacer" />
        {toast && <span style={{ color: "#7fd18f", fontSize: 13, marginInlineEnd: 8 }}>{toast}</span>}
        <span className="muted" style={{ fontSize: 12, marginInlineEnd: 8 }}>{count} שינויים</span>
        <button className="btn" type="button" onClick={refreshPreview}>רענן תצוגה</button>
        <button className="btn" type="button" onClick={resetAll}>אפס הכול</button>
        <button className="btn" type="button" onClick={exportJson}>ייצוא</button>
        <label className="btn ghost" style={{ cursor: "pointer" }}>
          ייבוא
          <input type="file" accept="application/json" style={{ display: "none" }}
            onChange={(e) => e.target.files?.[0] && importJson(e.target.files[0])} />
        </label>
        <button className="btn primary" type="button" onClick={save}>שמירה</button>
      </div>

      <div className="body body-inspect">
        <div className="preview-wrap">
          <iframe key={iframeKey} ref={iframeRef} src="/preview.html" title="preview"
            className="preview-frame" onLoad={onIframeLoad} />
          {inspect && <div className="inspect-hint">מצב בחירה פעיל — לחץ על אלמנט כדי לערוך. לניווט בין מסכים: כבה "בחירה".</div>}
        </div>

        <div className="panel right">
          {!selSel ? (
            <div className="empty-hint">
              לחץ על כל אלמנט בתצוגת התוכנה כדי לערוך אותו — צבע, גודל, ריווח, פינות,
              מיקום, טקסט והסתרה.<br /><br />
              לניווט בין מסכים (דף הבית / ספרייה / הגדרות): כבה "בחירה", לחץ בסרגל הצד,
              ואז הפעל "בחירה" שוב.
            </div>
          ) : (
            <div>
              <h3 style={{ margin: "0 0 4px" }}>{selInfo?.tag || "אלמנט"}</h3>
              <div className="muted" style={{ fontSize: 10, wordBreak: "break-all", marginBottom: 10 }}>{selSel}</div>

              <label className="field" style={{ display: "flex", alignItems: "center", gap: 8, flexDirection: "row" }}>
                <input type="checkbox" checked={!!cur.hidden} onChange={(e) => setHidden(e.target.checked)} />
                <span style={{ fontSize: 12 }}>הסתר אלמנט</span>
              </label>

              {selInfo?.isLeaf && (
                <div className="field">
                  <label>טקסט</label>
                  <textarea value={typeof cur.text === "string" ? cur.text : (selInfo?.text || "")}
                    onChange={(e) => setText(e.target.value)} />
                </div>
              )}

              <div className="row2">
                <div className="field">
                  <label>רקע</label>
                  <input type="text" value={cur.style?.background ?? ""} placeholder={computed("backgroundColor")}
                    onChange={(e) => setStyle("background", e.target.value)} />
                </div>
                <div className="field">
                  <label>צבע טקסט</label>
                  <input type="text" value={cur.style?.color ?? ""} placeholder={computed("color")}
                    onChange={(e) => setStyle("color", e.target.value)} />
                </div>
              </div>

              <div className="row2">
                <div className="field">
                  <label>גודל גופן</label>
                  <input type="text" value={cur.style?.fontSize ?? ""} placeholder={computed("fontSize")}
                    onChange={(e) => setStyle("fontSize", e.target.value)} />
                </div>
                <div className="field">
                  <label>עובי גופן</label>
                  <select value={cur.style?.fontWeight ?? ""} onChange={(e) => setStyle("fontWeight", e.target.value)}>
                    <option value="">—</option><option value="400">רגיל</option>
                    <option value="600">חצי-מודגש</option><option value="700">מודגש</option><option value="800">שמן</option>
                  </select>
                </div>
              </div>

              <div className="row2">
                <div className="field">
                  <label>ריווח פנימי</label>
                  <input type="text" value={cur.style?.padding ?? ""} placeholder={computed("padding")}
                    onChange={(e) => setStyle("padding", e.target.value)} />
                </div>
                <div className="field">
                  <label>ריווח חיצוני</label>
                  <input type="text" value={cur.style?.margin ?? ""} placeholder={computed("margin")}
                    onChange={(e) => setStyle("margin", e.target.value)} />
                </div>
              </div>

              <div className="row2">
                <div className="field">
                  <label>עיגול פינות</label>
                  <input type="text" value={cur.style?.borderRadius ?? ""} placeholder={computed("borderRadius")}
                    onChange={(e) => setStyle("borderRadius", e.target.value)} />
                </div>
                <div className="field">
                  <label>שקיפות (0-1)</label>
                  <input type="text" value={cur.style?.opacity ?? ""} placeholder={computed("opacity")}
                    onChange={(e) => setStyle("opacity", e.target.value)} />
                </div>
              </div>

              <div className="row2">
                <div className="field">
                  <label>רוחב</label>
                  <input type="text" value={cur.style?.width ?? ""} placeholder={computed("width")}
                    onChange={(e) => setStyle("width", e.target.value)} />
                </div>
                <div className="field">
                  <label>גובה</label>
                  <input type="text" value={cur.style?.height ?? ""} placeholder={computed("height")}
                    onChange={(e) => setStyle("height", e.target.value)} />
                </div>
              </div>

              <div className="field">
                <label>מסגרת</label>
                <input type="text" value={cur.style?.border ?? ""} placeholder={computed("border")}
                  onChange={(e) => setStyle("border", e.target.value)} />
              </div>

              <div className="field">
                <label>יישור טקסט</label>
                <select value={cur.style?.textAlign ?? ""} onChange={(e) => setStyle("textAlign", e.target.value)}>
                  <option value="">—</option><option value="right">ימין</option>
                  <option value="center">מרכז</option><option value="left">שמאל</option>
                </select>
              </div>

              <div className="muted" style={{ fontSize: 11, margin: "10px 0 6px" }}>הזזה חופשית (פיקסלים)</div>
              <div className="row2">
                <div className="field">
                  <label>אופקי (←/→)</label>
                  <input type="number" value={tVal.x || ""} onChange={(e) => setT(Number(e.target.value) || 0, tVal.y)} />
                </div>
                <div className="field">
                  <label>אנכי (↑/↓)</label>
                  <input type="number" value={tVal.y || ""} onChange={(e) => setT(tVal.x, Number(e.target.value) || 0)} />
                </div>
              </div>

              <button className="btn" type="button" style={{ marginTop: 12, width: "100%",
                background: "rgba(224,86,124,.15)", borderColor: "rgba(224,86,124,.5)", color: "#f0a8be" }}
                onClick={resetEl}>בטל שינויים לאלמנט זה</button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
