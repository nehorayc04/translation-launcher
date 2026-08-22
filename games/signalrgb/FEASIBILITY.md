# SignalRGB Hebrew — Feasibility

## Verdict: 🟢 **GO — easiest tier. PHASE 1 COMPLETE, every gate closed in-app.**

| Gate | Status |
|---|---|
| Container | 🟢 none — Qt `.qm` embedded in the exe, uncompressed, unencrypted |
| Text codec | 🟢 **written and byte-identical on 8/8 shipped files** (`work/qm.py`) |
| RTL slot | 🟢 official Arabic locale, fully translated by the vendor |
| Scope | 🟢 1,838 strings / 55.5k chars — a single pass, no fleet |
| Deploy | 🟢 **delta-0 in-place patch PROVEN in-app** |
| Font | 🟢 **PROVEN in-app — zero tofu** |
| bidi mode | 🟢 **PROVEN LOGICAL — store natural Hebrew, no reversal, no `&rlm;`** |
| Size budget | 🟢 delta-0 fits at any realistic ratio (see below) |
| Layout mirroring | ⚠️ **PROVEN ABSENT — cosmetic, not data-fixable** |

## ✅ Menu proof PASSED in-app (2026-07-20, user screenshot)

`work/build_menu_proof.py --deploy`, Settings screen. One image closed
everything at once:

* **`ZZ-SRGB-OK-ZZ`** rendered in place of the *About* nav header → the
  delta-0 patched `.qm` really loads out of the exe's qrc.
* **`שמע · ניטור · מאווררים · התראות · תוספים · שפה`** rendered clean in the
  nav, same weight and size as the surrounding Arabic → **the font gate never
  existed**; Qt's system-font fallback covers Hebrew for free.
* Every Hebrew word is in **correct letter order** → the engine runs the UBA
  itself ⇒ **store LOGICAL**. Never pre-reverse, never inject `&rlm;`/RLE.
* Untouched entries still render Arabic → a **partial** translation degrades
  gracefully, so the pass can ship incrementally.
* Arabic paragraph text auto-right-aligns and an embedded URL stays LTR inside
  it → long Hebrew paragraphs will lay out correctly too.

**⚠️ The app does NOT mirror its layout.** The nav panel stays on the left and
its labels stay left-aligned — for Hebrew *and* for the vendor's own Arabic.
Text direction is right, box direction is not, and a translation file cannot
change that. Consequence: per [[rtl-dont-flip-direction-words]], **no
direction word gets flipped** ("the left panel" stays "הפאנל השמאלי").

Optional untested lever for a later round: Qt derives
`QGuiApplication::layoutDirection()` from a translation of the string
`QT_LAYOUT_DIRECTION` = `"RTL"` (context `QGuiApplication`), which the shipped
Arabic does **not** contain. `patch_exe.py --deploy --rtl` adds it. Try it as
a separate round — one variable at a time.

## Text format — solved

`work/qm.py` is a complete pure-Python Qt `.qm` reader **and writer**,
including Qt's `elfHash` lookup table. Validation is the strongest kind
available: it re-builds each of the **8 shipped `.qm` files byte-for-byte
identically** (`python work/qm.py` → `byte-identical: 8/8`). Anything it
writes is therefore structurally what Qt itself would have written.

Discovered while doing that: blocks are emitted in the order
`Language, Hashes, Messages, Contexts, NumerusRules, Dependencies`, tags
6/7/8 carry **u32** lengths (not u8), and each message's item order is
`Translation*, [Comment], [SourceText], [Context], End`.

## Deploy — delta-0 in-place patch of the embedded Arabic `.qm`

There is no disk override: `:/i18n/SignalRgb_<locale>` is a qrc path, and the
binary never registers an external `.rcc`. So the exe is the deploy target.

Two facts make an in-place patch clean:

1. Every Qt resource is stored as `{u32be length}{payload}`, and the u32
   before each embedded `.qm` **equals its parsed size** (verified on all 8).
2. Qt's `.qm` reader stops at the first `tag == 0`, so the file can be
   **NUL-padded** to an exact length.

⇒ a Hebrew `.qm` no larger than 226,603 bytes is padded to exactly that and
written over the Arabic one. No offset, no length prefix and no other
resource moves. Nothing else in the 114 MB exe is touched.

### The size budget — and the lever that guarantees a fit

The Arabic `.qm` fills its slot **exactly**, so a naive Hebrew build
overflows as soon as Hebrew is ~0.9× English or longer:

```
ratio 0.85 -> as-is 224,201  FITS        minimal-prefix 130,611  FITS
ratio 0.95 -> as-is 235,059  OVERFLOW    minimal-prefix 141,469  FITS
ratio 1.00 -> as-is 240,489  OVERFLOW    minimal-prefix 146,899  FITS
ratio 1.25 -> as-is 267,633  OVERFLOW    minimal-prefix 174,043  FITS
```

**The lever (`work/size_budget.py minimize_prefixes`)**: QTranslator looks a
message up by `elfHash(source + comment)` and only *verifies* with whichever
of Comment/SourceText/Context that message happens to carry — those fields are
optional, and lrelease itself emits the minimal set. Keeping only what is
needed to disambiguate (1,126 messages need nothing, 687 need Context, 0 need
SourceText) **frees 93,590 bytes** — a 41% reduction, verified to still
re-parse to all 1,813 messages. Delta-0 is therefore safe with large margin.

## Activation

* In-app: **Settings → Language → العربية**.
* Programmatic: `HKCU\Software\WhirlwindFX\SignalRgb\UI` value `Locale` = `ar`
  (`work/patch_exe.py --lang ar`), read by `FetchCurrentLocaleFromRegistry`.

A launcher-side Hebrew/English switch is therefore a one-value registry write
— the cleanest activation of any target in this project after Borderless
Gaming's JSON key.

## Risks (stated honestly)

* **Patching breaks the Authenticode signature.** SignalRGB does not verify
  its own signature at launch, but this is a real change to a signed binary.
  Reverting restores the pristine bytes exactly.
* **A SignalRGB update wipes it** — Squirrel installs a new `app-<ver>` folder.
  The fix is to re-run `--deploy` (the patcher auto-detects the newest install
  and refreshes its backup).
* **The app must be closed** to write (the exe is locked while running).
* Store/effect content served from the API stays English.
* The vendor's Arabic is machine-translated — reference only.

## Comparison

Closest peer: **Borderless Gaming** (loose JSON, 343 strings). SignalRGB is
5× the string count and needs a binary patch instead of a file drop, but has
no font work, no archive, no repack, no encryption and no anti-cheat — and its
codec is already proven byte-exact.

## מסמכים קשורים
- באותה תיקייה: [[games/signalrgb/PIPELINE|PIPELINE]], [[games/signalrgb/RECON|RECON]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#signalrgb|CLAUDE_INDEX_games]]
