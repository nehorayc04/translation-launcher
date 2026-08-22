"""
Game-installation detector - finds installed games across every major PC
launcher AND drag-and-drop installs that live outside any launcher.

Coverage:
  • Steam              (registry + libraryfolders.vdf + appmanifest_*.acf)
  • Ubisoft Connect    (HKLM\\Ubisoft\\Launcher\\Installs)
  • Epic Games         (Manifests/*.item JSON)
  • GOG Galaxy         (HKLM\\GOG.com\\Games)
  • Rockstar           (HKLM\\Rockstar Games\\<title>)
  • Xbox / MS Store    (XboxGames\\<title>\\Content + ModifiableWindowsApps)
  • EA App / Origin    (HKLM\\Electronic Arts\\EA Desktop / Origin Games)
  • Amazon Games       (GameInstallInfo.sqlite)
  • Standalone         (deep-scan walks 2 levels under known roots; if the
                         folder name doesn't match, an executable-fingerprint
                         fallback inspects `*.exe` filenames inside)

All output is normalized to the launcher's own catalog IDs (matches
`games_catalog.ALL_GAMES.id`), so the rest of the app can do a simple
`detected[catalog_id]` lookup to get the install path.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import string
import sys
import time
from pathlib import Path
from typing import Callable

# winreg only exists on Windows. Wrap so the module still imports on Linux/Mac.
try:
    import winreg
except ImportError:
    winreg = None


# ─────────────────────────────────────────────────────────────
# Persistence - survive app restarts
# ─────────────────────────────────────────────────────────────
# Detected games are mirrored to disk after every scan so the next launch
# starts with the previous results already populated. We re-validate each
# path on load (drops entries whose folder was deleted in the meantime).
_STORE_FILE = Path.home() / ".translation_manager" / "detected_games.json"


def _load_persisted() -> dict[str, Path]:
    """Self-healing read - a corrupt detected_games.json falls back to its `.bak`
    (and repairs itself) instead of forcing the user through a full re-scan."""
    from . import resilience
    data = resilience.read_json(_STORE_FILE, default={}, name="detected_games")
    if not isinstance(data, dict):
        return {}
    out: dict[str, Path] = {}
    for cid, raw in data.items():
        if not isinstance(raw, str):
            continue
        p = Path(raw)
        if p.exists():
            out[cid] = p
    return out


def _save_persisted(payload: dict[str, Path]) -> None:
    """Self-healing, atomic write (keeps a `.bak` of the last good scan)."""
    from . import resilience
    resilience.write_json(_STORE_FILE, {k: str(v) for k, v in payload.items()},
                          name="detected_games")


# ─────────────────────────────────────────────────────────────
# Catalog-ID matching - every detected display name / folder name
# gets normalized and matched against these patterns. First match wins.
# ─────────────────────────────────────────────────────────────
# Edition suffixes commonly appended by launchers - strip them before matching
# so "GTAV Legacy" / "Cyberpunk Ultimate Edition" / "Witcher 3 GOTY" all resolve
# to their base catalog entries.
_EDITION_SUFFIXES = [
    "directorscut", "gameoftheyearedition", "gameoftheyear", "goty",
    "definitiveedition", "remastered", "ultimateedition", "ultimate",
    "completeedition", "complete", "deluxeedition", "deluxe",
    "goldedition", "gold", "specialedition", "special",
    "anniversaryedition", "anniversary", "legacy",
    "enhancedversion", "enhanced", "redux", "collection",
]


def _norm(s: str) -> str:
    """Lowercase + strip non-alphanumerics + drop trailing edition suffixes."""
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "", s)
    # Strip edition suffixes (repeat - some titles have stacked suffixes
    # like "Definitive Edition Remastered")
    changed = True
    while changed:
        changed = False
        for suf in _EDITION_SUFFIXES:
            if s.endswith(suf):
                s = s[:-len(suf)]
                changed = True
    return s


_PATTERNS: dict[str, list[str]] = {
    "cyberpunk":     ["cyberpunk2077", "cyberpunk"],
    "gtav":          ["grandtheftautov", "gtav", "gta5", "grandtheftauto5"],
    "rdr2":          ["reddeadredemption2", "rdr2"],
    "rdr1":          ["reddeadredemption"],   # plain RDR1
    "witcher3":      ["thewitcher3wildhunt", "thewitcher3", "witcher3"],
    "hogwarts":      ["hogwartslegacy"],
    "tsushima":      ["ghostoftsushima", "ghostoftsushimadirectorscut"],
    "spiderman":     ["marvelsspidermanremastered", "spidermanremastered", "spiderman"],
    "spidermanmm":   ["marvelsspidermanmilesmorales", "spidermanmilesmorales", "milesmorales"],
    "spiderman2":    ["marvelsspiderman2", "spiderman2"],
    "gow2018":       ["godofwar"],
    "gowragnarok":   ["godofwarragnarok", "godofwarragnarök"],
    "tlou1":         ["thelastofuspartione", "thelastofuspart1", "tlouparti"],
    "tlou2":         ["thelastofuspartii", "thelastofuspart2", "thelastofuspartiiremastered", "tloupartii", "tlou2"],
    "horizonzd":     ["horizonzerodawn", "horizonzerodawnremastered"],
    "horizonfw":     ["horizonforbiddenwest"],
    "watchdogs1":    ["watchdogs", "watch_dogs"],
    "watchdogs2":    ["watchdogs2", "watch_dogs_2"],
    "uncharted":     ["unchartedlegacyofthievescollection", "uncharted"],
    "ac1":           ["assassinscreed", "assassinscreeddirectorscut"],
    "ac2":           ["assassinscreedii", "assassinscreed2"],
    "acbrotherhood": ["assassinscreedbrotherhood"],
    "acrevelations": ["assassinscreedrevelations"],
    "ac3":           ["assassinscreediii", "assassinscreed3", "assassinscreed3remastered"],
    "acblackflag":   ["assassinscreedivblackflag", "assassinscreed4blackflag", "acblackflag"],
    "acrogue":       ["assassinscreedrogue"],
    "acunity":       ["assassinscreedunity"],
    "acsyndicate":   ["assassinscreedsyndicate"],
    "acorigins":     ["assassinscreedorigins"],
    "acodyssey":     ["assassinscreedodyssey"],
    "acvalhalla":    ["assassinscreedvalhalla"],
    "acmirage":      ["assassinscreedmirage"],
    # AC Shadows - id matches the website/Supabase games row ("ac-shadows",
    # with a hyphen) so detected_cached()["ac-shadows"] lines up with the
    # card the launcher fetches from the hub.
    "ac-shadows":    ["assassinscreedshadows"],
    "anno1800":      ["anno1800", "anno1800ubisoftconnect"],
    # id matches the future Supabase games row ("ratchet-rift-apart").
    "ratchet-rift-apart": ["ratchetclankriftapart", "ratchetandclankriftapart", "riftapart"],
    "plague-tale-innocence": ["aplaguetaleinnocence", "plaguetaleinnocence"],
    "plague-tale-requiem":   ["aplaguetalerequiem", "plaguetalerequiem"],
    "aot2":          ["attackontitan2", "aot2", "aot2finalbattle", "attackontitan2finalbattle"],
    # id matches the website/Supabase games row ("until-dawn", hyphenated).
    # 2024 remake ships under the "Until Dawn" folder; internal codename "Bates".
    "until-dawn":    ["untildawn", "untildawnremake", "bates"],
    "007-first-light": ["007firstlight", "007firstlightgame"],
    # id matches the website/Supabase games row ("farcry6"). Dunia engine (FAT2 v11).
    "farcry6":       ["farcry6", "far cry 6", "farcry 6"],
    # id matches the website/Supabase games row ("farcry5"). Dunia engine (FAT2 v10).
    "farcry5":       ["farcry5", "far cry 5", "farcry 5"],
    # Corsair Cove (Limbic Entertainment / Hooded Horse) - Unreal Engine 5, WinGDK
    # (Microsoft-Store/GDK build). Folder is "Corsair Cove"; project dir "CorsairCove".
    "corsair-cove":  ["corsaircove", "corsair cove"],
}


def match_to_catalog(name_or_folder: str) -> str | None:
    """Resolve a launcher display name or folder name to a catalog id.

    Exact-match only (after stripping common edition suffixes). Avoids
    false positives like "Assassin's Creed Shadows" → "Assassin's Creed".
    """
    # Try BOTH the suffix-STRIPPED form (so "Cyberpunk Ultimate Edition" → the
    # base entry) AND the raw-normalized form. The raw form is essential because
    # some catalog patterns literally CONTAIN an edition word ("hogwartslegacy",
    # "marvelsspidermanremastered", "unchartedlegacyofthievescollection"): for
    # those, stripping "legacy"/"remastered"/"collection" first would make the
    # pattern permanently unreachable and the installed game read as not-found.
    raw = re.sub(r"[^a-z0-9]+", "", name_or_folder.lower())
    # .copy() = a point-in-time snapshot, so a concurrent register_patterns()
    # (a catalog refresh can add a NEW key to _PATTERNS from another thread
    # while a scan is mid-loop here) can never raise "dictionary changed size
    # during iteration" - the same class of race already fixed in swr_cache.py.
    for target in (_norm(name_or_folder), raw):
        if not target:
            continue
        for cid, patterns in _PATTERNS.copy().items():
            if target in patterns:
                return cid
    return None


# ─────────────────────────────────────────────────────────────
# Executable-fingerprint matcher.
# Used by the deep scan when a folder name doesn't match a catalog
# pattern - we peek inside for a known main-binary filename so games
# installed under arbitrary folder names (repacks, manual installs,
# user-renamed dirs) still get detected.
# Filenames are matched case-insensitively.
# ─────────────────────────────────────────────────────────────
_EXE_PATTERNS: dict[str, list[str]] = {
    "cyberpunk":     ["Cyberpunk2077.exe"],
    "gtav":          ["GTA5.exe", "PlayGTAV.exe", "GTAVLauncher.exe", "GTA5_Enhanced.exe"],
    "rdr2":          ["RDR2.exe"],
    "rdr1":          ["RDR.exe", "RDR1.exe"],
    "witcher3":      ["witcher3.exe"],
    "hogwarts":      ["HogwartsLegacy.exe"],
    "tsushima":      ["GhostOfTsushima.exe"],
    "spiderman":     ["Spider-Man.exe", "MarvelsSpiderManRemastered.exe"],
    "spidermanmm":   ["MilesMorales.exe", "MarvelsSpiderManMilesMorales.exe"],
    "spiderman2":    ["MarvelsSpiderMan2.exe"],
    "gow2018":       ["GoW.exe"],
    "gowragnarok":   ["GoWR.exe"],
    "tlou1":         ["tlou-i.exe", "TheLastOfUsPartI.exe"],
    "tlou2":         ["tlou-ii.exe", "TheLastOfUsPartII.exe"],
    "horizonzd":     ["HorizonZeroDawn.exe", "HZD.exe"],
    "horizonfw":     ["HorizonForbiddenWest.exe"],
    "watchdogs1":    ["watch_dogs.exe"],
    "watchdogs2":    ["WatchDogs2.exe"],
    "uncharted":     ["u4.exe"],
    "ac1":           ["AssassinsCreed_Dx9.exe", "AssassinsCreed_Dx10.exe"],
    "ac2":           ["AssassinsCreedIIGame.exe"],
    "acbrotherhood": ["ACBSP.exe"],
    "acrevelations": ["ACR.exe", "ACR_SP.exe"],
    "ac3":           ["AC3SP.exe"],
    "acblackflag":   ["AC4BFSP.exe"],
    "acrogue":       ["ACRogueSP.exe", "ACRogue.exe"],
    "acunity":       ["ACU.exe"],
    "acsyndicate":   ["ACS.exe"],
    "acorigins":     ["ACOrigins.exe"],
    "acodyssey":     ["ACOdyssey.exe"],
    "acvalhalla":    ["ACValhalla.exe"],
    "acmirage":      ["ACMirage.exe"],
    "ac-shadows":    ["ACShadows.exe", "ACShadows_Plus.exe"],
    "anno1800":      ["Anno1800.exe"],
    "ratchet-rift-apart": ["RiftApart.exe"],
    "plague-tale-innocence": ["APlagueTale.exe", "APlagueTale_x64.exe"],
    "plague-tale-requiem":   ["APlagueTaleRequiem.exe", "APlagueTaleRequiem_x64.exe"],
    "aot2":          ["AOT2.exe", "AttackonTitan2.exe", "AOT2FB.exe"],
    # Until Dawn 2024 remake - internal codename "Bates". Root has a small
    # launcher stub Bates.exe; the shipping binary is Bates-Win64-Shipping.exe.
    "until-dawn":    ["Bates.exe", "Bates-Win64-Shipping.exe"],
    "007-first-light": ["007firstlight.exe", "007-first-light.exe", "007FirstLight.exe"],
    # Far Cry 6 - root launcher stub FarCry6.exe; the DX12/Vulkan game binaries
    # sit in bin/ (already in _EXE_SUBDIRS).
    "farcry6":       ["FarCry6.exe", "FC_m64d3d12.exe", "FC_m64.exe"],
    # Far Cry 5 - FarCry5.exe in bin/ is a 215 KB Steam stub that hands off and exits;
    # the engine lives in bin/FC_m64.dll, so match the stub (bin/ is in _EXE_SUBDIRS).
    "farcry5":       ["FarCry5.exe", "FarCry5_default.exe"],
    # Corsair Cove - the ROOT CorsairCove.exe is a 353 KB GDK launch stub; the
    # 174 MB shipping binary lives in CorsairCove/Binaries/WinGDK/ (in _EXE_SUBDIRS).
    "corsair-cove":  ["CorsairCove.exe"],
}

# Common sub-folders that hold the main binary in AAA titles.
_EXE_SUBDIRS = (
    "", "bin", "bin/x64", "x64", "Game", "Binaries", "Binaries/Win64",
    "RDR2", "GTA5", "Phoenix/Binaries/Win64",
    "Windows", "Windows/Bates/Binaries/Win64",
    "CorsairCove/Binaries/WinGDK",
)


def match_by_executable(folder: Path) -> str | None:
    """Inspect the folder + common bin/ sub-folders for a known main exe.
    Returns the matching catalog id, or None. Best-effort: silently
    swallows OSError on inaccessible folders / junctions.
    """
    try:
        for sub in _EXE_SUBDIRS:
            d = folder / sub if sub else folder
            try:
                names = {p.name.lower() for p in d.iterdir() if p.is_file()}
            except (OSError, PermissionError):
                continue
            # .copy() - same concurrent-register_patterns() race as match_to_catalog.
            for cid, exes in _EXE_PATTERNS.copy().items():
                for exe in exes:
                    if exe.lower() in names:
                        return cid
    except (OSError, PermissionError):
        pass
    return None


def find_exe(game_id: str, root) -> str | None:
    """Full path to `game_id`'s main EXE inside `root`, searching the known exe
    names across the common bin/ sub-folders. Used only to DISPLAY a full exe
    path in the UI (the appliers keep using the folder). None when the game has
    no known exe name or the exe isn't present (→ the UI shows the folder)."""
    if root is None:
        return None
    root = Path(root)
    # The game's own config already names its exe RELATIVE to the root when it has
    # a validation_file (Anno's is `Bin\Win64\Anno1800.exe`) - a fixed, verified
    # answer that beats guessing a name across a fixed list of bin/ sub-folders.
    try:
        from translation_manager.config import GAMES      # local: avoid a cycle
        for cfg in GAMES.values():
            if cfg.internal_id == game_id and cfg.validation_file.lower().endswith(".exe"):
                p = root / cfg.validation_file
                if p.is_file():
                    return str(p)
                break
    except Exception:                                     # pragma: no cover
        pass
    exes = _EXE_PATTERNS.get(game_id)
    if not exes:
        return None
    for sub in _EXE_SUBDIRS:
        d = root / sub if sub else root
        for name in exes:
            try:
                p = d / name
                if p.is_file():
                    return str(p)
            except OSError:
                continue
    return None


def _norm_name(s: str) -> str:
    return s.lower().replace(" ", "").replace("-", "").replace("_", "").replace("'", "")


def root_from_exe(game_id: str, exe_path, validation_rel: str | None = None) -> Path | None:
    """Given a full EXE path the user picked/typed, return the game ROOT folder
    the appliers expect (an exe at ``<root>\\bin\\x64\\game.exe`` → ``<root>``).

    Walks UP from the exe's own folder and returns the first ancestor that is
    authoritatively this game's root: a ``validation_rel`` file exists under it,
    OR its folder NAME matches this game's detect pattern. Folder-name is the
    discriminator (``match_by_executable`` can't tell ``<root>`` from
    ``<root>\\bin\\x64`` because both "contain" the exe). Falls back to the exe's
    own folder - the appliers all VALIDATE their target and return a clear error
    on a wrong root rather than corrupting anything, so this is safe."""
    try:
        exe = Path(exe_path)
    except Exception:
        return None
    if not exe.is_file():
        return None
    pats = [p for p in _PATTERNS.get(game_id, [])]
    cur = exe.parent
    for _ in range(6):                       # exe folder + up to 5 ancestors
        try:
            if validation_rel and (cur / validation_rel).is_file():
                return cur
        except OSError:
            pass
        nm = _norm_name(cur.name)
        if pats and any(_norm_name(p) in nm for p in pats):
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return exe.parent


# ─────────────────────────────────────────────────────────────
# Steam - registry + libraryfolders.vdf + appmanifest_*.acf
# ─────────────────────────────────────────────────────────────
def _steam_library_dirs() -> list[Path]:
    if winreg is None:
        return []
    paths: list[Path] = []
    for hive, sub in [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam"),
        (winreg.HKEY_CURRENT_USER,  r"SOFTWARE\Valve\Steam"),
    ]:
        try:
            with winreg.OpenKey(hive, sub) as k:
                install = winreg.QueryValueEx(k, "InstallPath")[0]
            main = Path(install) / "steamapps"
            if main.exists():
                paths.append(main)
                # Parse libraryfolders.vdf for any extra libraries
                vdf = main / "libraryfolders.vdf"
                if vdf.exists():
                    text = vdf.read_text(encoding="utf-8", errors="ignore")
                    for m in re.finditer(r'"path"\s*"([^"]+)"', text):
                        extra = Path(m.group(1).replace("\\\\", "\\")) / "steamapps"
                        if extra.exists() and extra not in paths:
                            paths.append(extra)
            break
        except OSError:
            continue
    return paths


def detect_steam() -> dict[str, Path]:
    found: dict[str, Path] = {}
    for lib in _steam_library_dirs():
        for acf in lib.glob("appmanifest_*.acf"):
            try:
                text = acf.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            name_m = re.search(r'"name"\s*"([^"]+)"', text)
            dir_m  = re.search(r'"installdir"\s*"([^"]+)"', text)
            if not (name_m and dir_m):
                continue
            install_path = lib / "common" / dir_m.group(1)
            if not install_path.exists():
                continue
            cid = match_to_catalog(name_m.group(1)) or match_to_catalog(dir_m.group(1))
            if cid and cid not in found:
                found[cid] = install_path
    return found


# ─────────────────────────────────────────────────────────────
# Ubisoft Connect - InstallDir under HKLM\Ubisoft\Launcher\Installs\<id>
# ─────────────────────────────────────────────────────────────
def detect_ubisoft() -> dict[str, Path]:
    if winreg is None:
        return {}
    found: dict[str, Path] = {}
    for hive, sub in [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Ubisoft\Launcher\Installs"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Ubisoft\Launcher\Installs"),
    ]:
        try:
            with winreg.OpenKey(hive, sub) as k:
                n_keys = winreg.QueryInfoKey(k)[0]
                for i in range(n_keys):
                    game_id = winreg.EnumKey(k, i)
                    try:
                        with winreg.OpenKey(k, game_id) as gk:
                            install_dir = winreg.QueryValueEx(gk, "InstallDir")[0]
                    except OSError:
                        continue
                    path = Path(install_dir.rstrip("\\/"))
                    if not path.exists():
                        continue
                    # Ubisoft doesn't put display name in the registry - use folder name
                    cid = match_to_catalog(path.name)
                    if cid and cid not in found:
                        found[cid] = path
            break
        except OSError:
            continue
    return found


# ─────────────────────────────────────────────────────────────
# Epic Games - Manifests/*.item JSON files
# ─────────────────────────────────────────────────────────────
def detect_epic() -> dict[str, Path]:
    candidates = [
        Path(os.environ.get("ProgramData", r"C:\ProgramData")) /
            "Epic" / "EpicGamesLauncher" / "Data" / "Manifests",
    ]
    found: dict[str, Path] = {}
    for d in candidates:
        if not d.exists():
            continue
        for item in d.glob("*.item"):
            try:
                data = json.loads(item.read_text(encoding="utf-8", errors="ignore"))
            except (OSError, json.JSONDecodeError):
                continue
            name = data.get("DisplayName") or data.get("MandatoryAppFolderName")
            install = data.get("InstallLocation")
            if not (name and install):
                continue
            path = Path(install)
            if not path.exists():
                continue
            cid = match_to_catalog(name) or match_to_catalog(path.name)
            if cid and cid not in found:
                found[cid] = path
    return found


# ─────────────────────────────────────────────────────────────
# GOG Galaxy - HKLM\GOG.com\Games\<gameId>
# ─────────────────────────────────────────────────────────────
def detect_gog() -> dict[str, Path]:
    if winreg is None:
        return {}
    found: dict[str, Path] = {}
    for hive, sub in [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\GOG.com\Games"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\GOG.com\Games"),
    ]:
        try:
            with winreg.OpenKey(hive, sub) as k:
                n = winreg.QueryInfoKey(k)[0]
                for i in range(n):
                    gid = winreg.EnumKey(k, i)
                    try:
                        with winreg.OpenKey(k, gid) as gk:
                            try:
                                path_str = winreg.QueryValueEx(gk, "path")[0]
                            except OSError:
                                path_str = winreg.QueryValueEx(gk, "PATH")[0]
                            try:
                                name = winreg.QueryValueEx(gk, "gameName")[0]
                            except OSError:
                                name = ""
                    except OSError:
                        continue
                    path = Path(path_str.rstrip("\\/"))
                    if not path.exists():
                        continue
                    cid = match_to_catalog(name) or match_to_catalog(path.name)
                    if cid and cid not in found:
                        found[cid] = path
            break
        except OSError:
            continue
    return found


# ─────────────────────────────────────────────────────────────
# Rockstar Launcher - appmanifest-like .rgs file inside each game dir.
# Easiest path is the registry key holding the launcher install root.
# ─────────────────────────────────────────────────────────────
def detect_rockstar() -> dict[str, Path]:
    if winreg is None:
        return {}
    found: dict[str, Path] = {}
    candidates = [
        r"SOFTWARE\WOW6432Node\Rockstar Games\Grand Theft Auto V",
        r"SOFTWARE\Rockstar Games\Grand Theft Auto V",
        r"SOFTWARE\WOW6432Node\Rockstar Games\Red Dead Redemption 2",
        r"SOFTWARE\Rockstar Games\Red Dead Redemption 2",
        r"SOFTWARE\WOW6432Node\Rockstar Games\Red Dead Redemption",
        r"SOFTWARE\Rockstar Games\Red Dead Redemption",
    ]
    name_to_cid = {
        "Grand Theft Auto V":      "gtav",
        "Red Dead Redemption 2":   "rdr2",
        "Red Dead Redemption":     "rdr1",
    }
    for sub in candidates:
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, sub) as k:
                try:
                    install = winreg.QueryValueEx(k, "InstallFolder")[0]
                except OSError:
                    install = winreg.QueryValueEx(k, "InstallFolderRetail")[0]
                game_name = sub.split("\\")[-1]
                cid = name_to_cid.get(game_name)
                p = Path(install)
                if cid and p.exists() and cid not in found:
                    found[cid] = p
        except OSError:
            continue
    return found


# ─────────────────────────────────────────────────────────────
# Xbox / Microsoft Store / PC Game Pass
# ─────────────────────────────────────────────────────────────
# Xbox app installs land in `<Drive>:\XboxGames\<DisplayName>\Content\`
# (default `C:\XboxGames`, but the user can pick any fixed drive).
# Some older PC Game Pass titles use `Program Files\ModifiableWindowsApps`
# with junctions into the real WindowsApps store.
# Folder name matches the in-store display name - works directly with
# `match_to_catalog`. We fall back to executable-fingerprint matching
# so titles like "Forza" with quirky folder names still resolve when
# they're in the catalog.
def detect_xbox() -> dict[str, Path]:
    found: dict[str, Path] = {}
    roots: list[Path] = []
    for drive in _list_fixed_drives():
        for sub in (
            "XboxGames",
            "Program Files\\ModifiableWindowsApps",
            "Program Files (x86)\\ModifiableWindowsApps",
        ):
            candidate = drive / sub
            if candidate.exists():
                roots.append(candidate)

    for root in roots:
        try:
            for title_dir in root.iterdir():
                if not title_dir.is_dir():
                    continue
                # Real install lives under `Content/` for Xbox app; the EA-
                # bundled Game Pass titles drop the game directly in the dir.
                content = title_dir / "Content"
                install = content if content.exists() else title_dir
                cid = match_to_catalog(title_dir.name) or match_by_executable(install)
                if cid and cid not in found:
                    found[cid] = install
        except (OSError, PermissionError):
            continue
    return found


# ─────────────────────────────────────────────────────────────
# EA App (modern) + Origin (legacy)
# ─────────────────────────────────────────────────────────────
def detect_ea() -> dict[str, Path]:
    if winreg is None:
        return {}
    found: dict[str, Path] = {}
    # EA App and Origin both expose per-title sub-keys whose values carry
    # `InstallLocation` (or legacy `Install Dir`) + `DisplayName`. We try
    # every plausible hive - modern EA Desktop first, legacy Origin last.
    candidates = [
        r"SOFTWARE\WOW6432Node\Electronic Arts\EA Desktop",
        r"SOFTWARE\Electronic Arts\EA Desktop",
        r"SOFTWARE\WOW6432Node\Origin Games",
        r"SOFTWARE\Origin Games",
        r"SOFTWARE\WOW6432Node\Origin",
        r"SOFTWARE\Origin",
    ]
    for sub in candidates:
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, sub) as k:
                n = winreg.QueryInfoKey(k)[0]
                for i in range(n):
                    gid = winreg.EnumKey(k, i)
                    try:
                        with winreg.OpenKey(k, gid) as gk:
                            install: str | None = None
                            for vn in ("InstallLocation", "InstallDir", "Install Dir"):
                                try:
                                    install = winreg.QueryValueEx(gk, vn)[0]
                                    break
                                except OSError:
                                    continue
                            if not install:
                                continue
                            try:
                                name = winreg.QueryValueEx(gk, "DisplayName")[0]
                            except OSError:
                                name = ""
                            p = Path(install.rstrip("\\/"))
                            if not p.exists():
                                continue
                            cid = (match_to_catalog(name)
                                   or match_to_catalog(p.name)
                                   or match_by_executable(p))
                            if cid and cid not in found:
                                found[cid] = p
                    except OSError:
                        continue
        except OSError:
            continue
    return found


# ─────────────────────────────────────────────────────────────
# Amazon Games - SQLite catalog at
#   %LOCALAPPDATA%\Amazon Games\Data\Games\Sql\GameInstallInfo.sqlite
# ─────────────────────────────────────────────────────────────
def detect_amazon() -> dict[str, Path]:
    appdata = os.environ.get("LOCALAPPDATA")
    if not appdata:
        return {}
    db = (Path(appdata) / "Amazon Games" / "Data" / "Games" / "Sql"
          / "GameInstallInfo.sqlite")
    if not db.exists():
        return {}
    found: dict[str, Path] = {}
    try:
        # Read-only URI form so we never lock the file while the launcher
        # is also running.
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            rows = con.execute(
                "SELECT InstallDirectory, ProductTitle FROM DbSet"
            ).fetchall()
        except sqlite3.OperationalError:
            rows = con.execute(
                "SELECT InstallDirectory, ProductTitle FROM Catalog"
            ).fetchall()
        con.close()
        for install, name in rows:
            if not install:
                continue
            p = Path(install)
            if not p.exists():
                continue
            cid = (match_to_catalog(name or "")
                   or match_to_catalog(p.name)
                   or match_by_executable(p))
            if cid and cid not in found:
                found[cid] = p
    except (sqlite3.DatabaseError, OSError):
        pass
    return found


# ─────────────────────────────────────────────────────────────
# Quick scan - all launcher detectors combined
# ─────────────────────────────────────────────────────────────
def detect_common_paths() -> dict[str, Path]:
    """Known fixed install locations from the game configs.

    No launcher registry knows a DRM-free / repack install (Corsair Cove lives at
    `E:\\Games\\Corsair Cove`, God of War at a hand-picked folder), so without this
    such a game only appears after the minutes-long deep drive scan. Checking each
    config's `common_paths` is a handful of `is_dir()` calls - microseconds - and
    every hit is confirmed by the config's own `validation_file`, so a leftover or
    empty folder is never accepted."""
    out: dict[str, Path] = {}
    try:
        from translation_manager.config import GAMES      # local: avoid a cycle
    except Exception:                                     # pragma: no cover
        return out
    for cfg in GAMES.values():
        if not cfg.internal_id or not cfg.common_paths:
            continue
        for raw in cfg.common_paths:
            try:
                p = Path(raw)
                if p.is_dir() and cfg.is_valid_dir(p):
                    out.setdefault(cfg.internal_id, p)
                    break
            except OSError:
                continue
    return out


def detect_via_launchers() -> dict[str, Path]:
    out: dict[str, Path] = {}
    for fn in (
        detect_steam,
        detect_ubisoft,
        detect_epic,
        detect_gog,
        detect_rockstar,
        detect_xbox,
        detect_ea,
        detect_amazon,
        # LAST: a launcher registry is authoritative, so a real store path always
        # wins over a fixed guess (setdefault keeps the first hit).
        detect_common_paths,
    ):
        try:
            for cid, path in fn().items():
                out.setdefault(cid, path)
        except Exception:
            # never fail the whole scan because of one bad launcher
            continue
    return out


# ─────────────────────────────────────────────────────────────
# Deep drive scan - walks common install roots on each drive
# (NOT a full filesystem scan - that would take minutes/hours)
# ─────────────────────────────────────────────────────────────
def _list_fixed_drives() -> list[Path]:
    if sys.platform != "win32":
        return []
    drives = []
    for letter in string.ascii_uppercase:
        p = Path(f"{letter}:\\")
        if p.exists():
            try:
                # Skip optical / network drives - too slow
                next(p.iterdir(), None)
                drives.append(p)
            except (OSError, PermissionError):
                continue
    return drives


# Folder-name → catalog-id lookup. Walks each candidate root up to 2
# directories deep so a game at `D:\Games\<Vendor>\<Title>` is matched
# on the inner `<Title>` segment, not just the outer `<Vendor>`. When a
# folder name doesn't match any catalog pattern we fall back to peeking
# at .exe filenames inside - that's how we catch repacks, manually-
# installed games, and any other "outside-any-launcher" install where
# the user has renamed the folder.
_COMMON_ROOTS = [
    # Launcher defaults
    "Program Files", "Program Files (x86)",
    "SteamLibrary", "GOG Games", "Epic Games",
    "Ubisoft", "Ubisoft Game Launcher",
    "Rockstar Games", "Origin Games", "EA Games", "EA",
    "XboxGames",
    "Amazon Games", "Bethesda.net Launcher", "Battle.net",
    # Generic user-picked roots
    "Games", "My Games", "MyGames", "PC Games", "PCGames",
    "GamesRepacks", "Repacks", "FitGirl Repacks", "DODI Repacks",
    "ModifiableWindowsApps",
]
# Sub-paths that may sit *inside* a candidate root and hold the real games.
_NESTED_SUBS = ["steamapps/common"]

# The roots that actually hold games on a real PC, in descending order of how
# likely they are - this is what lets the scan find everything FAST and stop,
# instead of grinding every folder on every disk. "Hot" roots are checked on
# EVERY drive before we fall back to the colder ones.
_HOT_ROOTS = [
    "SteamLibrary/steamapps/common",
    "Program Files (x86)/Steam/steamapps/common",
    "Program Files/Steam/steamapps/common",
    "Steam/steamapps/common",
    "steamapps/common",
    "Games",
    "Epic Games",
    "GOG Games",
    "XboxGames",
]


# ─────────────────────────────────────────────────────────────
# FUTURE-PROOFING: detection patterns can arrive from the SERVER.
#
# A brand-new game added to the catalog on the website becomes detectable on
# every installed launcher IMMEDIATELY - no app update, no rebuild. The catalog
# row just carries `detectFolders` (folder-name patterns) and/or `detectExes`
# (main-binary filenames); we merge them into the tables at runtime, additively,
# never overwriting a built-in.
# ─────────────────────────────────────────────────────────────
def register_patterns(rows: list[dict]) -> int:
    """Merge server-supplied detection hints from catalog rows. Returns the
    number of ids that gained a new pattern. Never raises."""
    added = 0
    try:
        for row in rows or []:
            cid = row.get("id")
            if not isinstance(cid, str) or not cid:
                continue

            folders = row.get("detectFolders") or []
            if isinstance(folders, str):
                folders = [folders]
            norm = [_norm(f) for f in folders if isinstance(f, str) and f.strip()]
            norm = [n for n in norm if n]
            if norm:
                have = _PATTERNS.setdefault(cid, [])
                new = [n for n in norm if n not in have]
                if new:
                    have.extend(new)
                    added += 1

            exes = row.get("detectExes") or []
            if isinstance(exes, str):
                exes = [exes]
            exes = [e.strip() for e in exes
                    if isinstance(e, str) and e.strip().lower().endswith(".exe")]
            if exes:
                have_e = _EXE_PATTERNS.setdefault(cid, [])
                new_e = [e for e in exes if e.lower() not in
                         {x.lower() for x in have_e}]
                if new_e:
                    have_e.extend(new_e)
                    added += 1
    except Exception:                                    # pragma: no cover
        return added
    return added


def _resolve_match(child: Path) -> str | None:
    """Try folder name first (fast); if that fails, sniff executables.
    Returns the catalog id or None."""
    cid = match_to_catalog(child.name)
    if cid:
        return cid
    return match_by_executable(child)


def _system_drive() -> Path:
    """The drive Windows itself is on - where most games land by default."""
    try:
        sd = os.environ.get("SystemDrive") or "C:"
        return Path(sd.rstrip("\\/") + "\\")
    except Exception:                                    # pragma: no cover
        return Path("C:\\")


def _scan_tiers(drives: list[Path]) -> list[tuple[str, list[Path]]]:
    """The candidate roots, grouped into tiers, MOST-LIKELY FIRST.

    This is the whole point of the cascade: on a normal PC every game is found
    in tier 1-2 in well under a second, and we never even look at the cold,
    expensive tiers. We only descend when something is still missing.
    """
    sysd = _system_drive()
    others = [d for d in drives if str(d).upper() != str(sysd).upper()]

    def hot(ds: list[Path]) -> list[Path]:
        return [d / r for d in ds for r in _HOT_ROOTS]

    def common(ds: list[Path]) -> list[Path]:
        out: list[Path] = []
        for d in ds:
            for r in _COMMON_ROOTS:
                out.append(d / r)
                for nr in _NESTED_SUBS:
                    out.append(d / r / nr)
        return out

    return [
        # 1. The single most common place: the system drive's game libraries.
        ("המקומות הנפוצים", hot([sysd])),
        # 2. Secondary drives' game libraries - where enthusiasts put games.
        ("כוננים נוספים",   hot(others)),
        # 3. The wider set of known install roots, system drive first.
        ("תיקיות התקנה",    common([sysd])),
        ("תיקיות התקנה נוספות", common(others)),
        # 4. Last resort: the top level of every drive (D:\<Game>, etc.).
        ("סריקה רחבה",      list(drives)),
    ]


def deep_scan_drives(progress_cb: Callable[[str], None] | None = None,
                     want: set[str] | None = None) -> dict[str, Path]:
    """Cascading, popularity-ordered drive scan.

    Instead of grinding every folder on every disk, we walk a ranked list of
    candidate roots - the places games ACTUALLY live, most likely first - and
    stop the moment there is nothing left to find (`want` empty). On a typical PC
    everything resolves in the first tier or two; the expensive wide scan only
    ever runs for the machines that genuinely need it.

    want - the catalog ids we're still missing (from the launcher scan). When
           supplied, the scan EXITS EARLY as soon as they're all found. Pass None
           to scan for everything.
    """
    found: dict[str, Path] = {}
    # `want is None` = scan for everything. An EMPTY set means "nothing left to
    # find" and must exit instantly - `if want` would treat it as falsy and walk
    # every disk, which is the exact opposite of what the caller asked for.
    remaining = set(want) if want is not None else None
    seen: set[str] = set()          # roots already walked (tiers overlap)

    def _record(child: Path) -> None:
        try:
            cid = _resolve_match(child)
        except (OSError, PermissionError):
            return
        if not cid or cid in found:
            return
        # Confirm we can actually read it (drops junctions / broken symlinks)
        try:
            next(child.iterdir(), None)
        except (OSError, PermissionError):
            return
        found[cid] = child
        if remaining is not None:
            remaining.discard(cid)

    def _done() -> bool:
        return remaining is not None and not remaining

    def _walk(root: Path) -> None:
        key = str(root).lower()
        if key in seen:
            return
        seen.add(key)
        if not root.exists():
            return
        try:
            level1 = list(root.iterdir())
        except (OSError, PermissionError):
            return
        for child in level1:
            if _done():
                return
            try:
                if not child.is_dir():
                    continue
            except OSError:
                continue
            _record(child)
            # Depth-2 so `Games/<Vendor>/<Title>` matches on the inner title.
            # Skipped when level-1 already matched (don't pay for it twice).
            if child in found.values():
                continue
            try:
                for grand in child.iterdir():
                    if _done():
                        return
                    if grand.is_dir():
                        _record(grand)
            except (OSError, PermissionError):
                continue

    drives = _list_fixed_drives()

    # Be a good neighbour: the launcher is very often scanning WHILE a game is
    # running. When the machine is loaded we breathe between roots so the scan
    # never steals frames. Costs a few ms on an idle machine, nothing on a busy
    # one (where the user would rather wait than stutter).
    try:
        from . import perf_manager
    except Exception:                                    # pragma: no cover
        perf_manager = None                              # type: ignore[assignment]

    for label, roots in _scan_tiers(drives):
        if _done():
            break
        if progress_cb:
            progress_cb(f"סורק - {label}")
        for root in roots:
            if _done():
                break
            _walk(root)
            if perf_manager is not None:
                try:
                    if perf_manager.should_defer_heavy():
                        time.sleep(0.02)                 # yield to the game
                except Exception:                        # pragma: no cover
                    pass

    if progress_cb:
        progress_cb(f"נמצאו {len(found)} משחקים")
    return found


# ─────────────────────────────────────────────────────────────
# Module-level cache (so other views can read installs without re-scanning).
# Seeded at import-time from `~/.translation_manager/detected_games.json` so
# the launcher boots with the previous session's findings already populated.
# ─────────────────────────────────────────────────────────────
_cache: dict[str, Path] = _load_persisted()


def cached() -> dict[str, Path]:
    return dict(_cache)


def refresh_quick() -> dict[str, Path]:
    _cache.clear()
    _cache.update(detect_via_launchers())
    _save_persisted(_cache)
    return cached()


def known_ids() -> set[str]:
    """Every catalog id we know how to detect (built-in + server-registered)."""
    return set(_PATTERNS) | set(_EXE_PATTERNS)


def refresh_deep(progress_cb: Callable[[str], None] | None = None
                 ) -> dict[str, Path]:
    """Launcher registries first (instant, covers most machines), then the
    cascading drive scan for whatever is STILL missing - which lets the scan
    stop as soon as everything is accounted for instead of always walking every
    tier on every disk."""
    # 1) The cheap, authoritative sources: the game launchers themselves.
    _cache.update(detect_via_launchers())

    # 2) Only hunt for what the launchers did NOT already give us. On a typical
    #    machine that list is short (or empty), so the deep scan exits in the
    #    first tier instead of grinding through every drive.
    missing = known_ids() - set(_cache)
    if missing:
        deep = deep_scan_drives(progress_cb, want=missing)
        for cid, path in deep.items():
            _cache.setdefault(cid, path)
    elif progress_cb:
        progress_cb(f"נמצאו {len(_cache)} משחקים")

    _save_persisted(_cache)
    return cached()
