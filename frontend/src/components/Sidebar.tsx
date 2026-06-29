// Right-side nav (RTL): brand, nav rows, bottom "settings + refresh"
// panel, version footer.
//
// Behavior (ported from the Lovable study): a 72px rail that expands to 230px
//  • on HOVER while floating → OVERLAYS the content + dims the backdrop,
//  • or PINNED (lock button) → stays open and PUSHES the content.
// SMOOTHNESS: every row keeps ONE structure in both states — labels are
// ALWAYS mounted and only fade+slide (opacity + padding), icons live in a
// fixed-width box — so nothing reflows/jumps while the width animates.
import { useEffect, useMemo, useState, type ComponentType, type SVGProps, type CSSProperties } from "react";
import { HomeIcon, LibraryIcon, DownloadsIcon, SettingsIcon } from "./NavIcons";
import { useLauncherAuth } from "../lib/useLauncherAuth";
import AuthModal from "./AuthModal";
import { getSidebarMode, type SidebarMode } from "../lib/themePrefs";

export type NavKey = "home" | "games" | "downloads" | "personal" | "settings";

interface NavLeaf {
  key:    NavKey;
  label:  string;
  Icon:   ComponentType<SVGProps<SVGSVGElement>>;
  accent: string;
}

const EASE = "cubic-bezier(.22,1,.36,1)";

// The reveal: a flex-1 clip that fades + slides its text. Always mounted, so
// the row never restructures when collapsing/expanding (this kills the jump).
function reveal(exp: boolean, pad = 12): CSSProperties {
  return {
    flex: "1 1 0%",
    minWidth: 0,
    overflow: "hidden",
    whiteSpace: "nowrap",
    textAlign: "right",
    opacity: exp ? 1 : 0,
    paddingRight: exp ? pad : 0,
    transition: "opacity .26s ease, padding-right .26s ease",
  };
}
// Fixed icon slot — the icon never moves while the row width animates.
const ICONBOX: CSSProperties = { flex: "0 0 48px", display: "grid", placeItems: "center" };

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

// Outline padlock — same line-icon style as the nav icons (replaces the 🔐 emoji).
function LockIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth={2} strokeLinecap="round" strokeLinejoin="round"
         width={20} height={20} {...props}>
      <rect x="4.5" y="10.5" width="15" height="10" rx="2.3" />
      <path d="M8 10.5V7a4 4 0 0 1 8 0v3.5" />
    </svg>
  );
}

const NAV: NavLeaf[] = [
  { key: "home",      label: "דף הבית",         Icon: HomeIcon,      accent: "#fff700" },
  { key: "games",     label: "ספרייה",          Icon: LibraryIcon,   accent: "#d4af37" },
  { key: "downloads", label: "הורדות ועדכונים", Icon: DownloadsIcon, accent: "#22c55e" },
  { key: "personal",  label: "אזור אישי",        Icon: PersonIcon,    accent: "#00ffe0" },
];

interface Props {
  current: NavKey;
  onNavigate: (key: NavKey) => void;
  onRefresh: () => Promise<void>;
  version: string;
}

export default function Sidebar({ current, onNavigate, version }: Props) {
  const year = useMemo(() => new Date().getFullYear(), []);
  // Display MODE is chosen in Settings → Appearance and shared via themePrefs;
  // mirror it here + react to live changes. "auto" = collapsed rail that
  // expands on hover (default); "wide"/"narrow" = locked open/collapsed.
  const [mode, setMode] = useState<SidebarMode>(getSidebarMode);
  const [hovered, setHovered] = useState(false);
  useEffect(() => {
    const onChange = (e: Event) => setMode((e as CustomEvent).detail as SidebarMode);
    window.addEventListener("sidebarmode", onChange);
    return () => window.removeEventListener("sidebarmode", onChange);
  }, []);

  const exp = mode === "wide" ? true : mode === "narrow" ? false : hovered;

  return (
    <aside
      className="sidebar-glass rounded-2xl flex flex-col flex-shrink-0 p-3 gap-3 overflow-hidden"
      style={{ width: exp ? 230 : 72, transition: `width .46s ${EASE}` }}
      onMouseEnter={() => { if (mode === "auto") setHovered(true); }}
      onMouseLeave={() => { if (mode === "auto") setHovered(false); }}
    >
        {/* Brand block — text reveal + avatar. Avatar fills the rail when collapsed
            so it sits DEAD-CENTRE (the pin moved to the bottom row). */}
        <div className="flex items-center px-1 pt-1 pb-3 border-b border-white/5">
          <div
            className="text-right overflow-hidden whitespace-nowrap"
            style={{ flex: exp ? "1 1 0%" : "0 0 0px", opacity: exp ? 1 : 0, paddingRight: exp ? 8 : 0, transition: "opacity .26s ease" }}
          >
            <div className="font-bold text-white text-[15px] leading-tight">פרויקט התרגום</div>
            <div className="font-display text-[8px] tracking-[0.25em] text-brand-cyan mt-0.5">
              H E B R E W &nbsp; A I
            </div>
          </div>

          <div className="grid place-items-center" style={{ flex: exp ? "0 0 48px" : "1 1 auto" }}>
            <div
              title="פרויקט התרגום"
              className="relative flex items-center justify-center w-12 h-12 rounded-full border-[1.5px] border-[#00ffe0] shadow-[0_0_12px_rgba(0,255,224,0.4)] overflow-hidden shrink-0"
            >
              {/* blurred cover fills the empty space with the image's own background */}
              <img src="./app-icon.png" alt="" aria-hidden
                   className="absolute inset-0 w-full h-full object-cover scale-125 blur-md" />
              {/* sharp logo, contained INSIDE the frame (not clipped by the circle) */}
              <img src="./app-icon.png" alt="פרויקט התרגום"
                   className="relative z-[1] w-10 h-10 object-contain" />
            </div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex flex-col gap-1 mt-1">
          {NAV.map((item) => (
            <NavRow key={item.key} item={item} current={current} onNavigate={onNavigate} exp={exp} />
          ))}
        </nav>

        {/* Spacer */}
        <div className="flex-1" />

        {/* Auth slot — sign in / avatar + logout. */}
        <AuthSlot exp={exp} />

        {/* Settings (refresh removed per request) */}
        <SettingsPanel
          active={current === "settings"}
          onOpen={() => onNavigate("settings")}
          exp={exp}
        />

        {/* Footer — height/opacity reveal (no mount/unmount → no jump). */}
        <div
          className="text-center text-[10px] text-slate-500 font-mono overflow-hidden"
          dir="ltr"
          style={{ height: exp ? 15 : 0, opacity: exp ? 1 : 0, transition: `opacity .3s ease, height .35s ${EASE}` }}
        >
          {version} • © {year}
        </div>
    </aside>
  );
}

// Single-structure nav row — label always mounted (reveal), icon in a fixed
// slot, so the row never reflows while the sidebar width animates.
function NavRow({
  item, current, onNavigate, exp,
}: {
  item:       NavLeaf;
  current:    NavKey;
  onNavigate: (key: NavKey) => void;
  exp:        boolean;
}) {
  const active = item.key === current;
  return (
    <button
      type="button"
      onClick={() => onNavigate(item.key)}
      title={!exp ? item.label : undefined}
      className={[
        "group relative flex items-center w-full rounded-xl py-2.5 transition-colors duration-150",
        active ? "nav-glass text-white" : "text-slate-400 hover:bg-white/[0.04] hover:text-slate-200",
      ].join(" ")}
      style={{ ["--ic" as string]: item.accent }}
    >
      <span
        className={[
          "absolute right-0 top-2 bottom-2 w-[3px] rounded-full transition-opacity",
          active ? "opacity-100" : "opacity-0",
        ].join(" ")}
        style={{ background: item.accent, boxShadow: active ? `0 0 16px 1px ${item.accent}, 0 0 4px ${item.accent}` : undefined }}
      />
      {active && (
        <span className="absolute inset-0 rounded-xl pointer-events-none"
              style={{ background: `linear-gradient(to left, ${item.accent}22, transparent 75%)` }}
              aria-hidden />
      )}
      <span className="relative z-[1] text-[14px]" style={{ ...reveal(exp), fontWeight: active ? 600 : 500 }}>
        {item.label}
      </span>
      <span style={ICONBOX} className="relative z-[1]">
        <item.Icon
          className={active ? "" : "group-hover:[color:var(--ic)] transition-colors duration-200"}
          width={20}
          height={20}
          style={active ? { color: item.accent } : undefined}
        />
      </span>
    </button>
  );
}

function AuthSlot({ exp }: { exp: boolean }) {
  const { user, signedIn, signOut, loading } = useLauncherAuth();
  const [modalOpen,     setModalOpen]     = useState(false);
  const [confirmLogout, setConfirmLogout] = useState(false);

  if (loading) {
    return (
      <div className="px-1 mb-1 rounded-xl bg-white/[0.03] text-[11px] text-slate-500 grid"
           style={{ minHeight: 46, placeItems: "center" }}>
        ...
      </div>
    );
  }

  if (!signedIn) {
    return (
      <>
        <div className={exp ? "px-1" : "px-1 grid place-items-center"}>
          <button
            type="button"
            onClick={() => setModalOpen(true)}
            title="פותח חלון התחברות/הרשמה בתוך הלאנצ׳ר"
            className={[
              "flex items-center justify-center overflow-hidden border border-[#00ffe0]/30 text-[#00ffe0] hover:bg-[#00ffe0]/10 transition",
              exp ? "w-full rounded-xl min-h-[46px] gap-2" : "w-10 h-10 rounded-full",
            ].join(" ")}
            style={{ background: exp ? "rgba(0,255,224,0.10)" : "transparent" }}
          >
            <LockIcon className="w-5 h-5 shrink-0" />
            <span
              className="text-xs font-semibold whitespace-nowrap"
              style={{ maxWidth: exp ? 170 : 0, opacity: exp ? 1 : 0, overflow: "hidden", transition: "max-width .3s ease, opacity .26s ease" }}
            >
              התחברות/הרשמה
            </span>
          </button>
        </div>
        <AuthModal open={modalOpen} onClose={() => setModalOpen(false)} />
      </>
    );
  }

  const initials = (user?.fullName || user?.email || '??').slice(0, 2).toUpperCase();

  return (
    <div className="px-1">
      <div
        className="flex items-center rounded-xl overflow-hidden"
        style={{
          minHeight: 46,
          background: exp ? "rgba(255,255,255,0.03)" : "transparent",
          boxShadow: exp ? "inset 0 0 0 1px rgba(255,255,255,0.06)" : "none",
          transition: "background .3s ease, box-shadow .3s ease",
        }}
      >
        {/* Avatar — on the RIGHT (first in RTL), next to the name; fills + centres when collapsed */}
        <div className="grid place-items-center" style={{ flex: exp ? "0 0 48px" : "1 1 auto" }}>
          <button
            type="button"
            onClick={() => setConfirmLogout(true)}
            title={`${user?.fullName || user?.email || ''} — לחץ ליציאה`}
            className="w-9 h-9 rounded-full overflow-hidden grid place-items-center border border-white/10 hover:border-rose-400/40 transition"
          >
            {user?.avatarUrl ? (
              <img src={user.avatarUrl} alt={user.fullName || user.email} referrerPolicy="no-referrer"
                   className="w-full h-full object-cover" />
            ) : (
              <span className="w-full h-full grid place-items-center bg-gradient-to-br from-[#00ffe0] to-[#7c3aed]
                               text-[10px] font-extrabold text-[#0a0a14]">{initials}</span>
            )}
          </button>
        </div>
        {/* Name + logout — to the LEFT of the avatar */}
        <div className="flex items-center gap-1 overflow-hidden"
             style={{ flex: exp ? "1 1 0%" : "0 0 0px", opacity: exp ? 1 : 0, transition: "opacity .26s ease" }}>
          <span className="flex-1 min-w-0 truncate text-[11px] font-semibold text-slate-100 text-right pr-2">
            {user?.fullName || user?.email?.split('@')[0]}
          </span>
          <button
            type="button"
            onClick={() => setConfirmLogout(true)}
            title="התנתק"
            className="shrink-0 text-[10px] text-rose-300 hover:text-rose-200 px-1.5 py-0.5
                       rounded border border-rose-500/20 hover:border-rose-500/40"
          >
            יציאה
          </button>
        </div>
      </div>
      <LogoutConfirm
        open={confirmLogout}
        userLabel={user?.fullName || user?.email?.split('@')[0] || ''}
        onCancel={() => setConfirmLogout(false)}
        onConfirm={async () => { setConfirmLogout(false); await signOut(); }}
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
      style={{ direction: "rtl", background: "rgba(0, 0, 0, 0.75)", backdropFilter: "blur(10px)" }}
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

// Settings — ONE structure (label reveal + fixed gear slot), exactly like a
// nav row, so it never swaps layouts during the width animation (the old
// two-branch swap caused the lingering teal square / delay).
function SettingsPanel({
  active, onOpen, exp,
}: {
  active: boolean;
  onOpen: () => void;
  exp: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onOpen}
      title={!exp ? "הגדרות" : undefined}
      className={[
        "group relative flex items-center w-full rounded-xl py-2 transition-colors duration-150",
        active ? "bg-white/[0.08] text-white" : "text-slate-300 hover:bg-white/[0.04]",
      ].join(" ")}
    >
      <span className="text-[13px] font-semibold relative z-[1]" style={reveal(exp)}>הגדרות</span>
      <span style={ICONBOX} className="relative z-[1]">
        <span className="w-9 h-9 rounded-lg grid place-items-center bg-[#00ffe0] text-brand-ink
                         shadow-[0_4px_14px_-4px_rgba(0,255,224,0.5)] group-hover:scale-105 transition-transform">
          <SettingsIcon className="w-[18px] h-[18px]" />
        </span>
      </span>
    </button>
  );
}
