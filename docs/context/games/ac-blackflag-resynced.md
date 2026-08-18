## Assassin's Creed Black Flag Resynced Hebrew — Phase-0 recon DONE, 🟡 GO-WITH-CAVEATS (2026-07-11)

New game scaffolded at `games/acblackflag/` (RECON.md + `tools/acbf_forge_probe.py`). User asked
for a **read-only GO/no-GO only** (no game files touched). Install `C:\Games\Assassin's Creed
Black Flag Resynced` — this is Ubisoft Singapore's full **2026 remake** ("Black Flag Resynced",
released 2026-07-09, **2 days before this recon**), NOT the 2013 classic — built on the **same
Anvil generation as AC Shadows** (RT/RTGI, DirectStorage, XeSS, FSR frame-gen, GFSDK Aftermath;
HUB trailer files reference Mirage/Odyssey/Origins/Valhalla/Shadows).

- **Container = `.forge`, magic `scimitar\x00` + version 50** (uniform, 157/157 forges
  surveyed) — newer than every scimitar version cracked so far in this repo (AC2=25, Unity=27,
  Shadows=42). Per-resource chunk wrapper reuses the exact AC-Shadows Oodle-Kraken chunk magic
  (`0x57FBAA33+0x1004FA99`, no bundled `oo2core*.dll` — borrow one, same as ACS/GoWR) so the
  low-level codec is very likely unchanged. **v50's TOC/index layout does NOT match v25/v27/v42
  byte-for-byte** — tested the AC-Unity-style `index_off@13→count→rec_start=index_off+0x70,20B
  records` against 3 real forges; a plausible count decodes but the record array isn't a flat
  table immediately after (Oodle chunk data starts ~30B later — far too little room for a
  126,249-entry array) → needs its own dedicated crack, not a drop-in reuse. **Lead:** a
  head+tail string scan of `DataPC_boot.forge` found the tail 400 MB dense with genuine
  plaintext class/property names (`GameContext`, `QuestExtensionInstance`,
  `TextStyleController`, and — directly relevant — **`dsArabic`**) → the name/reflection table
  likely sits near the file's END, not the start (concrete next step). Zero community tooling
  exists yet for this exact title/version (2 days old — no AnvilToolkit profile, no Nexus mod).
- **🟢 Localization — the decisive positive, ALREADY closed.** `localization.lang` (plaintext
  JSON) declares **`ar-SA` in BOTH `text.languages` AND `subtitles.languages`** (not just a
  stub) — no Arabic VO (expected, English audio stays). `streaminginstall.ini` confirms Arabic
  is a genuine separately-flagged text-only Ubisoft Connect language pack (`ara=65582`, no
  `,full`); `videos/ar/` ships Arabic localized videos too. **Activation lever found — a plain
  registry STRING** (simpler than every other game here): `uplay_install.state` shows per-lang
  keys `HKCU\SOFTWARE\Ubisoft\Assassins Creed Black Flag Resynced\Language` incl. **`ar-AA`**.
- **🟢 Font — ZERO injection work needed** (same finding as AC Shadows, independently verified
  via fontTools cmap+glyf): the shipped `resources/AvenirNextWorld-Regular.ttf` already has
  **all 27 Hebrew letters (U+05D0–05EA, real outlines, contours=1, not `.notdef`)** + 20 niqqud
  + Hebrew punctuation + full Arabic coverage. TrueType (`glyf`), so a glyph-merge target if any
  other in-game font ever lacks Hebrew.
- **⚠️ Denuvo confirmed present** (public coverage of this exact release + independently
  verified `.vmp0`–`.vmp3` VMProtect sections in the PE header of `ACBlackFlag.exe`) — a first
  for the AC lineup in this project (AC2/Unity/Shadows are all Denuvo-free). No EAC/BattlEye
  (single-player). Denuvo protects executable CODE, not arbitrary data archives, in every AC
  title analyzed here (Valhalla/Odyssey/Origins all ship Denuvo + have working asset mods in the
  wild) — flagged as a real-but-likely-benign caveat, not a proven blocker.
- **Verdict 🟡 GO-WITH-CAVEATS.** The two historically hardest gates (real Arabic RTL text+
  subtitle locale + a font that already ships full Hebrew) are BOTH closed for free, with an
  unusually simple registry activation lever — stronger starting position than most games at
  this stage. The one real gate is the container: brand-new forge sub-version, no existing
  tooling, TOC needs a fresh dedicated crack (the tail-of-file string lead is the next step).
  **Nothing was written to any game file this session** — pure read-only recon.

### 🟢🟢 VERDICT OVERTURNED (2026-07-24): the target REOPENS — modified forges DO load; the SHA-256 "wall" was a misdiagnosis

Re-research after a modding scene emerged (`games/acblackflag/RESEARCH_MODPATH.md`). **The
2026-07-17 "blocked by a SHA-256 content check" conclusion is contradicted by ~40+ live Nexus
mods for this exact title that modify the forges and load in-game** — incl. FOUR translation mods
adding NON-shipped scripts (Thai #10 ships a whole `DataPC_boot_patch_02.forge`+`resources/`;
Ukrainian #8 runs a bundled python patcher; Turkish #31; Indonesian #37), texture mods that edit
`DataPC_boot.forge` in-place via bundled injector exes ("wait for SUCCESS", #96–#127), and a
public **Forge Injector V1 BETA (#108)** = a standalone v50 read/write tool (729 resource IDs,
restore). ⇒ there is **no game-side integrity check on forge content**; the exe's VMProtect +
`SHA256/integrity/tamper` strings (re-measured 2026-07-24: 164/7/11, `.vmp0`–`.vmp3` present,
UNCHANGED after the Jul-22 patch) protect the CODE and fingerprint the build — they do NOT gate
data. **The black-screen was TECHNIQUE-specific: the project used append-relocate / full-repack
INTO `patch_01` (resource 1244); the community's working methods are the OPPOSITE — a same-slot
in-place resource replace in the BASE forge, or a fresh higher-priority `patch_02` override.**
No official mod support / no `mods/` folder / no ASI loader (Steam users beg for it, "not going to
happen") — the channel is the community injector + drop-in override forge. **Hebrew path reopens**:
patch the already-extracted Arabic slot (idx 27724 UI + 27725 subs) with this project's proven v50
codecs, deploy via in-place-same-slot OR a `patch_02` override (NOT append-relocate-into-patch_01),
font already free (loose `resources/AvenirNextWorld-Regular.ttf` has all 27 Hebrew glyphs),
activate via `…\Language = ar-AA`. **⚠️ Supported-channel + passive-measurement research only — no
DRM/anti-tamper work, game left clean.**

### 🔴 (superseded) FINAL VERDICT (2026-07-17): container + text FULLY CRACKED, deploy thought BLOCKED

Everything upstream of deploy was solved this session — v50 TOC, CFD codec, the char-index
LocalizationPackage, the Arabic slot, the font. **The game still refuses every modified forge.**
All game files were restored clean (patch forge md5-identical to original; user confirmed
"נפתח ערבית"). Full detail in the memory [[acbf-resynced-v50-cracked]].

- **What WAS cracked** (all pure-Python, in `games/acblackflag/tools/`): the **v50 forge TOC**
  (24-byte `<QIIII>` = offset, ts(=fileID), flags, size, nameHash(=TYPE, not a content hash));
  **`acbf_cfd.py`** = the CompressedFileData codec (`u64 magic 0x1004FA9957FBAA33` + 7-byte
  cinfo + `i32 blockCount` + BlockInfo `{i32 uncomp, i32 comp}×N` + blocks `{u32 adler, data}`,
  checksum = **`zlib.adler32(comp, 0)`**, Oodle Kraken, 262144-byte blocks); **`acbf_locpkg.py`**
  = the char-index/fragment-tree LocalizationPackage (marker `0xD28389B5`) with a working
  encoder. Round-trips byte-identical.
- **🔑 THE ANVIL DEPLOY LAW — the most transferable knowledge from this session.** Derived by
  isolation over ~8 in-game boots; it applies to EVERY Anvil title (Shadows/Unity/AC2), and each
  rule was learned from a distinct failure mode:
  1. **`buffer == object`, ALWAYS.** A native CFD satisfies `CFD0@10 == CFD1@4 + 51` (the
     descriptor's declared decoded length == the object's own size field + a 51-byte const).
     **Never pad.** Padding to preserve the on-disk size hangs the game at menu load — the
     loader reads exactly `CFD0@10` bytes and chokes on any trailing byte, zeros included.
  2. **The forge must stay 100% CONTIGUOUS.** Record data is streamed (DirectStorage) with no
     gaps. Shrinking a record's TOC `size` and leaving the hole → **black screen at boot**.
  3. **Three length fields must ALL be re-derived on any content change:** `CFD0@10` (decoded
     length of CFD1), `CFD1@4` (= decoded length − 51, the object size), and the payload's own
     `num` after the marker. A stale `@4` = out-of-bounds read = "warning window + crash".
  4. **Our Oodle is NOT the suspect.** Both 2.5 (`oo2core_5`, RDR2) and 2.9.12 (`oo2core_9`,
     BF6) produce lead byte `0x8C` — the same as the game's own blocks — and the game decodes
     our streams fine (proven by the resource decoding correctly on re-read).
  5. **Because our compression is smaller, a re-pack is mandatory.** `work/repack_patch.py` is
     the reference implementation: rewrite the resource, shift every LATER record's data earlier
     by `delta`, rewrite the whole TOC (offsets − delta, new size for the edited record), patch
     the desc `tocOffset`, then **verify the temp file** (contiguity invariant + the edited
     record decodes + spot-check later records) before `os.replace`. Full backup first.
  6. **Patch forges OVERRIDE base forges by fileID.** A game update rewrote
     `DataPC_boot_patch_01.forge` — which holds all 14 language UI packages (Arabic = idx
     **1244**) — silently shadowing my base-forge mod. **Always target the patch forge**, and
     re-verify after every game update.
- **🔴 THE BLOCKER: a SHA-256 integrity check on forge content.** The decisive experiment: a
  **100% structurally-natural** resource (no pad, native block count, all length fields correct)
  in a **fully contiguous** re-packed forge — with the Arabic content byte-identical, only the
  Oodle bytes differing — **still black-screens**, while the untouched forge boots Arabic fine.
  Both Oodle versions behave identically. `ACBlackFlag.exe` carries **SHA256 ×143 / integrity ×5
  / tamper ×11** strings, and there is no loose-file override loader. Conclusion: the content is
  hashed and validated. **Do NOT attempt to defeat it** — a byte-flip probe was correctly blocked
  as anti-tamper circumvention, and that stands as the project's policy.
- **⚠️ Tooling gotcha:** `build_menu_proof.py --revert` DELETES its own backup blobs, so a revert
  destroys the pristine resource you still need — re-extract it from the restored forge.
- **Where this goes:** the same toolchain retargets cleanly to **AC Shadows (v42)**, which has
  **13× fewer** integrity strings (SHA256 ×11 / tamper ×3) and a live Nexus forge-mod scene =
  empirical proof it accepts modified forges. Plan written to **`games/acshadows/PLAN_HEBREW.md`**
  (Shadows gets its own chat).
- **🔴 RE-CHECK (2026-08-10, after the working texture-mod scene appeared — Nexus "Forge Injector
  V1 BETA" #108 + texture/mesh mods): the blocker STANDS, and here's why the working mods don't
  help.** A read-only re-scan (game had an Aug-4 update that SHIFTED all patch indices — old
  `_patch_01` idx 1244 is now a stray 332-B resource; re-verify indices after EVERY update) proved
  the Arabic TEXT lives ONLY in the boot forge: `DataPC_shared_00.forge` (base, 7.9 GB, 48,926
  recs — the big moddable model/texture forge the texture mods target) carries **0 localization-
  marker (`0xD28389B5`) hits across 46,004 probed resources**, and `DataPC_shared_00_patch_01`
  = 0, and the current `DataPC_boot_patch_01` (post-update) = 0 (the loc override moved back to the
  base `DataPC_boot.forge`). **⇒ the working mods modify a DIFFERENT, non-hash-gated forge
  (`shared_00`) than the one that holds text (`boot`), so a live texture-mod scene is NOT evidence
  the text path accepts changes.** The only two theoretical text paths both require crossing the
  anti-tamper line (patch the exe/memory to disable the SHA check) — **out of scope**. **UNIVERSAL:
  "the game has working mods" ≠ "MY surface is moddable" — confirm the moddable forges actually
  CONTAIN your content type before treating a mod scene as a green light.**

---


