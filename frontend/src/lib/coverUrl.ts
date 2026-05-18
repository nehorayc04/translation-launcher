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
export function resolveCoverUrl(
  cover:   string | null | undefined,
  gameId?: string | null,
): string {
  if (cover) {
    // (1) absolute URL — admin upload, external host — pass through.
    if (/^https?:\/\//i.test(cover)) return cover;
    // (2) already a root-relative path — pass through.
    if (cover.startsWith('/'))       return cover;
    // (3) bare filename — map to the bundled /covers/<filename>.
    const stripped = cover.replace(/^covers\//i, '');
    return `/covers/${stripped}`;
  }
  // (4) no cover field at all — fall back to the bundled /covers/<id>.jpg
  //     convention so seeded games render even without a DB edit.
  return `/covers/${gameId ?? 'unknown'}.jpg`;
}
