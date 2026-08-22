# Watch Dogs 2 — Hebrew translation RECON (groundwork)

Initial local reconnaissance for assessing whether WD2 can be translated to proper
RTL Hebrew, using (where possible) the project's established Arabic-slot pipeline.

Date: 2026-06-16. Status: **feasibility study — nothing modified in the game folder.**

## Install

| Item | Value |
|---|---|
| Path | `F:\Games\WATCH_DOGS2` |
| Store | Ubisoft Connect (game ID 2688) |
| Engine | **Disrupt** (`bin\Disrupt_64.dll`) |
| Exe | `bin\WatchDogs2.exe` (+ `SplashScreen.exe`) |
| Anti-cheat | **EasyAntiCheat present** (`EAC.exe`, `EasyAntiCheat\`) |

## Data layout — `data_win64\`

`.dat` (data blob) + `.fat` (file-allocation-table / index) archive pairs:

| Archive | .dat size | Notes |
|---|---:|---|
| `common` | 536 MB | shared assets |
| `patch` / `patch2` | 1992 / 356 MB | patch layers (later overrides earlier) |
| `installpackage` | 2134 MB | base package |
| **`patch_english`** | **146 MB** | language layer (text + localized audio) |
| **`installpackage_english`** | **53 MB** | base language layer |
| `patch2_english`, `sound_english` | small | |
| `videos`, `sound`, `shadersobj` | large | non-text |

Subfolders: `data_win64\worlds\san_francisco`, `data_win64\dlc\{dlc1..3, custo01..20, ulc_*}`.

## FAT format — CONFIRMED by header bytes

All `.fat` files begin with magic **`35 54 41 46`** = ASCII **`5TAF`** (i.e. "FAT5"),
version dword **`0b 00 00 00`** = **version 11**.

```
patch_english.fat : 35 54 41 46 0b 00 00 00 01 06 46 00 ff ff ff ff ...   (171,912 B)
common.fat        : 35 54 41 46 0b 00 00 00 01 06 46 00 ff ff ff ff ...   (120,732 B)
patch.fat         : 35 54 41 46 0b 00 00 00 01 06 46 00 ff ff ff ff ...   (1,368,572 B)
installpackage_english.fat : 35 54 41 46 0b 00 00 00 ...                  (53,892 B)
```

→ This is the **Disrupt/Dunia FAT5 v11** container (Watch Dogs 2 / Far Cry Primal era).
The relevant unpackers/repackers (Gibbed.Disrupt family / QuickBMS scripts) target this.

Text is stored as **Oasis strings** (`oasisstrings_compressed.bin` / `.oasis`), keyed by
numeric CRC ids — the actual UI/subtitle/dialogue text lives inside these archives
(language text most likely in `patch_english.dat` / `installpackage_english.dat`).

## ⚠️ CRITICAL FINDING — no RTL locale ships

Shipped languages (from `Support\Readme\` subfolders): **English, French, German,
Italian, Spanish (+Mexican), Polish, Russian, Czech, Dutch, Hungarian,
Brazilian-Portuguese, Japanese, Korean, Simplified + Traditional Chinese.**

**No Arabic. No Hebrew. No RTL locale at all.**

Consequence: the platform's core trick — *hijack the shipped Arabic locale slot to
inherit the engine's tested RTL/bidi rendering for free* (proven on CP2077 / Steam /
Spider-Man 2) — **is NOT available here**. Whether proper RTL Hebrew can render in
Disrupt is the make-or-break unknown driving the feasibility study.

(Note: `EasyAntiCheat\Localization\ar_sa.cfg` exists, but that is only the EAC overlay's
own UI language — unrelated to in-game text rendering.)

## Open questions driving the feasibility workflow

1. Exact Oasis string format + encoding + which archive holds the EN text.
2. A confirmed-working extract **and repack** tool chain for WD2's FAT5 v11.
3. **RTL**: does Disrupt do any bidi shaping, or must Hebrew be pre-shaped/visually
   reversed at build time? Do the UI fonts even contain Hebrew glyphs?
4. EAC: is single-player offline file-modding safe from bans? Load order for mods.
5. Precedents: any RTL (Arabic/Persian/Hebrew) fan translation of a Disrupt/Dunia title.

→ See the feasibility brief (workflow output) appended/linked by the session.

## מסמכים קשורים
- באותה תיקייה: [[games/watchdogs2/FEASIBILITY|FEASIBILITY]], [[games/watchdogs2/PIPELINE|PIPELINE]]
- אינדקס לפי משחק: [[CLAUDE_INDEX_games#watchdogs2|CLAUDE_INDEX_games]]
