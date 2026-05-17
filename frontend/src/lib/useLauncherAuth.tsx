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

  const refresh = useCallback(async () => {
    try {
      const u = await api.authMe();
      setUser(u ?? null);
      // Identity changed → invalidate ownership cache.
      ownershipCache.current.clear();
    } catch {
      setUser(null);
      ownershipCache.current.clear();
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!api.ready()) { setLoading(false); return; }
    void refresh();
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
    signInPassword,
    signUpPassword,
    signOut,
    refresh,
    ownsGame,
  }), [user, loading, signInGoogle, signInPassword, signUpPassword, signOut, refresh, ownsGame]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useLauncherAuth(): LauncherAuthValue {
  const v = useContext(Ctx);
  if (!v) throw new Error("useLauncherAuth must be used inside <LauncherAuthProvider>");
  return v;
}
