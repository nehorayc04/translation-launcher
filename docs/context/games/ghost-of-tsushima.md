## Ghost of Tsushima Director's Cut Hebrew — Phase-1 DONE, 🟡 GO-WITH-CAVEATS (font gate) (2026-07-07)

New game scaffolded at `games/ghost_of_tsushima/` (RECON/FEASIBILITY/PIPELINE + `tools/xpps.py` +
`work/{got_rtl.py,build_menu_proof.py}` + `notes/`). Sucker Punch proprietary engine, **Nixxes** PC port. Install
`F:\Games\Ghost of Tsushima DC`, exe `GhostOfTsushima.exe`, Steam appid **2215430**, **RUNE crack (DRM-free)**.
Detector key + Supabase `games.id` = **`tsushima`** (already wired — the launcher already detects the install; a
catalog card `tsushima` exists in `game_detector.py`/`config.py`/`games.json`). Driven by
`universal/NEW_GAME_GROUNDWORK_PLAYBOOK.md` via a multi-agent workflow (`got-groundwork-phase1`, 6/8 agents; 2
network-errored, non-blocking) + adversarial verify. Memory [[tsushima-groundwork]].

- **🟢 Container = DSAR → PSARC — IDENTICAL to TLOU Part II.** Every `cache_pc/psarc/*.psarc` = magic **`DSAR`**
  (outer LZ4, entry flags low-byte `0x03`) → inner Sony PSARC v1.4 (`zlib`, block `0x10000`, TOC by `md5(path)`,
  entry-0 NUL manifest). `games/tlou2/tools/{dsar.py,psarc_write.py,dsar_write.py}` read+rebuild GoT **unchanged**
  (round-trip semantic-PASS on `gapack_misc_p`; **free growth, NO delta-0 pad**). GoT writer deltas: inner PSARC
  **`flags=0x0e`** (TLOU2 uses 0x0c), inner **STORED** (`compress=False` — DSAR/LZ4 outer does compression), DSAR
  filler `55*7`, 16-byte chunk align. Repack is semantic-loadable NOT byte-identical (LZ4 encoder + md5-vs-manifest
  data order — fine, matches TLOU2). ⚠️ `dsar.py` crashes on the `ct=254 PADDING*` sentinel (`gapack_misc_b`);
  target archives clean. (`music_*.psarc` = plain PSAR, audio.) **No Denuvo/EAC, PSARC has no whole-archive checksum.**
- **🟢 Text = `gapack_misc_l.psarc` → `lang_<lang>_text.xpps` (KCAP)** — one per language (~34). Source
  `/lang_english_text.xpps` (16,583,124 B); **Hebrew slot (Arabic) = `/lang_arabic_text.xpps` (17,064,240 B) —
  official Arabic locale EXISTS**, stored LOGICAL. Format **`KCAP`** ("PACK" LE): header + UTF-8 **NUL-separated**
  string blob + 16-byte index records `{u64 KEY, u64 OFFSET}` (file_pos=BASE@0x28+off) + trailer @0x2c. **Two KEY
  kinds:** (a) LARGE 64-bit content-hash — **GLOBAL, cross-language-stable → EN↔AR map by exact key** (UI/content
  ~13k reliable pairs); (b) SMALL structured dialogue ids `{u16,u16}` — **collide globally, join by block+position**
  (~28k dialogue). Codec `tools/xpps.py` (identity byte-identical; surgical override = append+repoint u64 offset +
  bump @0x2c). **⚠️ the reader UNDERCOUNTS (~15k of ~36k) — it only finds strictly-ascending contiguous tables;
  Phase 2 must widen it (walk the @0x2c trailer directory for all index sections).** **Scope ≈ 36,000 distinct
  strings** (~41k with dups): ~17.5k short (≤25 ch) UI · ~17.4k medium · ~1.4k long lore/subtitle. Tokens to
  preserve: PUA button/format glyphs `U+E000–U+F8FF` (matched pairs `U+F003/4/5`), `{SAVE_FOLDER}`/`{GPU_NAME}`/…,
  `%d`/`%f`, literal `\n`.
- **🟡 bidi = LEANS LOGICAL** (Arabic stored logical + `python-bidi` reorders it → engine bidis) — but Arabic
  official ≠ guaranteed Hebrew bidi (Witcher-3/GoWR lesson) → **menu-proof decides.**
- **🔴 THE GATE — font.** Menu+subtitle glyphs = a Sucker Punch proprietary **compressed `fOnk` VECTOR font**
  (`SFontData`/`FontGlyphs`/`FontVerts`) inside `game.sprig.texmeshman` (`gapack_misc_g`) — **NOT TTF, NOT DDS
  atlas** (0 sfnt anywhere). Arabic covered, **Hebrew almost certainly ABSENT**. The 34 `lang_<x>.msac.d.0.sps`
  (87 KB DDS) are localized button-legend images, NOT glyph atlases. Hebrew injection needs the `fOnk` format
  cracked (a sub-project, harder than the SM2/WD2/GoWR atlas/TTF work). The menu-proof tests coverage in-game.
- **🟢 Deploy = additive override `.psarc`, no gapack rebuild.** Drop a small psarc holding ONLY
  `/lang_arabic_text.xpps` (**leading slash** — md5(path) must match the shipping TOC), named to sort **after**
  `gapack_misc_l` (e.g. `zzz_hebrew.psarc`), into `cache_pc/psarc/`; the engine mounts all `*.psarc` alphabetically
  and later overrides earlier. The 55 shipped archives untouched; revert = delete one file. Precedent: Nexus #807
  Austronesian pack + commercial Persian RTL localization load. Activation = Settings → Options → General → **Text
  Language = العربية**. Community tools: GoTExtractor (Glumboi MIT), UnPSARC, GoT Translation Tool (#809).
- **✅ DEPLOY PROVEN IN-GAME 2026-07-07 — mechanism SOLVED; font is the lone remaining gate.** Deploy is NOT an
  added override psarc: the engine builds a global path map and CRASHES boot on the DUPLICATE `/lang_arabic_text.xpps`
  (both a faithful and an unfaithful DSAR crashed; a plain PSARC under a `gapack_misc_*` name is silently skipped —
  the engine reads DSAR magic there). **Deploy = EDIT `gapack_misc_l` IN PLACE.** Built `work/got_dsar.py` = a
  FAITHFUL GoT DSAR writer (the two deltas that made tlou2's `dsar_write` crash: reserved filler **`55*7`** not
  `54 55*6`, and **16-byte-aligned compOffsets** with **`PADDING*`** gap filler) + `patch_inner()` = a SURGICAL
  same-size editor that re-LZ4s ONLY the DSAR chunks overlapping the edit and copies every other chunk's payload
  VERBATIM. got_dsar proven engine-faithful by an identity rebuild of `gapack_misc_p` that BOOTED. The menu-proof
  `work/build_inplace_proof.py` (`--deploy`/`--revert`): a same-size in-place KCAP override (`xpps.patch_inplace`,
  Hebrew ≤ Arabic bytes) of the menu keys (all sit in the first ~562 KB = the xpps's RAW-block region, 260/261
  blocks raw, identity map inner=F+off with F=131072) → only **3 of 8383 DSAR chunks** re-LZ4'd, inner PSARC
  structurally unchanged, offline-validated (495 files re-read, others byte-identical) → deployed with a 1.43 GB
  `.he_backup`. **In-game result: `ZZ-GOT-OK-ZZ` (Latin marker) RENDERS in the main menu → the override loads +
  Latin/Arabic glyphs work; the Hebrew items render as TOFU (▯) → the `fOnk` font has NO Hebrew glyphs.** (The
  separate game LAUNCHER window renders Hebrew fine — a different font path, not reusable in-game.) So container +
  text + deploy are 🟢 PROVEN end-to-end; **bidi is still undetermined (tofu can't show order); the FONT is the one
  hard gate** → next = the `fOnk` glyph-injection sub-project (crack the compressed vector-font in
  `game.sprig.texmeshman`, add U+05D0–05EA outlines, repack `gapack_misc_g` via got_dsar) OR find a font-fallback.
  Reusable tooling now in place: `tools/xpps.py` (+`patch_inplace`), `work/got_dsar.py` (`wrap`/`patch_inner`/
  `chunk_boundaries`), `work/build_inplace_proof.py`, `work/dsar_engine_test.py`. Phase 2 (once font solved) =
  delegate ~36k translation per [[delegate-all-translation]] → in-place edit via the same tools → publish like
  SM2/WD2/GoWR; gender via the game's own `lang_russian`/`lang_spanish` locales joined by key.

### GoT FONT sub-project — exhaustive session 2026-07-08: mechanism MAPPED, one indirection still blocks
Full detail: `games/ghost_of_tsushima/notes/FONT_SESSION_2026-07-08.md`. Text+container+deploy stay PROVEN; the font
is the only open gate and it is genuinely research-grade (hardest in the project, cf. the AC Shadows v42 repacker).
**State left CLEAN** (gapack_misc_g pristine, gapack_misc_l = menu-proof/Hebrew-tofu, boots stable).
- **Font model CONFIRMED by live differential rendering (not theory).** 64-byte cmap record in `ghost_title.xpps`:
  `+0 cp · +14 face/page · +16 GLYPH-REF · +18 COUNT · +20 0xf8 · +22/+26/+30 f32 geom(x,y,size) · +46.. white ·
  +62 0xffff`. Latin (page 4, ref 39, geom 0) resolves by CP; Arabic has per-glyph refs (renders); **all 27 Hebrew
  letters share ref 1522 + size 5 = the notdef box = the in-game tofu.**
- **`tail-kind2` @0x97c8d0 IS the FontVerts store**: 48.9% clean normalized f32 (x,y) pairs in [-1,1] interleaved
  with `0x74XX74XX` "pack runs" (per-contour flags/topology). Zeroing it CRASHES the game ⇒ structurally used.
- **`store @0x8b0000` is NOT the outline — DISPROVEN in-game TWICE**: overwriting its bytes at the Hebrew slot
  (ref 1522) AND at the Arabic-alef slot (ref 1680) changed NOTHING on screen. The earlier 1.6M-token workflow
  attacked this wrong region; its "opaque 8-byte codec" is a red herring (likely a pointer table relocated at load,
  which is also why file-byte edits there are inert).
- Editing a record's `+16/+18` **crashes** at menu-render (wrong ref ⇒ OOB in the per-face store) ⇒ the ref IS
  consumed, but is only safely changeable within a face, and **the +16 → tail-kind2 mapping is still unknown**: not
  oid*8, not via @0x8b0000, **no absolute pointer table into tail anywhere in process memory**, and **no monotonic
  u32 offset table** in the file. It exists only as relocated in-memory state on the draw path.
- **Structural blocker beyond the codec:** the 27 Hebrew letters share ONE degenerate ref, so even a cracked coord
  format cannot render 27 DISTINCT letters without safely assigning new within-face refs (the same unknown).
- **Why the autonomous debugger could not finish it (all measured — do not repeat blindly):** the tessellation is a
  **ONE-TIME, cached** event (guard armed at the menu ⇒ 0 reads in 22 s). Catching it needs the guard armed BEFORE
  the first render, and each route failed for a concrete reason: (a) scanning all committed regions for the tail VA
  takes 30-75 s (region count grows during boot) ⇒ armed at t+38-110 s, after the render; (b) a scanner THREAD
  inside the debugger process causes **GIL contention that FREEZES the debuggee** (the loop can't call
  ContinueDebugEvent) and stalls boot — fixed by moving the scanner to a separate PROCESS; (c) forcing a re-render
  by resizing the window **hangs** (SetWindowPos blocks on a debugger-frozen window); (d) the tail bytes exist in
  MULTIPLE heap copies, so arming "the" copy may not be the one the tessellator reads. Measured tail region:
  **~2 MB, PRIVATE, PAGE_READWRITE (prot 0x04)** — filter on 0.5-8 MB RW for a fast scan; a 4-96 MB filter silently
  misses it (that mistake cost a whole run).
- **THE reliable finish = x64dbg (interactive):** attach, HW read-watchpoint on the live tail VA (get it with
  `work/live_trace.py`), trigger a re-render (enter a submenu / change Text Language); the RIP that hits IS the
  tessellator's vertex fetch → disassemble backward for the +16→offset math + vertex layout → then author Hebrew
  outlines into tail-kind2 and wire the 27 records. Tools ready: `work/got_dbg.py` (PAGE_GUARD debugger),
  `got_dbg_boot2.py` + `got_scan_arm.py` (two-process boot capture), `memdump.py`, `live_trace.py`.
- **Community check (done): NO existing GoT tool/mod cracks the font** — only mesh tools (ResHax/hex2obj; mesh verts
  are int16, UVs fp16, e.g. GOT_Model_Viewer) and the text tool (Nexus #809), both already surpassed here. There is
  no public shortcut; the font is unexplored by the community.
- **⚠️⚠️ SUPERSEDED 2026-07-20 (user present) — TWO of the claims above are now DISPROVEN; do NOT re-attempt them:**
  1. **x64dbg is NOT a viable finish, and NEITHER is any live-debug** — because the ENTIRE font is transformed at
     load: **NOTHING from `ghost_title.xpps` appears verbatim in the running game's memory.** Proven by two full-memory
     scans at the menu (Arabic+Hebrew-tofu on screen): `f[0x97c8d0:+40]` = **20 pure relocation-proof f32 coords = 0
     matches** across every PRIVATE/MAPPED region, and a full 64-byte cmap-record SIG = **0 matches** across
     PRIVATE/MAPPED/IMAGE. `got_scan_arm.py`/`live_trace.py` found the SIG only AT BOOT (a brief pre-transform window).
     ⇒ there is **no content-findable anchor address** for a PAGE_GUARD or an x64dbg HW watchpoint. The whole reason to
     have the user at the game (arm a watchpoint, trigger a re-render) is moot. **This is a pure STATIC file-format
     problem — the game does NOT need to be open.** (`work/got_catch_rerender.py` = the attach-at-menu design; correct
     but dead here, keep for a future game whose font IS verbatim in memory.)
  2. **The "27 Hebrew letters share ref 1522 → structural blocker" is a RED HERRING** — `ref` is NOT a per-glyph
     outline index. Latin all share **ref 39**, and **Arabic distinct-rendering codepoints ALSO share refs** (0x625-0x62a
     ALL = **ref 1680**, same face 129; the base 0x627/0x628 records differ only in geom-z = near-duplicate placeholders,
     since real Arabic rendering uses shaped presentation forms 0xFE80..). ref selects a **face/atlas-page**; the glyph
     resolves by CP within it. So Hebrew (face 104, ref 1522) is tofu because **1522 = the notdef page and the font has
     ZERO Hebrew outlines anywhere**, NOT because letters share a ref. Hebrew records are STRUCTURALLY IDENTICAL to the
     rendering Arabic records (same +18 range, +20=248, +46=1.0f, geom pattern) — they just point at notdef.
  - **The real (unchanged-in-kind) gate:** author 27 novel Hebrew outlines into the vertex store's file encoding
    (f32 pairs + `0x74XX74XX` pack-runs) and expose them via a face the Hebrew cmap points at — a from-scratch static
    crack of a studio-unique compressed vector font with no community tool and no live anchor. Research-grade; the
    sole open item (container+text+deploy PROVEN). cmap map: real tables @0x87a652 (n=612, Arabic+Hebrew, face 30-177)
    + @0x883f92 (n=2740, presentation forms); Latin fallback @0x8672a6 (face 0, ref 0/39, resolves-by-CP).

---


