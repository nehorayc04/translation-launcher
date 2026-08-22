# Assassin's Creed Black Flag Resynced — Phase-0 recon (read-only, 2026-07-11)

Install: `C:\Games\Assassin's Creed Black Flag Resynced`. This is **NOT** the 2013 classic
Black Flag — it is Ubisoft Singapore's full 2026 remake ("Black Flag Resynced", released
2026-07-09, 2 days before this recon), rebuilt on the **same Anvil engine generation as
Assassin's Creed Shadows** (RT/RTGI, DirectStorage, XeSS, AMD FSR frame-gen, GFSDK Aftermath —
all confirmed present; HUB trailer files reference Mirage/Odyssey/Origins/Valhalla/Shadows).
No file was modified during this recon — read-only probes only.

## Container
- `.forge` files, magic `scimitar\x00` + **version 50** (uniform across all 157 forges
  surveyed — `tools/acbf_forge_probe.py survey`). Newer than every previously-cracked
  version in this repo (AC2=25, AC Unity=27, AC Shadows=42).
- Per-resource chunk wrapper reuses the **exact same magic** as AC Shadows'
  `0x57FBAA33 + 0x1004FA99` Oodle-Kraken chunk header — the low-level codec is very likely
  unchanged (Oodle Kraken). No `oo2core_*.dll` ships (statically linked, same as AC Shadows /
  BF6) — borrowing a DLL from another installed title (as done for AC Shadows/GoWR) would work.
- **v50's TOC/index layout does NOT match v25 (AC2) / v27 (AC Unity) / v42 (AC Shadows)
  byte-for-byte.** Tested the AC-Unity-style `index_off@13 → count@index_off →
  rec_start=index_off+0x70, 20B records` layout against 3 real forges (`WhiteRoom`,
  `boot`, `shared_00`): a plausible `count` decodes at the expected offset (1050/0x41a is a
  FIXED header size across every file size tested, not a per-file pointer), but the bytes
  immediately after do **not** look like a flat record array — full resource chunk data
  (the Oodle chunk magic) starts only ~30–40 bytes later, far too little room for the
  declared count of records (126,249 for `DataPC_boot.forge`). So v50 needs its own
  dedicated index/chunk-walk reverse-engineering — NOT a 10-minute reuse of prior code.
- **Lead, worth following up:** a keyword string-scan of `DataPC_boot.forge`'s head+tail
  400 MB (`acs_forge_probe.py strings`) found mostly noise in the head, but the **tail**
  (last ~400 MB of the 25.6 GB file) is dense with genuine plaintext class/property names
  (`GameContext`, `QuestExtensionInstance`, `TextStyleController`,
  `ResourceVaultContextValueSetting`, `UI_TextHelper_*Hint`, and — directly relevant —
  **`dsArabic`**). This strongly suggests the real name/reflection metadata table (the
  AC-Unity-equivalent "descriptor table") sits near the **end** of the archive, not the
  start — a concrete starting point for the next cracking session.
- No community tool support exists yet for this specific title/version (it's 2 days old;
  web search found no AnvilToolkit profile or Nexus translation mod for it — unlike AC
  Unity, which already had a working free tool + a 2025 community English-loc mod to prove
  the round-trip).

## Localization — the decisive positive finding
- `localization.lang` (plaintext JSON at the game root) declares:
  - `text.languages` and `subtitles.languages` **both include `ar-SA`** (Arabic) — full
    text AND subtitle RTL support, not just a UI-only stub.
  - `sound.languages` has **no** Arabic (no Arabic VO recorded) — same as every other
    title in this project; English voice stays intact regardless of text language.
- `streaminginstall.ini` confirms Arabic is a genuine, separately-flagged Ubisoft Connect
  language pack (`[UbiConnectLanguagePacks] ara=65582`, text-only — no `,full` suffix,
  unlike the 8 voice+text languages). `videos/ar/` (Epilepsy/WarningSaving/disclaimer)
  confirms Arabic localized video assets ship too.
- **Activation lever found — a plain registry STRING, not an ini/JSON edit:**
  `uplay_install.state` lists per-language registry keys of the form
  `HKEY_CURRENT_USER\SOFTWARE\Ubisoft\Assassins Creed Black Flag Resynced\Language` with
  values `en-US`, `fr-FR`, …, **`ar-AA`**, `ru-RU`, `pl-PL`, `pt-BR`. Setting that key to
  `ar-AA` is very likely how the game picks its text language — simpler than every other
  game in this project (no `UserSettings.json` walk, no `.ini` regex, no XML).

## Font — ZERO injection work needed (verified directly, same finding as AC Shadows)
`resources/AvenirNextWorld-Regular.ttf` (the shipped main UI font, same family AC Shadows
uses) already contains, with **real glyph outlines** (not `.notdef`):
- **All 27 Hebrew letters U+05D0–05EA** (checked individually, 27/27 present, `contours=1`
  on sampled glyphs — not empty)
- 20 niqqud marks + Hebrew punctuation (maqaf, gershayim, geresh)
- 104 Arabic + 132 Arabic-presentation-form glyphs (for the shipped Arabic UI)
This is a TrueType (`glyf`) font — a straightforward glyph-merge target if any OTHER
in-game font turns out to lack Hebrew (not yet checked — only the two secondary CJK fonts
`DFPT_B5_v2.ttf` / `NotoSansKR-Medium.otf` were sampled and, as expected, have none; those
are CJK-only fallback faces, not used for Latin/Hebrew text).

## Anti-tamper / risk
- No EAC/BattlEye — single-player only, consistent with every AC title in this project.
- **Denuvo is present per public coverage of this exact release**, and the main exe's PE
  section table confirms `.vmp0`–`.vmp3` (VMProtect-virtualized code sections) —
  independently verified by parsing the PE header directly (`tools/` scratch, not kept).
  This protects the **executable's code**, not general data files, by design (Denuvo has
  never data-checksummed arbitrary game archives in any AC title analyzed in this
  project — AC Valhalla/Odyssey/Origins all ship Denuvo yet have working asset/cosmetic
  mods in the wild). Real risk here is *modest, not proven* — flagged as a caveat because
  this is the first Denuvo-confirmed title in the AC lineup this project has touched
  (AC2/Unity/Shadows are all Denuvo-free).

## Verdict
**🟡 GO-WITH-CAVEATS.** The two historically hardest gates in this whole project — a real
Arabic RTL text+subtitle locale, and a font that already ships full Hebrew glyph coverage —
are BOTH closed here for free, with an unusually simple registry-based activation lever on
top. That is a stronger starting position than most other games at this stage. The one real
gate is the **container**: this is a brand-new (2-day-old) forge sub-version with no
existing community tooling, and its TOC/index layout needed a fresh crack (not a drop-in
reuse of the AC2/Unity/Shadows code) — the tail-of-file string lead is the concrete next
step. Denuvo is a secondary, likely-benign caveat rather than a blocker. Nothing was
written to any game file this session.

## Tools
- `tools/acbf_forge_probe.py` — read-only: tries the AC-Unity-style TOC layout against a
  v50 forge and reports whether the offset/size invariant holds (currently: no, on all 3
  forges tested — see notes above).

---

# Phase-1 container + loc crack (2026-07-10, user owns the game — legit key)

The user bought a legit key, so in-game verification is unblocked. This session
CRACKED the scimitar-v50 container + the loc record format from scratch (no
community tool exists for v50) and mapped where localization actually lives.

## ✅ scimitar-v50 .forge container — FULLY CRACKED (reader 100% verified)
`tools/acbf_forge.py`. v50 differs from v42 (AC Shadows) ONLY in how the TOC
pointer is stored; the 24-byte record layout is unchanged.

    Header @0:  "scimitar\0" ; u32 version(=50) ; u32 @13 = 0x41a (CONSTANT,
                pointer to the manifest descriptor — v42 stored a u64 index_off here)
    Manifest descriptor @0x41a:
        u32  count
        u64  tocOffset          # u64! boot.forge's TOC is >4GB into the file
        u32  0 ; u64 0xFFFF...FFFF (sentinel)
    TOC @tocOffset: count x 24-byte records  <QIIII>:
        u64 offset ; u32 timestamp ; u32 flags ; u32 size ; u32 nameHash

Verified invariant `off[n+1]==off[n]+size[n]` = **100% on every forge**:
TitleScreen 95/95, boot_patch 1300/1300, shared_00 48925/48925,
**boot.forge 126248/126248** (25.6 GB, 126,249 resources). Each record's
`offset` points directly at the resource's first CFD (no per-resource header).

## ✅ Oodle-Kraken + CompressedFileData (CFD) — decoder working
`tools/acbf_cfd.py` (ported from acs_cfd; format UNCHANGED in v50). A resource
blob = one or more CFDs:

    u64 Magic = 0x1004FA9957FBAA33  (bytes 33 aa fb 57 99 fa 04 10)
    u8[7] cinfo ; i32 blockCount
    BlockInfoData: blockCount x { i32 uncomp, i32 comp }
    CompressedData: blockCount x { u32 adler=zlib.adler32(comp,0), u8[comp] }

Oodle via the borrowed `C:\Games\Battlefield 6\oo2core_9_win64.dll` (game ships
none — statically linked). ⚠️ **THE bug that hid most loc:** a naive "each
0x57FBAA33 is an independent 0x1F-header chunk" walk only works for a SINGLE
block; a multi-block CFD puts ALL block sizes in one table BEFORE the payloads,
so the naive walk misreads block1's info as block0's payload and stops early.
Fixed in `acbf_loc.decode_blob` (proper CFD walk) — English jumped 5,744→7,941.

## ✅ v50 loc record format — CRACKED (English readable)
`tools/acbf_loc.py`. Localized strings are inline field records inside a
serialized ScimitarClass (same family as AC Shadows' FADE9F44, but the text
offset shifts +1):

    [ lineID u64 ] [ 0xFADE9F44 u32 ] [ u16=0x0001 ] [ u16 ] [ u64 groupID ]
    [ u16=0x0000 ] [ charLen u32 @tag+18 ] [ UTF-16LE text @tag+22 ]

Verified on real strings ("Roberts!", "[small effort…", "Calm… little").
`lineID` is the cross-language key.

## 🔴 KEY FINDING — this install ships ONLY English text
Exhaustive crash-isolated scans (subprocess-per-batch so an Oodle segfault only
loses one batch; **0 crashed batches** across full runs):
- **boot.forge (all 126,249 resources):** the ONLY real text is **7,941 English
  dialogue/subtitle lines** (nameHash `0xa5b3bea0`, FADE9F44). Spoken lines
  ("The Wheel is yours, Captain."), incl. shanties as `[SP][spanish](english)`.
- **shared_00.forge (48,926):** no text at all (meshes/data).
- **Charleston region forge, frontend RED forges:** no text.
- **NO Arabic anywhere.** Every "Arabic run" a detector flagged was **numeric
  u16 data** in the 0x05xx-0x06xx range (vertex/index/mesh data), or a **256-entry
  consecutive U+0600–06FF table** inside ship-mesh resources — never real words
  (real words are non-monotonic). Confirmed with a word-like (non-monotonic,
  ≥8-letter) Arabic detector.
- **The ATK char-index LocalizationPackage (class hash 0x6E37B1AF) is ABSENT**
  (0 hits); the 8 `0xD28389B5` marker hits are 112-byte non-loc resources.
- **The UI/menu strings ("New Game", "Options") are NOT in the installed forges
  in any detectable form**, and neither are any non-English languages.

`uplay_install.state` registers all 13 text languages incl. **`ar-AA`** as
selectable, and `localization.lang` declares `ar-SA` in text+subtitles — but the
**DATA is not installed**. `streaminginstall.ini` flags Arabic as a SEPARATE
Ubisoft-Connect language pack (`ara=65582`, text-only). ⇒ the FitGirl repack's
base ships English dialogue only; UI + all non-English text (incl. Arabic)
download on demand via Ubisoft Connect and are absent here.

## Path forward (now that the user owns a legit key)
The Arabic-slot hijack (the RTL Hebrew plan) needs Arabic loc data present to
edit. It is not in this repack. Cleanest path: **install the game via the legit
Ubisoft Connect with Arabic (+ the full text) selected**, which downloads the
Arabic loc; then hijack it for Hebrew (font already ships all 27 Hebrew glyphs;
activation is the plain `…\Language = ar-AA` registry string). The v50
container + CFD + loc-record codecs built this session are ready to read/edit
that data once present. (Fallback if Arabic can't be obtained: build the Hebrew
loc into the English FADE9F44 slot — but English is LTR, so no engine RTL.)

## Tools built this session (`tools/`, read-only, pure-Python)
`acbf_forge.py` (v50 reader — list/verify/raw/hash) · `acbf_cfd.py` (CFD
decode/encode + roundtrip) · `acbf_loc.py` (FADE9F44 extractor: scan/extract/
toc-scan/chunk) · `acbf_scan_batch.py`+`acbf_scan_all.py` (crash-isolated
subprocess scanner) · `acbf_lpkg_batch.py` (char-index marker scan) ·
`acbf_locmap.py` (definitive loc map) · `acbf_walk.py`/`acbf_findloc.py`/
`acbf_hashfind.py` (exploration). Oodle DLL via env `ACS_OODLE_DLL`.

---

# ⭐ CORRECTION + BREAKTHROUGH — Arabic IS installed (char-index loc CRACKED) (2026-07-16)

**The earlier "only English installed / no Arabic" conclusion was WRONG.** The
user confirmed the game renders full Arabic in-game (Text=ar-SA). The Arabic was
hidden because (a) it is a **char-index / fragment-tree serialization** (text =
indices into a char dictionary, NOT literal UTF-16 — so every raw-UTF-16 and
FADE9F44 scan missed it), and (b) the marker scan that should have found it used
the **buggy single-block chunk walk** that truncated the multi-block loc-package
resources to ~112 bytes. With the FIXED multi-block CFD decoder they decode to
~800 KB each.

## ✅ v50 char-index LocalizationPackage — FULLY CRACKED (`tools/acbf_locpkg.py`)
The UI + ALL languages (incl. Arabic) live in resources with **nameHash
`0x6e3c9c6f`**, anchored on the IndexedData marker **`0xD28389B5`**. v50 layout
(all big-endian) — reversed from scratch this session (AC Shadows' u16 string-
table layout does NOT apply):

    u32 marker=0xD28389B5 ; i32 num ; num bytes of payload:
      u16 MaxIndexSize ; u16 fragCount ; fragCount x {u16 right,u16 left}  (tree)
      u16 recordCount  ; recordCount x { u64 stringID, u32 codeOff, u32 off2 }
      string codes at codeOff (fragment-index byte stream); a string ends where
      the next-larger codeOff begins.  fragment decode: leaf(left==0)->chr(right),
      node-> cache[left]+cache[right]; code byte b< MaxIndexSize -> frag[b+1],
      b==255 -> i16 escape, else 2-byte escape (-MaxIndexSize*255).

Proven: boot.forge idx 27722 decodes to **11,033** clean settings-menu strings
in German/Italian/Russian/French/Polish/Portuguese ("Allgemein", "Combattimento",
"Мышь и клавиатура", "Graphismes", …).

## ✅ The ARABIC slot — FOUND + EXTRACTED (the Hebrew-hijack target)
The 36 `0x6e3c9c6f` resources come in per-language pairs (a ~11,000-string UI
package + a ~5,345-string subtitle package). **Arabic:**
- **idx 27724 = Arabic UI, 11,000 strings** (10,904 Arabic) — `تصويب الحركة`
  (Aiming), `عام` (General), `القتال` (Combat), `الرسوميات` (Graphics), …
  → `extract/arabic_ui.json`
- **idx 27725 = Arabic subtitles, 5,345 strings** (5,239 Arabic) —
  `أتذكرك. الفارس من هافانا…` → `extract/arabic_subs.json`

Total Arabic scope ≈ **16,345 strings**. (English source = the FADE9F44 dialogue
[7,941] + the English char-index UI package; each language pair is UI+subs.)
Markers seen in subs: `[SP]` (Spanish-flavour), `[ono]`, `(بحماس)` (stage dirs).

## Where this leaves the Hebrew project — 🟢 GREEN, read-side COMPLETE
Everything to READ is cracked and verified: forge v50 container, CFD codec,
FADE9F44 English source, char-index LocalizationPackage (UI + subs, all langs),
and the Arabic slot is extracted. The Hebrew plan (hijack the Arabic slot; font
already ships all 27 Hebrew glyphs; activate via `…\Language = ar-AA` registry)
is intact and now DATA-backed. Remaining (write side):
1. char-index ENCODER (build a LocalizationPackage from Hebrew text) + identity
   round-trip proof (re-encode Arabic unchanged → byte/semantic-identical → loads).
2. forge repack / override write-back of resources 27724+27725.
3. delegate Arabic/English → Hebrew translation (~16k strings; per project rules).
4. menu-proof in-game (now possible — the user owns a legit key).

New tool: `tools/acbf_locpkg.py` (info/dump). Corpus: `extract/{arabic_ui,
arabic_subs,en}.json`.

---

# ⭐⭐ WRITE-SIDE CRACKED + HEBREW MENU-PROOF DEPLOYED (2026-07-16)

The v50 char-index LocalizationPackage layout was FULLY reversed (byte-identical
verbatim re-serialize confirms it):

    u16 MaxIndexSize ; u16 fragCount ; fragCount x {u16 right,u16 left}
    u16 recordCount ; recordCount x { u64 stringID, u32 codeOff, u32 lenTableOff }
    lenTable: recordCount x u32 (each = that string's code-byte length)
    code streams (fragment-index bytes) @codeOff

- **ENCODER** (`acbf_locpkg.build_payload`) — flat leaf dictionary (one fragment
  per unique char) + single/2-byte/i16 escapes. **Semantic round-trip on the
  full 11,000-string Arabic UI = 0 mismatches**; verbatim container re-serialize
  = byte-identical (630,790==630,790).
- **`acbf_locpkg.rebuild_resource`** — patch strings → rebuild payload, preserving
  the bytes before the marker + after the payload.
- **WRITE-BACK = append-relocate** (`work/build_menu_proof.py`): re-CFD-encode the
  patched resource (`acbf_cfd.build_cfd`), append it at boot.forge EOF (16-align),
  repoint TOC record 27724's offset+size. Reversible (backup = the 24-byte TOC
  record + original file size; `--revert` restores + truncates). Note: the new
  Oodle-compressed blob (367 KB) is actually SMALLER than the original (381 KB).

**DEPLOYED to the live legit install** (`C:\Games\...\DataPC_boot.forge`, game
was closed; only upc.exe running). 6 Arabic-UI strings patched to Hebrew:
متابعة→המשך, خروج→יציאה, تحميل→טעינה, القصة→עלילה, حفظ→שמירה, عام→"כללי ZZ-HEB-OK".
**On-disk re-read verified 6/6.** Awaiting the user's in-game screenshot (Text=
ar-SA already set) to confirm Hebrew renders (font ships Hebrew glyphs; bidi=the
engine's ar-SA RTL path — the proof decides logical-vs-visual, like other games).
Revert: `python work/build_menu_proof.py --revert`.

**This proves the ENTIRE pipeline end-to-end at file level** (forge read → CFD →
char-index decode → Hebrew patch → char-index encode → CFD → forge write-back →
re-read = Hebrew). Only the in-game visual (render + RTL) remains to confirm.

## מסמכים קשורים
- באותה תיקייה: [[games/acblackflag-resynced/RESEARCH_MODPATH|RESEARCH_MODPATH]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#acblackflag|CLAUDE_INDEX_games]]
