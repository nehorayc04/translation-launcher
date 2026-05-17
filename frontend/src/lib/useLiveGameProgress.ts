// Small launcher-side hook that pulls /api/progress?game=<id> via the
// Eel bridge (`api.getLiveProgress`). Shared by:
//   • GameCard            (mini bar on each in-progress tile)
//   • GameDetailPanel     (big bar above the action buttons)
//   • ProgressDashboard   (home-view live card)
//
// Behavior:
//   • No-ops when `enabled` is false or `api` isn't ready (dev UI mode).
//   • Re-fetches when `refreshNonce` bumps — App's sidebar refresh
//     button increments that counter, so one click updates everything.
//   • Optional `pollMs` polls in the background; set to 0 to disable.
//   • Silent on errors: keeps the last good snapshot in state.
//
// Returns: { snap, loaded }
//   loaded === false  → no fetch has completed yet (initial mount).
//                       Consumers should render an empty/0% state so the
//                       OLD static `game.progress` doesn't briefly flash.
//   loaded === true && snap === null  → server confirmed no row exists.
//                                       Consumers may fall back to static.
//   loaded === true && snap            → live data; use processed/total.
import { useEffect, useRef, useState } from "react";
import { api, type ProgressSnapshot } from "./eel";

export interface UseLiveGameProgressOpts {
  enabled?:      boolean;
  refreshNonce?: number;
  /** Background poll interval in ms. 0 disables polling (mount-only). */
  pollMs?:       number;
}

export interface LiveProgressState {
  snap:    ProgressSnapshot | null;
  loaded:  boolean;
}

export function useLiveGameProgress(
  gameId: string,
  { enabled = true, refreshNonce = 0, pollMs = 0 }: UseLiveGameProgressOpts = {},
): LiveProgressState {
  const [state, setState] = useState<LiveProgressState>({ snap: null, loaded: false });
  const timer = useRef<number | null>(null);

  // Reset to loading whenever we switch to a different game so the
  // previous game's number doesn't briefly render under the new title.
  useEffect(() => {
    setState({ snap: null, loaded: false });
  }, [gameId]);

  useEffect(() => {
    if (!enabled || !gameId || !api.ready()) return;
    let cancelled = false;

    const tick = async () => {
      try {
        const data = await api.getLiveProgress(gameId);
        if (!cancelled) setState({ snap: data, loaded: true });
      } catch {
        // Network blip — mark loaded so the consumer can fall back to
        // its static value rather than waiting forever at 0%.
        if (!cancelled) setState((s) => ({ snap: s.snap, loaded: true }));
      }
    };

    tick();
    if (pollMs > 0) {
      timer.current = window.setInterval(tick, pollMs);
    }

    return () => {
      cancelled = true;
      if (timer.current !== null) {
        window.clearInterval(timer.current);
        timer.current = null;
      }
    };
  }, [gameId, enabled, refreshNonce, pollMs]);

  // SWR push subscription — Python's background refresh fires
  // cache_refreshed("progress", data, gameId) whenever it notices the
  // server returned different numbers. Skips a full poll round-trip.
  useEffect(() => {
    if (!enabled || !gameId) return;
    const w = window as unknown as { __eelCacheHandlers?: ((k: string, d: unknown, s: string | null) => void)[] };
    if (!w.__eelCacheHandlers) w.__eelCacheHandlers = [];
    const handler = (kind: string, data: unknown, subKey: string | null) => {
      if (kind !== "progress" || subKey !== gameId) return;
      setState({ snap: data as ProgressSnapshot | null, loaded: true });
    };
    w.__eelCacheHandlers.push(handler);
    return () => {
      if (!w.__eelCacheHandlers) return;
      const i = w.__eelCacheHandlers.indexOf(handler);
      if (i >= 0) w.__eelCacheHandlers.splice(i, 1);
    };
  }, [gameId, enabled]);

  return state;
}
