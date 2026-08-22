// React context that mirrors the Python auth subsystem's state into
// the launcher UI. Lifecycle:
//
//   • On mount: call authMe() - if the keyring has a valid session
//     we get a user back; otherwise null.
//   • signIn() blocks the browser sign-in flow on the Python side
//     (opens system browser → loopback callback → token exchange).
//   • signOut() clears the keyring entry and the in-React user.
//   • ownsGame(id) hits the Supabase REST API via Python (RLS-scoped
//     to auth.uid()) - small in-memory cache so a render loop over
//     many games doesn't fire one HTTP per card.
import {
  createContext, useCallback, useContext, useEffect,
  useMemo, useRef, useState, type ReactNode,
} from "react";
import { api, type LauncherUser } from "./eel";

interface LauncherAuthValue {
  user:      LauncherUser | null;
  loading:   boolean;
  signedIn:  boolean;
  /** OAuth (Google) - opens system browser via loopback listener.
   *  `mfaRequired` ⇒ the account has 2FA; call `verifyMfa` with the code. */
  signInGoogle: () => Promise<{ ok: boolean; mfaRequired?: boolean; email?: string; error?: string }>;
  /** Abort an in-flight Google sign-in (kills the loopback HTTP
   *  server immediately so a fresh attempt can re-bind the port). */
  cancelGoogleSignIn: () => Promise<void>;
  /** Email/password - entirely inside the launcher window.
   *  `mfaRequired` ⇒ 2FA account; finish with `verifyMfa`. */
  signInPassword: (email: string, password: string) => Promise<{ ok: boolean; mfaRequired?: boolean; email?: string; error?: string }>;
  signUpPassword: (email: string, password: string, fullName: string)
    => Promise<{ ok: boolean; confirmed?: boolean; error?: string }>;
  /** Complete a pending 2FA login with the 6-digit TOTP code. */
  verifyMfa: (code: string) => Promise<{ ok: boolean; error?: string }>;
  /** Abandon a pending 2FA challenge (user closed the code screen). */
  cancelMfa: () => Promise<void>;
  signOut:   () => Promise<void>;
  refresh:   () => Promise<void>;
  ownsGame:  (gameId: string) => Promise<boolean>;
}

const Ctx = createContext<LauncherAuthValue | null>(null);

export function LauncherAuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<LauncherUser | null>(null);
  const [loading, setLoading] = useState(true);

  // Per-session ownership cache so a library view doesn't issue
  // one HTTP per card on every render.
  const ownershipCache = useRef<Map<string, boolean>>(new Map());

  // Mirror of `user` kept in a ref so the periodic poll's refresh() can read
  // the CURRENT identity (set by a poll OR a sign-in OR a sign-out) without a
  // stale closure, to detect a signed-in → signed-out transition.
  const userRef = useRef<LauncherUser | null>(null);
  useEffect(() => { userRef.current = user; }, [user]);

  // Monotonic auth-transition counter. Bumped on every EXPLICIT sign-in/
  // up/verify/out (via commitUser) so a refresh() poll already in flight
  // can tell an auth change happened mid-await and DROP its now-stale
  // authMe() result instead of clobbering the fresh identity. This is what
  // fixes the "login window flashes and comes back" race: a poll's
  // authMe() resolving null right after a fresh sign-in must not win.
  const authEpoch = useRef(0);
  const commitUser = useCallback((u: LauncherUser | null) => {
    authEpoch.current += 1;
    setUser(u);
    ownershipCache.current.clear();
  }, []);

  const refresh = useCallback(async () => {
    const epoch = authEpoch.current;
    try {
      const u = await api.authMe();
      // An explicit sign-in/out fired WHILE this poll was in flight → its
      // result is authoritative, not ours. Dropping this stale poll result
      // kills the login-window flash (an authMe() that resolves null right
      // after a fresh sign-in must NOT clobber the just-set user).
      if (authEpoch.current !== epoch) return;
      const prevId = userRef.current?.id ?? null;
      const nextId = u?.id ?? null;
      // Only invalidate the ownership cache when the identity actually
      // changes - the 60 s poll calls refresh() repeatedly and clearing
      // unconditionally would defeat the cache.
      if (prevId !== nextId) ownershipCache.current.clear();
      // Signed-in → signed-out transition. Single-session enforcement makes
      // the Python me() sign us out when another launcher install claims the
      // account; ask whether THAT is why, and if so explain it.
      if (prevId && !nextId) {
        try {
          if (await api.authConsumeTakeover()) {
            const msg = "נותקת מהמכשיר הזה כי נכנסת לחשבון מאותו משתמש במכשיר אחר.";
            window.dispatchEvent(new CustomEvent("auth-takeover", { detail: { message: msg } }));
            void api.notifyOs("התנתקת מהחשבון", msg).catch(() => {});
          }
        } catch { /* best-effort */ }
      }
      setUser(u ?? null);
    } catch {
      // Transport/bridge hiccup - DON'T sign out (Python me() already keeps
      // the session on a transient error and returns the cached identity).
      // Leaving `user` as-is avoids the "logged out after a while" bug.
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    let pollId = 0;
    const startPoll = () => {
      void refresh();
      // Poll every 60 s so a displaced install (another device signed into the
      // same account) disconnects on its own, and a revoked session is noticed
      // promptly rather than lingering on a stale access token.
      pollId = window.setInterval(() => { void refresh(); }, 60_000);
    };
    if (api.ready()) {
      startPoll();
    } else {
      // On the Qt build the QWebChannel bridge is often attached AFTER React's
      // first mount (App.tsx retries api.ready() for ~5s for the same reason).
      // A hard bail here would leave a valid persisted session showing as
      // signed-out AND never start the single-session poll - so wait for the
      // bridge instead of giving up.
      let tries = 0;
      const wait = window.setInterval(() => {
        if (cancelled) { window.clearInterval(wait); return; }
        if (api.ready()) { window.clearInterval(wait); startPoll(); }
        else if (++tries > 50) { window.clearInterval(wait); setLoading(false); } // ~10s
      }, 200);
      return () => { cancelled = true; window.clearInterval(wait); if (pollId) window.clearInterval(pollId); };
    }
    return () => { cancelled = true; if (pollId) window.clearInterval(pollId); };
  }, [refresh]);

  // Note: none of the operation methods below mutate `loading`. That
  // flag is reserved for the INITIAL bootstrap (authMe on mount); if
  // we flipped it during sign-in, the Sidebar's `if (loading) return
  // <shim>` branch fires and unmounts the AuthModal mid-flow - which
  // for Google OAuth means the user is left with a stuck loading
  // sidebar and no way to cancel. Callers (AuthModal) track their
  // own busy state instead.

  const signInGoogle = useCallback(async () => {
    try {
      const r = await api.authLogin();
      if (r.ok && r.mfaRequired) {
        // 2FA account - don't set the user; the modal shows the code screen.
        return { ok: true, mfaRequired: true, email: r.email };
      }
      if (r.ok && r.user) {
        commitUser(r.user);
        return { ok: true };
      }
      return { ok: false, error: r.error };
    } catch (e) {
      return { ok: false, error: (e as Error).message };
    }
  }, []);

  const cancelGoogleSignIn = useCallback(async () => {
    try {
      await api.authAbortLogin();
    } catch {
      // best-effort - the awaiting login() Promise will reject with
      // "cancelled" and the modal's onGoogle handler already routes
      // that to a benign close.
    }
  }, []);

  const signInPassword = useCallback(async (email: string, password: string) => {
    try {
      const r = await api.authSignInPassword(email, password);
      if (r.ok && r.mfaRequired) {
        // 2FA account - don't set the user; the modal shows the code screen.
        return { ok: true, mfaRequired: true, email: r.email };
      }
      if (r.ok && r.user) {
        commitUser(r.user);
        return { ok: true };
      }
      return { ok: false, error: r.error };
    } catch (e) {
      return { ok: false, error: (e as Error).message };
    }
  }, []);

  // Complete a pending 2FA login. On success the aal2 session is stored on the
  // Python side and the user dict returned - set it as the signed-in identity.
  const verifyMfa = useCallback(async (code: string) => {
    try {
      const r = await api.authVerifyMfa(code);
      if (r.ok && r.user) {
        commitUser(r.user);
        return { ok: true };
      }
      return { ok: false, error: r.error };
    } catch (e) {
      return { ok: false, error: (e as Error).message };
    }
  }, []);

  const cancelMfa = useCallback(async () => {
    try { await api.authCancelMfa(); } catch { /* best-effort */ }
  }, []);

  const signUpPassword = useCallback(async (email: string, password: string, fullName: string) => {
    try {
      const r = await api.authSignUpPassword(email, password, fullName);
      if (!r.ok) return { ok: false, error: r.error };
      if (r.confirmed && r.user) {
        // Project allows immediate sign-in (no email confirmation).
        commitUser(r.user);
      }
      // If not confirmed, stay signed out - caller surfaces the
      // "check your inbox" UX based on the `confirmed` flag.
      return { ok: true, confirmed: !!r.confirmed };
    } catch (e) {
      return { ok: false, error: (e as Error).message };
    }
  }, []);

  const signOut = useCallback(async () => {
    try { await api.authLogout(); } catch { /* swallow */ }
    commitUser(null);
  }, []);

  const ownsGame = useCallback(async (gameId: string) => {
    if (!user) return false;
    const cached = ownershipCache.current.get(gameId);
    if (cached !== undefined) return cached;
    try {
      const owns = await api.authOwnsGame(gameId);
      ownershipCache.current.set(gameId, owns);
      return owns;
    } catch {
      return false;
    }
  }, [user]);

  const value: LauncherAuthValue = useMemo(() => ({
    user,
    loading,
    signedIn: !!user,
    signInGoogle,
    cancelGoogleSignIn,
    signInPassword,
    signUpPassword,
    verifyMfa,
    cancelMfa,
    signOut,
    refresh,
    ownsGame,
  }), [user, loading, signInGoogle, cancelGoogleSignIn, signInPassword, signUpPassword, verifyMfa, cancelMfa, signOut, refresh, ownsGame]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useLauncherAuth(): LauncherAuthValue {
  const v = useContext(Ctx);
  if (!v) throw new Error("useLauncherAuth must be used inside <LauncherAuthProvider>");
  return v;
}
