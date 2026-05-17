// Settings — currently holds a quick app-info block and a list of
// games with overridden paths. Hooks straight into the eel API.
import type { Game } from "../lib/types";
import { api } from "../lib/eel";

interface Props {
  games: Game[];
  reportStatus: (text: string, warn?: boolean) => void;
  onRefresh: () => Promise<void>;
  version:  string;
}

export default function SettingsView({ games, reportStatus, onRefresh, version }: Props) {
  const overridden = games.filter((g) => g.install_path);

  const handleOpen = async (p: string) => {
    const r = await api.openFolder(p);
    if (!r.ok) reportStatus(r.error ?? "שגיאה", true);
  };

  const handleClear = async (id: string) => {
    await api.clearCustomPath(id);
    reportStatus("נתיב נמחק");
    await onRefresh();
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
