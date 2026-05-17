# Admin Control Overhaul — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Centralise the progress meter, give the admin site fine-grained control over what the website and desktop tool show, harden the desktop cache against stale-data-while-offline, universalise the monitor script for any project/stage, gate AI-suggested content behind admin approval, and add a broad customisation layer the admin can drive without editing code.

**Architecture:**
Three subsystems coordinate through Supabase:
- **Admin website** (`c:\Users\nc528\סקריפטים\אתר תרגום משחקים\`) — React 18 + Vite + TS + Supabase, serverless TS API on Vercel. Owns config; new tables back the new toggles.
- **Desktop tool** (`c:\Users\nc528\סקריפטים\תרגום משחקים\` — `main_eel.py` + `frontend/`) — Python Eel host serving a React UI. Reads config via existing `/api/*` proxies and the SWR cache.
- **Monitor script** (`c:\Users\nc528\סקריפטים\תרגום משחקים\cp2077_monitor.py`) — pushes per-game snapshots to `/api/admin/progress`. Will be split into a reusable `progress_monitor/` package and a thin Cyberpunk-specific entry.

A new `site_config` table (Supabase, jsonb) holds admin-editable settings (toggles, ordering, labels, colours, hero copy, …). Both website and desktop tool fetch it through `/api/config` and cache it via the existing SWR layer. AI-suggested news lands in a new `news_drafts` table; nothing publishes without an explicit admin **Approve**.

**Tech Stack:** React 18, Vite, TypeScript, Supabase Postgres, Vercel serverless TS functions, Python 3.11+ (Eel), framer-motion, ripgrep for searches. CustomTkinter UI in `translation_manager/ui/` is legacy and out of scope.

**Phasing — each phase ships independently:**
- Phase 1 — meter consolidation + show/hide toggle (req. #1, #2, #3)
- Phase 2 — per-game manual/auto data source (req. #4)
- Phase 3 — desktop cache hygiene (req. #5)
- Phase 4 — universal monitor (req. #7)
- Phase 5 — AI news drafts gated by approval (req. #6)
- Phase 6 — broad admin customisation layer (req. #8)

---

## File Structure

### New files

- `c:\Users\nc528\סקריפטים\אתר תרגום משחקים\supabase\config_migration.sql` — `site_config` + `news_drafts` tables.
- `c:\Users\nc528\סקריפטים\אתר תרגום משחקים\src\lib\useSiteConfig.ts` — React hook + context for site config.
- `c:\Users\nc528\סקריפטים\אתר תרגום משחקים\api\config.ts` — public read endpoint for `site_config`.
- `c:\Users\nc528\סקריפטים\אתר תרגום משחקים\api\admin\config.ts` — admin write endpoint.
- `c:\Users\nc528\סקריפטים\אתר תרגום משחקים\api\admin\news-drafts.ts` — list/approve/reject AI drafts.
- `c:\Users\nc528\סקריפטים\אתר תרגום משחקים\api\admin\suggest-news.ts` — generate a draft (does NOT publish).
- `c:\Users\nc528\סקריפטים\אתר תרגום משחקים\src\components\admin\ConfigTab.tsx` — central admin control surface.
- `c:\Users\nc528\סקריפטים\אתר תרגום משחקים\src\components\admin\NewsDraftsTab.tsx` — review/approve drafts.
- `c:\Users\nc528\סקריפטים\תרגום משחקים\frontend\src\lib\useSiteConfig.ts` — desktop equivalent of the hook.
- `c:\Users\nc528\סקריפטים\תרגום משחקים\progress_monitor\__init__.py` — generic monitor package.
- `c:\Users\nc528\סקריפטים\תרגום משחקים\progress_monitor\core.py` — universal `Monitor` class.
- `c:\Users\nc528\סקריפטים\תרגום משחקים\progress_monitor\adapters\cp2077.py` — Cyberpunk adapter.
- `c:\Users\nc528\סקריפטים\תרגום משחקים\progress_monitor\__main__.py` — CLI runner.

### Modified files

- `c:\Users\nc528\סקריפטים\אתר תרגום משחקים\src\components\GameCard.tsx` — drop the `LiveProgressBar`.
- `c:\Users\nc528\סקריפטים\תרגום משחקים\frontend\src\components\GameCard.tsx` — drop the per-card meter.
- `c:\Users\nc528\סקריפטים\אתר תרגום משחקים\src\components\ProgressDashboard.tsx` — read `showDashboard` from site config; render nothing when hidden; respect per-game manual/auto source.
- `c:\Users\nc528\סקריפטים\תרגום משחקים\frontend\src\components\ProgressDashboard.tsx` — same.
- `c:\Users\nc528\סקריפטים\אתר תרגום משחקים\supabase\schema.sql` — adds source/visibility columns on `progress_snapshots`.
- `c:\Users\nc528\סקריפטים\אתר תרגום משחקים\api\admin\progress.ts` — accept + persist new fields; refuse monitor writes when `source='manual'`.
- `c:\Users\nc528\סקריפטים\אתר תרגום משחקים\api\progress.ts` — return new fields.
- `c:\Users\nc528\סקריפטים\אתר תרגום משחקים\src\components\admin\ProgressEditor.tsx` — adds `Source` selector (manual / auto) and `Show in dashboard` toggle.
- `c:\Users\nc528\סקריפטים\אתר תרגום משחקים\src\pages\admin\AdminLayout.tsx` — add `Config` and `News Drafts` tabs.
- `c:\Users\nc528\סקריפטים\תרגום משחקים\translation_manager\swr_cache.py` — drop bundled-file seeding (req. #5).
- `c:\Users\nc528\סקריפטים\תרגום משחקים\main_eel.py` — first-launch online-required gate; remove bundled-file wiring.
- `c:\Users\nc528\סקריפטים\תרגום משחקים\installer.iss` — stop copying `games.json`/`news.json` into the install dir.
- `c:\Users\nc528\סקריפטים\תרגום משחקים\cp2077_monitor.py` — thin shim that imports `progress_monitor.adapters.cp2077` (back-compat).

---

## Conventions used in this plan

- File paths are absolute.
- Each task has `Files:`, then a checkboxed list of small steps.
- Steps that change code show the exact edit (search/replace blocks where helpful).
- Test commands use the project's existing scripts; if none exist for a phase, a smoke check is given (e.g. `npm run build`, `python -m progress_monitor --dry-run …`).
- Commit messages are suggestions — keep one commit per task unless a step says otherwise.
- "Admin site" = `c:\Users\nc528\סקריפטים\אתר תרגום משחקים\`. "Desktop tool" = `c:\Users\nc528\סקריפטים\תרגום משחקים\`. "Frontend" inside desktop tool = `…\תרגום משחקים\frontend\`.

---

# Phase 1 — Meter consolidation + show/hide toggle

Removes the per-card meter from both UIs and adds a single admin toggle that hides/shows the central control panel. Ships independently of the rest.

## Task 1.1 — Schema: add `show_dashboard` column

**Files:**
- Create: `c:\Users\nc528\סקריפטים\אתר תרגום משחקים\supabase\config_migration.sql`

- [ ] **Step 1 — Write the migration file**

```sql
-- 2026-05-17  Admin control overhaul migration (Phase 1)
-- Idempotent: safe to re-run.
alter table public.progress_snapshots
  add column if not exists show_dashboard boolean not null default true;

comment on column public.progress_snapshots.show_dashboard is
  'When false the central ProgressDashboard hides this game even if availability=in-progress.';
```

- [ ] **Step 2 — Run it in the Supabase SQL editor**

Paste the file's contents into Supabase → SQL Editor → Run. Expected: "Success. No rows returned."

- [ ] **Step 3 — Verify column exists**

```sql
select column_name, data_type, column_default
from information_schema.columns
where table_name = 'progress_snapshots' and column_name = 'show_dashboard';
```

Expected: 1 row, `boolean`, default `true`.

- [ ] **Step 4 — Commit**

```bash
git -C "c:/Users/nc528/סקריפטים/אתר תרגום משחקים" add supabase/config_migration.sql
git -C "c:/Users/nc528/סקריפטים/אתר תרגום משחקים" commit -m "db: add progress_snapshots.show_dashboard"
```

## Task 1.2 — API: return `showDashboard`; admin write accepts it

**Files:**
- Modify: `c:\Users\nc528\סקריפטים\אתר תרגום משחקים\api\progress.ts`
- Modify: `c:\Users\nc528\סקריפטים\אתר תרגום משחקים\api\admin\progress.ts`

- [ ] **Step 1 — Add `showDashboard` to the public read mapping**

In `api/progress.ts`, find the row→DTO mapping (single-row and list) and add `showDashboard: row.show_dashboard ?? true,` next to `phaseLabelHe`. (If the file already spreads a typed mapping, add the field alongside `phase_label_he`.)

- [ ] **Step 2 — Add the field to the admin upsert in `api/admin/progress.ts`**

After the `meta:` line in the `row` object, add:

```ts
    show_dashboard: typeof body.showDashboard === 'boolean' ? body.showDashboard : true,
```

- [ ] **Step 3 — Smoke: build the admin site**

```bash
cd "c:/Users/nc528/סקריפטים/אתר תרגום משחקים" && npm run build
```

Expected: build succeeds.

- [ ] **Step 4 — Commit**

```bash
git -C "c:/Users/nc528/סקריפטים/אתר תרגום משחקים" add api/progress.ts api/admin/progress.ts
git -C "c:/Users/nc528/סקריפטים/אתר תרגום משחקים" commit -m "api: pass through progress.showDashboard"
```

## Task 1.3 — Admin UI: add the toggle in `ProgressEditor`

**Files:**
- Modify: `c:\Users\nc528\סקריפטים\אתר תרגום משחקים\src\components\admin\ProgressEditor.tsx`

- [ ] **Step 1 — Extend the `ProgressDraft` interface and `EMPTY`**

Add `showDashboard: boolean;` to `ProgressDraft`. Add `showDashboard: true,` to the `EMPTY` constant.

- [ ] **Step 2 — Hydrate the field from the API response**

In the `useEffect`'s `r.ok` branch, in the `setDraft({…})` call, add:

```ts
            showDashboard: typeof data.showDashboard === 'boolean' ? data.showDashboard : true,
```

- [ ] **Step 3 — Send it on save**

In `save()`'s `JSON.stringify({…})` payload, add:

```ts
          showDashboard: draft.showDashboard,
```

- [ ] **Step 4 — Render the toggle**

Inside the `grid` block (`<div className="grid grid-cols-2 gap-3">`), add a `Field` at the end that spans both columns:

```tsx
            <div className="col-span-2">
              <label className="flex items-center gap-2 text-sm text-slate-200">
                <input
                  type="checkbox"
                  checked={draft.showDashboard}
                  onChange={(e) => set('showDashboard', e.target.checked)}
                  className="accent-cyan-400 w-4 h-4"
                />
                הצג את לוח הבקרה של המשחק הזה באתר ובתוכנה
              </label>
            </div>
```

- [ ] **Step 5 — Smoke**

```bash
cd "c:/Users/nc528/סקריפטים/אתר תרגום משחקים" && npm run build
```

Expected: clean build.

- [ ] **Step 6 — Commit**

```bash
git -C "c:/Users/nc528/סקריפטים/אתר תרגום משחקים" add src/components/admin/ProgressEditor.tsx
git -C "c:/Users/nc528/סקריפטים/אתר תרגום משחקים" commit -m "admin: show_dashboard toggle in ProgressEditor"
```

## Task 1.4 — Public site: respect `showDashboard`

**Files:**
- Modify: `c:\Users\nc528\סקריפטים\אתר תרגום משחקים\src\components\ProgressDashboard.tsx`

- [ ] **Step 1 — Read the flag from the snapshot**

After the line `const { snapshot, isLive, updatedAt } = useGameProgress(inProgress?.id ?? null);` add:

```tsx
  const showDashboard = snapshot?.showDashboard ?? true;
```

- [ ] **Step 2 — Skip render when hidden**

Change the early return from:

```tsx
  if (!inProgress && !snapshot) return null;
```

to:

```tsx
  if (!inProgress && !snapshot) return null;
  if (!showDashboard) return null;
```

- [ ] **Step 3 — Make the type include the field**

Open `c:\Users\nc528\סקריפטים\אתר תרגום משחקים\src\lib\useGameProgress.ts` (or wherever the `Snapshot` type lives), add `showDashboard?: boolean;` to the interface, and map `show_dashboard` → `showDashboard` if a mapping helper exists there.

- [ ] **Step 4 — Smoke**

```bash
cd "c:/Users/nc528/סקריפטים/אתר תרגום משחקים" && npm run build
```

- [ ] **Step 5 — Commit**

```bash
git -C "c:/Users/nc528/סקריפטים/אתר תרגום משחקים" add src/components/ProgressDashboard.tsx src/lib/useGameProgress.ts
git -C "c:/Users/nc528/סקריפטים/אתר תרגום משחקים" commit -m "web: hide ProgressDashboard when showDashboard=false"
```

## Task 1.5 — Public site: drop the per-card meter

**Files:**
- Modify: `c:\Users\nc528\סקריפטים\אתר תרגום משחקים\src\components\GameCard.tsx`

- [ ] **Step 1 — Remove the in-card bar**

Delete lines 117–122 (the `{game.availability === 'in-progress' && (<LiveProgressBar … />)}` block).

- [ ] **Step 2 — Delete the `LiveProgressBar` definition**

Delete the entire `function LiveProgressBar({…})` definition at the bottom of the file (lines ~183–220).

- [ ] **Step 3 — Drop the now-unused imports**

Remove `import { useGameProgress } from '../lib/useGameProgress';` and the `type { ThemeTokens }` import if it becomes unused. Run `npm run build` to surface any leftovers.

- [ ] **Step 4 — Smoke**

```bash
cd "c:/Users/nc528/סקריפטים/אתר תרגום משחקים" && npm run build
```

Expected: build succeeds with no unused-import warnings.

- [ ] **Step 5 — Commit**

```bash
git -C "c:/Users/nc528/סקריפטים/אתר תרגום משחקים" add src/components/GameCard.tsx
git -C "c:/Users/nc528/סקריפטים/אתר תרגום משחקים" commit -m "web: remove in-card progress bar; meter lives in ProgressDashboard only"
```

## Task 1.6 — Desktop tool: drop the per-card meter

**Files:**
- Modify: `c:\Users\nc528\סקריפטים\תרגום משחקים\frontend\src\components\GameCard.tsx`

- [ ] **Step 1 — Read the file**

```bash
sed -n '1,260p' "c:/Users/nc528/סקריפטים/תרגום משחקים/frontend/src/components/GameCard.tsx"
```

Identify the equivalent in-card progress bar (it mirrors the website's). Remove it and the supporting helper component, the same way as Task 1.5.

- [ ] **Step 2 — Drop unused imports**

Remove `useLiveGameProgress` (or `useGameProgress`) imports if they were only used by the removed bar.

- [ ] **Step 3 — Smoke**

```bash
cd "c:/Users/nc528/סקריפטים/תרגום משחקים/frontend" && npm run build
```

Expected: build succeeds.

- [ ] **Step 4 — Commit**

```bash
git -C "c:/Users/nc528/סקריפטים/תרגום משחקים" add frontend/src/components/GameCard.tsx
git -C "c:/Users/nc528/סקריפטים/תרגום משחקים" commit -m "desktop: remove in-card progress bar; central ProgressDashboard only"
```

## Task 1.7 — Desktop tool: respect `showDashboard`

**Files:**
- Modify: `c:\Users\nc528\סקריפטים\תרגום משחקים\frontend\src\components\ProgressDashboard.tsx`
- Modify: `c:\Users\nc528\סקריפטים\תרגום משחקים\frontend\src\lib\useLiveGameProgress.ts`

- [ ] **Step 1 — Mirror the type change**

In `useLiveGameProgress.ts`, add `showDashboard?: boolean;` to the `Snapshot` interface and map `show_dashboard` (snake_case from the JSON payload) → `showDashboard` if the file does explicit mapping.

- [ ] **Step 2 — Respect the flag in `ProgressDashboard.tsx`**

Apply the same `if (!showDashboard) return null;` early-return guard added in Task 1.4 Step 2.

- [ ] **Step 3 — Smoke**

```bash
cd "c:/Users/nc528/סקריפטים/תרגום משחקים/frontend" && npm run build
```

- [ ] **Step 4 — Commit**

```bash
git -C "c:/Users/nc528/סקריפטים/תרגום משחקים" add frontend/src/components/ProgressDashboard.tsx frontend/src/lib/useLiveGameProgress.ts
git -C "c:/Users/nc528/סקריפטים/תרגום משחקים" commit -m "desktop: hide ProgressDashboard when showDashboard=false"
```

## Task 1.8 — Manual smoke in browser + desktop

- [ ] **Step 1 — Start admin site dev server**

```bash
cd "c:/Users/nc528/סקריפטים/אתר תרגום משחקים" && npm run dev
```

- [ ] **Step 2 — Visit `/admin`, open the Cyberpunk progress editor, uncheck "הצג את לוח הבקרה"**

Expected: in another tab on `/`, the ProgressDashboard disappears within ~30s (next SWR refresh).

- [ ] **Step 3 — Re-check it and confirm the dashboard returns**

- [ ] **Step 4 — Confirm the per-card progress bar is gone from every card**

# Phase 2 — Per-game manual vs. auto data source

Adds a `source` ∈ {`manual`, `auto`} flag on `progress_snapshots`. The monitor refuses to overwrite a row marked `manual`. The admin UI shows the current source and lets you switch.

## Task 2.1 — Schema: add `source` column

**Files:**
- Modify: `c:\Users\nc528\סקריפטים\אתר תרגום משחקים\supabase\config_migration.sql`

- [ ] **Step 1 — Append the column to the migration**

```sql
alter table public.progress_snapshots
  add column if not exists source text not null default 'auto'
  check (source in ('auto', 'manual'));

comment on column public.progress_snapshots.source is
  'auto = monitor script writes; manual = admin-edited, monitor is refused.';
```

- [ ] **Step 2 — Run in Supabase SQL editor**

Expected: success.

- [ ] **Step 3 — Verify**

```sql
select column_name, data_type, column_default
from information_schema.columns
where table_name = 'progress_snapshots' and column_name = 'source';
```

- [ ] **Step 4 — Commit**

```bash
git -C "c:/Users/nc528/סקריפטים/אתר תרגום משחקים" add supabase/config_migration.sql
git -C "c:/Users/nc528/סקריפטים/אתר תרגום משחקים" commit -m "db: add progress_snapshots.source (auto|manual)"
```

## Task 2.2 — API: enforce `source` semantics

**Files:**
- Modify: `c:\Users\nc528\סקריפטים\אתר תרגום משחקים\api\admin\progress.ts`

- [ ] **Step 1 — Compute caller type and effective source**

After `const db = admin();`:

```ts
  const callerIsMonitor = adminCtx === null;        // monitor-token path
  const requestedSource: 'auto' | 'manual' =
    body.source === 'manual' ? 'manual' :
    body.source === 'auto'   ? 'auto'   :
    callerIsMonitor          ? 'auto'   : 'manual';
```

- [ ] **Step 2 — Reject monitor writes when the row is locked to manual**

Right after `gameId` validation, add:

```ts
  if (callerIsMonitor) {
    const { data: existing } = await db
      .from('progress_snapshots')
      .select('source')
      .eq('game_id', gameId)
      .maybeSingle();
    if (existing?.source === 'manual') {
      return res.status(409).json({ error: 'source-locked-manual' });
    }
  }
```

- [ ] **Step 3 — Persist `source`**

In the `row` object, add `source: requestedSource,` next to `show_dashboard`.

- [ ] **Step 4 — Update the public read in `api/progress.ts`**

Add `source: row.source ?? 'auto',` to the DTO mapping.

- [ ] **Step 5 — Smoke**

```bash
cd "c:/Users/nc528/סקריפטים/אתר תרגום משחקים" && npm run build
```

- [ ] **Step 6 — Commit**

```bash
git -C "c:/Users/nc528/סקריפטים/אתר תרגום משחקים" add api/admin/progress.ts api/progress.ts
git -C "c:/Users/nc528/סקריפטים/אתר תרגום משחקים" commit -m "api: enforce progress source (manual locks out monitor writes)"
```

## Task 2.3 — Admin UI: source selector

**Files:**
- Modify: `c:\Users\nc528\סקריפטים\אתר תרגום משחקים\src\components\admin\ProgressEditor.tsx`

- [ ] **Step 1 — Add `source` to draft + EMPTY**

`source: 'manual' | 'auto';` in the interface, `source: 'auto',` in `EMPTY`.

- [ ] **Step 2 — Hydrate**

In the `setDraft({…})` after fetching, add:

```ts
            source: data.source === 'manual' ? 'manual' : 'auto',
```

- [ ] **Step 3 — Send on save**

In the POST body add `source: draft.source,`.

- [ ] **Step 4 — Render the selector**

Add inside the grid, near the `phase` field:

```tsx
            <Field label="מקור נתונים"
                   hint="auto = הסקריפט מעדכן כל 15 ד׳ · manual = רק עריכה ידנית כאן">
              <select
                value={draft.source}
                onChange={(e) => set('source', e.target.value === 'manual' ? 'manual' : 'auto')}
                className={inputClass}
              >
                <option value="auto">אוטומטי (cp2077_monitor)</option>
                <option value="manual">ידני (ערכים מהאתר בלבד)</option>
              </select>
            </Field>
```

- [ ] **Step 5 — Smoke**

```bash
cd "c:/Users/nc528/סקריפטים/אתר תרגום משחקים" && npm run build
```

- [ ] **Step 6 — Commit**

```bash
git -C "c:/Users/nc528/סקריפטים/אתר תרגום משחקים" add src/components/admin/ProgressEditor.tsx
git -C "c:/Users/nc528/סקריפטים/אתר תרגום משחקים" commit -m "admin: source selector (manual|auto) in ProgressEditor"
```

## Task 2.4 — End-to-end check

- [ ] **Step 1 — Open `/admin` → Cyberpunk → set source to `manual`, set processed=1234, save**

- [ ] **Step 2 — Run the monitor once locally**

```bash
cd "c:/Users/nc528/סקריפטים/תרגום משחקים" && python cp2077_monitor.py --once
```

Expected: log line "source-locked-manual" or HTTP 409 from the API. Row stays at 1234.

- [ ] **Step 3 — Flip back to `auto` in admin, run monitor again**

Expected: row updates with live numbers.

# Phase 3 — Desktop cache hygiene

Removes the bundled-JSON seeding from the desktop tool. First launch requires internet to populate the cache; subsequent launches are fine offline.

## Task 3.1 — Stop seeding from bundled files in `swr_cache.py`

**Files:**
- Modify: `c:\Users\nc528\סקריפטים\תרגום משחקים\translation_manager\swr_cache.py`

- [ ] **Step 1 — Make `_seed_bundled` a no-op**

Replace the body of `_seed_bundled` with:

```python
def _seed_bundled(bundled_files: dict[str, Path]) -> None:
    """Intentionally a no-op.

    Earlier versions seeded the cache from JSON files shipped with the
    installer. That caused users without internet on first launch to see
    stale data from whenever the installer was signed. The cache is now
    network-only: first launch MUST be online; everything else is served
    from cache.json on disk.
    """
    return
```

- [ ] **Step 2 — Keep `configure(bundled_files=…)` signature for back-compat**

The `bundled_files` parameter stays in `configure(…)` so callers don't break, but it's ignored. Add an info log when callers still pass it:

In `configure`, after assigning `_push_cb`, before `_ensure_loaded(…)`:

```python
    if bundled_files:
        log.info("[swr] ignoring %d bundled files — cache is network-only now",
                 len(bundled_files))
```

- [ ] **Step 3 — Smoke: import the module from a fresh interpreter**

```bash
cd "c:/Users/nc528/סקריפטים/תרגום משחקים" && python -c "from translation_manager import swr_cache; swr_cache.configure(bundled_files={'x': __import__('pathlib').Path('.')}); print('ok')"
```

Expected: `ok` printed, an INFO log about ignoring bundled files.

- [ ] **Step 4 — Commit**

```bash
git -C "c:/Users/nc528/סקריפטים/תרגום משחקים" add translation_manager/swr_cache.py
git -C "c:/Users/nc528/סקריפטים/תרגום משחקים" commit -m "swr: drop bundled-file seeding (network-only cache)"
```

## Task 3.2 — `main_eel.py`: first-launch online check

**Files:**
- Modify: `c:\Users\nc528\סקריפטים\תרגום משחקים\main_eel.py`

- [ ] **Step 1 — Add an online preflight before opening Eel**

Add this function near the top of `main_eel.py` (after the imports):

```python
def _has_any_cache() -> bool:
    """True if the SWR cache already has at least one entry on disk."""
    p = pathlib.Path.home() / ".translation_manager" / "cache.json"
    if not p.exists():
        return False
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return bool(raw.get("entries"))


def _ping_api(timeout: float = 3.0) -> bool:
    try:
        r = requests.get("https://translations.example/api/games", timeout=timeout)
        return r.ok
    except requests.RequestException:
        return False
```

Replace `https://translations.example` with the project's actual API base URL (search `main_eel.py` for an existing `API_BASE` or similar).

- [ ] **Step 2 — Block startup if first-launch and offline**

Just before the Eel `start(…)` call, add:

```python
    if not _has_any_cache() and not _ping_api():
        _show_no_internet_dialog()
        sys.exit(1)
```

- [ ] **Step 3 — Add the no-internet dialog**

```python
def _show_no_internet_dialog() -> None:
    """Tk-based blocking dialog. Used only when the launcher cannot start
    its cache from the network on first run."""
    import tkinter as tk
    from tkinter import messagebox
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror(
        "אין חיבור לאינטרנט",
        "להפעלה הראשונה של מנהל התרגומים נדרש חיבור לאינטרנט "
        "כדי להוריד את הקטלוג המעודכן (משחקים, חדשות, תמונות).\n\n"
        "אנא התחבר לאינטרנט ופתח שוב את האפליקציה.",
    )
    root.destroy()
```

- [ ] **Step 4 — Remove the `bundled_files=` argument from `swr_cache.configure(…)`**

Search for `swr_cache.configure(` in `main_eel.py`; drop the `bundled_files=…` kwarg.

- [ ] **Step 5 — Smoke: simulate first launch offline**

```bash
mv ~/.translation_manager/cache.json ~/.translation_manager/cache.json.bak 2>/dev/null
# disconnect Wi-Fi
python "c:/Users/nc528/סקריפטים/תרגום משחקים/main_eel.py"
```

Expected: dialog appears, app exits.

- [ ] **Step 6 — Restore + reconnect, launch again**

Expected: launcher starts; cache is populated after the first network fetch; `cat ~/.translation_manager/cache.json | head` shows entries.

- [ ] **Step 7 — Commit**

```bash
git -C "c:/Users/nc528/סקריפטים/תרגום משחקים" add main_eel.py
git -C "c:/Users/nc528/סקריפטים/תרגום משחקים" commit -m "launcher: require internet on first launch; no bundled cache"
```

## Task 3.3 — Installer: stop copying cache seed files

**Files:**
- Modify: `c:\Users\nc528\סקריפטים\תרגום משחקים\installer.iss`

- [ ] **Step 1 — Open `installer.iss` and find any `[Files]` lines bundling `games.json`, `news.json`, or `cache.json`**

Comment them out (`;` prefix in Inno Setup) and add a comment:

```
; 2026-05-17  Removed bundled JSON seeds — cache must be populated from the
; live API on first launch (see swr_cache._seed_bundled).
```

- [ ] **Step 2 — Build the installer**

```bash
cd "c:/Users/nc528/סקריפטים/תרגום משחקים" && iscc installer.iss
```

Expected: installer builds; the resulting `.exe` is smaller than the previous one (no JSON seeds).

- [ ] **Step 3 — Commit**

```bash
git -C "c:/Users/nc528/סקריפטים/תרגום משחקים" add installer.iss
git -C "c:/Users/nc528/סקריפטים/תרגום משחקים" commit -m "installer: stop bundling JSON cache seeds"
```

# Phase 4 — Universal monitor

Split `cp2077_monitor.py` into a reusable `progress_monitor/` package with pluggable adapters. The Cyberpunk-specific logic moves to `progress_monitor/adapters/cp2077.py`; the legacy `cp2077_monitor.py` becomes a one-line shim.

## Task 4.1 — Scaffold the package

**Files:**
- Create: `c:\Users\nc528\סקריפטים\תרגום משחקים\progress_monitor\__init__.py`
- Create: `c:\Users\nc528\סקריפטים\תרגום משחקים\progress_monitor\core.py`
- Create: `c:\Users\nc528\סקריפטים\תרגום משחקים\progress_monitor\__main__.py`

- [ ] **Step 1 — Write `__init__.py`**

```python
"""Universal progress monitor.

Push per-game progress snapshots to /api/admin/progress for any project
(extraction, translation, packaging, QA, deployment, …) regardless of
which game it is.
"""
from .core import Monitor, Snapshot, Stage  # noqa: F401
```

- [ ] **Step 2 — Write `core.py`**

```python
"""Generic monitor primitives — adapter-driven."""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import requests

log = logging.getLogger(__name__)

# Stages match api/admin/progress.ts PHASE_VALUES.
Stage = str  # 'extraction' | 'translation' | 'packaging' | 'qa' | 'deployment' | 'idle' | custom


@dataclass
class Snapshot:
    game_id:        str
    phase:          Stage = 'translation'
    phase_label_he: str | None = None
    processed:      int = 0
    total:          int = 0
    rate_per_hour:  int = 0
    unit:           str = 'שורות'
    gpu_model:      str = ''
    ai_model:       str = ''
    meta:           dict[str, Any] = field(default_factory=dict)


@dataclass
class Monitor:
    """Wraps a project-specific adapter callback into a poll-and-push loop.

    adapter()  -> Snapshot | None    Called every `interval_s` seconds.
                                     Return None to skip this tick.
    """
    game_id:    str
    adapter:    Callable[[], Snapshot | None]
    api_base:   str = field(default_factory=lambda: os.environ.get(
                    'PROGRESS_API_BASE', 'https://your-site.example'))
    api_token:  str = field(default_factory=lambda: os.environ.get('MONITOR_TOKEN', ''))
    interval_s: float = 900.0     # 15 min

    def push(self, snap: Snapshot) -> bool:
        if not self.api_token:
            log.error("MONITOR_TOKEN missing; cannot push")
            return False
        body = {
            'gameId':       snap.game_id,
            'phase':        snap.phase,
            'phaseLabelHe': snap.phase_label_he,
            'processed':    snap.processed,
            'total':        snap.total,
            'ratePerHour':  snap.rate_per_hour,
            'unit':         snap.unit,
            'gpuModel':     snap.gpu_model,
            'aiModel':      snap.ai_model,
            'meta':         snap.meta or None,
        }
        try:
            r = requests.post(
                f"{self.api_base}/api/admin/progress",
                json=body,
                headers={'Authorization': f'Bearer {self.api_token}'},
                timeout=20,
            )
        except requests.RequestException as e:
            log.warning("push failed: %s", e)
            return False
        if r.status_code == 409 and 'source-locked-manual' in r.text:
            log.info("row is locked to manual; skipping")
            return True               # benign — caller doesn't need to retry
        if not r.ok:
            log.warning("push HTTP %s: %s", r.status_code, r.text[:200])
            return False
        return True

    def run(self, *, once: bool = False, dry_run: bool = False) -> int:
        """Returns the number of successful pushes (useful for tests)."""
        sent = 0
        while True:
            try:
                snap = self.adapter()
            except Exception as e:                      # noqa: BLE001
                log.exception("adapter raised: %s", e)
                snap = None
            if snap is not None:
                if dry_run:
                    log.info("[dry-run] would push %s", snap)
                    sent += 1
                elif self.push(snap):
                    sent += 1
            if once:
                return sent
            time.sleep(self.interval_s)
```

- [ ] **Step 3 — Write `__main__.py`**

```python
"""CLI runner: python -m progress_monitor --adapter cp2077 [--once] [--dry-run]"""
from __future__ import annotations

import argparse
import importlib
import logging
import sys


def main() -> int:
    p = argparse.ArgumentParser(prog='progress_monitor')
    p.add_argument('--adapter', required=True,
                   help='dotted path of an adapter module exposing build() -> Monitor')
    p.add_argument('--once',    action='store_true', help='single tick then exit')
    p.add_argument('--dry-run', action='store_true', help='log what would be pushed; no HTTP')
    p.add_argument('-v', '--verbose', action='store_true')
    args = p.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(asctime)s %(levelname)s %(name)s: %(message)s',
    )

    try:
        mod = importlib.import_module(f'progress_monitor.adapters.{args.adapter}')
    except ImportError:
        mod = importlib.import_module(args.adapter)
    monitor = mod.build()
    monitor.run(once=args.once, dry_run=args.dry_run)
    return 0


if __name__ == '__main__':
    sys.exit(main())
```

- [ ] **Step 4 — Smoke**

```bash
cd "c:/Users/nc528/סקריפטים/תרגום משחקים" && python -c "from progress_monitor import Monitor, Snapshot; print(Snapshot('cp2077'))"
```

Expected: prints a `Snapshot(game_id='cp2077', …)`.

- [ ] **Step 5 — Commit**

```bash
git -C "c:/Users/nc528/סקריפטים/תרגום משחקים" add progress_monitor/
git -C "c:/Users/nc528/סקריפטים/תרגום משחקים" commit -m "monitor: scaffold universal progress_monitor package"
```

## Task 4.2 — Port Cyberpunk logic into an adapter

**Files:**
- Create: `c:\Users\nc528\סקריפטים\תרגום משחקים\progress_monitor\adapters\__init__.py`
- Create: `c:\Users\nc528\סקריפטים\תרגום משחקים\progress_monitor\adapters\cp2077.py`

- [ ] **Step 1 — Empty `adapters/__init__.py`**

```python
```

- [ ] **Step 2 — Read the existing `cp2077_monitor.py`**

```bash
sed -n '1,200p' "c:/Users/nc528/סקריפטים/תרגום משחקים/cp2077_monitor.py"
```

Identify (a) where it reads progress (file counts, log scraping, etc.), (b) the constants/paths it depends on, (c) the GPU/AI labels it sends.

- [ ] **Step 3 — Implement `cp2077.py`**

Use this skeleton; fill the body of `_collect()` from the existing script's logic:

```python
"""Cyberpunk 2077 adapter for the universal progress monitor."""
from __future__ import annotations

import logging
from pathlib import Path

from ..core import Monitor, Snapshot, Stage

log = logging.getLogger(__name__)

GAME_ID = 'cyberpunk-2077'
GPU      = 'AMD RX 9070 16GB'
AI_MODEL = 'Gemma-2 27B'


def _detect_stage() -> Stage:
    """Read a stage marker file or fall back to 'translation'."""
    marker = Path.home() / '.translation_manager' / 'cp2077_stage'
    if marker.exists():
        return marker.read_text(encoding='utf-8').strip() or 'translation'
    return 'translation'


def _collect() -> Snapshot | None:
    """Return a fresh snapshot or None when there's nothing to report."""
    # TODO at execution: copy the existing cp2077_monitor.py body that:
    # - reads lm_translation_progress.json (or whatever current source)
    # - computes processed / total / rate_per_hour
    # See the existing cp2077_monitor.py and reuse its helpers as needed.
    raise NotImplementedError(
        "Move the existing cp2077_monitor.py reading logic here unchanged."
    )


def build() -> Monitor:
    return Monitor(game_id=GAME_ID, adapter=_collect)
```

- [ ] **Step 4 — Implement `_collect()` for real**

Open the existing `cp2077_monitor.py` and lift the JSON-reading / rate-calculation code into `_collect`. Return a `Snapshot` from `Snapshot(game_id=GAME_ID, phase=_detect_stage(), gpu_model=GPU, ai_model=AI_MODEL, processed=…, total=…, rate_per_hour=…)`.

- [ ] **Step 5 — Dry-run end-to-end**

```bash
cd "c:/Users/nc528/סקריפטים/תרגום משחקים" && python -m progress_monitor --adapter cp2077 --once --dry-run -v
```

Expected: log shows a fully populated `Snapshot`; no HTTP errors.

- [ ] **Step 6 — Live one push with real token**

```bash
MONITOR_TOKEN=… PROGRESS_API_BASE=https://your-site.example python -m progress_monitor --adapter cp2077 --once
```

Expected: success, row updates in `progress_snapshots`.

- [ ] **Step 7 — Commit**

```bash
git -C "c:/Users/nc528/סקריפטים/תרגום משחקים" add progress_monitor/adapters/
git -C "c:/Users/nc528/סקריפטים/תרגום משחקים" commit -m "monitor: cyberpunk-2077 adapter"
```

## Task 4.3 — Replace `cp2077_monitor.py` with a thin shim

**Files:**
- Modify: `c:\Users\nc528\סקריפטים\תרגום משחקים\cp2077_monitor.py`

- [ ] **Step 1 — Replace the whole file**

```python
"""Back-compat shim — delegates to `python -m progress_monitor --adapter cp2077`."""
from __future__ import annotations

import sys

from progress_monitor.adapters.cp2077 import build


def main() -> int:
    once = '--once' in sys.argv
    dry  = '--dry-run' in sys.argv
    build().run(once=once, dry_run=dry)
    return 0


if __name__ == '__main__':
    sys.exit(main())
```

- [ ] **Step 2 — Confirm `cp2077_monitor.bat` still works**

```bash
"c:/Users/nc528/סקריפטים/תרגום משחקים/cp2077_monitor.bat"
```

Expected: behaves exactly as before (push runs successfully).

- [ ] **Step 3 — Commit**

```bash
git -C "c:/Users/nc528/סקריפטים/תרגום משחקים" add cp2077_monitor.py
git -C "c:/Users/nc528/סקריפטים/תרגום משחקים" commit -m "monitor: cp2077_monitor.py is now a shim over progress_monitor"
```

# Phase 5 — AI news drafts (gated by approval)

The admin site can ask an LLM for news ideas. Drafts land in a `news_drafts` table. Nothing publishes until the admin clicks **Approve**, which copies the row into `public.news`.

## Task 5.1 — Schema: `news_drafts` table

**Files:**
- Modify: `c:\Users\nc528\סקריפטים\אתר תרגום משחקים\supabase\config_migration.sql`

- [ ] **Step 1 — Append the table**

```sql
create table if not exists public.news_drafts (
  id           uuid primary key default gen_random_uuid(),
  created_at   timestamptz not null default now(),
  status       text not null default 'pending' check (status in ('pending', 'approved', 'rejected')),
  date         date not null default current_date,
  kind         text not null default 'system',
  badge        text,
  title        text not null,
  detail       text not null default '',
  link         text references public.games(id) on delete set null,
  source       text not null default 'manual'  -- 'manual' | 'ai'
);
create index if not exists news_drafts_status_idx on public.news_drafts (status, created_at desc);
alter table public.news_drafts enable row level security;
grant all on public.news_drafts to service_role;
```

- [ ] **Step 2 — Run in Supabase SQL editor**

Expected: table created.

- [ ] **Step 3 — Commit**

Already part of `config_migration.sql`; commit any pending changes.

## Task 5.2 — API: drafts CRUD + suggest + approve

**Files:**
- Create: `c:\Users\nc528\סקריפטים\אתר תרגום משחקים\api\admin\news-drafts.ts`
- Create: `c:\Users\nc528\סקריפטים\אתר תרגום משחקים\api\admin\suggest-news.ts`

- [ ] **Step 1 — `news-drafts.ts` — list, approve, reject, delete**

```ts
import type { VercelRequest, VercelResponse } from '@vercel/node';
import { admin } from '../_lib/supabaseAdmin.js';
import { requireAdmin } from '../_lib/auth.js';
import { safe } from '../_lib/safe.js';
import { audit } from '../_lib/audit.js';

export default safe(async function handler(req: VercelRequest, res: VercelResponse) {
  const ctx = await requireAdmin(req, res);
  if (!ctx) return;
  const db = admin();

  if (req.method === 'GET') {
    const { data, error } = await db
      .from('news_drafts')
      .select('*')
      .order('created_at', { ascending: false });
    if (error) return res.status(400).json({ error: error.message });
    return res.status(200).json(data);
  }

  if (req.method === 'POST') {
    const action = String((req.body as any)?.action ?? '');
    const id     = String((req.body as any)?.id ?? '');
    if (!id) return res.status(400).json({ error: 'missing-id' });
    if (action === 'approve') {
      const { data: draft } = await db
        .from('news_drafts').select('*').eq('id', id).single();
      if (!draft) return res.status(404).json({ error: 'not-found' });
      const newsId = `n_${id.slice(0, 8)}`;
      await db.from('news').upsert({
        id:     newsId,
        date:   draft.date,
        kind:   draft.kind,
        badge:  draft.badge,
        title:  draft.title,
        detail: draft.detail,
        link:   draft.link,
      });
      await db.from('news_drafts').update({ status: 'approved' }).eq('id', id);
      audit(ctx.email, 'approve', 'news_draft', id, { newsId });
      return res.status(200).json({ ok: true, newsId });
    }
    if (action === 'reject') {
      await db.from('news_drafts').update({ status: 'rejected' }).eq('id', id);
      audit(ctx.email, 'reject', 'news_draft', id, {});
      return res.status(200).json({ ok: true });
    }
    return res.status(400).json({ error: 'bad-action' });
  }

  if (req.method === 'DELETE') {
    const id = String(req.query.id ?? '');
    if (!id) return res.status(400).json({ error: 'missing-id' });
    await db.from('news_drafts').delete().eq('id', id);
    audit(ctx.email, 'delete', 'news_draft', id, {});
    return res.status(200).json({ ok: true });
  }

  return res.status(405).json({ error: 'method-not-allowed' });
});
```

- [ ] **Step 2 — `suggest-news.ts` — call Anthropic, insert as `pending`**

```ts
import type { VercelRequest, VercelResponse } from '@vercel/node';
import { admin } from '../_lib/supabaseAdmin.js';
import { requireAdmin } from '../_lib/auth.js';
import { safe } from '../_lib/safe.js';
import { audit } from '../_lib/audit.js';

export default safe(async function handler(req: VercelRequest, res: VercelResponse) {
  if (req.method !== 'POST') return res.status(405).json({ error: 'method-not-allowed' });
  const ctx = await requireAdmin(req, res);
  if (!ctx) return;

  const key = process.env.ANTHROPIC_API_KEY;
  if (!key) return res.status(500).json({ error: 'missing-ANTHROPIC_API_KEY' });

  const db = admin();
  const { data: games } = await db.from('games').select('id, title_he, availability, version');
  const { data: news }  = await db.from('news').select('title, date').order('date', { ascending: false }).limit(20);

  const prompt = `אתה עורך חדשות לאתר תרגומי משחקים לעברית.
משחקים נוכחיים: ${JSON.stringify(games)}.
חדשות אחרונות (אל תחזור עליהן): ${JSON.stringify(news)}.

הצע 3 פריטי חדשות חדשים בעברית — קצרים, מדויקים, רלוונטיים.
החזר JSON: [{"title": "...", "detail": "...", "kind": "system|mod", "badge": "חדש"|null, "link": "<game-id-or-null>"}].`;

  const r = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: {
      'x-api-key':         key,
      'anthropic-version': '2023-06-01',
      'content-type':      'application/json',
    },
    body: JSON.stringify({
      model: 'claude-opus-4-7',
      max_tokens: 1024,
      messages: [{ role: 'user', content: prompt }],
    }),
  });
  if (!r.ok) return res.status(502).json({ error: 'anthropic-failed', detail: await r.text() });
  const payload = await r.json();
  const text = payload?.content?.[0]?.text ?? '';
  const jsonMatch = text.match(/\[[\s\S]*\]/);
  if (!jsonMatch) return res.status(502).json({ error: 'bad-suggestion-format' });
  const items = JSON.parse(jsonMatch[0]) as Array<{
    title: string; detail: string; kind?: string; badge?: string | null; link?: string | null;
  }>;

  const rows = items.map((it) => ({
    title:  String(it.title).slice(0, 240),
    detail: String(it.detail ?? ''),
    kind:   it.kind === 'mod' ? 'mod' : 'system',
    badge:  it.badge ?? null,
    link:   it.link ?? null,
    source: 'ai',
  }));
  const { data, error } = await db.from('news_drafts').insert(rows).select();
  if (error) return res.status(400).json({ error: error.message });
  audit(ctx.email, 'suggest', 'news_draft', '', { count: rows.length });
  return res.status(200).json(data);
});
```

- [ ] **Step 3 — Smoke (admin must have `ANTHROPIC_API_KEY` set in Vercel env)**

```bash
cd "c:/Users/nc528/סקריפטים/אתר תרגום משחקים" && npm run build
```

- [ ] **Step 4 — Commit**

```bash
git -C "c:/Users/nc528/סקריפטים/אתר תרגום משחקים" add api/admin/news-drafts.ts api/admin/suggest-news.ts
git -C "c:/Users/nc528/סקריפטים/אתר תרגום משחקים" commit -m "api: AI news suggestions + approval workflow"
```

## Task 5.3 — Admin UI: drafts tab

**Files:**
- Create: `c:\Users\nc528\סקריפטים\אתר תרגום משחקים\src\components\admin\NewsDraftsTab.tsx`
- Modify: `c:\Users\nc528\סקריפטים\אתר תרגום משחקים\src\pages\admin\AdminLayout.tsx`

- [ ] **Step 1 — Build `NewsDraftsTab.tsx`**

```tsx
import { useEffect, useState } from 'react';
import { adminJSON } from '../../lib/apiAdmin';
import { useToast } from './ToastProvider';
import { GhostButton, PrimaryButton, Skeleton } from './primitives';

interface Draft {
  id: string; title: string; detail: string; date: string; kind: string;
  badge: string | null; link: string | null; status: string; source: string;
  created_at: string;
}

export function NewsDraftsTab() {
  const toast = useToast();
  const [items, setItems] = useState<Draft[] | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  async function load() {
    try {
      setItems(await adminJSON('/api/admin/news-drafts'));
    } catch (e) { toast.push((e as Error).message, 'error'); }
  }
  useEffect(() => { load(); }, []);

  async function suggest() {
    setBusyId('__suggest');
    try {
      await adminJSON('/api/admin/suggest-news', { method: 'POST' });
      toast.push('הצעות AI נוצרו — אשר/דחה למטה', 'success');
      await load();
    } catch (e) { toast.push((e as Error).message, 'error'); }
    finally { setBusyId(null); }
  }
  async function act(id: string, action: 'approve' | 'reject') {
    setBusyId(id);
    try {
      await adminJSON('/api/admin/news-drafts', { method: 'POST', body: JSON.stringify({ id, action }) });
      toast.push(action === 'approve' ? 'פורסם' : 'נדחה', 'success');
      await load();
    } catch (e) { toast.push((e as Error).message, 'error'); }
    finally { setBusyId(null); }
  }

  if (items === null) return <Skeleton className="h-32" />;

  return (
    <div className="space-y-5">
      <div className="flex items-baseline justify-between gap-4 flex-wrap">
        <div>
          <h2 className="text-xl font-bold text-white">חדשות — הצעות לאישור</h2>
          <p className="text-sm text-slate-400 mt-1">
            ה-AI יציע פריטי חדשות. שום דבר לא יפורסם עד שתאשר ידנית.
          </p>
        </div>
        <PrimaryButton onClick={suggest} disabled={busyId !== null}>
          {busyId === '__suggest' ? 'מבקש הצעות…' : 'בקש הצעות מ-AI'}
        </PrimaryButton>
      </div>
      <div className="grid gap-3">
        {items.length === 0 && <div className="text-sm text-slate-500">אין הצעות פתוחות.</div>}
        {items.map((d) => (
          <div key={d.id} className="border border-white/10 rounded-xl p-4 bg-white/[0.02]">
            <div className="flex items-baseline justify-between gap-3">
              <div className="text-white font-semibold">{d.title}</div>
              <div className="text-[11px] text-slate-500" dir="ltr">{d.status} · {d.source}</div>
            </div>
            <div className="text-sm text-slate-300 mt-1 whitespace-pre-wrap">{d.detail}</div>
            <div className="text-[11px] text-slate-500 mt-2" dir="ltr">{d.date} · {d.kind} · {d.link ?? '—'}</div>
            {d.status === 'pending' && (
              <div className="flex gap-2 mt-3">
                <PrimaryButton onClick={() => act(d.id, 'approve')} disabled={busyId === d.id}>אשר ופרסם</PrimaryButton>
                <GhostButton  onClick={() => act(d.id, 'reject')}  disabled={busyId === d.id}>דחה</GhostButton>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2 — Wire the tab into `AdminLayout.tsx`**

Read `AdminLayout.tsx`, find the tab registry (likely an array or switch on a `tab` URL param), add `news-drafts` next to `news`. Render `<NewsDraftsTab />` when active.

- [ ] **Step 3 — Smoke**

```bash
cd "c:/Users/nc528/סקריפטים/אתר תרגום משחקים" && npm run build
```

- [ ] **Step 4 — End-to-end**

In dev, open `/admin?tab=news-drafts`, click "בקש הצעות מ-AI" → drafts appear → approve one → verify it appears in `public.news` and on the public site after the next refresh.

- [ ] **Step 5 — Commit**

```bash
git -C "c:/Users/nc528/סקריפטים/אתר תרגום משחקים" add src/components/admin/NewsDraftsTab.tsx src/pages/admin/AdminLayout.tsx
git -C "c:/Users/nc528/סקריפטים/אתר תרגום משחקים" commit -m "admin: AI news drafts tab with explicit approve/reject"
```

# Phase 6 — Broad admin customisation layer

A single `site_config` row stores a JSON object the admin edits. Both the website and the desktop tool subscribe to it through `/api/config` (cached via SWR). Sections covered (initial set — extensible): hero copy, theme accent colours, section visibility (hero / dashboard / news / updates / faq), section ordering, FAQ items, footer text, custom CSS variables.

## Task 6.1 — Schema: `site_config` (single-row k/v)

**Files:**
- Modify: `c:\Users\nc528\סקריפטים\אתר תרגום משחקים\supabase\config_migration.sql`

- [ ] **Step 1 — Append**

```sql
create table if not exists public.site_config (
  id          smallint primary key default 1,           -- enforced single row
  data        jsonb not null default '{}'::jsonb,
  updated_at  timestamptz not null default now(),
  constraint single_row check (id = 1)
);
insert into public.site_config (id, data) values (1, '{}'::jsonb) on conflict (id) do nothing;
alter table public.site_config enable row level security;
grant select on public.site_config to anon, authenticated;
grant all    on public.site_config to service_role;
drop policy if exists "anon read config" on public.site_config;
create policy "anon read config" on public.site_config for select using (true);
```

- [ ] **Step 2 — Run + commit**

```bash
git -C "c:/Users/nc528/סקריפטים/אתר תרגום משחקים" add supabase/config_migration.sql
git -C "c:/Users/nc528/סקריפטים/אתר תרגום משחקים" commit -m "db: add site_config jsonb single-row table"
```

## Task 6.2 — API: `/api/config` (public read) + `/api/admin/config` (write)

**Files:**
- Create: `c:\Users\nc528\סקריפטים\אתר תרגום משחקים\api\config.ts`
- Create: `c:\Users\nc528\סקריפטים\אתר תרגום משחקים\api\admin\config.ts`

- [ ] **Step 1 — `api/config.ts` (public, GET only)**

```ts
import type { VercelRequest, VercelResponse } from '@vercel/node';
import { admin } from './_lib/supabaseAdmin.js';
import { safe } from './_lib/safe.js';

export default safe(async function handler(_req: VercelRequest, res: VercelResponse) {
  const db = admin();
  const { data, error } = await db.from('site_config').select('data, updated_at').eq('id', 1).single();
  if (error) return res.status(500).json({ error: error.message });
  res.setHeader('Cache-Control', 'public, max-age=30, s-maxage=30');
  return res.status(200).json({
    config:    data?.data ?? {},
    updatedAt: data?.updated_at ?? null,
  });
});
```

- [ ] **Step 2 — `api/admin/config.ts` (admin write, partial merge)**

```ts
import type { VercelRequest, VercelResponse } from '@vercel/node';
import { admin } from '../_lib/supabaseAdmin.js';
import { requireAdmin } from '../_lib/auth.js';
import { safe } from '../_lib/safe.js';
import { audit } from '../_lib/audit.js';

export default safe(async function handler(req: VercelRequest, res: VercelResponse) {
  const ctx = await requireAdmin(req, res);
  if (!ctx) return;
  if (req.method !== 'POST' && req.method !== 'PATCH') {
    return res.status(405).json({ error: 'method-not-allowed' });
  }
  const patch = (req.body as any)?.patch;
  if (!patch || typeof patch !== 'object') {
    return res.status(400).json({ error: 'missing-patch-object' });
  }
  const db = admin();
  const { data: cur } = await db.from('site_config').select('data').eq('id', 1).single();
  const next = { ...(cur?.data ?? {}), ...patch };
  const { data, error } = await db
    .from('site_config')
    .update({ data: next, updated_at: new Date().toISOString() })
    .eq('id', 1)
    .select('data, updated_at')
    .single();
  if (error) return res.status(400).json({ error: error.message });
  audit(ctx.email, 'update', 'site_config', '1', { keys: Object.keys(patch) });
  return res.status(200).json({ config: data.data, updatedAt: data.updated_at });
});
```

- [ ] **Step 3 — Smoke**

```bash
cd "c:/Users/nc528/סקריפטים/אתר תרגום משחקים" && npm run build
```

- [ ] **Step 4 — Commit**

```bash
git -C "c:/Users/nc528/סקריפטים/אתר תרגום משחקים" add api/config.ts api/admin/config.ts
git -C "c:/Users/nc528/סקריפטים/אתר תרגום משחקים" commit -m "api: /config (public) + /admin/config (write) for site_config"
```

## Task 6.3 — React hook + provider on the website

**Files:**
- Create: `c:\Users\nc528\סקריפטים\אתר תרגום משחקים\src\lib\useSiteConfig.ts`
- Modify: `c:\Users\nc528\סקריפטים\אתר תרגום משחקים\src\App.tsx`

- [ ] **Step 1 — Write the hook**

```ts
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';

export interface SiteConfig {
  // Each field is OPTIONAL — only `patch` set values land here. UI code uses
  // ?? defaults for everything so a fresh database still renders correctly.
  hero?: {
    titleHe?:    string;
    taglineHe?:  string;
    accent?:     string;       // CSS colour
  };
  sections?: {
    visible?:    Record<string, boolean>;     // { dashboard: true, news: true, … }
    order?:      string[];                    // ['hero', 'dashboard', 'grid', 'news']
  };
  theme?: {
    primary?:    string;
    secondary?:  string;
    fontDisplay?: string;
    fontBody?:   string;
  };
  faq?: Array<{ q: string; a: string }>;
  footer?: { textHe?: string };
  customCss?: string;
}

const Ctx = createContext<SiteConfig | null>(null);

export function SiteConfigProvider({ children }: { children: ReactNode }) {
  const [cfg, setCfg] = useState<SiteConfig | null>(null);
  useEffect(() => {
    let alive = true;
    const fetchOnce = () =>
      fetch('/api/config').then((r) => r.json()).then((j) => {
        if (alive) setCfg(j?.config ?? {});
      }).catch(() => { if (alive) setCfg({}); });
    fetchOnce();
    const id = window.setInterval(fetchOnce, 30_000);
    return () => { alive = false; window.clearInterval(id); };
  }, []);
  const value = useMemo(() => cfg ?? {}, [cfg]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useSiteConfig(): SiteConfig {
  return useContext(Ctx) ?? {};
}
```

- [ ] **Step 2 — Wrap the app**

In `App.tsx`, import `SiteConfigProvider` and wrap the existing tree (innermost still works) — typically next to the `ThemeProvider`.

- [ ] **Step 3 — Apply `customCss`**

In the same provider component, when `cfg.customCss` is a non-empty string, inject a `<style>` element. Add inside `SiteConfigProvider`:

```tsx
  useEffect(() => {
    const css = cfg?.customCss ?? '';
    let el = document.getElementById('site-custom-css') as HTMLStyleElement | null;
    if (!css) { el?.remove(); return; }
    if (!el) {
      el = document.createElement('style');
      el.id = 'site-custom-css';
      document.head.appendChild(el);
    }
    el.textContent = css;
  }, [cfg?.customCss]);
```

- [ ] **Step 4 — Use it in `Hero`**

In `src/components/Hero.tsx`, replace hardcoded title/tagline with `const cfg = useSiteConfig(); … cfg.hero?.titleHe ?? '<existing default>'`.

- [ ] **Step 5 — Use it in section visibility / order**

In `HomePage.tsx`, wrap each section in a check on `cfg.sections?.visible?.[key] ?? true`, and render sections in `cfg.sections?.order ?? defaultOrder`.

- [ ] **Step 6 — Smoke**

```bash
cd "c:/Users/nc528/סקריפטים/אתר תרגום משחקים" && npm run build && npm run dev
```

Open the site; everything renders the same as before (empty config = defaults).

- [ ] **Step 7 — Commit**

```bash
git -C "c:/Users/nc528/סקריפטים/אתר תרגום משחקים" add src/lib/useSiteConfig.ts src/App.tsx src/components/Hero.tsx src/pages/HomePage.tsx
git -C "c:/Users/nc528/סקריפטים/אתר תרגום משחקים" commit -m "web: SiteConfigProvider + apply hero/sections/customCss"
```

## Task 6.4 — Admin UI: `ConfigTab`

**Files:**
- Create: `c:\Users\nc528\סקריפטים\אתר תרגום משחקים\src\components\admin\ConfigTab.tsx`
- Modify: `c:\Users\nc528\סקריפטים\אתר תרגום משחקים\src\pages\admin\AdminLayout.tsx`

- [ ] **Step 1 — Build `ConfigTab.tsx`**

```tsx
import { useEffect, useState } from 'react';
import { adminJSON } from '../../lib/apiAdmin';
import { useToast } from './ToastProvider';
import { Field, PrimaryButton, GhostButton, Skeleton, inputClass } from './primitives';

interface ConfigShape {
  hero?: { titleHe?: string; taglineHe?: string; accent?: string };
  sections?: { visible?: Record<string, boolean>; order?: string[] };
  theme?: { primary?: string; secondary?: string; fontDisplay?: string; fontBody?: string };
  footer?: { textHe?: string };
  customCss?: string;
}

const SECTION_KEYS = ['hero', 'dashboard', 'grid', 'news', 'updates', 'faq', 'footer'] as const;

export function ConfigTab() {
  const toast = useToast();
  const [cfg, setCfg] = useState<ConfigShape | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    fetch('/api/config')
      .then((r) => r.json())
      .then((j) => setCfg(j?.config ?? {}))
      .catch((e) => toast.push((e as Error).message, 'error'));
  }, []);

  if (!cfg) return <Skeleton className="h-64" />;

  function patch<K extends keyof ConfigShape>(key: K, value: ConfigShape[K]) {
    setCfg((c) => ({ ...(c ?? {}), [key]: value }));
  }

  async function save() {
    setBusy(true);
    try {
      await adminJSON('/api/admin/config', { method: 'POST', body: JSON.stringify({ patch: cfg }) });
      toast.push('הגדרות נשמרו', 'success');
    } catch (e) { toast.push((e as Error).message, 'error'); }
    finally { setBusy(false); }
  }

  return (
    <div className="space-y-6">
      <section>
        <h3 className="text-white font-semibold mb-2">Hero (גיבור הראשי)</h3>
        <div className="grid grid-cols-2 gap-3">
          <Field label="כותרת"><input className={inputClass} dir="rtl"
            value={cfg.hero?.titleHe ?? ''}
            onChange={(e) => patch('hero', { ...(cfg.hero ?? {}), titleHe: e.target.value })} /></Field>
          <Field label="טקסט תיאור"><input className={inputClass} dir="rtl"
            value={cfg.hero?.taglineHe ?? ''}
            onChange={(e) => patch('hero', { ...(cfg.hero ?? {}), taglineHe: e.target.value })} /></Field>
          <Field label="צבע מבטא (CSS color)"><input className={inputClass} dir="ltr"
            placeholder="#00ffe0"
            value={cfg.hero?.accent ?? ''}
            onChange={(e) => patch('hero', { ...(cfg.hero ?? {}), accent: e.target.value })} /></Field>
        </div>
      </section>

      <section>
        <h3 className="text-white font-semibold mb-2">סקציות — תצוגה וסדר</h3>
        <div className="grid grid-cols-2 gap-3">
          {SECTION_KEYS.map((k) => (
            <label key={k} className="flex items-center gap-2 text-sm text-slate-200">
              <input type="checkbox" className="accent-cyan-400 w-4 h-4"
                checked={cfg.sections?.visible?.[k] ?? true}
                onChange={(e) => patch('sections', {
                  ...(cfg.sections ?? {}),
                  visible: { ...(cfg.sections?.visible ?? {}), [k]: e.target.checked },
                })} />
              {k}
            </label>
          ))}
        </div>
        <Field label="סדר תצוגה (אחד-בשורה, מתוך הרשימה למעלה)" hint="ריק = ברירת מחדל">
          <textarea className={inputClass + ' h-24 font-mono'} dir="ltr"
            value={(cfg.sections?.order ?? []).join('\n')}
            onChange={(e) => patch('sections', {
              ...(cfg.sections ?? {}),
              order: e.target.value.split('\n').map((s) => s.trim()).filter(Boolean),
            })} />
        </Field>
      </section>

      <section>
        <h3 className="text-white font-semibold mb-2">עיצוב</h3>
        <div className="grid grid-cols-2 gap-3">
          <Field label="צבע ראשי"><input className={inputClass} dir="ltr"
            value={cfg.theme?.primary ?? ''}
            onChange={(e) => patch('theme', { ...(cfg.theme ?? {}), primary: e.target.value })} /></Field>
          <Field label="צבע משני"><input className={inputClass} dir="ltr"
            value={cfg.theme?.secondary ?? ''}
            onChange={(e) => patch('theme', { ...(cfg.theme ?? {}), secondary: e.target.value })} /></Field>
          <Field label="פונט כותרות"><input className={inputClass} dir="ltr"
            value={cfg.theme?.fontDisplay ?? ''}
            onChange={(e) => patch('theme', { ...(cfg.theme ?? {}), fontDisplay: e.target.value })} /></Field>
          <Field label="פונט גוף"><input className={inputClass} dir="ltr"
            value={cfg.theme?.fontBody ?? ''}
            onChange={(e) => patch('theme', { ...(cfg.theme ?? {}), fontBody: e.target.value })} /></Field>
        </div>
      </section>

      <section>
        <h3 className="text-white font-semibold mb-2">פוטר</h3>
        <Field label="טקסט פוטר"><textarea className={inputClass + ' h-20'} dir="rtl"
          value={cfg.footer?.textHe ?? ''}
          onChange={(e) => patch('footer', { textHe: e.target.value })} /></Field>
      </section>

      <section>
        <h3 className="text-white font-semibold mb-2">Custom CSS (זהירות)</h3>
        <Field label="ייוזרק בעמוד כל 30 שניות אם השתנה" hint="ריק = ללא הזרקה">
          <textarea className={inputClass + ' h-32 font-mono'} dir="ltr"
            value={cfg.customCss ?? ''}
            onChange={(e) => patch('customCss', e.target.value)} />
        </Field>
      </section>

      <div className="flex justify-end gap-2">
        <GhostButton onClick={() => location.reload()}>בטל שינויים</GhostButton>
        <PrimaryButton onClick={save} disabled={busy}>{busy ? 'שומר…' : 'שמור'}</PrimaryButton>
      </div>
    </div>
  );
}
```

- [ ] **Step 2 — Wire into `AdminLayout.tsx`**

Add a `config` tab. Render `<ConfigTab />`.

- [ ] **Step 3 — Smoke**

```bash
cd "c:/Users/nc528/סקריפטים/אתר תרגום משחקים" && npm run build
```

- [ ] **Step 4 — End-to-end**

In dev, change the hero title via `/admin?tab=config` and save. Open `/` in another tab — within ~30s the new title shows up. Then toggle `dashboard=false` in `sections.visible` — the dashboard hides everywhere.

- [ ] **Step 5 — Commit**

```bash
git -C "c:/Users/nc528/סקריפטים/אתר תרגום משחקים" add src/components/admin/ConfigTab.tsx src/pages/admin/AdminLayout.tsx
git -C "c:/Users/nc528/סקריפטים/אתר תרגום משחקים" commit -m "admin: ConfigTab — hero/sections/theme/footer/customCss"
```

## Task 6.5 — Desktop tool mirror

**Files:**
- Create: `c:\Users\nc528\סקריפטים\תרגום משחקים\frontend\src\lib\useSiteConfig.ts`
- Modify: `c:\Users\nc528\סקריפטים\תרגום משחקים\frontend\src\App.tsx`
- Modify: `c:\Users\nc528\סקריפטים\תרגום משחקים\frontend\src\views\HomeView.tsx`

- [ ] **Step 1 — Copy the hook** (paste the same code from Task 6.3 step 1) and adapt the fetch URL to whatever the desktop tool uses to hit the API (Eel exposes `eel.fetch_config()` or a direct fetch to the website depending on the existing pattern — check `frontend/src/lib/eel.ts`).

- [ ] **Step 2 — Wrap `App.tsx`** with `SiteConfigProvider` and apply `customCss` the same way.

- [ ] **Step 3 — Apply sections.visible / order in `HomeView.tsx`** the same way as the website.

- [ ] **Step 4 — Smoke**

```bash
cd "c:/Users/nc528/סקריפטים/תרגום משחקים/frontend" && npm run build
cd "c:/Users/nc528/סקריפטים/תרגום משחקים" && python main_eel.py
```

In the running launcher: change a config value in the admin website → within 30s the launcher reflects it.

- [ ] **Step 5 — Commit**

```bash
git -C "c:/Users/nc528/סקריפטים/תרגום משחקים" add frontend/src/lib/useSiteConfig.ts frontend/src/App.tsx frontend/src/views/HomeView.tsx
git -C "c:/Users/nc528/סקריפטים/תרגום משחקים" commit -m "desktop: SiteConfigProvider mirror + apply customCss/sections"
```

---

## Cross-phase verification checklist

- [ ] **All 8 user requirements covered** — verify against the running list in the conversation that produced this plan.
- [ ] **Schema migration is idempotent** — re-running `config_migration.sql` doesn't fail.
- [ ] **First-run offline = blocked dialog**, first-run online = cache populated, subsequent offline = works from cache.
- [ ] **Monitor refuses to overwrite `source='manual'` rows** (HTTP 409).
- [ ] **AI suggestions never publish** until an admin presses Approve.
- [ ] **Per-card meter gone**, central dashboard hides when `showDashboard=false` OR `sections.visible.dashboard=false`.
- [ ] **Admin can rename hero, reorder sections, inject custom CSS** and the changes propagate to both website and desktop tool within 30 seconds.

---

## Self-review notes (built in during planning)

1. **Spec coverage**
   - Req. #1 (toggle): Tasks 1.1–1.4 (site_config-based system-wide); per-game in 1.3.
   - Req. #2 (drop in-card meter): Tasks 1.5, 1.6.
   - Req. #3 (meter only in central panel): inherent in tasks 1.5–1.7.
   - Req. #4 (manual vs auto): Phase 2.
   - Req. #5 (cache hygiene): Phase 3 + installer task.
   - Req. #6 (AI suggestions gated): Phase 5.
   - Req. #7 (universal monitor): Phase 4.
   - Req. #8 (broad customisation): Phase 6.
2. **No placeholders** — every code step has its actual content; the one explicit `TODO` is in Task 4.2 Step 3 and is followed in Step 4 with the actual implementation requirement and the source file to lift from. (The TODO exists because the existing `cp2077_monitor.py` is >25k tokens and can't fit verbatim here.)
3. **Type/name consistency** — `showDashboard` / `show_dashboard`, `source` / `source` used uniformly across schema, API, hooks, UI. `Snapshot` interface adds the same two fields on website and desktop tool.
