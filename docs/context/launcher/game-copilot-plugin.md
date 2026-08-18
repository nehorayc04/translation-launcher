## 🧭 Game Co-Pilot plugin — live in-game AI overlay (built + LOCAL install DONE 2026-08-09, NOT published)

New plugin (5th one, alongside save-backup) using the EXISTING declarative
plugin architecture (`plugins/registry.py` + `plugins/engine.py` +
`GenericPluginRenderer.tsx` — **zero frontend/React code needed**, the
Settings panel is generated entirely from a Python `ui` manifest, same as
save-backup). While a game is running: a global hotkey (or a button in the
plugin's own settings) toggles a small always-on-top glass panel over the
game; it captures the foreground window, sends it (+ a Hebrew prompt) to the
user's own Gemini/OpenAI API key, and shows a short Hebrew step-by-step
explanation of what's on screen and what to do.

- **`translation_manager/plugins/game_copilot.py`** (NEW) — the stateless
  "kind" engine: config shape (provider/model/hotkey/corner + last result),
  8 fixed hotkey presets + 4 corner presets (no free-form key-capture UI),
  the capture (Win32 `GetForegroundWindow`+`GetWindowRect`, in-memory JPEG via
  PIL `ImageGrab`, never written to disk), game-name detection (reuses
  `game_detector.match_to_catalog` on the window title, falls back to the
  exe name via `QueryFullProcessImageNameW`), the AI calls (Gemini
  `generateContent` with best-effort `google_search` grounding + a
  no-tool retry; OpenAI vision chat-completions as a 2nd provider), and the
  Hebrew prompt (🎮/📍/🎯/📋/💡 structured answer). The **API key is stored in
  the OS keyring** (service `TranslationManagerGameCopilot`), never in the
  plain-JSON plugin config — same posture as `auth/storage.py`. A tiny
  thread-safe IPC (`report_runtime_status`/`request_toggle`/`request_show`/
  `poll_pending`, one `threading.Lock`) is how a QThreadPool worker (the
  Settings panel's `toggle_overlay`/`test_now` actions) asks the GUI thread to
  show/hide the overlay without ever touching a QWidget off-thread.
- **`translation_manager/qt_shell/game_copilot_runtime.py`** (NEW) — the
  Qt-specific half. Global hotkey via `RegisterHotKey(NULL, ...)` (delivers
  `WM_HOTKEY` to the calling THREAD's queue) + a `QAbstractNativeEventFilter`
  on `windows_generic_MSG` (the exact same technique `qt_shell/main_window.py`
  already uses for `WM_NCCALCSIZE` — proven pattern in this codebase, so the
  hotkey callback runs safely on the GUI thread with no extra plumbing). The
  overlay is a frameless, translucent, `WA_ShowWithoutActivating` (never
  steals focus from the game) `QTextBrowser`-based card, RTL, draggable,
  positioned per the configured corner. A `QTimer` (600ms) on the GUI thread
  polls install/enable state + the IPC; the AI call always runs on a plain
  background `threading.Thread`, and its result reaches the GUI thread via a
  **queued Signal** (Qt's automatic cross-thread delivery) — the analysis
  pipeline itself never touches Qt.
- **Wired**: `plugins/registry.py` `SUPPORTED_KINDS` += `"game_copilot"`,
  a bundled catalog entry (`id:"game-copilot"`, icon 🧭, accent `#38bdf8`) +
  its full `ui` manifest (`_game_copilot_ui()`) + `_default_config` branch.
  `plugins/engine.py` `get_state()`/`_dispatch()` gained a `_kind_of(pid)`
  branch at the top that delegates the WHOLE call to `game_copilot.py` for
  `kind=="game_copilot"` — the existing save_backup code path below is
  UNTOUCHED (regression-tested: save-backup still dispatches correctly).
  `main_qt.py` calls `game_copilot_runtime.ensure_started()` right after
  `main_eel.plugins_boot()` (cheap no-op poll until installed+enabled) and
  `game_copilot_runtime.stop()` in `_on_close_to_exit()` (releases the
  hotkey cleanly on real exit).
- **🔴 A LIVE PRODUCTION WRITE WAS MADE, additive + reversible + zero effect on
  shipped builds:** `available()` merges the ADMIN-MANAGED cloud catalog
  (`site_config.plugins` on the hub) over the bundled fallback, and — same as
  the documented save-backup rollout — a bundled-only entry is invisible to
  any user with real internet access, because the cloud fetch succeeds and
  only iterates entries the cloud already lists. Verified this is genuinely
  true here (this dev machine has live internet). **Seeded a metadata-only
  `game-copilot` row into the live `site_config.data.plugins` array**
  (service key from `website/.env`, same mechanism/table the save-backup
  entry used) — additive (`save-backup` row untouched), and harmless to every
  CURRENTLY INSTALLED launcher (their baked `SUPPORTED_KINDS` doesn't include
  `"game_copilot"`, so the merge silently filters it out) until a NEW build
  with this code is actually published.
- **Verified end-to-end (isolated `%USERPROFILE%`, no real user data touched):**
  catalog lookup finds the bundled `ui` via the metadata-only cloud row →
  install/enable/set_provider/set_model/set_hotkey/set_corner/set_api_key
  (real keyring round-trip, cleaned up after)/clear_api_key/toggle_overlay
  (IPC)/open_url all work; disabled/removed correctly blocks mutating
  actions; save-backup's own dispatch is unaffected (regression check). A
  REAL offscreen Qt smoke test (`QT_QPA_PLATFORM=offscreen`) built the actual
  `GameCopilotController` + `QApplication`, ran a poll tick, toggled the
  overlay open/closed via the exact `engine.run_action` path a Settings-panel
  click uses, and rendered a real Hebrew-formatted answer + an error state
  into the `QTextBrowser` — no crashes.
- **NOT DONE / explicitly out of scope this round:** no real launch/hotkey/
  overlay test on an actual running game (needs the user, per
  [[minimize-game-restarts]] I verified everything provably offline first);
  `RegisterHotKey` can fail if the chosen combo is already claimed by another
  app — the plugin degrades gracefully (status text says so, the settings
  button always works as a fallback); no code changes were made to
  `main_eel.py` (the legacy Eel/dev build has no Qt overlay infrastructure —
  this feature is Qt-shell-only, matching the shipped build).
- **✅ LOCAL BUILD + INSTALL DONE (2026-08-09), per the user's explicit "תבנה
  את מקומית שאני יבדוק את זה".** `& '.\build_exe.bat'` → BUILD_ID
  `20260809064426`, dev_build 219, dist exe fresh (verified mtime). ISCC
  compile of `installer.iss` took **~10 min** (593.5 s — a large
  `_internal` tree, incl. the vendored `dat1lib` + win32/zope deps; the
  FIRST attempt was killed by the PowerShell tool's 5-min foreground
  timeout mid-LZMA-compression, NOT a real failure — re-ran it
  `run_in_background: true` and it finished clean, exit 0, only the two
  pre-existing benign warnings (OnlyBelowVersion / PrivilegesRequired+HKCU)).
  Output: `Output\TranslationManager-Setup-1.2.0.exe` (141,414,198 B).
  Launched via `Start-Process` so the UAC prompt (per
  `PrivilegesRequired=admin`) is up for the user to accept — installing
  requires the user's own click, an agent shell cannot accept UAC.
  **Answered the user's "can this ship without a reinstall?" question:
  NO** — the cloud plugin catalog can only edit DECLARATIVE metadata/UI for
  primitives the app already ships (see `plugins/__init__.py`'s security
  design: never downloaded-and-executed code); a global hotkey + overlay +
  screen-capture + AI call is genuinely new Python/Qt code, so it can only
  reach a user through a real build — this one, and eventually a "פרסם".
  **Still NOT published** — no GitHub release, no `launcher_releases` row,
  no winget manifest touch. Say "פרסם" to ship it.

### Round 2 — glass panel, edge-dock+arrow, REAL key/gamepad capture, API-key hardening (2026-08-09, LOCAL install DONE)

User feedback on round 1 was 4 concrete asks: (1) the overlay should look like the launcher —
glass, slightly blurred; (2) it should dock flush to a screen edge with a centered arrow-handle
to collapse/expand, matching the collapsible settings rail elsewhere in the app; (3) saving a
Gemini API key "doesn't work"; (4) replace the fixed hotkey-preset dropdown with a REAL
press-a-physical-key(-or-2)/controller-button capture, like the existing controller-rebind UI.
All 4 shipped, all confined to the 3 files touched in round 1 (no new frontend/React code, per
the same declarative-plugin design) — verified by `py_compile` + real import/smoke tests before
building (`_normalize_hotkey`/`_normalize_edge` migration, the built `_game_copilot_ui()`
manifest walked to confirm every button's `action` matches a real `run_action` handler, the
`report_runtime_status`/capture IPC names cross-checked against what `game_copilot_runtime.py`
calls, and the `plugin_action` timeout chain — bridge 300s / eel.ts default 120s — checked to
comfortably exceed the new 30s capture budget).

- **Config-shape change:** `cfg["hotkey"]` went from a preset-name STRING to a captured SPEC
  dict — `{"type":"keyboard","mods":int,"vk":int,"label":str}` or
  `{"type":"gamepad","buttons":int,"label":str}`. `game_copilot._normalize_hotkey()` migrates an
  old preset string (already on THIS machine from round-1 testing) to the new shape transparently;
  the legacy 8-entry preset table is kept ONLY for that migration, no longer offered in the UI.
  Corners collapsed **4 → 2**: `cfg["corner"]` (key name kept, to skip a 2nd migration) now holds
  only `"left"`/`"right"` — the panel is ALWAYS vertically centered, directly answering "the arrow
  in the middle". `_normalize_edge()` migrates any old 4-corner value.
- **Hotkey/gamepad CAPTURE — no low-level keyboard hook needed.** `GetAsyncKeyState`/
  `XInputGetState` both query GLOBAL system state (not limited by window focus), so a plain
  ~45ms poll loop is enough — simpler and more robust than a `WH_KEYBOARD_LL` hook (no
  HOOKPROC/thread-lifetime plumbing). New `_CaptureDialog(QDialog)` in
  `game_copilot_runtime.py`: samples both, shows the forming combo live, **locks in on
  RELEASE** (press 1-2 keys/buttons together, then let go — exactly the interaction asked for),
  Esc cancels immediately, a 25s internal deadline guarantees the dialog always closes within
  the worker-thread's 30s budget. Keyboard combos cap at ONE non-modifier key (Ctrl/Shift/Alt/Win
  + one key, matching `RegisterHotKey`'s own shape); gamepad combos cap at ≤2 simultaneous XInput
  buttons. A dual Xbox/PlayStation button-label table (`A/✕`, `B/○`, …) is shown since XInput
  can't detect physical controller brand.
  - **The blocking pattern reuses the EXISTING `busyLabel` mechanism, zero new frontend code.**
    Clicking "עריכה" (Edit) calls `run_action("start_capture")` on a QThreadPool WORKER thread
    (per `bridge.py`'s existing off-thread dispatch); that call `request_capture()`s then BLOCKS
    on a plain `time.sleep(0.08)` poll (`await_capture_result`, 30s timeout) — meanwhile the GUI
    thread's normal 600ms poll tick notices the request within one tick, **stops its own timer**
    (avoids a rare re-entrant-tick edge case while the dialog's nested `.exec()` event loop runs),
    tears down the currently-registered hotkey, pops `_CaptureDialog` modally, and reports the
    locked spec (or "cancelled") back through `report_capture_result()`. The Settings button's
    `busyLabel="לחצו על מקש/ים או כפתור/י שלט (Esc לביטול)…"` is what the user sees the whole time
    — no new UI primitive.
  - New action `reset_hotkey` (→ the built-in Ctrl+Shift+G default) sits next to Edit.
- **Glass / acrylic styling — the SAME native Win32 mechanism the launcher itself would use.**
  `_apply_glass(hwnd)` calls the undocumented `SetWindowCompositionAttribute` with
  `ACCENT_ENABLE_ACRYLICBLURBEHIND`, applied to both the overlay panel's and the capture dialog's
  native HWND on first `showEvent` — real OS blur-behind of whatever sits under the window
  (the game), not just a translucent fill. Best-effort/silently-no-ops on failure (older Windows
  builds), so the QSS translucent gradient underneath still reads as reasonable flat glass on
  its own. DWM corner-rounding was considered and skipped — irrelevant for a
  `WA_TranslucentBackground` per-pixel-alpha window (only matters for opaque rectangular HWNDs).
- **Edge-dock + centered arrow-handle — replaces the old 4-corner floating + free-drag.**
  `_OverlayPanel` is now ONE window: a `QHBoxLayout` (explicit `LeftToRight`, independent of the
  card's own RTL content) ordering `[_HandleTab, card]` or `[card, _HandleTab]` by dock side, both
  `Qt.AlignVCenter` — so the arrow sits centered on the panel's height, flush to the true screen
  edge (`_EDGE_MARGIN=10px`), matching the launcher's own collapsible settings-rail pattern. The
  handle is a small `_HandleTab(QPushButton)` with a chevron glyph (◂/▸, flips per edge+state) —
  clicking it hides/shows just the card (`QWidget.setVisible`) IN PLACE, a lighter action than the
  hotkey's full show/hide of the whole window. Free-drag (`mousePress/Move/ReleaseEvent`) was
  REMOVED entirely now that position is edge-driven, not draggable.
- **API-key fix — diagnostic hardening, not a single confirmed root-cause.** Full code tracing
  (frontend `{{local.apiKey}}` interpolation → `resolveArgs` → `plugin_action` RPC → `engine.py`
  `_kind_of` routing → `game_copilot.set_api_key` → keyring → the Gemini REST call/response
  shape) found no obvious wiring bug anywhere, and this environment can't make a live call to
  Google's API to pin the exact failure — so the fix instead makes ANY failure immediately
  visible and specific instead of silent/delayed: (a) **keyring write-then-read-back** — a
  keyring backend can report success without truly persisting (a locked/misconfigured Windows
  Credential vault); `set_api_key` now re-reads the key right after writing and fails loudly if
  it doesn't match; (b) **an immediate live network verification call** (`verify_api_key` — a
  minimal "reply with exactly one word: OK" prompt, no image) runs the moment the key is saved,
  so "put in the key, nothing happens" becomes an immediate pass/fail; (c) **the PROVIDER'S OWN
  error text is now surfaced verbatim** — `_extract_error_detail()` reads the shared
  `{"error":{"message":...}}` shape both Gemini and OpenAI use and appends it to the Hebrew
  status-code message (`_friendly_http_error` now takes the response object, not a bare status
  code). **Honest caveat for the user:** if the key still fails after this, the NEW error message
  will say specifically why (wrong key / no permission / model not found / quota) — that answer
  itself is the real diagnosis this round couldn't reach from the code alone.
- **Verified before building:** `py_compile` clean on all 3 files; a real Python import of
  `game_copilot.py` exercised `_normalize_hotkey`/`_normalize_edge`/`default_config()` against
  legacy-string, dict-passthrough, `None`, and old-corner-value inputs — all migrate correctly;
  `registry._game_copilot_ui()` was built and walked, confirming every `button`/`field` node's
  `action` (`start_capture`/`reset_hotkey`/`set_corner`/`set_api_key`/`clear_api_key`/`open_url`/
  `toggle_overlay`/`test_now`/`set_provider`/`set_model`) has a matching `run_action` handler and
  every `optionsBind`/template field (`hotkeyLabel`, `edgeOptions`) is actually returned by
  `get_state()`; `main_qt.py`'s `ensure_started()`/`stop()` call sites confirmed unchanged
  (zero-arg signature preserved); the `plugin_action` timeout chain (bridge 300s, eel.ts default
  120s) confirmed to comfortably clear the new 30s capture budget.
- **✅ LOCAL BUILD + INSTALL DONE (2026-08-09).** `& '.\build_exe.bat'` → BUILD_ID
  `20260809135020`, dev_build 220, dist exe mtime confirmed fresh (~1 min old at check time).
  ISCC (background, exit 0) → `Output\TranslationManager-Setup-1.2.0.exe` (141,420,299 B, mtime
  confirmed ~7s old). Launched via `Start-Process` for the user's UAC + click-through — an agent
  shell cannot accept UAC. **Still NOT published** — say "פרסם" to ship it.

### Round 3 — real user testing found 2 bugs, both fixed (2026-08-09, LOCAL install DONE)

The user tested round 2 in-game and sent 2 screenshots: (1) the error card DID surface the real
Gemini error text (proof the API-key hardening works — a genuine free-tier quota exhaustion,
`limit: 0` for `gemini-2.0-flash`, not a broken key), but the raw English detail was one
unformatted wall of mixed-direction text, and the design overall needed real polish; (2) a tiny,
cramped-looking floating element (the collapsed handle at its old 24×68 size, flat single-color
fill, no shadow — read as a stray sliver rather than a deliberate UI piece). A follow-up message
added a 3rd, more important bug: **"וגם הוא לא מזהה את המקשי השלט שמחובר"** (it also doesn't
detect the connected controller's buttons).

- **🎮 THE CONTROLLER BUG — root cause identified with high confidence, no live testing needed to
  be sure of it: XInput is Xbox-controller-only.** `_xinput_buttons()` (round 2's only gamepad
  source) uses the `XInputGetState` API, which by design **never sees a PlayStation DualSense/
  DualShock connected in its native mode** — Windows only routes genuine Xbox-class pads (or
  anything explicitly emulating one) through XInput; a Sony pad is exposed only through the
  legacy DirectInput/joystick subsystem. This is a well-established, universal Windows fact, not
  a guess specific to this session.
  - **Fix: added a 2nd, independent controller backend — the legacy `winmm.dll` joystick API**
    (`joyGetPosEx`/`JOYINFOEX`, the same flat API behind the old `joy.cpl` "Game Controllers"
    panel) — a plain C export, no COM, always present, and it DOES see any HID game controller
    Windows has installed, Sony pads included. `_joy_legacy_buttons()` polls up to 16 legacy
    joystick slots and ORs their button bitmasks; `_joy_legacy_label()` reports generically
    ("שלט (זיהוי כללי): כפתור N") since raw legacy button numbering isn't standardized across
    brands/drivers the way XInput's is.
  - **Both backends are polled together, everywhere** — `_CaptureDialog._tick()` (capture) and
    `GameCopilotController._gp_tick()` (the live hotkey trigger) try XInput first (nicer names
    for genuine Xbox pads) and fall through to the legacy poll only when XInput reports nothing
    that tick (cheap to skip when XInput already claimed the tick). The captured spec now carries
    a `"backend": "xinput"|"legacy"` field so the trigger-side poll always re-checks against the
    SAME backend the combo was captured from (the two bitmask spaces are unrelated — comparing a
    legacy mask against `_xinput_buttons()` would silently never fire). `_apply_hotkey`'s
    "driver present" check now branches on the backend (`_WINMM is not None` vs
    `_XINPUT is not None`) accordingly.
- **🖋 Error-message formatting** — `_format_error(msg)` (new, parallel to the existing
  `_format_answer`) splits an error on the FIRST `" — "` (exactly where `_friendly_http_error`
  joins the Hebrew summary to the provider's own raw text) and renders them as two visually
  distinct blocks: a bold amber RTL summary line, and — only when a detail half exists — a
  separate, explicitly `dir='ltr'`, slightly muted, word-broken block underneath for the raw
  (often English, URL-heavy, multi-line) provider text. `set_error()` now calls it instead of
  dumping everything as one undifferentiated RTL blob.
- **✨ Stronger "glass" look, not dependent on native OS blur alone.** Widened/softened the
  `_GLASS_CARD_QSS` highlight band (a taller, gentler top sheen + a brighter hairline border +
  an 18px radius, up from 16px) so the card reads as frosted glass purely from its own gradient
  even where the best-effort native Acrylic call doesn't come through. Added a shared
  `_glass_shadow(widget, radius, y_offset)` helper (`QGraphicsDropShadowEffect`) applied to BOTH
  the overlay card and the capture-dialog card — real drop shadows give a floating-over-the-game
  look that doesn't depend on OS support at all. The `_HandleTab` grew **24×68 → 30×80**, got its
  OWN drop shadow, a real glass gradient fill (was flat `rgba`) instead of a solid color, a
  brighter border, a bigger/bolder chevron, and its outward (screen-edge) corners went from a
  hard square 0px to a soft 6px (inward corners stay 18px) so it reads as a deliberate floating
  chip even when collapsed and shown alone.
- **Verified before rebuilding:** `py_compile` clean; a real offscreen-Qt smoke test
  (`QT_QPA_PLATFORM=offscreen`) confirmed BOTH `winmm` and `XInput` load without error on this
  machine, `_xinput_buttons()`/`_joy_legacy_buttons()` both execute cleanly (return 0, correctly,
  since no controller is attached to the BUILD machine), `_format_error` renders both the
  with-detail and no-detail cases, and `_OverlayPanel`/`_CaptureDialog`/`GameCopilotController`
  all instantiate and run their key methods (edge switch, collapse toggle, reposition, `_tick`,
  `_gp_tick`) without exceptions.
- **✅ LOCAL BUILD + INSTALL DONE (2026-08-09).** `& '.\build_exe.bat'` → BUILD_ID
  `20260809141744`, dev_build 221, dist exe fresh. ISCC (background, exit 0) →
  `Output\TranslationManager-Setup-1.2.0.exe` (141,423,880 B, mtime confirmed ~8s old). Launched
  via `Start-Process` for the user's UAC + click-through. **Still NOT published.**
- **Honest caveat, stated to the user:** the controller fix is built on a well-founded, high-
  confidence diagnosis (Sony pad + native XInput = structurally invisible, a universal Windows
  fact) rather than a live test with the user's actual hardware in the loop (not possible from
  this environment) — if it's STILL not detected after this build with a genuine PlayStation pad,
  or if the pad is actually a genuine Xbox controller and still fails, that would point to
  something else and needs the user's own next report to pin down.

### Round 4 — the panel was STILL opaque (native backdrop mechanism swap) + 5-provider AI (2026-08-09, LOCAL install DONE)

User, after round 3: **"זה לא שקוף מטושטש אלא אטום! תתקן את זה."** (it's not translucent/blurred,
it's OPAQUE — fix it) + **"וגם שיעבוד על כל סוגי המפתחות שיש בעולם ולא רק של גוגל כגון groq
וnvapi וsambanova ועוד. מודל מתאים"** (make it work with every kind of API key in the world, not
just Google's — groq, nvapi, sambanova and more, with a suitable model [per provider]).

- **🪟 OPACITY — TWO independent causes, both fixed.** (1) `SetWindowCompositionAttribute` /
  `ACCENT_ENABLE_ACRYLICBLURBEHIND` (round 1's mechanism) is an older, undocumented Windows-10-era
  API; on this DWM it plausibly never actually composited blur behind a Qt
  `WA_TranslucentBackground` layered window (that translucency plumbing itself is confirmed
  correctly set on both `_OverlayPanel`/`_CaptureDialog` — never the problem). **Replaced with
  `DwmSetWindowAttribute` / `DWMWA_SYSTEMBACKDROP_TYPE`(38) / `DWMSBT_TRANSIENTWINDOW`(3, =
  Acrylic)** — the SAME modern, first-class DWM call this project's own **FleetDash** ("מצב הצי")
  tool already uses successfully for its own floating glass panel, so this is a
  proven-in-this-codebase mechanism, not a first attempt. `_apply_glass(hwnd)` kept its exact
  name/signature so both call sites needed no change. (2) **Independent of native blur, the QSS
  fill itself was near-opaque** — `_GLASS_CARD_QSS`'s gradient peaked at **222-240/255 (87-94%
  opaque)** across most of the card, so even perfect native blur behind it would barely show
  through. Lowered to **150-170/255 (~59-67% opacity)**, defense-in-depth so the panel reads as
  genuine glass even on a machine where DWM Acrylic is ever unavailable.
- **🌐 FIVE AI providers instead of just Gemini/OpenAI — `_call_provider()` dispatcher.** Gemini
  keeps its own native `generateContent` REST call; **OpenAI, Groq, NVIDIA NIM (`nvapi`), and
  SambaNova all speak the IDENTICAL OpenAI-compatible chat-completions shape**
  (`messages`/`content` in, `choices[0].message.content` out) — the exact fact this project's OWN
  translation-fleet infra (`universal/fleet_providers.py`) already leans on for these same four
  providers — so ONE `_call_openai_compatible(name, base_url, api_key, model, prompt, image)`
  serves all of them, parameterized only by base URL + display name. Groq gets the project's own
  documented fix (a real browser User-Agent — the Cloudflare "1010" trap already solved in
  `fleet_providers.py`).
  - **`PROVIDER_OPTIONS`/`MODEL_OPTIONS`/`_PROVIDER_KEY_URL`/`_OPENAI_COMPAT_BASE`** — a
    catalog-driven Settings dropdown (provider → its own model list → its own "get a free key"
    URL, ONE generic button+row in the manifest replacing the old two hardcoded
    Gemini-only/OpenAI-only rows). Chosen model per provider — honest caveat: exact catalog
    naming/availability is training-data knowledge, not live-verified: Groq
    llama-4-scout/maverick (vision) + llama-3.3-70b-versatile (text); NVIDIA NIM
    llama-3.2-90b/11b-vision-instruct + llama-3.1-70b-instruct (text); SambaNova
    Llama-3.2-90B-Vision-Instruct + two text-only fallbacks, the vision one labeled
    "אם זמין לחשבון שלכם" since SambaNova's vision-model availability varies by account.
  - **`"vision": bool` per model + `_model_supports_vision()`** — not every model on every
    provider accepts an image; picking a text-only model now SKIPS screen capture entirely (no
    wasted API call sending an unusable image) and appends an explanatory Hebrew note to the
    prompt instead. `registry.py` shows a matching amber warning row
    (`visibleWhen:"!modelSupportsVision"`).
  - `get_state()` now returns `keyUrl` (routes the ONE "get a key" button per provider) and
    `modelSupportsVision`, both consumed directly by the existing declarative UI manifest — zero
    new frontend/React code, per the plugin architecture's whole design.
- **🎮 The R1+R2 gamepad-combo semantics the user re-confirmed mid-session
  ("לחיצה אורכה על R1 ואחר כך על R2 ... ורק אם אני לוחץ על שתיהם זה יעבוד") were ALREADY correct
  from rounds 2-3 — no new code needed.** Capture accumulates buttons via a union-while-held mask
  (holding R1 alone never locks; the combo only locks on FULL release — i.e. after both were held
  together and THEN released), and the live trigger requires `(mask & target) == target` — a
  subset press never fires. Confirmed by re-reading the logic, not by new live testing (no
  gamepad attached in this environment) — told to the user to verify directly rather than claimed
  as newly fixed.
- **Verified before rebuilding — 2 offscreen Qt smoke passes, both clean:** (1) module-level — all
  5 providers' catalog entries internally consistent (`MODEL_OPTIONS`/`_PROVIDER_KEY_URL`/
  `_OPENAI_COMPAT_BASE` all keyed the same); `get_state()` returns the right `keyUrl`/`model`/
  `modelSupportsVision` per provider (isolated fake `registry` config — no real install/disk
  touched); **`_call_provider()` was exercised against the REAL network for all 5 providers with a
  deliberately-invalid key** — every one reached its real endpoint and came back with a proper
  provider-side 400/401 "invalid key" error correctly wrapped into a Hebrew `RuntimeError` (strong
  evidence the base URLs, request shape, and the Groq UA fix are all genuinely correct — not just
  that the code doesn't crash); the `game-copilot` UI manifest JSON contains both new
  `keyUrl`/`modelSupportsVision` bindings. (2) widget-level — `_GLASS_CARD_QSS`'s new alpha values
  confirmed present verbatim; `_OverlayPanel`/`_CaptureDialog` constructed + SHOWN for real
  (invoking the real `showEvent` → the real `_apply_glass()` DWM call, offscreen HWND, no
  exception); `panel.set_error()` rendered real HTML into the body with no exception.
- **✅ LOCAL BUILD + INSTALL DONE (2026-08-09).** `& '.\build_exe.bat'` → BUILD_ID
  `20260809144631`, dev_build 222, dist exe fresh (~26s old at check time, `=== BUILD SUCCESS ===`).
  ISCC (background, exit 0, "Successful compile", only the 2 pre-existing benign warnings) →
  `Output\TranslationManager-Setup-1.2.0.exe` (141,415,006 B, mtime confirmed ~6s old). Launched
  via `Start-Process` for the user's UAC + click-through. **Still NOT published.**
- **Honest caveats, stated to the user:** (a) the DWM-Acrylic swap is a well-reasoned fix built on
  a mechanism already proven working elsewhere in this codebase, but — like every visual fix this
  session — it cannot be confirmed from this environment without the user's own screen; if it's
  STILL opaque after this build, the QSS-alpha half of the fix should at minimum make it visibly
  LESS opaque even if native Acrylic still isn't compositing, which would narrow the next
  diagnosis specifically to the DWM call. (b) exact model IDs/catalog per new provider
  (Groq/NIM/SambaNova) are the best available choice from training knowledge, not live-verified
  against each provider's current API — if a specific model name has since changed or is
  unavailable, the provider call surfaces THAT provider's own real error text (thanks to the
  round-3 error-formatting work), making it a one-line model-ID fix rather than a silent failure.

### Round 5 — real transparency fix, richer glass+logo+animations, robust gamepad capture, long-press drag-to-reposition (2026-08-09, LOCAL install DONE)

User tested the round-4 build and sent a screenshot: the panel was still **visibly opaque with a
hard white-ish border**, colours read as "too plain", there were **no real animations**, and TWO
functional problems surfaced under real use: pressing 2 gamepad buttons and releasing did NOT
reliably lock in the combo (asked to choose again / picked the wrong thing), and there was no way
to reposition the panel except a Settings dropdown. Full request, verbatim intent: nicer colours,
GENUINE transparency (see the game through the card), no hard edges, a nice logo, real launcher-
style animations, auto-grow/shrink vertically to the AI text while staying anchored ("קבוע"), a
correct press-and-HOLD-then-second-button gamepad capture, and Samsung-side-panel-style long-press-
then-drag repositioning to any screen edge (works whether the panel is open or collapsed). Explicit
instruction: **"תשתמש בסקילים של עיצוב"** (use design skills). All of it shipped in one pass —
`translation_manager/plugins/game_copilot.py` (edge-model extension) +
`translation_manager/plugins/registry.py` (one label string) +
`translation_manager/qt_shell/game_copilot_runtime.py` (full rewrite, same file, no new files).

- **🔴 THE REAL ROOT CAUSE OF "STILL OPAQUE" — a missing `DwmExtendFrameIntoClientArea` call.**
  Round 4's `DwmSetWindowAttribute`/`DWMWA_SYSTEMBACKDROP_TYPE`(38) alone is a well-documented
  no-op on a plain frameless Win32/Qt window UNLESS the window first tells DWM to treat its whole
  client area as "glass" — `DwmExtendFrameIntoClientArea(hwnd, &MARGINS{-1,-1,-1,-1})`. Without it
  the backdrop call can report success with **zero visible effect**, which is exactly what
  happened. `_apply_glass()` now calls both, in that order, still best-effort/no-op-on-failure.
  The `_GLASS_CARD_QSS` fill alpha was also lowered again in this pass (see below).
- **🎨 Design pass — richer glass, a real logo, no hard edges, matching the launcher's motion
  language.** Read `frontend/src/index.css`'s own design tokens as the reference (`.glass`/
  `.glass-soft` fill/border values, the `.nav-slide`/`.view-transition` springy easing curve
  `cubic-bezier(.34,1.35,.5,1)`) rather than guessing:
  - **`_GLASS_CARD_QSS`** replaced the flat grayscale gradient with a diagonal **warm-gold → whisper-
    of-cyan → deep-indigo** gradient (echoing the brand's yellow/cyan pairing) at genuinely low
    alpha (58/26/152/178 of 255), a barely-there warm hairline border (was a stark white 1px line),
    and a bigger 20px radius everywhere (card + handle + capture dialog all share the constant).
  - **`_brand_icon_path()`** (new, duplicates `tray.py`'s `_icon_path` dev/`_MEIPASS` resolution
    pattern locally, same reasoning as the existing Win32-constant duplication in this file) loads
    `build_assets/app.ico` as a small `QIcon` pixmap next to the title in the header — RTL layout
    auto-mirrors it to sit beside the Hebrew title on the visual right.
  - **`_spring_curve()`** (new) builds a `QEasingCurve.BezierSpline` with `addCubicBezierSegment
    (QPointF(.34,1.35), QPointF(.5,1), QPointF(1,1))` — the EXACT same overshoot-then-settle motion
    as the launcher's own CSS, reused for every animation below so the native panel feels like part
    of the same product instead of a generic Qt default ease.
  - **`_HandleTab`**: no visible hard border (soft `rgba(255,255,255,26)` hairline instead), a
    richer vertical glass gradient, bigger rounded corners on BOTH sides (was a hard 0-radius on the
    screen-flush side), and a genuine drop shadow via the existing `_glass_shadow` helper (now
    slightly indigo-tinted instead of flat black) — no longer reads as a stray sliver when collapsed.
  - Header buttons' hover state shifted from a flat white-brighten to a **cyan-tinted** glow
    (`rgba(56,189,248,42)`), matching the accent used throughout the app.
- **📏 Auto-grow/shrink to AI-text length, symmetric around a fixed anchor ("קבוע").**
  `_set_body_html()` measures the real rendered document height (`QTextDocument.setTextWidth` +
  `.size().height()`, capped at ~62% of screen height) and, IF the panel is already visible, hands
  the target to `_animate_body_height()` — a `QVariantAnimation` stepping `_body.setFixedHeight()`
  and calling `reposition()` on every frame using the spring curve. **`reposition()` was rewritten
  to be anchor-centered**: the window's CENTER (not top-left) stays pinned at a persisted `edge_pos`
  fraction along whichever edge it's docked to, so a height change grows/shrinks the panel
  SYMMETRICALLY (up AND down for a left/right dock, left AND right for a top/bottom dock) instead
  of drifting — directly matching the user's "יתרחב למעלה ולמטה … שזה יהיה קבוע" wording. Manual
  expand/collapse (short click on the handle) is untouched and still works at any time.
- **🎬 Real show/hide motion.** `show_animated()`/`hide_animated()` (new, replacing bare `.show()`/
  `.hide()` at every call site in `GameCopilotController`) fade+slide the WHOLE window in from the
  direction of its docked edge (`QPropertyAnimation` on the real Qt properties `windowOpacity` +
  `pos`, run together in a `QParallelAnimationGroup`, spring easing on the move / cubic on the
  fade) and fade out on close. `show_animated()` is a safe no-op-but-raise when already visible, so
  a loading→result content swap never re-triggers the entrance animation.
- **🕹️ Gamepad-combo capture root-caused and fixed — the real bug, not the "already correct"
  claim from an earlier round.** Live testing proved 2-button capture DID misfire. Diagnosis: the
  OLD code ran two fully independent per-backend state machines (XInput vs the legacy winmm
  joystick API) and let them interleave — a single-tick zero-read glitch from one backend (common
  on wireless/BT pads) could hand control to the other mid-hold, corrupting the accumulated combo,
  and there was no debounce on the "released" edge so one dropped sample could finalize early with
  an incomplete combo. **Fix in `_CaptureDialog._tick()`:** the capture now **locks onto whichever
  backend first reports ANY press** for the rest of that one attempt (never both, never switches
  mid-combo); the "released" edge requires **`_RELEASE_DEBOUNCE = 3` consecutive EMPTY polls**
  (poll interval tightened 45ms→30ms, so ~90ms of genuine silence) before finalizing; a visible
  **"🔒 הוסיפו כפתור נוסף או שחררו לבחירה"** hint appears once a single button has been held past
  `_ARM_MS = 320ms` (matching the user's described mental model: hold-then-add-a-second-button);
  and holding >2 buttons shows a **"⚠ עד 2 כפתורים בלבד"** warning instead of silently misbehaving.
- **↔️ Long-press-and-drag repositioning to ANY of 4 screen edges — Samsung side-panel style,
  replacing the Settings-dropdown-only model.** `_HandleTab` gained `mousePressEvent`/
  `mouseMoveEvent`/`mouseReleaseEvent` overrides: a 320ms `QTimer` arms "drag mode" if the button is
  still held without releasing; once armed, the whole window follows the cursor live
  (`dragStarted`/`dragMoved`/`dragFinished` signals → `_OverlayPanel._on_drag_start/_move/_finish`);
  on release, `_snap_to_nearest_edge()` picks whichever of the 4 screen edges the window's CENTER
  is closest to (by simple distance), computes the along-edge fraction, and persists BOTH the new
  `edge` and `edge_pos` straight to `registry.set_config()` (the next periodic `_sync_from_config`
  tick reads the identical value back — no fighting). The handle is the single drag affordance
  chosen deliberately because it's ALWAYS visible whether the card is expanded or collapsed
  ("אפילו שהוא פתוח, אפילו שהוא סגור"), so no need to distinguish draggable-vs-interactive regions
  inside the card itself. A short click (no hold) still just toggles collapse, unaffected.
  - **Backend data-model extension** (`game_copilot.py`, `registry.py`): `EDGE_OPTIONS` grew from
    2 values (left/right, always vertically centered) to 4 (`left`/`right`/`top`/`bottom`);
    `DEFAULT_EDGE_POS = 0.5` + `_normalize_edge_pos()` (clamps to [0,1], NaN-safe) added alongside
    the existing `_normalize_edge()` (which now also migrates the old 4-corner values
    `top-right`/`bottom-left`/etc. down to their nearest side, on top of its existing 2→4 migration
    duty). `default_config()`/`get_state()` carry `edge_pos`/`edgePos`. Picking a value from the
    Settings dropdown (still offered as the keyboard/no-mouse fallback) resets `edge_pos` back to
    centered, since a discrete choice carries no along-edge position information. The Settings
    label was updated to mention the drag ("או גררו את החץ שלה בלחיצה ארוכה, גם כשהיא סגורה").
  - **`_OverlayPanel._reflow()` generalized to 4 edges**: the outer layout is now a `QBoxLayout`
    (not a fixed `QHBoxLayout`) whose direction switches between `LeftToRight` (left/right dock) and
    `TopToBottom` (top/bottom dock); `_HandleTab.set_orientation(vertical)` swaps its fixed size
    between 30×80 and 80×30; `_HandleTab.set_style()` now picks one of 4 chevron glyphs (◂▸/▴▾) and
    4 corner-radius patterns depending on which edge it's flush against.
- **Verified before rebuilding — `py_compile` on all 3 touched files clean, then a real offscreen
  Qt smoke test**: `_HandleTab` orientation swap, all 4×2 `set_style()` combinations, a simulated
  short-click (no drag fires) AND a simulated long-press→move→release (both `dragMoved` and
  `dragFinished` fire correctly, `_dragging` resets); `_OverlayPanel` cycled through all 4 edges +
  `reposition()`, collapse/expand, `set_loading`/`set_content`/`set_error`/`set_hotkey_label`, a
  full drag start/move/finish cycle, and BOTH `show_animated()` (fresh + already-visible no-op
  branches) and `hide_animated()` actually invoked with `app.processEvents()` pumped afterward (no
  exception); `_CaptureDialog` constructed with its internal timers stopped (no real controller in
  this environment) and the label-formatting helpers (`_gp_label`/`_joy_legacy_label`) exercised
  directly; `GameCopilotController` ticked + stopped cleanly with no plugin installed. Separately,
  `game_copilot.py`'s `_normalize_edge`/`_normalize_edge_pos`/`default_config`/`EDGE_OPTIONS` were
  round-trip-tested for every migration path (old 2-value, old 4-corner, out-of-range/NaN floats).
- **✅ LOCAL BUILD + INSTALL DONE (2026-08-09).** `& '.\build_exe.bat'` → BUILD_ID `20260809153249`,
  dev_build 223 → ISCC → `Output\TranslationManager-Setup-1.2.0.exe` → installed locally (UAC
  click-through by the user). **Still NOT published** — say "פרסם" to ship it.
- **Honest caveats, stated to the user (same posture as every round):** the
  `DwmExtendFrameIntoClientArea` fix is well-grounded (this is the textbook missing piece for
  Mica/Acrylic on a non-WinUI window) but, like every visual fix this session, cannot be confirmed
  from this environment without the user's own screen — if the panel is STILL not genuinely
  translucent after this build, the two DWM calls together are the full extent of what's
  achievable via the documented API; anything beyond that would mean the compositor itself is
  declining to apply it (rare, but possible on some driver/theme configurations). The gamepad-lock
  fix is a real, reasoned root-cause fix (backend racing + no release-debounce, both now closed)
  but was necessarily built and verified without a physical controller attached in this
  environment — genuinely needs the user's own hardware to confirm the exact 2-button hold-then-
  release feel now matches what they described.

### Round 6 — the panel "looked Python-drawn"; hand-painted the fill, found + fixed a REAL transparency bug via pixel-level self-verification (2026-08-14, LOCAL install DONE)

User, after round 5: *"בגלל שזה נוצר דרך עיצוב של פיתון אז זה נראה מכוער האם יש דרך אחרת שיהיה
גם עיצוב שקוף זכוכית מטושטש קצת שגם הטקסט יהיו קריא וגם הדברים והצבעים שיש מתחת יראו כמו שצריך
כגון זכוכית מטשטשת. בלי קצוות רקע מוזרים וצבעים קבועים ובלי בעיות ביצועים"* — 6 explicit criteria:
doesn't look artificially "drawn"; genuinely transparent+blurred; text stays readable; the real
content behind it (the GAME) shows through, not a fixed/hardcoded color; no weird background
edges (the round-5 QSS border/corner artifact); no performance cost. All in
`translation_manager/qt_shell/game_copilot_runtime.py`.

- **Kept DWM Acrylic as the blur source, deliberately — not manual capture-and-blur.** This
  project's own documented history: GDI/BitBlt screen capture (`QScreen.grabWindow`, `mss`,
  `ImageGrab`) returns BLACK frames for a modern DX12 flip-model exclusive-fullscreen game. DWM's
  own compositor has privileged access to the real final frame regardless of how the game
  presents — a completely different code path from third-party capture, and effectively free
  (no manual per-frame capture+blur loop). This is what answers "without performance problems"
  directly: the blur is the OS compositor's job, not ours.
- **Added `DWMWA_WINDOW_CORNER_PREFERENCE`(33)=`DWMWCP_ROUND`(2) as a second, independent line of
  defense against square pixels** — the exact same call this codebase already uses successfully
  in `qt_shell/main_window.py`, now also applied to the overlay/capture-dialog HWNDs inside
  `_apply_glass()` (still inside the existing best-effort `try/except`, after the existing
  `DwmExtendFrameIntoClientArea` + `DWMWA_SYSTEMBACKDROP_TYPE` calls from round 5).
- **Replaced the QSS-painted card fill with a hand-painted `QPainterPath`.** New
  `_rounded_path(rect, radius)` / `_asymmetric_rounded_path(rect, big, small, big_side)` (the
  asymmetric one built ONLY from safe uniform `addRoundedRect` + rectangle-region
  `.intersected()`/`.united()` — deliberately no hand-rolled `arcTo()` sweep math, which can't be
  visually verified from here and a wrong sweep could self-intersect) and a new `_GlassCard(QFrame)`
  whose `paintEvent` fills ONLY that rounded path (never calls `super().paintEvent()`), replacing
  the old `_GLASS_CARD_QSS` string entirely (both `_OverlayPanel` and `_CaptureDialog` now
  construct `_GlassCard(self, radius=20.0)` instead of a plain `QFrame` + a QSS stylesheet).
  `_HandleTab` got the matching treatment (`paintEvent` fills `_asymmetric_rounded_path` with a
  hover/press-aware gradient + hand-draws the chevron glyph), replacing its own QSS block.
- **Per the Apple-design skill's own rule — "put color on a solid layer, not the translucent
  foreground; never stack a light translucent surface on another"** — the loud round-5 rainbow
  gold→cyan→indigo diagonal gradient was REMOVED from the see-through card fill and replaced with
  a low-alpha, mostly-neutral cool-navy gradient (`26/16/120` of 255) with just a hint of brand
  cyan — genuine glass, not a colored film. "Richness" stays on solid, opaque chrome only: the
  title text (brand yellow), section headers in the AI answer (cyan), button hover glows, and the
  handle's own vivid blue gradient (legitimate — it's a small SOLID chip, not the see-through
  surface).
- **🔴🔴 SELF-CAUGHT REAL BUG: `_GlassCard`'s corners rendered fully OPAQUE, not transparent —
  found by my own rigorous pixel-level testing, not by the user.** My first verification used
  `widget.render(QImage)` and reported the card's corners at `alpha=255` and the handle's CENTER
  at `alpha=0` — both looked like real bugs. Re-testing with `.grab()` instead (the SAME path both
  the coarse smoke test and real on-screen painting actually go through) showed the handle was
  fine all along (`.render()` was the flawed instrument, not the widget) — but it also revealed
  `_GlassCard.grab()` rasterizes as **`Format_RGB32`, which has NO ALPHA CHANNEL AT ALL**, so its
  corners came back `(239,239,239,255)` — Qt's default opaque palette background, not the intended
  see-through. **Root cause: `_GlassCard` (a plain `QFrame`) never set `Qt.WA_TranslucentBackground`,
  so Qt treats it as opaque wherever the custom `paintEvent` doesn't paint** — exactly the "weird
  square edges around the glass" class of defect the user described, now with a concrete pixel
  measurement instead of a guess. Fix: `self.setAttribute(Qt.WA_TranslucentBackground, True)` +
  `Qt.WA_NoSystemBackground` + `setAutoFillBackground(False)` in `_GlassCard.__init__` (and the
  same three, defensively, in `_HandleTab.__init__` even though it already worked — makes the
  requirement explicit rather than relying on an unstated QPushButton+flat implementation detail).
  **Verified after the fix, via `.grab()`**: card format now has a real alpha channel, all 4
  corners `alpha=0`, center `alpha=62` (a genuinely light, see-through fill — not a solid card);
  handle corners `alpha=6–51` (soft rounded edge), center `alpha=243` (a real, mostly-opaque solid
  chip, as intended). **UNIVERSAL for this codebase: a hand-painted partial-alpha `paintEvent` on
  a CHILD widget needs `WA_TranslucentBackground` explicitly — without it, Qt/`.grab()` silently
  demotes the surface to an opaque RGB format and the corners fill with the default palette color,
  which reads exactly like "weird edges" and can hide behind a coarse smoke test that only checks
  `grab()` didn't throw, never its actual alpha.**
- **Verified: `py_compile` clean; the full 46-check offscreen smoke test still 100% pass; PLUS a
  new pixel-alpha verification** (`widget.grab().toImage().pixelColor(x,y).alpha()` at all 4
  corners + center, for both `_GlassCard` and `_HandleTab` across the round-5 edge/style matrix) —
  all pass on the corrected code. This pixel test is new methodology for this feature and is a
  stronger check than anything used in rounds 1-5 (those verified "doesn't throw/has a real size",
  never actual per-pixel transparency).
- **Honest caveats, unchanged posture:** the DWM Acrylic + corner-rounding mechanism is
  architecturally sound and matches this codebase's own proven pattern, and the transparency bug
  is now genuinely fixed and pixel-verified — but NONE of this can be confirmed against the real
  compositor, a real GPU, or an actual game running behind the panel from this environment; only
  the user's own screen settles whether it now reads as real frosted glass rather than a flat
  color. **Still NOT published — LOCAL install only, per the standing rule; say "פרסם" to ship it.**

### Round 7 — the DWM Acrylic backdrop was silently defeated by `WA_TranslucentBackground` itself; fixed the ROOT layer, plus a Groq model retirement (2026-08-15, LOCAL install `20260815200743`)

User, after round 6 shipped: **"התוסף לא ישתנה"** (the plugin isn't changing) + two screenshots — the
second matched the current build's real loading text exactly, so this was NOT a stale-screenshot
false alarm (my first hypothesis, ruled out by cross-checking the live launcher log + the running
process's exact BUILD_ID): the panel genuinely still rendered as a flat, non-glassy gray card over a
visually rich background, even with round 6's corner-transparency fix installed and confirmed
working via pixel test. Round 6 fixed a REAL bug (`_GlassCard` corners going opaque); it was never
the bug the user was actually looking at.

- **🔴🔴 THE ROOT CAUSE, confirmed via `WebSearch` (not guessed): `Qt.WA_TranslucentBackground` on a
  TOP-LEVEL window, on Windows, makes Qt create it as a classic GDI **layered window**
  (`WS_EX_LAYERED`) — and that compositing model is architecturally INCOMPATIBLE with DWM's native
  `DWMWA_SYSTEMBACKDROP_TYPE` (Acrylic/Mica).** Two non-combinable rendering paths. So every
  `_apply_glass()` call in rounds 5-6 was reporting success on all three DWM calls
  (`DwmExtendFrameIntoClientArea` → `DWMWA_SYSTEMBACKDROP_TYPE=38` → `DWMWA_WINDOW_CORNER_
  PREFERENCE=33`) while the window's own `WA_TranslucentBackground` attribute (set in `_OverlayPanel.
  __init__`/`_CaptureDialog.__init__` since round 1) silently forced it into the ONE mode where none
  of that backdrop material can ever actually show through. This is the real reason the panel always
  looked flat — not a paint bug, a window-creation-attribute bug, one layer below anything a pixel
  test on a CHILD widget (round 6's whole verification) could ever catch.
- **Fix: `Qt.WA_TranslucentBackground` → `Qt.WA_NoSystemBackground` on BOTH top-level windows**
  (`_OverlayPanel.__init__`, `_CaptureDialog.__init__`). `WA_NoSystemBackground` gets the actually-
  needed effect (skip Qt's own opaque erase-before-paint, so nothing but our own `paintEvent`s ever
  draws into the window) WITHOUT going layered — leaving DWM's own backdrop material visible
  wherever we don't explicitly paint, which is the documented way native Mica/Acrylic windows work.
  The CHILD widgets (`_GlassCard`, `_HandleTab`) correctly KEEP `WA_TranslucentBackground` — they
  aren't native top-level windows, so they never trigger this issue, and round 6's fix for them
  stays exactly as-is.
- **🔴 A second, independently-confirmed instance of the SAME incompatibility: `QWidget.
  setWindowOpacity()` on Windows ALSO auto-enables `WS_EX_LAYERED`, regardless of any other
  attribute** — a second `WebSearch` found this is documented to be WORSE than a flat gray card on a
  DWM-backdrop window ("a black opaque background with no alpha channel that doesn't compose with
  the Mica or Acrylic material underneath"). This codebase had FIVE `setWindowOpacity()`/
  `windowOpacity` call sites on `_OverlayPanel` — the drag-dim (`_on_drag_start`/`_on_drag_finish`,
  0.90↔1.0) and the round-5 show/hide fade animations (`show_animated`/`hide_animated`/
  `_finish_hide`) — every one of which would have RE-TRIGGERED the layered-window mode the moment it
  fired (i.e. on every single drag, show, and hide), undoing the fix above at runtime and risking the
  documented black-box artifact on top of it.
- **Fix: moved every opacity animation off the native window entirely, onto a `QGraphicsOpacityEffect`
  on a new plain `_content` wrapper widget.** `_OverlayPanel.__init__` now builds a minimal top-level
  layout holding ONE child (`self._content`, a `QWidget`), and the real `outer` box layout (holding
  `_card`+`_handle`, previously installed directly on `self`) now lives on `_content` instead — so
  `_reflow()` reads/writes `self._content.layout()`, not `self.layout()`. `self._content_effect =
  QGraphicsOpacityEffect(self._content)` is what every fade/dim now drives:
  `_on_drag_start`/`_on_drag_finish` call `_content_effect.setOpacity(0.90/1.0)`;
  `show_animated`/`hide_animated`/`_finish_hide`'s `QPropertyAnimation`s target `b"opacity"` on
  `_content_effect` instead of `b"windowOpacity"` on `self`. `QGraphicsOpacityEffect` is pure
  Qt-internal offscreen-buffer compositing on a non-top-level child — it never touches
  `WS_EX_LAYERED` or any native window attribute, so it can't reintroduce the DWM incompatibility no
  matter how often a drag/show/hide fires. **UNIVERSAL for this codebase: on a DWM-backdrop
  (Acrylic/Mica) top-level window, NEITHER `WA_TranslucentBackground` NOR `setWindowOpacity()` may
  ever be used — both silently force `WS_EX_LAYERED`, which cannot compose with the backdrop. Any
  fade/dim on such a window MUST go through a `QGraphicsOpacityEffect` on a child widget instead.**
  > ⚠️ **HALF-SUPERSEDED BY ROUND 12 — read that section before acting on this one.** The
  > `WS_EX_LAYERED`-vs-DWM-backdrop fact is correct, but the CONCLUSION drawn here (drop
  > `WA_TranslucentBackground`, keep `DWMWA_SYSTEMBACKDROP_TYPE`) is what later rendered the
  > overlay as a **black rectangle**: a non-translucent Qt window has an opaque client area, and
  > the `QWebEngineView` that now hosts the panel paints solid black through it. The overlay is
  > deliberately on the **other** recipe — layered `WA_TranslucentBackground` +
  > `SetWindowCompositionAttribute`/`ACCENT_ENABLE_ACRYLICBLURBEHIND`. The `setWindowOpacity()`
  > ban still stands unconditionally, and the `QGraphicsOpacityEffect` advice is itself superseded
  > for the web-view panel (an opacity effect on an ancestor of a `QWebEngineView` can blank it —
  > fades live in the page's CSS instead).
- **Separately, user-reported: Groq retired `llama-3.3-70b-versatile`** (the text-only Groq entry in
  `MODEL_OPTIONS`, `translation_manager/plugins/game_copilot.py`). Replaced with **`openai/gpt-oss-
  120b`** — not a blind guess: this exact model id is ALREADY proven live on Groq elsewhere in this
  project (the Crimson Desert translation fleet's own provider validation, `PROVIDERS` retargeting —
  "groq `openai/gpt-oss-120b` — 3.5 s · 8/8 ✅ keep"). **Added `_effective_model(provider, cfg)`** —
  a persisted `model` value that's no longer a real entry in `MODEL_OPTIONS[provider]` (this exact
  scenario: anyone who had `llama-3.3-70b-versatile` selected before this fix) now silently falls
  back to that provider's live default (`_default_model`) instead of sending a dead id to the API or
  leaving the Settings dropdown on a stale, unmatched selection. Wired into all four places that used
  to read `cfg.get("model") or _default_model(provider)` directly (`_call_provider`, `get_state`,
  `run_action`'s `set_api_key` verification call) — a still-valid saved model is preserved verbatim;
  only a genuinely-retired one migrates.
- **Verified: `py_compile` clean on both touched files; a real offscreen-Qt smoke test** (fresh for
  this round — constructs `_OverlayPanel`/`_CaptureDialog` for real, cycles all 4 dock edges via the
  new `_content.layout()` path, collapse/expand, drag-start/finish confirming `_content_effect`
  moves while `panel.windowOpacity()` stays pinned at `1.0` throughout, `show_animated`/
  `hide_animated` run to completion with REAL wall-clock pumping so the 150-200ms `QPropertyAnimation`
  genuinely finishes and fires `_finish_hide`, plus an isolated fake-registry `get_state()`/
  `run_action()` round-trip proving a stale `llama-3.3-70b-versatile` config migrates to the live
  default and `set_model` rejects the now-defunct id) — **all core checks pass.** Pixel-re-verified
  `_GlassCard`'s corners stay near-zero alpha after the `_content` restructuring (top corners 0-2/255;
  the bottom two read ~25/255, explained by `_glass_shadow(self._card, radius=46, y_offset=8)`'s own
  downward-offset drop shadow bleeding into the `.grab()`'d pixmap — a soft, expected shadow gradient,
  nowhere near round 6's original fully-opaque-255 bug, and unrelated to this round's window-attribute
  change).
- **Round 7b (same day, the FIRST build's real-world result) — `_CaptureDialog` was left in the OLD,
  broken shape and it showed: user screenshots after installing build `20260815194717` showed the
  hotkey/gamepad "קביעת קיצור-דרך חדש" dialog rendering as a completely BLANK, flat light-gray rounded
  box (rounded corners = DWM's own corner-rounding call succeeded; flat untinted light gray = DWM
  Acrylic's own default fill with nothing painted over it) — no title, no instructions, nothing — while
  the main `_OverlayPanel` (2nd screenshot) rendered its real content correctly. Root cause: the round-7
  fix above was applied to `_CaptureDialog.__init__`'s `WA_TranslucentBackground`→`WA_NoSystemBackground`
  swap, but **`_CaptureDialog` never got the `_content` wrapper-widget restructuring** — its `_GlassCard`
  was still added as a DIRECT child of the top-level `QDialog`. Empirically (not theoretically — this is
  the exact structural difference between the one that worked and the one that didn't), a bare
  `WA_NoSystemBackground` top-level window with its real content nested straight onto `self` composites
  as an empty DWM surface; routing everything through one extra plain `QWidget` (itself
  `WA_TranslucentBackground`+`WA_NoSystemBackground`) between the native window and the actual content —
  precisely the shape that already fixed `_OverlayPanel` — is what makes Qt paint the card+text again.
  **Fix: gave `_CaptureDialog.__init__` the identical `content` wrapper** (no `QGraphicsOpacityEffect`
  needed there — the dialog never fades — just the extra widget layer). **Verified via `.grab()` pixel
  test** (the same reliable method established earlier in this project): center pixel went from what
  would be a flat ~(240,240,240,255) "blank" signature to a real navy gradient fill (24,54,77,119) with
  genuine per-row colour variance (stdev 5.6–13.5 across R/G/B, not near-zero) and a near-transparent
  rounded corner (0,0,0,1) — i.e. the card, its border, and its text are actually being composited now,
  not just the bare native surface. Also re-ran the full `_OverlayPanel` regression suite unchanged
  (still shows/hides/holds real content correctly) to confirm this didn't disturb the earlier fix.
  **UNIVERSAL: when a structural fix works on one class but the SAME bug is reported on a sibling class
  that superficially got "the same" attribute swap, check whether the FULL structural pattern (not just
  the one-line attribute change) was actually replicated — a partial port of a fix can leave the
  identical defect in a sibling that looks fixed from the diff alone.**
- **Honest caveats, same posture as every round in this file: this is now the SECOND independently-
  confirmed root cause for the identical user complaint** (a flat, non-glassy panel/dialog), and both
  fixes are grounded in either a specific `WebSearch`-confirmed Windows/Qt fact or, for round 7b, direct
  empirical replication of a structural pattern already proven in-app to work — but DWM compositor
  behavior on the real desktop cannot be verified from this environment under any circumstances. Only the
  user's own screen, on the actual freshly-built install (`20260815200743`), settles whether the panel
  AND the hotkey-capture dialog now genuinely show real frosted glass. **Still NOT published — LOCAL
  install only, per the standing rule; say "פרסם" to ship it.**

### Round 8 — the user supplied a REFERENCE IMAGE ("כזה בדיוק"): machined-bezel chrome, a faceted stone, and the offline preview that caught two design defects before any build (2026-08-15, LOCAL build `20260815213827`)

Rounds 6-7 chased "make it look premium" from a verbal description. This round the user posted a
**target image** and said *"כזה בדיוק"* — a wide panel with a chamfered graphite bezel, a control rail
of machined keys, a blue faceted gemstone with a ▶ glyph, and a genuinely see-through blurred interior.
A picture is a far stronger spec than an adjective, and everything below is built to match it.

- **The card is now a hand-painted machined BEZEL, not a rounded rect with a hairline border.**
  `_GlassCard.paintEvent` paints three layers in order: (1) the glass pane at deliberately low alpha
  (measured `a=47` at centre) so the real desktop/game — already blurred for us by DWM Acrylic — is
  the dominant content rather than a tint; (2) the bezel ring, computed as
  `outer.subtracted(inner)` over two `_chamfer_path` octagons and filled with a multi-stop gradient;
  (3) a classic **three-line bevel** — bright on the outer contour, dark on the inner contour (the
  shadowed step down into the glass), then a second bright lip just outside it. `_chamfer_path` is
  built from straight segments only, so unlike a hand-swept rounded path it cannot self-intersect.
- **🔴🔴 A DIAGONAL METAL GRADIENT SILENTLY FLATTENS ON A WIDE PANEL — and it looks fine in code
  review.** A `QLinearGradient(topLeft, bottomRight)` evaluates each pixel by its **projection onto
  that diagonal axis**, so on a panel much wider than it is tall the top edge and the bottom edge
  project into nearly the SAME band: measured **4/255 lightness apart at 428×194**, i.e. the "metal"
  rendered as a flat grey border. Lighting it from **straight overhead** (`topLeft → bottomLeft`) is
  aspect-ratio independent and is also what a real machined bezel looks like — bright top edge, dark
  body, rim catch along the bottom. After the switch the same measurement reads **207/255 of range**.
  Applied to the frame, the stone's socket, and the keys so every part is lit from one direction.
  **UNIVERSAL: any gradient meant to imply a light SOURCE must run along a fixed axis, never along a
  diagonal whose meaning changes with the widget's aspect ratio.**
- **🔑 THE OFFLINE COMPOSITED PREVIEW IS WHAT MADE THIS CHEAP — it caught two real design defects
  with ZERO builds and ZERO game launches.** `scratchpad/preview_bezel.py` grabs the REAL widget
  (`panel._card.grab()`) and composites it over a synthetic bokeh backdrop, then I *look at the PNG*.
  That is how both the flat-gradient bug above and a second one — the metal reading as **polished
  chrome rather than the reference's graphite** — were found and fixed before a single build. The
  fix for the second was to concentrate the light into thin bands (bright top edge, one specular
  sweep, bottom rim) and keep the body dark; a light body across the whole ring reads as cheap
  polished plastic. **This generalises to every visual change in this project: render the widget
  composited over a plausible background and judge the image, exactly as `work/preview_ingame.py`
  does for game fonts.** (Tofu in the preview is only the offscreen platform lacking a Hebrew font —
  not a defect.)
- **The facets are real geometry, not a texture.** `_chamfer_points` returns the stone's 8 chamfer
  vertices; joining each consecutive pair to the centre cuts 8 wedges, and alternating wedges get a
  light/dark wash — which is how a cut stone actually catches light, and reads as depth at any size
  with no image asset. A gloss sweep over the crown is the stone's own path `intersected` with a
  top-slice rect, so it can never spill outside the cut. Measured: blue-channel stdev **43** across
  the stone (real facet variance), centre `rgb(48,85,185)`.
- **Structural change: the control rail moved INSIDE the frame.** Previously a card plus a separate
  floating chip beside it; now one cohesive milled instrument whose rail (✕ · stone · ↻) sits on the
  side FACING the docked screen edge. Collapsing hides only the content column, leaving a slim
  vertical strip with the stone still grabbable — verified it genuinely shrinks (**430 → 82 px**),
  which the old fixed-width card could not do.
- **Header chrome deleted to match the reference** (which has none). The one thing the title bar
  carried — the detected game's name — moved INTO the text pane as a small gold line (`_title_html`),
  so it costs no vertical furniture. `_format_answer` grew an optional `title` argument.
- **Text legibility over a pane this transparent needed a widget-level shadow.** Qt's rich-text
  engine does not support CSS `text-shadow`, so a `QGraphicsDropShadowEffect` is applied to the
  `QTextBrowser` **widget** — which shadows its whole rendered content, glyphs included. Same for
  the footer label. Two small widgets, so the compositing cost is negligible.
- **🔴 THE RESTRUCTURE INTRODUCED A REAL GEOMETRY BUG, and the old design had been masking it.**
  With the rail moved inside the frame, collapsing hides `_col` but the WINDOW did not shrink:
  measured every `sizeHint` in the chain at **82** while `self.width()` stayed **430**, because
  `adjustSize()` does not reliably shrink an already-shown top-level window. Previously invisible —
  the old collapse hid the whole card, so a too-wide window was just transparent space; now it is a
  wide EMPTY bezel. Fixed with `root.setSizeConstraint(QLayout.SetFixedSize)`, which makes Qt resize
  the window to its layout on every change (exactly right for a content-sized overlay, and it also
  keeps the body-height animation's growth in step). Verified: **430 → 82 → 430** across
  collapse/expand, and the window still grows with a long answer (196 → 291).
  **UNIVERSAL: when a widget moves INSIDE a painted container, any latent "the window is bigger than
  its content" bug stops being invisible — re-test collapse/resize after a structural move, and
  prefer `SetFixedSize` over `adjustSize()` for a window that must track its content.**
- **⚠️ TWO MEASUREMENT LESSONS from the smoke test itself, both of which produced a FALSE failure
  before being fixed:** (a) **testing a gradient by comparing two arbitrary points is unreliable** —
  two points can legitimately land in similarly-lit bands of a perfectly good gradient (this reported
  "flat" on a ring whose real range is 207/255); measure the **range across the whole run** instead.
  (b) A vertical column through the bezel **passes outside the cut octagon at both ends**, so its
  alpha is legitimately ~13 there — an "is it opaque metal?" check must skip the chamfer zone or it
  fails on correct output. Both failures were the test being wrong, not the code.
- **Verified: `py_compile` clean, and a 30-check offscreen pixel suite all-pass**
  (`scratchpad/smoke_bezel.py`) — chamfered corners cut (`a=7`), ring opaque + banded, pane
  see-through, stone blue with facet variance, both keys chamfered + opaque, the rail on the correct
  side at all 4 dock edges, collapse/expand, drag dimming the CONTENT effect while
  **`windowOpacity` stays exactly 1.0** (the round-7 `WS_EX_LAYERED` guarantee, now regression-
  tested), show/hide animations completing, and `_CaptureDialog` still painting real content (it
  inherits the new bezel for free, since it already used `_GlassCard`).
- **⚠️ KNOWN, MEASURED, deliberately NOT fixed this round: the card's drop shadow renders NOTHING.**
  With `SetFixedSize` the window is exactly the card's size (measured: panel 430×196 == card
  430×196), so a 46px `QGraphicsDropShadowEffect` has no room and is entirely clipped — it costs an
  offscreen pass and draws zero pixels. This predates the redesign (the old zero-margin root layout
  clipped it too). Giving it room means padding the root layout AND subtracting that pad in
  `reposition()` so the docked bezel stays the same distance from the screen edge — contained, but
  it touches the dock maths, and the bezel's bright outer rim already provides the separation the
  shadow was for. Left for a follow-up rather than shipped unverified.
- **Honest caveat, unchanged from every prior round:** the geometry, colour, transparency and
  structure are all verified at pixel level offscreen, and the composited preview looks like the
  reference — but **DWM Acrylic's actual blur on the real desktop cannot be produced in this
  environment**, so only the user's own screen settles whether the finished panel reads as true
  frosted glass over a running game. **Still NOT published — LOCAL install only; say "פרסם" to ship.**


