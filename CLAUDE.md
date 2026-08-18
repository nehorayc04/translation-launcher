# Translation Launcher — Project Index

A Windows desktop launcher (Eel/Qt + React frontend) for Hebrew game-translation mods, plus the
per-game translation pipelines that produce those mods, plus a public website/hub (separate repo,
`website/`) and a Cloudflare-Worker/Supabase backend. Every game/software title, every launcher
subsystem, and every reusable engineering lesson has its own file under `docs/context/` — **this
root file is deliberately thin** so it costs almost nothing to load on every message. Everything
below it is loaded ONLY on demand.

## How to work in this repo

1. **General conduct** (git safety, destructive-action confirmation, code style, communication
   style) is governed by the system prompt and by the user's global `~/.claude/CLAUDE.md` — both
   are already injected every session; nothing here duplicates them.
2. **Standing rules that apply to EVERY translation/task in this repo** (the IRON RULE plain-hyphen
   rule, delegate-all-translation, local-build-only publishing gate, mod pricing default, etc.) —
   read **[`docs/context/standing-rules.md`](docs/context/standing-rules.md)** before starting any
   translation, build, or publish action. It is short; read it whenever the task touches a game mod,
   a launcher build, or a publish step.
3. **The `orchestration/` control plane** (multi-agent task board, if the user references it) —
   see [`docs/context/orchestration.md`](docs/context/orchestration.md).
4. **A separate, persistent cross-session memory system** already exists at
   `~/.claude/projects/<this-project>/memory/` (indexed by `MEMORY.md`, auto-loaded by the global
   instructions) — it holds reusable engineering lessons, user feedback, and standing preferences
   that are NOT specific to this repo's file layout. It is complementary to, not a duplicate of,
   the files below.
5. **📘 THE reusable cross-game engineering reference** —
   [`docs/context/playbook.md`](docs/context/playbook.md) — distills every hard-won lesson from
   every game worked on so far (container/codec reverse-engineering method, RTL/bidi engine
   classes, font-injection rules, deploy patterns, fleet/QA protocols, publish mechanics). **Read
   it whenever starting groundwork on a NEW game or hitting a rendering/deploy/fleet problem that
   might already be solved.**

### Topic-file rule (read this every session, it is the whole point of this split)

> **Read a topic file from `docs/context/` ONLY when the user asks to work on that specific
> topic.** Do not pre-load unrelated topic files "just in case" — that defeats the purpose of the
> split. If the user starts a genuinely NEW project/game/software target, create a new file for it
> under `docs/context/games/<slug>.md` (or the appropriate subfolder) and **update the index below**
> with a one-line pointer. Keep this root file itself lean — new standing rules that apply
> everywhere go into `docs/context/standing-rules.md`, not here.

---

## Index of topic files (`docs/context/`)

### Cross-cutting reference (read on demand, not every session)
| File | What's in it |
|---|---|
| [`standing-rules.md`](docs/context/standing-rules.md) | IRON RULE (plain hyphen), local-build-only publish gate, mod pricing default — read before any translation/build/publish task |
| [`playbook.md`](docs/context/playbook.md) | 🌍 THE universal reusable playbook — container/codec RE method, RTL/bidi classes, font injection, deploy patterns, fleet/QA/publish mechanics (31 sections) |
| [`dev-and-build-reference.md`](docs/context/dev-and-build-reference.md) | Repo layout, dev setup, running locally, building the installer, build-id re-release rule, license |
| [`orchestration.md`](docs/context/orchestration.md) | The `orchestration/` multi-agent control-plane (board/state/rules/handoff files) |
| [`fleet-and-pool-infra.md`](docs/context/fleet-and-pool-infra.md) | Cross-game NIM/community-compute fleet infrastructure, self-hosted pool server migration, dashboard, security hardening |
| [`translation-quality-tooling.md`](docs/context/translation-quality-tooling.md) | Gender/number ambiguity tooling, visual-LQA capture backbone, universal multilang review/translate engine, deterministic localization "brain", translation-memory + context window |
| [`website-notes.md`](docs/context/website-notes.md) | Public website UX/feature notes that aren't launcher-specific |
| [`security-audit-2026-07-20.md`](docs/context/security-audit-2026-07-20.md) | Security audit + ACL hardening of this repo (hardcoded creds/deps/output-dir perms/TEMP scoping) |

### Launcher app (`docs/context/launcher/`)
| File | What's in it |
|---|---|
| [`big-launch-and-winhanced.md`](docs/context/launcher/big-launch-and-winhanced.md) | "הפלטפורמה המאוחדת" — Winhanced-inspired Big-Launch console-mode shell (WPF), research + build history |
| [`catalog-and-integration.md`](docs/context/launcher/catalog-and-integration.md) | Bringing games into the launcher catalog (detection, cover art, install flow) |
| [`community-compute-plugin.md`](docs/context/launcher/community-compute-plugin.md) | The Community-Compute (BYOK volunteer-fleet) Android/desktop plugin — design + redesign rounds |
| [`game-copilot-plugin.md`](docs/context/launcher/game-copilot-plugin.md) | The Game Co-Pilot live in-game AI overlay plugin |
| [`plugin-system.md`](docs/context/launcher/plugin-system.md) | The declarative cloud-plugin engine + save-backup plugin (the foundational plugin architecture) |
| [`native-appliers-and-mod-system.md`](docs/context/launcher/native-appliers-and-mod-system.md) | Native mod appliers, server-first mod delivery, offline package builder, in-game language switcher, auto-update |
| [`design-and-ui.md`](docs/context/launcher/design-and-ui.md) | UI/UX redesign rounds — notifications, glass panels, icons, animations, layout |
| [`security-perf-and-audits.md`](docs/context/launcher/security-perf-and-audits.md) | Scenario audits, resilience passes, FPS/perf fixes, security hardening |
| [`community-translate-pool.md`](docs/context/launcher/community-translate-pool.md) | The `/translate` crowdsourced Hebrew-line contribution system |
| [`publish-and-versioning.md`](docs/context/launcher/publish-and-versioning.md) | Version-management system, winget/UniGetUI publishing, telemetry, public beta ship |
| [`bugfixes-misc.md`](docs/context/launcher/bugfixes-misc.md) | Miscellaneous launcher bug fixes not tied to one of the above topics |

### Per-game / per-software translation projects (`docs/context/games/`)
| File | Status (at last write) |
|---|---|
| [`cyberpunk2077.md`](docs/context/games/cyberpunk2077.md) | Shipped — full pipeline, DLC, QA infra (the original/flagship project) |
| [`spiderman2.md`](docs/context/games/spiderman2.md) | Shipped, native applier, RTL/font fixes |
| [`spiderman-remastered.md`](docs/context/games/spiderman-remastered.md) | Mod built COMPLETE but incompatible with the current game exe (v3.618+) |
| [`watchdogs2.md`](docs/context/games/watchdogs2.md) | Shipped |
| [`anno1800.md`](docs/context/games/anno1800.md) | Shipped, purchasable in launcher |
| [`gowr.md`](docs/context/games/gowr.md) | Feasibility GO |
| [`gta5.md`](docs/context/games/gta5.md) | Legacy shipped; Enhanced + Menyoo also covered |
| [`ac2.md`](docs/context/games/ac2.md) | GO |
| [`ac-unity.md`](docs/context/games/ac-unity.md) | 🔴 NO-GO — font gate closed, no reachable font |
| [`ac-shadows.md`](docs/context/games/ac-shadows.md) | 🟡 GO-with-caveats |
| [`ac-blackflag-resynced.md`](docs/context/games/ac-blackflag-resynced.md) | 🟡 GO-with-caveats |
| [`ac-mirage.md`](docs/context/games/ac-mirage.md) | ✅ Phase 1 complete, GO |
| [`ac-odyssey.md`](docs/context/games/ac-odyssey.md) | ✅ Phase 1 complete, GO |
| [`ac-origins.md`](docs/context/games/ac-origins.md) | ✅ Phase 1 complete, GO |
| [`witcher3.md`](docs/context/games/witcher3.md) | Shipped, New-Era fleet work |
| [`rdr2.md`](docs/context/games/rdr2.md) | ✅ Phase 1 complete, GO |
| [`skyrim.md`](docs/context/games/skyrim.md) | ✅ Phase 1 complete, GO |
| [`hogwarts-legacy.md`](docs/context/games/hogwarts-legacy.md) | GO |
| [`plague-tale-requiem.md`](docs/context/games/plague-tale-requiem.md) | Translation + gender-review 100%, mod built local |
| [`tlou.md`](docs/context/games/tlou.md) | Part II — Phase 1 complete, GO |
| [`ghost-of-tsushima.md`](docs/context/games/ghost-of-tsushima.md) | 🟡 GO-with-caveats — font gate |
| [`uncharted-lot.md`](docs/context/games/uncharted-lot.md) | GO |
| [`until-dawn.md`](docs/context/games/until-dawn.md) | Phase 1 complete, GO |
| [`ratchet-clank-rift-apart.md`](docs/context/games/ratchet-clank-rift-apart.md) | GO, medium tier |
| [`corsair-cove.md`](docs/context/games/corsair-cove.md) | ✅ Phase 1 complete, GO |
| [`crimson-desert.md`](docs/context/games/crimson-desert.md) | Phase 2, "דור 3" fleet live |
| [`attack-on-titan-2.md`](docs/context/games/attack-on-titan-2.md) | ✅ Phase 1 complete except font |
| [`007-first-light.md`](docs/context/games/007-first-light.md) | Phase 1 groundwork DONE, GO |
| [`battlefield6.md`](docs/context/games/battlefield6.md) | 🟡 Phase 1 partial, caveats |
| [`farcry5.md`](docs/context/games/farcry5.md) | GO, one open gate (font) |
| [`farcry6.md`](docs/context/games/farcry6.md) | 🟢🟢 All gates closed |
| [`forza-horizon-6.md`](docs/context/games/forza-horizon-6.md) | ✅ Phase 1 complete, GO |
| [`fl-studio.md`](docs/context/games/fl-studio.md) | Phase 1 groundwork DONE, GO |
| [`signalrgb.md`](docs/context/games/signalrgb.md) | Phase 1 complete, GO (software, not a game) |
| [`borderless-gaming.md`](docs/context/games/borderless-gaming.md) | Phase 1 complete, GO (software) |
| [`virtualdj.md`](docs/context/games/virtualdj.md) | Shipped (software) |

---

## Root-level things NOT covered above

If a task involves the `website/` subfolder (its own git repo), read `website/CLAUDE.md` there
directly — it is not part of this split. If a task involves a completely new topic not fitting any
file above, use judgment: extend the closest existing file if it's a natural continuation, or
create a new one under `docs/context/` and add it to the index.
