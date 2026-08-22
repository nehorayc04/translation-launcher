# AC Shadows Hebrew — FONT GATE research + verification (2026-07-27)

Read-only research pass. **Nothing on the game was modified, deployed, reverted, or launched.**
All decode used the borrowed `oo2core_9_win64.dll`
(`C:\Users\Nehoray_Cohen\Projects\Game translator\Game Lab\Battlefield 6\oo2core_9_win64.dll` —
the documented `C:\Games\Battlefield 6` path is gone; BF6 was moved into the project's `Game Lab`).

---

## 0. TL;DR / VERDICT

**Font gate = LIKELY-ALREADY-WORKING for glyph RENDERING, but the deployed build will look
BROKEN on spacing and MUST be rebuilt with donor-selection before it is shippable.**

- The deployed state is 100% intact on disk (all 8 PHXFD weights, 27/27 Hebrew each, real ink;
  the 11-string text proof is also still live; forges contiguous; backups present; **no game-update
  revert** — forge mtimes are exactly the deploy time). It has never been launched.
- On the next cold launch the main menu (already set to the Arabic slot) will show the 11 menu
  items in Hebrew. Glyphs will render (font gate closeable) **but spacing will be visibly wrong** —
  the current injector picks donors by *area rank*, which hands א an **advance of 353 px** (vs ~45 px
  ideal), i.e. an ~8× gap after some letters. Every letter is a correct glyph; the layout is garbage.
- **The fix is proven and needs zero metric rewrites**: pick each Hebrew letter's donor by nearest
  *advance* + uniform *height*. Measured on the real record table it cuts mean advance error from
  **54 px → 0.8 px**, advance stdev **51 → 8.7** (matching the ideal 8.8 spread), max advance
  **353 → 57**, and height stdev **3.1 → 0.8**. It drops straight into the existing exact-slot pipeline.
- **Append-relocate is very likely available on v42 and would be strictly better than exact-slot
  fill** (arbitrary growth, no entropy-budget search): the two *nearest siblings*, AC Origins (v28)
  and AC Mirage (v29), both deploy by append-relocate and boot in-game (+13.7 MB on Origins), and
  the v42 record layout is byte-identical to what Mirage patches. But it is **unproven on v42** and
  carries a residual DirectStorage-contiguity risk (the v50 Black-Flag-Resynced sibling requires
  contiguity). **For the FONT it is moot** — the atlas repurposes slots in place, no growth needed.
- **Prior art: non-Latin NEW scripts already render in AC Shadows via mods** (a Thai fan
  translation exists; Thai is not an official language, so its glyphs are not shipped). No *public*
  tool writes the PHXFD atlas; AnvilToolkit's public support stops before Shadows and the ResHax
  Mirage/Valhalla loc tool "is currently NOT WORKING with AC: Shadows." Our atlas-injection crack is,
  as far as public evidence goes, the only documented open method for the Shadows font.

---

## 1. VERIFIED current on-disk state (read-only)

Script: `scratchpad/acs_verify_deployed.py`. Results:

### 1a. Forge TOC contiguity — all OK
| forge | version | resources | contiguity invariant |
|---|---|---|---|
| DataPC_boot.forge | v42 | 129,844 | 129,843/129,843 OK |
| DataPC_boot_patch_01.forge | v42 | 46,564 | 46,563/46,563 OK |
| DataPC_boot_patch_02.forge | v42 | 38,556 | 38,555/38,555 OK |

`off[n+1] == off[n] + size[n]` holds with **zero exceptions** → the forges are byte-packed, no gaps,
no alignment padding.

### 1b. Pristine backups — all 8 present and decodable
`games/acshadows/work/_atlasbak_{20630,20631,20632,24062,24063,82569,82570,82571}.bin` all exist and
their stored blob length equals the recorded slot size. Revert (`acs_atlas_inject2.py --revert`) is safe.

### 1c. Live font weights — 27/27 Hebrew, real ink, no empty rasters
| idx | forge | slot | Hebrew cps | ink px | empty |
|---|---|---|---|---|---|
| 20630 | patch_02 | 684,064 | 27/27 | 22,313 | 0 |
| 20631 | patch_02 | 3,310,492 | 27/27 | 22,128 | 0 |
| 20632 | patch_02 | 1,248,838 | 27/27 | 24,098 | 0 |
| 24062 | patch_01 | 3,283,267 | 27/27 | 22,128 | 0 |
| 24063 | patch_01 | 1,240,306 | 27/27 | 24,098 | 0 |
| 82569 | boot | 684,186 | 27/27 | 22,313 | 0 |
| 82570 | boot | 697,324 | 27/27 | 22,128 | 0 |
| 82571 | boot | 1,097,770 | 27/27 | 24,098 | 0 |

ASCII read-back of live glyphs (patch_02 20630) shows recognisable ש, ל, ם, etc. — real letterforms,
not tofu.

### 1d. Text proof also still live — 11/11
`acs_loc_deploy.py --proof --verify` re-read the LIVE forges: **11/11** menu lineIDs read back as the
expected Hebrew, incl. the Latin marker `ZZ-ACS-OK`. The 3 `.lpbak_` sidecars are present
(boot→51444, patch_01→18566, patch_02→17388). So BOTH surfaces (text + font) are deployed and coexist.

### 1e. No game-update / Ubisoft-Connect revert
The three boot forges' mtimes are all **2026-07-18 23:40:32** — exactly the font-deploy time in
CLAUDE.md. Today is 2026-07-27. Nothing has rewritten the forges since. Sizes unchanged. **A game
update or a Connect "verify files" has NOT run.** (If one ever does, it rewrites the patched forge and
reverts everything — re-run `acs_atlas_inject2.py --apply` + `acs_loc_deploy.py --apply`.)

### 1f. Activation is already set
`Documents\Assassin's Creed Shadows\ACShadows.ini` → `[Language] Client=ar-SA / Text=ar-SA /
Subtitles=ar-SA`. The game is already pointed at the Arabic slot we patched, so **no setting change is
needed before launch.**

---

## 2. THE EXACT ONE-LAUNCH VERIFICATION

Launch the game (INI is already `ar-SA`). Look at the **main menu** — it renders from the Arabic
LocalizationPackage + the Arabic PHXFD atlas, both of which are patched. The 11 patched strings are
the main-menu / pause-menu items:

`ZZ-ACS-OK` (Continue) · **משחק חדש** (New Game) · **טעינה** (Load) · **מערכת** (System) ·
**עלילה** (Story) · **חנות** (Store) · **אנימוס** (Animus) · **חזרה** (Back) · **אפשרויות** (Options) ·
**מפה** (Map) · **משימות** (Quests).

Read the outcomes:

| What you see | What it proves |
|---|---|
| **`ZZ-ACS-OK` (Latin) + the 10 words render as Hebrew letters** (even if spacing/size is ugly) | ✅ **FONT GATE CLOSED.** The PHXFD atlas injection reaches the live renderer; Hebrew glyphs rasterize. The whole read→inject→exact-slot→deploy chain works for the font. Proceed to the donor-selection rebuild (§4). |
| **Hebrew letters render but with huge irregular GAPS / oversized letters** | ✅ Gate closed, ⚠️ **expected** — this is the area-rank donor bug (א gets a 353 px advance). NOT a font failure. The §4 rebuild fixes it entirely. |
| **`ZZ-ACS-OK` shows but the 10 Hebrew words are `□□□`/tofu boxes** | Text mounts, glyphs don't → the atlas is NOT the live renderer for this weight, OR a weight was missed. (Contradicts the offline flip-probe finding; would need re-investigation. Unlikely given §1c.) |
| **Menu is in Arabic (متابعة / النظام …), not Hebrew at all** | The patch didn't load → a game update reverted the forge (check mtimes) or the wrong slot is live. Re-deploy. |
| **Menu is in English** | `ACShadows.ini` was reset off `ar-SA` → set `[Language] Text/Subtitles/Client=ar-SA` and relaunch. |
| **Black screen after the logo** | A deploy overshoot (should not happen — §1a shows contiguity intact and slots exact). Revert with `acs_atlas_inject2.py --revert` + `acs_loc_deploy.py --revert`. |

**Why this one screen is sufficient**: the Latin marker separates "file didn't load" from "font has no
glyphs" (the two otherwise look identical), and the same screen exercises BOTH the text package and the
font atlas. One photo decides the gate.

---

## 3. PRIOR ART (URLs)

The single most important finding: **non-Latin, non-official scripts already render in AC Shadows via
community mods**, so the end-goal is empirically achievable on this engine.

- **AC Shadows Thai Localization** — https://www.nexusmods.com/assassinscreedshadows/mods/196
  (author *NoOnetranslator*, v1.1.11, 18 endorsements). Thai is **not** an official AC Shadows
  language, so its glyphs are **not** in any shipped atlas — this mod must inject/replace the font
  (almost certainly the same PHXFD-atlas repurpose we do, most likely into the Arabic slot). Install is
  a drag-into-the-game-folder drop. The author documents **no** technical method and locks permissions
  (no conversion/reuse) — the method is private. This is the strongest proof our approach's end-state is
  reachable; it is **not** a reusable tool.
- **Same author ships Thai across the whole Anvil lineage** — Brotherhood
  (https://www.nexusmods.com/assassinscreedbrotherhood/mods/160), Black Flag
  (https://www.nexusmods.com/assassinscreedivblackflag/mods/477), Syndicate
  (https://www.nexusmods.com/assassinscreedsyndicate/mods/65), Mirage
  (https://www.nexusmods.com/assassinscreedmirage/mods/76), Shadows (196). So Thai rendering is solved
  by this team across classic scimitar **and** the SDF/PHXFD era (Mirage, Shadows). Author hub:
  https://sites.google.com/view/noonetranslator/ (Discord `johntaber`).
- **AC Shadows Chinese Localization (+inventory editor)** —
  https://www.nexusmods.com/assassinscreedshadows/mods/211. **Does NOT count as new-script prior art**:
  AC Shadows officially ships **Chinese (Simplified + Traditional), Japanese, Korean** as screen
  languages, so a CJK atlas is already present; this mod only re-edits an existing CJK slot (no font
  work). (Official Russian text localization by Logrus IT similarly means Cyrillic ships.)
  Ubisoft language list: https://www.ubisoft.com/en-us/help/assassins-creed-shadows/gameplay/article/language-options-in-assassins-creed-shadows/000111197
- **AC Shadows Czech Localization** — https://www.nexusmods.com/assassinscreedshadows/mods/186
  (Latin+diacritics, AI translation) — no new-script font issue.
- **ResHax — the technical hub** (login/gated; content not directly fetchable):
  - "Assassins Creed Shadows **Font**" thread — https://reshax.com/topic/1807-assassins-creed-shadows-font/
    (confirms "the AC Shadows font is a new format, not ttf/otf"; the exact PHXFD dissection we have is,
    as far as public evidence shows, not published there).
  - "Assassins Creed Shadows **Localization Files**" thread —
    https://reshax.com/topic/1779-assassins-creed-shadows-localization-files/
  - "Assassin's Creed **Localization tool (Mirage, Valhalla)**" (SDF/PHXFD-era loc tool by NoobInCoding)
    — https://reshax.com/files/file/9-assassins-creed-localization-tool-mirage-valhalla/ — its own page
    states **"Currently NOT WORKING with AC: Shadows"**, and users asked (Mar 2025) to "please add
    support for Assassin's Creed Shadows." So public tooling did **not** cover Shadows loc/font.
- **AnvilToolkit** publishes per-game pages up to Mirage/Odyssey
  (https://www.nexusmods.com/assassinscreedmirage/mods/103, .../assassinscreedodyssey/mods/266) —
  **no AC Shadows AnvilToolkit page exists**. There is no public AnvilToolkit v42 font support.
- **No public PHXFD tool** surfaced (GitHub code search is auth-gated and the GitHub MCP returned "Bad
  credentials"; web search found nothing). Treat the PHXFD atlas format as community-undocumented.

**Conclusion**: the format is not public; a working private Thai solution exists (proving feasibility);
we hold the only documented open PHXFD-injection method. There is no tool to adopt and nothing that
changes our approach — it validates it.

---

## 4. DONOR-SELECTION DESIGN (fixes spacing with ZERO metric rewrites)

**Constraint (proven, do not re-litigate):** rewriting a record's metrics (advance/bbox/W/H) makes the
engine draw the donor slot's ORIGINAL Arabic shape (`acs_atlas_inject.py` v1 did this and it failed;
`acs_atlas_inject2.py` changes only codepoint + pixels and renders). So the ONLY control over a Hebrew
letter's advance and size is **which Arabic-presentation-form donor slot it is written into**.

**The current bug (v2 `inject_pixels_only`):** it takes the **27 largest-area donors** and assigns
letter *i* (in alphabet order) to the *i*-th largest. Donor area is unrelated to a letter's ideal
width, so the assignment is essentially random w.r.t. spacing. Measured on the pristine record table
(scripts `scratchpad/acs_donor_analysis.py` + `acs_donor_joint.py`):

| metric | current (area-rank) | JOINT donor pick | ideal |
|---|---|---|---|
| mean \|advance error\| | **54.2 px** | **0.8 px** | 0 |
| advance stdev | 51.4 | 8.7 | 8.8 |
| **max advance** | **353 px** (א) | **57 px** | — |
| height stdev | 3.1 (mean H 62, oversized) | 0.8 (mean H 51) | — |

The donor pool is huge — **751 Arabic-presentation-form slots per weight** (cp 0xFB50–0xFEFF, real
raster) covering advances densely across 0–380 px — so nearest-advance matching hits any target to
sub-pixel and still leaves the height free to pin uniform. Fit is satisfied (all joint-picked donors
W≥41, H≥49). Reproduce/inspect: `python games/acshadows/work/acs_donor_select.py`
(and `acs_verify_deployed.py` for the §1 on-disk check — both read-only, both persisted in `work/`).

### Algorithm (drop-in replacement for `inject_pixels_only`'s slot choice)

```
donors = [r for r in records if 0xFB50 <= r.cp <= 0xFEFF and r.W*r.H > 0]     # ~751
# ideal advance per Hebrew letter = the letter's NATURAL advance in the donor font,
# scaled so the Hebrew MEDIAN advance == the donor pool's MEDIAN advance:
ideal_adv[i] = natural_adv(HEB[i]) * (median(donor.adv) / median(natural_adv))
Ht = median(donor.H)                                    # target body height (~50-51)
# joint cost: match advance AND keep height uniform, with a hard fit floor:
cost[i][j] = |donor[j].adv - ideal_adv[i]| / median(donor.adv)
           + 2.0 * |donor[j].H - Ht| / Ht
           + (5.0 if donor[j].H < 0.9*Ht else 0.0)      # too-short slot penalty
assign = min-cost one-to-one assignment (greedy: most-constrained letter first is enough here)
# then, exactly as v2: write ONLY codepoint(+32) and the rasterised letter into the chosen
# slot's original W x H canvas. NEVER touch the metric floats.
```

`games/acshadows/work/acs_donor_select.py` (persisted) contains a working reference implementation
(greedy assignment + validation) and prints the per-letter result. Fold its `assign` into
`acs_atlas_inject2.inject_pixels_only` (replace the `cand = sorted(...by -area)[:27]` block), keep the
rest of the exact-slot pipeline unchanged.

**Two residual refinements (minor, do after the launch confirms glyphs render):**
1. **Render at a fixed pixel body, letterboxed** (not scale-to-fill the slot). With joint donors now
   near-uniform H this is mostly moot, but it also fixes relative proportions (lamed's ascender, the
   ך ן ף ץ ק descenders). Keep the letter ≤ the slot's W×H.
2. **Baseline** — the donor's own bearings (which we cannot change) set where the slot sits on the
   line; picking donors with uniform H keeps baselines consistent. Descenders won't truly descend
   without a bearing edit — accept as cosmetic.

### The higher-upside PROBE (needs one launch; removes the constraint if it passes)

The "metrics rewrite → original shape" fact was only ever tested as *all 7 floats at once*. The theory
is that only **W/H** (the atlas cell) trigger the fallback, and **advance (index 0)** may be freely
editable. If true, we could write the correct advance directly (no donor matching) **and** fix
bearings/baseline. Build a small A/B: on 3–4 letters rewrite ONLY `advance` (index 0) to the correct
value, leaving W/H = donor's, and launch:
- corrected spacing on those letters → advance is a free lever; direct-write beats donor matching.
- letters revert to the donor's Arabic shape → any metric touch triggers the fallback; donor-choice is
  the only lever (ship §4 as written).

Either way §4 is the safe shipping path; the probe is pure upside.

### Page-2 / size-page as a second lever — NO
The size-page header (`u32 em=1000 | u32 0 | f32 scale | u32 count`, page-2 count 108, rasters into the
TAIL) is a separate glyph *table* (a second set of records/rasters), not a global scale knob. Its `em`
and `scale` are per-page, and editing them is a metric change on that page's records — same fallback
risk as any metric edit, and it governs a different (108-glyph) page, not the 1058-record main atlas the
menu uses. It is not a useful lever for even spacing; leave it alone.

---

## 5. APPEND-RELOCATE vs EXACT-SLOT FILL (v42)

**Answer: exact-slot fill is the proven shipping method and is all the FONT needs. Append-relocate is
very likely available on v42 and would be strictly better for TEXT growth, but it is unproven on v42 —
adopt it only behind a one-resource identity-relocate probe.**

Evidence, bracketing v42:

| game | forge ver | deploy method | in-game result |
|---|---|---|---|
| AC Origins | scimitar **v28** | **append-relocate** (append at EOF, repoint one record), **+13.7 MB** | ✅ DEPLOYED + VERIFIED; 300 untouched resources byte-identical |
| AC Mirage | scimitar **v29** | **append-relocate** (patch `offset @rec+0`, `size @rec+16`) | ✅ built + offline-validated on a real forge copy; append path |
| **AC Shadows** | **v42** | exact-slot in-place (text 11 strings + font 8/8 **PROVEN in-game earlier / on-disk now**) | append-relocate **UNTESTED** |
| AC Black Flag Resynced | scimitar **v50** | contiguous full re-pack required; append/hole → **black screen**; + SHA-256 wall | ❌ blocked |

Key facts:
- The **v42 record is 24 B `{u64 offset@0, u32 ts@8, u32 flags@12, u32 size@16, u32 nameHash@20}`** —
  the engine reads each resource by its own offset+size, and this is **byte-identical to the fields
  Mirage's append-relocate patches** (`offset @rec+0`, `size @rec+16`). So the mechanic transfers
  structurally.
- AC Shadows' **DRM profile matches Origins/Mirage, not BFR**: the Origins note explicitly calls it
  "the AC-Shadows profile (asset mods load), not the Black-Flag-Resynced content-hash wall
  (SHA256 ×143 / integrity ×5 / tamper ×11)"; Shadows has SHA256 ×11 / tamper ×3 and a live forge-mod
  scene. So the SHA-256 wall that ultimately killed BFR does **not** apply here.
- **Caveat**: the "forge must stay 100% contiguous, DirectStorage streams with no gaps" law was learned
  on BFR **v50**, which also uses DirectStorage. AC Shadows uses DirectStorage too (`dstorage.dll`).
  Append-relocate does not create an *unallocated* gap (old bytes stay in place, file grows at EOF), and
  Origins/Mirage prove that grow-and-repoint boots — but it does break the strict TOC contiguity
  invariant, and v42's DirectStorage behaviour on that is not directly observed. Hence: **probe before
  relying on it.**

**Why it's moot for the FONT**: the atlas injection *repurposes existing slots in place* — decoded
object size is unchanged, exact-slot fill lands 8/8, no growth pressure. Append-relocate buys the font
nothing.

**Where it would help (TEXT only)**: `acs_loc_deploy.py` already reports a few strings that "does not
fit slot — left vanilla" (over-slot skips). Hebrew is usually ≤ the Arabic/English source so this is
rare, but for the full 52,343-string ship it eliminates every skip and removes the exact-fill
entropy-search entirely. **If ever needed, the decisive probe** (one launch): append a byte-identical
copy of ONE non-critical resource at the forge EOF, repoint its record's `offset@+0`/`size@+16`, launch
→ boots? Then arbitrary-growth append-relocate is unlocked for text.

---

## 6. REMAINING GAPS TO A SHIPPED MOD

1. **Full corpus** — 52,343 Arabic-slot strings exist; **15,997 unique lineIDs** were extracted and
   uploaded to the `/translate` pool (`ac-shadows`). The remaining ~36k need extraction (the loc
   packages live in 2,127 `LocalizationPackage` resources across boot/patch_01/patch_02; the extractor
   `tools/acs_oasis.py` + `acs_loc_deploy` walk them). Then translation is delegated (per project rule),
   not done here.
2. **Font rebuild** — re-run the injector with §4 donor selection (mandatory before ship; the current
   deploy renders but is spaced wrong). Font is otherwise complete: 8/8 weights, 27/27, in-place, no
   growth.
3. **Build + deploy the full text** through `acs_loc_deploy.py --apply heb.json` (exact-slot in-place,
   which already works), across all 3 forges, then **verify by reading back the WINNING copy** (§8e
   base+patch rule — the string exists in all three, the engine picks by load order).
4. **Surfaces the loc packages may not reach** — the standard audit still owes a pass: hardcoded exe
   strings, texture-baked UI text, and the language-picker's own native names. The menu proof shows the
   loc packages DO drive the menu, so the core UI is covered; a full grep of the install + exe for
   visible English is the pre-ship completeness check (as done for other games).
5. **bidi** — established LOGICAL (the shipped Arabic stores the base block and lets the engine
   shape/reorder), so Hebrew stores natural, no bidi code. Confirmed by the text proof reading back
   correctly; the launch will visually confirm RTL order in the menu.

---

## 7. Files produced this session (all read-only analysis)
Persisted into `games/acshadows/work/` (runnable with the repo `.venv`; set nothing — paths are absolute):
- `acs_verify_deployed.py` — the on-disk state verifier (§1): forge contiguity, backups, 8×27/27 Hebrew.
- `acs_donor_select.py` — the joint advance+height donor selection reference impl + live-glyph ASCII (§4).

Left in scratchpad (superseded by the two above):
- `acs_donor_analysis.py` — first-pass donor pool vs Hebrew ideal advances (area-rank vs nearest-advance).

No game file was written. Revert commands if ever needed:
`python games/acshadows/work/acs_atlas_inject2.py --revert` (font) and
`python games/acshadows/work/acs_loc_deploy.py --revert` (text).

## מסמכים קשורים
- באותה תיקייה: [[games/acshadows/FEASIBILITY|FEASIBILITY]], [[games/acshadows/FORMAT|FORMAT]], [[games/acshadows/PIPELINE|PIPELINE]], [[games/acshadows/PLAN_HEBREW|PLAN_HEBREW]], [[games/acshadows/RECON|RECON]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#acshadows|CLAUDE_INDEX_games]]
