// Thin wrapper around window.eel that adds typings + promise interop.
// All Python @eel.expose functions are wrapped here.
import type { Game, OpResult, ScanResult } from "./types";

// Eel attaches functions to window.eel.<name>. Calling them returns a thunk
// that, when called with (), starts an async RPC; resolving requires
// awaiting eel's promise-style return.
declare global {
  interface Window {
    eel: any;
  }
}

// Mock for when running the React dev server WITHOUT the python backend
// (e.g. when iterating on UI alone). Returns sensible empty fallbacks so
// the app still renders.
function isEelReady(): boolean {
  return typeof window !== "undefined" && !!window.eel;
}

async function call<T>(name: string, ...args: unknown[]): Promise<T> {
  if (!isEelReady()) {
    console.warn(`[eel] not ready — call ${name} bypassed`);
    throw new Error(`eel unavailable: ${name}`);
  }
  const fn = window.eel[name];
  if (typeof fn !== "function") {
    throw new Error(`eel function not exposed: ${name}`);
  }
  return new Promise<T>((resolve, reject) => {
    try {
      fn(...args)((result: T) => resolve(result));
    } catch (e) {
      reject(e);
    }
  });
}

export type UpdateKind = "system" | "translation";
export type DownloadState = "running" | "done" | "cancelled" | "error";

export interface UpdateItem {
  id:        string;
  kind:      UpdateKind;
  title:     string;
  version:   string;
  size_mb:   number;
  notes:     string;
  url:       string | null;
  simulated: boolean;
}

export interface ProgressSnapshot {
  gameId:        string;
  phase:         string;
  phaseLabelHe:  string | null;
  processed:     number;
  total:         number;
  ratePerHour:   number;
  unit:          string;
  gpuModel:      string;
  aiModel:       string;
  meta:          unknown;
  updatedAt:     number | null;
}

export interface NewsItem {
  id:     string;
  date:   string;        // ISO yyyy-mm-dd
  kind:   "system" | "mod" | string;
  badge:  string | null; // "חדש" / "מוד חדש" / null
  title:  string;
  detail: string;
  link:   string | null; // game id to deep-link to, or null
}

export const api = {
  ready:            (): boolean => isEelReady(),
  getAllGames:      ()                          => call<Game[]>("get_all_games"),
  getGame:          (id: string)                => call<Game>("get_game", id),
  getNews:          ()                          => call<NewsItem[]>("get_news"),
  refreshCatalog:   ()                          => call<{games: Game[]; news: NewsItem[]; catalog_source: string; news_source: string}>("refresh_catalog"),
  scanQuick:        ()                          => call<ScanResult>("scan_quick"),
  scanDeep:         ()                          => call<ScanResult>("scan_deep"),
  setCustomPath:    (id: string, p: string)     => call<Game>("set_custom_path", id, p),
  clearCustomPath:  (id: string)                => call<Game>("clear_custom_path", id),
  enableMod:        (id: string)                => call<OpResult>("enable_mod_for", id),
  disableMod:       (id: string)                => call<OpResult>("disable_mod_for", id),
  uninstallMod:     (id: string)                => call<OpResult>("uninstall_mod_for", id),
  launchGame:       (id: string)                => call<OpResult>("launch_game", id),
  openFolder:       (p: string)                 => call<OpResult>("open_folder", p),
  listUpdates:      ()                          => call<UpdateItem[]>("list_updates"),
  getLiveProgress:  (id: string)                => call<ProgressSnapshot | null>("get_live_progress", id),
  startDownload:    (id: string)                => call<{ok: boolean; error?: string}>("start_download", id),
  cancelDownload:   (id: string)                => call<{ok: boolean; error?: string}>("cancel_download", id),
};
