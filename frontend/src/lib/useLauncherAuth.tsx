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
  signIn:    () => Promise<{ ok: boolean; error?: string }>;
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

  const signIn = useCallback(async () => {
    setLoading(true);
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
    } finally {
      setLoading(false);
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
    signIn,
    signOut,
    refresh,
    ownsGame,
  }), [user, loading, signIn, signOut, refresh, ownsGame]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useLauncherAuth(): LauncherAuthValue {
  const v = useContext(Ctx);
  if (!v) throw new Error("useLauncherAuth must be used inside <LauncherAuthProvider>");
  return v;
}
