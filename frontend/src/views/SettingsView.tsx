// Settings — app info, lifecycle toggles, custom game paths.
//
// Lifecycle toggles bind directly to the launcher_prefs.json + Windows
// HKCU autostart registry entry through the eel bridge. The version
// string is fed in from APP_VERSION (locked at v1.1.0) so the small
// label at the sidebar footer and the "על האפליקציה" block stay in
// lockstep.
import { useState } from "react";
import type { Game, LauncherPrefs } from "../lib/types";
import { api } from "../lib/eel";

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
  const [busy, setBusy] = useState<"close" | "autostart" | null>(null);

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

  return (
    <div className="h-full overflow-y-auto px-8 py-6 animate-fade-in">
      <h1 className="text-3xl font-extrabold text-white mb-6 text-right">הגדרות</h1>

      <section className="glass rounded-2xl p-6 mb-6">
        <div className="flex items-baseline justify-between mb-3">
          <span dir="ltr" className="font-mono text-xs text-slate-400">
            {version}
          </span>
          <h2 className="text-lg font-bold text-white text-right">על האפליקציה</h2>
        </div>
        <p className="text-slate-300 text-sm leading-relaxed text-right">
          מנהל מודי תרגום עברי למשחקי PC. כלל הלוגיקה (זיהוי משחקים, הפעלה/השבתה/הסרה של מודים)
          מורצת ע״י Python בעוד שכל הממשק נבנה ב-React + Tailwind. הסגנון תואם את האתר הציבורי.
        </p>
      </section>

      <section className="glass rounded-2xl p-6 mb-6">
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

      <section className="glass rounded-2xl p-6">
        <h2 className="text-lg font-bold text-white mb-4 text-right">נתיבים מותאמים אישית</h2>
        {overridden.length === 0 ? (
          <div className="text-slate-400 text-sm text-right">
            אין נתיבים מותאמים. כשתגדיר נתיב ידני בכרטיס משחק הוא יופיע כאן.
          </div>
        ) : (
          <ul className="space-y-2">
            {overridden.map((g) => (
              <li
                key={g.id}
                className="flex items-center justify-between gap-3 bg-white/5 rounded-xl p-3"
              >
                <div className="flex gap-2">
                  <button
                    onClick={() => handleClear(g.id)}
                    className="text-xs px-3 py-1.5 border border-rose-500/30 text-rose-200
                               rounded-lg hover:bg-rose-500/10"
                  >
                    נקה
                  </button>
                  <button
                    onClick={() => g.install_path && handleOpen(g.install_path)}
                    className="text-xs px-3 py-1.5 bg-brand-yellow text-brand-ink rounded-lg
                               font-bold hover:bg-yellow-300"
                  >
                    פתח
                  </button>
                </div>
                <div className="flex-1 text-right">
                  <div dir="ltr" className="text-white font-semibold text-left">{g.titleEn}</div>
                  <div dir="ltr" className="text-slate-400 text-xs text-left mt-0.5 truncate">
                    {g.install_path}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
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
