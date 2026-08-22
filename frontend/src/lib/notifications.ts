// Global notifications + background-activity store (framework-agnostic singleton
// + a React hook). Two jobs:
//
//  1. BACKGROUND ACTIVITIES - the launcher self-update download and mod installs
//     stream progress over onLauncherUpdateProgress / onModProgress. Those events
//     used to live in the DownloadsView SelfUpdatePanel's LOCAL state, so leaving
//     the screen mid-download lost the progress and the panel showed "עדכן עכשיו"
//     again while the download silently kept running (then suddenly installed).
//     Now the store subscribes ONCE at App level (never unmounts) and keeps the
//     live progress, so any screen (the panel, the notifications window) reflects
//     the ongoing download and it never "disappears".
//
//  2. NOTIFICATIONS - admin-controlled SYSTEM notifications (software/plugin
//     updates + system messages), which are a SEPARATE feed from the public
//     `news` (news stays on the home screen). They're edited from a dedicated
//     admin place → `site_config.notifications` (public GET /api/config, CORS-
//     open), shown to every user, plus app-generated "update available" notices.
//     The bell above the avatar shows the state (has-new / none / muted); the
//     floating panel lists everything, with mute + dismiss.
import { useSyncExternalStore } from 'react';
import { onLauncherUpdateProgress, onModProgress } from './eel';

const CONFIG_URL = 'https://hebrew-translation-hub.com/api/config';

export interface Activity {
  id:     string;                        // 'launcher-update' | 'mod-install'
  kind:   'launcher-update' | 'mod';
  title:  string;
  pct:    number;
  phase:  string;                        // download|verify|apply|launch|done|error|cancelled
  detail?: string;
  active: boolean;                       // still running
  error:  boolean;
  ts:     number;
}
export interface Notif {
  id:    string;
  title: string;
  body?: string;
  ts:    number;
  kind:  string;                         // 'news' | 'update' | 'system'
  read:  boolean;
  link?: string | null;                  // game id to deep-link, or null
}
export interface NotifSnapshot {
  activities: Activity[];
  notifs:     Notif[];
  muted:      boolean;
  unread:     number;
  bell:       'none' | 'has' | 'muted';
}

const LS = {
  muted: 'pth.notif.muted', dismissed: 'pth.notif.dismissed', read: 'pth.notif.read',
  // v2: bumped so this build starts with a CLEAN seen-set - the previous logic
  // silently seeded every existing notification as "seen" on first launch, so a
  // pre-existing (e.g. the admin's test) notification could never pop again.
  seen: 'pth.notif.seen2', seenInit: 'pth.notif.seeninit2',
};
const lsGet = (k: string, d: string) => { try { return localStorage.getItem(k) ?? d; } catch { return d; } };
const lsSet = (k: string, v: string) => { try { localStorage.setItem(k, v); } catch { /* ignore */ } };
const parseSet = (s: string) => { try { const a = JSON.parse(s); return new Set<string>(Array.isArray(a) ? a : []); } catch { return new Set<string>(); } };

let activities = new Map<string, Activity>();
let systemNotifs: Notif[] = [];
let extraNotifs: Notif[] = [];
let muted = lsGet(LS.muted, '0') === '1';
const dismissed = parseSet(lsGet(LS.dismissed, '[]'));
const readIds = parseSet(lsGet(LS.read, '[]'));
// Ids already surfaced to the user (so a notif "pops" only ONCE, ever). Seeded
// on the first-ever launch so pre-existing notifs don't all pop at once.
const seenIds = parseSet(lsGet(LS.seen, '[]'));
let seenInited = lsGet(LS.seenInit, '0') === '1';
function markSeen(id: string) { seenIds.add(id); lsSet(LS.seen, JSON.stringify([...seenIds].slice(-800))); }

// A new notification "pops": a top-center toast + a native OS notification
// (handled in App via the "notif-pop" event). MUTED → never pops (the red bell
// dot still appears because unread > 0).
function firePop(n: { title: string; body?: string; link?: string | null }) {
  if (muted) return;
  try { window.dispatchEvent(new CustomEvent('notif-pop', { detail: { title: n.title, body: n.body, link: n.link ?? null } })); } catch { /* ignore */ }
}

const subs = new Set<() => void>();
let inited = false;
let snap: NotifSnapshot | null = null;
let launchTimer: number | null = null;

const ACTIVE = (ph: string) => !['done', 'error', 'cancelled', 'idle', ''].includes(ph);
function emit() { snap = null; subs.forEach((f) => f()); }

export function subscribe(cb: () => void): () => void {
  subs.add(cb);
  return () => { subs.delete(cb); };
}

export function getSnapshot(): NotifSnapshot {
  if (snap) return snap;
  const acts = [...activities.values()].sort((a, b) => b.ts - a.ts);
  const all = [...extraNotifs, ...systemNotifs]
    .filter((n) => !dismissed.has(n.id))
    .map((n) => ({ ...n, read: readIds.has(n.id) }))
    .sort((a, b) => b.ts - a.ts)
    .slice(0, 40);
  const activeCount = acts.filter((a) => a.active).length;
  const unread = all.filter((n) => !n.read).length + activeCount;
  const bell: NotifSnapshot['bell'] = muted ? 'muted' : (unread > 0 ? 'has' : 'none');
  snap = { activities: acts, notifs: all, muted, unread, bell };
  return snap;
}

function upsertActivity(a: Activity) {
  activities.set(a.id, a);
  // Auto-drop a finished activity after ~10s so it doesn't linger forever
  // (but its terminal state is visible meanwhile).
  if (!a.active) {
    window.setTimeout(() => {
      const cur = activities.get(a.id);
      if (cur && !cur.active && cur.ts === a.ts) { activities.delete(a.id); emit(); }
    }, 10_000);
  }
  emit();
}

/** Wire the global progress subscriptions ONCE. Call from App on boot. */
export function initNotifications() {
  if (inited) return;
  inited = true;

  onLauncherUpdateProgress((p) => {
    upsertActivity({
      id: 'launcher-update', kind: 'launcher-update', title: 'עדכון התוכנה',
      pct: p.pct, phase: p.phase, detail: p.detail,
      active: ACTIVE(p.phase), error: p.phase === 'error', ts: Date.now(),
    });
    // UAC-dismissed watchdog - GLOBAL now (fires even if no screen is mounted):
    // "launch" means the installer was spawned; if we're still alive ~30s later,
    // the UAC prompt was likely declined → surface an error instead of a stuck bar.
    if (launchTimer !== null) { window.clearTimeout(launchTimer); launchTimer = null; }
    if (p.phase === 'launch') {
      launchTimer = window.setTimeout(() => {
        upsertActivity({
          id: 'launcher-update', kind: 'launcher-update', title: 'עדכון התוכנה',
          pct: 0, phase: 'error', active: false, error: true, ts: Date.now(),
          detail: 'ההתקנה לא התחילה - ייתכן שחלון ההרשאות (UAC) נדחה. נסה שוב.',
        });
      }, 30_000);
    }
  });

  onModProgress((p) => {
    upsertActivity({
      id: 'mod-install', kind: 'mod', title: 'התקנת תרגום',
      pct: p.pct, phase: p.phase, detail: p.detail,
      active: ACTIVE(p.phase), error: p.phase === 'error', ts: Date.now(),
    });
  });

  void refreshSystemNotifs();
  window.setInterval(() => { void refreshSystemNotifs(); }, 5 * 60 * 1000);

  // Also re-check the moment the launcher regains focus (throttled to ~8s), so a
  // notification the admin just added POPS within a second of returning to the
  // app instead of waiting out the 5-minute poll.
  let lastFocusPoll = 0;
  const onFocus = () => {
    const now = Date.now();
    if (now - lastFocusPoll < 8000) return;
    lastFocusPoll = now;
    void refreshSystemNotifs();
  };
  window.addEventListener('focus', onFocus);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) onFocus(); });
}

/** Pull the admin-controlled SYSTEM notifications (separate from news) from the
 *  site config (`/api/config` → `config.notifications`, CORS-open public GET). */
export async function refreshSystemNotifs() {
  try {
    const r = await fetch(CONFIG_URL, { headers: { Accept: 'application/json' } });
    const doc = await r.json();
    const arr: unknown = doc?.config?.notifications;
    if (!Array.isArray(arr)) { systemNotifs = []; emit(); return; }
    systemNotifs = arr
      .filter((n): n is Record<string, unknown> => !!n && typeof n === 'object'
        && (n as Record<string, unknown>).active !== false
        && !!(n as Record<string, unknown>).title)
      .slice(0, 30)
      .map((n) => ({
        id: 'sys:' + String(n.id ?? n.title),
        title: String(n.title),
        body: n.body ? String(n.body) : undefined,
        ts: n.ts ? (Date.parse(String(n.ts)) || Date.now()) : Date.now(),
        kind: n.kind ? String(n.kind) : 'system',
        read: false,
        link: (n.link as string | null | undefined) ?? null,
      }));
    // Pop the genuinely-new notifications (never seen, not already read/dismissed),
    // most-recent first. Capped so a first-launch backfill can't flood the screen,
    // and everything is marked seen so it pops exactly ONCE. `firePop` respects
    // mute (muted → no pop, only the red bell dot).
    const pool = [...systemNotifs, ...extraNotifs];
    const fresh = pool
      .filter((n) => !seenIds.has(n.id) && !readIds.has(n.id) && !dismissed.has(n.id))
      .sort((a, b) => b.ts - a.ts);
    for (const n of pool) markSeen(n.id);      // baseline: everything is now "seen"
    if (!seenInited) { seenInited = true; lsSet(LS.seenInit, '1'); }
    for (const n of fresh.slice(0, 2)) firePop(n);   // pop up to the 2 newest
    emit();
  } catch { /* offline → keep the last set */ }
}

/** App-generated notice (e.g. "translation update available"). Idempotent by id. */
export function pushNotif(n: { id: string; title: string; body?: string; kind?: string; link?: string | null }) {
  if (extraNotifs.some((x) => x.id === n.id) || dismissed.has(n.id)) return;
  extraNotifs.unshift({ id: n.id, title: n.title, body: n.body, ts: Date.now(), kind: n.kind || 'system', read: false, link: n.link });
  extraNotifs = extraNotifs.slice(0, 20);
  // A deliberate app notice → pop once (firePop respects mute).
  if (!seenIds.has(n.id)) { markSeen(n.id); firePop({ title: n.title, body: n.body, link: n.link }); }
  emit();
}

export function getActivity(id: string): Activity | null { return activities.get(id) ?? null; }
export function dismiss(id: string) { dismissed.add(id); lsSet(LS.dismissed, JSON.stringify([...dismissed])); emit(); }
export function clearAllNotifs() {
  for (const n of getSnapshot().notifs) dismissed.add(n.id);
  lsSet(LS.dismissed, JSON.stringify([...dismissed].slice(-500)));
  emit();
}
export function markAllRead() {
  for (const n of getSnapshot().notifs) readIds.add(n.id);
  lsSet(LS.read, JSON.stringify([...readIds].slice(-500)));
  emit();
}
export function setMuted(m: boolean) { muted = m; lsSet(LS.muted, m ? '1' : '0'); emit(); }
export function isMuted() { return muted; }

// ── React bindings ───────────────────────────────────────────────────
export function useNotifications(): NotifSnapshot {
  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
}
export function useActivity(id: string): Activity | null {
  const s = useNotifications();
  return s.activities.find((a) => a.id === id) ?? null;
}
