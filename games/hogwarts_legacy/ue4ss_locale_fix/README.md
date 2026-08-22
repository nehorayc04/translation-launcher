# HebrewLocaleFix — UE4SS clock/number fix (investigation result)

## ⛔ VERDICT (2026-08-09, tested in-game): NOT VIABLE FOR SHIPPING — HL's own anti-mod system kills the game
Both Lua fixes below **worked correctly** (proven live in `UE4SS.log`: `SetCurrentLocale('en-US')`
applied every second, the news widget `UI_BP_ScrollingTextBlock_C
…WidgetTree.scrollingMOTDText` was found by name and collapsed on every tick). But **~25 seconds
after boot, Hogwarts Legacy's own "Unofficial modifications detected" dialog
(`https://go.wbgames.com/hl-unofficial-mods`) appeared, and shortly after dismissing it the process
exited cleanly — no crash dump, no Windows Application-Error event.** This is the game's own
anti-tamper system reacting to the `dwmapi.dll` proxy injection UE4SS itself requires, independent
of what the Lua script does — even a completely empty UE4SS mod would trigger the same dialog and
(very likely) the same termination. **We do not pursue bypassing it** (DRM/anti-tamper
circumvention is out of scope). UE4SS was fully removed from the game install; only the safe
text-only `.pak` mod ships. This folder is kept for reference only — do NOT reinstall UE4SS for
this purpose without re-confirming HL's anti-mod behavior has changed.

**One real tooling fact worth keeping:** `UE4SS-settings.ini`'s `[EngineVersionOverride]` ships
EMPTY by default, and the pattern scanner then fails with `[PS] Failed to find EngineVersion` on
every attempt → `Fatal Error: PS scan timed out` (UE4SS never loads at all). Hogwarts Legacy is
UE **4.27** — set `MajorVersion = 4` / `MinorVersion = 27` to get past that (needed for ANY future
UE4SS work on this game, unrelated to the anti-mod finding above).


## The finding
The Hebrew mod hijacks arAE, the game's only RTL slot. Unreal derives TWO things from a
culture, and they are **independent settings**:

| UE setting | controls | our value | want |
|---|---|---|---|
| **Language** (`SetCurrentLanguage`) | which localized TEXT loads | arAE → **Hebrew** ✅ | keep |
| **Locale** (`SetCurrentLocale`) | date/number/**time** FORMATTING (clock `م/ص`, ٠١٢ digits) | arAE → Arabic ✗ | en-US |

So the clock `م`/`ص` + Arabic-Indic digits come from the **formatting LOCALE**, not the text.
`UKismetInternationalizationLibrary::SetCurrentLocale("en-US")` is a static BlueprintCallable
UFunction → **UE4SS Lua can call it** and switch ONLY the formatting to en-US, leaving the
Hebrew text intact. → **the clock IS fixable** (see `HebrewLocaleFix/scripts/main.lua`).

## ⚠️ The news card is NOT fixable this way
The main-menu "News of the Day" is a **WB live-service server feed keyed on the text LANGUAGE**
(arAE) — the server returns Arabic. `SetCurrentLocale` changes only client-side FORMATTING, not
the language code sent to the news server. The only ways to English news are (a) revert the text
language to English (defeats the whole mod) or (b) hook/rewrite the news HTTP request
(invasive, network-layer). **Recommendation: leave the news as-is** — it is one edge card, not
the game's text.

## Install (needs UE4SS — a separate framework, single-player, safe with Denuvo)
1. Install **UE4SS** for Hogwarts Legacy (dwmapi/xinput proxy DLL into
   `Phoenix\Binaries\Win64\`). It is the standard HL Lua-mod framework (large Nexus scene).
2. Copy `HebrewLocaleFix\` into `Phoenix\Binaries\Win64\ue4ss\Mods\`.
3. Add a line `HebrewLocaleFix : 1` to `ue4ss\Mods\mods.txt` (the `enabled.txt` here also enables it).
4. Launch. The clock should read AM/PM with Latin digits while the UI stays Hebrew. F10 re-applies.

## Status
**Retired — see the verdict at the top.** The Lua logic is correct and could be reused if HL's
anti-mod detection is ever removed/relaxed, or ported to a game whose anti-tamper doesn't react
to UE4SS. `main.lua` v2 (persistent `LoopAsync` reapply, since a one-shot
`RegisterInitGameStatePostHook` gets silently overwritten by the game's own frontend-level locale
re-apply) is the working version — kept for reference.
