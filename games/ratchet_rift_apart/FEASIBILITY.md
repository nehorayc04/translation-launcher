# Ratchet & Clank: Rift Apart — FEASIBILITY

**Verdict: 🟢 GO — medium tier.** The container, text codec, DAT1 repack, and the native toc-redirect
applier are all **proven reusable from Spider-Man 2 this session**. The remaining Phase-1 gates are
mechanical and de-risked: a Hebrew **font injection** (Proxima Nova, same class as SM2/GoWR/Anno/W3)
and the **bidi storage mode** (LOGICAL vs VISUAL), which a single in-game menu-proof screenshot decides.
No Denuvo, no anti-cheat, and RTL is proven achievable on this exact engine (SM-Remastered Arabic mod).

## Why medium, not easy
- **No Arabic slot** → LTR (English) hijack, so RTL is NOT inherited for free. The bidi mode must be
  determined by a menu-proof (unlike Hogwarts/W3 where an Arabic locale gave a strong prior). cohtml runs
  the Unicode Bidi Algorithm, so the technical prior is **LOGICAL + `&rlm;` anchors**, with **VISUAL** as the
  fallback — but the English-slot base direction is LTR, so it must be confirmed in-game.
- **Font injection required** (0/27 Hebrew on every shipped font) — a bounded, solved sub-task, not a blocker.
- **Subtitle-heavy scope** (~17.5k translatable, 10k of it spoken VO) — a real translation haul, but moderate
  (smaller than GoWR 48k / CP2077 100k+).

## Gate status
| Gate | Status | Evidence |
|---|---|---|
| Container read | ✅ PROVEN | dat1lib reads the toc (TOC2/RCRA v202300); 147 archives / 340,665 assets |
| Text codec | ✅ PROVEN | 9-section DAT1, same tags as SM2; 24,575 entries decoded; keys+values extracted |
| Arabic slot | ❌ ABSENT (verified) | 0 Arabic/0 Hebrew in all 32 variants → LTR-hijack |
| DAT1 repack | ✅ PROVEN | identity round-trip SEMANTIC-PASS (0/24,575); 1-string Hebrew read-back OK |
| Native applier | ✅ PROVEN (as-is) | spiderman2_mod.py sections/methods all resolve on R&C toc; size-entry redirect valid |
| Font (Hebrew) | ⚠️ INJECTION REQUIRED | Proxima Nova, clean sfnt TTF; 0/27 Hebrew — inject via fontTools (solved class) |
| bidi mode | ⚠️ MENU-PROOF DECIDES | cohtml UBA → LOGICAL+RLM prior; build BOTH, screenshot picks |
| DRM / anti-cheat | ✅ CLEAR | no Denuvo, no EAC; asset mods load |
| Deploy path | ✅ PROVEN | toc-redirect + d/mods (SM2 native applier), backup+revert; no repack, no Overstrike |
| Community precedent | ✅ GREEN | Overstrike/dat1lib support R&C; SM-Remastered Arabic RTL mod exists |

## Variant → language map (32 variants; English = the hijack target)
| v | code | language | v | code | language |
|--:|---|---|--:|---|---|
| 0 | en-US | **English (US) — SOURCE / hijack** | 16 | sv | Swedish |
| 1 | en-US | English (US) — dup of v0 | 17 | pt-BR | Portuguese (Brazil) |
| 2 | en-GB | English (UK) | 18 | en-GB | English (UK) — dup of v2 |
| 3 | da | Danish | 19 | tr | Turkish — *alt "sacrifice" slot* |
| 4 | nl | Dutch | 20 | es-419 | Spanish (LatAm) |
| 5 | fi | Finnish | 21 | zh-Hans | Chinese (Simplified) |
| 6 | fr | French | 22 | zh-Hant | Chinese (Traditional) |
| 7 | de | German | 23 | — | EMPTY STUB |
| 8 | it | Italian | 24 | cs | Czech |
| 9 | ja | Japanese | 25 | hu | Hungarian |
| 10 | ko | Korean | 26 | el | Greek |
| 11 | no | Norwegian | 27 | ro | Romanian |
| 12 | pl | Polish | 28 | — | EMPTY STUB |
| 13 | pt-PT | Portuguese (Portugal) | 29 | — | EMPTY STUB |
| 14 | ru | Russian | 30 | — | EMPTY STUB |
| 15 | es-ES | Spanish (Spain) | 31 | hr | Croatian |

## Activation (how the user turns on Hebrew)
- **TEXT language** = an in-game setting: **Settings → Game Settings → Text Language** (separate from Voice/Audio).
  The engine selects the variant purely by a fixed **language-enum index** (variant *N* = language *N*); there is
  **no separate language-code manifest** and **no `HKCU\Software\Insomniac Games\Ratchet` registry key** (that
  key exists only for SM2 on this machine). The choice persists in the game's own user-settings/save.
- `flt.ini [GameSettings] Language=english` = the launch/depot + **voice** locale; **Text Language overrides
  on-screen text independently** → English VO is preserved for free.
- **Recommended = zero-friction English hijack:** ship Hebrew INTO the English variants (patch v0 en-US at minimum;
  for region-safety patch all four: 0, 1, 2, 18). The user keeps Text Language at its default (English) and sees
  Hebrew. **Alternative** (if in-game English must stay viewable): hijack **Turkish (v19)** as a sacrifice slot and
  translate v19's own language-name string to `עברית` so the Settings dropdown reads "Hebrew".

## bidi — the one determination left (menu-proof, do NOT assume)
- cohtml/GameFace **ignores CSS `direction`/`dir`** and honors **only Unicode bidi CONTROL chars** (proven on
  SM2 + CP2077). Because cohtml runs the UBA, storing **VISUAL** on a bidi engine would **double-reverse** →
  mangled text. So the **prior is LOGICAL + a leading `&rlm;` (U+200F, NOT RLE/PDF U+202B/202C — SM2 proved Heebo
  lacked those → tofu)** per segment to raise the base direction (alignment + neutral/number resolution) in the
  LTR English container.
- **The open risk:** whether cohtml grants a per-string RTL base from the anchor when the outer container is LTR,
  or clamps to the container. **That is exactly what the menu-proof resolves** → build BOTH (LOGICAL+RLM and
  VISUAL) and let the screenshot pick. (Precedent split: Hogwarts landed LOGICAL; TLOU/GoT/007 landed VISUAL.)

## Font atmosphere recommendation
**Rubik** (primary) — rounded geometric sans, first-class **bilingual Hebrew+Latin** (one family, Meir Sadan
Hebrew), full weight range (Light→Black), SIL-OFL. Fits R&C's playful colorful sci-fi/cartoon UI far better than
GoWR's serif David or SM2's corporate Heebo. Alternates for display/title keys: **Varela Round** (warmer/rounder,
~1 weight) / **Fredoka** (bubbly, headers only). Confirm the look in the menu-proof screenshot.

## Risks / unknowns
- bidi mode unconfirmed until the menu-proof (medium — but both builds are cheap and the applier is proven).
- In-game boot/render not yet confirmed (needs the user to launch) — but SM2 ships this exact path proven in-game.
- Font injection must EMPTY the U+200F/U+200E glyphs (SM2 lesson) so `&rlm;` anchors don't render as visible marks.
- CREDITS (3,595, mostly proper names) is low translation priority — translate UI + subtitles first.

## מסמכים קשורים
- באותה תיקייה: [[games/ratchet_rift_apart/PIPELINE|PIPELINE]], [[games/ratchet_rift_apart/PUBLISH|PUBLISH]], [[games/ratchet_rift_apart/RECON|RECON]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#ratchet_rift_apart|CLAUDE_INDEX_games]]
