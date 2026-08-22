# UNCHARTED: Legacy of Thieves Collection — FEASIBILITY

## Verdict: 🟢 **GO — easy/medium tier.** One of the strongest Phase-1 positions in the project.

Four of the six pillars are **closed and proven offline in a single session**, entirely by reusing
the TLOU Part I toolchain. Two gates remain, and both are decided by one or two in-game proofs.

| Pillar | State |
|---|---|
| Container (PSARC v1.4 / Oodle) | 🟢 **Cracked — reused unchanged.** Repack proven: identity rebuild same size + content-identical, Hebrew edit round-trips with all 47 other entries byte-identical, **0.1 s** |
| Text codec | 🟢 **Written + self-tested.** `tools/unc_loc.py`, identity re-encode **byte-identical** on all 3 file types |
| Scope / tokens | 🟢 **36,610 unique strings / 1.15 M chars**, and a corpus with **0 braces, 0 tags, 0 entities** — 252 `[TOKEN]` and 8 printf specs in total |
| Reference panel + gender | 🟢 **Free.** 100 % sid parity across 23 languages ⇒ 22 oracle languages per line; ~10 of them gendered (rus/pol/cze + fre/ita/spa/sas/por/bra/gre) |
| Activation | 🟢 **One word in one text file** (`steam_settings/force_language.txt`) |
| DRM / anti-cheat | 🟢 **None.** No Denuvo, no VMProtect, no EAC/BattlEye; unpacked PE |
| **Font** | 🟡 **Injection required** — 0/27 Hebrew in all 9 bitmap atlases *and* all 17 Iggy/Flash fonts. Format is the easiest yet (plain-text BMFont + uncompressed RGBA TGA), but there are **two surfaces** |
| **bidi** | 🟡 **Undetermined** — the menu proof decides, and there is an unusually good chance it comes out free (below) |

Two bonuses that materially cut the work:

* **One archive serves both games.** `uncharted4/text2.psarc` and `thelostlegacy/text2.psarc` are
  byte-identical and hold Uncharted 4 *and* The Lost Legacy text. **A single translation ships two
  games** — the best effort/output ratio in the project.
* **The repack is instant** (0.1 s for the 24 MB text archive), so the build→deploy→test loop costs
  nothing. Contrast CP2077 (~76 s onscreens, hours for subtitles) or GoWR (4 h DLC bake).

---

## The decisive question: is the dormant `ara` slot alive?

This is the one finding that could move the project from "LTR hijack + hand-baked VISUAL" (the
TLOU/AC2/Anno class) to "real RTL locale" (the CP2077/SM2/Witcher class).

**The evidence that it might be:**

1. The exe's language table is a list of triplets — *loc code · hud-flash-keys symbol · font name* —
   and it contains a full **`'ara'` / `*hud-flash-keys-ar-ae-array*` / `arabic`** row, alongside
   `LANGUAGE_ARABIC` and the BCP-47 tag `ar`.
2. The third field of that triplet is demonstrably the **font asset name**: `rus`→`russian`,
   `chi`→`chinese`, `kor`→`korean`, `jpn`→`japanese` are *exactly* the `.fnt` files that ship in
   `fonts.psarc`. So the Arabic row points at an `arabic.fnt` that simply **was not shipped on PC**.
3. **Uncharted 4 shipped Arabic subtitles on PS4** for the MENA region — this is real shipped code,
   not a dead enum left over from a template.
4. Language availability is **data-driven**: `LanguageManager::FindPlayGoAvailableLanguage` and
   `m_languages[preferredTextAndSubtitleLanguage].IsTextSupported()` — a language becomes usable when
   its files exist.
5. The Flash UI already carries a **U+200E (LRM)** glyph as its own one-glyph font.

**The evidence that it might not be:** `supported_languages.txt` omits Arabic; no `ara.*` loc file
and no `arabic.fnt`/`arabic_00.tga` ship; and the only `rightToLeft` string in the exe belongs to a
**focus-navigation** enum (`topDown/bottomUp`, `leftToRight/rightToLeft`, `pressed/released`) — that
is UI navigation, **not text bidi**. So RTL text layout is *not* independently confirmed.

**⇒ Do not assume it. Test it.** Proof B in PIPELINE adds `ara.common` + `ara.subtitles` +
`arabic.fnt`/`arabic_00.tga` and selects the slot. One launch answers it:

* **If it loads and reorders** → store Hebrew **LOGICAL**, no VISUAL bake, best possible outcome.
* **If it loads without reordering** → still a clean dedicated slot; store **VISUAL**.
* **If it does not load at all** → fall back to the LTR hijack (below). Nothing is lost.

---

## Fallback plan if `ara` is dead: which LTR slot to hijack

| candidate | why | cost |
|---|---|---|
| **`eng`** | **Zero user action** — the game already boots English (the Until Dawn outcome). Requires injecting Hebrew into `main.fnt` | Latin atlas is 84 % full; needs the free alpha rows or a bigger atlas |
| **`rus`** | Has its **own dedicated atlas** (`russian.fnt` / `russian_00.tga`, Myriad Pro Light) whose 63 Cyrillic glyphs can be **replaced** by 27 Hebrew ones — plenty of room, Latin untouched | user must set the language to Russian |
| **`uke`** | `LANGUAGE_UKENGLISH` = **en-GB**, whose text is essentially identical to `eng` ⇒ **the cheapest thing in the game to sacrifice** | may not be selectable via the Steam language name |

Recommendation: try **`eng`** first (best UX), keep **`rus`** as the guaranteed-room fallback.

---

## Font gate — the real remaining work

Two independent renderers, and **which one draws what is not yet known**:

* **(a) Native bitmap atlases** (`main.fnt` + `main_00.tga`, and the per-language variants). The
  format is the friendliest encountered in this project: the descriptor is **plain text** and the
  atlas is **uncompressed 32-bit RGBA TGA** — no BC7 encoder (AC Mirage), no SDF (AC Shadows), no
  DXT5 (Plague Tale), no binary glyph records (GoWR). Injection is: rasterize 27 glyphs into free
  atlas space, append `char id=` lines. Measured free space: the **alpha channel is only 47.9 % used
  and rows 69→128 are completely empty** (~15 k px), with the option to enlarge `scaleW/scaleH` if
  the engine honours the descriptor (unproven — test before relying on it).
* **(b) Iggy / Flash** (`fontlib.iggy`, `fmenu.iggy`). 17 `DefineFont3` faces, **all 0/27 Hebrew**.
  Iggy is RAD's proprietary compiled-Flash format; editing it is materially harder than the atlas.
  Mitigation to test first: the `.swf` sources ship alongside in `flash1.psarc`, so the cheapest
  route may be to patch the SWF and let Iggy consume it, or to find that the menus fall back to the
  atlas font for the hijacked locale.

**The menu proof is designed to identify the split in a single launch** (patch a menu string *and*
a subtitle string, inject only into the atlas, and see which one renders Hebrew vs tofu).

---

## Risks, honestly stated

| risk | severity | note |
|---|---|---|
| Iggy menu fonts | **medium** | The one genuinely new reverse-engineering surface. Subtitles may well be fine while menus need work; a subtitles-first ship is viable (the AC Unity precedent — but there the *text* was unreachable, here it is not) |
| Atlas capacity | low | Alpha channel has room for most of 27 glyphs; enlarging the atlas or hijacking `russian_00.tga` both solve it outright |
| bidi unknown | low | Both outcomes are already handled — VISUAL is a solved, reusable transform (`universal` + RDR2/TLOU implementations) |
| Repack accepted in-game | low | PSARC has no whole-archive checksum, name hashes are md5(path) and content-independent, and the identical writer is proven in-game on TLOU Part I |
| Long UI blocks | low | 119 strings > 140 chars (patch notes, privacy policy) using a literal `\` separator — preserve it |

**No risk from:** DRM, anti-cheat, archive integrity checks, encryption, compression licensing
(the game ships its own Oodle DLL), or game updates (this is a 2022 title that is no longer patched).

---

## Effort estimate

| stage | estimate |
|---|---|
| Phase 1 (this document) | ✅ **done** |
| Menu proof A + B | ~1 session incl. the font injector |
| Translation of 36,610 lines | delegated ([[delegate-all-translation]]) — comparable to TLOU1 (32,881) / GoWR (48,886); the free 22-language panel makes it a New-Era pass |
| Build + deploy | minutes (0.1 s repack) |
| Publish | standard (GitHub release + Worker slug + Supabase row) |

## מסמכים קשורים
- באותה תיקייה: [[games/uncharted_lot/PIPELINE|PIPELINE]], [[games/uncharted_lot/RECON|RECON]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#uncharted_lot|CLAUDE_INDEX_games]]
