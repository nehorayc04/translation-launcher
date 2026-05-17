// Singleton subscriber for download progress events.
//
// The actual `eel.expose("update_download_progress", ...)` registration
// lives in `public/eel-bindings.js` — a static, unminified script. That's
// because Vite/Rolldown can emit string literals as template-literal
// backticks, and eel's HTML scanner then mis-captures the exposed name
// (e.g. `` `update_download_progress` ``) which crashes Python on boot.
//
// This hook simply pushes a listener into the global registry that the
// static bindings dispatch to.
import { useEffect, useState } from "react";
import type { DownloadState } from "./eel";

export interface ProgressEntry {
  pct:   number;
  speed: string;
  state: DownloadState;
}

const progressMap: Map<string, ProgressEntry> = new Map();
const listeners:   Set<() => void>            = new Set();

function notify() { listeners.forEach((fn) => fn()); }

function onEvent(itemId: string, pct: number, speed: string, state: DownloadState) {
  progressMap.set(itemId, { pct, speed, state });
  notify();
  if (state !== "running") {
    setTimeout(() => {
      const e = progressMap.get(itemId);
      if (e && e.state !== "running") {
        progressMap.delete(itemId);
        notify();
      }
    }, 4000);
  }
}

// Register against the global registry created by eel-bindings.js.
// The bindings file may load slightly before or after this module — both
// orderings work because the registry is just an Array.
const w = window as any;
if (!w.__eelDLHandlers) w.__eelDLHandlers = [];
w.__eelDLHandlers.push(onEvent);

export function useDownloadProgress(): Map<string, ProgressEntry> {
  const [, setTick] = useState(0);
  useEffect(() => {
    const fn = () => setTick((t) => t + 1);
    listeners.add(fn);
    return () => { listeners.delete(fn); };
  }, []);
  return progressMap;
}
