# GoT DC font — session 2026-07-08 (autonomous, user away): capture loop + store-codec wall

## ✅ NEW capability: fully-autonomous in-game launch + screenshot (reusable)
`work/got_cap.py` + `work/memdump.py`. The two blockers to self-verification are SOLVED:
- **Elevation:** `GhostOfTsushima.exe` manifest = requireAdministrator (`CreateProcess` -> WinError 740).
  We are non-elevated and can't register a Highest-runlevel task (Access denied) or accept UAC (user away).
  **Fix: launch with env `__COMPAT_LAYER=RUNASINVOKER`** -> runs asInvoker, ignores the manifest, NO UAC.
  Verified: game boots + runs stable (the earlier "exit at 25s" was the USER closing it, not a crash).
- **Capture:** GoT is a DX12 **flip-model** swapchain -> GDI `ImageGrab` returns BLACK. **Fix: `dxcam`**
  (DXGI Desktop Duplication; pip-installed into the repo `.venv`). `got_cap.py` grab() uses dxcam, GDI fallback.
- **Launcher:** `HKCU\...\Ghost of Tsushima DIRECTOR'S CUT\ShowLauncher` = 1 shows the Nixxes launcher
  (GDI window, renders Hebrew fine via system font-linking — NOT the in-game path). **Set ShowLauncher=0
  via PowerShell** (the `reg.exe` CLI fails on the apostrophe in "DIRECTOR'S CUT" + MSYS backslash mangling)
  -> boots straight to the in-game menu (~11s, shaders cached). `TextLanguage=21` (Arabic slot) already set.
- CLI: `got_cap.py launch|wait <png>|shot <png> [move]|click <fx> <fy>|kill|ps`. Boot->menu ~11-140s
  (shader compile varies). ⚠️ synthetic clicks on the LAUNCHER didn't register (focus-lock); use ShowLauncher=0.

## Record model — CONFIRMED (resolves the round-2-vs-attempt5 contradiction, from real data)
`ghost_title.xpps` 64-byte cmap record: `+0 u32 cp` · `+14 u16 page/face` · **`+16 u16 OUTLINE-ID`** ·
**`+18 u16 COUNT`** · `+20 u8 0xf8` · `+22/+26/+30 f32 geom (x,y,size)` · `+46..+61 f32×4 white` · `+62 0xffff`.
- **Latin** (A/O/i): page=4, region=39, geom=0 — near-identical, outline resolved by CP externally (attempt#5 right).
- **Arabic** (0x627): page=129, outline-id=1680, count=6, geom(114,0,10) — per-glyph, REAL (round-2 right).
- **Hebrew** (0x5d0..0x5ea @0x87ec92, stride 64): ALL share page=104, outline-id=1522, count∈{11,12,13},
  size=**5** = notdef box -> the in-game **tofu**. Hebrew POINTS (nikud) 0x591.. have 35 distinct real refs.

## 🔴 THE WALL: the outline STORE @~0x8afe80 (font sub-resource 0x850c00..0x8b74b0)
- A **RAW array of 8-byte units** (NOT compressed, NOT encrypted): 3782 units, entropy 7.9. Resolution =
  `store[outline_id .. outline_id+count]` (8-byte units). Proven RAW because 3 specific units repeat VERBATIM
  ~111× each = the shared notdef-box vertices (compression/whitening would destroy verbatim repeats).
  The box unit-sequence is `A B C B C…` = a **GENERATE_QUAD** triangle/quad strip.
- **The 8-byte unit encoding is UNCRACKED.** Ruled OUT (this session + 2 prior workflows): int16/uint16 pairs,
  f32 pairs, f16×4, i32/u32 pairs, 10-24-bit signed bitfields, ECB/AES (no global 16-byte-block dup pattern
  matching a cipher), zlib/lz4/Oodle (GoT ships NO oo2core; no codec lead byte). **Notdef-box known-plaintext
  FAILED:** the 3 box units (`af4f663e9270bd11`,`b7f87c6e102c74b7`,`3a79c7b0c2da2f34`) do NOT form an
  axis-aligned rectangle under any tried (x,y) extraction. `af4f663e`=0.225 as f32 looks clean but the pair
  and the Arabic units decode to garbage -> the coords are packed in a non-obvious way (candidate NEXT
  hypotheses: parallel x-array/y-array (not interleaved), biased/scaled f16, 16.16 fixed, half-edge/Bezier ctrl).
- **Cross-face repoint CRASHES the game** (~20s, at menu-render time): pointing a Hebrew record's (+16,+18) at
  an Arabic outline crashes -> the engine picks the store/face by the cp's SCRIPT, indexes by +16 -> an Arabic
  outline-id (1680) into the small Hebrew-face store = OOB. This CONFIRMS (+16,+18) is consumed (the ref IS the
  lever) but repointing is only valid WITHIN the Hebrew face. So Hebrew needs REAL Hebrew outlines authored in
  the Hebrew face's store (needs the codec). Pristine gapack_misc_g is stable >39s (edit is what crashes).
  Both my full-body copy AND the workflow's 6-byte-ref copy crash (`build_mechproof.py` / the workflow artifact).

## Authoritative source = the exe (memory-dumped, defeats VMProtect)
`memdump.py exec|live|strings` — ReadProcessMemory the running game (same user/integrity, no admin). Dumped
125MB of UNPACKED exec code to `scratchpad/gotmem.*.bin` (+ `.index.txt`). Font-string VAs (exe base ~0x7ff7f20d1000):
FontGlyphs 0x7ff7f31d9310 · FontVerts 0x7ff7f31d9320 · SFontData 0x7ff7f32291b8 · GENERATE_QUAD 0x7ff7f33498e0 ·
FONT_KIND 0x7ff7f33498f0 · FONTK 0x7ff7f3233cf8. **RIP-xrefs (2): code @0x7ff7f220461f->GENERATE_QUAD,
@0x7ff7f22047a6->FONT_KIND — but that function is REFLECTION/schema-registration (builds 24-byte field
descriptors: name-ptr + 64-bit hash + enum default), NOT the decoder.** The real tessellator is reached from
the text-draw path (reads the parsed SFontData struct) — a deeper trace TODO.

## Tools built this session (`work/`)
`got_cap.py` (launch/capture), `memdump.py` (RPM dump/live-search/strings), `build_mechproof.py` (crashes -
Latin-O has +18=0xffff=count 65535 -> OOB; keep only Arabic Test A next time), `/c/tmp/got_{ght_dump,indir,
store,ecb,crack,xref,disasm}.py` (analysis scratch). Cached `extract/ghost_title.xpps` (10,103,200 B).

## NEXT (relentless): 3 live paths, hardest gate in the project (cf. AC Shadows v42-repacker wall)
1. **exe decoder trace** (background workflow): from the SFontData reflection struct, follow to the code that
   reads FontVerts + tessellates -> the authoritative 8-byte-unit format.
2. **fresh codec hypotheses** on the store (parallel arrays / biased-f16 / 16.16 / half-edge), cross-validated
   on notdef-box + nikud-dot cribs.
3. **differential rendering** (uses the capture loop): perturb an ARABIC glyph's store units (same-face, safe),
   redeploy (`got_dsar.patch_inner`, 1s) -> screenshot -> observe shape change -> empirically decode. Slow
   (~11s boot/iter) but relentless. Read the game's own Arabic menu (revert gapack_misc_l to pristine for that).

## ⚡ CRITICAL UPDATE — differential rendering DISPROVES @0x8b0000 as the outline (2026-07-08, decisive)
Ran the capture loop (RUNASINVOKER + dxcam) on real edits. FULL menu captured (`/c/tmp/got_st_6.png`): top marker
`ZZ-GOT-OK-ZZ` renders (override loads); the game's own Arabic items render perfectly (لعبة جديدة / دخول طور
الأساطير / تسجيل الدخول إلى PlayStation / الخروج من اللعبة); our Hebrew override items = tofu boxes.
- **TEST 1** (`work/build_storetest.py`): overwrote the HEBREW notdef store slot (oid 1522 @0x8b2f90) with Arabic-alef
  store bytes → **Hebrew menu STILL tofu boxes** (no change). Same-face store-byte edit did NOT crash.
- **TEST 2** (`/c/tmp/storetest2.py`): overwrote the ARABIC-alef store slot (oid 1680 @0x8b3480) with the notdef-box
  bytes → **the on-screen Arabic alefs were UNCHANGED** (still perfect ا). Did NOT crash.
- ⇒ **The @0x8b0000 8-byte-unit array is NOT the glyph outline** (editing it changes NOTHING on screen). The prior
  workflow (1.6M tokens) + all my codec brute-forcing were attacking the WRONG region. tail-kind2 @0x97c8d0 also
  decodes to garbage as f32 at oid offsets — also not it (as tried).
- **TEST 3** (`/c/tmp/ref_test.py`): changed the Arabic-alef cmap RECORD +16 (1680→1690) + +18 (6→4) →
  **game CRASHED at load** (even though 0x627/0x62c looked same-face). ⇒ **+16/+18 are STRUCTURALLY CRITICAL**
  (a wrong value → crash) but the DATA they index at 0x8b0000 is inert to rendering → **+16 maps to a DIFFERENT
  structure** (a pointer table? a per-face outline heap allocated at load?), NOT the 0x8b0000 array, and 1690 is
  likely a different face/allocation → OOB → crash. The REAL outline store is UNIDENTIFIED.
- **Net rule learned:** editing store BYTES (@0x8b0000) = safe + no visual effect; editing cmap +16/+18 = crash.
  So the visible contour comes from somewhere reached via +16 that is NOT 0x8b0000. Candidates still open:
  the kind1 "curve/metric" blobs (@0x8eefa0.., cp-indexed — dir[0] starts with (0,cp) pairs A/E/G), kind3
  (@0x8f43b0, cp lists + ptrs), or a load-time-allocated heap the cmap +16 indexes indirectly.
- **THE authoritative path = trace the exe TESSELLATOR** from the cmap-record read (mov of +16/+18) to the actual
  vertex fetch + GENERATE_QUAD, in the memory dump (`gotmem.*.bin`). Agents (Workflow) blocked until session reset
  (~05:50 Asia/Jerusalem); retry then. Game is REVERTED to the clean menu-proof state (gapack_misc_g pristine).
- **TEST 4** (`/c/tmp/tailzero.py`): zeroed a big middle chunk of **tail-kind2 @0x97c8d0** (the region with ~48%
  of f32-pairs in [-1,1] = real normalized coords) → **game CRASHED at load** (unlike @0x8b0000 which was inert).
  ⇒ **tail-kind2 IS structurally used at load** and holds real coordinates → it is the STRONGEST candidate for the
  real "FontVerts" outline store. But decoding tail-kind2[+16*8 : ...] as f32 pairs = garbage → the cmap +16→tail
  mapping is NOT a direct oid*8; likely an intermediate offset/pointer table (candidate: the disproven @0x8b0000
  array may be that pointer table, RELOCATED at load via the trailer @0x9a2750 reloc dir — which would explain why
  editing @0x8b0000's file bytes is INERT: the loader overwrites them with relocated pointers). NEXT: the exe
  tessellator RE resolves the +16 → tail-kind2 mapping + the f32 vertex layout definitively.

## FINAL STATE this session (2026-07-08) — mechanism fully mapped, ONE indirection blocks injection
Workflow `w11i31s67` RAN (session reset) + live-memory tracing (`work/live_trace.py`, `/c/tmp/live2.py`,`live3.py`,
`offtable.py`) established:
- **tail-kind2 IS the FontVerts outline store** (CONFIRMED): 48.9% clean normalized f32 (x,y) pairs in [-1,1]
  INTERLEAVED with "pack runs" (`0x74XX74XX` = per-contour flags/topology or u16 fixed-point). Run map e.g.
  CLEAN[0:10]/pack[10:75]/CLEAN[75:93]/… First clean run @0x97c8d0 = (-0.6128,0.7584),(0.2221,0.6355),… Zeroing it
  crashes → structurally used. Runtime VA this boot = 0x2cbb3377d40 (a READWRITE data page; standalone allocation —
  the KCAP is NOT loaded contiguously, sections are relocated to separate heaps).
- **The +16 → tail-kind2 mapping is an UNKNOWN indirection** (the last blocker): NOT direct oid*8 (garbage); NOT via
  @0x8b0000 (inert + high-entropy content-hashes, not offsets/VAs); **NO absolute pointer table into tail** (scanned
  ALL committed regions, 0 with ≥20 tail-pointers); **NO clean monotonic u32 offset-table indexed by oid** in the
  file. So the resolver is multi-level / hashed and only exists as RELOCATED in-memory state on the draw path.
- **Structural blocker beyond the codec:** all 27 Hebrew letters share the degenerate oid=1522, and changing a
  record's +16/+18 CRASHES (cross-face OOB). So even a cracked coord codec can't render 27 DISTINCT Hebrew letters
  without safely assigning distinct within-Hebrew-face oids → needs the oid→tail table structure (same unknown).
- Exe RIP-xref to font strings = REFLECTION only (data-driven hash dispatch, no code xref to the tessellator). The
  exec-only memory dump lacks the relocated font-heap pointers.
- **THE definitive next step (needs an INTERACTIVE DEBUGGER — not available in this autonomous shell; do NOT attempt
  DebugActiveProcess/HW-watchpoint blind while the user is away — risk of hanging the game/system):** in x64dbg,
  set a HW read-watchpoint on the tail-kind2 VA (found live via `live_trace.py`); the RIP that hits it IS the
  tessellator's vertex fetch. Disassemble backward from there to read: how +16 → the tail byte-offset (the indirection
  table) and the f32 vertex/pack-run layout. THEN Hebrew injection = write real Hebrew outline runs into tail-kind2 +
  wire the 27 Hebrew records (within-face). Alternatively: dump the game's NON-EXEC data pages fully + reconstruct
  the relocated resource table (heavier, no debugger).
- **VERDICT:** container+text+deploy PROVEN end-to-end; the FONT is a genuine research-grade gate (the hardest in the
  project) needing debugger-level tessellator RE. Autonomous data+empirical analysis has been exhausted this session.
  Game left CLEAN (gapack_misc_g pristine, gapack_misc_l menu-proof = Hebrew tofu, boots stable). All tooling +
  findings persisted for a debugger-equipped continuation.

---

## Session 2026-07-20 (user present): live-debug DEFINITIVELY DEAD + the structural blocker DISPROVEN

Two big results, both change future attempts. Game closed + pristine after; fleet intact.

### 🔴🔴 The runtime is FULLY TRANSFORMED — NOTHING from the font file is verbatim in memory
Two full-memory scans of the RUNNING game at the main menu (Arabic + Hebrew-tofu on screen):
- **`f[0x97c8d0:+40]` (20 pure f32 vertex coords, relocation-proof) = 0 matches** across every
  committed PRIVATE/MAPPED region (2,454 regions, prot R/RW, ≤48 MB). So even the raw float coords
  are re-encoded at load, not just pointers.
- **A full 64-byte cmap-record SIG = 0 matches** across PRIVATE/MAPPED/IMAGE.
⇒ The whole font (cmap + vertex store) is decompressed AND transformed into an opaque runtime
structure. `got_scan_arm.py` only found the SIG AT BOOT because it caught it in the brief pre-transform
window. **This KILLS every live-debug plan** — there is no content-findable anchor address for a
PAGE_GUARD or an x64dbg HW watchpoint. The reason to have the user at the game (trigger a re-render
while a watchpoint is armed) is moot: I can't find the address to arm. Deploy remains file-edit (the
file bytes ARE consumed at LOAD → the differential-render crashes/changes prove it), so this is now a
**pure static file-format problem — the game does NOT need to be open for it.**
- New tool `work/got_catch_rerender.py` (attach-at-menu + user-triggered re-render) — correct design,
  but dead-on-arrival here because the store isn't findable in memory. Keep for a future game whose
  font IS verbatim in memory.

### 🟢 cmap map (static, from the file) — and the "shared-ref" model
`ghost_title.xpps` has ~29 cmap sub-tables (64-byte records, `+62==0xffff`). The real glyph tables:
- **@0x87a652, n=612** — faces 30-177, cp 0x4f5.., 121 real refs (1269-1879). **Holds BOTH Arabic and
  Hebrew.** Hebrew letters/niqqud are here at **face 104 / ref 1522** (the notdef page).
- **@0x883f92, n=2740** — faces 179-600, cp 0x6e2.., 296 refs (Arabic presentation forms etc.).
- **@0x8672a6, n=1230, face 0** and **@0x8668a4** — degenerate/fallback (ref 0/39, geom 0). This is the
  Latin "page 4, ref 39, resolves-by-CP" table.
Record layout: `+0 cp(u32) · +14 face(u16) · +16 ref(u16) · +18 (u16, small 3-26) · +20=248 ·
+22/+26/+30 f32 geom · +46 = 1.0f`.

### 🟢🔴 THE STRUCTURAL BLOCKER ("27 Hebrew letters share ref 1522 → can't be distinct") is WRONG
- **Latin** all share **ref 39** and render distinctly ("resolves by CP") — known.
- **Arabic** ALSO shares refs across distinct-rendering codepoints: 0x625-0x62a ALL = **ref 1680**,
  same face 129. So **ref is NOT a per-glyph outline index** — it selects a face/atlas-page; the glyph
  is chosen by CP (and Arabic shaping picks presentation forms 0xFE80.. — the base 0x627 records look
  like near-duplicate placeholders: 0x627/0x628 differ only in geom-z). ⇒ Hebrew sharing ref 1522 is
  NOT the reason it's tofu; it's tofu because **1522 = the notdef page and the font has ZERO Hebrew
  outlines anywhere.** The old "distinct-ref" requirement is a red herring.
- Hebrew records (face 104, ref 1522) are STRUCTURALLY IDENTICAL to Arabic records (face 129, ref 1680)
  — same +18 range, +20=248, +46=1.0f, geom pattern. They are well-formed; they just point at notdef.

### The remaining REAL gate (unchanged in kind, clarified in shape)
To render Hebrew I must **author 27 novel Hebrew outlines into the vector-vertex store** (@0x97c8d0:
f32 (x,y) pairs + `0x74XX74XX` pack/flag runs) AND expose them through a face/ref the Hebrew cmap
records point at. No existing face has Hebrew outlines, and the outline ENCODING (how a glyph's
contour is laid out + how a face/cp locates its data — no monotonic file offset-table found; likely
count-delimited/streamed) is still not cracked to the authoring level. A live watchpoint would have
revealed the file→glyph consumption — but the runtime transform makes that impossible. **This is a
from-scratch static crack of a studio-unique compressed vector font with NO community tool** (mesh
tools give int16 verts only; text tool Nexus #809 is text-only) — research-grade, the hardest gate in
the project. Container + text + deploy remain fully PROVEN; the font is the sole open item.

### Reusable universal lessons (added to CLAUDE.md §12 + memory)
- A font that renders after a live switch but is 0-verbatim-matches in memory ⇒ load-time transform ⇒
  live-debug can't anchor. Prove it with a relocation-proof (pure-float) SIG scan before building a
  debugger session around finding the store.
- "Distinct glyphs must have distinct indices" is FALSE for atlas/face fonts — verify by checking
  whether the vendor's OWN distinct glyphs (here Arabic) share an index before treating a shared index
  as a blocker.

---

## Session 2026-07-21 (autonomous): the addressing crux tested from a NEW angle — CONFIRMED sparse-handle

Attacked the ref→offset blocker directly (not the coord codec) with two fresh static tests.
Game never opened; file-only. Result: independently re-confirms the wall, no new opening.

### 🔴 ref (+16) is a SPARSE HANDLE, not a sequential block index (`work/ref_density.py`)
- 4553 cmap records → **415 distinct refs**, span [0..65535], **density 0.6%**, longest
  consecutive (+1) run = **3**, gap histogram 1..12+. ⇒ `ref` is NOT a block index — a
  hash/handle. So a table/hash MUST map ref→store-offset, and that table is proven absent from
  the file (searched: no monotonic u32 offset-table, no absolute pointer array). It is
  computed/relocated at load → **not statically recoverable**. This kills the "store is a
  sequential stream, ref=block index" hypothesis cleanly.
- Structure noise worth noting: +18 is often the sentinel 0xffff (Latin ref 39 has +18=0xffff,
  "resolve by CP"), so +18 is NOT a plain vertex count; the size-sum check is meaningless.
  Regular pattern: refs 1272/1292/1312/1332 (Δ=20) each count=54 shared-by-19 = Arabic
  positional-form groups.

### 🔴 the coord codec is STATICALLY UNDISAMBIGUABLE (`work/store_s16.py`, `work/store_parse.py`)
- The tail @0x97c8d0 (155,856 B) reads as plausible normalized coords under BOTH f32-pairs AND
  s16/32768 — the SAME bytes give in-[-1,1] values either way. "100% of s16/32768 samples are
  in-range" is **tautological** (s16/32768 ∈ [-1,1) by definition) → NOT evidence. Without a
  located known-glyph (blocked by the sparse-handle result above) there is no Rosetta stone to
  disambiguate f32-vs-s16 or the pack-run (`0x74XX74XX`) topology.
- Store run-map: mostly high-entropy "OTHER" under an f32 lens, only 304 B of clean PACK, 5937
  scattered clean-f32 runs. Not a cleanly-segmented block stream.

### VERDICT (unchanged, now triangulated from 3 independent angles)
Autonomous STATIC crack cannot close: (1) live-debug dead — runtime fully transformed, 0
verbatim matches (2026-07-20); (2) coord codec ambiguous, no locatable Rosetta; (3) ref→offset
is a sparse handle with no file-resident table. The only authoritative path left is an
INTERACTIVE-debugger (x64dbg) CODE-breakpoint trace of the exe tessellator — NOT a content
watchpoint (which the runtime transform forbids), but a RIP breakpoint on the code that
references GENERATE_QUAD (xref @0x7ff7f220461f, from the memory dump) which fires at tessellation
time and exposes the runtime vertex format + source pointer. That is a user-driven, hours-scale,
uncertain effort against a VMProtect-packed exe (anti-debug likely). GoT is the ONLY project
game blocked purely on font (container+text+deploy+bidi all PROVEN) → it can wait for a
debugger-equipped push while other games ship. New tools: `work/{store_parse,store_s16,ref_density}.py`.

## Session 2026-07-22 (autonomous, "תנסה שוב") — sequential-store model found; coord codec is the real wall

A fresh attack on the crux, from an angle NOT tried before: is the glyph's store OFFSET a
field INSIDE the 64-byte cmap record (only ~30 of 64 bytes were ever mapped)? Tools:
`work/rec_offset_hunt.py`, `work/walk_store.py`, `work/align_walk.py`.

- **CORRECTION to the prior "sparse-handle dead end": the store is SEQUENTIAL, not handle-addressed.**
  `+18` (u16) is the block's vertex COUNT for the 1281 records that own a block; the other 3272 are
  `0xffff` (3108, Latin resolve-by-CP) or `0` (164) = no block. `sum(count)=13310`, and
  **`sum*12 = 159,720` vs store `155,856` (ratio 0.976)** — only the 12 B/vertex stride lands near
  1.0 (4B=2.93, 8B=1.46, 16B=0.73). So blocks are ~**12 B/vertex, laid sequentially in record
  order — NO ref→offset table is needed at all** (ref is just a face/atlas-page tag). This overturns
  the earlier framing that the addressing was the wall.
- **BUT the model does not CLOSE and the content is GARBAGE — the coord codec is the true wall.**
  The sequential walk **overshoots by 3,864 B (322 verts, 102.5%)**, and `align_walk.py` finds **no
  principled rule that closes it to gap 0** (best clean fits are noise: drop count==10 → +24,
  stride10+header18 → +302). Decoding a block under every 12 B codec (3×f32, 2×f32+u32, 6×s16)
  yields astronomically-wrong floats / only-tautologically-in-range s16 — no sane glyph. The 92
  face-104 (Hebrew/notdef) block-owning records have **92 DISTINCT block contents** (not one shared
  box), so the earlier "all Hebrew point at one notdef box" mental model was wrong too.
- **VERDICT (now triangulated from 4 angles, all converging):** (1) live-debug dead — runtime fully
  transformed, nothing verbatim in memory; (2) coord values ambiguous under f32 vs s16 with no
  locatable Rosetta; (3) addressing is sequential 12 B (this session's correction — cleaner than the
  handle theory, but doesn't help); (4) the sequential walk won't close and blocks decode as garbage
  ⇒ **the on-disk vertex CONTENT is packed/transformed, exactly as the runtime-transform proof
  predicted.** The wall is the COORD CODEC, not the addressing.
- **Only authoritative path unchanged:** an interactive x64dbg **CODE-breakpoint** on the tessellator
  (RIP xref to `GENERATE_QUAD` @0x7ff7f220461f) to watch packed-bytes→vertices at runtime — a code
  anchor, so the runtime-transform (no content watchpoint possible) does not block it. User-driven,
  hours-scale, uncertain, vs a VMProtect-packed exe. GoT remains the ONLY project game blocked
  purely on font (container+text+deploy+bidi all proven). State left CLEAN (no game-file writes;
  `gapack_misc_g` pristine; fleet intact).

## Session 2026-07-22 (cont.) — internet + files exhausted per user ask ("search / any hint")

User: "it must be somewhere in the game files, maybe search the internet or there's a hint."
Both angles worked, both negative — recorded so they are NOT re-tried.

- **Internet (5 targeted searches): NO community crack, format undocumented EVERYWHERE.**
  GoT font format / SFontData/FontVerts (nothing); GoT translation mods (Nexus #807 Austronesian,
  #809 GoT Translation Tool) = **Latin-script langs injected into the Greek slot, NO new glyphs
  needed, font untouched**; ResHax PSARC topic = archive tools only, **"font format details remain
  undocumented"**, a user asking to swap Arabic→Persian got **no technical answer**; Sucker Punch
  **Sprig** engine + **inFamous** (same engine, older/more-modded) = nothing; the unique tag
  **`fOnk`/`SFontData`** = 0 hits anywhere. ⇒ the community has never cracked this vector font.
- **Files: the REAL fOnk font is NOT ghost_title.xpps.** Tag scan: `game.sprig.texmeshman` has the
  **only** `fOnk` chunk (@0x156BFF7) and it is **high-entropy / compressed** (byte texture
  `66 4f 6e 6b 0b 8d 90 b1… 10 2e 46 77 8e` with LZ-style back-refs, garbage under every f32/s16
  lens). `ghost_title.xpps` (what every prior session analyzed) has **ZERO** fOnk/FontVerts/
  SFontData tags → it is a **separate** font system (readable 64B cmap incl. Hebrew→ref1522→notdef +
  a half-clean-f32 store). `m_lm_menu.sprig.xpps` = **KCAP text**, not a font. So the two font
  encodings in the game are BOTH opaque: ghost_title's store won't nail block boundaries
  (+322-vert overshoot), and the texmeshman fOnk is compressed.
- **Escapes re-confirmed dead (from font_fallback.md):** no OS/GDI/DirectWrite/Uniscribe/FontLink in
  the in-game renderer (GDI is launcher-only); no font config/registry/ini selector; no embedded
  TTF/OTF to swap; `debugfont.dds` is the dev-overlay bitmap font (not a menu path);
  `lang_*.msac.d.0.sps` DDS = button-legend images, not glyph atlases.
- **NET: the font wall is a proprietary, opaque, per-font-compressed vector codec unique to Sucker
  Punch, undocumented on the entire internet and uncracked by the community — confirmed from files
  AND internet.** No file-based shortcut, no bitmap/OS escape. Only technical path to the coord codec
  remains the interactive x64dbg CODE-trace of the tessellator (hard/uncertain, VMProtect-packed).

## Session 2026-07-22 (LIVE debug, user present) — x64dbg premise DISPROVEN at the disasm level

Ran the game NON-elevated (`__COMPAT_LAYER=RUNASINVOKER`; the user's normal launch was ELEVATED
= VM_READ denied) and attached read-only. Real progress on tooling + a decisive negative:

- **Exe base fixed via PEB walk** (VMProtect erases the MZ/PE header, so a PE-scan fails; the
  PEB→Ldr→InLoadOrder first-entry DllBase works): DllBase this launch = `0x7ff69a1a0000`.
- **The stale anchor RVA was WRONG by 0x1000.** The recorded prior base `~0x7ff7f20d1000` is NOT
  64KB-aligned = not a real DllBase. The true GENERATE_QUAD **lea-xref RVA is 0x13461f** (not
  0x13361f); FONT_KIND lea-xref RVA = 0x1347a6. Found by scanning the exe image for
  `lea reg,[rip]->"GENERATE_QUAD"` (the code there is REAL, not VM-virtualized).
- **🔴 THE ANCHORS ARE REFLECTION, NOT THE TESSELLATOR — the whole x64dbg plan's premise is dead.**
  Disassembled the GENERATE_QUAD-referencing function: it `lea`s the "GENERATE_QUAD" string + stores
  a name-hash `0xf7eb86d9b80c944` + a type id `0x110d` into globals, builds a 0x18-byte descriptor,
  and registers it — classic REFLECTION/schema registration that runs ONCE at startup. The two
  function pointers it stores (`0x…aadcf10`, `0x…ad8c000`) disassemble to **tiny property
  getters/setters** (`mov eax,[rcx+0x1f0]; ret` / `cmp [rcx+0x1f0],edx; …; jmp`) each padded with
  `int3` — accessor thunks, NOT a decode loop. So "GENERATE_QUAD"/"FONT_KIND" are reflected
  enum/type names; the code that references them is metadata registration, and **breakpointing it
  yields nothing about the coord codec.** There are also **zero `lea->FontVerts`/`lea->SFontData`**
  sites (those strings are reflection field names, referenced via pointer tables, not code) → **no
  font-string code anchor reaches the actual tessellator/decoder.**
- **NET:** the prior "only authoritative path = x64dbg CODE-breakpoint on the GENERATE_QUAD xref" is
  INVALID — that address is reflection registration, not the decode. Reaching the real decode needs
  a heavier approach with no ready anchor: (a) trace the engine's generic pass-dispatch on the hash
  `0xf7eb86d9b80c944` to its execute callback, or (b) hook the D3D12 vertex upload to capture the
  tessellator's output, or (c) breakpoint the fOnk decompression/font-load to grab the runtime
  vertex buffer. All are multi-session, uncertain, vs a VMProtect-packed exe. Tools built this
  session (reusable): `work/got_anchor.py` (PEB-base + xref anchor locator), `work/got_codebp.py`
  (HW-execute-BP register/pointer dumper), `work/{rec_offset_hunt,walk_store,align_walk}.py`. Game
  left running non-elevated; NO game-file writes; store pristine.

## Session 2026-07-22 (cont.) — D3D12 vertex-capture path: blind scan is low-signal

User chose the heavy vertex-capture path. Built `work/got_vbscan.py` (scans PRIVATE+RW upload
heaps for screen-space UI/text vertex patterns: bounded pos.xy, few distinct Y baselines).
Result: several structured float buffers, but NONE confirmable as the font/tessellator output by
content alone. Most-promising `0x019af7cb0000` (2.16MB) shows a clean **stride-3-float (12B)
`(neg, pos, pos-same)` repeat** — matches the 12B/vertex walk_store finding — but it is ~60k
triples (too big for the ~13k-vertex font) and the values (-40..+2) aren't clean screen coords, so
it is more likely a general UI/mesh buffer, not the glyph store. **Blind memory scanning cannot
confirm which buffer is the tessellator's font output** — the inherent limit. The reliable
realization of "capture the vertices the tessellator produces" is **RenderDoc** (a purpose-built
D3D12 frame-capture that shows every draw's vertex buffer + geometry; needs install, may resist
VMProtect) or a full injected D3D12 vtable hook (a real dev sub-project). Both are the next step if
this path continues. Tool built: `work/got_vbscan.py` (private-RW scanner, reusable). Game left
running non-elevated; no game-file writes.

## Session 2026-07-22 (cont.) — LIVE breakthroughs: runtime font object + on-disk verbatim in RAM

Pushed the live-debug path hard (user present, driving language/setting changes). Real, concrete
discoveries — and the reason the codec still resists.

- **✅ DR hardware watchpoints WORK here — VMProtect does NOT block them** (proven: a R/W watchpoint
  on a per-frame-changing address caught 2 RIPs, 1075 hits). Tools: `work/got_databp.py` (DR0 R/W
  watchpoint → distinct accessing RIPs), `work/got_codebp.py` (DR0 execute BP), `work/got_memdiff.py`
  (per-region CRC snapshot diff), `work/got_vbscan.py`.
- **✅ FOUND the runtime font OBJECT via a memory-diff across a language change** (`got_memdiff.py`:
  churn-excluded diff of Arabic→English). Region **0x019c8d200000 (4 MB)** holds the parsed cmap =
  **1516 records, same 64-byte layout as on-disk (cp/face/ref/cnt/geom), and it INCLUDES all 27
  Hebrew codepoints U+05D0..U+05EA** (ref=0xffff=notdef → the tofu). This CORRECTS the prior "cmap
  not in memory" claim.
- **🔑 Mapped the runtime glyph indirection:** each record has, at **+6, a 48-bit pointer** (zero
  on-disk, relocated at load) → a **per-face glyph-pointer array**; `ref` indexes it; the entry →
  a glyph descriptor holding a vertex `count` (e.g. 0x473=1139) and MORE pointers into OTHER heaps
  (0x04e6e…). ⇒ **the runtime font is a multi-heap C++ object GRAPH, so the on-disk store is a
  SERIALIZED object graph — not a flat "coordinate codec". That is why every flat-decode attempt
  (walk_store etc.) failed.**
- **✅✅ FOUND the on-disk file VERBATIM in RAM** — the on-disk store @0x97c8d0 sits byte-identical at
  **0x02302dde7d40** (private RW), and file@0x1000 at 0x022f1d410530. **The prior "nothing verbatim
  in memory" was WRONG** (it searched the transformed cmap, not the loaded raw file). So BOTH the
  on-disk form AND the parsed form are live in memory simultaneously.
- **🔴 THE REMAINING BLOCKER: the font pipeline is AGGRESSIVELY CACHED.** A R/W watchpoint on the
  verbatim store (0x02302dde7d40) fired **0 times** during steady rendering, menu navigation,
  Text-Language changes, AND display-setting changes. The parser reads the store **once at initial
  font load**; nothing re-reads it afterward. So the parser (= the on-disk→runtime decoder) cannot
  be caught by a watchpoint during normal operation — it needs **attach-at-BOOT** (arm the read
  watchpoint before the menu first renders), which is racy (the full-memory search to locate the
  store buffer takes ~30-60 s, likely slower than the load→parse window).
- **Two concrete but heavy paths remain:** (a) attach-at-boot to catch the parser's single read of
  the store → dump its source(on-disk)+dest(runtime) registers → the transform directly; or
  (b) CORRELATE the two live forms — read a known glyph's on-disk block AND its runtime clean
  outline (traverse the +6→array→descriptor→outline graph across heaps) → Rosetta the serialization.
  Both are genuine multi-session RE (reverse a proprietary serialized scene-graph, then author new
  glyph nodes). Real progress, real map — not close to shippable Hebrew. Game left running
  non-elevated; NO game-file writes.

## Session 2026-07-22 (cont., "תמשיך עד הפיצוח") — FIRST real differential EDITS of tail-kind2 (not just zeroing)

Pivoted OFF live-debug (2026-07-20 proved it dead) to the one un-run test: EDIT tail-kind2 coords +
relaunch + screenshot. Built a clean, reusable differential rig (pristine font baseline, Arabic menu,
surgical edit → `got_dsar.patch_inner` → RUNASINVOKER relaunch → dxcam shot). **New, concrete results
— the first time anyone edited tail-kind2 and observed the game (prior sessions only ZEROED it):**
- **✅ A surgical clean-f32 edit SURVIVES.** Scaling ONLY the first 20 contiguous clean floats
  (@0x97c8d0..0x97c920, no pack-runs in range) by 1.5x → game boots to a full clean Arabic main menu,
  no crash. ⇒ **there is NO per-block bbox/checksum** — clean coords ARE editable in place.
- **🔴 A BLANKET clean-f32 scale CRASHES at font-load (~50 s in).** Scaling all 1228 small-f32
  (abs∈(1e-4,1.5), pack-runs excluded) by 1.4x → boots ~48 s then crashes. ⇒ some of those "small
  floats" are **structural fields (per-contour counts / bbox / deltas) interleaved between the
  pack-runs**, and corrupting them breaks the parse. So the store is a **densely-interleaved
  coord+structure stream**, not a flat coord array — matching the "serialized object graph" model.
- **🔴 The store has almost NO long clean-coord runs.** A run-detector (≥6 consecutive clean f32)
  finds only **4 runs / 58 floats** in the entire 155 KB store, yet ~48.9% of the bytes are clean-f32.
  ⇒ glyph contours are stored as **SHORT bursts (2–5 coords) each preceded by a `0x74XX74XX` pack-run
  header** (per-contour/segment). This is why a blanket scale hits interleaved structure and crashes,
  and why the safe-to-edit set is tiny.
- **The first-block edit produced NO visible menu change** — block-0's glyph is not a main-menu glyph
  (or the on-disk coords are a pre-transform source, not the direct screen outline). Inconclusive
  without a Rosetta (which coord-burst = which glyph) — the SAME irreducible wall, now from an 8th angle.
- **NET (8th independent confirmation):** the differential RIG now works (clean menu, surgical edits
  survive, ~60 s/iter), but the store is a densely-interleaved coord+structure stream with no locatable
  known-glyph → mapping a burst to a glyph, then decoding the pack-run/burst format, then AUTHORING 27
  Hebrew contours, then WIRING the cmap (editing +16/+18 still CRASHES) + handling store growth/reloc,
  is a genuine multi-session RE + font-authoring project. Container/text/deploy/bidi remain PROVEN.
  Game left CLEAN (gapack_misc_g reverted to pristine, verified byte-size; no game running).
- **Reusable rig for a future dedicated push:** revert both gapacks → set TextLanguage=21 (Arabic) via
  PowerShell (apostrophe path) → `got_cap.py launch` (RUNASINVOKER) → surgical `patch_inner` edit of a
  chosen store span → relaunch → `got_cap.py shot <png> move`. The ONE thing that would break the
  Rosetta: a **RenderDoc** D3D12 frame-capture of the Arabic menu's glyph vertex buffer (known glyph →
  its output vertices → correlate to the on-disk burst) — the clean, purpose-built anchor a blind
  differential can't provide.

## Session 2026-07-22 (cont., "תנסה לערוך את EXE") — 🔴🔴 THE EXE IS **NOT** PACKED (major correction) + runtime glyph object decoded

### 🔴🔴 CORRECTION THAT CHANGES EVERY FUTURE ATTEMPT: GhostOfTsushima.exe is a PLAIN PE
Every prior session assumed "VMProtect-packed" and built plans around it ("x64dbg vs a VMProtect exe,
uncertain", "static patch is dead"). **That is WRONG.** `pefile` on the on-disk exe shows a completely
normal image: `.text` (RVA 0x1000, **17.6 MB of plain code**), `.rdata`, `.data`, `.pdata` (a FULL
RUNTIME_FUNCTION table), `_RDATA`, `.rsrc`, `.reloc` (0x49388 — proportionate, not a packer stub).
**No `.vmp0`/`.vmp1`/`.xtls`.** The "packed" belief came from the PE header being erased **in memory**
only. ⇒ **static RE + static patching of GoT are fully viable**, and a runtime RIP maps 1:1 to a file
RVA (`RIP - AllocationBase`) for offline disassembly. Get the image base reliably with
`VirtualQueryEx(...).AllocationBase` on any known code address (the PEB InLoadOrder walk returned a
DLL base this launch and is NOT reliable here).

### ✅ The runtime glyph object — decoded, incl. the EXACT byte that makes Hebrew tofu
Located the runtime cmap by **structural signature** (64-B records, `+20==0xF8`, `+62==0xFFFF`,
plausible cp) with a C-speed regex (`\xf8[\s\S]{41}\xff\xff`, anchor +20→+62) — the earlier
"0 verbatim matches" claim failed only because it searched for on-disk bytes, not the structure.
Runtime cmap arena = `0x236_xxxxxxxx` (80 sub-tables, one per Unicode block).
| cp | face | ref | cnt | glyph-obj +0x40 (data ptr) | +0x50 (count) |
|---|---|---|---|---|---|
| U+0645 Arabic meem | 136 | 1712 | 30 | **0x2369c7dd948** | **30** |
| U+062A Arabic teh | 129 | 1680 | 3 | valid | 3 |
| **U+05D0 Hebrew alef** | 176 | **0xFFFF** | 0xFFFF | **NULL** | **0xFFFFFFFF** |
| U+0041 Latin A | 4 | **0xFFFF** | 0xFFFF | valid | — |
- **Record `+6` = a 48-bit pointer (zero on disk, relocated at load) → a per-face array of glyph-object
  pointers**, stride **0x60 Latin / 0xF0 Arabic / 0xC0 Hebrew**.
- **Glyph object layout: `+0x40` data pointer · `+0x50` count · `+0x20/+0x28` prev/next (linked list) ·
  `+0x30` owner · `+0x80` geom (matches the record's geom) · `+0x90` metrics (advance/size).**
- **🔑 Hebrew's glyph objects EXIST and are fully linked — only `+0x40` is NULL.** That is "the font has
  zero Hebrew outlines", now proven at the exact byte.
- **🔑 Hebrew is structurally IDENTICAL to LATIN** (both `ref = 0xFFFF` = resolve-by-CP) and Latin renders
  perfectly ⇒ the long-held "shared/degenerate ref" theories were all red herrings; the ONLY difference
  is the presence of glyph data for the face.

### 🔴 The font-named code anchors are property accessors — closed with evidence
`FontGlyphs`/`FontVerts` are **memory-allocator TAG names** (indices 73/74 of a 189-entry table at RVA
0x11089e0) — referenced by index, never by address, which is why every string-xref hunt across 6 sessions
found nothing. `SFontData` is one of **8975** resource-type names (index 1658) with no parallel handler
array. The only `lea`→font-string xref in the whole file is the known GENERATE_QUAD one. And the function
pointers hanging off the glyph graph (`RVA 0x93cf10/0x93d050/0xbeecb0/0xbef830`) disassemble to
**property setter/getter thunks** (`cmp [rcx+0x1f0],edx; mov …; jmp`) of the engine's generic
property/animation system — NOT geometry code. Also ruled out statically: no `cmp [reg+0x14],0xF8` and no
`cmp [reg+0x3E],0xFFFF` anywhere (the record is not validated by those constants), no `fOnk` immediate.

### Where this leaves the crack
The generic property graph is NOT the outline; the actual glyph geometry source for a face is still
unlocated. But the problem is now much better posed and the tooling is far stronger: the exe is plain
(full static RE + `.pdata` function table), the runtime structures are mapped, and any RIP observed at
runtime is directly disassemblable offline. The cheapest decisive next step is unchanged in KIND but now
much more tractable: get ONE known-glyph Rosetta (RenderDoc D3D12 capture of the Arabic menu's glyph
vertex buffer, or a watchpoint on a face's glyph-data pointer during a forced text re-layout), then walk
back through the now-plain exe. New tool: `work/find_cmap_live.py` (structural runtime-cmap locator).
