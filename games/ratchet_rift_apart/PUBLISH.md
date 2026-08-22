# Ratchet & Clank: Rift Apart - go-live checklist

Status: **LIVE ON THE WEBSITE + LAUNCHER CATALOG** (2026-07-02). The `games` DB row is
inserted (`availability=planned`, free, `show_on_website=true`, `show_on_launcher=true`), the
3 images are uploaded to the public `covers` bucket, and the website is deployed. Because both
the website grid and the launcher read the LIVE server catalog, the "מתוכנן" card shows on BOTH
right now, with no launcher rebuild. Verified: `/api/games` returns `ratchet-rift-apart`;
cover/banner/logo URLs HEAD 200.

**Still NOT done (only on an explicit "פרסם"):** the launcher RELEASE (step 4) - needed only so
OFFLINE users get the bundled-catalog entry + the `game_detector` pattern. The live card already
shows without it, so this is optional/low-priority.

## DONE 2026-07-02
- [x] `covers/ratchet-rift-apart.webp` (600x900), `banners/ratchet-rift-apart.webp` (1600x517),
      `logos/ratchet-rift-apart.png` (360x154) uploaded to the public `covers` bucket.
- [x] Supabase `games` row inserted (id `ratchet-rift-apart`, planned, price 0, stage stable,
      cover/banner/logo URLs set, both show flags true).
- [x] Website deployed (`vercel --prod`) - ships the `games.ts` SEO/structured-data entry.
- [ ] Launcher release (step 4 below) - deferred until "פרסם".

- **id:** `ratchet-rift-apart` (same in `games_catalog.py`, `game_detector.py`, website `games.ts`,
  and the future Supabase `games` row - they MUST match).
- **availability:** planned · **price:** 0 (free placeholder card).
- **assets/** here: `cover.png` (portrait capsule), `banner.png` (3840x1240 wide), `logo.png`
  (transparent wordmark).

## When the user says "פרסם" (publish)

1. **Upload the 3 images to the public Supabase `covers` bucket** (same convention as the
   2026-06-28 banner upload - see `scratchpad/upload_banners.py` as a template):
   - `covers/ratchet-rift-apart.webp`  (re-encode cover.png -> webp, longest edge <=1600, q82)
   - `banners/ratchet-rift-apart.webp` (re-encode banner.png -> webp, <=1600px, q82)
   - `logos/ratchet-rift-apart.png`    (logo.png, keep alpha, <=360px)
2. **Insert the Supabase `games` row** (service key from `website/.env`): `id='ratchet-rift-apart'`,
   `title_en='Ratchet & Clank: Rift Apart'`, `title_he="רצ'ט אנד קלאנק: ריפט אפארט"`,
   `availability='planned'`, `status='locked'`, `cover_url` = the absolute bucket URL (or leave
   null -> the launcher/website fall back to `covers/<id>.webp`), `banner_url`, `logo_url`,
   `price_cents=0`, `show_on_website=true`, `show_on_launcher=true`.
   - The **launcher shows it live immediately** (it reads the live catalog).
   - The **website grid shows it live** too (grid is DB-driven via `useDynamicGames`).
3. **Deploy the website** (`cd website && vercel --prod`) - ships the `games.ts` SEO/structured-data
   entry (the grid already updated from the DB in step 2).
4. **Publish the launcher release** (`build_exe.bat` -> ISCC -> `publish_release.py 1.0.1 beta`) so
   installed users get the bundled-catalog entry + the detector pattern (needed only for
   offline/detection; the live card already shows without it).
5. (optional) Push a news draft via `universal/claude_suggest.py`.

## To REMOVE (undo) before publishing
Nothing is live, so just revert the 3 code edits: the `CatalogGame(...)` in `games_catalog.py`,
the two `ratchet-rift-apart` lines in `game_detector.py`, and the `plannedSeeds` entry in
`website/src/data/games.ts`. (After publishing, also delete the Supabase row + bucket objects.)

## מסמכים קשורים
- באותה תיקייה: [[games/ratchet_rift_apart/FEASIBILITY|FEASIBILITY]], [[games/ratchet_rift_apart/PIPELINE|PIPELINE]], [[games/ratchet_rift_apart/RECON|RECON]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#ratchet_rift_apart|CLAUDE_INDEX_games]]
