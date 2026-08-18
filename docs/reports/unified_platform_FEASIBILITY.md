# Unified Platform (Track B) — FEASIBILITY

Go/no-go reasoning per decision and per task. Facts are in `unified_platform_RECON.md`; the
checkable task list this feeds is `unified_platform_PIPELINE.md`. Every item below is an
**independent small bet** — there is deliberately no single all-or-nothing gate for the whole
initiative; C0 through C6 each ship or don't ship on their own merits.

## (A) Audience — verdict: 🟢 GO on a Desktop-Hebrew-first default (reversible)

**Evidence for the default, not a question waiting on the user:**
- `game_detector.py` covers Steam/Ubisoft/Epic/GOG/Rockstar/Xbox/EA/Amazon — every PC storefront,
  **zero** handheld-specific detection anywhere.
- **Zero** TDP/RyzenAdj/PawnIO references in any real `.py` file today (only in the PDF-rendering
  scratchpad scripts used to generate the research docs themselves — not product code).
- The entire UI is Hebrew-RTL and the entire `games/*` corpus is AAA-PC-title localization — that
  IS the product's reason to exist; a handheld-first pivot would be a different product.

Per the project's own Auto-Mode convention ("make the reasonable call, they'll redirect if
needed"), this is **stated as the assumption driving ordering**, not blocked on a question — C0-C4
below are all desktop-relevant regardless, so nothing is wasted if the audience is later widened.
PawnIO/RyzenAdj/TDP work stays fully out of scope for this plan either way, deferred behind a later
explicit Handheld-audience confirmation.

## (B) Stage-0 POC — hypothesis, pass/fail bar, and why WPF over Tauri

**Corrected hypothesis** (see RECON's GPU-compositing correction): NOT "can Python+Web render glass
at all" (already proven yes on decent hardware by the current Qt build) — it's **"does a WebView2
host raise the reliability floor on weak/GPU-blocklisted hardware, where Qt's current toggle/
auto-degrade currently falls back to flat/no-blur."**

**Pass bar**: on at least one weak/older-GPU machine, the WebView2 host renders the SAME frontend
(unmodified) with visibly-blurred glass where the current Qt build on that same machine currently
shows the flat `data-backdrop="none"` fallback — measured via DevTools Performance panel + the
existing `[gpu-probe]` console line, side by side.

**Fail bar**: WebView2 on that weak machine ALSO falls back to software rendering / shows the same
or worse frame timing than the current Qt build's flat-fallback path. If so, Stage 4 (the native
host) loses its strongest justification and should be re-evaluated on other merits only (native
hardware/controller/overlay access, background footprint) rather than "better glass on weak
hardware."

**Scaffold choice: WPF + `Microsoft.Web.WebView2`, not Tauri.** This is a Windows-only tool with no
cross-platform requirement. On Windows, Tauri's `wry` webview backend is ITSELF a WebView2 wrapper
— so a raw WPF host answers the identical rendering-engine question with a fraction of the
toolchain (no Rust/cargo/tauri-cli setup). The .NET-vs-Tauri choice for the EVENTUAL Stage-4 native
host is a separate, later decision about hardware-access ergonomics, footprint, and packaging — it
does not gate this narrow measurement.

**Explicitly out of scope for the POC**: IPC, packaging, install/update logic, any production code
path. It is a disposable single-window prototype; the MEASUREMENT is the deliverable, not the code.

## (C) Stage 1-3 — per-item go/no-go

| Item | Verdict | Why |
|---|---|---|
| **C0** Big Picture Mode ON | ✅ **DONE** (2026-08-16) | Verified `spatialNav.ts`'s focusable queries are fully DOM-generic (no coupling to Sidebar/BigPictureMode's specific structure) and `BigPictureMode.tsx` owns its entire keyboard lifecycle independently (document-level capture-phase handler, `stopImmediatePropagation`) — the only integration point with the generic nav engine is the `nav-back` custom event, a plain listener with no DOM traversal. `Sidebar.tsx` still carries `data-sidebar` intact. The "may have drifted" risk flagged in the plan did not materialize on inspection. Flag flipped `App.tsx:44`, `tsc -b` clean. |
| **C1** Discord Rich Presence | 🟢 GO | Pure-additive: new module, new pref (opt-out default True), no touch to Base 1. Only cost is registering a free Discord Application ID (human operator step, not blocking the code). |
| **C2** Cross-store badge (surface-only) | 🟢 GO, narrow scope | Purely a display of data `game_detector.py` already resolves — `source_launcher` on the payload + a small badge. Explicitly NOT full enumeration (see RECON's limit) — that's real Phase-2 work, sequenced after C3/C4 so newly-discovered titles have somewhere better to land than a blank card. |
| **C3** Cover/hero art | 🟢 GO, establishes a real gap | The genuinely load-bearing item: no API-key storage convention exists yet, and this is the first thing that needs one. Establish git-ignored `.env`/local-JSON per RECON, cache via the existing `resilience.py` atomic-write pattern, degrade to current bundled static art on any failure — zero regression risk even if the external APIs are unreachable. |
| **C4** Price comparison (₪) | 🟢 GO, depends on C3's key convention | Steam's `appdetails` is keyless; IsThereAnyDeal needs a free key via C3's now-established convention. Cataloged titles only, TTL-cached. |
| **C5** Smart Launch Watcher | 🟡 GO, opt-in only | Higher blast-radius than C0-C4 — it manipulates OTHER processes' windows via `SetWinEventHook`, matched against a small JSON pattern list. Ship default **False** (opt-in), not the C1-style opt-out default. A bad pattern match auto-dismissing the wrong dialog is a real, if contained, risk. |
| **C6** Sunshine/mDNS discovery | 🟢 GO, lowest priority | Narrowest audience (only users already self-hosting Sunshine). Launcher-only — browse mDNS, hand off to an already-installed Moonlight via `subprocess`; no streaming code of our own. |

## Legal/ToS checklist — apply to every C0-C6 PR

Before merging any Stage-1-3 change, confirm against `unified_platform_RECON.md`'s legal map:
1. Does it call ONLY 🌍-tier public APIs or orchestrate 🏠-tier self-hostable local tools?
2. Does it avoid touching anything in the 🔒 tier (Winhanced's own servers, UI assets, Smart-
   Profiles dataset, Smart-Launch-Watcher *code*)?
3. Does it avoid auto-claiming a free game under any code path?
4. If it touches OCR/overlay-over-a-game-window at any point (not currently scoped for C0-C6): does
   it gate on a confirmed non-anti-cheat title?

If all four are clean, the change is legally in-bounds for this plan.

## API-key storage convention (established by C3, referenced by C4)

Git-ignored local file, matching the `website/.env` pattern already used elsewhere in this repo —
NOT the `keyring`-based `auth/storage.py` mechanism (that's for per-user secrets; these are shared
app-level public keys). First concrete instance: `translation_manager/art_fetch.py` reads a
`.env`/local-JSON holding the SteamGridDB + IGDB keys; `price_lookup.py` (C4) reuses the same file
for the IsThereAnyDeal key.
