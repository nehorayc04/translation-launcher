// Resolve a game's `cover` field (as it arrives from the website's
// /api/games or from Supabase directly) to a renderable `<img src>`.
//
// The catalog DB stores `cover_url` in three different shapes:
//   • bare filename               e.g. "cyberpunk.jpg"
//   • root-relative path          e.g. "/covers/aot2.png"
//   • absolute URL                e.g. "https://.../covers/foo.png"
//
// Inside the launcher (loaded by Eel from http://localhost:<port>/),
// a bare filename like "cyberpunk.jpg" resolves to the eel root and
// 404s - the file is actually bundled at /covers/cyberpunk.jpg.
// This helper normalises every shape to a usable launcher path/URL.
//
// Root-relative paths (case 2) target files served by the live website
// (e.g. software covers seeded after the launcher build). They CANNOT
// just pass through, because in eel the origin is localhost. We prepend
// the live website base URL so the browser fetches from Vercel instead
// of trying to serve from the launcher's local HTTP root.

const REMOTE_BASE = 'https://hebrew-translation-hub.com';
// Covers/banners/logos live in the public Supabase `covers` bucket and are
// STREAMED from the server - they are no longer bundled into the installer
// (it shrank the download; the QtWebEngine disk cache keeps them locally and
// re-fetches if that cache is cleared). This is the fallback when the DB
// `cover` is a bare filename or missing.
const COVERS_BASE = 'https://mfudkftrluabqlrpkvtj.supabase.co/storage/v1/object/public/covers';
const BUCKET_MARK = '/public/covers/';

// ── OFFLINE PACKAGE image mirror ───────────────────────────────
// Covers/banners/logos are ABSOLUTE server URLs, so a machine with no internet
// renders nothing (the QtWebEngine disk cache only helps if it was online once,
// and an installer cannot safely fabricate entries in Chromium's internal cache
// format on another machine). A pre-built offline package therefore ships the
// images and the backend hands us a file:// base + the list it carries.
//
// PREFER LOCAL when the package has the file: it is the same image, paints
// instantly and needs no request. Trade-off (accepted): if an admin later
// replaces a cover on the server, this machine keeps showing the packaged one
// until a fresh package is built - which is exactly the point-in-time nature of
// an offline snapshot.
let _offlineBase = '';
let _offlineRels = new Set<string>();

/** Wire the local mirror (called once at boot from the offline-assets RPC). */
export function initOfflineImages(base: string, rels: string[]): void {
  _offlineBase = (base || '').replace(/\/+$/, '');
  _offlineRels = new Set(Array.isArray(rels) ? rels : []);
}

export function hasOfflineImages(): boolean {
  return !!_offlineBase && _offlineRels.size > 0;
}

/** Apply the offline mirror to an ALREADY-absolute bucket asset (banner/logo,
 *  which the catalog stores as full URLs and never go through resolveCoverUrl). */
export function resolveAssetUrl(url: string | null | undefined): string {
  if (!url) return '';
  return localFor(url) ?? url;
}

/** file:// URL for a remote cover URL, when the package carries that image. */
function localFor(url: string): string | null {
  if (!hasOfflineImages()) return null;
  const i = url.indexOf(BUCKET_MARK);
  if (i < 0) return null;                       // not a bucket image → no mirror
  let rel: string;
  try {
    rel = decodeURIComponent(url.slice(i + BUCKET_MARK.length).split('?')[0]);
  } catch {
    return null;
  }
  // The sub-path matters: a cover and its banner share the SAME basename.
  if (!rel || !_offlineRels.has(rel)) return null;
  return `${_offlineBase}/${rel.split('/').map(encodeURIComponent).join('/')}`;
}

export function resolveCoverUrl(
  cover:   string | null | undefined,
  gameId?: string | null,
): string {
  const remote = resolveRemoteCoverUrl(cover, gameId);
  return localFor(remote) ?? remote;
}

/** The plain server URL, ignoring any offline mirror. */
export function resolveRemoteCoverUrl(
  cover:   string | null | undefined,
  gameId?: string | null,
): string {
  if (cover) {
    // (1) absolute URL - admin upload, external host - pass through.
    if (/^https?:\/\//i.test(cover)) return cover;
    // (2) root-relative path - file lives on the live site; prepend
    //     the remote origin so eel doesn't try to serve from localhost.
    if (cover.startsWith('/'))       return `${REMOTE_BASE}${cover}`;
    // (3) bare filename - resolve to the public covers bucket on the server
    //     (covers are no longer bundled locally).
    const stripped = cover.replace(/^covers\//i, '');
    return `${COVERS_BASE}/${stripped}`;
  }
  // (4) no cover field at all - fall back to the server covers/<id>.webp
  //     convention so seeded games still render even without a DB edit.
  return `${COVERS_BASE}/${gameId ?? 'unknown'}.webp`;
}
