// Right-side nav (RTL): brand, three nav rows, bottom "settings + refresh"
// panel, version footer. The bottom panel replaces the old UpdatesMenu —
// updates now live in the dedicated /downloads view.
import { useMemo, useState, type ComponentType, type SVGProps } from "react";
import { HomeIcon, LibraryIcon, DownloadsIcon, SettingsIcon } from "./NavIcons";

export type NavKey = "home" | "library" | "downloads" | "settings";

interface NavDef {
  key:    NavKey;
  label:  string;
  Icon:   ComponentType<SVGProps<SVGSVGElement>>;
  accent: string;
}

// "settings" intentionally NOT in this list — it now sits in the bottom
// panel alongside the refresh button.
const NAV: NavDef[] = [
  { key: "home",      label: "דף הבית",         Icon: HomeIcon,      accent: "#fff700" },
  { key: "library",   label: "ספרייה",          Icon: LibraryIcon,   accent: "#d4af37" },
  { key: "downloads", label: "הורדות ועדכונים", Icon: DownloadsIcon, accent: "#22c55e" },
];

interface Props {
  current: NavKey;
  onNavigate: (key: NavKey) => void;
  onRefresh: () => Promise<void>;
}

export default function Sidebar({ current, onNavigate, onRefresh }: Props) {
  const year = useMemo(() => new Date().getFullYear(), []);
  return (
    <aside className="glass-strong rounded-2xl flex flex-col w-[230px] flex-shrink-0 p-3 gap-3">
      {/* Brand block */}
      <div className="flex items-center justify-end gap-3 px-2 pt-2 pb-3
                      border-b border-white/5">
        <div className="text-right">
          <div className="font-bold text-white text-[15px] leading-tight">פרויקט התרגום</div>
          <div className="font-display text-[8px] tracking-[0.25em] text-brand-cyan mt-0.5">
            H E B R E W &nbsp; A I
          </div>
        </div>

        {/* NEW AAA NEON BRAND AVATAR WITH IMAGE */}
        <div className="relative flex items-center justify-center w-11 h-11 rounded-full bg-[#1a0d40] border-[1.5px] border-[#00ffe0] shadow-[0_0_12px_rgba(0,255,224,0.4)] overflow-hidden shrink-0 transition-all duration-300 hover:scale-105 hover:shadow-[0_0_20px_rgba(0,255,224,0.7)] group">
          {/* אפקט הארה פנימי במעבר עכבר שמונח מעל התמונה */}
          <div className="absolute inset-0 bg-gradient-to-br from-[#00ffe0]/30 to-[#fff700]/30 opacity-0 group-hover:opacity-100 transition-opacity duration-300 z-10 pointer-events-none" />

          {/* התמונה מהאתר (וודא שהשם profile.png תואם לקובץ ששמת בתיקיית public) */}
          <img
            src="/profile.png"
            alt="User Profile"
            className="w-full h-full object-cover relative z-0"
            onError={(e) => {
              // במקרה שהתמונה לא נמצאת, נחזור לאות "ת" בתור גיבוי
              e.currentTarget.style.display = 'none';
              e.currentTarget.nextElementSibling?.classList.remove('hidden');
            }}
          />
          <span className="hidden text-[#fff700] font-black text-xl tracking-tighter drop-shadow-[0_0_8px_rgba(255,247,0,0.9)] z-10" style={{ fontFamily: 'system-ui, sans-serif', paddingBottom: '2px' }}>
            ת
          </span>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex flex-col gap-1 mt-1">
        {NAV.map(({ key, label, Icon, accent }) => {
          const active = key === current;
          return (
            <button
              key={key}
              onClick={() => onNavigate(key)}
              className={[
                "group relative flex items-center gap-3 text-right",
                "rounded-xl pr-3 pl-3 py-3 transition-all duration-150",
                active
                  ? "bg-white/[0.08] text-white"
                  : "text-slate-400 hover:bg-white/[0.04] hover:text-slate-200",
              ].join(" ")}
            >
              <span
                className={[
                  "absolute right-0 top-2 bottom-2 w-[3px] rounded-full transition-opacity",
                  active ? "opacity-100" : "opacity-0",
                ].join(" ")}
                style={{ background: accent }}
              />
              <span className="flex-1 text-[14px] font-medium">{label}</span>
              <Icon
                className="transition-colors"
                style={{ color: active ? accent : undefined }}
              />
            </button>
          );
        })}
      </nav>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Bottom action panel — Settings + Refresh */}
      <SettingsPanel
        active={current === "settings"}
        onOpen={() => onNavigate("settings")}
        onRefresh={onRefresh}
      />

      <div className="text-center text-[10px] text-slate-500 pb-1">
        v1.0  •  © {year}
      </div>
    </aside>
  );
}

function SettingsPanel({
  active, onOpen, onRefresh,
}: {
  active: boolean;
  onOpen: () => void;
  onRefresh: () => Promise<void>;
}) {
  const [spinning, setSpinning] = useState(false);

  const handleRefresh = async (e: React.MouseEvent) => {
    e.stopPropagation();           // don't trigger the Settings click
    if (spinning) return;
    setSpinning(true);
    try {
      await onRefresh();
    } finally {
      // Keep the animation visible for at least 400ms so the click
      // feels responsive even on a fast network.
      setTimeout(() => setSpinning(false), 400);
    }
  };

  return (
    <div className="flex items-stretch gap-2">
      {/* Settings — primary, flex-1 */}
      <button
        onClick={onOpen}
        className={[
          "flex-1 rounded-xl border transition flex items-center justify-end gap-3 p-3 group",
          active
            ? "bg-white/[0.10] border-white/15 text-white"
            : "bg-white/[0.04] border-white/5 hover:bg-white/[0.07] hover:border-white/10",
        ].join(" ")}
      >
        <div className="text-right flex-1">
          <div className="text-white font-semibold leading-tight text-[13px]">
            הגדרות
          </div>
          <div className="text-slate-400 text-[10px]">נתיבים וגרסה</div>
        </div>
        <div className="relative w-10 h-10 rounded-xl bg-[#00ffe0] grid place-items-center
                        shadow-[0_4px_14px_-4px_rgba(0,255,224,0.5)]
                        group-hover:scale-105 transition">
          <SettingsIcon className="w-5 h-5 text-brand-ink" />
        </div>
      </button>

      {/* Refresh — compact icon-only square */}
      <button
        onClick={handleRefresh}
        disabled={spinning}
        title="רענון מהשרת"
        aria-label="רענון מהשרת"
        className={[
          "w-12 rounded-xl border transition grid place-items-center group",
          "bg-white/[0.04] border-white/5 hover:bg-white/[0.07] hover:border-white/10",
          "disabled:opacity-60 disabled:cursor-wait",
        ].join(" ")}
      >
        <svg
          viewBox="0 0 24 24"
          className={[
            "w-5 h-5 text-slate-200 transition-transform",
            spinning ? "animate-spin" : "group-hover:rotate-90",
          ].join(" ")}
          fill="none"
          stroke="currentColor"
          strokeWidth={2.2}
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden
        >
          <path d="M21 12a9 9 0 1 1-3.1-6.8" />
          <path d="M21 4v5h-5" />
        </svg>
      </button>
    </div>
  );
}
