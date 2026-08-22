# Assassin's Creed Shadows — Hebrew translation FEASIBILITY

**Verdict: 🟡 GO-WITH-CAVEATS — "prove before you invest".**
Researched 2026-06-17 via a 7-agent workflow (5 parallel researchers → synthesis
→ adversarial verify) + direct local probing. Empirical anchors are in
[RECON.md](RECON.md); the recipe is in [PIPELINE.md](PIPELINE.md).

> ### ✅ UPDATE 2026-06-17 — Stage 0 Part A PASSED (in-game, user-confirmed)
> Set `ACShadows.ini [Language] Text=ar-AE / Subtitles=ar-AE` (via
> `tools/acs_set_language.py --arabic`) and launched the VANILLA game. The
> first-run **Initial-Setup screen rendered fully in Arabic, correctly RTL**
> (engine-native layout mirroring: labels right-aligned, values left, headers
> RTL, Arabic text properly shaped/joined). `لغة النص = العربية` (Text=Arabic),
> `لغة الصوت = English` (Sound stayed English). **The Arabic RTL text slot is
> REAL and selectable on this SKU** — the single biggest research dispute is
> resolved GREEN. Only the repacker gate (Part B) remains.

Four of the five pipeline pillars are SOLVED and locally verified. The project
is gated by ONE hard dependency: there is **no free / open / scriptable forge
REPACKER for the 2025 `scimitar` v42 generation** yet. So a *manual* one-off
Hebrew mod is likely achievable; an *automated launcher pipeline* (the usual end
goal) is blocked until an open repacker exists.

---

## 🟢 SOLVED (verified)

| Pillar | Status | Evidence |
|---|---|---|
| **Format** | scimitar **v42** | `b"scimitar\x00"` + `uint32 LE 0x2A` at offset 9 — confirmed byte-for-byte on AnimusRoom / boot / patch_01 / patch_02 via `tools/acs_forge_probe.py`. |
| **Font (the big de-risk)** | **No font work needed** | `resources/AvenirNextWorld-Regular.ttf` carries **52 Hebrew glyphs** (real 1–2-contour outlines, not `.notdef`) + 104 Arabic + 133 Arabic presentation forms. The shipped UI font already renders Hebrew AND does Arabic shaping/RTL. No Heebo surgery (SM2), no atlas build (WD2), no CR2W swap (CP2077). |
| **Localization system** | **Oasis string-IDs** | `VoiceAnimDataByOasisID` + `Dialogue*` in the Anvil type table. Text = a per-language binary **`LocalizationPackage_<Lang>.data`** resource INSIDE the forge, keyed by numeric Oasis hashes (one file per language). Same family as WD2's oasisstrings. |
| **Language selection** | **Trivial INI edit** | `Documents\…\ACShadows.ini` → `[Language] Text=/Subtitles=` use plain locale codes (`en-US`). Flip to `ar-AE`. The 23-byte root `localization.lang` (`b"LANG…"`) is just a pointer stamp. |
| **Deploy / Denuvo** | **Unblocked** | Denuvo protects the *executable*, not asset `.forge` archives — proven by many working retexture/outfit forge mods on Nexus + a Mod Manager. **No EAC/anti-cheat DLL** in the install. Deploy = repack-and-replace a patch forge + back up vanilla. |
| **Audio** | **Irrelevant** | Per-language sound forges (bra/eng/fre/ger/ita/jap/spa) don't matter; a text translation keeps English (or Japanese) voice and swaps only on-screen text. |
| **Translate stage** | **Already scaffolded** | The proven SM2/WD2 LM trio is copied into `work/acs_{translate,watchdog,progress}.py` (templates). |

## 🔴 THE GATE — the one thing that decides it

**A working, drivable repacker for scimitar v42.** Extraction is solved and the
community has already extracted + decompressed AC Shadows loc files (ResHax topic
1779). But:

- **AnvilToolkit** (Joschuka / Kamzik123) is the only tool that EXTRACTS *and*
  REPACKS forge + `LocalizationPackage` — officially confirmed only **up to AC
  Mirage (2023)**. For Shadows (v42, 2025) the only working build is a
  **donation / Discord-gated private BETA**, and its ability to *repack* a v42
  `LocalizationPackage` into a forge that *loads* is **unconfirmed by any
  shipped artifact**.
- The forge inner blocks are **Oodle-Kraken** compressed (lead byte `0x8C`), but
  **the game ships no `oo2core_*_win64.dll`** — any repacker must supply Oodle
  from another title.
- Reimport must **preserve the `.header` sidecar** or the game crashes.
- **No localization/text mod exists for AC Shadows in any language** (only
  retextures/DDS swaps), despite demand — so repack-and-load of a *new-strings*
  package is proven by zero precedent.

➡️ **A Discord-gated closed binary cannot be bundled into the launcher or
automated.** Even if a manual mod succeeds, the self-serve launcher integration
stays blocked until an open/scriptable v42 repacker exists (or the closed tool
is reverse-engineered / a bespoke Oodle-aware packer is written).

## ⚠️ Corrections from the adversarial pass (do not regress)

1. ~~**The Arabic text slot is DISPUTED, not on-disk-proven.**~~ **RESOLVED
   2026-06-17 — PROVEN in-game (Stage 0 Part A above).** Setting `Text=ar-AE`
   rendered the whole UI in Arabic RTL on this exact install. Game8's omission
   was simply an incomplete list. No longer a risk.
2. **Deploy slot is `DataPC_boot_patch_01.forge`, NOT `_02`.** Every live Shadows
   mod + the Mod Manager target **patch_01**; `patch_02` (10.7 GB, newer mtime)
   is the GAME's own title-update forge, not the mod slot. (An earlier synthesis
   claim got this backwards.)
3. **Anti-tamper presence:** `aegir_f.dll` + `memorywrapper_f.dll` are the
   Denuvo wrapper family; `upc_r2_loader64.dll` is Ubisoft Connect. No EAC, but
   integrity checks exist — the identity round-trip (below) is what proves a
   repacked forge survives them.
4. **"Community decompressed the loc files" supports EXTRACTION only**, not
   repack/reimport — don't let it overstate repack feasibility.

---

## ✅ The decisive cheap experiment — run THIS first (prove-before-invest)

Two parts; Part A costs ~10 minutes and a text editor and can flip the whole
project to NO-GO for near-zero cost. **Do Part A before acquiring any tool.**

### PART A — is Arabic a real, selectable text slot on this install? (~10 min)
1. Back up + rewrite the language config (helper provided — see PIPELINE.md):
   `python tools/acs_set_language.py --arabic`  (sets `Text=ar-AE`,
   `Subtitles=ar-AE`; `--restore` reverts from the auto-backup).
2. Launch AC Shadows on the **vanilla** game (no mod) and open the menu/HUD.
3. **If the UI/subtitles render in Arabic RTL → pillar 3 is PROVEN on this SKU**
   and the whole Arabic-slot-hijack strategy is validated.
   **If Arabic does NOT appear** (falls back to English / code rejected) → the
   slot is gated on this SKU; rethink the strategy before any forge work.

### PART B — does a v42 repack load past integrity? (only if A passes)
A **zero-translation identity round-trip** that resolves the repacker gate
without writing a single Hebrew word:
1. Acquire the AnvilToolkit AC Shadows beta (ATK Discord) + an `oo2core` DLL from
   another Oodle title on this machine.
2. Extract the **Arabic** `LocalizationPackage` from `DataPC_boot.forge`.
3. Repack it **UNCHANGED** into `DataPC_boot_patch_01.forge` (back up vanilla
   first), supplying oo2core; preserve the `.header` sidecar.
4. Deploy, set `Text=ar-AE`, launch → **does the game boot and still show vanilla
   Arabic?** If yes, repack + Oodle + header + Denuvo-integrity + load all work
   for the `LocalizationPackage` resource type. Only then is it safe to invest in
   translation.

If A and B both pass, the remaining work is the well-trodden SM2/WD2 path
(extract EN + Arabic packages → translate into the Arabic slot with the local LM
→ repack → deploy → publish). See [PIPELINE.md](PIPELINE.md).

---

## Bottom line
Feasibility is **plausible and unusually well-positioned** (font + locale +
oasis system + deploy are all green, the Arabic RTL slot is now **proven in-game**,
and the translate stage is a copy-paste of a proven pipeline). After Stage 0
Part A passed, **exactly one hard dependency remains**: a drivable scimitar-v42
forge REPACKER (currently only AnvilToolkit's gated beta) — prove it with the
zero-translation identity round-trip (Part B) before committing engineering time.
The **launcher-integration end goal specifically remains blocked** until an
open/scriptable v42 repacker exists, independent of whether a manual mod works.

## מסמכים קשורים
- באותה תיקייה: [[games/acshadows/FORMAT|FORMAT]], [[games/acshadows/PIPELINE|PIPELINE]], [[games/acshadows/PLAN_HEBREW|PLAN_HEBREW]], [[games/acshadows/RECON|RECON]], [[games/acshadows/RESEARCH_FONT|RESEARCH_FONT]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#acshadows|CLAUDE_INDEX_games]]
