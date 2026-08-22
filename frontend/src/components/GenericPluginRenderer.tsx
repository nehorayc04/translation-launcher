// GenericPluginRenderer - draws ANY declarative cloud-plugin UI.
//
// A plugin ships a `ui` manifest (a tree of nodes) + calls audited primitives via
// api.pluginAction. This renderer walks the tree and renders it with the launcher
// design system, so NEW plugin UI (and new save/file-domain plugins) reach users
// with NO app rebuild. It runs no plugin code - every button action is a named
// primitive the bundled Python engine executes safely.
import { useEffect, useState } from "react";
import type { CSSProperties, SVGProps, ComponentType, ReactNode } from "react";
import { api, type PluginUiNode } from "../lib/eel";
import {
  IconOptSectionBackedSaves, IconAppPluginsBtnAutodetect, IconAppPluginsBtnBackupNow,
  IconAppPluginsBtnOpenFolder, IconOptBtnRemoveEntry, IconOptBtnAddDetected,
  IconOptBtnBrowseFolder, IconOptSectionBackupHistory, IconOptBtnRestoreBackup,
  IconOptBtnControllerReset,
} from "./UiIcons";

type Report = (text: string, warn?: boolean) => void;
type IconCmp = ComponentType<SVGProps<SVGSVGElement>>;

// Icon slot-id → component (explicit map so tree-shaking keeps only what's used).
const ICONS: Record<string, IconCmp> = {
  "opt-section-backed-saves": IconOptSectionBackedSaves,
  "app-plugins-btn-autodetect": IconAppPluginsBtnAutodetect,
  "app-plugins-btn-backup-now": IconAppPluginsBtnBackupNow,
  "app-plugins-btn-open-folder": IconAppPluginsBtnOpenFolder,
  "opt-btn-remove-entry": IconOptBtnRemoveEntry,
  "opt-btn-add-detected": IconOptBtnAddDetected,
  "opt-btn-browse-folder": IconOptBtnBrowseFolder,
  "opt-section-backup-history": IconOptSectionBackupHistory,
  "opt-btn-restore-backup": IconOptBtnRestoreBackup,
  "opt-btn-reset": IconOptBtnControllerReset,
};

type Scope = Record<string, unknown>;
type UbiGame = { number: string; path: string; name: string; added: boolean };
type UbiAccount = {
  account: string; accountShort: string; label: string; path: string;
  games: UbiGame[]; gamesCount: number; addedCount: number; allAdded: boolean;
};

const PencilIcon = (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 20h9" /><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z" />
  </svg>
);

// ── tiny, safe scope helpers (NO eval, NO arbitrary JS) ──
function getPath(scope: Scope, key: string): unknown {
  return key.split(".").reduce<unknown>(
    (o, k) => (o && typeof o === "object" ? (o as Record<string, unknown>)[k] : undefined),
    scope,
  );
}
function interp(tpl: string, scope: Scope): string {
  return tpl.replace(/\{\{([\w.]+)\}\}/g, (_, k) => {
    const v = getPath(scope, k);
    return v == null ? "" : String(v);
  });
}
function truthy(scope: Scope, expr?: string): boolean {
  if (!expr) return true;
  const neg = expr.startsWith("!");
  const v = getPath(scope, neg ? expr.slice(1) : expr);
  const t = Array.isArray(v) ? v.length > 0 : !!v;
  return neg ? !t : t;
}
function resolveArgs(args: unknown, scope: Scope): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  if (!args || typeof args !== "object") return out;
  for (const [k, v] of Object.entries(args as Record<string, unknown>)) {
    if (typeof v === "string") out[k] = interp(v, scope);
    else if (v && typeof v === "object" && "$bind" in (v as object))
      out[k] = getPath(scope, String((v as Record<string, unknown>).$bind)) ?? [];
    else out[k] = v;
  }
  return out;
}

export default function GenericPluginRenderer({
  pluginId, ui, state: initialState, accent, reportStatus,
}: {
  pluginId: string;
  ui: PluginUiNode[];
  state: Record<string, unknown>;
  accent: string;
  reportStatus?: Report;
}) {
  const [state, setState] = useState<Record<string, unknown>>(initialState);
  const [local, setLocal] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());   // open Ubisoft accounts
  const [editing, setEditing] = useState<{ key: string; value: string } | null>(null); // inline rename
  // Re-seed when the parent reloads the plugin (e.g. after install/enable).
  useEffect(() => { setState(initialState); }, [initialState]);

  const accentBtn = (b: number): CSSProperties =>
    ({ background: `${accent}22`, border: `1px solid ${accent}${b}`, color: accent });

  // Fire an action directly (used by the Ubisoft tree + inline rename, which
  // aren't plain manifest buttons). Same result handling as runAction.
  const doAction = async (action: string, args: Record<string, unknown>) => {
    setBusy(action);
    try {
      let r = await api.pluginAction(pluginId, action, args);
      // A result may ask to CONFIRM before doing anything (e.g. adding a huge
      // save folder whose backup would weigh tens of GB). The engine returns
      // `confirm` and does NOT act; on OK we re-call with confirmed:true.
      const confirmMsg = (r as { confirm?: string }).confirm;
      if (confirmMsg && !args.confirmed) {
        if (!window.confirm(confirmMsg)) return r;      // user declined → do nothing
        r = await api.pluginAction(pluginId, action, { ...args, confirmed: true });
      }
      if (r.state) setState(r.state);
      if (r.status) reportStatus?.(r.status, !r.ok);
      return r;
    } catch { reportStatus?.("הפעולה נכשלה", true); return { ok: false }; }
    finally { setBusy(null); }
  };

  const runAction = async (node: PluginUiNode, scope: Scope) => {
    if (!node.action) return;
    if (node.confirm && !window.confirm(interp(node.confirm, scope))) return;
    setBusy(node.action);
    try {
      const args = resolveArgs(node.args, scope);
      const r = await api.pluginAction(pluginId, node.action, args);
      if (r.state) setState(r.state);
      if (r.status) reportStatus?.(r.status, !r.ok);
      const then = (node as { then?: { setLocalFrom?: Record<string, string>; clearLocal?: string[] } }).then;
      if (then?.setLocalFrom) {
        const rr = r as unknown as Record<string, unknown>;
        setLocal((l) => {
          const n = { ...l };
          for (const [k, f] of Object.entries(then.setLocalFrom!)) {
            const v = rr[f];
            // Only overwrite when the action returned a value. A cancelled folder
            // picker returns "" - keep whatever the user had typed instead of
            // wiping it.
            if (v != null && String(v) !== "") n[k] = String(v);
          }
          return n;
        });
      }
      if (then?.clearLocal) setLocal((l) => {
        const n = { ...l }; then.clearLocal!.forEach((k) => { n[k] = ""; }); return n;
      });
    } catch { reportStatus?.("הפעולה נכשלה", true); }
    finally { setBusy(null); }
  };

  const fieldChange = async (node: PluginUiNode, value: string | number) => {
    if (!node.action || !node.bind) return;
    const args = node.control === "number"
      ? { key: node.bind, value }
      : { value };
    try {
      const r = await api.pluginAction(pluginId, node.action, args);
      if (r.state) setState(r.state);
      if (r.status) reportStatus?.(r.status, !r.ok);
    } catch { reportStatus?.("הפעולה נכשלה", true); }
  };

  const IconOf = (name?: string, w = 16) => {
    const C = name ? ICONS[name] : undefined;
    return C ? <C width={w} className="shrink-0 opacity-90" /> : null;
  };

  const renderButton = (node: PluginUiNode, scope: Scope, key: string) => {
    if (!truthy(scope, node.visibleWhen)) return null;
    const disabled = busy !== null || (!!node.disabledWhen && truthy(scope, node.disabledWhen));
    const running = busy === node.action && node.busyLabel;
    const label = running ? node.busyLabel : (node.label ? interp(node.label, scope) : "");
    const v = node.variant || "primary";
    const cls: Record<string, string> = {
      primary: "text-xs px-3 py-1.5 rounded-lg font-bold disabled:opacity-40 inline-flex items-center gap-1.5",
      primarySm: "text-xs px-2.5 py-1 rounded-lg font-semibold shrink-0 disabled:opacity-40 inline-flex items-center gap-1.5",
      ghost: "text-xs px-3 py-1.5 rounded-lg bg-white/[0.06] hover:bg-white/[0.1] text-slate-200 disabled:opacity-40 inline-flex items-center gap-1.5",
      danger: "text-xs text-rose-300/80 hover:text-rose-200 shrink-0 disabled:opacity-40 inline-flex items-center gap-1",
      warn: "text-xs px-2.5 py-1 rounded-lg font-semibold text-amber-200 border border-amber-400/40 hover:bg-amber-400/10 shrink-0 disabled:opacity-40 inline-flex items-center gap-1.5",
      icon: "text-xs text-slate-400 hover:text-slate-200 shrink-0 disabled:opacity-40",
    };
    const style = v === "primary" || v === "primarySm" ? accentBtn(66) : undefined;
    return (
      <button key={key} type="button" disabled={disabled} style={style}
        onClick={() => void runAction(node, scope)} className={cls[v] || cls.primary}>
        {IconOf(node.icon, v === "icon" || v === "danger" ? 15 : 16)}{label}
      </button>
    );
  };

  const renderField = (node: PluginUiNode, key: string) => {
    const val = getPath(state, node.bind || "");
    if (node.control === "select") {
      const opts = (getPath(state, node.optionsBind || "") as { value: string; label: string }[]) || [];
      return (
        <label key={key} className="block">
          <span className="text-xs text-slate-400">{node.label}</span>
          <div className="relative mt-1">
            <select value={String(val ?? "")} onChange={(e) => void fieldChange(node, e.target.value)}
              className="appearance-none w-full bg-black/40 border border-white/10 rounded-lg pr-3 pl-9 py-2 text-sm text-white cursor-pointer">
              {opts.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
            <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2" style={{ color: accent }}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={3.2} strokeLinecap="round" strokeLinejoin="round"><path d="m6 9 6 6 6-6" /></svg>
            </span>
          </div>
        </label>
      );
    }
    // number
    const min = node.min ?? 1, max = node.max ?? 100;
    return (
      <label key={key} className="block">
        <span className="text-xs text-slate-400">{node.label}</span>
        <input type="number" min={min} max={max} value={Number(val ?? min)}
          onChange={(e) => {
            // Ignore an EMPTY field (mid-edit clear-and-retype) - committing it
            // would coerce to `min` (0 = unlimited for "keep") and silently turn
            // rotation off. Persist only a real number the user actually typed.
            const raw = e.target.value;
            if (raw === "") return;
            const num = Number(raw);
            if (!Number.isFinite(num)) return;
            void fieldChange(node, Math.max(min, Math.min(max, num)));
          }}
          className="mt-1 w-full bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-sm text-white" />
      </label>
    );
  };

  const renderInput = (node: PluginUiNode, key: string, scope: Scope) => {
    const lk = (node.bind || "").replace(/^local\./, "");
    const style: CSSProperties = {};
    if (node.width) style.width = node.width;
    const flexCls = node.flex === 2 ? "flex-[2] min-w-[180px]" : node.flex === 1 ? "flex-1 min-w-[120px]" : "";
    // The placeholder is a TEMPLATE like any other label - without interpolating
    // it the user literally reads "{{base}}" in the box (a real shipped bug).
    const ph = node.placeholder ? interp(node.placeholder, scope) : undefined;
    return (
      <input key={key} value={local[lk] || ""} placeholder={ph} dir={node.dir as "ltr" | "rtl" | undefined}
        onChange={(e) => setLocal((l) => ({ ...l, [lk]: e.target.value }))} style={style}
        className={`${flexCls || "w-40"} bg-black/40 border border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-white`} />
    );
  };

  const commitEdit = (action: string, args: Record<string, unknown>) =>
    void doAction(action, args).then(() => setEditing(null));

  const renderList = (node: PluginUiNode, scope: Scope, key: string) => {
    const arr = (getPath(scope, node.bind || "") as Record<string, unknown>[]) || [];
    const it = node.item || {};
    const style: CSSProperties = node.maxHeight ? { maxHeight: node.maxHeight, overflowY: "auto" } : {};
    return (
      <ul key={key} className="space-y-1.5" style={style}>
        {arr.map((item, i) => {
          const isc: Scope = { ...state, ...item, local };
          const editKey = `entry:${String(item.id ?? i)}`;
          const isEditing = !!it.editableAction && editing?.key === editKey;
          return (
            <li key={String(item.id ?? item.path ?? i)} className="flex items-center gap-2 rounded-lg bg-black/30 px-3 py-2">
              <span className="flex-1 min-w-0">
                {isEditing ? (
                  <input autoFocus value={editing!.value}
                    onChange={(e) => setEditing({ key: editKey, value: e.target.value })}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") commitEdit(it.editableAction!, { id: item.id, label: editing!.value });
                      if (e.key === "Escape") setEditing(null);
                    }}
                    className="w-full bg-black/50 border border-white/20 rounded px-2 py-1 text-sm text-white" />
                ) : (
                  <>
                    {it.text && <span className="text-sm text-white block truncate">{interp(it.text, isc)}</span>}
                    {/* The subtext is LTR by default because it started life as a
                        file PATH - but a Hebrew status line ("לא הוגדר") rendered
                        LTR pushes its punctuation to the wrong side. Opt in per list. */}
                    {it.subtext && <span className="text-[11px] text-slate-500 block truncate"
                      dir={it.subtextDir === "rtl" ? "rtl" : "ltr"}>{interp(it.subtext, isc)}</span>}
                  </>
                )}
              </span>
              {it.badge && !isEditing && <span className="text-[10px] text-slate-500 shrink-0">{interp(it.badge, isc)}</span>}
              {it.editableAction && (isEditing ? (
                <button type="button" title="שמור" style={{ color: accent }} className="text-xs shrink-0"
                  onClick={() => commitEdit(it.editableAction!, { id: item.id, label: editing!.value })}>✓</button>
              ) : (
                <button type="button" title="שנה שם" className="text-slate-400 hover:text-slate-200 shrink-0"
                  onClick={() => setEditing({ key: editKey, value: String(item.label ?? interp(it.text || "", isc)) })}>{PencilIcon}</button>
              ))}
              {!isEditing && (it.buttons || []).map((b, bi) => renderButton(b, isc, `${key}_${i}_${bi}`))}
            </li>
          );
        })}
      </ul>
    );
  };

  const renderUbiTree = (node: PluginUiNode, key: string) => {
    const accounts = (getPath(state, node.bind || "ubisoftAccounts") as UbiAccount[]) || [];
    if (!accounts.length) return null;
    return (
      <div key={key}>
        <div className="text-sm font-semibold text-slate-200 mb-2 inline-flex items-center gap-1.5">
          {IconOf(node.icon, 20)}{node.title ? interp(node.title, state) : "יוביסופט"}
        </div>
        <div className="space-y-1.5">
          {accounts.map((acc) => {
            const open = expanded.has(acc.account);
            const editKey = `acct:${acc.account}`;
            const isEditing = editing?.key === editKey;
            return (
              <div key={acc.account} className="rounded-xl border border-white/10 bg-black/20">
                <div className="flex items-center gap-2 px-3 py-2">
                  <button type="button" title={open ? "כווץ" : "הרחב"} className="text-slate-400 hover:text-slate-200 shrink-0"
                    onClick={() => setExpanded((s) => { const n = new Set(s); if (open) n.delete(acc.account); else n.add(acc.account); return n; })}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={3} strokeLinecap="round" strokeLinejoin="round"
                      style={{ transform: open ? "rotate(90deg)" : "none", transition: "transform .15s" }}><path d="m9 6 6 6-6 6" /></svg>
                  </button>
                  <span className="flex-1 min-w-0">
                    {isEditing ? (
                      <input autoFocus value={editing!.value}
                        onChange={(e) => setEditing({ key: editKey, value: e.target.value })}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") commitEdit("rename_account", { account: acc.account, name: editing!.value });
                          if (e.key === "Escape") setEditing(null);
                        }}
                        className="w-full bg-black/50 border border-white/20 rounded px-2 py-1 text-sm text-white" />
                    ) : (
                      <span className="text-sm text-white truncate inline-flex items-center gap-1.5">
                        {IconOf("app-plugins-btn-open-folder", 14)}{acc.label}
                      </span>
                    )}
                  </span>
                  <span className="text-[10px] text-slate-500 shrink-0">{acc.addedCount}/{acc.gamesCount}</span>
                  {isEditing ? (
                    <button type="button" title="שמור" style={{ color: accent }} className="text-xs shrink-0"
                      onClick={() => commitEdit("rename_account", { account: acc.account, name: editing!.value })}>✓</button>
                  ) : (
                    <>
                      <button type="button" title="שנה שם משתמש" className="text-slate-400 hover:text-slate-200 shrink-0"
                        onClick={() => setEditing({ key: editKey, value: acc.label })}>{PencilIcon}</button>
                      <button type="button" disabled={busy !== null || acc.allAdded} style={accentBtn(66)}
                        onClick={() => void doAction("add_ubi_account", { account: acc.account })}
                        className="text-xs px-2.5 py-1 rounded-lg font-semibold shrink-0 disabled:opacity-40 inline-flex items-center gap-1.5">
                        {IconOf("opt-btn-add-detected", 15)}הוסף חשבון
                      </button>
                    </>
                  )}
                </div>
                {open && (
                  <ul className="px-3 pb-2 pt-2 space-y-1 border-t border-white/5">
                    {acc.games.map((g) => (
                      <li key={g.path} className="flex items-center gap-2 pr-5">
                        <span className="flex-1 min-w-0">
                          <span className="text-[13px] text-slate-200 block truncate">{g.name}</span>
                          <span className="text-[10px] text-slate-500 block truncate" dir="ltr">{g.path}</span>
                        </span>
                        {g.added ? (
                          <span className="text-[11px] text-emerald-300 shrink-0">✓ נוסף</span>
                        ) : (
                          <button type="button" disabled={busy !== null} style={accentBtn(55)}
                            onClick={() => void doAction("add_ubi_game", { account: acc.account, number: g.number, path: g.path, gameName: g.name })}
                            className="text-xs px-2.5 py-1 rounded-lg font-semibold shrink-0 disabled:opacity-40 inline-flex items-center gap-1.5">
                            {IconOf("opt-btn-add-detected", 15)}הוסף
                          </button>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  // ── HERO: the one status line + the one switch that matters, given the top of
  // the page instead of being a button in a stack of identical grey boxes.
  const renderHero = (node: PluginUiNode, scope: Scope, key: string) => {
    const t = node.toggle;
    const on = t ? !!getPath(scope, t.bind || "") : false;
    const blocked = !!t?.disabledWhen && truthy(scope, t.disabledWhen);
    return (
      <div key={key} className="rounded-2xl p-5 flex items-center gap-5 flex-wrap"
        style={{ background: `linear-gradient(120deg, ${accent}1f 0%, transparent 70%)`,
                 border: `1px solid ${accent}33` }}>
        <div className="flex-1 min-w-[220px]">
          <div className="text-lg font-bold text-white">{node.title ? interp(node.title, scope) : ""}</div>
          {node.subtitle && <p className="text-[13px] text-slate-400 mt-1">{interp(node.subtitle, scope)}</p>}
        </div>
        <div className="flex items-center gap-3 shrink-0">
          {(node.children || []).map((c, i) => renderNode(c, `${key}_a${i}`, scope))}
          {t && (
            <button type="button" role="switch" aria-checked={on}
              disabled={busy !== null || blocked}
              title={blocked ? (t.blockedHint || "") : undefined}
              onClick={() => void runAction({ type: "button", action: t.action, args: { value: !on } }, scope)}
              className="inline-flex items-center gap-2.5 disabled:opacity-40">
              <span className="text-sm font-bold" style={{ color: on ? accent : "#94a3b8" }}>
                {on ? (t.onLabel || "פעיל") : (t.offLabel || "כבוי")}
              </span>
              <span className="relative w-[54px] h-[30px] rounded-full transition-colors duration-200"
                style={{ background: on ? accent : "rgba(255,255,255,.12)",
                         boxShadow: on ? `0 0 16px ${accent}66` : "none" }}>
                <span className="absolute top-[3px] w-6 h-6 rounded-full bg-white transition-all duration-200"
                  style={{ left: on ? 27 : 3 }} />
              </span>
            </button>
          )}
        </div>
      </div>
    );
  };

  // ── CARDS: one rich card per data row - title + status chip + its OWN paste
  // field + buttons + a fold-out step-by-step guide. A `list` row is a single
  // line, so anything that needs a per-row INPUT (an API key per provider) had to
  // share one field + a dropdown: the user then had to pick the right provider by
  // hand and could silently save a Groq key under SambaNova. A field per card
  // removes the choice entirely.
  const renderCards = (node: PluginUiNode, scope: Scope, key: string) => {
    const arr = (getPath(scope, node.bind || "") as Record<string, unknown>[]) || [];
    const c = node.card || {};
    return (
      <div key={key} className="space-y-2">
        {arr.map((item, i) => {
          // The input's bind is a TEMPLATE (`local.k_{{id}}`) so every card owns a
          // separate box; `inputValue` is injected into the row scope so a button
          // can read it without a nested {{ }} interpolation.
          const lk = c.input ? interp(c.input.bind || "", item as Scope).replace(/^local\./, "") : "";
          const val = local[lk] || "";
          const isc: Scope = { ...state, ...item, local, inputValue: val };
          const gKey = `${key}_g${i}`;
          const open = expanded.has(gKey);
          const shown = expanded.has(`${gKey}_eye`);
          const steps = (getPath(isc, c.steps?.bind || "") as string[]) || [];
          // A chip with NO condition stays neutral - `truthy(undefined)` is true,
          // which would paint every chip green ("✓ saved") including the empty ones.
          const ok = !!c.chipWhen && truthy(isc, c.chipWhen);
          return (
            <div key={String(item.id ?? i)} className="rounded-xl border border-white/10 bg-black/20 px-4 py-3">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-sm font-bold text-white">{interp(c.title || "", isc)}</span>
                {c.chip && (
                  <span className="text-[11px] px-2 py-0.5 rounded-full font-semibold"
                    style={ok ? { color: "#86efac", border: "1px solid #86efac55" }
                              : { color: "#94a3b8", border: "1px solid #94a3b855" }}>
                    {interp(c.chip, isc)}
                  </span>
                )}
              </div>
              {c.note && <p className="text-[12px] text-slate-500 mt-0.5">{interp(c.note, isc)}</p>}

              <div className="flex items-center gap-2 mt-2 flex-wrap">
                {c.input && (
                  <div className="relative flex-1 min-w-[200px]">
                    <input value={val} dir={c.input.dir as "ltr" | "rtl" | undefined}
                      type={c.input.secret && !shown ? "password" : "text"}
                      placeholder={c.input.placeholder ? interp(c.input.placeholder, isc) : undefined}
                      onChange={(e) => setLocal((l) => ({ ...l, [lk]: e.target.value }))}
                      className="w-full bg-black/40 border border-white/10 rounded-lg pr-2.5 pl-8 py-1.5 text-xs text-white" />
                    {c.input.secret && (
                      <button type="button" title={shown ? "הסתר" : "הצג"}
                        onClick={() => setExpanded((s) => { const n = new Set(s); const k2 = `${gKey}_eye`; if (n.has(k2)) n.delete(k2); else n.add(k2); return n; })}
                        className="absolute left-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200">
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}
                          strokeLinecap="round" strokeLinejoin="round">
                          <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7-10-7-10-7Z" /><circle cx="12" cy="12" r="3" />
                          {!shown && <path d="m3 3 18 18" />}
                        </svg>
                      </button>
                    )}
                  </div>
                )}
                {/* Buttons sit AFTER the field in the DOM → left of it in RTL. */}
                {(c.buttons || []).map((b, bi) => renderButton(
                  // `clearInput` is resolved here because only the renderer knows
                  // this row's local key name.
                  b.clearInput ? { ...b, then: { ...(b.then || {}), clearLocal: [lk] } } : b,
                  isc, `${gKey}_b${bi}`))}
              </div>

              {c.steps && steps.length > 0 && (
                <>
                  <button type="button" aria-expanded={open}
                    onClick={() => setExpanded((s) => { const n = new Set(s); if (open) n.delete(gKey); else n.add(gKey); return n; })}
                    className="mt-2 inline-flex items-center gap-1.5 text-[11px] text-slate-400 hover:text-slate-200">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.6}
                      strokeLinecap="round" strokeLinejoin="round" className="transition-transform duration-200"
                      style={{ transform: open ? "rotate(180deg)" : "none" }}><path d="m6 9 6 6 6-6" /></svg>
                    {c.steps.title || "איך משיגים מפתח?"}
                  </button>
                  {open && (
                    <ol className="mt-2 space-y-1.5 border-t border-white/5 pt-2">
                      {steps.map((s, si) => (
                        <li key={si} className="flex gap-2 items-start">
                          <span className="text-[10px] font-bold w-[18px] h-[18px] rounded-full shrink-0 mt-[1px] inline-flex items-center justify-center"
                            style={{ background: `${accent}22`, color: accent }}>{si + 1}</span>
                          <span className="text-[12px] text-slate-300 leading-relaxed">{s}</span>
                        </li>
                      ))}
                    </ol>
                  )}
                </>
              )}
            </div>
          );
        })}
      </div>
    );
  };

  // ── STATS: equal tiles, one number each. A number needs a tile, not a paragraph.
  const renderStats = (node: PluginUiNode, scope: Scope, key: string) => (
    <div key={key} className="grid grid-cols-2 sm:grid-cols-3 gap-3">
      {(node.items || []).map((it, i) => (
        <div key={i} className="rounded-xl border border-white/10 bg-black/20 px-4 py-3">
          <div className="text-[11px] text-slate-500">{interp(it.label || "", scope)}</div>
          <div className="text-2xl font-extrabold mt-0.5 truncate"
            style={it.tone === "accent" ? { color: accent } : undefined}>
            {interp(it.value || "", scope)}
          </div>
          {it.caption && <div className="text-[11px] text-slate-500 mt-0.5 truncate">{interp(it.caption, scope)}</div>}
        </div>
      ))}
    </div>
  );

  // ── COLLAPSE: the technical settings a volunteer must never have to read are
  // present but folded away, so the page is short by default.
  const renderCollapse = (node: PluginUiNode, scope: Scope, key: string) => {
    const open = !!expanded.has(key);
    return (
      <div key={key} className="rounded-xl border border-white/10 bg-black/20 overflow-hidden">
        <button type="button" aria-expanded={open}
          onClick={() => setExpanded((s) => { const n = new Set(s); if (open) n.delete(key); else n.add(key); return n; })}
          className="w-full flex items-center gap-2 px-4 py-3 text-right hover:bg-white/[0.03] transition-colors">
          <span className="flex-1 text-xs font-semibold text-slate-300">{node.title ? interp(node.title, scope) : ""}</span>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.6}
            strokeLinecap="round" strokeLinejoin="round" className="text-slate-400 transition-transform duration-200"
            style={{ transform: open ? "rotate(180deg)" : "none" }}><path d="m6 9 6 6 6-6" /></svg>
        </button>
        {open && <div className="px-4 pb-4 space-y-2">{(node.children || []).map((c, i) => renderNode(c, `${key}_c${i}`, scope))}</div>}
      </div>
    );
  };

  const renderNode = (node: PluginUiNode, key: string, scope: Scope): ReactNode => {
    if (!truthy(scope, node.visibleWhen)) return null;
    switch (node.type) {
      case "hero":
        return renderHero(node, scope, key);
      case "stats":
        return renderStats(node, scope, key);
      case "cards":
        return renderCards(node, scope, key);
      case "collapse":
        return renderCollapse(node, scope, key);
      case "grid2":
        return <div key={key} className="grid sm:grid-cols-2 gap-3">{(node.children || []).map((c, i) => renderNode(c, `${key}_${i}`, scope))}</div>;
      case "row":
        return <div key={key} className="flex gap-2 flex-wrap">{(node.children || []).map((c, i) => renderNode(c, `${key}_${i}`, scope))}</div>;
      case "field":
        return renderField(node, key);
      case "input":
        return renderInput(node, key, scope);
      case "button":
        return renderButton(node, scope, key);
      case "text": {
        // `size`/`tone` let a manifest build a real stat card (a big accent number
        // over a muted caption) instead of two identical grey lines.
        const size = (node as { size?: string }).size;
        const tone = (node as { tone?: string }).tone;
        const cls = size === "xl" ? "text-3xl font-extrabold leading-tight"
          : size === "lg" ? "text-lg font-bold"
          : node.muted ? "text-[13px] text-slate-500 py-1 break-all"
          : "text-sm text-slate-300";
        const st: CSSProperties = tone === "accent" ? { color: accent } : {};
        return <p key={key} dir={node.dir === "ltr" ? "ltr" : undefined} style={st}
          className={cls}>{node.value ? interp(node.value, scope) : String(getPath(scope, node.bind || "") ?? "")}</p>;
      }
      case "list":
        return renderList(node, scope, key);
      case "ubitree":
        return renderUbiTree(node, key);
      case "section": {
        const ha = (node as { headerActions?: PluginUiNode[] }).headerActions;
        return (
          <div key={key}>
            <div className="flex items-center justify-between mb-2 gap-2 flex-wrap">
              <span className="text-sm font-semibold text-slate-200 inline-flex items-center gap-1.5">
                {IconOf(node.icon, 20)}{node.title ? interp(node.title, scope) : ""}
              </span>
              {ha && ha.length > 0 && (
                <div className="flex gap-2 items-center flex-wrap">
                  {ha.map((c, i) => renderNode(c, `${key}_ha_${i}`, scope))}
                </div>
              )}
            </div>
            {(node.children || []).map((c, i) => renderNode(c, `${key}_c_${i}`, scope))}
          </div>
        );
      }
      case "box": {
        const hdr = (node as { header?: { text?: string; button?: PluginUiNode } }).header;
        return (
          <div key={key} className="rounded-xl border border-white/10 bg-black/20 p-3">
            {hdr ? (
              <div className="flex items-center justify-between gap-2 mb-2">
                <span className="text-xs font-semibold text-slate-300">{hdr.text ? interp(hdr.text, scope) : ""}</span>
                {hdr.button && renderButton(hdr.button, scope, `${key}_hb`)}
              </div>
            ) : node.title ? (
              <div className="text-xs font-semibold text-slate-300 mb-2">{interp(node.title, scope)}</div>
            ) : null}
            <div className="space-y-1.5">
              {(node.children || []).map((c, i) => renderNode(c, `${key}_c_${i}`, scope))}
            </div>
          </div>
        );
      }
      default:
        return null;
    }
  };

  const scope: Scope = { ...state, local };
  return (
    <div className="border-t border-white/5 px-5 py-4 space-y-5" style={{ background: `${accent}08` }}>
      {ui.map((n, i) => renderNode(n, `n${i}`, scope))}
    </div>
  );
}
