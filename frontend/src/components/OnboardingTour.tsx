// First-run onboarding - a short animated multi-step welcome. Shown once
// (localStorage 'onboardingDone'); skippable. Robust modal carousel (no
// fragile element-anchored coachmarks).
import { useEffect, useState, type ReactNode } from "react";
import { IconAppOnboardingStepWelcome, IconAppOnboardingStepTheme } from "./UiIcons";

const STEPS: { icon: ReactNode; title: string; body: string }[] = [
  { icon: <IconAppOnboardingStepWelcome width={30} />, title: "ברוך הבא למנהל התרגומים",
    body: "המרכז החכם שלך לניהול והתקנת תרגומים עבריים למשחקי PC - מאובטח, מהיר, ומעוצב בסטנדרט הגבוה ביותר. הסיור קצר, ואפשר לדלג בכל שלב." },
  { icon: "🔍", title: "שלב 1 - שהתוכנה תמצא את המשחק",
    body: "היכנס ל'ספרייה'. משחקים מותקנים מזוהים אוטומטית. לא רואה את המשחק? לחץ 'סריקת כוננים מלאה' לסריקת כל הכוננים, או פתח את כרטיס המשחק והזן ידנית את הנתיב המלא לתיקיית ההתקנה." },
  { icon: "⬇️", title: "שלב 2 - התקנת התרגום",
    body: "פתח את כרטיס המשחק ולחץ 'התקן תרגום'. התוכנה מורידה ומתקינה את המוד עבורך, עם סרגל התקדמות. תרגומים בתשלום נפתחים אחרי רכישה; השאר חינמיים." },
  { icon: "✅", title: "שלב 3 - הפעלה בתוך המשחק",
    body: "אחרי ההתקנה - בכרטיס המשחק בחר 'שפת המשחק: עברית'. במשחק עצמו הגדר את שפת הטקסט/כתוביות ל-العربية (הערבית) פעם אחת, והעברית תופיע. הכול הפיך בלחיצה." },
  { icon: <IconAppOnboardingStepTheme width={30} />, title: "כל משחק וצבע משלו",
    body: "כשנכנסים לעמוד משחק - כל התוכנה נצבעת בצבע הכותר. אפשר לכוונן צבע אווירה, גודל טקסט ואנימציות ב'הגדרות → מראה'." },
  { icon: "🕹️", title: "שליטה מלאה במקלדת ובשלט",
    body: "נווט עם החיצים או ה-D-pad, הפעל ב-Enter / כפתור A, וחזור עם Backspace / כפתור B. אפשר לפתוח שוב את המדריך הזה בכל עת מ'הגדרות → כללי'." },
];

export default function OnboardingTour({ onClose }: { onClose: () => void }) {
  const [i, setI] = useState(0);
  const last = i === STEPS.length - 1;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      else if (e.key === "ArrowLeft" || e.key === "Enter") { e.preventDefault(); setI((x) => Math.min(STEPS.length - 1, x + 1)); }
      else if (e.key === "ArrowRight") { e.preventDefault(); setI((x) => Math.max(0, x - 1)); }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const s = STEPS[i];
  return (
    <div className="fixed inset-0 z-[150] grid place-items-center p-4"
         style={{ direction: "rtl", background: "rgba(0,0,0,0.78)", backdropFilter: "blur(12px)" }}>
      <div className="w-full max-w-md rounded-2xl border border-white/10 bg-slate-900/92 backdrop-blur-2xl
                      shadow-[0_30px_70px_-20px_rgba(0,0,0,0.85)] overflow-hidden">
        <div className="relative px-7 py-8 text-center">
          <div className="absolute -top-12 left-1/2 -translate-x-1/2 w-56 h-40 rounded-full bg-brand-cyan/15 blur-3xl" aria-hidden />
          <div key={i} className="relative animate-scale-in">
            <div className="text-5xl mb-4">{s.icon}</div>
            <h3 className="text-white font-extrabold text-xl mb-2">{s.title}</h3>
            <p className="text-slate-300 text-sm leading-relaxed">{s.body}</p>
          </div>
        </div>
        {/* dots */}
        <div className="flex justify-center gap-2 pb-4">
          {STEPS.map((_, k) => (
            <span key={k} className="h-1.5 rounded-full transition-all duration-300"
                  style={{ width: k === i ? 22 : 7, background: k === i ? "#00ffe0" : "rgba(255,255,255,0.3)" }} />
          ))}
        </div>
        {/* footer */}
        <div className="px-7 py-4 border-t border-white/5 flex items-center justify-between">
          <button type="button" onClick={onClose}
                  className="text-xs text-slate-400 hover:text-slate-200 transition">דלג</button>
          <div className="flex gap-2">
            {i > 0 && (
              <button type="button" onClick={() => setI((x) => x - 1)}
                      className="px-4 py-2 rounded-xl bg-white/5 border border-white/10 text-slate-200 hover:bg-white/10 text-sm font-semibold transition">
                הקודם
              </button>
            )}
            <button type="button"
                    onClick={() => last ? onClose() : setI((x) => x + 1)}
                    className="group relative overflow-hidden px-5 py-2 rounded-xl bg-brand-cyan text-brand-ink text-sm font-bold transition hover:brightness-110">
              <span className="sheen-layer" aria-hidden />
              {last ? "בואו נתחיל ▸" : "הבא"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
