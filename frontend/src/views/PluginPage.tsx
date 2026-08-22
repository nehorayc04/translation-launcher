// A single installed plugin as its OWN full-screen view - the same shape as a
// game/software detail page: the manager (תוספים) is a GRID of cards, a click
// opens this page.
//
// Why not an accordion in the manager: expanding every plugin's settings inline
// made the list grow with each plugin and buried the one you came for under the
// rest. A card grid stays scannable and a plugin gets a whole page to itself.
//
// It renders the SAME declarative manifest the manager used to render (via the
// shared DeclarativePluginBody), so a plugin's UI is defined in exactly one place
// and a manifest-less plugin keeps its built-in fallback panel.
import { useCallback, useEffect, useState } from "react";
import { api, type PluginMeta } from "../lib/eel";
import { DeclarativePluginBody } from "../components/PluginsSettings";
import { IconNavPlugins, IconOptBtnDisableTranslation, IconOptBtnPluginDownload } from "../components/UiIcons";
import { shortName } from "../lib/pluginName";

type Report = (text: string, warn?: boolean) => void;

export default function PluginPage({
  pluginId, reportStatus, onOpenManager,
}: {
  pluginId: string;
  reportStatus?: Report;
  onOpenManager: () => void;
}) {
  const [meta, setMeta] = useState<PluginMeta | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const snap = await api.getPlugins();
      setMeta((snap.plugins ?? []).find((x) => x.id === pluginId) ?? null);
    } catch { /* keep whatever we have - a blip must not blank the page */ }
    finally { setLoaded(true); }
  }, [pluginId]);

  useEffect(() => {
    setLoaded(false);
    void load();
    // The manager (and this page) fire `pluginschanged` on install/toggle, so a
    // change made on the other screen is reflected here without a reload.
    const onChanged = () => void load();
    window.addEventListener("pluginschanged", onChanged);
    return () => window.removeEventListener("pluginschanged", onChanged);
  }, [load]);

  const accent = meta?.accent ?? "#a78bfa";
  const gone = loaded && (!meta || !meta.installed);

  const update = async () => {
    if (!meta) return;
    setBusy(true);
    try {
      const r = await api.updatePlugin(meta.id);
      const added = r.addedSettings?.length ?? 0;
      reportStatus?.(r.ok
        ? `עודכן לגרסה ${r.version ?? ""}${added ? ` · ${added} הגדרות חדשות` : ""}`
        : "העדכון נכשל", !r.ok);
      window.dispatchEvent(new CustomEvent("pluginschanged"));
      await load();
    } finally { setBusy(false); }
  };

  const toggle = async () => {
    if (!meta) return;
    setBusy(true);
    try {
      const on = !meta.enabled;
      const r = await api.setPluginEnabled(meta.id, on);
      reportStatus?.(r.ok ? (on ? "התוסף הופעל" : "התוסף כובה") : "הפעולה נכשלה", !r.ok);
      window.dispatchEvent(new CustomEvent("pluginschanged"));
      await load();
    } finally { setBusy(false); }
  };

  return (
    <div className="h-full overflow-y-auto px-8 py-6 animate-fade-in">
      <section className="space-y-5">
        <button type="button" onClick={onOpenManager}
          className="text-xs text-slate-400 hover:text-slate-200 transition-colors">
          → חזרה לתוספים
        </button>

        <header className="animate-rise text-right flex items-start gap-4 flex-wrap">
          <div className="flex-1 min-w-0">
            <h1 className="text-3xl font-extrabold inline-flex items-center gap-2">
              {meta?.icon
                ? <span className="text-[26px] leading-none">{meta.icon}</span>
                : <IconNavPlugins width={22} className="shrink-0 opacity-90" style={{ color: accent }} />}
              <span className="text-gradient-accent" style={{ ["--pg-accent" as string]: accent }}>
                {shortName(meta?.name)}
              </span>
            </h1>
            {meta?.tagline && <p className="text-sm text-slate-400 mt-1">{meta.tagline}</p>}
            {meta?.description && (
              <p className="text-[13px] text-slate-500 mt-2 leading-relaxed max-w-3xl whitespace-pre-line">
                {meta.description}
              </p>
            )}
          </div>

          {/* The on/off control lives HERE, next to the thing it controls - the
              manager card only decides whether the plugin exists on this machine. */}
          {meta?.installed && (
            <div className="flex items-center gap-2 shrink-0 flex-wrap justify-end">
              {meta.version && (
                <span className="text-[11px] text-slate-500">
                  v{meta.updateAvailable ? meta.installedVersion : meta.version}
                </span>
              )}
              {/* An update needs NO app rebuild: the manifest is already read live
                  from the catalog; this adopts the version stamp + any setting a
                  newer version added. */}
              {meta.updateAvailable && (
                <button type="button" disabled={busy} onClick={() => void update()}
                  className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl text-sm font-bold text-emerald-200 border border-emerald-400/40 hover:bg-emerald-400/10 disabled:opacity-40">
                  <IconOptBtnPluginDownload width={17} className="shrink-0 opacity-90" />
                  {busy ? "…" : `עדכון ל-${meta.version}`}
                </button>
              )}
              <span className="text-[11px] px-2 py-0.5 rounded-full font-semibold"
                style={{ color: meta.enabled ? "#86efac" : "#94a3b8",
                         border: `1px solid ${meta.enabled ? "#86efac55" : "#94a3b855"}` }}>
                {meta.enabled ? "פעיל" : "כבוי"}
              </span>
              <button type="button" disabled={busy} onClick={() => void toggle()}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm font-bold transition disabled:opacity-40"
                style={meta.enabled
                  ? { background: "rgba(255,255,255,.06)", color: "#cbd5e1" }
                  : { background: `${accent}26`, border: `1px solid ${accent}66`, color: accent }}>
                {meta.enabled
                  ? <IconOptBtnDisableTranslation width={18} className="shrink-0 opacity-90" />
                  : <IconOptBtnPluginDownload width={18} className="shrink-0 opacity-90" />}
                {busy ? "…" : meta.enabled ? "השבת" : "הפעלה"}
              </button>
            </div>
          )}
        </header>

        {gone ? (
          <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-6 text-slate-300">
            <div className="font-bold text-white mb-1">התוסף אינו מותקן</div>
            <p className="text-sm text-slate-400">אפשר להתקין אותו מחדש מעמוד התוספים.</p>
            <button type="button" onClick={onOpenManager}
              className="mt-3 text-sm font-semibold underline" style={{ color: accent }}>
              מעבר לתוספים ←
            </button>
          </div>
        ) : !loaded ? (
          <div className="text-sm text-slate-500 animate-pulse">טוען…</div>
        ) : meta && !meta.enabled ? (
          <div className="rounded-2xl border border-amber-400/30 bg-amber-400/[0.06] p-5 text-sm text-slate-300">
            התוסף כבוי. הפעילו אותו כדי להשתמש בו.
          </div>
        ) : meta ? (
          <div className="rounded-2xl border border-white/10 bg-slate-900/50 overflow-hidden">
            <DeclarativePluginBody plugin={meta} reportStatus={reportStatus} />
          </div>
        ) : null}
      </section>
    </div>
  );
}
