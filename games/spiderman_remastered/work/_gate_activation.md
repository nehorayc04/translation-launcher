# MSMR — GATE: THE ACTIVATION LEVER  🟢 GREEN (best possible outcome)

**Verdict: the text language is ONE `REG_DWORD` in `HKCU`. It is a drop-in
`kind:"registry"` entry in `translation_manager/game_language.py` — the same
mechanism Spider-Man 2 already uses. Activation costs the user ZERO actions.**

Read-only investigation. **Nothing under `D:\Games\Spider-man Remastered` or in the
user's settings was modified.** Every claim below is backed by a command that was
actually run; logs archived as `_activation_probe{1..8}.log`, scripts as
`_probe_activation{,2..8}.py`.

---

## 0. TL;DR for the pipeline

| Question | Answer | Confidence |
|---|---|---|
| Where is the TEXT language stored? | `HKCU\Software\Insomniac Games\Marvel's Spider-Man Remastered` → **`TextLanguage`** (REG_DWORD) | **certain** — the path string is literally in the exe |
| Which value = the Arabic (Hebrew) slot? | **`19`** (`kLanguageArabic`) | **proven** (§4) |
| Which value = English? | **`1`** (`kLanguageEnglish`) | **proven** (§4) |
| Is it a binary save blob? | **NO.** `-userprefs.save` exists but holds **no** language key | **certain** (§3) |
| Launcher mechanism | `kind:"registry"` — already implemented | — |
| Text vs voice independent? | **YES** — separate `TextLanguage` / `AudioLanguage` values | **certain** (§5) |
| User actions to activate | **ZERO** (launcher writes it pre-launch) | (§6) |

Ready-to-paste `LANG_CONFIGS` entry:

```python
"spiderman-remastered": {
    "kind":   "registry",
    "subkey": r"Software\Insomniac Games\Marvel's Spider-Man Remastered",
    "value":  "TextLanguage",
    "codes":  {"english": 1, "hebrew": 19},   # 19 = kLanguageArabic
    # MSMR does NOT have SM2's `englishVO` (proven absent, §5).
    # See §7 for the FirstRun caveat before shipping.
},
```

> ⚠️ **Do NOT copy Spider-Man 2's numbers.** SM2 uses `english=0, hebrew=18`.
> MSMR's enum is **different** (§4) — `0` is `kLanguageNone`, and Arabic is `19`.

---

## 1. Resolving the REAL user profile (the documented sandbox trap)

`%USERPROFILE%` / `%APPDATA%` / `%LOCALAPPDATA%` are redirected in this
environment, so everything was resolved through `SHGetKnownFolderPath`
(`FOLDERID_Profile`) per the CLAUDE.md rule.

```
KF Profile          = C:\Users\Nehoray_Cohen
KF Documents        = C:\Users\Nehoray_Cohen\Documents
KF LocalAppData     = C:\Users\Nehoray_Cohen\AppData\Local
KF RoamingAppData   = C:\Users\Nehoray_Cohen\AppData\Roaming
KF SavedGames       = C:\Users\Nehoray_Cohen\Saved Games
---- env ----
$env:USERPROFILE    = C:\Users\Nehoray_Cohen
$env:APPDATA        = C:\Users\Nehoray_Cohen\AppData\Roaming
```

**On THIS run the env vars happened to agree with the known folders** (this shell
was not redirected). That is luck, not a guarantee — the launcher code must keep
using `FOLDERID_Profile`. It does not matter for the shipped switch anyway,
because the answer turned out to be the **registry**, which has no path problem.

---

## 2. Where the settings actually live — the search

### 2.1 Documents  ✅ (user data root, but not the language)

The game's **own log** names it:

```
[Startup] Marvel's Spider-Man Remastered
[Startup] Build: v1.812.1.0
[Startup] Game directory: C:\Users\<username>\Documents\Marvel's Spider-Man Remastered\
```
— `Documents\Marvel's Spider-Man Remastered\Marvel's Spider-Man Remastered.log`

Contents:

```
C:\Users\Nehoray_Cohen\Documents\Marvel's Spider-Man Remastered\
    76561198241587222\-userprefs.save          1460
    76561198241587222\slot0-s.save            94734
    76561200016358402\-userprefs.save          1464
    76561200016358402\slot0-s.save           112414
    76561200016358402\slot0-s-manual-0.save   95774
    Marvel's Spider-Man Remastered.log         23873
    Marvel's Spider-Man Remastered-v1.812.1.0 2025-06-05-02-00-19.mdmp
    Screenshots\
```

Per-Steam-ID subfolders; `-userprefs.save` is the settings blob. **Analysed in §3
— it does NOT contain the language.**

### 2.2 LocalAppData / RoamingAppData  ❌ (no settings)

```
AppData\Local\      -> only "Marvel's Spider-Man 2\firstboot.flag"  (SM2, not MSMR)
AppData\Roaming\Insomniac Games\Marvel's Spider-Man Remastered\
                       cache.pso            (shader cache)
                       crs\metadata         (0 bytes)
                       crs\settings.dat     (40 bytes — crash-reporter opt-in)
                       crs\reports\
```
`crs` = the **c**rash-**r**eporting **s**ervice (`crs-client.dll`, `crs-handler.exe`
in the game folder). No language, no game settings.

### 2.3 Saved Games / profile root  ❌

`Saved Games\` holds only `.lnk` shortcuts (all pointing at
`C:\Users\nc528\OneDrive\` — a stale profile, unrelated).
`C:\Users\Nehoray_Cohen\.insomniac\` contains only `.nomedia` + an empty
`InsomniacEngine\`.

### 2.4 Steam  ❌ (not applicable — cracked install)

```
HKCU\Software\Valve\Steam\SteamPath = c:/program files (x86)/steam
userdata\1714033054\1817070  -> does not exist
userdata\19627\1817070       -> does not exist
localconfig.vdf              -> no "1817070" block
```
The game is a FitGirl repack with an FLT Steam-emu, not a Steam-library install.
There is no Steam per-app language setting and no launch options for it.

### 2.5 `flt.ini` — the **Steam-emu's** setting, NOT the game's ❗

`D:\Games\Spider-man Remastered\flt.ini` (byte-identical duplicate at
`NoDVD\FLT\flt.ini`):

```ini
[GameSettings]
AppId=1817070
UserName=Player
Language=English
Offline=0
AutoDLC=0
Penis=0
BuildId=9304506

[DLC]
2083110=Marvel's Spider-Man Remastered - Pre-purchase Entitlements
```

**Evidence it belongs to the emulator, not the game — two independent proofs:**

1. **Company it keeps.** `Language` sits inside `[GameSettings]` next to `AppId`,
   `UserName`, `Offline`, `AutoDLC`, `BuildId` and a `[DLC]` list. Those are pure
   Steam-emulation fields. It is shipped in `NoDVD\FLT\` — the crack's own folder,
   alongside sibling emus that carry the same field
   (`NoDVD\CODEX\steam_emu.ini`, `NoDVD\ALI213\SteamConfig.ini`).
2. **The game binary never reads any INI.** Byte-scan of `Spider-Man.exe`
   (121,325,496 B), ASCII **and** UTF-16:

   | string | ASCII hits | UTF-16 hits |
   |---|---|---|
   | `flt.ini` | 0 | 0 |
   | `.ini` | 0 | 0 |
   | `Language=` | 0 | 0 |
   | `TextLanguage` *(positive control)* | **2** | 0 |
   | `Software\Insomniac Games\Marvel's Spider-Man Remastered` *(control)* | **1** | 0 |

   The controls prove the scan works on this binary; the zeros are real.

**What it DOES affect:** `Language=English` is what the emulated
`steam_api64.dll` returns for `GetCurrentGameLanguage()`, which the game uses
**only to seed `TextLanguage` on first run** (§7). It is not the live setting and
the launcher must not touch it.

### 2.6 Registry  ✅ **THE ANSWER**

```
HKCU\Software\Insomniac Games                                  -> EXISTS
    SUBKEY Marvel's Spider-Man 2
    SUBKEY Marvel's Spider-Man Remastered
    SUBKEY Ratchet & Clank - Rift Apart

HKCU\Software\Insomniac Games\Marvel's Spider-Man Remastered   -> EXISTS
    VALUE  'TextLanguage'   REG_DWORD = 19
    VALUE  'FirstRun'       REG_DWORD = 0
    SUBKEY Graphics   (Monitor, Fullscreen, TextureQuality, RTReflections, HDR, ...)
    SUBKEY Input      (EnableMouseSmoothing, DPad_*, *_Bumper_*, ...)
```

Not present (checked, all reported `NOT PRESENT`):
`HKCU\Software\{Sony Interactive Entertainment, Nixxes, Nixxes Software, Marvel,
PlayStation, PlayStation PC}`, and `…\Insomniac Games\Marvel's Spider-Man`.

**The exe itself contains the path** — authoritative, not inferred:

```
0x037DB2A9: ['%s cannot be started while Steam is not running.',
             'You do not own %s on Steam.',
             'Failed to initialize Steam.',
             "Software\\Insomniac Games\\Marvel's Spider-Man Remastered",
             'https://upload.studiocrs...']
```

---

## 3. `-userprefs.save` — a binary DAT1 blob, and the language is **NOT** in it

```
size = 1460 / 1464 bytes
printable 807/1460 (55%),  NUL bytes 367
first 16 bytes: 31 54 41 44 08 00 00 00 b4 05 00 00 01 00 00 00
                 '1' 'T' 'A' 'D'   <-- "DAT1" little-endian
```

It is the **same DAT1 serialization as the game archives and the `slot0-s.save`
game saves** — i.e. exactly the GoWR `userpreferences` shape. Complete key list
(49 ASCII runs, all of them):

```
1TAD  Save  MouseControlNormal  MouseControlAiming  RecentTipHashes
CameraInvertX  CameraInvertY  RumbleEnabled  ControllerSpeakerEnabled
SubtitlesEnabled  TextSubtitlesEnabled  GoreEnabled  ProfanityEnabled
OutlinesEnabled  VoiceChatEnabled  MasterVolume  MusicVolume  DialogVolume
SFXVolume  UIVolume  ControllerSpeakerVolume  ListeningMode
HeadphonesListeningMode  UIAdjustX  UIAdjustY  UIAdjustW  UIAdjustH
LookSensitivity  GammaCorrection  CrossGameEnabled  CharacterPreference
LastSlot  StartupGammaShown  BootFlowShown  MostRecentTipIndex
NewGamePlusUnlocked  UseEnglishAudio  EnableLoadingScreens
EnableFastTravelScreens  PSNAccountLinked  AcceptedSIEAnalytics
SensitivityFactorX  SensitivityFactorY  InvertX  InvertY
```

Containment test on the raw bytes:

```
contains 'TextLanguage' : False
contains 'AudioLanguage': False
contains 'Language'     : False
contains 'Arabic'       : False
contains 'English'      : True     <- only inside 'UseEnglishAudio'
```

**⛔ DO-NOT-EDIT**, and happily **we never need to**:

* It is a checksummed-looking binary blob living **in the same directory, with
  the same extension and the same `1TAD` magic, as the user's game saves** —
  the GoWR precedent says do not go near it.
* The only language-adjacent key is **`UseEnglishAudio`** (an *audio* override,
  §5) — not the text language.
* **The text language is not in this file at all**, so the switch never touches it.

---

## 4. `TextLanguage = 19` → **`kLanguageArabic`** (proven, not assumed)

### 4.1 The enum name table

One clean 32-entry, NUL-delimited table at `0x04EB3878` in `Spider-Man.exe`:

| pos | name | | pos | name |
|---|---|---|---|---|
| 0 | `kLanguageNone` | | 16 | `kLanguageSwedish` |
| 1 | `kLanguageEnglish` | | 17 | `kLanguageMxSpanish` |
| 2 | `kLanguageUkEnglish` | | 18 | `kLanguageBrPortuguese` |
| 3 | `kLanguageDanish` | | **19** | **`kLanguageArabic`** |
| 4 | `kLanguageDutch` | | 20 | `kLanguageTurkish` |
| 5 | `kLanguageFinnish` | | 21 | `kLanguageLaSpanish` |
| 6 | `kLanguageFrench` | | 22 | `kLanguageChineseSimplified` |
| 7 | `kLanguageGerman` | | 23 | `kLanguageChineseTraditional` |
| 8 | `kLanguageItalian` | | 24 | `kLanguageCaFrench` |
| 9 | `kLanguageJapanese` | | 25 | `kLanguageCzech` |
| 10 | `kLanguageKorean` | | 26 | `kLanguageHungarian` |
| 11 | `kLanguageNorwegian` | | 27 | `kLanguageGreek` |
| 12 | `kLanguagePolish` | | 28 | `kLanguageRomanian` |
| 13 | `kLanguagePortuguese` | | 29 | `kLanguageThai` |
| 14 | `kLanguageRussian` | | 30 | `kLanguageVietnamese` |
| 15 | `kLanguageSpanish` | | 31 | `kLanguageIndonesian` |

**`kLanguageHebrew` = 0 occurrences** (ASCII and UTF-16; `Hebrew` = 0 in both).
⇒ There is no Hebrew locale — **the Arabic-slot hijack is the only route.**

### 4.2 🔴🔴 THE ENUM IS **PER-TITLE** — never carry SM2's number across

Same 32-slot table extracted from `RiftApart.exe` for comparison:

| | MSMR | R&C Rift Apart |
|---|---|---|
| pos 16 | Swedish | Swedish |
| pos 17 | **MxSpanish** | *(absent)* |
| pos 18 | BrPortuguese | BrPortuguese |
| pos 19 | **Arabic** | Turkish |
| pos 18 | — | **Arabic** |
| pos 31 | Indonesian | **Croatian** |

Confirmed by exact string counts (`_probe_activation8.py`):

```
kLanguageMxSpanish   MSMR=1  R&C=0
kLanguageCroatian    MSMR=0  R&C=1
```

MSMR **inserts `kLanguageMxSpanish` at 17**, shifting Arabic from 18 → **19**.
SM2 ships `hebrew: 18`; **MSMR must ship `19`.** A copy-paste of the SM2 entry
would silently select **Turkish**.

### 4.3 Proving the enum VALUE equals the table POSITION

The name table gives *order*, not the numeric base. Two candidates:

* **H1** — `kLanguageNone = 0` ⇒ value == table position ⇒ Arabic = **19**
* **H2** — `kLanguageNone = -1` ⇒ value == position − 1 ⇒ Arabic = **18**

**Proof (self-contained in MSMR): a language that ships a DUB must also ship
SUBTITLES.**

MSMR's `toc` lists 12 per-language voice archives, in this order:

```
[34] a00s034.us   [35] a00s035.fr   [36] a00s036.de   [37] a00s037.it
[38] a00s038.jp   [39] a00s039.pl   [40] a00s040.pt   [41] a00s041.ru
[42] a00s042.es   [43] a00s043.br   [44] a00s044.ar   [45] a00s045.la
```
(only `.us` is on disk — an English-only selective install; the others are still
declared in the toc, so the game *ships* those languages.)

MSMR's 23 localization variants occupy span slots (`span / 8`):

```
present : 0 1 3 4 5 6 7 8 9 10 11 12 13 14 15 16 18 19 21 23 25 26 27
missing : 2 17 20 22 24
```

Cross the two:

| hypothesis | dubbed-language values | all have a text slot? |
|---|---|---|
| **H1** (None=0) | 1,6,7,8,9,12,13,14,15,18,**19**,21 | ✅ **12 / 12 — zero orphans** |
| **H2** (None=−1) | 0,5,6,7,8,11,12,13,14,**17**,18,**20** | ❌ 17 (`br`) and 20 (`la`) **missing** |

H2 requires Brazilian Portuguese and LatAm Spanish to ship a **full voice dub with
no subtitles** — impossible. **H1 is the mapping.**

Three independent corroborations:

1. **Slot 0 duplicates slot 1.** `slot0 size = 6033201`, `slot1 size = 6033201`
   — byte-for-byte the same length, exactly what you expect if slot 0 is
   `kLanguageNone` falling back to `kLanguageEnglish`.
2. **Live sibling registry.** `HKCU\…\Ratchet & Clank - Rift Apart\TextLanguage
   = 1`, and R&C's table position 1 is `kLanguageEnglish`. (Under H2 that value
   would mean the user deliberately chose *English (UK)*.)
3. **The unshipped slots are exactly the languages a 2018 PS4 title wouldn't
   have:** 2 UkEnglish, 17 MxSpanish (MSMR ships `LaSpanish` at 21 instead),
   20 Turkish, 22 ChineseSimplified (it ships *Traditional* at 23), 24 CaFrench.

### 4.4 A near-miss worth recording

A 26-entry locale-code array sits **immediately after** the name table at
`0x04EB3B2C`:

```
XX us gb dk nl fi de it kr pt ru es se mx br ar tr la cs ct fc cz hu el ro vi
```

It looks like a parallel array and **is not** — it is missing `fr, jp, no, pl,
th, id`, so it has 26 entries against the enum's 32 and cannot be index-aligned.
Forcing the alignment puts `ct` (Chinese Traditional) opposite `kLanguageArabic`.
**Do not use this table to map indices.**

### 4.5 Bonus — the Steam→enum seeding table

A separate 21-entry cluster at `0x037DB12F`, adjacent to the Steam-init error
strings and the registry-path string:

```
english german japanese french italian koreana spanish portuguese tchinese
russian polish dutch finnish norwegian swedish hungarian czech arabic
brazilian greek latam
```

These are Steam's `GetCurrentGameLanguage()` names — used to seed `TextLanguage`
on first run. Note `arabic` is present, so a Steam-side `arabic` also resolves to
`kLanguageArabic`.

---

## 5. TEXT and VOICE are independent → **English VO is preserved for free** ✅

`TextLanguage` and `AudioLanguage` are two **adjacent registry value-name string
constants** in the exe (2 occurrences each, ASCII):

```
0x037DC2F0: [... 'SAVE: Requesting Auto Save', 'TextLanguage', 'AudioLanguage',
             'Game', 'Set_InGame', ...]
```

and the two settings-menu option ids are likewise separate:

```
0x03A20728: [..., 'TextLanguageIndex', 'SettingsKeyBinding', 'SettingsGamepad', ...]
0x03A209C8: [..., 'AllowSIEAnalytics', 'PcOnlyHeader', 'AudioLanguageIndex']
```

Three more reinforcements:

* The live MSMR key currently holds **`TextLanguage` only** — no `AudioLanguage`
  value has ever been written, and the game runs in English audio. Writing
  `TextLanguage` alone provably does not disturb audio.
* MSMR ships a dedicated English-audio override, surfaced in the exe as
  *"Always use English audio if you have it installed regardless of system
  language"*, persisted as **`UseEnglishAudio`** in `-userprefs.save`.
* **This install has only `a00s034.us` on disk** — the other 11 voice archives
  were not installed — so the audio is English regardless of any setting.

**🔴 MSMR does NOT use SM2's `englishVO` registry value.** Verified with a
control:

```
englishVO   MSMR=0   R&C=1      (search method proven working by the R&C hit)
```

SM2's `LANG_CONFIGS` pins `extra: {"englishVO": 1}`. **Do not copy that into the
MSMR entry** — the value does not exist in this game; MSMR's equivalent lives in
the do-not-edit blob and does not need touching.

---

## 6. Cost to the user: **ZERO actions**

* **Via the launcher (the shipping path): 0 actions.** One `REG_DWORD` write to
  `HKCU`, done before the game starts — no elevation (HKCU), no file in the game
  folder, no admin. `game_language.py`'s existing `kind:"registry"` branch
  (`_reg_read`/`_reg_write`, `CreateKeyEx(HKEY_CURRENT_USER, …)`) handles it
  unchanged, including capturing the user's pre-mod value for
  `restore_original()`.
* **Manual fallback: 1 setting.** In-game Options → Language → Text = العربية
  (the exe exposes `TextLanguageIndex` as a settings-menu option). A restart is
  the safe assumption, and it is moot for the launcher path, which writes the
  value while the game is closed.
* **There is no launcher dialog to fight.** `ShowLauncher` = **0 occurrences** in
  `Spider-Man.exe` (control: **1** in `RiftApart.exe`, whose HKCU key does carry
  `ShowLauncher=1`). MSMR has no Nixxes pre-game launcher window.

---

## 7. ⚠️ Caveats and open items

1. **`FirstRun` seeding — verify before shipping.** The key carries
   `FirstRun = REG_DWORD 0`, and the exe holds the 21-name Steam language table
   (§4.5). The obvious reading is that on a **never-launched** install the game
   seeds `TextLanguage` from `GetCurrentGameLanguage()` (which the FLT emu
   answers `English`), which could **overwrite** a language the launcher wrote
   first. Not proven — I did not launch the game. Cheap mitigations, in
   preference order: (a) write the language **after** the user's first launch;
   (b) pin `FirstRun = 1` alongside `TextLanguage` (the same trick SM2 uses for
   `englishVO`) — but confirm that does not skip a needed first-boot step;
   (c) simply re-apply on every launch. **Flagging, not asserting.**
2. **`hebrew: 19` is derived from *this* build** (`v1.812.1.0`, exe dated
   2022-08-12). The enum already differs between MSMR and R&C, so a future MSMR
   patch could in principle shift it. Re-extract the `kLanguage*` table
   (`_probe_activation3.py`) if the exe ever changes.
3. **The user's MSMR is *currently* set to `19` (= Arabic).** Cosmetic
   observation, but worth knowing before an in-game proof: the machine is already
   parked on the Arabic slot (SM2 likewise sits at its own Arabic, `18`).
   `restore_original()` would capture `19` as the "pre-mod" value if `set_mode`
   is called before the user is put back on English — **set English (1) once
   before wiring the switch**, or the restore target will be wrong.
4. **Two Steam-ID profile folders exist** (`76561198241587222`,
   `76561200016358402`) with independent `-userprefs.save`. Irrelevant to the
   language (which is per-machine in HKCU, not per-profile), but relevant to any
   later save-touching work.
5. **`games.id` not decided here.** The example entry above uses
   `"spiderman-remastered"`; the catalog gate owns the real id, and the
   `LANG_CONFIGS` key must match it exactly.

---

## 8. Evidence index

| file | what |
|---|---|
| `_probe_activation.py` / `_activation_probe1.log` | known folders, settings-folder hunt, full registry dump, Steam, game folder, exe keyword scan |
| `_probe_activation2.py` / `…2.log` | enum table at file-offset precision, `-userprefs.save` anatomy, loc-variant census |
| `_probe_activation3.py` / `…3.log` | sibling-exe enum cross-check (R&C), complete `-userprefs.save` key list |
| `_probe_activation4.py` / `…4.log` | live registry for all Insomniac titles, toc archive list, locale-code cluster, PE sections |
| `_probe_activation5.py` / `…5.log` | raw hex of the enum + code table, `.lnk` resolution, broad exe hunt |
| `_probe_activation6.py` / `…6.log` | **the dub-vs-subtitle proof that fixes the enum base** |
| `_probe_activation7.py` / `…7.log` | Text/Audio independence, registry path string, Steam name table, INI negatives |
| `_probe_activation8.py` / `…8.log` | **controls for every negative claim** (ASCII + UTF-16) |

Run any of them with the repo venv:
`./.venv/Scripts/python.exe games/spiderman_remastered/work/_probe_activationN.py`
