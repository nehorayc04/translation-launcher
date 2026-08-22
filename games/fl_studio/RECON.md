# FL Studio 2026 (Image-Line) — Hebrew localization RECON

**Target software:** FL Studio 2026 — the flagship DAW by Image-Line. NOT a game (peer of
VirtualDJ / SignalRGB in this project). Proposed `games.id` = **`fl-studio`**, `is_software=true`.

Install: `C:\Program Files\Image-Line\FL Studio 2026\`
Main exe: `FL64.exe` (596 KB launcher/stub) → engine `FLEngine_x64.dll` (22.2 MB) + `FLMManaged.dll`
(9.3 MB). Written in **Delphi/Object Pascal** (Image-Line's long-standing stack). Parts of the modern
UI use **WebView2** (`WebView2Loader.dll` present) — browser/store/some panels are Chromium; the MAIN
mixing/piano-roll/channel-rack UI is native Delphi.

The second path the user named — `C:\Program Files\FL Cloud Plugins\` — is a SEPARATE product and is
essentially **out of scope** (see §6).

---

## 1. Where the UI text lives — `System\Languages\*.moe`

`System\Languages\` ships **7 language files**, each `<lang>.moe` (the localized strings) + `<lang>.svg`
(the language-selector flag icon):

| file | size | script |
|---|---:|---|
| `de.moe` | 901 KB | German (Latin) |
| `es.moe` | 924 KB | Spanish (Latin) |
| `fr.moe` | 767 KB | French (Latin) |
| `ja.moe` | 942 KB | Japanese (CJK) |
| `ko.moe` | 918 KB | Korean (CJK) |
| `vi.moe` | 982 KB | Vietnamese (Latin+diacritics) |
| `zh.moe` | 848 KB | Chinese (CJK) |

**There is NO `en.moe`** — only `en.svg`. English is the **built-in source**, hard-embedded in
`FLEngine_x64.dll` (confirmed: `Channel rack`, `Piano roll`, `Playlist`, `Mixer`, `Tempo`,
`New pattern`, `Save as` all present as BOTH ASCII and UTF-16LE in the DLL). ⇒ **LTR-slot hijack**
model (AC2 / Anno / GTA / TLOU class) — there is **NO Arabic and NO Hebrew** locale.

Loader evidence in `FLEngine_x64.dll` (UTF-16 strings, offset ~6.14 MB): `System\Languages\`, `.moe`,
`.mo`, `LC_MESSAGES`, `Default`, and the registry key `Software\Image-Line\Shared\Language` /
`Program language`.

---

## 2. Format = **encrypted GNU gettext `.mo`** — CRACKED (fixed-keystream XOR)

The `.mo` / `LC_MESSAGES` / `Default` strings in the loader are the tell: `.moe` = an **encrypted
gettext `.mo`** (the "e" = encrypted). Proven this session (pure Python, `work/moe_crack.py`):

- **Header:** `file[0:4]` = version `00 01 00 00`; `file[4:16]` = a 12-byte constant
  `57 1b 4e 10 0c 6b cd d9 1a ba 51 41` — **identical across all 7 files** (a format signature /
  likely the keystream seed). `file[16:]` = ciphertext.
- **Cipher = a FIXED keystream XOR** (a stream cipher whose keystream is the SAME across every
  language file). PROVEN two ways:
  1. `de.moe` and `es.moe` are **byte-identical for the first 116,840 bytes** — impossible for two
     different translations unless the keystream is fixed and the plaintext prefix (the English
     msgid table) is shared.
  2. Decrypting `file[16:20]` against the gettext little-endian magic `de 12 04 95` and `file[28:32]`
     against `revision=0` gives a self-consistent keystream, and **crib-dragging the
     language-independent gettext metadata block** `MIME-Version: 1.0\nContent-Type: text/plain;
     charset=UTF-8\nContent-Transfer-Encoding: 8bit\n` lands at `de.moe` body offset **55428** and
     decrypts **byte-perfect**.
- Body entropy ≈ 7.89–7.93 bits/byte (looks encrypted), but it is **NOT** AES/RC4/ChaCha (no crypto
  constants in the binary, no block alignment — divergence points are byte-granular, not 16-aligned).
  It is the **weakest possible cipher: a fixed XOR keystream**, and it is broken by known-plaintext —
  and the English source is *known* (embedded in the DLL). This is a CRACKABLE gate, not a wall.

**Decrypted plaintext = standard gettext `.mo`** (magic `0x950412de`, revision 0, `O=28`). Once the
full keystream is recovered, editing is trivial (standard `msgid → msgstr` pairs; `polib`/`msgfmt`).

**⚠️ Non-standard section order (from divergence analysis, to confirm in Phase 2):** `de`/`es` share
116,840 bytes then diverge, while `fr` diverges from both at byte 268 (fr has a different string count
`N`, being a smaller/older extraction). This implies the offset tables and the English msgid pool come
BEFORE the per-language msgstr pool, so the shared prefix = header + O-table + English msgids (identical
across langs) and the divergence = where the msgstr offset table / translations begin.

---

## 3. RTL / bidi — UNDETERMINED (menu-proof decides)

The `.moe` only supplies strings; the **native Delphi renderer** decides bidi. Unknown whether it runs
the Unicode Bidi Algorithm (→ store LOGICAL) or draws in storage order (→ store VISUAL). The WebView2
panels get full bidi for free (Chromium), but the main UI is native. **Build BOTH a LOGICAL and a
VISUAL menu-proof and let one screenshot decide** (standard project procedure). No pre-reversal until
the proof shows whether it mirrors.

---

## 4. Font — Hebrew almost certainly renders via SYSTEM FALLBACK (menu-proof confirms)

Bundled UI fonts `Artwork\Fonts\{Cuprum,FrancoisOne,Fruity microfont}.ttf` cover **0/27 Hebrew** —
**but they also cover 0 CJK and 0 Arabic**, and FL ships Japanese/Korean/Chinese/Vietnamese. So the
native renderer **already falls back to a system font** for every non-Latin script it ships. ⇒ Hebrew
(U+05D0–05EA) will almost certainly get the same system fallback and render with **no font work at
all** — exactly the Borderless-Gaming inference ("a Latin-only bundled font + shipped non-Latin locales
⇒ fallback is already load-bearing"). Confirm in the menu-proof; only if it tofus does a font sub-project
arise.

---

## 5. Activation = ONE registry value (cleanest lever in the project)

`HKCU\Software\Image-Line\Shared\Language` → **`Program language`** (REG_SZ) — currently `"en"`.
The value is the `.moe` filename stem (`de`/`es`/`fr`/`ja`/`ko`/`vi`/`zh`/`en`). An in-launcher
Hebrew/English switch is a single `REG_SZ` write (a `kind:"registry"` `game_language.py` entry, same
mechanism as SM2 / SignalRGB).

**Two deploy options (menu-proof decides which FL accepts):**
- **(A) Add a real `he` locale** — drop `he.moe` + `he.svg` into `System\Languages\`, set
  `Program language = he`. FL enumerates `System\Languages\*.moe` and builds the selector from the
  `.svg` files, so a new locale *should* appear (like Borderless Gaming's discovered picker). Cleanest.
- **(B) Hijack an existing slot** — replace e.g. `vi.moe` (Vietnamese, least-used) with the Hebrew
  `.moe`, set `Program language = vi`. Guaranteed to load; label reads "Vietnamese" unless the `.svg`
  is also swapped.

Deploy is a **loose-file drop, no repack, no archive, no anti-cheat** — the easiest deploy class in
the project. Removal = delete `he.moe`/restore `vi.moe` + reset the registry value.

---

## 6. FL Cloud Plugins — OUT OF SCOPE (thin cloud/WebView2 app)

`C:\Program Files\FL Cloud Plugins\` = `FL Cloud Plugins.exe` (6.7 MB, **WebView2/V8/Qt** hints) +
`install-helper` + `licence-engine` + `Resources\offline.html`. The app's UI is **served from the
cloud**; the ONLY local translatable text is **3 strings** in `offline.html`
("Instruments and Effects", "We can't detect an internet connection.", "You need to be online to use
this application."). No local i18n/JSON/`.mo`. Being WebView2, bidi + Hebrew are free anyway. **Not a
translation target** beyond optionally Hebraizing those 3 offline strings.

---

## 7. Scope (estimate — exact count in Phase 2)

FL Studio is a very large DAW; the `.moe` files are ~800–980 KB. A gettext `.mo` that size typically
holds **~8,000–16,000 UI strings**. Tokens to preserve will be printf-style / `%s` / `&`-accelerators
(to confirm on the decrypted corpus). **Single pass — no fleet.** Exact `N`, token inventory, and the
UI-vs-tooltip breakdown come out of the Phase-2 full decrypt.

---

## VERDICT: 🟢 GO (software tier). Gate = the encryption, and it is already cracked.

Every historically-hard gate is green or easy: English source embedded (known-plaintext), font almost
certainly free (system fallback proven by shipped CJK), deploy is a loose-file drop with no repack/anti-
cheat, activation is one registry value. The single real gate — the `.moe` encryption — is a **fixed
XOR keystream over a gettext `.mo`**, proven decryptable this session (metadata block recovered
byte-perfect). Phase 1.5 = recover the FULL keystream + run a menu-proof to lock bidi + font + the
add-`he` vs hijack-`vi` deploy question.

## מסמכים קשורים
- באותה תיקייה: [[games/fl_studio/FEASIBILITY|FEASIBILITY]], [[games/fl_studio/PIPELINE|PIPELINE]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#fl_studio|CLAUDE_INDEX_games]]
