# FL Studio 2026 Hebrew — FEASIBILITY

**Verdict: 🟢 GO (software tier).** One real gate (the `.moe` encryption) — already proven crackable.

## Gate-by-gate

| Gate | Status | Notes |
|---|---|---|
| Container / text format | 🟢 **CRACKED** | `.moe` = fixed-keystream XOR over a GNU gettext `.mo`. Metadata block decrypted byte-perfect (`work/moe_crack.py`). |
| Encryption key | 🟡 recover full keystream | Fixed keystream ⇒ known-plaintext break; English source is embedded in `FLEngine_x64.dll`. Multiple viable methods (below). This is Phase-1.5. |
| Source language | 🟢 **English, embedded** | No `en.moe`; English UI strings are in the DLL (ASCII + UTF-16). |
| RTL slot | 🟢 **LTR hijack** | 7 langs (de/es/fr/ja/ko/vi/zh), no Arabic/Hebrew. Add a real `he` locale, or hijack `vi`. |
| bidi mode | 🟡 **menu-proof decides** | Native Delphi renderer — unknown LOGICAL vs VISUAL. WebView2 panels are bidi-free. |
| Font | 🟢 **likely free** | Bundled fonts cover 0 Hebrew AND 0 CJK, yet FL ships JP/KO/ZH ⇒ system fallback already load-bearing ⇒ Hebrew renders. Confirm in proof. |
| Deploy | 🟢 **loose-file drop** | Drop `he.moe` (+`he.svg`) into `System\Languages\`. No repack, no archive, no anti-cheat. |
| Activation | 🟢 **one registry value** | `HKCU\Software\Image-Line\Shared\Language\Program language` (REG_SZ) = the locale stem. |
| DRM / anti-tamper | 🟢 | Localization is a loose data file; no integrity check on `System\Languages\`. FL has licensing but not on the language files. |
| Scope | 🟢 single pass | ~8–16k UI strings (estimate); exact count in Phase 2. No fleet. |

## The one gate in depth — recovering the FULL keystream

The cipher is a fixed XOR keystream `KS` (same across all 7 files). `plaintext = ciphertext XOR KS`.
Proven anchors: `KS[0:8]` (gettext magic+rev), `KS[12:16]` (`O=28`), `KS[55428:55516]` (metadata crib).
To get the whole `KS` (enough to decrypt every file AND re-encrypt a new Hebrew `.mo`), any of:

1. **English-msgid crib-drag + extension** — the msgid pool is known English (from the DLL). Drag a
   batch of known UI strings, recover local `KS`, walk adjacent NUL-separated msgids, extend. Then
   reconstruct the gettext offset tables from the recovered msgids (sorted, cumulative offsets) to
   recover `KS` over the low-constraint table region. Closes the loop.
2. **Two-file text constraint over the msgstr pool** — `de` and `es` share `N` (aligned). Past their
   divergence (116,840) each byte has TWO independent text constraints (German text AND Spanish text
   must both decrypt to plausible UTF-8) → reliable `KS` recovery over the entire msgstr pool. Anchor
   at the metadata (55428) and extend right to EOF.
3. **Find the keystream generator in the DLL** — the keystream is deterministic (fixed); the 12-byte
   header `57 1b 4e 10 …` is very likely its seed. If the generator (a Delphi PRNG) is located, the
   exact full-length keystream is reproduced trivially — and this also hands over the ENCRYPT routine.

Once `KS` is in hand: decrypting any `.moe` and **encrypting a Hebrew `.mo` → `he.moe`** are both just
`XOR KS` + prepend the 16-byte header. Read AND write from one break.

## Precedent / risk

- Community FL Studio translation is famously blocked precisely by this `.moe` encryption (Image-Line
  ships official translations). This groundwork **breaks that block** — the cipher is weak.
- Patching the exe is NOT required (the `.moe` is a loose data file). No signature/anti-tamper concern
  on `System\Languages\`.
- A FL Studio update replaces `System\Languages\*.moe` (and may bump the `.moe` version / rotate the
  keystream) → re-verify the keystream + re-deploy after a major update (same posture as every
  loose-file target here).

## Non-goal: FL Cloud Plugins

Thin WebView2/cloud app — 3 local strings in `offline.html`, rest is server-served. Not a target.

## מסמכים קשורים
- באותה תיקייה: [[games/fl_studio/PIPELINE|PIPELINE]], [[games/fl_studio/RECON|RECON]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#fl_studio|CLAUDE_INDEX_games]]
