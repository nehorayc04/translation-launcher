"""MSMR activation-lever probe — READ ONLY.

Answers: where does Marvel's Spider-Man Remastered persist the TEXT language,
is it flippable by the launcher, and are text/voice independent?

NOTHING is written to the game folder or to the user's settings. Every access
below is a read.

⚠️ %USERPROFILE% / %APPDATA% / %LOCALAPPDATA% are REDIRECTED in this sandbox
(Antigravity profile). The REAL profile is resolved via SHGetKnownFolderPath
(FOLDERID_Profile) — the documented CLAUDE.md trap.
"""
from __future__ import annotations

import ctypes
import json
import os
import re
import sys
from ctypes import wintypes
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GAME = Path(r"D:\Games\Spider-man Remastered")


# ────────────────────────────────────────────────────────────
# 1. Known folders (the ONLY trustworthy paths in this sandbox)
# ────────────────────────────────────────────────────────────
class GUID(ctypes.Structure):
    _fields_ = [("a", wintypes.DWORD), ("b", wintypes.WORD),
                ("c", wintypes.WORD), ("d", ctypes.c_ubyte * 8)]


def known(a, b, c, d):
    fid = GUID(a, b, c, (ctypes.c_ubyte * 8)(*d))
    out = ctypes.c_wchar_p()
    if ctypes.windll.shell32.SHGetKnownFolderPath(
            ctypes.byref(fid), 0, None, ctypes.byref(out)) != 0:
        return None
    try:
        return out.value
    finally:
        ctypes.windll.ole32.CoTaskMemFree(out)


KF = {
    "Profile":        known(0x5E6C858F, 0x0E22, 0x4760, (0x9A, 0xFE, 0xEA, 0x33, 0x17, 0xB6, 0x71, 0x73)),
    "Documents":      known(0xFDD39AD0, 0x238F, 0x46AF, (0xAD, 0xB4, 0x6C, 0x85, 0x48, 0x03, 0x69, 0xC7)),
    "LocalAppData":   known(0xF1B32785, 0x6FBA, 0x4FCF, (0x9D, 0x55, 0x7B, 0x8E, 0x7F, 0x15, 0x70, 0x91)),
    "RoamingAppData": known(0x3EB685DB, 0x65F9, 0x4CF6, (0xA0, 0x3A, 0xE3, 0xEF, 0x65, 0x72, 0x9F, 0x3D)),
    "SavedGames":     known(0x4C5C32FF, 0xBB9D, 0x43B0, (0xB5, 0xB4, 0x2D, 0x72, 0xE5, 0x4E, 0xAA, 0xA4)),
    "PublicDocuments": known(0xED4824AF, 0xDCE4, 0x45A8, (0x81, 0xE2, 0xFC, 0x79, 0x65, 0x08, 0x36, 0x34)),
}

print("=" * 78)
print("1. KNOWN FOLDERS (real)  vs  ENV (redirected in this sandbox)")
print("=" * 78)
for k, v in KF.items():
    print(f"  KF {k:<16} = {v}")
print("  ---- env ----")
for k in ("USERPROFILE", "APPDATA", "LOCALAPPDATA", "HOMEDRIVE", "HOMEPATH"):
    print(f"  $env:{k:<14} = {os.environ.get(k)}")
print(f"  Path.home()          = {Path.home()}")

PROFILE = Path(KF["Profile"]) if KF["Profile"] else Path.home()
DOCS    = Path(KF["Documents"]) if KF["Documents"] else PROFILE / "Documents"
LAD     = Path(KF["LocalAppData"]) if KF["LocalAppData"] else PROFILE / "AppData/Local"
RAD     = Path(KF["RoamingAppData"]) if KF["RoamingAppData"] else PROFILE / "AppData/Roaming"
SAVED   = Path(KF["SavedGames"]) if KF["SavedGames"] else PROFILE / "Saved Games"


# ────────────────────────────────────────────────────────────
# 2. Hunt the settings folder
# ────────────────────────────────────────────────────────────
def hunt(base: Path, label: str, pat: re.Pattern, depth: int = 2):
    """List direct children of `base` whose name matches `pat` (case-insens)."""
    print(f"\n  [{label}] {base}   exists={base.is_dir()}")
    if not base.is_dir():
        return []
    hits = []
    try:
        for child in sorted(base.iterdir()):
            if pat.search(child.name):
                hits.append(child)
                print(f"      MATCH  {'<DIR>' if child.is_dir() else f'{child.stat().st_size:>10}'}  {child.name}")
    except OSError as e:
        print(f"      (cannot list: {e})")
    if not hits:
        print("      (no name match at this level)")
    return hits


SPIDEY = re.compile(r"spider|insomniac|nixxes|marvel", re.I)

print()
print("=" * 78)
print("2. SETTINGS-FOLDER HUNT  (Documents / LocalAppData / Roaming / SavedGames)")
print("=" * 78)
roots = [(DOCS, "Documents"), (LAD, "LocalAppData"), (RAD, "RoamingAppData"),
         (SAVED, "SavedGames"), (PROFILE, "Profile")]
found_dirs = []
for base, label in roots:
    found_dirs += hunt(base, label, SPIDEY)


def tree(root: Path, label: str, max_files: int = 400):
    print(f"\n  ---- TREE of {label}: {root}")
    n = 0
    try:
        for p in sorted(root.rglob("*")):
            rel = p.relative_to(root)
            if p.is_dir():
                print(f"      <DIR>            {rel}")
            else:
                try:
                    st = p.stat()
                    print(f"      {st.st_size:>12}  {rel}")
                except OSError:
                    print(f"      {'?':>12}  {rel}")
                n += 1
                if n >= max_files:
                    print("      ... (truncated)")
                    return
    except OSError as e:
        print(f"      (cannot walk: {e})")


for d in found_dirs:
    if d.is_dir():
        tree(d, d.name)


# ────────────────────────────────────────────────────────────
# 3. Registry
# ────────────────────────────────────────────────────────────
print()
print("=" * 78)
print("3. REGISTRY  (HKCU + HKLM, read-only)")
print("=" * 78)
try:
    import winreg
except ImportError:
    winreg = None
    print("  winreg unavailable")

TYPE_NAME = {
    winreg.REG_SZ: "REG_SZ", winreg.REG_EXPAND_SZ: "REG_EXPAND_SZ",
    winreg.REG_DWORD: "REG_DWORD", winreg.REG_QWORD: "REG_QWORD",
    winreg.REG_BINARY: "REG_BINARY", winreg.REG_MULTI_SZ: "REG_MULTI_SZ",
} if winreg else {}


def dump_key(hive, hname, sub, depth=0, maxdepth=3):
    pad = "    " * (depth + 1)
    try:
        k = winreg.OpenKey(hive, sub, 0, winreg.KEY_READ)
    except FileNotFoundError:
        if depth == 0:
            print(f"  {hname}\\{sub}  -> NOT PRESENT")
        return False
    except OSError as e:
        print(f"  {hname}\\{sub}  -> error {e}")
        return False
    with k:
        if depth == 0:
            print(f"  {hname}\\{sub}  -> EXISTS")
        i = 0
        while True:
            try:
                name, val, typ = winreg.EnumValue(k, i)
            except OSError:
                break
            tn = TYPE_NAME.get(typ, str(typ))
            if isinstance(val, bytes):
                val = val[:64].hex()
            print(f"{pad}VALUE  {name!r:<34} {tn:<14} = {val!r}")
            i += 1
        if depth < maxdepth:
            j = 0
            while True:
                try:
                    child = winreg.EnumKey(k, j)
                except OSError:
                    break
                print(f"{pad}SUBKEY {child}")
                dump_key(hive, hname, sub + "\\" + child, depth + 1, maxdepth)
                j += 1
    return True


if winreg:
    CANDIDATES = [
        r"Software\Insomniac Games",
        r"Software\Insomniac Games\Marvel's Spider-Man Remastered",
        r"Software\Insomniac Games\Marvel's Spider-Man",
        r"Software\Insomniac Games\Marvel's Spider-Man 2",
        r"Software\Sony Interactive Entertainment",
        r"Software\Nixxes",
        r"Software\Nixxes Software",
        r"Software\Marvel",
        r"Software\PlayStation PC",
        r"Software\PlayStation",
    ]
    for sub in CANDIDATES:
        dump_key(winreg.HKEY_CURRENT_USER, "HKCU", sub)
    print()
    # Broad sweep of HKCU\Software top-level names for anything spidey/sony
    print("  ---- HKCU\\Software top-level scan for spider/insomniac/nixxes/sony/playstation ----")
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software", 0, winreg.KEY_READ) as k:
            i = 0
            pat = re.compile(r"spider|insomniac|nixxes|sony|playstation|marvel", re.I)
            while True:
                try:
                    name = winreg.EnumKey(k, i)
                except OSError:
                    break
                if pat.search(name):
                    print(f"      HKCU\\Software\\{name}")
                i += 1
    except OSError as e:
        print(f"      (scan failed: {e})")


# ────────────────────────────────────────────────────────────
# 4. Steam userdata
# ────────────────────────────────────────────────────────────
print()
print("=" * 78)
print("4. STEAM  (userdata / appid 1817070 / launch options)")
print("=" * 78)
steam_paths = []
if winreg:
    for hive, hname, sub, val in [
        (winreg.HKEY_CURRENT_USER, "HKCU", r"Software\Valve\Steam", "SteamPath"),
        (winreg.HKEY_LOCAL_MACHINE, "HKLM", r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
        (winreg.HKEY_LOCAL_MACHINE, "HKLM", r"SOFTWARE\Valve\Steam", "InstallPath"),
    ]:
        try:
            with winreg.OpenKey(hive, sub, 0, winreg.KEY_READ) as k:
                v, _ = winreg.QueryValueEx(k, val)
                print(f"  {hname}\\{sub}\\{val} = {v}")
                steam_paths.append(Path(v))
        except OSError:
            print(f"  {hname}\\{sub}\\{val} -> not present")
for cand in [Path(r"C:\Program Files (x86)\Steam")]:
    if cand.is_dir() and cand not in steam_paths:
        steam_paths.append(cand)

for sp in steam_paths:
    ud = sp / "userdata"
    print(f"\n  userdata: {ud}  exists={ud.is_dir()}")
    if ud.is_dir():
        for uid in sorted(ud.iterdir()):
            g = uid / "1817070"
            print(f"      user {uid.name}: appid 1817070 dir exists = {g.is_dir()}")
            if g.is_dir():
                tree(g, f"steam userdata/{uid.name}/1817070")
    # localconfig (launch options / per-app language)
    if ud.is_dir():
        for uid in sorted(ud.iterdir()):
            lc = uid / "config" / "localconfig.vdf"
            if lc.is_file():
                try:
                    txt = lc.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                m = re.search(r'"1817070"\s*\{(.*?)\n\t{5}\}', txt, re.S)
                if m:
                    print(f"\n      localconfig.vdf [{uid.name}] app 1817070 block:")
                    for ln in m.group(1).splitlines()[:40]:
                        print("        " + ln.rstrip())
                else:
                    print(f"      localconfig.vdf [{uid.name}]: no 1817070 block")


# ────────────────────────────────────────────────────────────
# 5. Game folder: flt.ini + any loose settings/config files
# ────────────────────────────────────────────────────────────
print()
print("=" * 78)
print("5. GAME FOLDER (read-only)")
print("=" * 78)
print(f"  {GAME}  exists={GAME.is_dir()}")
if GAME.is_dir():
    for p in sorted(GAME.iterdir()):
        try:
            sz = p.stat().st_size if p.is_file() else -1
        except OSError:
            sz = -1
        print(f"      {'<DIR>' if p.is_dir() else f'{sz:>12}'}  {p.name}")

for name in ("flt.ini", "steam_emu.ini", "ALI213.ini", "codex.ini", "steam_settings",
             "NoDVD", "_SSE Fix"):
    p = GAME / name
    if p.is_file():
        print(f"\n  ---- {name} ----")
        try:
            print(p.read_text(encoding="utf-8", errors="replace")[:4000])
        except OSError as e:
            print(f"      (unreadable: {e})")
    elif p.is_dir():
        print(f"\n  ---- {name}/ (dir) ----")
        tree(p, name, max_files=80)

# any loose ini/cfg/json/xml anywhere in the game folder (excluding huge asset_archive)
print("\n  ---- loose config-ish files in game folder (excl. asset_archive) ----")
if GAME.is_dir():
    for p in GAME.rglob("*"):
        if "asset_archive" in p.parts:
            continue
        if p.is_file() and p.suffix.lower() in (".ini", ".cfg", ".json", ".xml", ".txt", ".vdf", ".yaml", ".yml"):
            try:
                print(f"      {p.stat().st_size:>10}  {p.relative_to(GAME)}")
            except OSError:
                pass


# ────────────────────────────────────────────────────────────
# 6. Exe strings — what setting names does the game itself know?
# ────────────────────────────────────────────────────────────
print()
print("=" * 78)
print("6. EXE STRINGS — language/settings keywords inside Spider-Man.exe")
print("=" * 78)
exe = GAME / "Spider-Man.exe"
if exe.is_file():
    data = exe.read_bytes()
    print(f"  size = {len(data):,}")

    def find_ascii(pattern, limit=60, ctx=0):
        rx = re.compile(pattern.encode("ascii"), re.I)
        seen, out = set(), []
        for m in rx.finditer(data):
            s = max(0, m.start() - 80)
            e = min(len(data), m.end() + 80)
            chunk = data[s:e]
            for tok in re.findall(rb"[\x20-\x7e]{4,}", chunk):
                t = tok.decode("ascii", "replace")
                if rx.search(tok) and t not in seen:
                    seen.add(t)
                    out.append(t)
                    if len(out) >= limit:
                        return out
        return out

    def find_utf16(pattern, limit=40):
        rx = re.compile(pattern.encode("utf-16-le"), re.I)
        seen, out = set(), []
        for m in rx.finditer(data):
            s = max(0, m.start() - 120)
            e = min(len(data), m.end() + 120)
            chunk = data[s:e]
            for tok in re.findall(rb"(?:[\x20-\x7e]\x00){4,}", chunk):
                t = tok.decode("utf-16-le", "replace")
                if pattern.lower() in t.lower() and t not in seen:
                    seen.add(t)
                    out.append(t)
                    if len(out) >= limit:
                        return out
        return out

    for pat in ["language", "Language", "subtitle", "Subtitle", "voice", "Voice",
                "locale", "settings.", "SETTINGS", "\\.ini", "\\.json", "\\.cfg",
                "Documents", "Saved Games", "Insomniac", "Nixxes",
                "Spider-Man Remastered", "SOFTWARE\\\\", "Software\\\\"]:
        hits = find_ascii(pat, limit=40)
        print(f"\n  ASCII ~ {pat!r}: {len(hits)} distinct")
        for h in hits[:40]:
            print(f"      {h}")

    print("\n  ---- UTF-16 probes ----")
    for pat in ["language", "Spider-Man", "Insomniac", "Documents", "settings",
                "Saved Games", "subtitle"]:
        hits = find_utf16(pat, limit=25)
        print(f"\n  UTF16 ~ {pat!r}: {len(hits)} distinct")
        for h in hits[:25]:
            print(f"      {h}")
else:
    print("  exe missing")

print()
print("DONE")
