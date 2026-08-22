// Settings - app info, lifecycle toggles, custom game paths.
//
// Lifecycle toggles bind directly to the launcher_prefs.json + Windows
// HKCU autostart registry entry through the eel bridge. The version
// string is fed in from APP_VERSION (locked at v1.1.0) so the small
// label at the sidebar footer and the "על האפליקציה" block stay in
// lockstep.
import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import type { Game, LauncherPrefs, AppIconOption } from "../lib/types";
import { api, type UpdatePrefs } from "../lib/eel";
import {
  getAnimLevel, setAnimLevel, type AnimLevel,
  getTextScale, setTextScale, getAccent, setAccentPref,
  getAccent2, setAccent2Pref,
  getRainbow, setRainbow, getSidebarMode, setSidebarMode, type SidebarMode,
  getSounds, setSounds,
} from "../lib/themePrefs";
import { useAccentSetter } from "../lib/useAccent";
import { CHANGELOG } from "../lib/changelog";
import ControllerSettings from "../components/ControllerSettings";
import SegmentedControl from "../components/SegmentedControl";
import { IconOptBtnShowOnboarding, IconOptBtnOpenPath, IconOptHdrAbout, IconOptHdrPaths, IconOptHdrPrivacy } from "../components/UiIcons";

interface Props {
  games: Game[];
  reportStatus: (text: string, warn?: boolean) => void;
  /** LOCAL re-read of the app state (getAllGames) - used after a path delete. */
  onRefresh: () => Promise<void>;
  /** FULL server refresh (catalog + news + updates) - the "רענן את התוכנה"
   *  button. Owns its own toast lifecycle, so the button must not add one. */
  onRefreshFromServer: () => Promise<void>;
  version:  string;
  /** null until the first launcher_prefs fetch resolves. */
  launcherPrefs: LauncherPrefs | null;
  /** Notify App.tsx of the latest snapshot so the CloseBehaviorModal
   *  state stays in sync (and the toggle stops re-prompting once set). */
  onPrefsChange: (next: LauncherPrefs) => void;
}

export default function SettingsView({
  games, reportStatus, onRefresh, onRefreshFromServer, version,
  launcherPrefs, onPrefsChange,
}: Props) {
  const overridden = games.filter((g) => g.install_path);
  const [busy, setBusy] = useState<"close" | "autostart" | "gpu" | null>(null);
  const [refreshing, setRefreshing] = useState(false);

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
      reportStatus(next ? "דיווח קריסות מופעל - תודה שאתה עוזר לשפר" : "דיווח קריסות כובה");
    } catch (e) {
      reportStatus(`שגיאה: ${(e as Error).message}`, true);
    } finally {
      setCrashBusy(false);
    }
  };

  // The custom frameless title bar is now ALWAYS ON (no toggle - by request).
  // Settings below only take effect at PROCESS START, so changing one offers a
  // real restart instead of a toast the user has to act on themselves.
  const [restartMsg, setRestartMsg] = useState<string | null>(null);


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

  // Translation-cache management is no longer global - each mod's cache
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
          ? "הופעל - התוכנה תעלה ברקע עם Windows"
          : "הופסק - התוכנה לא תעלה אוטומטית");
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
      setRestartMsg(next
        ? "האצת החומרה (כרטיס המסך) תופעל לאחר הפעלה מחדש של התוכנה."
        : "האצת החומרה תכבה לאחר הפעלה מחדש של התוכנה.");
    } catch (e) {
      reportStatus(`שגיאה: ${(e as Error).message}`, true);
    } finally {
      setBusy(null);
    }
  };

  const [tab, setTab] = useState<TabKey>("general");

  // Springy sliding indicator for the side-tabs (matches the sidebar nav).
  const tabsRef = useRef<HTMLElement | null>(null);
  const [tabInd, setTabInd] = useState<{ top: number; height: number; on: boolean }>({ top: 0, height: 0, on: false });
  useLayoutEffect(() => {
    // Re-measure the active tab on: tab change, first-paint settle (rAF), the
    // text-size setting changing the tab heights (ResizeObserver), and window
    // resize. Keying only on [tab] left the pill stranded at the OLD position
    // when the text scale changed - it only "fixed itself" on the next click.
    const measure = () => {
      const el = tabsRef.current?.querySelector<HTMLElement>(`[data-tab="${tab}"]`);
      if (!el) { setTabInd((s) => ({ ...s, on: false })); return; }
      setTabInd({ top: el.offsetTop, height: el.offsetHeight, on: true });
    };
    measure();
    const raf = requestAnimationFrame(measure);
    const nav = tabsRef.current;
    const ro = new ResizeObserver(measure);
    if (nav) ro.observe(nav);
    window.addEventListener("resize", measure);
    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      window.removeEventListener("resize", measure);
    };
  }, [tab]);

  const TABS: { key: TabKey; label: string; Icon: (p: { className?: string }) => ReactNode }[] = [
    { key: "general",    label: "כללי",    Icon: IconGeneral },
    { key: "appearance", label: "מראה",    Icon: IconAppearance },
    { key: "controller", label: "שלט",     Icon: IconController },
    { key: "updates",    label: "עדכונים", Icon: IconUpdates },
    { key: "changelog",  label: "יומן שינויים", Icon: IconChangelog },
    { key: "privacy",    label: "פרטיות",  Icon: IconPrivacy },
    { key: "paths",      label: "נתיבים",  Icon: IconPaths },
  ];

  return (
    <div className="h-full overflow-y-auto px-8 py-6 animate-fade-in">
      <h1 className="text-3xl font-extrabold mb-6 text-right animate-rise"><span className="text-gradient">הגדרות</span></h1>

      <div className="flex gap-6 items-start">
        {/* Side tab list (RTL → right). data-nav-menu = D-pad up/down switches
            the active tab live (not just moves the focus ring). */}
        <nav ref={tabsRef} data-nav-menu className="relative w-48 shrink-0 flex flex-col gap-1 sticky top-0">
          {/* Single springy pill that slides to the active tab. */}
          <span
            className="nav-slide nav-slide-glass absolute right-0 left-0 rounded-xl bg-white/[0.08] pointer-events-none z-0"
            aria-hidden
            style={{ top: tabInd.top, height: tabInd.height, opacity: tabInd.on ? 1 : 0,
                     ["--nav-accent" as string]: "#00ffe0" }}
          >
            {/* Glowing edge bar removed per user request - the active tab keeps
                its accent wash + glass; no bar on the tab's edge. */}
          </span>
          {TABS.map((t) => {
            const on = tab === t.key;
            return (
              <button
                key={t.key}
                type="button"
                data-tab={t.key}
                onClick={() => setTab(t.key)}
                className={[
                  "group relative z-[1] flex items-center gap-3 rounded-xl px-3 py-2.5 text-right transition-colors",
                  on ? "text-white" : "text-slate-400 hover:bg-white/[0.04] hover:text-slate-200",
                ].join(" ")}
              >
                <span className="flex-1 font-medium text-[14px]">{t.label}</span>
                <t.Icon className={on ? "text-brand-cyan" : "text-slate-500 group-hover:text-brand-cyan"} />
              </button>
            );
          })}
        </nav>

        {/* Active tab content. */}
        <div className="flex-1 min-w-0 view-transition" key={tab}>
          {tab === "general" && (
            <>
              <section className="glass rounded-2xl p-6 mb-6">
                <div className="flex items-baseline justify-between mb-3">
                  <h2 className="text-lg font-bold text-white text-right inline-flex items-center gap-1.5"><IconOptHdrAbout width={20} className="shrink-0 opacity-90" />על האפליקציה</h2>
                  <span dir="ltr" className="font-mono text-xs text-slate-400 flex items-center gap-1.5">
                    {version}
                  </span>
                </div>
                <p className="text-slate-300 text-sm leading-relaxed text-right">
                  מנהל מודי תרגום עברי למשחקי PC - התקנה, הפעלה ועדכון בלחיצה.
                </p>
              </section>

              <section className="glass rounded-2xl p-6 mb-6">
                <h2 className="text-lg font-bold text-white mb-2 text-right">רענון והדרכה</h2>
                <p className="text-slate-400 text-xs mb-4 text-right leading-relaxed">
                  רענן את נתוני התוכנה (קטלוג, חדשות ועדכונים) או פתח מחדש את מדריך ההתחלה למתחילים.
                </p>
                <div className="flex gap-2 justify-end flex-wrap">
                  <button
                    type="button"
                    disabled={refreshing}
                    onClick={async () => {
                      // FULL server refresh (catalog + news + updates) - the same
                      // path the controller "רענון" uses. It owns the toast
                      // lifecycle ("מרענן מהשרת..." → "עודכן מהשרת" / "אין חיבור"),
                      // so we DON'T add a premature "התוכנה רועננה" here - that was
                      // what made the button LOOK done while it only re-read the
                      // local catalog and never actually hit the server.
                      setRefreshing(true);
                      try { await onRefreshFromServer(); }
                      catch (e) { reportStatus(`שגיאה: ${(e as Error).message}`, true); }
                      finally { setRefreshing(false); }
                    }}
                    className="px-4 py-2 rounded-xl bg-brand-cyan/15 border border-brand-cyan/40
                               text-brand-cyan text-sm font-bold hover:bg-brand-cyan/25 transition
                               disabled:opacity-50 flex items-center gap-2"
                  >
                    {refreshing ? (
                      <span className="w-4 h-4 border-2 border-brand-cyan border-t-transparent rounded-full animate-spin" />
                    ) : (
                      <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="currentColor"
                           strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                        <path d="M21 12a9 9 0 1 1-3.1-6.8" /><path d="M21 4v5h-5" />
                      </svg>
                    )}
                    רענן את התוכנה
                  </button>
                  <button
                    type="button"
                    onClick={() => { window.dispatchEvent(new CustomEvent("open-onboarding")); reportStatus("מדריך ההתחלה נפתח"); }}
                    className="px-4 py-2 rounded-xl bg-white/5 border border-white/10
                               text-slate-200 text-sm font-bold hover:bg-white/10 transition inline-flex items-center gap-1.5"
                  >
                    <IconOptBtnShowOnboarding width={18} className="shrink-0 opacity-90" />
                    הצג מדריך התחלה
                  </button>
                </div>
              </section>

              <section className="glass rounded-2xl p-6">
                <h2 className="text-lg font-bold text-white mb-4 text-right">הפעלה ומגש מערכת</h2>
                <ToggleRow
                  enabled={startWithOs}
                  busy={busy === "autostart"}
                  onChange={toggleStartWithOs}
                  title="הפעלה עם עליית Windows"
                  subtitle="התוכנה תיטען אוטומטית בכניסה ל-Windows, מוסתרת במגש המערכת - בלי לפתוח את חלון הלאנצ׳ר. ניתן לפתוח דרך אייקון המגש בכל רגע."
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
                  subtitle="מומלץ להשאיר דלוק - הממשק יזרום חלק יותר. כבה רק אם אתה רואה הבהוב או ריצוד בתצוגה. שינוי נכנס לתוקף בהפעלה הבאה של התוכנה."
                  disabled={launcherPrefs === null}
                />
              </section>
            </>
          )}

          {tab === "appearance" && <AppearanceSettings reportStatus={reportStatus} />}


          {tab === "controller" && <ControllerSettings reportStatus={reportStatus} />}

          {tab === "updates" && (
            <section className="glass rounded-2xl p-6">
              <h2 className="text-lg font-bold text-white mb-4 text-right">עדכוני תרגומים</h2>
              <ToggleRow
                enabled={updPrefs?.betaChannel === true}
                busy={updBusy}
                onChange={(next) => applyUpdPrefs(next,
                  next ? "ערוץ בטא הופעל - תקבל גם גרסאות מוקדמות" : "ערוץ בטא כובה - רק גרסאות יציבות")}
                title="קבלת גרסאות בטא"
                subtitle="כברירת מחדל מוצעים רק עדכונים יציבים. הפעלה תציע גם גרסאות מוקדמות (אלפא/בטא/RC) - חדשות יותר אך עשויות להיות פחות יציבות. אפשר לכוונן פר-מוד בכרטיס המשחק."
                disabled={updPrefs === null}
              />
              <p className="text-slate-400 text-xs mt-4 leading-relaxed text-right">
                כשקיים עדכון לתרגום מותקן - תקבל הודעה בתוך התוכנה וגם התראה במערכת (Windows).
                העדכון לעולם לא מותקן לבד; אתה בוחר מתי לעדכן מתוך כרטיס המשחק או ממסך ההורדות.
              </p>
              <div className="h-px bg-white/10 my-4" />
              <div className="flex items-start gap-4">
                <button
                  type="button"
                  onClick={async () => {
                    try {
                      await api.notifyOs("בדיקת התראה", "ההתראות של Windows עובדות. כך תיראה הודעה על עדכון תרגום.");
                      reportStatus("נשלחה התראת בדיקה - חפש אותה בפינת המסך");
                    } catch {
                      reportStatus("שליחת ההתראה נכשלה", true);
                    }
                  }}
                  className="shrink-0 px-4 py-2 rounded-xl bg-white/5 border border-white/10 text-slate-200
                             hover:bg-white/10 text-sm font-semibold transition"
                >
                  שלח התראת בדיקה
                </button>
                <div className="flex-1 text-right">
                  <div className="text-white font-bold">בדיקת התראות Windows</div>
                  <div className="text-slate-400 text-xs mt-1 leading-relaxed">
                    שולח התראה אמיתית עכשיו. לא רואה אותה? פתח הגדרות Windows → מערכת → התראות,
                    ודא שההתראות דלוקות, ש'נא לא להפריע' כבוי, ושהתוכנה מאושרת ברשימה.
                  </div>
                </div>
              </div>
            </section>
          )}

          {tab === "changelog" && <ChangelogSettings />}

          {tab === "privacy" && (
            <section className="glass rounded-2xl p-6">
              <h2 className="text-lg font-bold text-white mb-4 text-right inline-flex items-center gap-1.5"><IconOptHdrPrivacy width={20} className="shrink-0 opacity-90" />פרטיות ודיווחים</h2>
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
              <h2 className="text-lg font-bold text-white mb-4 text-right inline-flex items-center gap-1.5"><IconOptHdrPaths width={20} className="shrink-0 opacity-90" />נתיבים מותאמים אישית</h2>
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
                          className="text-xs px-3 py-1.5 bg-brand-yellow text-brand-ink rounded-lg font-bold hover:bg-yellow-300 inline-flex items-center gap-1.5"
                        ><IconOptBtnOpenPath width={18} className="shrink-0 opacity-90" />פתח</button>
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

      {restartMsg && (
        <RestartPrompt
          message={restartMsg}
          onLater={() => setRestartMsg(null)}
          onRestart={async () => {
            setRestartMsg(null);
            try { await api.restartApp(); }
            catch { reportStatus("ההפעלה מחדש נכשלה - סגור ופתח את התוכנה ידנית", true); }
          }}
        />
      )}
    </div>
  );
}

/** Shown when a setting only takes effect at process start (hardware
 *  acceleration, the custom title bar): offer a REAL restart, not just a toast. */
function RestartPrompt({ message, onRestart, onLater }: {
  message: string; onRestart: () => void; onLater: () => void;
}) {
  return (
    <div
      className="fixed inset-0 z-[200] grid place-items-center animate-fade-in"
      style={{ background: "rgba(4,4,12,0.72)" }}
      onMouseDown={onLater}
    >
      <div
        className="glass-strong rounded-2xl p-6 w-[90%] max-w-md ring-1 ring-white/10
                   shadow-[0_30px_70px_-20px_rgba(0,0,0,0.9)]"
        dir="rtl"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <h3 className="text-lg font-bold text-white mb-2">נדרשת הפעלה מחדש</h3>
        <p className="text-sm text-slate-300 leading-relaxed mb-5">{message}</p>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={onRestart}
            className="px-4 py-2 rounded-xl bg-[#00ffe0] text-brand-ink font-bold text-sm
                       hover:brightness-110 transition"
          >
            הפעל מחדש עכשיו
          </button>
          <button
            type="button"
            onClick={onLater}
            className="px-4 py-2 rounded-xl bg-white/5 border border-white/10 text-slate-300
                       text-sm font-semibold hover:bg-white/10 transition"
          >
            הפעל מאוחר יותר
          </button>
        </div>
      </div>
    </div>
  );
}

type TabKey = "general" | "appearance" | "controller" | "updates" | "changelog" | "privacy" | "paths";

/** Version-history timeline for the launcher itself (bundled `CHANGELOG`). */
function ChangelogSettings() {
  const stageLabel: Record<string, string> = {
    beta: "בטא", alpha: "אלפא", rc: "מועמד לשחרור", stable: "יציב",
  };
  const fmtDate = (iso: string) => {
    try {
      return new Date(iso + "T00:00:00").toLocaleDateString("he-IL",
        { day: "numeric", month: "long", year: "numeric" });
    } catch { return iso; }
  };
  return (
    <section className="glass rounded-2xl p-6">
      <h2 className="text-xl font-bold text-white mb-1 text-right">יומן שינויים</h2>
      <p className="text-slate-400 text-[13px] mb-5 text-right leading-relaxed">
        כל מה שהשתנה בתוכנה, גרסה אחר גרסה. הגרסה החדשה ביותר למעלה.
      </p>

      <div className="relative pr-4">
        {/* vertical timeline rail (RTL → on the right) */}
        <span className="absolute right-[5px] top-2 bottom-2 w-px bg-white/10" aria-hidden />
        <div className="flex flex-col gap-7">
          {CHANGELOG.map((entry, i) => (
            <div key={entry.version} className="relative">
              {/* node */}
              <span
                className="absolute right-[-1px] top-1.5 w-[11px] h-[11px] rounded-full ring-4 ring-[#0b0b14]"
                style={{ background: i === 0 ? "#00ffe0" : "rgba(255,255,255,0.35)",
                         boxShadow: i === 0 ? "0 0 12px #00ffe0" : "none" }}
                aria-hidden
              />
              <div className="pr-6">
                <div className="flex items-center gap-2 flex-wrap mb-1.5" dir="rtl">
                  <span className="text-white font-extrabold text-lg tabular-nums">v{entry.version}</span>
                  {entry.channel && (
                    <span className="text-[11px] font-bold px-2 py-0.5 rounded-md
                                     bg-brand-yellow/15 text-brand-yellow ring-1 ring-brand-yellow/30">
                      {stageLabel[entry.channel] ?? entry.channel}
                    </span>
                  )}
                  {i === 0 && (
                    <span className="text-[11px] font-bold px-2 py-0.5 rounded-md
                                     bg-emerald-500/15 text-emerald-200 ring-1 ring-emerald-400/30">
                      מותקן כעת
                    </span>
                  )}
                  <span className="text-slate-500 text-[12px] mr-auto">{fmtDate(entry.date)}</span>
                </div>
                {entry.headline && (
                  <p className="text-slate-300 text-[14px] leading-relaxed font-semibold text-right mb-3">{entry.headline}</p>
                )}
                <div className="flex flex-col gap-3.5">
                  {entry.groups.map((g) => (
                    <div key={g.label}>
                      <div className="text-slate-200 text-[14px] font-bold text-right mb-1.5">{g.label}</div>
                      <ul className="space-y-1.5">
                        {g.items.map((it, k) => (
                          <li key={k} className="text-slate-300 text-[13.5px] leading-relaxed text-right flex gap-2" dir="rtl">
                            <span className="text-[#00ffe0] shrink-0 mt-[2px]">•</span>
                            <span className="flex-1">{it}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function IconChangelog({ className }: { className?: string }) {
  return <svg className={className} width={20} height={20} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M12 8v4l3 2" /><path d="M3.05 11a9 9 0 1 1 .5 4" /><path d="M3 5v4h4" /></svg>;
}

/* Tab icons (stroke=currentColor). */
function IconGeneral({ className }: { className?: string }) {
  return <svg className={className} width={20} height={20} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.6 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.6a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" /></svg>;
}
function IconAppearance({ className }: { className?: string }) {
  // Flaticon UICONS "sparkles" (Regular Rounded) - user's icon-manager pick.
  return <svg className={className} width={20} height={20} viewBox="0 0 24 24" fill="currentColor" aria-hidden><path d="M18.27 22Q18 22 17.8 21.87Q17.6 21.73 17.47 21.47L16.8 19.73L15 19Q14.8 18.87 14.67 18.67Q14.53 18.47 14.53 18.2Q14.53 17.93 14.67 17.73Q14.8 17.53 15.07 17.4L16.8 16.73L17.47 15Q17.6 14.8 17.8 14.67Q18 14.53 18.27 14.53Q18.53 14.53 18.73 14.67Q18.93 14.8 19 15L19.73 16.8L21.47 17.47Q21.73 17.6 21.87 17.8Q22 18 22 18.27Q22 18.53 21.87 18.73Q21.73 18.93 21.47 19L19.73 19.73L19 21.47Q18.93 21.73 18.73 21.87Q18.53 22 18.27 22ZM10.33 19.47Q9.8 19.53 9.33 19.2Q8.87 18.87 8.73 18.33L7.4 14.13L3.13 12.73Q2.6 12.53 2.3 12.07Q2 11.6 2 11.07Q2 10.53 2.33 10.1Q2.67 9.67 3.2 9.47L7.4 8.2L8.8 4Q8.93 3.47 9.4 3.13Q9.87 2.8 10.43 2.83Q11 2.87 11.43 3.2Q11.87 3.53 12 4L13.27 8.2L17.47 9.53Q18 9.73 18.33 10.17Q18.67 10.6 18.67 11.17Q18.67 11.73 18.33 12.17Q18 12.6 17.47 12.8L13.27 14.13L11.93 18.33Q11.8 18.87 11.33 19.2Q10.87 19.53 10.33 19.47ZM10.4 4.53 8.87 9.13Q8.67 9.53 8.27 9.67L3.67 11.07L8.33 12.67Q8.73 12.8 8.87 13.2L10.33 17.8L11.87 13.2Q11.93 12.8 12.4 12.67L17 11.2L12.4 9.67Q11.93 9.53 11.8 9.13ZM17.27 12ZM19.07 7.8Q18.8 7.8 18.57 7.63Q18.33 7.47 18.27 7.2L18 6L16.8 5.67Q16.53 5.6 16.33 5.37Q16.13 5.13 16.17 4.87Q16.2 4.6 16.37 4.37Q16.53 4.13 16.8 4.07L18 3.8L18.27 2.6Q18.33 2.33 18.57 2.17Q18.8 2 19.1 2Q19.4 2 19.6 2.17Q19.8 2.33 19.87 2.6L20.2 3.8L21.4 4.13Q21.67 4.2 21.83 4.4Q22 4.6 22 4.9Q22 5.2 21.83 5.43Q21.67 5.67 21.4 5.73L20.2 6L19.87 7.2Q19.8 7.47 19.6 7.63Q19.4 7.8 19.07 7.87Z" /></svg>;
}
function IconUpdates({ className }: { className?: string }) {
  return <svg className={className} width={20} height={20} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M21 12a9 9 0 1 1-3.1-6.8" /><path d="M21 4v5h-5" /></svg>;
}
function IconController({ className }: { className?: string }) {
  // Flaticon UICONS "gamepad" (Regular Rounded) - user's icon-manager pick.
  return <svg className={className} width={20} height={20} viewBox="0 0 24 24" fill="currentColor" aria-hidden><path d="M20.53 6.2Q19.93 5.27 19 4.7Q18.07 4.13 16.93 4.13H7Q5.87 4.13 4.93 4.7Q4 5.27 3.4 6.2Q2 8.73 2 11.6Q2 13.87 2.57 15.77Q3.13 17.67 4.07 18.77Q5 19.87 6.13 19.87Q8 19.87 9.13 16.33Q9.2 16.07 9.43 15.9Q9.67 15.73 10 15.73H14Q14.27 15.73 14.5 15.9Q14.73 16.07 14.87 16.33Q16 19.87 17.87 19.87Q19 19.87 19.93 18.77Q20.87 17.67 21.43 15.77Q22 13.87 22 11.6Q21.87 8.67 20.53 6.2ZM17.8 18.2Q17.53 18.2 17.13 17.6Q16.73 17 16.33 15.8Q16.13 15 15.47 14.53Q14.8 14.07 13.93 14.07H10Q9.13 14.07 8.47 14.57Q7.8 15.07 7.53 15.8Q7.13 17 6.77 17.6Q6.4 18.2 6.13 18.2Q5.73 18.2 5.13 17.37Q4.53 16.53 4.13 15.13Q3.67 13.47 3.67 11.6Q3.67 9.2 4.8 7Q5.2 6.47 5.77 6.13Q6.33 5.8 7 5.8H16.93Q17.53 5.8 18.13 6.13Q18.73 6.47 19.07 7Q20.27 9.2 20.27 11.6Q20.27 13.47 19.8 15.13Q19.4 16.53 18.8 17.37Q18.2 18.2 17.8 18.2ZM9.53 9.47H8.67V8.67Q8.67 8.27 8.43 8.07Q8.2 7.87 7.83 7.87Q7.47 7.87 7.23 8.07Q7 8.27 7 8.67V9.47H6.2Q5.8 9.47 5.57 9.7Q5.33 9.93 5.33 10.33Q5.33 10.73 5.57 10.93Q5.8 11.13 6.2 11.13H7V12Q7 12.4 7.23 12.6Q7.47 12.8 7.83 12.8Q8.2 12.8 8.43 12.6Q8.67 12.4 8.67 12V11.2H9.53Q9.87 11.2 10.1 10.97Q10.33 10.73 10.33 10.33Q10.33 9.93 10.1 9.73Q9.87 9.53 9.47 9.53ZM16.2 9.07Q16.2 9.6 16.53 9.97Q16.87 10.33 17.4 10.33Q17.93 10.33 18.3 9.97Q18.67 9.6 18.67 9.07Q18.67 8.53 18.3 8.17Q17.93 7.8 17.4 7.8Q16.87 7.8 16.53 8.17Q16.2 8.53 16.2 9.07ZM13.67 11.6Q13.67 12.13 14.03 12.47Q14.4 12.8 14.93 12.8Q15.47 12.8 15.83 12.47Q16.2 12.13 16.2 11.6Q16.2 11.07 15.83 10.7Q15.47 10.33 14.93 10.33Q14.4 10.33 14.03 10.7Q13.67 11.07 13.67 11.6Z" /></svg>;
}
function IconPrivacy({ className }: { className?: string }) {
  // Flaticon UICONS "fingerprint-verified" (Regular Rounded) - user's icon-manager pick.
  return <svg className={className} width={20} height={20} viewBox="0 0 24 24" fill="currentColor" aria-hidden><path d="M2.82 18.59Q2.55 18.59 2.32 18.39Q2.08 18.19 2.02 17.9Q1.95 17.6 2.15 17.3Q2.35 17 2.68 16.93Q4.15 16.66 4.81 14.8Q5.35 13.4 5.35 11.13Q5.35 10.67 5.41 10.27Q5.48 9.87 5.78 9.67Q6.08 9.47 6.41 9.54Q6.75 9.6 6.95 9.87Q7.15 10.13 7.08 10.47Q7.01 10.8 7.01 11.2Q7.01 14.86 5.68 16.8Q4.68 18.26 3.02 18.59ZM2.82 14.46Q3.22 14.46 3.45 14.23Q3.68 14 3.68 13.67V11.13Q3.68 9.14 4.68 7.4Q5.68 5.67 7.41 4.67Q9.14 3.67 11.21 3.67Q13.67 3.67 15.67 5.21Q15.94 5.41 16.27 5.34Q16.6 5.27 16.84 5.01Q17.07 4.74 17 4.41Q16.94 4.07 16.67 3.87Q14.21 2.01 11.14 2.01Q8.68 2.01 6.58 3.24Q4.48 4.47 3.25 6.57Q2.02 8.67 2.02 11.13V13.67Q2.02 14 2.25 14.26Q2.48 14.53 2.88 14.53ZM11.21 5.34Q9.94 5.34 8.81 5.84Q7.68 6.34 6.81 7.27Q6.61 7.54 6.61 7.87Q6.61 8.2 6.88 8.44Q7.15 8.67 7.51 8.67Q7.88 8.67 8.08 8.4Q8.68 7.74 9.48 7.37Q10.28 7 11.18 7Q12.07 7 12.87 7.37Q13.67 7.74 14.27 8.4Q14.54 8.67 14.87 8.67Q15.21 8.67 15.47 8.47Q15.74 8.27 15.77 7.94Q15.81 7.6 15.54 7.34Q14.74 6.4 13.57 5.87Q12.41 5.34 11.21 5.34ZM18.27 8.8Q18.4 9.07 18.6 9.24Q18.8 9.4 19 9.4Q19.2 9.4 19.34 9.34Q19.67 9.27 19.84 8.94Q20 8.6 19.87 8.34Q19.6 7.4 19.14 6.6Q18.94 6.27 18.6 6.2Q18.27 6.14 17.97 6.3Q17.67 6.47 17.57 6.8Q17.47 7.14 17.67 7.4Q18.07 8.07 18.27 8.8ZM22 16.13Q22 17.73 21.2 19.06Q20.4 20.39 19.07 21.19Q17.74 21.99 16.17 21.99Q14.61 21.99 13.27 21.19Q11.94 20.39 11.14 19.06Q10.34 17.73 10.34 16.16Q10.34 14.6 11.14 13.27Q11.94 11.93 13.27 11.13Q14.61 10.33 16.17 10.33Q17.74 10.33 19.07 11.13Q20.4 11.93 21.2 13.27Q22 14.6 22 16.13ZM20.33 16.13Q20.33 15.06 19.77 14.1Q19.2 13.13 18.24 12.57Q17.27 12 16.17 12Q15.07 12 14.11 12.57Q13.14 13.13 12.57 14.1Q12.01 15.06 12.01 16.16Q12.01 17.26 12.57 18.23Q13.14 19.19 14.11 19.76Q15.07 20.33 16.17 20.33Q17.27 20.33 18.24 19.76Q19.2 19.19 19.77 18.23Q20.33 17.26 20.33 16.2ZM8.28 16.6Q7.81 16.6 7.61 16.93Q6.68 18.26 5.95 18.86Q4.75 19.86 3.02 20.33Q2.68 20.46 2.52 20.76Q2.35 21.06 2.45 21.36Q2.55 21.66 2.78 21.83Q3.02 21.99 3.28 21.99H3.48Q5.55 21.39 7.01 20.13Q7.88 19.39 8.88 17.93L8.94 17.86Q9.08 17.66 9.08 17.36Q9.08 17.06 8.84 16.83Q8.61 16.6 8.28 16.6ZM17.67 15.13 15.81 16.93Q15.74 17 15.61 17Q15.47 17 15.41 16.93L14.47 16Q14.21 15.73 13.87 15.73Q13.54 15.73 13.27 16Q13.01 16.26 13.01 16.6Q13.01 16.93 13.27 17.2L14.21 18.13Q14.81 18.66 15.61 18.66Q16.4 18.66 17 18.13L18.8 16.33Q19.07 16.06 19.07 15.73Q19.07 15.4 18.84 15.16Q18.6 14.93 18.27 14.9Q17.94 14.86 17.67 15.13ZM10.34 11.13Q10.34 10.8 10.71 10.53Q11.08 10.27 11.41 10.33Q11.74 10.4 12.04 10.23Q12.34 10.07 12.41 9.74Q12.47 9.4 12.31 9.1Q12.14 8.8 11.81 8.74Q11.14 8.54 10.41 8.84Q9.68 9.14 9.18 9.77Q8.68 10.4 8.68 11.2V12Q8.68 12.33 8.91 12.57Q9.14 12.8 9.51 12.8Q9.88 12.8 10.11 12.57Q10.34 12.33 10.34 12Z" /></svg>;
}
function IconPaths({ className }: { className?: string }) {
  // Flaticon UICONS "api" (Regular Rounded) - user's icon-manager pick.
  return <svg className={className} width={20} height={20} viewBox="0 0 24 24" fill="currentColor" aria-hidden><path d="M19.73 13.53 19.4 13.33Q19.53 12.67 19.53 12Q19.53 11.33 19.4 10.6L19.73 10.4Q20.67 9.93 20.93 8.9Q21.2 7.87 20.67 7Q20.13 6.13 19.17 5.83Q18.2 5.53 17.27 6.07L16.87 6.27Q15.8 5.4 14.53 4.93V4.47Q14.53 3.47 13.77 2.73Q13 2 12 2Q11 2 10.27 2.73Q9.53 3.47 9.53 4.47V4.93Q8.2 5.4 7.13 6.27L6.73 6.07Q5.87 5.6 4.87 5.87Q3.87 6.13 3.33 7Q2.8 7.87 3.07 8.87Q3.33 9.87 4.27 10.4L4.6 10.6Q4.47 11.33 4.47 12Q4.47 12.67 4.6 13.33L4.27 13.53Q3.33 14.07 3.07 15.07Q2.8 16.07 3.33 16.97Q3.87 17.87 4.83 18.13Q5.8 18.4 6.73 17.87L7.13 17.67Q8.2 18.6 9.47 19.07V19.47Q9.47 20.53 10.2 21.27Q10.93 22 11.97 22Q13 22 13.73 21.27Q14.47 20.53 14.47 19.47V19.07Q15.8 18.6 16.87 17.67L17.27 17.87Q18.13 18.4 19.13 18.13Q20.13 17.87 20.67 16.97Q21.2 16.07 20.93 15.07Q20.67 14.07 19.73 13.53ZM17.6 10.47Q17.87 11.27 17.87 12Q17.87 12.73 17.6 13.53Q17.53 13.8 17.63 14.07Q17.73 14.33 18 14.47L18.93 15Q19.2 15.2 19.3 15.53Q19.4 15.87 19.23 16.17Q19.07 16.47 18.73 16.57Q18.4 16.67 18.07 16.47L17.2 15.93Q16.93 15.8 16.67 15.83Q16.4 15.87 16.2 16.07Q15 17.27 13.47 17.67Q13.2 17.73 13.03 17.97Q12.87 18.2 12.87 18.47V19.53Q12.87 19.87 12.6 20.1Q12.33 20.33 12 20.33Q11.67 20.33 11.43 20.1Q11.2 19.87 11.2 19.53V18.47Q11.2 18.2 11 17.97Q10.8 17.73 10.53 17.67Q9 17.27 7.87 16.07Q7.6 15.8 7.3 15.8Q7 15.8 6.8 15.93L5.93 16.47Q5.6 16.67 5.27 16.57Q4.93 16.47 4.77 16.17Q4.6 15.87 4.7 15.53Q4.8 15.2 5.07 15L6 14.47Q6.2 14.33 6.33 14.07Q6.47 13.8 6.4 13.53Q6.13 12.73 6.13 12Q6.13 11.27 6.4 10.47Q6.47 10.2 6.33 9.93Q6.2 9.67 6 9.53L5.07 9Q4.8 8.8 4.7 8.47Q4.6 8.13 4.77 7.83Q4.93 7.53 5.27 7.43Q5.6 7.33 5.93 7.53L6.8 8.07Q7.07 8.2 7.33 8.17Q7.6 8.13 7.8 7.93Q8.93 6.73 10.53 6.33Q10.8 6.27 10.97 6.03Q11.13 5.8 11.13 5.53V4.47Q11.13 4.13 11.4 3.9Q11.67 3.67 12 3.67Q12.33 3.67 12.57 3.9Q12.8 4.13 12.8 4.47V5.53Q12.8 5.8 13 6.03Q13.2 6.27 13.47 6.33Q15 6.73 16.13 7.93Q16.33 8.13 16.63 8.17Q16.93 8.2 17.2 8.07L18.07 7.53Q18.4 7.33 18.7 7.43Q19 7.53 19.2 7.83Q19.4 8.13 19.3 8.47Q19.2 8.8 18.93 9L18 9.53Q17.73 9.67 17.63 9.93Q17.53 10.2 17.6 10.47ZM13.47 8.8 12.13 15.47Q12.07 15.8 11.83 15.97Q11.6 16.13 11.33 16.13H11.2Q10.8 16.07 10.63 15.8Q10.47 15.53 10.53 15.13L11.87 8.47Q11.93 8.13 12.2 7.97Q12.47 7.8 12.83 7.87Q13.2 7.93 13.37 8.2Q13.53 8.47 13.47 8.8ZM9.67 11.07 8.67 12.07 9.67 13.07Q9.93 13.27 9.93 13.63Q9.93 14 9.7 14.23Q9.47 14.47 9.1 14.47Q8.73 14.47 8.47 14.2L7.47 13.2Q7 12.73 7 12.03Q7 11.33 7.47 10.87L8.47 9.87Q8.73 9.6 9.07 9.6Q9.4 9.6 9.67 9.87Q9.93 10.13 9.93 10.47Q9.93 10.8 9.67 11ZM16.53 10.87Q17 11.33 17 12.03Q17 12.73 16.53 13.2L15.53 14.2Q15.27 14.47 14.93 14.47Q14.6 14.47 14.33 14.23Q14.07 14 14.07 13.63Q14.07 13.27 14.33 13.07L15.33 12.07L14.33 11.07Q14.07 10.8 14.07 10.47Q14.07 10.13 14.33 9.87Q14.6 9.6 14.93 9.6Q15.27 9.6 15.53 9.87Z" /></svg>;
}

// ───────────────────────────────────────────────────────────────
// Appearance - user theming (animations / density / ambient accent).
const ACCENT_SWATCHES: { hex: string; label: string }[] = [
  { hex: "#00ffe0", label: "טורקיז" },
  { hex: "#fff700", label: "צהוב" },
  { hex: "#7c3aed", label: "סגול" },
  { hex: "#22c55e", label: "ירוק" },
  { hex: "#ff4d8d", label: "ורוד" },
  { hex: "#3b82f6", label: "כחול" },
  { hex: "#ff8a3d", label: "כתום" },
  { hex: "#14b8a6", label: "טורקיז-ים" },
  { hex: "#6366f1", label: "אינדיגו" },
  { hex: "#f43f5e", label: "אדום ורדרד" },
  { hex: "#38bdf8", label: "תכלת" },
  { hex: "#a3e635", label: "ליים" },
];
// Two-tone ambient swatches - a soft wash of two colours in one circle. Curated
// to be tasteful (analogous / pleasing pairs).
const DUAL_SWATCHES: { hex: string; hex2: string; label: string }[] = [
  { hex: "#00ffe0", hex2: "#7c3aed", label: "טורקיז-סגול" },
  { hex: "#3b82f6", hex2: "#00ffe0", label: "כחול-טורקיז" },
  { hex: "#ff4d8d", hex2: "#ff8a3d", label: "ורוד-כתום" },
  { hex: "#7c3aed", hex2: "#ff4d8d", label: "סגול-ורוד" },
  { hex: "#22c55e", hex2: "#00ffe0", label: "ירוק-טורקיז" },
  { hex: "#6366f1", hex2: "#22d3ee", label: "אינדיגו-תכלת" },
  { hex: "#f43f5e", hex2: "#fb923c", label: "שקיעה" },
  { hex: "#0ea5e9", hex2: "#a855f7", label: "כחול-סגול" },
];

function AppearanceSettings({ reportStatus }: { reportStatus: (t: string, w?: boolean) => void }) {
  const [animLevel, setAnimLevelState] = useState<AnimLevel>(getAnimLevel());
  const [textScale, setTextScaleState] = useState<number>(getTextScale());
  const [accent, setAccentState]   = useState<string>(getAccent());
  const [accent2, setAccent2State] = useState<string>(getAccent2());
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

  const onAnimLevel = (next: AnimLevel) => {
    setAnimLevel(next); setAnimLevelState(next);
    reportStatus({
      high:   "אנימציות: מלאה - זכוכית על כל הכפתורים",
      normal: "אנימציות: רגילה",
      low:    "אנימציות: מופחתת - תנועה חיונית בלבד",
      off:    "אנימציות: כבויה - מצב מהיר",
    }[next]);
  };
  const onTextScale = (px: number) => {
    setTextScale(px); setTextScaleState(px);
    reportStatus(`גודל הטקסט: ${Math.round((px / 16) * 100)}%`);
  };
  const onAccent = (hex: string) => {
    setAccentPref(hex); setAccent2Pref(hex);      // solid → secondary == primary
    setAccentState(hex); setAccent2State(hex);
    setRainbow(false); setRainbowState(false);   // picking a solid colour exits "colourful"
    applyAccentNow(hex);   // live-paint the ambient background now (both tones = hex)
    reportStatus("צבע האווירה עודכן");
  };
  const onDualAccent = (hex: string, hex2: string) => {
    setAccentPref(hex); setAccent2Pref(hex2);
    setAccentState(hex); setAccent2State(hex2);
    setRainbow(false); setRainbowState(false);
    applyAccentNow(null);   // re-read both prefs → two-tone ambient live
    reportStatus("צבע האווירה עודכן");
  };
  const onSidebar = (m: SidebarMode) => {
    setSidebarMode(m); setSbMode(m);
    reportStatus("מצב הסרגל עודכן");
  };

  return (
    <>
      <section className="glass rounded-2xl p-6 mb-6">
        <h2 className="text-lg font-bold text-white mb-4 text-right">תנועה, צלילים וטקסט</h2>
        <div className="mb-1 text-right">
          <div className="text-white font-semibold">אנימציות ואפקטים</div>
          <p className="text-slate-400 text-xs mt-1 mb-3 leading-relaxed">
            עוצמת התנועה והזכוכית בממשק. ככל שנמוך יותר - קל יותר למחשב.
          </p>
        </div>
        <SegmentedControl<AnimLevel>
          ariaLabel="עוצמת אנימציות"
          value={animLevel}
          onChange={onAnimLevel}
          options={[
            { value: "high",   label: "מלאה",   hint: "זכוכית על הכל" },
            { value: "normal", label: "רגילה",  hint: "ברירת מחדל" },
            { value: "low",    label: "מופחתת", hint: "תנועה חיונית בלבד" },
            { value: "off",    label: "כבויה",  hint: "ללא תנועה" },
          ]}
        />
        <div className="h-px bg-white/10 my-4" />
        <ToggleRow
          enabled={sounds}
          busy={false}
          onChange={onSounds}
          title="צלילי ממשק"
          subtitle="צליל קליק עדין בלחיצות. כבוי כברירת מחדל - הפעל אם אתה אוהב משוב קולי."
          disabled={false}
        />
        <div className="h-px bg-white/10 my-4" />
        <div>
          {/* EXACTLY the ToggleRow layout so this row lines up with the others:
              the CONTROL (here the % badge) is the FIRST child → it sits in the
              same right-hand column as the toggles, and the title+description is a
              `flex-1 text-right` block → "גודל הטקסט" lands on the SAME right edge
              as "אנימציות ואפקטים" / "צלילי ממשק". */}
          <div className="flex items-start gap-4 mb-3">
            <span className="w-12 shrink-0 flex justify-center">
              <span className="text-[11px] font-bold tabular-nums text-[#00ffe0]
                               bg-[#00ffe0]/10 border border-[#00ffe0]/25 rounded-md px-1.5 py-0.5">
                {Math.round((textScale / 16) * 100)}%
              </span>
            </span>
            <div className="flex-1 text-right">
              <div className="text-white font-bold">גודל הטקסט</div>
              <div className="text-slate-400 text-xs mt-1 leading-relaxed">החלק כדי להגדיל או להקטין את הטקסט בכל התוכנה (75%-125%).</div>
            </div>
            <button
              type="button"
              onClick={() => onTextScale(16)}
              disabled={textScale === 16}
              title="חזרה לגודל המקורי (100%)"
              aria-label="איפוס גודל הטקסט לברירת המחדל"
              className="shrink-0 grid place-items-center w-8 h-8 rounded-lg border border-white/10
                         text-slate-300 hover:text-white hover:bg-white/5 transition
                         disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="currentColor"
                   strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                <path d="M3 12a9 9 0 1 0 2.6-6.4L3 8" />
                <path d="M3 3v5h5" />
              </svg>
            </button>
          </div>
          <input
            type="range"
            min={12}
            max={20}
            step={0.8}
            value={textScale}
            onChange={(e) => onTextScale(Number(e.target.value))}
            aria-label="גודל הטקסט"
            dir="ltr"
            className="w-full h-2 cursor-pointer accent-[#00ffe0]"
          />
          <div className="flex justify-between mt-2 text-[11px] text-slate-400" dir="ltr">
            <span>טקסט קטן יותר</span>
            <span>טקסט גדול יותר</span>
          </div>
        </div>
      </section>

      <section className="glass rounded-2xl p-6 mb-6">
        <h2 className="text-lg font-bold text-white mb-2 text-right">סרגל הצד</h2>
        <p className="text-slate-400 text-xs mb-4 text-right leading-relaxed">
          איך הסרגל הצדדי מתנהג. ברירת מחדל: ריחוף - נפתח כשמעבירים עליו עכבר.
        </p>
        <SegmentedControl<SidebarMode>
          ariaLabel="מצב סרגל הצד"
          value={sbMode}
          onChange={onSidebar}
          options={[
            { value: "auto",   label: "ריחוף",       hint: "נפתח במעבר עכבר" },
            { value: "wide",   label: "נעול רחב",    hint: "תמיד פתוח" },
            { value: "narrow", label: "נעול מצומצם", hint: "תמיד מצומצם" },
          ]}
        />
      </section>

      <section className="glass rounded-2xl p-6">
        <h2 className="text-lg font-bold text-white mb-2 text-right">צבע אווירה</h2>
        <p className="text-slate-400 text-xs mb-4 text-right leading-relaxed">
          הצבע שצובע את רקע התוכנה כשאין משחק פתוח. בתוך עמוד משחק הרקע נצבע אוטומטית בצבע הכותר.
        </p>
        <div className="flex gap-3 justify-end flex-wrap">
          {/* Colourful / rainbow - a soft multi-colour ambient wash. */}
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
            const on = !rainbow && accent.toLowerCase() === s.hex.toLowerCase()
              && accent2.toLowerCase() === s.hex.toLowerCase();
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
          {/* Two-tone swatches - two colours blended in one circle. */}
          {DUAL_SWATCHES.map((s) => {
            const on = !rainbow && accent.toLowerCase() === s.hex.toLowerCase()
              && accent2.toLowerCase() === s.hex2.toLowerCase();
            const grad = `linear-gradient(135deg, ${s.hex} 0%, ${s.hex2} 100%)`;
            return (
              <button
                key={s.hex + s.hex2}
                type="button"
                onClick={() => onDualAccent(s.hex, s.hex2)}
                title={s.label}
                aria-label={s.label}
                className="w-10 h-10 rounded-full transition-transform hover:scale-110 grid place-items-center"
                style={{ background: grad, boxShadow: on ? `0 0 0 3px #0a0a14, 0 0 0 5px ${s.hex2}` : `0 4px 12px -4px ${s.hex}99` }}
              >
                {on && <span className="text-white text-lg font-black drop-shadow-[0_1px_2px_rgba(0,0,0,0.8)]">✓</span>}
              </button>
            );
          })}
        </div>
      </section>

      <AppIconPicker reportStatus={reportStatus} />
    </>
  );
}

// ───────────────────────────────────────────────────────────────
// App icon picker - switch the icon shown in the taskbar, folder-shortcut
// and window (+ tray) between the brand default and a circle / rounded-square
// frame. Applies LIVE (window + taskbar + tray) and repoints the launch
// shortcuts; the raw .exe icon in Explorer stays the build default.
function AppIconPicker({ reportStatus }: { reportStatus: (t: string, w?: boolean) => void }) {
  const [variant, setVariant] = useState<string>("");
  const [options, setOptions] = useState<AppIconOption[]>([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let alive = true;
    api.getAppIcon()
      .then((s) => { if (alive) { setVariant(s.variant); setOptions(s.options); } })
      .catch(() => {});
    return () => { alive = false; };
  }, []);

  // Parse the current variant into its axes so the controls reflect it.
  // "brand" is the standalone default logo (not in the style grid) - when it's
  // active the grid controls fall back to a neutral style so clicking one just
  // switches away from brand.
  // The picker offers the two brand CHROME badges (matching the website) -
  // circle (the default) and rounded-square. Only the frame shape is selectable.
  const brandForShape = (sh: string) =>
    options.find((o) => o.style === "brand" && o.shape === sh);

  /** The SHAPE the active variant represents - drives which segment is lit.
   *  Falls back to "circle" (the default badge) for anything unknown, so the
   *  control always shows a definite selection rather than an empty row. */
  const shapeOf = (id: string): string =>
    options.find((o) => o.id === id)?.shape === "square" ? "square" : "circle";

  const apply = (id: string | undefined) => {
    if (!id || id === variant || busy) return;
    setBusy(true);
    setVariant(id);   // optimistic
    api.setAppIcon(id)
      .then((r) => {
        if (r?.variant) setVariant(r.variant);   // sync to the REAL effective variant
        // Honour the backend's ok flag - it returns ok:false (and the previous
        // variant) when the id is invalid or the apply failed. Don't claim success.
        if (r?.ok) reportStatus("אייקון התוכנה עודכן");
        else reportStatus("החלפת האייקון נכשלה", true);
      })
      .catch(() => reportStatus("החלפת האייקון נכשלה", true))
      .finally(() => setBusy(false));
  };

  return (
    <section className="glass rounded-2xl p-6 mt-6">
      <h2 className="text-lg font-bold text-white mb-2 text-right">אייקון התוכנה</h2>
      <p className="text-slate-400 text-xs mb-4 text-right leading-relaxed">
        האייקון שרואים בשורת המשימות, בקיצור הדרך ובחלון התוכנה. אפשר להחליף בין צורת עיגול
        לריבוע מעוגל. ההחלפה מיידית (האייקון בקובץ ה-exe עצמו נשאר ברירת המחדל).
      </p>

      {/* The two brand CHROME badges - circle (default) / rounded-square.
          Same segmented control as every other choice in the app; the icon each
          option APPLIES is its own glyph, so you still pick by seeing it. */}
      <SegmentedControl<string>
        ariaLabel="צורת אייקון התוכנה"
        value={shapeOf(variant)}
        onChange={(sh) => apply(brandForShape(sh)?.id)}
        disabled={busy}
        showHints={false}
        options={([["circle", "עיגול"], ["square", "ריבוע מעוגל"]] as [string, string][])
          .map(([k, label]) => {
            const opt = brandForShape(k);
            return {
              value: k,
              label,
              title: label,
              icon: opt ? (
                <img src={`./${opt.thumb}`} alt="" aria-hidden
                     className="w-9 h-9 object-contain select-none" draggable={false} />
              ) : undefined,
            };
          })}
      />
    </section>
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
