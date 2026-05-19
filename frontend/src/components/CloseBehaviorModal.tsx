// First-launch close-behavior modal.
//
// Shown by App.tsx the first time the launcher starts AND no
// closeBehavior preference exists yet. The user picks either
// "minimise to tray" or "close completely"; if they tick the
// "remember" checkbox the choice is persisted and this modal never
// reappears. With the checkbox off we apply the choice once for this
// session — the next launcher boot prompts again.
//
// We can't truly intercept Windows' "X" click (Eel + Chrome --app has
// no hook for that — see the discussion in main_eel._on_window_closed)
// so this is the cleanest way to honour the SPIRIT of the request:
// "ask once, remember forever, behave silently from then on".
import { useState } from "react";
import { api } from "../lib/eel";
import type { LauncherPrefs } from "../lib/types";

interface Props {
  onResolved: (next: LauncherPrefs) => void;
}

type Choice = "minimize" | "close";

export default function CloseBehaviorModal({ onResolved }: Props) {
  const [choice,   setChoice]   = useState<Choice>("minimize");
  const [remember, setRemember] = useState(true);
  const [busy,     setBusy]     = useState(false);

  const submit = async () => {
    setBusy(true);
    try {
      if (remember) {
        const r = await api.setCloseBehavior(choice);
        onResolved({ closeBehavior: r.closeBehavior, startWithOs: r.startWithOs });
      } else {
        // One-time choice — don't persist. Resolve with the choice for
        // this session only; the next boot will see closeBehavior=null
        // and re-prompt.
        onResolved({ closeBehavior: choice, startWithOs: false });
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-6"
         style={{ background: "rgba(0,0,0,0.72)", backdropFilter: "blur(12px)" }}>
      <div
        className="w-full max-w-lg rounded-3xl border border-white/10 p-8 animate-scale-in"
        style={{
          background: "linear-gradient(135deg, rgba(15,15,30,0.95) 0%, rgba(8,8,16,0.95) 100%)",
          boxShadow:  "0 30px 80px -20px rgba(0,0,0,0.85), 0 0 60px -20px rgba(255,247,0,0.25)",
        }}
      >
        <div className="flex items-center gap-3 mb-4">
          <div className="w-12 h-12 rounded-2xl bg-brand-yellow grid place-items-center
                          shadow-[0_8px_24px_-8px_rgba(255,247,0,0.6)]">
            <span className="text-brand-ink font-extrabold text-2xl">✕</span>
          </div>
          <div className="leading-tight">
            <h2 className="text-white font-extrabold text-lg">סגירת התוכנה</h2>
            <p className="text-slate-400 text-xs">בחירה חד-פעמית — אפשר לשנות בהגדרות בכל רגע</p>
          </div>
        </div>

        <p className="text-slate-200 mb-5 leading-relaxed">
          כיצד תרצה שפעולת הסגירה תתנהג כאשר תלחץ על כפתור ה-✕?
        </p>

        <div className="grid grid-cols-1 gap-2.5 mb-5">
          <OptionCard
            active={choice === "minimize"}
            onClick={() => setChoice("minimize")}
            accent="#22c55e"
            title="מזער לרקע"
            subtitle="התוכנה תמשיך לרוץ בשקט במגש המערכת (system tray) ללא השפעה על ביצועי המחשב"
            icon={<MinimizeIcon />}
          />
          <OptionCard
            active={choice === "close"}
            onClick={() => setChoice("close")}
            accent="#ef4444"
            title="סגור לצמיתות"
            subtitle="התוכנה תיסגר לחלוטין; כדי לפתוח שוב יש להפעיל את הלאנצ׳ר מההתחלה"
            icon={<CloseIcon />}
          />
        </div>

        <label className="flex items-center gap-3 mb-6 cursor-pointer select-none
                          rounded-xl px-3 py-2.5 border border-white/10 bg-white/[0.03]
                          hover:bg-white/[0.05] transition">
          <input
            type="checkbox"
            checked={remember}
            onChange={(e) => setRemember(e.target.checked)}
            className="w-4 h-4 accent-brand-yellow"
          />
          <span className="text-sm text-slate-200">זכור את בחירתי לתמיד</span>
          <span className="text-[10px] text-slate-500 mr-auto">
            ניתן לשנות מאוחר יותר בהגדרות
          </span>
        </label>

        <button
          type="button"
          disabled={busy}
          onClick={submit}
          className="w-full py-3 rounded-xl bg-brand-yellow hover:bg-yellow-300
                     text-brand-ink font-extrabold transition
                     disabled:opacity-50 disabled:cursor-wait
                     shadow-[0_10px_30px_-10px_rgba(255,247,0,0.6)]"
        >
          {busy ? "שומר…" : "אישור"}
        </button>
      </div>
    </div>
  );
}

// ───────────────────────────────────────────────────────────────
function OptionCard({
  active, onClick, accent, title, subtitle, icon,
}: {
  active:   boolean;
  onClick:  () => void;
  accent:   string;
  title:    string;
  subtitle: string;
  icon:     React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="text-right flex items-start gap-3 p-4 rounded-2xl border transition
                 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/30"
      style={{
        background:  active ? `${accent}15` : "rgba(255,255,255,0.02)",
        borderColor: active ? `${accent}88` : "rgba(255,255,255,0.08)",
        boxShadow:   active ? `0 8px 24px -10px ${accent}66` : "none",
      }}
    >
      <div
        className="w-10 h-10 rounded-xl grid place-items-center shrink-0"
        style={{ background: `${accent}25`, color: accent }}
      >
        {icon}
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-white font-bold leading-tight">{title}</div>
        <div className="text-slate-400 text-xs mt-1 leading-relaxed">{subtitle}</div>
      </div>
      <div
        className="w-5 h-5 rounded-full border-2 grid place-items-center shrink-0 mt-0.5"
        style={{ borderColor: active ? accent : "rgba(255,255,255,0.25)" }}
      >
        {active && <span className="w-2.5 h-2.5 rounded-full" style={{ background: accent }} />}
      </div>
    </button>
  );
}

function MinimizeIcon() {
  return (
    <svg viewBox="0 0 24 24" width={20} height={20} fill="none"
         stroke="currentColor" strokeWidth={2.4}
         strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M5 13h14" />
      <path d="M5 19h14" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg viewBox="0 0 24 24" width={20} height={20} fill="none"
         stroke="currentColor" strokeWidth={2.4}
         strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M6 6l12 12" />
      <path d="M18 6L6 18" />
    </svg>
  );
}
