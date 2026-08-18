# Cloud Plugin Host — SAFE declarative engine (2026-07-15)

Goal: install/update a plugin from the cloud in an ALREADY-installed launcher with
**NO app rebuild**, WITHOUT reversing the app's security posture. Decision (user,
2026-07-15): **safe declarative engine — the launcher NEVER downloads-and-executes
code.** A plugin is DECLARATIVE data (UI manifest + a recipe over AUDITED primitives).

This EXTENDS the existing `translation_manager/plugins/` base (registry + host +
save_backup), whose `__init__.py` already states the rule: "a plugin is DECLARATIVE
data, never downloaded-and-executed code... run by a built-in, audited HOST."

## What flows from the cloud WITHOUT a rebuild
- The whole plugin **UI** (sections/buttons/lists/fields/labels/icons/layout).
- Plugin **catalog** metadata (name/version/available) — already cloud-driven via
  `site_config.data.plugins`.
- A **new plugin** whose behavior is composed from the bundled AUDITED primitives
  (the launcher's domain: game saves / config / files — backup, copy, sync, restore,
  detect, schedule, pick-folder, list/remove entries).
## What still needs a rebuild (rare)
- A genuinely NEW primitive/capability the audited host doesn't have yet. (Adding a
  new primitive is a small, reviewed code change — the security boundary stays intact.)

## 1. Plugin manifest (cloud catalog entry, sha-none — it's data)
Each catalog entry (bundled fallback in `registry._bundled_catalog()`, or admin
`site_config.plugins[i]`) gains a `ui` (declarative tree) + `capabilities` (which
audited primitives it may call). No package download, no code.
```json
{
  "id": "save-backup", "kind": "save_backup",
  "name": "...", "version": "1.1.0", "icon": "floppy-disks", "accent": "#22c55e",
  "capabilities": ["detect","entries","backup","restore","schedule","picker"],
  "ui": { "...declarative tree, see 2..." }
}
```
`kind` still selects which PRIMITIVE SET the host exposes (save_backup = the existing
`save_backup.py` functions). `ui` is fully cloud-editable.

## 2. Declarative UI schema (drawn by the generic renderer)
Nodes the renderer knows; interactive controls call `plugin_action(pid, action, args)`:
- `{type:"section", title, icon, children}`
- `{type:"row", children}`  (horizontal group)
- `{type:"text", value | bind}`  (`bind`=state key; `{{field}}` interpolation)
- `{type:"banner", tone:"warn|info", icon, text, visibleWhen}`
- `{type:"button", label, icon, action, args, variant, disabledWhen, confirm?}`
- `{type:"list", bind:"stateArrayKey", empty, item:{ text, subtext, badge, buttons:[...] }}`
- `{type:"field", control:"text|folder|select|toggle|schedule", bind, label, options?}`
`visibleWhen`/`disabledWhen` are evaluated against `state` (a safe tiny expression:
`!key`, `key`, `key==val`, `len(key)`). NO arbitrary JS.

## 3. Generic action layer (`plugins/engine.py`, NEW) — the audited primitives
A single dispatcher `run_action(pid, kind, action, args) -> {ok, state?, status?}` that
maps an action NAME to a bundled, audited function. For `kind=="save_backup"` it wraps
the existing `save_backup.py` + `registry` + `host`:
- `detect` -> save_backup.detect() ; `add_detected(game_id)` ; **`add_all`** ;
  `remove_entry(id)` ; `set_entry_enabled(id,on)` ; `add_manual(path,label)` ;
  `backup_now(name?)` (-> host.run_now) ; `list_backups` ; `restore(backup_id)` ;
  `set_schedule(value)` ; `pick_folder` ; `open_folder(path)`.
Every primitive validates its args + confines paths (the plugin's own dirs + the
user-picked folders), exactly like today. `get_state(pid,kind)` returns the dict the
UI binds to: `{entitled, detected[], entries[], backups[], schedule, ...}`.

## 4. Generic RPCs (`main_eel.py`) — STABLE, no per-plugin rebuild
- `plugin_ui(pid)` -> `{ ui, state, meta }` (ui from the catalog manifest; state from engine).
- `plugin_action(pid, action, argsJson)` -> `{ ok, state?, status? }`.
- Existing `plugins_snapshot / install_plugin / remove_plugin / set_plugin_enabled /
  get_plugin_config / set_plugin_config` stay.
DRM gate `registry.can_use_plugins()` re-checked in every action (never UI-only).

## 5. Frontend generic renderer
- `GenericPluginRenderer.tsx` (NEW) — walks the `ui` tree, draws with the design system
  + `UiIcons` (icon by NAME). Buttons -> `plugin_action` -> re-render from returned state.
- `PluginsSettings.tsx` renders `GenericPluginRenderer` for a plugin that has a `ui`
  manifest; the hardcoded `SaveBackupPanel` stays as the fallback for a manifest-less
  catalog entry (and until parity is verified).

## 6. Migration of save_backup
The bundled `_bundled_catalog()` entry gains the `ui` manifest describing today's panel
(banner, detected list + per-row הוסף + **הוסף הכל**, manual add, entries list w/ toggle+
remove, גבה עכשיו/history/restore, schedule) + `capabilities`. Then the SAME UI is
served (and future-editable) from the cloud `site_config.plugins`. Result: the 3 tweaks
shipped today (השבת + distinct icon + הוסף הכל) become cloud-editable data.

## 7. Cloud — GATED on explicit "פרסם" (do NOT deploy)
The `ui` + `capabilities` live in the admin `site_config.data.plugins` (public GET, already
wired in `registry._fetch_cloud_catalog`). Admin edit = the existing PluginsTab, extended
with a `ui`/`capabilities` editor. Nothing to deploy for logic — it's config. Build + test
LOCALLY first; seed the cloud config only on "פרסם".

## Build order (each stage locally tested)
1. `plugins/engine.py` — the audited primitive dispatcher + `get_state` over save_backup. (unit-test)
2. Generic RPCs in `main_eel.py` + bridge slots + `eel.ts`.
3. `_bundled_catalog()` save-backup `ui` manifest (parity w/ today incl. the 3 tweaks).
4. `GenericPluginRenderer.tsx` + wire `PluginsSettings.tsx`.
5. Local run (`python main_eel.py`) -> verify save_backup via the generic renderer == today.
6. Rebuild + install locally. (Cloud/admin editor + seeding only on "פרסם".)
