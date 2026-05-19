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
// 404s — the file is actually bundled at /covers/cyberpunk.jpg.
// This helper normalises every shape to a usable launcher path/URL.
//
// Root-relative paths (case 2) target files served by the live website
// (e.g. software covers seeded after the launcher build). They CANNOT
// just pass through, because in eel the origin is localhost. We prepend
// the live website base URL so the browser fetches from Vercel instead
// of trying to serve from the launcher's local HTTP root.

const REMOTE_BASE = 'https://hebrew-translation-hub.vercel.app';

export function resolveCoverUrl(
  cover:   string | null | undefined,
  gameId?: string | null,
): string {
  if (cover) {
    // (1) absolute URL — admin upload, external host — pass through.
    if (/^https?:\/\//i.test(cover)) return cover;
    // (2) root-relative path — file lives on the live site; prepend
    //     the remote origin so eel doesn't try to serve from localhost.
    if (cover.startsWith('/'))       return `${REMOTE_BASE}${cover}`;
    // (3) bare filename — map to the bundled /covers/<filename>.
    const stripped = cover.replace(/^covers\//i, '');
    return `/covers/${stripped}`;
  }
  // (4) no cover field at all — fall back to the bundled /covers/<id>.jpg
  //     convention so seeded games render even without a DB edit.
  return `/covers/${gameId ?? 'unknown'}.jpg`;
}
