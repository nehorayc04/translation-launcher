// Settings — app info, lifecycle toggles, custom game paths.
//
// Lifecycle toggles bind directly to the launcher_prefs.json + Windows
// HKCU autostart registry entry through the eel bridge. The version
// string is fed in from APP_VERSION (locked at v1.1.0) so the small
// label at the sidebar footer and the "על האפליקציה" block stay in
// lockstep.
import { useEffect, useState, type ReactNode } from "react";
import type { Game, LauncherPrefs } from "../lib/types";
import { api, type UpdatePrefs } from "../lib/eel";
import {
  getAnims, setAnims, getDensity, setDensity, getAccent, setAccentPref,
  getRainbow, setRainbow, getSidebarMode, setSidebarMode, type SidebarMode,
  getSounds, setSounds, type Density,
} from "../lib/themePrefs";
import { useAccentSetter } from "../lib/useAccent";

interface Props {
  games: Game[];
  reportStatus: (text: string, warn?: boolean) => void;
  onRefresh: () => Promise<void>;
  version:  string;
  /** null until the first launcher_prefs fetch resolves. */
  launcherPrefs: LauncherPrefs | null;
  /** Notify App.tsx of the latest snapshot so the CloseBehaviorModal
   *  state stays in sync (and the toggle stops re-prompting once set). */
  onPrefsChange: (next: LauncherPrefs) => void;
}

export default function SettingsView({
  games, reportStatus, onRefresh, version,
  launcherPrefs, onPrefsChange,
}: Props) {
  const overridden = games.filter((g) => g.install_path);
  const [busy, setBusy] = useState<"close" | "autostart" | "gpu" | null>(null);

  // ── Crash reporting (default ON; user can opt out) ────────
  const [crashOptIn, setCrashOptIn] = useState(true);
  const [crashBusy, setCrashBusy]   = useState(false);
  useEffect(() => {
    let alive = true;
    void api.getCrashOptIn().then((v) => { if (alive) setCrashOptIn(v); }).catch(() => {});
    return () => { alive = false; };
  }, []);
  const toggleCrash = async (next: boolean) => {
    setCrashBusy(true);
    try {
      await api.setCrashOptIn(next);
      setCrashOptIn(next);
      reportStatus(next ? "דיווח קריסות מופעל — תודה שאתה עוזר לשפר" : "דיווח קריסות כובה");
    } catch (e) {
      reportStatus(`שגיאה: ${(e as Error).message}`, true);
    } finally {
      setCrashBusy(false);
    }
  };

  // ── Mod update channel + behaviour ────────────────────────
  const [updPrefs, setUpdPrefs] = useState<UpdatePrefs | null>(null);
  const [updBusy, setUpdBusy]   = useState(false);
  useEffect(() => {
    let alive = true;
    void api.getUpdatePrefs().then((v) => { if (alive) setUpdPrefs(v); }).catch(() => {});
    return () => { alive = false; };
  }, []);
  const applyUpdPrefs = async (beta: boolean, msg: string) => {
    setUpdBusy(true);
    try {
      const r = await api.setUpdatePrefs(beta);
      setUpdPrefs(r);
      reportStatus(msg);
    } catch (e) {
      reportStatus(`שגיאה: ${(e as Error).message}`, true);
    } finally {
      setUpdBusy(false);
    }
  };

  // Translation-cache management is no longer global — each mod's cache
  // is cleared from its own detail panel (GameDetailPanel), next to that
  // mod's install path.

  const handleOpen = async (p: string) => {
    const r = await api.openFolder(p);
    if (!r.ok) reportStatus(r.error ?? "שגיאה", true);
  };

  const handleClear = async (id: string) => {
    await api.clearCustomPath(id);
    reportStatus("נתיב נמחק");
    await onRefresh();
  };

  // ── Lifecycle toggles ────────────────────────────────────
  const minimizeOnClose = launcherPrefs?.closeBehavior === "minimize";
  const startWithOs     = launcherPrefs?.startWithOs === true;

  const toggleMinimizeOnClose = async (next: boolean) => {
    setBusy("close");
    try {
      const r = await api.setCloseBehavior(next ? "minimize" : "close");
      onPrefsChange({ closeBehavior: r.closeBehavior, startWithOs: r.startWithOs });
      reportStatus(next ? "סגירה ל-X תמזער למגש המערכת" : "סגירה ל-X תסגור לחלוטין");
    } catch (e) {
      reportStatus(`שגיאה: ${(e as Error).message}`, true);
    } finally {
      setBusy(null);
    }
  };

  const toggleStartWithOs = async (next: boolean) => {
    setBusy("autostart");
    try {
      const r = await api.setStartWithOs(next);
      onPrefsChange({ closeBehavior: r.closeBehavior, startWithOs: r.startWithOs });
      if (r.ok) {
        reportStatus(next
          ? "הופעל — התוכנה תעלה ברקע עם Windows"
          : "הופסק — התוכנה לא תעלה אוטומטית");
      } else {
        reportStatus(`שגיאה: ${r.error ?? "לא ידוע"}`, true);
      }
    } catch (e) {
      reportStatus(`שגיאה: ${(e as Error).message}`, true);
    } finally {
      setBusy(null);
    }
  };

  // GPU acceleration is ON unless the user opted out (default = smooth UI).
  const gpuEnabled = launcherPrefs?.disableGpu !== true;
  const toggleGpu = async (next: boolean) => {
    setBusy("gpu");
    try {
      const r = await api.setGpuCompositing(next);
      onPrefsChange({ closeBehavior: r.closeBehavior, startWithOs: r.startWithOs, disableGpu: r.disableGpu });
      reportStatus(next
        ? "האצת חומרה תופעל — הפעל את התוכנה מחדש כדי להחיל"
        : "האצת חומרה תכבה — הפעל את התוכנה מחדש כדי להחיל");
    } catch (e) {
      reportStatus(`שגיאה: ${(e as Error).message}`, true);
    } finally {
      setBusy(null);
    }
  };

  const [tab, setTab] = useState<TabKey>("general");

  const TABS: { key: TabKey; label: string; Icon: (p: { className?: string }) => ReactNode }[] = [
    { key: "general",    label: "כללי",    Icon: IconGeneral },
    { key: "appearance", label: "מראה",    Icon: IconAppearance },
    { key: "updates",    label: "עדכונים", Icon: IconUpdates },
    { key: "privacy",    label: "פרטיות",  Icon: IconPrivacy },
    { key: "paths",      label: "נתיבים",  Icon: IconPaths },
  ];

  return (
    <div className="h-full overflow-y-auto px-8 py-6 animate-fade-in">
      <h1 className="text-3xl font-extrabold mb-6 text-right animate-rise"><span className="text-gradient">הגדרות</span></h1>

      <div className="flex gap-6 items-start">
        {/* Side tab list (RTL → right). */}
        <nav className="w-48 shrink-0 flex flex-col gap-1 sticky top-0">
          {TABS.map((t) => {
            const on = tab === t.key;
            return (
              <button
                key={t.key}
                type="button"
                onClick={() => setTab(t.key)}
                className={[
                  "group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-right transition",
                  on ? "bg-white/[0.08] text-white" : "text-slate-400 hover:bg-white/[0.04] hover:text-slate-200",
                ].join(" ")}
              >
                <span className={["absolute right-0 top-2 bottom-2 w-[3px] rounded-full transition-opacity",
                  on ? "opacity-100" : "opacity-0"].join(" ")}
                  style={{ background: "#00ffe0", boxShadow: on ? "0 0 14px #00ffe0" : undefined }} />
                <span className="flex-1 font-medium text-[14px]">{t.label}</span>
                <t.Icon className={on ? "text-brand-cyan" : "text-slate-500 group-hover:text-brand-cyan"} />
              </button>
            );
          })}
        </nav>

        {/* Active tab content. */}
        <div className="flex-1 min-w-0 animate-fade-in" key={tab}>
          {tab === "general" && (
            <>
              <section className="glass rounded-2xl p-6 mb-6">
                <div className="flex items-baseline justify-between mb-3">
                  <span dir="ltr" className="font-mono text-xs text-slate-400 flex items-center gap-1.5">
                    {version}
                  </span>
                  <h2 className="text-lg font-bold text-white text-right">על האפליקציה</h2>
                </div>
                <p className="text-slate-300 text-sm leading-relaxed text-right">
                  מנהל מודי תרגום עברי למשחקי PC — התקנה, הפעלה ועדכון בלחיצה.
                </p>
              </section>

              <section className="glass rounded-2xl p-6">
                <h2 className="text-lg font-bold text-white mb-4 text-right">הפעלה ומגש מערכת</h2>
                <ToggleRow
                  enabled={startWithOs}
                  busy={busy === "autostart"}
                  onChange={toggleStartWithOs}
                  title="הפעלה עם עליית Windows"
                  subtitle="התוכנה תיטען אוטומטית בכניסה ל-Windows, מוסתרת במגש המערכת — בלי לפתוח את חלון הלאנצ׳ר. ניתן לפתוח דרך אייקון המגש בכל רגע."
                  disabled={launcherPrefs === null}
                />
                <div className="h-px bg-white/10 my-3" />
                <ToggleRow
                  enabled={minimizeOnClose}
                  busy={busy === "close"}
                  onChange={toggleMinimizeOnClose}
                  title="המשך ריצה ברקע בלחיצה על X"
                  subtitle="במקום לסגור את התוכנה לגמרי, לחיצה על ✕ תמזער אותה למגש המערכת והיא תמשיך לרוץ בשקט עד שתבחר 'סגור לצמיתות' מתפריט המגש."
                  disabled={launcherPrefs === null}
                />
              </section>

              <section className="glass rounded-2xl p-6 mt-6">
                <h2 className="text-lg font-bold text-white mb-4 text-right">ביצועים</h2>
                <ToggleRow
                  enabled={gpuEnabled}
                  busy={busy === "gpu"}
                  onChange={toggleGpu}
                  title="האצת חומרה (כרטיס מסך)"
                  subtitle="מומלץ להשאיר דלוק — הממשק יזרום חלק יותר. כבה רק אם אתה רואה הבהוב או ריצוד בתצוגה. שינוי נכנס לתוקף בהפעלה הבאה של התוכנה."
                  disabled={launcherPrefs === null}
                />
              </section>
            </>
          )}

          {tab === "appearance" && <AppearanceSettings reportStatus={reportStatus} />}

          {tab === "updates" && (
            <section className="glass rounded-2xl p-6">
              <h2 className="text-lg font-bold text-white mb-4 text-right">עדכוני תרגומים</h2>
              <ToggleRow
                enabled={updPrefs?.betaChannel === true}
                busy={updBusy}
                onChange={(next) => applyUpdPrefs(next,
                  next ? "ערוץ בטא הופעל — תקבל גם גרסאות מוקדמות" : "ערוץ בטא כובה — רק גרסאות יציבות")}
                title="קבלת גרסאות בטא"
                subtitle="כברירת מחדל מוצעים רק עדכונים יציבים. הפעלה תציע גם גרסאות מוקדמות (אלפא/בטא/RC) — חדשות יותר אך עשויות להיות פחות יציבות. אפשר לכוונן פר-מוד בכרטיס המשחק."
                disabled={updPrefs === null}
              />
              <p className="text-slate-400 text-xs mt-4 leading-relaxed text-right">
                כשקיים עדכון לתרגום מותקן — תקבל הודעה בתוך התוכנה וגם התראה במערכת (Windows).
                העדכון לעולם לא מותקן לבד; אתה בוחר מתי לעדכן מתוך כרטיס המשחק או ממסך ההורדות.
              </p>
            </section>
          )}

          {tab === "privacy" && (
            <section className="glass rounded-2xl p-6">
              <h2 className="text-lg font-bold text-white mb-4 text-right">פרטיות ודיווחים</h2>
              <ToggleRow
                enabled={crashOptIn}
                busy={crashBusy}
                onChange={toggleCrash}
                title="שליחת דוחות קריסה לצוות הפיתוח"
                subtitle="כשהתוכנה נתקלת בשגיאה, נשלח דוח אנונימי (סוג השגיאה, מערכת ההפעלה והלוג) כדי שנוכל לתקן. נתיבים אישיים וטוקנים מנוקים לפני השליחה. אפשר לכבות בכל עת."
                disabled={false}
              />
            </section>
          )}

          {tab === "paths" && (
            <section className="glass rounded-2xl p-6">
              <h2 className="text-lg font-bold text-white mb-4 text-right">נתיבים מותאמים אישית</h2>
              <h3 className="text-sm font-bold text-slate-200 mb-2 text-right border-b border-white/10 pb-1.5">משחקים</h3>
              {overridden.length === 0 ? (
                <div className="text-slate-400 text-sm text-right mb-2 mt-2">
                  אין נתיבי משחקים מותאמים. כשתגדיר נתיב ידני בכרטיס משחק הוא יופיע כאן.
                </div>
              ) : (
                <ul className="space-y-2 mt-2">
                  {overridden.map((g) => (
                    <li key={g.id} className="flex items-center justify-between gap-3 bg-white/5 rounded-xl p-3">
                      <div className="flex gap-2">
                        <button
                          type="button"
                          onClick={() => handleClear(g.id)}
                          className="text-xs px-3 py-1.5 border border-rose-500/30 text-rose-200 rounded-lg hover:bg-rose-500/10"
                        >נקה</button>
                        <button
                          type="button"
                          onClick={() => g.install_path && handleOpen(g.install_path)}
                          className="text-xs px-3 py-1.5 bg-brand-yellow text-brand-ink rounded-lg font-bold hover:bg-yellow-300"
                        >פתח</button>
                      </div>
                      <div className="flex-1 min-w-0 text-right">
                        <div dir="ltr" className="text-white font-semibold text-left truncate">{g.titleEn}</div>
                        <div dir="ltr" title={g.install_path ?? undefined}
                             className="text-slate-400 text-xs text-left mt-0.5 truncate">{g.install_path}</div>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          )}
        </div>
      </div>
    </div>
  );
}

type TabKey = "general" | "appearance" | "updates" | "privacy" | "paths";

/* Tab icons (stroke=currentColor). */
function IconGeneral({ className }: { className?: string }) {
  return <svg className={className} width={18} height={18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.6 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.6a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" /></svg>;
}
function IconAppearance({ className }: { className?: string }) {
  // Clean "sparkle" mark — reads clearly at 18px (the old palette-with-dots
  // glyph looked muddy). A big 4-point star + a small one = "look / polish".
  return <svg className={className} width={18} height={18} viewBox="0 0 24 24" fill="currentColor" stroke="none" aria-hidden><path d="M12 2.5l1.9 5.1a3 3 0 0 0 1.8 1.8l5.1 1.9-5.1 1.9a3 3 0 0 0-1.8 1.8L12 20.1l-1.9-5.1a3 3 0 0 0-1.8-1.8L3.2 11.3l5.1-1.9a3 3 0 0 0 1.8-1.8z" /><path d="M18.5 2.5l.7 1.9a1.5 1.5 0 0 0 .9.9l1.9.7-1.9.7a1.5 1.5 0 0 0-.9.9l-.7 1.9-.7-1.9a1.5 1.5 0 0 0-.9-.9L15 6l1.9-.7a1.5 1.5 0 0 0 .9-.9z" /></svg>;
}
function IconUpdates({ className }: { className?: string }) {
  return <svg className={className} width={18} height={18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M21 12a9 9 0 1 1-3.1-6.8" /><path d="M21 4v5h-5" /></svg>;
}
function IconPrivacy({ className }: { className?: string }) {
  return <svg className={className} width={18} height={18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" /></svg>;
}
function IconPaths({ className }: { className?: string }) {
  return <svg className={className} width={18} height={18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" /></svg>;
}

// ───────────────────────────────────────────────────────────────
// Appearance — user theming (animations / density / ambient accent).
const ACCENT_SWATCHES: { hex: string; label: string }[] = [
  { hex: "#00ffe0", label: "טורקיז" },
  { hex: "#fff700", label: "צהוב" },
  { hex: "#7c3aed", label: "סגול" },
  { hex: "#22c55e", label: "ירוק" },
  { hex: "#ff4d8d", label: "ורוד" },
  { hex: "#3b82f6", label: "כחול" },
];

function AppearanceSettings({ reportStatus }: { reportStatus: (t: string, w?: boolean) => void }) {
  const [anims, setAnimsState]     = useState<boolean>(getAnims());
  const [density, setDensityState] = useState<Density>(getDensity());
  const [accent, setAccentState]   = useState<string>(getAccent());
  const [sounds, setSoundsState]   = useState<boolean>(getSounds());
  const [rainbow, setRainbowState] = useState<boolean>(getRainbow());
  const [sbMode, setSbMode] = useState<SidebarMode>(getSidebarMode());
  const applyAccentNow = useAccentSetter();
  const onRainbow = () => {
    setRainbow(true); setRainbowState(true);
    reportStatus("רקע צבעוני הופעל");
  };

  const onSounds = (next: boolean) => {
    setSounds(next); setSoundsState(next);
    reportStatus(next ? "צלילי ממשק הופעלו" : "צלילי ממשק כובו");
  };

  const onAnims = (next: boolean) => {
    setAnims(next); setAnimsState(next);
    reportStatus(next ? "אנימציות הופעלו" : "אנימציות כובו — מצב מהיר");
  };
  const onDensity = (d: Density) => {
    setDensity(d); setDensityState(d);
    reportStatus(d === "compact" ? "תצוגה צפופה" : "תצוגה מרווחת");
  };
  const onAccent = (hex: string) => {
    setAccentPref(hex); setAccentState(hex);
    setRainbow(false); setRainbowState(false);   // picking a solid colour exits "colourful"
    applyAccentNow(hex);   // live-paint the ambient background now
    reportStatus("צבע האווירה עודכן");
  };
  const onSidebar = (m: SidebarMode) => {
    setSidebarMode(m); setSbMode(m);
    reportStatus("מצב הסרגל עודכן");
  };

  return (
    <>
      <section className="glass rounded-2xl p-6 mb-6">
        <h2 className="text-lg font-bold text-white mb-4 text-right">תנועה וצפיפות</h2>
        <ToggleRow
          enabled={anims}
          busy={false}
          onChange={onAnims}
          title="אנימציות ואפקטים"
          subtitle="מעברים חלקים, זוהר נושם ואפקטים. כיבוי נותן מצב מהיר ומינימלי (טוב למחשבים חלשים)."
          disabled={false}
        />
        <div className="h-px bg-white/10 my-4" />
        <ToggleRow
          enabled={sounds}
          busy={false}
          onChange={onSounds}
          title="צלילי ממשק"
          subtitle="צליל קליק עדין בלחיצות. כבוי כברירת מחדל — הפעל אם אתה אוהב משוב קולי."
          disabled={false}
        />
        <div className="h-px bg-white/10 my-4" />
        <div className="flex items-center justify-between gap-4">
          <div className="flex rounded-lg overflow-hidden border border-white/10">
            {([["comfortable", "מרווח"], ["compact", "צפוף"]] as [Density, string][]).map(([k, label]) => (
              <button
                key={k}
                type="button"
                onClick={() => onDensity(k)}
                className={["px-4 py-1.5 text-sm transition",
                  density === k ? "bg-brand-cyan/15 text-brand-cyan font-semibold" : "text-slate-400 hover:bg-white/5"].join(" ")}
              >{label}</button>
            ))}
          </div>
          <div className="text-right">
            <div className="text-white font-bold">צפיפות התצוגה</div>
            <div className="text-slate-400 text-xs mt-1">כמה מידע על המסך בבת אחת.</div>
          </div>
        </div>
      </section>

      <section className="glass rounded-2xl p-6 mb-6">
        <h2 className="text-lg font-bold text-white mb-2 text-right">סרגל הצד</h2>
        <p className="text-slate-400 text-xs mb-4 text-right leading-relaxed">
          איך הסרגל הצדדי מתנהג. ברירת מחדל: ריחוף — נפתח כשמעבירים עליו עכבר.
        </p>
        <div className="flex flex-col gap-2">
          {([["auto", "ריחוף", "נפתח בריחוף עכבר; מצומצם כברירת מחדל"], ["wide", "נעול רחב", "תמיד פתוח"], ["narrow", "נעול מצומצם", "תמיד מצומצם"]] as [SidebarMode, string, string][]).map(([k, label, desc]) => {
            const on = sbMode === k;
            return (
              <button
                key={k}
                type="button"
                onClick={() => onSidebar(k)}
                className={[
                  "flex items-center gap-3 rounded-xl border px-4 py-2.5 transition text-right",
                  on ? "bg-brand-cyan/15 border-brand-cyan/50" : "bg-white/[0.03] border-white/10 hover:bg-white/[0.06]",
                ].join(" ")}
              >
                <span className={["w-4 h-4 rounded-full border-2 shrink-0 grid place-items-center", on ? "border-brand-cyan" : "border-slate-500"].join(" ")}>
                  {on && <span className="w-2 h-2 rounded-full bg-brand-cyan" />}
                </span>
                <span className="flex-1 min-w-0">
                  <span className="block text-white font-semibold text-sm">{label}</span>
                  <span className="block text-slate-400 text-[11px]">{desc}</span>
                </span>
              </button>
            );
          })}
        </div>
      </section>

      <section className="glass rounded-2xl p-6">
        <h2 className="text-lg font-bold text-white mb-2 text-right">צבע אווירה</h2>
        <p className="text-slate-400 text-xs mb-4 text-right leading-relaxed">
          הצבע שצובע את רקע התוכנה כשאין משחק פתוח. בתוך עמוד משחק הרקע נצבע אוטומטית בצבע הכותר.
        </p>
        <div className="flex gap-3 justify-end flex-wrap">
          {/* Colourful / rainbow — a soft multi-colour ambient wash. */}
          <button
            type="button"
            onClick={onRainbow}
            title="צבעוני"
            aria-label="צבעוני"
            className="w-10 h-10 rounded-full transition-transform hover:scale-110 grid place-items-center"
            style={{
              background: "conic-gradient(from 210deg, #00ffe0, #7c3aed, #ff4d8d, #fff700, #22c55e, #00ffe0)",
              boxShadow: rainbow ? "0 0 0 3px #0a0a14, 0 0 0 5px #ffffff" : "0 4px 12px -4px rgba(255,255,255,0.4)",
            }}
          >
            {rainbow && <span className="text-white text-lg font-black drop-shadow-[0_1px_2px_rgba(0,0,0,0.8)]">✓</span>}
          </button>
          {ACCENT_SWATCHES.map((s) => {
            const on = !rainbow && accent.toLowerCase() === s.hex.toLowerCase();
            return (
              <button
                key={s.hex}
                type="button"
                onClick={() => onAccent(s.hex)}
                title={s.label}
                aria-label={s.label}
                className="w-10 h-10 rounded-full transition-transform hover:scale-110 grid place-items-center"
                style={{ background: s.hex, boxShadow: on ? `0 0 0 3px #0a0a14, 0 0 0 5px ${s.hex}` : `0 4px 12px -4px ${s.hex}99` }}
              >
                {on && <span className="text-brand-ink text-lg font-black">✓</span>}
              </button>
            );
          })}
        </div>
      </section>
    </>
  );
}

// ───────────────────────────────────────────────────────────────
function ToggleRow({
  enabled, busy, onChange, title, subtitle, disabled,
}: {
  enabled:  boolean;
  busy:     boolean;
  onChange: (next: boolean) => void;
  title:    string;
  subtitle: string;
  disabled: boolean;
}) {
  return (
    <div className="flex items-start gap-4">
      <button
        type="button"
        role="switch"
        aria-checked={enabled}
        disabled={busy || disabled}
        onClick={() => onChange(!enabled)}
        className="relative w-12 h-7 rounded-full transition shrink-0
                   disabled:opacity-50 disabled:cursor-wait"
        style={{
          background: enabled ? "#fff700" : "rgba(255,255,255,0.12)",
          boxShadow:  enabled ? "0 6px 16px -8px rgba(255,247,0,0.6)" : "none",
        }}
      >
        <span
          className="absolute top-0.5 w-6 h-6 rounded-full transition-all"
          style={{
            left: enabled ? "calc(100% - 1.5rem - 0.125rem)" : "0.125rem",
            background: enabled ? "#0a0a14" : "rgba(255,255,255,0.85)",
          }}
        />
      </button>
      <div className="flex-1 text-right">
        <div className="text-white font-bold">{title}</div>
        <div className="text-slate-400 text-xs mt-1 leading-relaxed">{subtitle}</div>
      </div>
    </div>
  );
}
