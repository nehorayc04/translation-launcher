// Right-side nav (RTL): brand, nav rows, bottom "settings + refresh"
// panel, version footer.
//
// Behavior (ported from the Lovable study): a 72px rail that expands to 230px
//  • on HOVER while floating → OVERLAYS the content + dims the backdrop,
//  • or PINNED (lock button) → stays open and PUSHES the content.
// SMOOTHNESS: every row keeps ONE structure in both states - labels are
// ALWAYS mounted and only fade+slide (opacity + padding), icons live in a
// fixed-width box - so nothing reflows/jumps while the width animates.
import { useEffect, useLayoutEffect, useMemo, useRef, useState, type ComponentType, type SVGProps, type CSSProperties } from "react";
import { HomeIcon, LibraryIcon, DownloadsIcon, SettingsIcon, UserIcon } from "./NavIcons";
import { useLauncherAuth } from "../lib/useLauncherAuth";
import { api } from "../lib/eel";
import NotificationsBell from "./NotificationsBell";
import AuthModal from "./AuthModal";
import { getSidebarMode, type SidebarMode } from "../lib/themePrefs";
import { IconOptBtnLogout, IconOptBtnLogoutConfirm, IconAppSidebarLogoutWarning } from "./UiIcons";

const SITE_URL = "https://hebrew-translation-hub.com/";

// `plugin:<id>` is a DYNAMIC key: an installed plugin gets its own row under the
// "תוספים" group, so a plugin the user actually uses is one click away instead of
// buried inside the manager list.
export type NavKey =
  | "home" | "games" | "software" | "downloads" | "plugins" | "personal" | "settings"
  | `plugin:${string}`;

// Grid glyph for the תוכנות row.
// Flaticon UICONS "box-open" (Regular Rounded) - the תוכנות row (user's pick).
function AppsIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" width={20} height={20} {...props}>
      <path d="M17.87 5.33H16.93Q16.6 3.87 15.47 2.93Q14.33 2 12.87 2H11.2Q9.67 2 8.53 2.93Q7.4 3.87 7.07 5.33H6.2Q5.07 5.33 4.1 5.9Q3.13 6.47 2.57 7.43Q2 8.4 2 9.53V17.8Q2 18.93 2.57 19.9Q3.13 20.87 4.1 21.43Q5.07 22 6.2 22H17.87Q18.93 22 19.9 21.43Q20.87 20.87 21.43 19.9Q22 18.93 22 17.8V9.47Q22 8.4 21.43 7.43Q20.87 6.47 19.9 5.9Q18.93 5.33 17.8 5.33ZM11.2 3.67H12.87Q13.67 3.67 14.3 4.13Q14.93 4.6 15.2 5.33H8.8Q9.07 4.6 9.7 4.13Q10.33 3.67 11.2 3.67ZM6.2 7H17.87Q18.87 7 19.6 7.73Q20.33 8.47 20.33 9.47V10.33H17.87V9.47Q17.87 9.13 17.6 8.9Q17.33 8.67 17 8.67Q16.67 8.67 16.43 8.9Q16.2 9.13 16.13 9.53V10.33H7.87V9.47Q7.87 9.13 7.6 8.9Q7.33 8.67 7 8.67Q6.67 8.67 6.43 8.9Q6.2 9.13 6.2 9.53V10.33H3.67V9.47Q3.67 8.47 4.4 7.73Q5.13 7 6.2 7ZM17.87 20.33H6.2Q5.13 20.33 4.4 19.6Q3.67 18.87 3.67 17.8V12H6.2V12.8Q6.2 13.2 6.43 13.43Q6.67 13.67 7 13.67Q7.33 13.67 7.57 13.43Q7.8 13.2 7.87 12.87V12H16.2V12.8Q16.2 13.2 16.43 13.43Q16.67 13.67 17 13.67Q17.33 13.67 17.6 13.43Q17.87 13.2 17.87 12.87V12H20.33V17.8Q20.33 18.87 19.6 19.6Q18.87 20.33 17.8 20.33Z" />
    </svg>
  );
}

// Flaticon UICONS "apps-add" (Regular Rounded) - the תוספים row (user's pick).
function PluginsIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" width={20} height={20} {...props}>
      <path d="M7.87 2H5.33Q3.93 2 2.97 2.97Q2 3.93 2 5.33V7.8Q2 9.2 2.97 10.17Q3.93 11.13 5.33 11.13H7.87Q9.2 11.13 10.2 10.17Q11.2 9.2 11.13 7.87V5.33Q11.2 3.93 10.2 2.97Q9.2 2 7.87 2ZM9.53 7.8Q9.53 8.53 9.03 9Q8.53 9.47 7.8 9.47H5.33Q4.67 9.47 4.17 9Q3.67 8.53 3.67 7.8V5.33Q3.67 4.67 4.17 4.17Q4.67 3.67 5.33 3.67H7.87Q8.53 3.67 9.03 4.17Q9.53 4.67 9.53 5.33ZM7.87 12.8H5.33Q3.93 12.87 2.97 13.83Q2 14.8 2 16.13V18.67Q2 20.07 2.97 21.03Q3.93 22 5.33 22H7.87Q9.2 22 10.17 21.03Q11.13 20.07 11.13 18.67V16.13Q11.2 14.8 10.2 13.8Q9.2 12.8 7.87 12.87ZM9.53 18.67Q9.53 19.33 9.03 19.83Q8.53 20.33 7.8 20.33H5.33Q4.67 20.33 4.17 19.83Q3.67 19.33 3.67 18.67V16.13Q3.67 15.47 4.17 14.97Q4.67 14.47 5.33 14.47H7.87Q8.53 14.47 9.03 14.97Q9.53 15.47 9.53 16.13ZM18.67 12.8H16.2Q14.8 12.8 13.83 13.8Q12.87 14.8 12.87 16.13V18.67Q12.87 20.07 13.83 21.03Q14.8 22 16.2 22H18.67Q20.07 22 21.03 21.03Q22 20.07 22 18.67V16.13Q22 14.8 21.03 13.8Q20.07 12.8 18.67 12.87ZM20.33 18.67Q20.33 19.33 19.83 19.83Q19.33 20.33 18.67 20.33H16.2Q15.47 20.33 15 19.83Q14.53 19.33 14.53 18.67V16.13Q14.53 15.47 15 14.97Q15.47 14.47 16.2 14.47H18.67Q19.33 14.47 19.83 14.97Q20.33 15.47 20.33 16.13ZM13.67 7.8H16.2V10.33Q16.2 10.67 16.43 10.93Q16.67 11.2 17 11.17Q17.33 11.13 17.6 10.9Q17.87 10.67 17.87 10.33V7.8H20.33Q20.67 7.8 20.93 7.57Q21.2 7.33 21.2 7Q21.2 6.67 20.93 6.4Q20.67 6.13 20.33 6.13H17.87V3.67Q17.87 3.33 17.6 3.1Q17.33 2.87 17 2.83Q16.67 2.8 16.43 3.07Q16.2 3.33 16.13 3.67V6.13H13.67Q13.33 6.2 13.07 6.43Q12.8 6.67 12.83 7Q12.87 7.33 13.1 7.6Q13.33 7.87 13.67 7.87Z" />
    </svg>
  );
}

interface NavLeaf {
  key:    NavKey;
  label:  string;
  Icon:   ComponentType<SVGProps<SVGSVGElement>>;
  accent: string;
}

// The plain reveal curve for the text/padding reveals (NOT the rail width). The
// liquid width spring is applied separately, and ONLY at "full animation", via the
// .sidebar-rail-tr CSS class (index.css) - at normal/low it stays this plain ease,
// exactly like before the liquid effect.
const EASE = "cubic-bezier(.22,1,.36,1)";

// The reveal: a flex-1 clip that fades + slides its text. Always mounted, so
// the row never restructures when collapsing/expanding (this kills the jump).
function reveal(exp: boolean, pad = 12): CSSProperties {
  return {
    flex: "1 1 0%",
    minWidth: 0,
    overflow: "hidden",
    whiteSpace: "nowrap",
    // A clipped label cuts a word in half and reads as a rendering glitch; an
    // ellipsis reads as "there is more" (the full name is in the tooltip).
    textOverflow: "ellipsis",
    textAlign: "right",
    opacity: exp ? 1 : 0,
    paddingRight: exp ? pad : 0,
    // Reserve the (now absolutely-pinned) 48px icon column on the left so a long
    // label never slides under the icon.
    paddingLeft: 48,
    transition: "opacity .26s ease, padding-right .26s ease",
  };
}
// Icon slot ABSOLUTELY pinned to the row's rail edge (left) so its x-position is
// completely independent of the row width - the rail can spring open/closed and the
// icon never reflows or jitters. The parent button is `relative` in both callers.
const ICONBOX: CSSProperties = { position: "absolute", left: 0, top: 0, bottom: 0, width: 48, display: "grid", placeItems: "center" };

// Outline padlock - same line-icon style as the nav icons (replaces the 🔐 emoji).
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

// "אזור אישי" is intentionally NOT a nav row - the personal area is reached by
// clicking the user's profile/avatar in the auth slot below (avoids a duplicate).
// Flat nav - no "ספרייה" folder: משחקים and תוכנות are ordinary top-level rows.
const NAV: NavLeaf[] = [
  { key: "home",      label: "דף הבית",         Icon: HomeIcon,      accent: "#fff700" },
  { key: "games",     label: "משחקים",          Icon: LibraryIcon,   accent: "#d4af37" },
  { key: "software",  label: "תוכנות",          Icon: AppsIcon,      accent: "#00c2ff" },
  { key: "downloads", label: "הורדות ועדכונים", Icon: DownloadsIcon, accent: "#22c55e" },
  { key: "plugins",   label: "תוספים",          Icon: PluginsIcon,   accent: "#a78bfa" },
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

  const nav = NAV;

  // Springy sliding active-indicator (like the admin site's layoutId glow) -
  // ONE pill that measures the active NavRow and slides to it, so switching
  // menus reads as a fluid motion instead of a hard on/off per row.
  const navRef = useRef<HTMLElement | null>(null);
  const activeAccent = nav.find((n) => n.key === current)?.accent ?? "#00ffe0";
  const [ind, setInd] = useState<{ top: number; height: number; on: boolean }>({ top: 0, height: 0, on: false });
  useLayoutEffect(() => {
    const nav = navRef.current;
    if (!nav) return;
    const measure = () => {
      const el = nav.querySelector<HTMLElement>(`[data-tour="nav-${current}"]`);
      if (!el) { setInd((s) => ({ ...s, on: false })); return; }
      setInd({ top: el.offsetTop, height: el.offsetHeight, on: true });
    };
    measure();
    // Re-measure after first paint settles + whenever the rows resize (the
    // text-size setting) or the window resizes, so the pill never strands.
    const raf = requestAnimationFrame(measure);
    const ro = new ResizeObserver(measure);
    ro.observe(nav);
    window.addEventListener("resize", measure);
    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      window.removeEventListener("resize", measure);
    };
  }, [current, exp, mode, hovered]);

  return (
    // NO `overflow-hidden` on the aside: every label already clips itself via its
    // own reveal wrapper (overflow:hidden), so the container clip was only cutting
    // the teal glow of the settings gear (and the brand avatar) at the rail edge ->
    // a hard "cut" that read like a frame. Without it the glow renders fully; no
    // text leaks because the reveals self-clip.
    <aside
      data-sidebar
      // sidebar-rail-tr carries the width transition: a LIQUID spring only at "full
      // animation" (data-anim=high), a plain quick ease otherwise (index.css). No
      // minWidth clamp - the FULL spring (over-and-back on BOTH open and close) is
      // wanted; the icons don't jump because each icon is absolutely pinned to the
      // rail edge (ICONBOX below), so the width springing never reflows them.
      className="sidebar-glass rounded-2xl flex flex-col flex-shrink-0 p-3 gap-3 sidebar-rail-tr"
      data-open={exp ? "1" : "0"}
      style={{ width: exp ? 230 : 72 }}
      onMouseEnter={() => { if (mode === "auto") setHovered(true); }}
      onMouseLeave={() => { if (mode === "auto") setHovered(false); }}
    >
        {/* Brand block - text reveal + avatar. Avatar fills the rail when collapsed
            so it sits DEAD-CENTRE (the pin moved to the bottom row). */}
        <div className="flex items-center pt-1 pb-3 border-b border-white/5">
          <div
            className="text-right overflow-hidden whitespace-nowrap"
            style={{ flex: "1 1 0%", opacity: exp ? 1 : 0, paddingRight: exp ? 8 : 0, transition: `opacity .26s ease, padding-right .46s ${EASE}` }}
          >
            <div className="font-bold text-white text-[15px] leading-tight">פרויקט התרגום</div>
            <div className="font-display text-[8px] tracking-[0.25em] text-brand-cyan mt-0.5">
              H E B R E W &nbsp; A I
            </div>
          </div>

          <div className="grid place-items-center" style={{ flex: "0 0 48px" }}>
            {/* No frame - the glowing logo floats gently. FIXED px so the
                text-size setting never scales it; drop-shadow gives the neon
                glow in the icon's own blue+red. */}
            {/* The brand logo opens the official site (the hero's "האתר הרשמי"
                button was removed, so this is the way there). Opened through
                the backend, NOT a raw <a>: inside the Qt shell the page origin
                is file://, so only the host can hand the URL to the real
                browser. */}
            <button
              type="button"
              onClick={() => { void api.openExternal(SITE_URL).catch(() => {}); }}
              title="פרויקט התרגום - מעבר לאתר הרשמי"
              aria-label="מעבר לאתר הרשמי"
              className="grid place-items-center rounded-full transition-transform
                         hover:scale-105 active:scale-95 focus:outline-none
                         focus-visible:ring-2 focus-visible:ring-brand-cyan/60"
            >
              <img src="./app-logo.png" alt="פרויקט התרגום"
                   className="object-contain shrink-0 float-soft"
                   style={{ width: 44, height: 44,
                            filter: "drop-shadow(0 0 7px rgba(79,139,255,0.55)) drop-shadow(0 0 12px rgba(255,59,123,0.32))" }} />
            </button>
          </div>
        </div>

        {/* Nav - flat rows (home · משחקים · תוכנות · הורדות). A single springy
            pill slides behind the active row (see `ind`). */}
        <nav ref={navRef} className="relative flex flex-col gap-1 mt-1">
          {/* The indicator carries EVERYTHING that marks "you are here": the
              accent wash, the glowing edge bar, and (at anim=high) the GLASS.
              Keeping the glass on this one travelling element - instead of
              hanging it off :hover per row - is what makes the effect follow the
              selection and slide with you, which is the whole point. */}
          <span
            className="nav-slide nav-slide-glass absolute right-0 left-0 rounded-xl pointer-events-none z-0"
            aria-hidden
            style={{
              top: ind.top,
              height: ind.height,
              opacity: ind.on ? 1 : 0,
              ["--nav-accent" as string]: activeAccent,
              // The SUBTLE GLASS look the user liked - a faint accent wash that lets
              // the backdrop-filter blur dominate (a translucent glass pane with just
              // a hint of the selection's colour), NOT a strong solid accent fill (that
              // read as a glowing pill, which the user rejected). The right-edge "cut"
              // was the 1px border (removed in index.css), never this gradient.
              background: `linear-gradient(to left, ${activeAccent}22, transparent 82%)`,
            }}
          >
            {/* Glowing edge bar removed per user request - the indicator keeps its
                accent wash + glass; no bar on the row's edge. */}
          </span>
          {nav.map((item) => (
            <NavRow key={item.key} item={item} current={current} onNavigate={onNavigate} exp={exp} />
          ))}
        </nav>

        {/* Spacer */}
        <div className="flex-1" />

        {/* Notifications bell - sits ABOVE the avatar. System notices + updates
            (admin-controlled) + live background-download progress. */}
        <NotificationsBell exp={exp} />

        {/* Auth slot - sign in / avatar + logout. */}
        <AuthSlot exp={exp} onNavigate={onNavigate} />

        {/* Settings (refresh removed per request) */}
        <SettingsPanel
          active={current === "settings"}
          onOpen={() => onNavigate("settings")}
          exp={exp}
        />

        {/* Footer - height/opacity reveal (no mount/unmount → no jump). */}
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

// Single-structure nav row - label always mounted (reveal), icon in a fixed
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
      data-tour={`nav-${item.key}`}
      onClick={() => onNavigate(item.key)}
      title={!exp ? item.label : undefined}
      className={[
        "group relative z-[1] flex items-center w-full rounded-xl h-[46px] transition-colors duration-150",
        active ? "text-white" : "text-slate-400 hover:bg-white/[0.04] hover:text-slate-200",
      ].join(" ")}
      style={{ ["--ic" as string]: item.accent }}
    >
      <span
        className="relative z-[1] text-[14px]"
        style={{ ...reveal(exp, 12), fontWeight: active ? 600 : 500 }}
      >
        {item.label}
      </span>
      <span style={ICONBOX} className="relative z-[1]">
        <item.Icon
          className={active ? "" : "group-hover:[color:var(--ic)] transition-colors duration-200"}
          width={25}
          height={25}
          style={active ? { color: item.accent } : undefined}
        />
      </span>
    </button>
  );
}


function AuthSlot({ exp, onNavigate }: { exp: boolean; onNavigate: (key: NavKey) => void }) {
  const { user, signedIn, signOut, loading } = useLauncherAuth();
  const [modalOpen,     setModalOpen]     = useState(false);
  const [confirmLogout, setConfirmLogout] = useState(false);
  // Remote avatar failed to load (offline / blocked CDN) → show the initials.
  // Reset when the URL changes so a re-login with a working picture recovers.
  const [avatarBroken,  setAvatarBroken]  = useState(false);
  const avatarUrl = user?.avatarUrl;
  useEffect(() => { setAvatarBroken(false); }, [avatarUrl]);

  if (loading) {
    return (
      <div className="px-1 mb-1 rounded-xl bg-white/[0.03] text-[11px] text-slate-500 grid"
           style={{ minHeight: 46, placeItems: "center" }}>
        ...
      </div>
    );
  }

  if (!signedIn) {
    // Collapsed rail → a real profile-avatar placeholder (person on a subtle
    // gradient) so the slot never looks like an empty ring. Expanded → the
    // full "sign in / register" button.
    return (
      <>
        <div className={exp ? "px-1" : "px-1 grid place-items-center"}>
          {exp ? (
            <button
              type="button"
              data-tour="profile"
              onClick={() => setModalOpen(true)}
              title="פותח חלון התחברות/הרשמה בתוך הלאנצ׳ר"
              className="flex items-center justify-center overflow-hidden border border-[#00ffe0]/30 text-[#00ffe0] hover:bg-[#00ffe0]/10 transition w-full rounded-xl min-h-[46px] gap-2"
              style={{ background: "rgba(0,255,224,0.10)" }}
            >
              <LockIcon className="w-5 h-5 shrink-0" />
              <span className="text-xs font-semibold whitespace-nowrap">התחברות/הרשמה</span>
            </button>
          ) : (
            <button
              type="button"
              data-tour="profile"
              onClick={() => setModalOpen(true)}
              title="התחברות / הרשמה"
              className="relative w-[40px] h-[40px] rounded-full overflow-hidden grid place-items-center border border-white/15 hover:border-[#00ffe0]/50 transition"
            >
              <span className="absolute inset-0 bg-gradient-to-br from-slate-600/40 to-slate-800/60" aria-hidden />
              <UserIcon className="relative w-[24px] h-[24px] text-slate-200" />
            </button>
          )}
        </div>
        <AuthModal open={modalOpen} onClose={() => setModalOpen(false)} />
      </>
    );
  }

  const initials = (user?.fullName || user?.email || '??').slice(0, 2).toUpperCase();

  return (
    <div>
      <div
        className="flex items-center rounded-xl overflow-hidden"
        style={{
          minHeight: 46,
          background: exp ? "rgba(255,255,255,0.03)" : "transparent",
          boxShadow: exp ? "inset 0 0 0 1px rgba(255,255,255,0.06)" : "none",
          transition: "background .3s ease, box-shadow .3s ease",
        }}
      >
        {/* Logout + name - on the RIGHT (logout rightmost, then the name) */}
        <div className="flex items-center gap-1 overflow-hidden"
             style={{ flex: "1 1 0%", opacity: exp ? 1 : 0, paddingRight: exp ? 10 : 0, transition: `opacity .26s ease, padding-right .46s ${EASE}` }}>
          <button
            type="button"
            onClick={() => setConfirmLogout(true)}
            title="התנתק"
            className="shrink-0 inline-flex items-center gap-1.5 text-[10px] text-rose-300 hover:text-rose-200 px-1.5 py-0.5
                       rounded border border-rose-500/20 hover:border-rose-500/40"
          >
            <IconOptBtnLogout width={18} className="shrink-0 opacity-90" />
          </button>
          <span className="flex-1 min-w-0 truncate text-[11px] font-semibold text-slate-100 text-left pl-2">
            {user?.fullName || user?.email?.split('@')[0]}
          </span>
        </div>
        {/* Avatar - on the LEFT; opens the personal area. Fixed 48px slot (like
            the brand icon + nav icons) so it never re-flexes/snaps mid-animation
            and sits DEAD-CENTRE in the rail when collapsed. */}
        <div className="grid place-items-center" style={{ flex: "0 0 48px" }}>
          <button
            type="button"
            data-tour="profile"
            onClick={() => onNavigate("personal")}
            title="האזור האישי"
            className="w-[36px] h-[36px] rounded-full overflow-hidden grid place-items-center border border-white/10 hover:border-brand-cyan/40 transition"
          >
            {/* The avatar is a REMOTE Google image. Having a src is not the same
                as having a picture: offline, a blocked CDN or a rate-limited
                request leaves an EMPTY circle, because the initials bubble below
                only covered "no url at all". Fall back on a failed LOAD too. */}
            {user?.avatarUrl && !avatarBroken ? (
              <img src={user.avatarUrl} alt={user.fullName || user.email} referrerPolicy="no-referrer"
                   onError={() => setAvatarBroken(true)}
                   className="w-full h-full object-cover" />
            ) : (
              <span className="w-full h-full grid place-items-center bg-gradient-to-br from-[#00ffe0] to-[#7c3aed]
                               text-[10px] font-extrabold text-[#0a0a14]">{initials}</span>
            )}
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
            <IconAppSidebarLogoutWarning width={24} className="opacity-90" />
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
            className="inline-flex items-center justify-center gap-1.5 px-4 py-2 rounded-xl bg-rose-500/20 border border-rose-500/40
                       text-rose-200 hover:bg-rose-500/30 hover:text-rose-100
                       text-xs font-semibold transition
                       shadow-[0_6px_16px_-6px_rgba(244,63,94,0.5)]"
            autoFocus
          >
            <IconOptBtnLogoutConfirm width={18} className="shrink-0 opacity-90" />
            כן, התנתק
          </button>
        </div>
      </div>
    </div>
  );
}

// Settings - ONE structure (label reveal + fixed gear slot), exactly like a
// nav row, so it never swaps layouts during the width animation (the old
// two-branch swap caused the lingering teal square / delay).
function SettingsPanel({
  active, onOpen, exp,
}: {
  active: boolean;
  onOpen: () => void;
  exp: boolean;
}) {
  // The active white frame appears ONLY when the rail is WIDE. When collapsed the
  // button is JUST the gear - identical whether or not Settings is the open view.
  const framed = active && exp;
  return (
    <button
      type="button"
      data-tour="nav-settings"
      onClick={onOpen}
      title={!exp ? "הגדרות" : undefined}
      className={[
        // FIXED height (px, not rem py-*) so nothing scales with the text size.
        "group relative flex items-center w-full rounded-xl h-[46px] transition-colors duration-150",
        framed ? "text-white" : "text-slate-300 hover:bg-white/[0.04]",
      ].join(" ")}
    >
      {/* Active highlight (fill + crisp inset ring) - rendered ONLY while active,
          and FADED IN only when the rail is wide (exp). As the rail collapses it
          fades to 0 so the narrow rail shows just the gear, exactly like the
          inactive state. Opacity-only transition → smooth, never breaks mid
          width-animation. */}
      {active && (
        <span
          aria-hidden
          className="absolute inset-0 rounded-xl bg-white/[0.08] ring-1 ring-inset ring-white/30 pointer-events-none"
          style={{ opacity: exp ? 1 : 0, transition: "opacity .3s ease" }}
        />
      )}
      <span className="text-[13px] font-semibold relative z-[1]" style={reveal(exp)}>הגדרות</span>
      <span style={ICONBOX} className="relative z-[1]">
        <span className="w-[36px] h-[36px] rounded-lg grid place-items-center bg-[#00ffe0] text-brand-ink
                         shadow-[0_4px_14px_-4px_rgba(0,255,224,0.5)] group-hover:scale-105 transition-transform">
          <SettingsIcon className="w-[18px] h-[18px]" />
        </span>
      </span>
    </button>
  );
}
