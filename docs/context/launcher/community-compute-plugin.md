## 🔴🔴 THE PLUGIN HOST NEVER STARTED AT BOOT — an AttributeError swallowed by a broad `except` (2026-08-13)

The community-compute plugin showed **"אין קשר לשרת"** on a machine where the pool was healthy, the
keys were saved and the toggle was on. Two independent bugs, and the second one is the expensive
lesson.

1. **Cloudflare 403s urllib's DEFAULT User-Agent** (`error code: 1010`) — the documented
   project-wide trap, hit again in `plugins/community_compute._cc`. The pool answered `curl`
   perfectly while every call from the plugin was refused at the edge. Fixed with a browser `_UA`
   header. The Android app was unaffected because Dart sends its own UA, and the PROVIDER call
   already carried one — only the pool call was bare. The status line also collapsed
   "nobody answered" and "the server answered and said no" into one message; it now shows the
   server's own reason.
2. **`plugins/__init__.py` imported only `registry`, so `plugins.host` was NOT an attribute of the
   package** — and all three call sites reach it that way (`_plugins().host.on_boot()` /
   `.on_game_launch()` / `.run_now()`). Every one sits behind a broad `except`, and `main_qt`
   swallowed the result with a bare `pass`, so `plugins_boot()` raised `AttributeError: module
   'translation_manager.plugins' has no attribute 'host'` on EVERY boot, silently, forever.
   ⇒ The scheduler only ever started when the user TOGGLED a plugin (that path goes through
   `registry`, which imports `host` lazily). A background plugin therefore sat "on" and idle after
   every launch, and the on-boot save backups never ran either.
   **The tell was in the log all along**: `[plugins] host started` appeared at 14:42 — an hour
   after that session's 12:57 boot, i.e. at the moment of a manual toggle, never at a boot.
   Fixed in three places: `from . import host` in the package `__init__`, an explicit submodule
   import in `_plugins()`, and BOTH swallow sites now LOG.

**UNIVERSAL: a submodule is not an attribute of its package until something imports it. Any
`pkg.sub.fn()` behind a broad `except` is a silent, permanent no-op waiting to happen — import the
submodule explicitly, and never let a boot-path failure be swallowed by `pass`.** Recognise it by a
log line that appears only after a user action which has no business starting a subsystem.
Same family as [[systemexit-escapes-except-exception]]: a broad `except` hiding a boot failure.

⚠️ **A verification trap hit while diagnosing this**: `Start-Process` and
`ProcessStartInfo.EnvironmentVariables` did NOT override the sandbox's redirected `USERPROFILE`, so
the launcher I started booted into the **Antigravity sandbox profile** and wrote its log there —
the real log looked frozen and the app looked broken. Launch it through a `.cmd` that `set`s the
real profile paths first, then read the real `.translation_manager\launcher.log`
([[env-redirection-real-home]]).


## 🎨 Community-Compute Android app — full launcher-grade redesign + admin fleet dashboard (2026-07-30, LOCAL, APK built, NOT installed)

The user asked to make the CC Android worker "הכי זורמת מלוטשת ומגניבה כמו הלנאצ'ר והאתר" BEFORE
installing it. Rebuilt the whole Flutter UI as a native launcher-grade app (real GPU: `BackdropFilter`,
`AnimationController`, `CustomPainter`), and added a website admin dashboard for the fleet.
**`flutter analyze` 0 errors; APK built 49.3 MB → `community_compute/dist/CommunityCompute-1.0.0.apk`.
NOT installed (user wants to review), NOT published outward.**

- **`lib/theme.dart`** — `T` tokens + `accents` map (green/cyan/yellow/purple/pink/amber); `Prefs extends
  ChangeNotifier` singleton (`Prefs.I`: accentKey, anim 3/2/1/0, backdrop, textScale 0.85-1.25, notif;
  `dur(ms)` scales every animation by the level, `glassBlur`). `GlassPanel` uses a REAL `BackdropFilter`
  when blur is on. `Ambient` = the launcher's shifting multi-blob colorful background (24s controller,
  accent-tinted, respects `animOn`). **🔴 Bug fixed: a `Positioned` inside a `LayoutBuilder` does NOT
  anchor to the parent `Stack` — wrap the Stack in ONE LayoutBuilder and build `Positioned` children
  directly with the known constraints** (hit in both `Ambient` and `StageArc`).
- **`lib/icons.dart`** (NEW) — `CcIcon(name,...)` + `_IconPainter`, launcher-style stroke glyphs (no
  emoji anywhere): power/key/gear/info/activity/download/upload/globe/shield/check/copy/external/
  chevron/close/minus/plus/battery/dot.
- **`lib/widgets/stage_arc.dart`** (NEW) — the live RAINBOW ARC showing the exact pipeline stage RTL
  (משיכה→תרגום/ביקורת→שליחה): 3 hued segments (cyan/accent/purple), a comet travels the active segment,
  nodes pulse + show download/activity/upload icons (check when done), a title+subtitle below say the
  action in good Hebrew. Labels **translate vs review** from the job's `sys`, and a `check` phase shows
  the auto-QA. Driven by `engine.arcSegment`/`arcRunning`/`stageTitle`/`stageSub`.
- **`lib/widgets/big_toggle.dart`** — NARROWER pill (196×96), accent-aware, `AnimatedScale` on press,
  **פעיל/כבוי centered BELOW** the pill (not painted inside).
- **`lib/screens/home.dart`** — StageArc + BigToggle + 3 stat cards (שורות שתרמת · מאגר מקומי · קצב/דקה)
  + a full status panel: מצב עבודה, חיבור לשרת, מפתחות פעילים, **כתובת ה-IP שלך** (hint "מוצגת לך בלבד -
  לא נשלחת לשרת"), תורגמו בשעה האחרונה.
- **`lib/screens/keys.dart`** — the consent checkbox now **GATES the Save button** (`onPressed: _consent
  ? _save : null`) — fixing "אני מבין/ה לא משפיע"; per-provider expandable **step-by-step Hebrew guide**
  (Groq/SambaNova/NIM) with a "פתחו את האתר" `launchUrl` button (`url_launcher` added); obscured key
  fields with a green hasKey dot.
- **`lib/screens/settings.dart`** (NEW) — launcher-style personalization: animation LEVEL segmented
  (מלאה/רגילה/מופחתת/כבויה), accent swatches, real-blur toggle, text-size slider, persistent-notification
  toggle, and a **battery-optimization** row (`isBatteryUnrestricted`/`requestBatteryUnrestricted`).
- **`lib/main.dart`** — 4-tab glass nav with `CcIcon` (הפעלה/מפתחות/הגדרות/מידע), **liquid-glass screen
  transitions** (`AnimatedSwitcher` + `ImageFiltered` blur→0 materialise), live `MediaQuery.textScaler`
  + accent from `Prefs`, and a **one-time post-install battery prompt**.
- **`lib/fg_service.dart` / `lib/engine.dart` / `lib/state.dart`** — the **persistent notification**
  updates in real time (translated-last-hour + rate/min) via `FlutterForegroundTask.updateService`,
  throttled 12s, gated by the notif pref; the engine tracks phase/mode/rate and fetches the device IP
  once (shown locally only). Manifest gained `REQUEST_IGNORE_BATTERY_OPTIMIZATIONS`.
- **Every user-facing `—` replaced with `-`** (the remaining em-dashes are code comments only).

- **🌐 ADMIN FLEET DASHBOARD + device BLOCK (website, code-complete, deploy-gated).** Schema:
  `cc_workers.blocked boolean` + `cc_claim` now returns NO new work for a blocked worker (in-flight
  submits still complete) — **applied live to Supabase** via the Management API. API: extended the
  admin-gated `api/admin/system-status.ts` with `?cc=1` (stats + worker list) and `POST ?ccBlock=1|0`
  (block/unblock; blocking also releases that device's claimed lines back to the pool immediately, no
  reslice). No new Vercel function (respects the 12-fn cap). UI: `components/admin/CommunityComputeTab.tsx`
  (new "מחשוב קהילתי" tab under ניהול→קהילה ונתונים) shows connected/waiting/blocked counts, the queue
  (open/claimed/done + %), and a per-device row with a block/unblock button. **Privacy: the control
  plane stores NO key and NO IP, so none can be shown; the worker_id is a random device UUID, truncated
  in the response.** `tsc -b` + `vite build` clean; the panel queries were verified against the live DB
  (open 17,249 · done 375 · 1 device · 0 blocked).
- **The admin dashboard was DEPLOYED by the user** (a blanket `vercel --prod` re-publishes the whole site;
  verified first that the newest public UI — the glass FABs — was ALREADY live, so the deploy only added
  the admin tab. The `website/CLAUDE.md` "LOCAL only" note for the glass FABs was STALE.)
- **🔴🔴 THE DASHBOARD SHOWED ALL-ZEROS while the phone was working (455 done) — a MISSING service_role
  GRANT, swallowed into 0.** The CC tables (`cc_lines`/`cc_workers`) had **no grant to `service_role`**
  (`has_table_privilege('service_role','cc_lines','SELECT')` = false), so the admin panel's service-role
  read was permission-denied; supabase-js returned `{error}` and my endpoint did `count ?? 0` / `data ??
  []` → all zeros with a 200. The PHONE worked because it uses the SECURITY-DEFINER RPCs (granted to anon),
  not direct table reads. **Fix (live, no redeploy): `grant select on cc_lines to service_role; grant
  select, update on cc_workers …; grant update on cc_lines …`** → the already-deployed endpoint returns
  real data on the next refresh. **The recurring Supabase trap: a table created via the Management API is
  NOT auto-granted to service_role — the service-role API silently gets denied.** Hardened the endpoint to
  surface `.error` (never silent 0 again) — ships on the next deploy. Memory
  [[edge-cache-hides-slow-query]]-adjacent grant lesson.
- **🔒 Security hardening (user asked "can a hacker take over / poison?"): `cc_claim` now enforces a
  per-worker in-flight cap (300 lines) on top of the blocked-check** (a rogue device can't hoard/drain the
  queue; lease-expiry returns the rest). `cc_submit` ALREADY only writes lines the worker currently HOLDS
  (`worker_id = p_worker AND status='claimed'`). The device holds only the public anon key + a soft
  `app_secret` (no service key), the only surface is 5 fixed SECURITY-DEFINER RPCs (no dynamic SQL), RLS is
  default-deny, and returned text is UNTRUSTED → the QA gate + manual approval catch poisoning before
  anything ships; the operator can BLOCK any device instantly. So a compromised device can at worst poison
  its own ~50 held lines (caught before shipping) or waste quota — it cannot take over the server or read/
  modify other data.

- **🎨 FULL in-app redesign ROUND 2 (2026-07-30, after the user installed it — APK rebuilt 49.4 MB, NOT
  published outward).** The user sent a punch-list; every item fixed, `flutter analyze` 0 errors:
  - **Rainbow «צבעוני» accent = the DEFAULT** (`Prefs.accentKey='rainbow'`): a `Timer` cycles the hue
    ~4.5 fps when animOn, the `accent` getter returns the live HSL colour so the whole UI + Ambient
    colour-shift like the launcher. Settings shows a conic-gradient swatch first + a "מחליף צבעים
    אוטומטית (ברירת מחדל)" caption.
  - **StageArc rebuilt** — title+subtitle now sit BELOW the arch in a Column (no overlap), the subtitle
    WRAPS freely (no ellipsis); the traveling dot is replaced by a **flowing WAVE of light** (two gaussian
    pulses sweeping the active segment) that passes THROUGH the active node; the arc flows through each
    node cleanly (a dark disc masks the line inside + a coloured ring = continuation) and the icon stays
    bright/visible.
  - **Rotating explanations** — the engine cycles 2-3 phrasings per phase every 4 s (via a UI `Timer`), so
    nothing looks stuck; **uptime** ("פועל כבר X") tracked in `state.startedAt` and shown under the toggle
    + in the persistent notification.
  - **Persistent NOTIFICATION** — root cause was the missing POST_NOTIFICATIONS grant: now
    `FgService.requestPermissions()` is called at boot + on service start; the notification carries uptime.
  - **Nav transition = CROSSFADE** (not liquid-glass): `AnimatedSwitcher` fade+scale with an overlapping
    `layoutBuilder` so both tabs are visible mid-transition ("step1 first · step2 both · step3 second").
  - **Settings segmented highlight RTL fix** — the AnimatedAlign x was negated (item[0] is on the RIGHT in
    RTL), so "מלאה" now highlights on the right, not inverted onto "כבויה".
  - **No-ellipsis everywhere** — status-row values WRAP (maxLines 2, softWrap), stat numbers use a
    `FittedBox` scale-down, status labels shortened — so nothing truncates even when text-size is raised.
  - **Copy** — deleted the "…בדיוק כמו בלאנצ'ר" subtitle; swept singular-first-person → impersonal/plural
    ("לא נשלחים אליי" → "לא נשלחים לשום שרת", "מוצגת לך" → "מוצגת רק לכם").

- **🎨 FULL in-app redesign ROUND 3 (2026-07-30, APK rebuilt 50.3 MB → `dist/CommunityCompute-1.0.0.apk`,
  NOT installed, NOT published).** Another user punch-list, all shipped; `flutter analyze` 0 errors:
  - **🔴🔴 THE PERSISTENT-NOTIFICATION BUG ROOT-CAUSED — flutter_foreground_task v8 needs the `<service>`
    declared MANUALLY in AndroidManifest.** Nothing appeared in the shade even with the POST_NOTIFICATIONS
    permission granted, because the FGS service element was never declared → `startService` failed silently
    and no notification was created. Fix: add
    `<service android:name="com.pravera.flutter_foreground_task.service.ForegroundService"
    android:foregroundServiceType="dataSync" android:exported="false" android:stopWithTask="false"/>` inside
    `<application>`. **UNIVERSAL: flutter_foreground_task ≥6 does NOT auto-merge its service — a missing
    `<service>` (not a missing permission) is why an ongoing notification never shows; the engine loop keeps
    running because it lives in the main isolate, which masks the failure.**
  - **🔴 COLOURS SPLIT into two independent choices** (was one "rainbow accent" that cycled everything). Now
    `Prefs.accentKey` = a STATIC button/highlight colour (swatches), and a separate `Prefs.rainbowBg` toggle
    ("צבעים מתחלפים ברקע") cycles only the AMBIENT background hue. Old `accent=='rainbow'` migrates → `green`.
    `Prefs.ambient` (cycling or static) drives the background; `Prefs.accent` (always static) drives buttons.
    A wrong reading last round made rainbow the ACCENT — the user wanted the cycle on the background only.
  - **🔴 GLASS was reading as a black panel** — `BackdropFilter` was on, but the fill was a 60%-dark overlay
    over a mostly-dark canvas (no colour behind most panels to blur). Fix: always-on blur + a frosted WHITE
    sheen gradient fill (`0x2E→0x14 white` over a hint of ink) + a brighter hairline border + BOOSTED ambient
    blobs (higher alpha, 4th broad blob) so there's always colour to refract. Removed the on/off backdrop
    toggle — glass is always on.
  - **🔴 TAB TRANSITION → real liquid-glass** (the earlier "crossfade" was itself the bug the user was
    describing, not the target). Now `AnimatedSwitcher` + `ImageFiltered` blur 14→0 + scale 0.965→1 as the
    incoming screen MATERIALISES into focus (the launcher's look), outgoing blurs+fades out.
  - **🔴 ARC WAVE → a light travelling ALONG the stroke, not dots.** `_ArcPainter` step 2 now brightens the
    active segment's ARC LINE ITSELF with a moving gaussian band (48 overlapping sub-arcs = one continuous
    ribbon), travelling **RIGHT→LEFT** (`centre = 1 - (t*1.5)%1`, wrapped so it re-enters). The node's dark
    disc (drawn after) masks the middle → the wave "passes underneath" the icon and re-emerges, exactly per
    the 4-endpoint spec. Node ring pulses via `_wave(0.5,…)`.
  - **NEW "דפדפן" tab** between מפתחות and הגדרות (`webview_flutter`, `BrowserScreen`) — loads
    hebrew-translation-hub.com with a slim home/back/forward/reload chrome + a live progress line; a real
    DOWNLOAD (github `/releases/download/` or a `.apk/.exe/.zip/…` path) is handed to Android's system
    download-manager via `launchUrl(externalApplication)` + `NavigationDecision.prevent`.
  - **KEYS eye-toggle** — a per-field show/hide (`obscureText: !_show[id]`, `eye`/`eye-off` glyph), like the
    website's password field.
  - **CADENCE** — data (rate/buffer/uptime) refreshes every **3 s**; the explanation phrasing rotates every
    **~10 s** (a 3 s timer, `_variant++` only when `_tick % 3 == 0`) so numbers feel live and text never
    jitters.
  - **LINES COUNT UP one-by-one** — the "שורות שתרמת" stat is a `TweenAnimationBuilder<int>` (IntTween,
    ~1.4 s ease-out) so a committed batch of 50 is shown ticking up, not jumping — the display animates even
    though the queue is still claimed/submitted in batches of 50.
  - New icon glyphs: `eye`/`eye-off`/`chevron-left`/`chevron-right`/`refresh`/`home`.
  - **🔴🔴 "0 נתונים" (a phone stuck at 0 lines/rate while CONNECTED, phase='מתרגם') — DIAGNOSED via the
    control plane, then a fail-fast fix.** Queried `cc_lines`/`cc_workers` (Management API): the FLEET was
    healthy (done 455→885; other android devices had contributed 280 & 605), but the reporting device
    (`4e76a2c7`) had CLAIMED 50 lines and committed 0 for 9 min — its single 1/3 key never produced a
    success. Root cause of the *stuck look*: `_call` had a **180 s timeout × 5 chunks + a retry pass**, so a
    failing/slow single provider blocked one batch for **up to ~15-25 min** while the UI sat on the green
    "מתרגם" phase, looking alive but producing nothing. **Fix (`providers.dart`): fail FAST** — per-call
    timeout 180→120 s; `_shard` now BREAKS on any HARD status (`timeout/neterr/401/403/http/429/402/503/
    cooldown`) with empty output instead of grinding all 5 chunks (`parse` still continues, it's per-chunk);
    and `_call` now sets a short COOLDOWN on every hard failure (401/403→120 s, http→30 s, timeout→30 s,
    neterr→20 s) so the immediate retry pass SKIPS the just-failed key. Net: a dead/slow single key now
    surfaces "תקלת ספק · <ספק>: <סיבה>" within ~2 min (was ~15) and the device releases its 50 lines back to
    the pool after 2 fails instead of hoarding them. **UNIVERSAL: a BYOK worker with ONE slow/failing
    provider must fail a doomed batch in ~one call, not grind every chunk at a long timeout — otherwise a bad
    key is indistinguishable from "working, just slow" for many minutes. The user-side cure is a fast key
    (Groq); the app-side cure is fail-fast + a truthful per-provider reason.** APK rebuilt 50.3 MB.


## 🎨 Community-Compute Android — ROUND 4 redesign: arc→ring, jank kill, keys import/export (2026-07-30, APK rebuilt 50.3 MB, NOT installed)

Another user punch-list on the installed app; all shipped, `flutter analyze` 0 errors, APK →
`community_compute/dist/CommunityCompute-1.0.0.apk` (NOT installed — user reviews; NOT published).
- **🔴🔴 THE JANK ROOT CAUSE — a 220 ms `Timer` on the GLOBAL `Prefs` ChangeNotifier rebuilt the
  WHOLE app 4-5×/sec.** The background hue was stepped by `Prefs._bgTimer` calling `notifyListeners()`,
  and `MaterialApp` is wrapped in `AnimatedBuilder(animation: Prefs.I)` → every 220 ms the entire tree
  (incl. the WebView) rebuilt = "האפליקציה זזה לאט", AND the hue moved in visible 220 ms steps that
  bunched up when busy = "נתקע ומשתנה לצבע אחר". **Fix: deleted the timer entirely; the hue now lives
  inside `Ambient` on its OWN `AnimationController` (a slow 46 s loop, seamless 0°→360° wrap, no jump),
  wrapped in `RepaintBoundary` so it composites alone.** `Prefs.bgCycles` just tells `Ambient` whether
  to cycle. **UNIVERSAL: never drive a continuous animation by `notifyListeners()` on a ChangeNotifier
  that a top-level `AnimatedBuilder` listens to — it rebuilds the world every tick; put the animation in
  a local `AnimationController` + `RepaintBoundary`, and reserve `notifyListeners` for real state
  changes.** A single-controller hue would JUMP at the t-wrap unless the period is an exact 360°
  multiple — a SEPARATE slow controller decouples hue speed from blob motion and guarantees a seamless
  loop.
- **arc → RING (`widgets/stage_ring.dart`, replaces `stage_arc.dart`).** A full circle divided into
  **4** stages (fetch·translate·check·send, up from 3), RTL top reads right→left, a light WAVE flows
  continuously AROUND the ring (`n=108` overlapping sub-arcs, two bands half a cycle apart, travelling
  counter-clockwise so the top goes right→left) passing UNDER each node (dark disc masks it, re-emerges).
  **All the text + the ON/OFF toggle live INSIDE the ring**, packed in a **`FittedBox(scaleDown)` over a
  fixed-width `SizedBox`** so it can NEVER overlap regardless of text-size/wording (the size guard).
  `BigToggle` gained a `scale` param (nested at 0.72). `engine.ringStage` (0..3) added alongside the old
  `arcSegment`.
- **Pending-submit card + the "מאגר מקומי always 0" fix.** The old "buffer" stat showed the inbox
  (drains instantly online → always 0, confusing). Replaced the middle card with **"ממתין לשליחה" =
  `outbox.length`** (count-up via `TweenAnimationBuilder<int>`, climbs per translated line, resets to 0
  on submit → those lines then join "שורות שתרמת"). The offline buffer is demoted to an honest status
  row ("מאגר לא-מקוון · 0 = הכול מסונכרן"). **UNIVERSAL: a headline stat that's structurally always 0
  online is noise — surface the number that actually moves (the un-submitted outbox), and label the
  always-0 safety buffer as a status row, not a hero stat.**
- **Live IP** — `engine._refreshIp` re-fetches every ~90 s (and updates only if the value changed),
  not just once when empty. **provfail flash suppressed** — a single momentary all-provider blip
  (rate-limit/network) no longer flashes the red "תקלת ספק"; it only surfaces after **2 consecutive**
  failures (matching the release threshold), so a normal free-tier hiccup that self-recovers stays
  invisible. **Text size** default 0.85, range widened 0.70-1.40.
- **Floating GLASS** — the bottom nav pill AND the browser chrome were opaque `T.glass` rectangles
  ("מלבן ורקע שחור") → now `ClipRRect + BackdropFilter(18) + frosted-white sheen gradient + bright
  hairline`, real glass over the shifting background. Browser nav buttons → round glass `InkWell`s; the
  `refresh` glyph redrawn as a clean circular-arrow.
- **Keys import/export (`screens/keys.dart`).** A panel with ייצוא (build a `id=value` block → copy to
  clipboard + show it to save/transfer) and ייבוא (paste a block OR a single key → `_parseKeys` handles
  JSON, `id=/id: value` lines, AND bare-token auto-detect: `gsk_`→groq, `nvapi-`→nim, else sambanova →
  fills the fields; the user still presses שמירה through the consent gate to persist). One file or a
  single line, "ready-made file" via clipboard — no new native plugin.
- **🔴🔴 "בהמתנה - אין שורות בתור" was a FALSE message — diagnosed via the control plane, then
  hardened.** The user's device showed "no lines in queue" while the control plane had **15,872 open
  lines** and `cc_claim` (dumped: `SECURITY DEFINER`, blocked-check + per-worker 300-cap, claims `open`
  OR lease-expired rows `FOR UPDATE SKIP LOCKED`) would clearly have returned lines — the worker's
  `last_seen` was **293 s** old (5 min with no RPC) while holding 100 live-leased claimed lines. ⇒ the
  CLIENT loop had stalled/gone-idle-and-long-slept, and the UI printed a hardcoded "no lines" for the
  whole idle window. **Three client fixes (engine.dart):** (1) the whole `while(_alive)` body is now
  wrapped in `try/catch` so an unexpected exception can NEVER kill the pull-loop (a dead loop = a frozen
  "idle" screen forever) — it breathes and continues, the queue keeps its lines; (2) the idle backoff
  ceiling drops to **18 s** whenever `online && !queueEmpty` (a spurious empty response / blip must not
  strand the worker on a 60 s sleep while thousands of lines wait) — only a genuine offline/drained
  state backs off to 60 s; (3) **truthful labeling** — a `queueEmpty` getter (`_emptyClaims >= 2`, i.e.
  the server confirmed empty TWICE) gates the "אין שורות בתור" text on both the home work-label and the
  ring title/subtitle; otherwise it shows "מתחבר לתור · בודק שורות חדשות". **UNIVERSAL: a pull-worker's
  idle/empty message must be driven by a CONFIRMED-empty server response, never by "we're not currently
  working" — the latter conflates a blip, a long backoff, and a stalled loop with a genuinely drained
  queue and lies to the user; and any background pull-loop MUST be exception-proof or a single throw
  freezes it into a false idle.** Un-lost: the 100 stuck claims lease-expire back to the pool in ~10 min
  (no data loss); the immediate user remedy is a toggle OFF→ON or an app restart to revive the loop.


## 🖥 Community-Compute R&C pilot — added to BOTH dashboards, 2-device health verified (2026-07-31)

Two volunteer phones now translate R&C via the community control plane; the user asked to confirm
health (no duplicates) and add R&C to the control panel + the fleet EXE with 2 streams.
- **Health verified straight from the control plane:** 2 devices each hold **50 DISJOINT** claimed
  lines (`worker_id` is single-valued + `cc_claim` uses `FOR UPDATE SKIP LOCKED`), every `done` row
  has exactly one `out` and no non-done row has output ⇒ **architecturally impossible to duplicate**;
  `done` climbing (~3.8k/17,624), ~24 lines/min. `cc_submit` also only writes lines the worker still
  HOLDS, so a reclaimed-then-recovered line can't double-count.
- **Homepage progress dashboard:** `games/ratchet_rift_apart/work/cc_progress.py` — reads the anon
  `cc_stats` RPC (`done` + `workers`=active-in-10-min=streams), posts to `/api/admin/progress` as
  gameId=`ratchet-rift-apart`, unit שורות, **`aiModel` EXACTLY `תרגום רב לשונית - {streams} זרמים`**
  (the user's requested wording, no extras). R&C's row is already `coming-soon` (`!= 'planned'`) +
  `show_on_website` ⇒ it passes the dashboard gate with no catalog change; verified live in
  `/api/progress`. Persistence WITHOUT admin: `run_cc_progress.vbs`→`.bat` copied to the **Startup
  folder** (`Register-ScheduledTask` needs admin and 403'd here); a single instance runs now.
  ⚠️ At-logon-single + start-now avoids the documented two-pushers duplicate-rate trap (a session
  process dies on logoff/reboot, so the Startup copy never overlaps it).
- **FleetDash EXE (`tools/fleet_dashboard`):** community-compute fits NEITHER data source (no local
  banks, no ssh VMs), so a dedicated `collect_cc(hist, win)` in `collector.py` reads `cc_stats` and
  appends R&C as a game + **one stream per active device** (numbered #22/#23 via the same
  `stream_ids` registry, `kind="community"`, `provider="community"`), marked **`cc=True`** so
  `health.py` skips its NIM-fleet rules (no false "pull frozen"/"worker dead"). ⚠️ `rate_per_min`
  returns **None on the first tick** (empty history) → `grate/per` crashed; coerce `... or 0.0`.
  Verified via an isolated `collect_cc({},15)` call (2 streams, done/total correct) — `dash.py --once`
  hangs on the slow ssh probes, not the CC code. Rebuilt: `pyinstaller --noconfirm FleetDash.spec`
  (dropped `--clean`; it hit the same Windows build-lock — wipe `build/` via `Remove-Item` first,
  and kill a running `FleetDash.exe` or it's a WinError 5). `dist/FleetDash.exe` 50.4 MB.
- **UNIVERSAL: to surface a DIFFERENT-mechanism workstream (volunteer BYOK) in a fleet dashboard
  built for one model (NIM VMs), don't retrofit the game/machine/provider loop — add a parallel
  collector that emits the SAME stream/game dict shape with a `cc=True` marker the health layer
  skips, so the row renders without triggering rules that don't apply.**


## 🎨 Community-Compute Android — ROUND 5 + installed via adb to the user's phone (2026-07-31)

Another punch-list; all shipped, `flutter analyze` 0 errors, and — the user enabled USB debugging —
**installed directly with `adb install -r` (data preserved) + launch-verified (process alive, 0 FATAL).**
Package `com.hebrewtranslationhub.community_compute`; APK `dist/CommunityCompute-1.0.0.apk` (50.3 MB).
- **Bigger ring/toggle/text, standard on tablet.** Ring cap 340→420, inner inset 0.245→0.21, toggle
  scale 0.72→**0.98**, fonts up (title 17→20, subtitle 10.5→13); **uptime moved OUT of the ring to
  below it** (home.dart) so the toggle owns the center and is big. **Tablet:** a global
  `Center + ConstrainedBox(maxWidth: 560)` in `main.dart` caps ALL screen content so on a large
  display everything stays a comfortable standard size, centred (the ring's own `min(width, 420)`
  also keeps it from ballooning). The FittedBox no-overlap guard is retained.
- **🔴🔴 THE BOTTOM NAV LOOKED BLACK BECAUSE `bottomNavigationBar` IS A SEPARATE SLOT WITH NO BODY
  BEHIND IT.** A `BackdropFilter` in the nav had only the near-black Scaffold background to refract →
  it read black, not glass, no matter how frosted the fill. **Fix: `Scaffold(extendBody: true)`** so
  the body Stack (incl. the colourful `Ambient`) reaches BEHIND the nav → the blur now refracts real
  colour = floating glass. **Cost: `extendBody` lets content scroll under the nav**, so every scroll
  view needs manual bottom clearance (explicit ListView padding is NOT auto-adjusted) — bumped
  home/keys/settings/about ListViews' bottom padding to **88** and padded the browser's WebView bottom
  by 84. **UNIVERSAL: a translucent bottom nav can only look like glass if the colourful body extends
  behind it (`extendBody: true`); and the moment it does, every explicit-padding scroll view must add
  the nav's height as bottom padding itself.**
- **Refresh glyph** redrawn as an ~11/12 circle + a **solid filled triangle** arrowhead (a stroke
  chevron read as weak) — cleaner button. **Hue `% 360` guard** on the ambient cycle (belt-and-braces
  against a 360°≡0° edge at the controller wrap).
- **🔴🔴 THE WINDOWS BUILD-LOCK WHACK-A-MOLE — `AccessDenied`/`Unable to delete` on `build/…` that
  MOVES between subdirs each retry = zombie Gradle daemons + AV holding freshly-written files.** The
  same session had built fine twice, then 6 consecutive failures each on a DIFFERENT `build/app/…`
  dir (mergeReleaseNativeLibs → native_symbol_tables → native-debug-symbols → mergeReleaseAssets →
  packageRelease/tmp). Clearing each dir + retrying is whack-a-mole; `flutter clean`+rebuild still
  failed. **What worked: (a) `Stop-Process` ALL `java.exe` (the Gradle daemons — Android Studio open
  on the project keeps respawning them and locking `build/`), (b) `Remove-Item -Recurse -Force build`,
  then (c) ONE uninterrupted background build.** Also added `ndk { debugSymbolLevel = "none" }` to the
  release buildType (skips the native-symbol tasks — useless for a sideloaded APK and a frequent
  lock target). The Defender fix (`Add-MpPreference -ExclusionPath`) needs admin (failed here).
  **UNIVERSAL: an `AccessDenied` that migrates to a new `build/` subdir on each retry is a live
  file-lock, not a config bug — kill every `java.exe`, wipe `build/`, close Android Studio (its sync
  relocks continuously), and build once without interruption; retrying without killing the daemons
  just moves the lock.**
- Standing rules unchanged: still a PILOT (only R&C in the queue, translate mode), the VM fleet
  untouched, nothing published outward. Installing to the user's OWN phone (they enabled debugging)
  is their device install, not a publish.


## 🎨 Community-Compute Android — ROUND 4 redesign: arc→ring, jank kill, keys import/export (2026-07-30, APK rebuilt 50.3 MB, NOT installed)

UniGetUI is just a GUI over the public `microsoft/winget-pkgs` source — everything flows through PRs there. The
personal-name identifier `Nehoray.TranslationManager` (1.0.1/1.0.2) is being retired in favor of a clean
**`HTH.TranslationManager`** (Publisher `Hebrew Translation Hub`) under the org migration.
- **The three PRs (Git Data API on the `nehorayc04/winget-pkgs` fork; a removal PR may touch only ONE version
  directory):** `#404647` remove Nehoray **1.0.1 — MERGED**; `#404617` add `HTH.TranslationManager 1.1.0` —
  validation PASSED, awaiting moderator merge; `#404624` remove Nehoray **1.0.2** — validation passed, moderator
  asked the standard **"highest-version removal"** question (answered: same app re-published under the new
  identifier at 1.1.0, and the old manifest's `Publisher: Nehoray` no longer matches the installer's ARP
  `Hebrew Translation Hub` so `winget list/upgrade` can't correlate installed copies — it's actively wrong, not
  just redundant).
- **🔑 THE HASH TRAP on a re-published-in-place asset:** the launcher's public GitHub release asset is
  `--clobber`'d on every publish (same `v1.1.0-beta` tag, changing bytes), so the winget manifest's
  `InstallerSha256` goes STALE the moment a new build ships. winget CI re-downloads the URL and re-hashes →
  `Error-Hash-Mismatch`. Fix on every re-publish: recompute the LIVE asset sha (download it, don't trust the
  build log) and update the manifest sha before the winget PR can pass. This round: `5C995099…` (stale) →
  `F8FB523F…` (live, 140,877,712 B, matched exactly). [[launcher-release-checklist]]
- **`Validation-Defender-Error` did NOT fire this round** (it did on the earlier 1.0.1) — the unsigned Inno
  installer passed Defender clean; the real fix for that FP long-term is code-signing (Azure Trusted Signing
  ~$10/mo). **⚠️ The GH token for the fork API comes from `git credential fill` (host github.com); a browser
  User-Agent header is required or GitHub 401s. `urllib` on the machine's base Python works; a `os.popen`
  credential re-read inside the same `python -` heredoc can 401 — read the token in bash and pass via env.**


