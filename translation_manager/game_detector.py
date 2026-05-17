"""
Game-installation detector — finds installed games across every major PC
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
from pathlib import Path
from typing import Callable

# winreg only exists on Windows. Wrap so the module still imports on Linux/Mac.
try:
    import winreg
except ImportError:
    winreg = None


# ─────────────────────────────────────────────────────────────
# Persistence — survive app restarts
# ─────────────────────────────────────────────────────────────
# Detected games are mirrored to disk after every scan so the next launch
# starts with the previous results already populated. We re-validate each
# path on load (drops entries whose folder was deleted in the meantime).
_STORE_FILE = Path.home() / ".translation_manager" / "detected_games.json"


def _load_persisted() -> dict[str, Path]:
    if not _STORE_FILE.exists():
        return {}
    try:
        data = json.loads(_STORE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    out: dict[str, Path] = {}
    for cid, raw in data.items():
        p = Path(raw)
        if p.exists():
            out[cid] = p
    return out


def _save_persisted(payload: dict[str, Path]) -> None:
    try:
        _STORE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _STORE_FILE.write_text(
            json.dumps({k: str(v) for k, v in payload.items()},
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass


# ─────────────────────────────────────────────────────────────
# Catalog-ID matching — every detected display name / folder name
# gets normalized and matched against these patterns. First match wins.
# ─────────────────────────────────────────────────────────────
# Edition suffixes commonly appended by launchers — strip them before matching
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
    # Strip edition suffixes (repeat — some titles have stacked suffixes
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
    "anno1800":      ["anno1800", "anno1800ubisoftconnect"],
}


def match_to_catalog(name_or_folder: str) -> str | None:
    """Resolve a launcher display name or folder name to a catalog id.

    Exact-match only (after stripping common edition suffixes). Avoids
    false positives like "Assassin's Creed Shadows" → "Assassin's Creed".
    """
    target = _norm(name_or_folder)
    if not target:
        return None
    for cid, patterns in _PATTERNS.items():
        if target in patterns:
            return cid
    return None


# ─────────────────────────────────────────────────────────────
# Executable-fingerprint matcher.
# Used by the deep scan when a folder name doesn't match a catalog
# pattern — we peek inside for a known main-binary filename so games
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
    "anno1800":      ["Anno1800.exe"],
}

# Common sub-folders that hold the main binary in AAA titles.
_EXE_SUBDIRS = (
    "", "bin", "bin/x64", "x64", "Game", "Binaries", "Binaries/Win64",
    "RDR2", "GTA5", "Phoenix/Binaries/Win64",
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
            for cid, exes in _EXE_PATTERNS.items():
                for exe in exes:
                    if exe.lower() in names:
                        return cid
    except (OSError, PermissionError):
        pass
    return None


# ─────────────────────────────────────────────────────────────
# Steam — registry + libraryfolders.vdf + appmanifest_*.acf
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
# Ubisoft Connect — InstallDir under HKLM\Ubisoft\Launcher\Installs\<id>
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
                    # Ubisoft doesn't put display name in the registry — use folder name
                    cid = match_to_catalog(path.name)
                    if cid and cid not in found:
                        found[cid] = path
            break
        except OSError:
            continue
    return found


# ─────────────────────────────────────────────────────────────
# Epic Games — Manifests/*.item JSON files
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
# GOG Galaxy — HKLM\GOG.com\Games\<gameId>
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
# Rockstar Launcher — appmanifest-like .rgs file inside each game dir.
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
# Folder name matches the in-store display name — works directly with
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
    # every plausible hive — modern EA Desktop first, legacy Origin last.
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
# Amazon Games — SQLite catalog at
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
# Quick scan — all launcher detectors combined
# ─────────────────────────────────────────────────────────────
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
    ):
        try:
            for cid, path in fn().items():
                out.setdefault(cid, path)
        except Exception:
            # never fail the whole scan because of one bad launcher
            continue
    return out


# ─────────────────────────────────────────────────────────────
# Deep drive scan — walks common install roots on each drive
# (NOT a full filesystem scan — that would take minutes/hours)
# ─────────────────────────────────────────────────────────────
def _list_fixed_drives() -> list[Path]:
    if sys.platform != "win32":
        return []
    drives = []
    for letter in string.ascii_uppercase:
        p = Path(f"{letter}:\\")
        if p.exists():
            try:
                # Skip optical / network drives — too slow
                next(p.iterdir(), None)
                drives.append(p)
            except (OSError, PermissionError):
                continue
    return drives


# Folder-name → catalog-id lookup. Walks each candidate root up to 2
# directories deep so a game at `D:\Games\<Vendor>\<Title>` is matched
# on the inner `<Title>` segment, not just the outer `<Vendor>`. When a
# folder name doesn't match any catalog pattern we fall back to peeking
# at .exe filenames inside — that's how we catch repacks, manually-
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


def _resolve_match(child: Path) -> str | None:
    """Try folder name first (fast); if that fails, sniff executables.
    Returns the catalog id or None."""
    cid = match_to_catalog(child.name)
    if cid:
        return cid
    return match_by_executable(child)


def deep_scan_drives(progress_cb: Callable[[str], None] | None = None
                     ) -> dict[str, Path]:
    found: dict[str, Path] = {}

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
            found[cid] = child
        except (OSError, PermissionError):
            pass

    for drive in _list_fixed_drives():
        if progress_cb:
            progress_cb(f"סורק {drive.drive}")

        # Build the full candidate list for this drive:
        candidates: list[Path] = [drive] + [drive / r for r in _COMMON_ROOTS]
        for c in list(candidates):
            for nr in _NESTED_SUBS:
                candidates.append(c / nr)

        for root in candidates:
            if not root.exists():
                continue
            try:
                level1 = list(root.iterdir())
            except (OSError, PermissionError):
                continue
            for child in level1:
                if not child.is_dir():
                    continue
                _record(child)
                # Depth-2: walk one more level so games installed under
                # vendor folders (`Games/CDPR/Cyberpunk 2077`, etc.) are
                # also matched. Skipped if level-1 already matched, so
                # we don't pay the cost twice.
                if any(found.get(k) == child for k in found):
                    continue
                try:
                    for grand in child.iterdir():
                        if grand.is_dir():
                            _record(grand)
                except (OSError, PermissionError):
                    continue

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


def refresh_deep(progress_cb: Callable[[str], None] | None = None
                 ) -> dict[str, Path]:
    # Quick scan first to get a baseline
    _cache.update(detect_via_launchers())
    # Then merge deep-scan results (without overwriting good launcher data)
    deep = deep_scan_drives(progress_cb)
    for cid, path in deep.items():
        _cache.setdefault(cid, path)
    _save_persisted(_cache)
    return cached()
