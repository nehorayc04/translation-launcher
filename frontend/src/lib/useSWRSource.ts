// useSWRSource - generic React hook that pairs an initial Eel fetch with
// a subscription to Python's `cache_refreshed` push events.
//
// Flow:
//   1. On mount, call `initialFetch()` - this returns the cached/stale
//      value from Python's SWR layer immediately (no network round-trip
//      on subsequent launches).
//   2. Register a listener into `window.__eelCacheHandlers` (set up by
//      `public/eel-bindings.js`). When Python's background refresh
//      notices the server returned different data, it pushes a
//      `cache_refreshed(kind, data, subKey)` event; the listener filters
//      by `kind` + `subKey` and quietly swaps the data into React state.
//   3. Cleanup on unmount removes the listener.
//
// Why mirror `useDownloadProgress`'s registry pattern? Because the actual
// `eel.expose()` registration must happen in unminified, scanner-friendly
// JS (public/eel-bindings.js) - bundled React code can't safely call
// eel.expose() without tripping eel's HTML parser. The registry is the
// hand-off between the two worlds.
import { useCallback, useEffect, useRef, useState } from "react";

export type SWRKind = "games" | "news" | "updates" | "progress";

type CacheHandler = (kind: string, data: unknown, subKey: string | null) => void;

declare global {
  interface Window {
    __eelCacheHandlers?: CacheHandler[];
  }
}

export interface UseSWRSourceResult<T> {
  /** Current value. `null` until the first fetch completes (or if the
   *  server has no data). */
  data:        T | null;
  /** True between mount and the first fetch resolution. */
  loading:     boolean;
  /** True while a manual `refetch()` is in flight. */
  refreshing:  boolean;
  /** Manually invalidate the local state and re-run `initialFetch()`. */
  refetch:     () => void;
}

/**
 * @param kind          One of the SWR cache kinds Python knows about.
 * @param initialFetch  Function that returns the cached/stale value
 *                      (e.g. `() => api.getAllGames()`). Called on mount
 *                      and on every `refetch()`.
 * @param subKey        Optional sub-key for per-instance kinds like
 *                      "progress" (one entry per game id).
 */
export function useSWRSource<T>(
  kind: SWRKind,
  initialFetch: () => Promise<T>,
  subKey?: string,
): UseSWRSourceResult<T> {
  const [data,       setData]       = useState<T | null>(null);
  const [loading,    setLoading]    = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // Keep the latest fetcher in a ref so the cache-event handler always
  // calls the freshest closure without re-registering on every render.
  const fetchRef = useRef(initialFetch);
  useEffect(() => { fetchRef.current = initialFetch; }, [initialFetch]);

  const runFetch = useCallback(async (markRefreshing: boolean) => {
    if (markRefreshing) setRefreshing(true);
    try {
      const fresh = await fetchRef.current();
      setData(fresh);
    } catch (e) {
      console.warn(`[useSWRSource] initial fetch for ${kind}/${subKey ?? "-"} failed`, e);
    } finally {
      setLoading(false);
      if (markRefreshing) setRefreshing(false);
    }
  }, [kind, subKey]);

  // Initial mount + subKey change: pull current value from Python.
  useEffect(() => {
    runFetch(false);
  }, [runFetch]);

  // Subscribe to Python's `cache_refreshed` pushes.
  useEffect(() => {
    const w = window;
    if (!w.__eelCacheHandlers) w.__eelCacheHandlers = [];
    const handler: CacheHandler = (evtKind, evtData, evtSubKey) => {
      if (evtKind !== kind) return;
      // Treat undefined and null subKeys as equivalent - Python sends
      // `null` for scalar kinds; the hook may not pass `subKey` at all.
      const myKey  = subKey ?? null;
      const evtKey = evtSubKey ?? null;
      if (myKey !== evtKey) return;
      setData(evtData as T);
    };
    w.__eelCacheHandlers.push(handler);
    return () => {
      if (!w.__eelCacheHandlers) return;
      const i = w.__eelCacheHandlers.indexOf(handler);
      if (i >= 0) w.__eelCacheHandlers.splice(i, 1);
    };
  }, [kind, subKey]);

  const refetch = useCallback(() => { runFetch(true); }, [runFetch]);

  return { data, loading, refreshing, refetch };
}
