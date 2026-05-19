// Right-side nav (RTL): brand, nav rows, bottom "settings + refresh"
// panel, version footer. The bottom panel replaces the old UpdatesMenu —
// updates now live in the dedicated /downloads view.
import { useEffect, useMemo, useState, type ComponentType, type SVGProps } from "react";
import { HomeIcon, LibraryIcon, DownloadsIcon, SettingsIcon, FolderIcon, AppsIcon } from "./NavIcons";
import { useLauncherAuth } from "../lib/useLauncherAuth";
import AuthModal from "./AuthModal";

export type NavKey = "home" | "games" | "apps" | "downloads" | "personal" | "settings";

interface NavLeaf {
  kind:   "leaf";
  key:    NavKey;
  label:  string;
  Icon:   ComponentType<SVGProps<SVGSVGElement>>;
  accent: string;
}

interface NavGroup {
  kind:     "group";
  id:       string;                                     // not a NavKey — header is non-routable
  label:    string;
  Icon:     ComponentType<SVGProps<SVGSVGElement>>;
  accent:   string;
  children: NavLeaf[];
}

type NavItem = NavLeaf | NavGroup;

// Small inline icon for the Personal Area row — kept inline so we don't
// need to touch NavIcons.tsx and risk another runtime mismatch.
function PersonIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth={2} strokeLinecap="round" strokeLinejoin="round"
         width={20} height={20} {...props}>
      <circle cx="12" cy="8" r="4" />
      <path d="M4 21c0-4 4-7 8-7s8 3 8 7" />
    </svg>
  );
}

// "settings" intentionally NOT in this list — it sits in the bottom
// panel alongside the refresh button. "personal" is added as a regular
// nav row (instead of overloading the auth-slot button) so the whole
// row tree stays simple and crash-free.
const NAV: NavItem[] = [
  { kind: "leaf",  key: "home", label: "דף הבית", Icon: HomeIcon, accent: "#fff700" },
  {
    kind:   "group",
    id:     "library",
    label:  "ספרייה",
    Icon:   FolderIcon,
    accent: "#d4af37",
    children: [
      { kind: "leaf", key: "games", label: "משחקים", Icon: LibraryIcon, accent: "#d4af37" },
      { kind: "leaf", key: "apps",  label: "תוכנות", Icon: AppsIcon,    accent: "#66c0f4" },
    ],
  },
  { kind: "leaf", key: "downloads", label: "הורדות ועדכונים", Icon: DownloadsIcon, accent: "#22c55e" },
  { kind: "leaf", key: "personal",  label: "אזור אישי",        Icon: PersonIcon,    accent: "#00ffe0" },
];

interface Props {
  current: NavKey;
  onNavigate: (key: NavKey) => void;
  onRefresh: () => Promise<void>;
  /** Dynamic version string from App.APP_VERSION (e.g. "v1.1.0").
   *  Replaces the previously hardcoded "v1.0" footer. */
  version: string;
}

export default function Sidebar({ current, onNavigate, onRefresh, version }: Props) {
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
        {NAV.map((item) =>
          item.kind === "leaf"
            ? <NavRow key={item.key} item={item} current={current} onNavigate={onNavigate} />
            : <NavGroupRow key={item.id} group={item} current={current} onNavigate={onNavigate} />
        )}
      </nav>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Auth slot — sign in / avatar + logout. The "אזור אישי" entry
          point lives in the main NAV list above (not here) so this row
          stays simple and HTML-valid (no nested clickables). */}
      <AuthSlot />

      {/* Bottom action panel — Settings + Refresh */}
      <SettingsPanel
        active={current === "settings"}
        onOpen={() => onNavigate("settings")}
        onRefresh={onRefresh}
      />

      <div className="text-center text-[10px] text-slate-500 pb-1 font-mono" dir="ltr">
        {version} • © {year}
      </div>
    </aside>
  );
}

// Standalone nav row (leaf). Mirrors the old map-callback markup so it
// stays visually identical to a top-level item.
function NavRow({
  item, current, onNavigate, indent = false,
}: {
  item:     NavLeaf;
  current:  NavKey;
  onNavigate: (key: NavKey) => void;
  indent?:  boolean;
}) {
  const active = item.key === current;
  return (
    <button
      onClick={() => onNavigate(item.key)}
      className={[
        "group relative flex items-center gap-3 text-right",
        "rounded-xl pl-3 py-2.5 transition-all duration-150",
        // RTL: indent pushes content away from the right edge.
        indent ? "pr-7 text-[13px]" : "pr-3 text-[14px]",
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
        style={{ background: item.accent }}
      />
      <span className="flex-1 font-medium">{item.label}</span>
      <item.Icon
        className="transition-colors"
        width={indent ? 16 : 20}
        height={indent ? 16 : 20}
        style={{ color: active ? item.accent : undefined }}
      />
    </button>
  );
}

// Non-routable section header + its indented children. Header highlights
// faintly when one of its children is the active view.
function NavGroupRow({
  group, current, onNavigate,
}: {
  group:     NavGroup;
  current:   NavKey;
  onNavigate: (key: NavKey) => void;
}) {
  const childActive = group.children.some((c) => c.key === current);
  return (
    <div className="flex flex-col">
      <div
        className={[
          "relative flex items-center gap-3 text-right",
          "rounded-xl pr-3 pl-3 py-2 cursor-default select-none",
          childActive ? "text-slate-100" : "text-slate-500",
        ].join(" ")}
      >
        <span
          className="absolute right-0 top-2 bottom-2 w-[2px] rounded-full opacity-30"
          style={{ background: group.accent }}
        />
        <span className="flex-1 text-[14px] font-semibold tracking-wide">
          {group.label}
        </span>
        <group.Icon
          width={18}
          height={18}
          style={{ color: childActive ? group.accent : undefined }}
        />
      </div>
      <div className="flex flex-col gap-0.5 mt-0.5">
        {group.children.map((child) => (
          <NavRow
            key={child.key}
            item={child}
            current={current}
            onNavigate={onNavigate}
            indent
          />
        ))}
      </div>
    </div>
  );
}

function AuthSlot() {
  const { user, signedIn, signOut, loading } = useLauncherAuth();
  const [modalOpen,        setModalOpen]        = useState(false);
  const [confirmLogout,    setConfirmLogout]    = useState(false);

  if (loading) {
    return (
      <div className="px-3 py-2 mx-2 rounded-xl bg-white/[0.03] text-[11px] text-slate-500 text-center">
        ...
      </div>
    );
  }

  if (!signedIn) {
    return (
      <>
        <div className="px-2 mb-2">
          <button
            type="button"
            onClick={() => setModalOpen(true)}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-xl
                       bg-[#00ffe0]/10 border border-[#00ffe0]/30 text-[#00ffe0]
                       hover:bg-[#00ffe0]/20 transition text-xs font-semibold"
            title="פותח חלון התחברות/הרשמה בתוך הלאנצ׳ר"
          >
            <span>🔐 התחברות/הרשמה</span>
          </button>
        </div>
        <AuthModal open={modalOpen} onClose={() => setModalOpen(false)} />
      </>
    );
  }

  const initials = (user?.fullName || user?.email || '??').slice(0, 2).toUpperCase();

  return (
    <div className="px-2 mb-2">
      <div className="flex items-center gap-2 px-2 py-2 rounded-xl
                      bg-white/[0.03] border border-white/[0.05]">
        {user?.avatarUrl ? (
          <img
            src={user.avatarUrl}
            alt={user.fullName || user.email}
            referrerPolicy="no-referrer"
            className="w-7 h-7 rounded-full object-cover shrink-0"
          />
        ) : (
          <div className="w-7 h-7 rounded-full grid place-items-center shrink-0
                          bg-gradient-to-br from-[#00ffe0] to-[#7c3aed]
                          text-[10px] font-extrabold text-[#0a0a14]">
            {initials}
          </div>
        )}
        <div className="min-w-0 flex-1">
          <div className="text-[11px] font-semibold text-slate-100 truncate">
            {user?.fullName || user?.email?.split('@')[0]}
          </div>
        </div>
        <button
          type="button"
          onClick={() => setConfirmLogout(true)}
          title="התנתק"
          className="text-[10px] text-rose-300 hover:text-rose-200 px-1.5 py-0.5
                     rounded border border-rose-500/20 hover:border-rose-500/40"
        >
          יציאה
        </button>
      </div>
      <LogoutConfirm
        open={confirmLogout}
        userLabel={user?.fullName || user?.email?.split('@')[0] || ''}
        onCancel={() => setConfirmLogout(false)}
        onConfirm={async () => {
          setConfirmLogout(false);
          await signOut();
        }}
      />
    </div>
  );
}

function LogoutConfirm({
  open, userLabel, onCancel, onConfirm,
}: {
  open: boolean;
  userLabel: string;
  onCancel: () => void;
  onConfirm: () => void | Promise<void>;
}) {
  // Escape to dismiss — close-on-backdrop-click is handled inline below.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onCancel(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onCancel]);

  if (!open) return null;
  return (
    <div
      className="fixed inset-0 z-[110] grid place-items-center p-4"
      style={{
        direction: "rtl",
        background: "rgba(0, 0, 0, 0.75)",
        backdropFilter: "blur(10px)",
      }}
      onMouseDown={(e) => { if (e.target === e.currentTarget) onCancel(); }}
    >
      <div
        className="w-full max-w-sm rounded-2xl border border-white/10
                   bg-slate-900/90 backdrop-blur-2xl p-6
                   shadow-[0_30px_60px_-20px_rgba(0,0,0,0.85),0_0_40px_-10px_rgba(244,63,94,0.25)]"
      >
        <div className="flex items-start gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-rose-500/15 border border-rose-500/30
                          grid place-items-center text-lg shrink-0">
            ⚠️
          </div>
          <div className="flex-1 text-right">
            <h3 className="text-white font-bold text-base">האם להתנתק?</h3>
            {userLabel && (
              <p className="text-slate-400 text-xs mt-0.5 truncate">
                מחובר כעת כ־<span className="text-slate-200">{userLabel}</span>
              </p>
            )}
          </div>
        </div>
        <p className="text-slate-300 text-xs leading-relaxed mb-5 text-right">
          ההתנתקות תנקה את הסשן המקומי. תוכל להתחבר שוב בכל עת.
        </p>
        <div className="flex gap-2 justify-end">
          <button
            type="button"
            onClick={onCancel}
            className="px-4 py-2 rounded-xl bg-white/5 border border-white/10
                       text-slate-300 hover:bg-white/10 text-xs font-semibold transition"
          >
            ביטול
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className="px-4 py-2 rounded-xl bg-rose-500/20 border border-rose-500/40
                       text-rose-200 hover:bg-rose-500/30 hover:text-rose-100
                       text-xs font-semibold transition
                       shadow-[0_6px_16px_-6px_rgba(244,63,94,0.5)]"
            autoFocus
          >
            כן, התנתק
          </button>
        </div>
      </div>
    </div>
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
