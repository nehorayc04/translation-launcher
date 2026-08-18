## FL Studio 2026 (Image-Line) Hebrew — Phase-1 groundwork DONE, encryption CRACKED, 🟢 GO (2026-07-21)

New target scaffolded at `games/fl_studio/` (RECON/FEASIBILITY/PIPELINE + `work/` + `extract/`).
**Software, not a game** (peer of VirtualDJ / SignalRGB). Install
`C:\Program Files\Image-Line\FL Studio 2026\`; engine = `FLEngine_x64.dll` (22 MB, **Delphi**) with
some **WebView2** panels. Proposed `games.id` = **`fl-studio`**, `is_software=true`. Memory
[[fl-studio-groundwork-go]]. The user ALSO named `C:\Program Files\FL Cloud Plugins` — that is a
separate **thin WebView2/cloud app** (`FL Cloud Plugins.exe` + `Resources\offline.html`, 3 local
strings) → **OUT OF SCOPE**, the real target is FL Studio.

- **🔑 Text = 7 `System\Languages\<lang>.moe` files** (de/es/fr/ja/ko/vi/zh) + per-lang `<lang>.svg`
  selector icons. **No `en.moe`** → English is the built-in source, hard-embedded in
  `FLEngine_x64.dll` (`Channel rack`/`Piano roll`/`Mixer`/… present as ASCII **and** UTF-16). All 7
  langs are LTR/CJK → **NO Arabic, NO Hebrew** → **LTR-slot hijack**, not the Arabic trick.
- **🟢 THE GATE — `.moe` = an ENCRYPTED GNU gettext `.mo` — CRACKED this session (`work/moe_crack.py`).**
  The loader strings `System\Languages\`, `.mo`, `LC_MESSAGES`, `Default` gave it away (the "e" =
  encrypted). Header = `00 01 00 00` (version) + a 12-byte constant `57 1b 4e 10 0c 6b cd d9 1a ba 51
  41` **identical across all 7 files** (signature / likely keystream seed); `file[16:]` = ciphertext.
  **Cipher = a FIXED XOR keystream** (same keystream across every language), the weakest possible
  cipher. PROVEN two ways: (1) `de.moe` and `es.moe` are **byte-identical for the first 116,840 bytes**
  (impossible for two real translations unless the keystream is fixed and the English msgid prefix is
  shared); (2) crib-dragging the language-independent gettext metadata block `MIME-Version: 1.0\n
  Content-Type: text/plain; charset=UTF-8\nContent-Transfer-Encoding: 8bit\n` lands at `de.moe` body
  offset **55428** and decrypts **byte-perfect** to that exact block, and the header decrypts to the
  gettext magic `950412de` + revision 0 + `O=28`. It is NOT AES/RC4/ChaCha (no crypto constants, no
  16-byte block alignment). ⇒ **known-plaintext-breakable, and the English source IS known** (in the
  DLL). This is a crackable gate, not a wall — the community block on FL translation IS this weak cipher.
- **⚠️ Full keystream = the Phase-1.5 deliverable (not finished).** Anchors recovered: `KS[0:8]`
  (magic+rev), `KS[12:16]` (`O=28`), `KS[55428:]` (metadata). The statistical 2-file fill was noisy in
  the low-constraint TABLE region (`work/moe_fullks.py`). Clean methods to finish: (a) English-msgid
  crib-drag + reconstruct the gettext offset tables from the recovered msgids to close the table region;
  (b) de+es two-file text constraint over the msgstr pool (aligned, same `N`, past divergence 116,840);
  (c) find the keystream PRNG in the DLL (the 12-byte header is likely the seed) → also hands over the
  ENCRYPT routine. Once `KS` is in hand, **decrypt any `.moe` AND encrypt a Hebrew `.mo` → `he.moe`**
  are both just `XOR KS` + the 16-byte header (read AND write from one break).
- **Font = almost certainly FREE (system fallback).** Bundled `Artwork\Fonts\{Cuprum,FrancoisOne,
  Fruity microfont}.ttf` cover **0/27 Hebrew — but also 0 CJK / 0 Arabic**, while FL ships JP/KO/ZH ⇒
  the native renderer already falls back to a system font for every non-Latin script it ships ⇒ Hebrew
  gets the same fallback (the Borderless-Gaming inference). Confirm in the menu-proof; only tofu triggers
  a font sub-project. (Some panels are WebView2 → bidi + Hebrew free there regardless.)
- **bidi = menu-proof decides.** Native Delphi renderer — unknown LOGICAL vs VISUAL. Build BOTH variants
  with distinct Latin markers, one screenshot decides. Do NOT pre-reverse before the proof.
- **🔑 Activation = ONE registry value** (cleanest lever in the project): `HKCU\Software\Image-Line\
  Shared\Language` → **`Program language`** (REG_SZ, currently `"en"`) = the `.moe` filename stem. An
  in-launcher Hebrew/English switch is a single `REG_SZ` write (`kind:"registry"` `game_language.py`).
- **Deploy = loose-file drop, NO repack, NO anti-cheat.** Two options the proof will choose between:
  (A) add a real `he.moe`+`he.svg` to `System\Languages\` + set `Program language=he` (FL enumerates
  the folder + builds the selector from the `.svg` → should appear, like Borderless's discovered
  picker) — cleanest; (B) hijack `vi.moe` (least-used) + set `Program language=vi` — guaranteed to load.
- **Scope estimate ≈ 8–16k UI strings, single pass (no fleet)** — exact `N` + token inventory come out
  of the Phase-2 full decrypt. NEXT = finish `KS` → identity round-trip codec → menu-proof → delegate →
  publish like VirtualDJ/SignalRGB (id=`fl-studio`, `is_software=true`), price per the "can-this-be-sold"
  check ([[can-this-mod-be-sold]]: a `.moe` is a from-scratch corpus, not a derivative of Image-Line's
  own file, so paid is more defensible than VirtualDJ — but it IS Image-Line software + trademark, so
  decide before pricing). **Run all tooling with the repo `.venv` python.**

---


