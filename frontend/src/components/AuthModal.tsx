// Embedded launcher auth modal — keeps the entire password flow inside
// the app window. Three actions:
//   • Login    → useLauncherAuth.signInPassword(email, password)
//   • Register → useLauncherAuth.signUpPassword(email, password, fullName)
//   • Google   → useLauncherAuth.signInGoogle() (still uses the RFC 8252
//                loopback flow — opens the system browser, comes back via
//                127.0.0.1 listener). Closing the modal mid-Google is OK,
//                Python's await_code() times out cleanly.
//
// Styling matches the rest of the launcher (glass + neon accent on the
// active tab). All state lives locally; the parent just toggles `open`.
import { useEffect, useRef, useState } from "react";
import { useLauncherAuth } from "../lib/useLauncherAuth";
import { api } from "../lib/eel";

type Mode = "login" | "register";

interface Props {
  open:    boolean;
  onClose: () => void;
}

export default function AuthModal({ open, onClose }: Props) {
  const { signInPassword, signUpPassword, signInGoogle, cancelGoogleSignIn } = useLauncherAuth();
  const [mode,     setMode]     = useState<Mode>("login");
  const [email,    setEmail]    = useState("");
  const [password, setPassword] = useState("");
  const [pwConfirm, setPwConfirm] = useState("");
  const [fullName, setFullName] = useState("");
  const [busy,     setBusy]     = useState(false);
  const [error,    setError]    = useState<string | null>(null);
  const [info,     setInfo]     = useState<string | null>(null);
  // Separate busy flag for the Google flow so we can render a richer
  // "waiting for browser" state. MUST live up here with the other
  // useState calls — Rules of Hooks forbid declaring it below the
  // `if (!open) return null` early return, since the hook-call count
  // would change between closed↔open renders and crash the whole tree.
  const [googleBusy, setGoogleBusy] = useState(false);
  // "Copied!" toast on the Copy Link button — flips back to its
  // default label after 1.5s. Kept up here for the same Rules of
  // Hooks reason as googleBusy.
  const [copied, setCopied] = useState(false);
  // Pre-fetched authorize URL. Populated by the polling effect below
  // the moment googleBusy flips true. We MUST have the URL ready
  // SYNCHRONOUSLY at click time — clipboard APIs in Eel/Chromium
  // reject writeText() if there's any async gap between the user
  // gesture and the call. Awaiting the Eel bridge inside the onClick
  // handler is exactly that gap, which is why the old version
  // appeared to succeed but silently dropped the payload.
  const [authUrl, setAuthUrl] = useState("");
  const firstInput = useRef<HTMLInputElement>(null);

  // Reset state every open + focus first input
  useEffect(() => {
    if (!open) return;
    setError(null); setInfo(null);
    const t = setTimeout(() => firstInput.current?.focus(), 50);
    return () => clearTimeout(t);
  }, [open, mode]);

  // Escape to close. Allowed even while the Google flow is mid-flight
  // (Python's listener will time out cleanly on its own) but blocked
  // during a password POST (it's near-instant; closing mid-POST would
  // race the setUser callback).
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !busy) onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, busy, onClose]);

  // Pre-fetch the authorize URL the instant Google waiting starts.
  // Python sets the URL synchronously BEFORE calling webbrowser.open,
  // so by the time signInGoogle() has registered as awaited (which is
  // what flips googleBusy true) the URL is already available on the
  // Python side. We poll briefly to cover the edge case where this
  // effect runs before login() reaches the assignment — 10 tries at
  // 100 ms is a 1 s window, far longer than the URL build needs.
  useEffect(() => {
    if (!googleBusy) { setAuthUrl(""); return; }
    let cancelled = false;
    let tries = 0;
    const tick = async () => {
      if (cancelled) return;
      try {
        const u = await api.authGetAuthorizeUrl();
        if (cancelled) return;
        if (u) { setAuthUrl(u); return; }
      } catch { /* keep polling */ }
      tries += 1;
      if (tries < 10) setTimeout(tick, 100);
    };
    tick();
    return () => { cancelled = true; };
  }, [googleBusy]);

  if (!open) return null;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null); setInfo(null);

    if (!email || !password) {
      setError("מלא אימייל וסיסמה");
      return;
    }
    if (mode === "register") {
      if (password.length < 8)      return setError("סיסמה חייבת להיות לפחות 8 תווים");
      if (password !== pwConfirm)   return setError("הסיסמאות אינן תואמות");
    }

    setBusy(true);
    const r = mode === "login"
      ? await signInPassword(email, password)
      : await signUpPassword(email, password, fullName.trim());
    setBusy(false);

    if (!r.ok) {
      setError(r.error || "פעולה נכשלה");
      return;
    }
    // Register path may need email confirmation — keep the modal open
    // with a clear "check your inbox" message instead of silently
    // closing while still signed-out.
    if (mode === "register" && !("confirmed" in r ? r.confirmed : true)) {
      setInfo("נשלח אימייל אישור לכתובת. אשר אותו ואז התחבר.");
      return;
    }
    onClose();
  };

  // (googleBusy useState is now declared above with the other hooks —
  // it MUST be unconditional to satisfy Rules of Hooks. Closing the
  // modal mid-Google is fine: Python's loopback await_code() times
  // out cleanly in ~2 min so no zombie listener lingers.)
  const onGoogle = async () => {
    setError(null); setInfo(null);
    setGoogleBusy(true);
    const r = await signInGoogle();
    setGoogleBusy(false);
    if (!r.ok) {
      setError(r.error || "התחברות דרך Google נכשלה");
      return;
    }
    onClose();
  };

  const cancelGoogle = async () => {
    // EXPLICIT abort — calls auth_abort_login() so the Python
    // loopback HTTP server is torn down immediately, freeing port
    // 8085 for the next attempt. Without this the React state would
    // reset but Python would keep blocking in await_code(), and
    // every subsequent click would queue behind it (the "multi-window
    // delay" bug). Awaited so the modal can't render a fresh Google
    // button until the old listener is actually gone.
    await cancelGoogleSignIn();
    setGoogleBusy(false);
    setError(null);
  };

  // SYNCHRONOUS copy — no `await` between the user click and the
  // write, which Chromium/Eel security requires for non-user-gesture
  // clipboard access. The URL is grabbed from authUrl state (populated
  // by the prefetch effect above); we never await the Eel bridge in
  // the click handler itself.
  //
  // Two-layer strategy:
  //   1. navigator.clipboard.writeText — the modern path. It returns
  //      a Promise, but we kick it off WITHOUT awaiting it here so the
  //      browser still sees this as a user-gesture call. We attach
  //      .then/.catch to the Promise to flip the UI label or fall
  //      through to step 2.
  //   2. execCommand('copy') with a hidden <textarea> — the legacy
  //      path. Works in older Chromium / restricted contexts where
  //      writeText is blocked entirely. Synchronous, no Promise.
  const copyAuthorizeUrl = () => {
    if (!authUrl) {
      setError("הקישור לא זמין עדיין. נסה שוב בעוד רגע.");
      return;
    }
    const flash = () => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    };
    const legacyCopy = (): boolean => {
      try {
        const ta = document.createElement("textarea");
        ta.value         = authUrl;
        ta.style.position = "fixed";
        ta.style.top      = "-1000px";   // off-screen, not display:none
        ta.style.opacity  = "0";          //   (which disables selection)
        ta.setAttribute("readonly", "");
        document.body.appendChild(ta);
        ta.select();
        ta.setSelectionRange(0, authUrl.length);
        const ok = document.execCommand("copy");
        document.body.removeChild(ta);
        return ok;
      } catch {
        return false;
      }
    };
    try {
      // Modern path — Promise-returning. Do NOT await: that breaks the
      // user-gesture invariant. .then for success, .catch for fallback.
      const maybe = navigator.clipboard?.writeText?.(authUrl);
      if (maybe && typeof maybe.then === "function") {
        maybe.then(flash).catch(() => {
          if (legacyCopy()) flash();
          else setError("שגיאת העתקה — נסה לסמן ולהעתיק ידנית.");
        });
        return;
      }
    } catch { /* fall through to legacy */ }
    if (legacyCopy()) flash();
    else setError("שגיאת העתקה — נסה לסמן ולהעתיק ידנית.");
  };

  return (
    <div
      className="fixed inset-0 z-[100] grid place-items-center p-4"
      style={{
        direction: "rtl",
        background: "rgba(0, 0, 0, 0.75)",
        backdropFilter: "blur(10px)",
      }}
      onMouseDown={(e) => { if (e.target === e.currentTarget && !busy) onClose(); }}
    >
      <div
        className="relative w-full max-w-md rounded-2xl border border-white/10
                   bg-slate-900/85 backdrop-blur-2xl p-6 sm:p-7
                   shadow-[0_30px_60px_-20px_rgba(0,0,0,0.85),0_0_40px_-10px_rgba(0,255,224,0.25)]"
      >
        {/* close button — busy here is the PASSWORD post, which is
            near-instant. The Google wait uses its own overlay below
            and exposes a Cancel that doesn't require the X button. */}
        <button
          type="button"
          aria-label="סגור"
          onClick={() => !busy && onClose()}
          className="absolute top-3 left-3 w-8 h-8 rounded-full grid place-items-center
                     text-slate-400 hover:text-white hover:bg-white/5 transition"
        >
          ×
        </button>

        {/* Google-waiting overlay — covers the modal contents while we
            await the loopback callback. Renders ON TOP of the form so
            the user sees the modal is alive and can cancel without
            being thrown out into a stuck sidebar state. */}
        {googleBusy && (
          <div className="absolute inset-0 z-10 rounded-2xl flex flex-col items-center justify-center
                          gap-4 px-6 text-center bg-slate-900/95 backdrop-blur-sm">
            <div className="w-12 h-12 rounded-full border-2 border-[#00ffe0] border-t-transparent animate-spin" />
            <div className="text-white font-bold text-lg">ממתין להתחברות דרך Google…</div>
            <div className="text-slate-400 text-xs max-w-xs leading-relaxed">
              נפתחה חלונית דפדפן. אשר את חשבון Google שלך שם וההתחברות תושלם
              אוטומטית. אם הדפדפן פתח את הפרופיל הלא נכון — העתק את הקישור
              והדבק אותו בדפדפן שאתה רוצה.
            </div>
            <div className="mt-2 flex items-center gap-2">
              <button
                type="button"
                onClick={copyAuthorizeUrl}
                className={[
                  "px-4 py-1.5 rounded-lg border text-xs font-semibold transition",
                  copied
                    ? "bg-[#00ffe0]/15 border-[#00ffe0]/40 text-[#00ffe0]"
                    : "bg-[#00ffe0]/5 border-[#00ffe0]/25 text-[#00ffe0] hover:bg-[#00ffe0]/10",
                ].join(" ")}
                title="מעתיק את כתובת ההתחברות ללוח — תוכל להדביק בכל דפדפן"
              >
                {copied ? "✓ הקישור הועתק" : "📋 העתק קישור"}
              </button>
              <button
                type="button"
                onClick={cancelGoogle}
                className="px-4 py-1.5 rounded-lg bg-white/5 border border-white/10
                           text-slate-300 hover:bg-white/10 text-xs"
              >
                בטל וחזור
              </button>
            </div>
          </div>
        )}

        {/* brand */}
        <div className="text-center mb-5">
          <div className="inline-block w-11 h-11 rounded-xl bg-[#00ffe0] grid place-items-center
                          shadow-[0_4px_20px_-4px_rgba(0,255,224,0.45)] mb-3">
            <span className="text-[#0a0a14] font-extrabold text-xl">🔐</span>
          </div>
          <h2 className="text-xl font-bold text-white tracking-wide">
            {mode === "login" ? "התחברות" : "הרשמה"}
          </h2>
          <p className="text-slate-400 text-xs mt-1">
            {mode === "login"
              ? "הכנס את פרטיך כדי לגשת לאזור האישי."
              : "צור חשבון חדש לרכישת תרגומים."}
          </p>
        </div>

        {/* tab toggle */}
        <div className="grid grid-cols-2 mb-5 p-1 rounded-xl bg-white/5 border border-white/10">
          <TabPill active={mode === "login"}    onClick={() => setMode("login")}>התחבר</TabPill>
          <TabPill active={mode === "register"} onClick={() => setMode("register")}>הרשם</TabPill>
        </div>

        {/* form */}
        <form onSubmit={submit} className="space-y-3">
          {mode === "register" && (
            <Field label="שם מלא">
              <input
                ref={mode === "register" ? firstInput : undefined}
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                autoComplete="name"
                maxLength={120}
                dir="auto"
                disabled={busy}
                className={inputCls}
              />
            </Field>
          )}
          <Field label="אימייל">
            <input
              ref={mode === "login" ? firstInput : undefined}
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              required
              disabled={busy}
              dir="ltr"
              className={`${inputCls} text-left`}
            />
          </Field>
          <Field label="סיסמה">
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              required
              minLength={mode === "register" ? 8 : undefined}
              disabled={busy}
              dir="ltr"
              className={`${inputCls} text-left`}
            />
          </Field>
          {mode === "register" && (
            <Field label="אימות סיסמה">
              <input
                type="password"
                value={pwConfirm}
                onChange={(e) => setPwConfirm(e.target.value)}
                autoComplete="new-password"
                required
                minLength={8}
                disabled={busy}
                dir="ltr"
                className={`${inputCls} text-left`}
              />
            </Field>
          )}

          {error && (
            <div className="rounded-lg bg-rose-500/10 border border-rose-500/30
                            text-rose-200 text-xs p-2.5 text-center">
              {error}
            </div>
          )}
          {info && (
            <div className="rounded-lg bg-emerald-500/10 border border-emerald-500/30
                            text-emerald-200 text-xs p-2.5 text-center">
              {info}
            </div>
          )}

          <button
            type="submit"
            disabled={busy}
            className="w-full bg-[#00ffe0] hover:bg-cyan-300 text-[#0a0a14] font-bold
                       px-5 py-2.5 rounded-xl transition-all
                       disabled:opacity-40 disabled:cursor-not-allowed
                       shadow-[0_8px_20px_-8px_rgba(0,255,224,0.55)]"
          >
            {busy ? "…" : mode === "login" ? "התחבר" : "הרשם"}
          </button>
        </form>

        {/* divider */}
        <div className="my-4 flex items-center gap-3 text-[10px] tracking-[0.4em] text-slate-500">
          <div className="flex-1 h-px bg-white/10" />
          <span>או</span>
          <div className="flex-1 h-px bg-white/10" />
        </div>

        {/* Google — uses the loopback browser flow. Disabled while
            either the password form OR a previous Google attempt is
            in flight (the latter is also covered by the full-modal
            overlay above; this is defence-in-depth). */}
        <button
          type="button"
          onClick={onGoogle}
          disabled={busy || googleBusy}
          className="w-full flex items-center justify-center gap-3 rounded-xl
                     bg-white text-[#0a0a14] font-semibold px-4 py-2.5
                     border border-white/20 hover:bg-slate-100 transition-all
                     disabled:opacity-40 disabled:cursor-not-allowed
                     shadow-[0_6px_16px_-6px_rgba(255,255,255,0.25)]"
          title="ייפתח דפדפן להשלמת ההתחברות עם Google"
        >
          <GoogleGlyph />
          <span>המשך עם Google</span>
        </button>

        <div className="mt-4 text-center text-[10px] text-slate-500 tracking-wider">
          v1.0 • all credentials handled inside the launcher
        </div>
      </div>
    </div>
  );
}

const inputCls =
  "w-full bg-black/40 border border-white/10 focus:border-[#00ffe0]/50 " +
  "rounded-lg px-3 py-2 text-sm text-slate-100 outline-none";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="block text-[11px] text-slate-400 mb-1 text-right">{label}</span>
      {children}
    </label>
  );
}

function TabPill({
  active, onClick, children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={[
        "py-2 rounded-lg text-sm font-semibold transition",
        active
          ? "bg-[#00ffe0] text-[#0a0a14] shadow-[0_4px_12px_-4px_rgba(0,255,224,0.55)]"
          : "text-slate-300 hover:bg-white/5",
      ].join(" ")}
    >
      {children}
    </button>
  );
}

function GoogleGlyph() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden>
      <path fill="#4285F4" d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.91c1.7-1.57 2.69-3.88 2.69-6.62z"/>
      <path fill="#34A853" d="M9 18c2.43 0 4.47-.81 5.96-2.18l-2.91-2.26c-.81.54-1.84.86-3.05.86-2.34 0-4.33-1.58-5.04-3.71H.96v2.33A9 9 0 0 0 9 18z"/>
      <path fill="#FBBC05" d="M3.96 10.71A5.41 5.41 0 0 1 3.68 9c0-.59.1-1.17.28-1.71V4.96H.96A9 9 0 0 0 0 9c0 1.45.35 2.83.96 4.04l3-2.33z"/>
      <path fill="#EA4335" d="M9 3.58c1.32 0 2.5.45 3.44 1.35l2.58-2.58A9 9 0 0 0 9 0 9 9 0 0 0 .96 4.96l3 2.33C4.67 5.16 6.66 3.58 9 3.58z"/>
    </svg>
  );
}
