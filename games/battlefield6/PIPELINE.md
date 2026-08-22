# Battlefield 6 — PIPELINE (not yet buildable — Phase-1 continues)

Unlike every other `PIPELINE.md` in this repo, this one is a **plan**, not a working
recipe — Phase 1 groundwork is not finished (see `FEASIBILITY.md` open items). Filling
this in is the definition of "done" for the rest of Phase 1.

## Planned shape (once the open gates close)

1. **Extract** — `tools/bf6_toc.py` (done) reads any per-category `.toc` header. Next:
   port `ReadBundleData`/`ReadChunkData`/`ReadCasBundles` (already decompiled and
   understood, see `RECON.md`) to actually list every bundle/chunk name + its CAS
   offset/size, then decompress one CAS payload (needs the Oodle wrapper — copy the
   ctypes pattern from `games/acshadows/tools/acs_oodle.py` or
   `games/cyberpunk2077` — same `oo2core_9_win64.dll`, already shipped with BF6) and
   locate the localization resource inside it.
2. **Translate** — once the English source + Arabic skeleton are both extractable,
   this is a standard EN→Hebrew job into the Arabic slot (per the Universal Playbook,
   §0 "Arabic-slot hijack"), delegated to a second agent per
   `universal/AGENT_TRANSLATION_HANDOFF_TEMPLATE.md` — Claude builds tooling only, never
   translates ([[delegate-all-translation]]).
3. **Build/pack** — blocked on the `ToCSig` question (FEASIBILITY.md gate #3). If the
   signature isn't verified for local single-player assets, this is a normal
   read-modify-write repack (like every other game here); if it is verified, this
   needs either a bypass or an additive/non-destructive loader mechanism (FMT does not
   have one for BF6 yet — `CanLaunchMods:false`).
4. **Deploy** — target the standalone `SP/` build first (lower risk, no live-service
   surface). Activation is presumably an in-game language setting, same as every other
   title here — not yet confirmed for BF6's specific menu wording.
5. **Font** — not yet checked at all.

## What already exists

- `tools/bf6_toc.py` — read-only `.toc` header parser, validated against 6 real files.
- `notes/FMT_BF6Profile.json` + `notes/FMT_decompiled_BF6Plugin/` — the community-tool
  evidence this whole recon is grounded in.

## Do NOT do

- Do not attach a debugger or otherwise touch the *live* `bf6.exe`/`EAAntiCheat`
  process — every finding here came from static file/tool analysis, and that should
  stay the discipline for this title given the anti-cheat presence.
- Do not assume Arabic = same locale code shape as other games here (`ArabicSA`, not
  `ar`/`ar-AE`/`ar-ar`) — check `chunkmanifest`-style language names, not a guess.

## מסמכים קשורים
- באותה תיקייה: [[games/battlefield6/FEASIBILITY|FEASIBILITY]], [[games/battlefield6/RECON|RECON]], [[games/battlefield6/RESEARCH_LOC|RESEARCH_LOC]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#battlefield6|CLAUDE_INDEX_games]]
