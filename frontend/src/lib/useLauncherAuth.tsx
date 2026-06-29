// React context that mirrors the Python auth subsystem's state into
// the launcher UI. Lifecycle:
//
//   • On mount: call authMe() — if the keyring has a valid session
//     we get a user back; otherwise null.
//   • signIn() blocks the browser sign-in flow on the Python side
//     (opens system browser → loopback callback → token exchange).
//   • signOut() clears the keyring entry and the in-React user.
//   • ownsGame(id) hits the Supabase REST API via Python (RLS-scoped
//     to auth.uid()) — small in-memory cache so a render loop over
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
  /** OAuth (Google) — opens system browser via loopback listener. */
  signInGoogle: () => Promise<{ ok: boolean; error?: string }>;
  /** Abort an in-flight Google sign-in (kills the loopback HTTP
   *  server immediately so a fresh attempt can re-bind the port). */
  cancelGoogleSignIn: () => Promise<void>;
  /** Email/password — entirely inside the launcher window. */
  signInPassword: (email: string, password: string) => Promise<{ ok: boolean; error?: string }>;
  signUpPassword: (email: string, password: string, fullName: string)
    => Promise<{ ok: boolean; confirmed?: boolean; error?: string }>;
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

  const refresh = useCallback(async () => {
    try {
      const u = await api.authMe();
      const prevId = userRef.current?.id ?? null;
      const nextId = u?.id ?? null;
      // Only invalidate the ownership cache when the identity actually
      // changes — the 60 s poll calls refresh() repeatedly and clearing
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
      // Transport/bridge hiccup — DON'T sign out (Python me() already keeps
      // the session on a transient error and returns the cached identity).
      // Leaving `user` as-is avoids the "logged out after a while" bug.
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!api.ready()) { setLoading(false); return; }
    void refresh();
    // Poll every 60 s so a displaced install (another device signed into the
    // same account) disconnects on its own, and a revoked session is noticed
    // promptly rather than lingering on a stale access token.
    const id = window.setInterval(() => { void refresh(); }, 60_000);
    return () => window.clearInterval(id);
  }, [refresh]);

  // Note: none of the operation methods below mutate `loading`. That
  // flag is reserved for the INITIAL bootstrap (authMe on mount); if
  // we flipped it during sign-in, the Sidebar's `if (loading) return
  // <shim>` branch fires and unmounts the AuthModal mid-flow — which
  // for Google OAuth means the user is left with a stuck loading
  // sidebar and no way to cancel. Callers (AuthModal) track their
  // own busy state instead.

  const signInGoogle = useCallback(async () => {
    try {
      const r = await api.authLogin();
      if (r.ok && r.user) {
        setUser(r.user);
        ownershipCache.current.clear();
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
      // best-effort — the awaiting login() Promise will reject with
      // "cancelled" and the modal's onGoogle handler already routes
      // that to a benign close.
    }
  }, []);

  const signInPassword = useCallback(async (email: string, password: string) => {
    try {
      const r = await api.authSignInPassword(email, password);
      if (r.ok && r.user) {
        setUser(r.user);
        ownershipCache.current.clear();
        return { ok: true };
      }
      return { ok: false, error: r.error };
    } catch (e) {
      return { ok: false, error: (e as Error).message };
    }
  }, []);

  const signUpPassword = useCallback(async (email: string, password: string, fullName: string) => {
    try {
      const r = await api.authSignUpPassword(email, password, fullName);
      if (!r.ok) return { ok: false, error: r.error };
      if (r.confirmed && r.user) {
        // Project allows immediate sign-in (no email confirmation).
        setUser(r.user);
        ownershipCache.current.clear();
      }
      // If not confirmed, stay signed out — caller surfaces the
      // "check your inbox" UX based on the `confirmed` flag.
      return { ok: true, confirmed: !!r.confirmed };
    } catch (e) {
      return { ok: false, error: (e as Error).message };
    }
  }, []);

  const signOut = useCallback(async () => {
    try { await api.authLogout(); } catch { /* swallow */ }
    setUser(null);
    ownershipCache.current.clear();
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
    signOut,
    refresh,
    ownsGame,
  }), [user, loading, signInGoogle, cancelGoogleSignIn, signInPassword, signUpPassword, signOut, refresh, ownsGame]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useLauncherAuth(): LauncherAuthValue {
  const v = useContext(Ctx);
  if (!v) throw new Error("useLauncherAuth must be used inside <LauncherAuthProvider>");
  return v;
}
