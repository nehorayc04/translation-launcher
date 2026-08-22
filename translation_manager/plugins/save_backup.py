"""
plugins.save_backup - the "Automatic Game-Save Backup" plugin engine.

What it does:
  • AUTO-LOCATES where a game keeps its saves - a known-paths database (per
    catalog id, extendable from the CLOUD so new games are covered with no app
    update) PLUS a smart heuristic scan of every common Windows save root, scored
    by name similarity + how "save-like" the folder looks (recent, small files).
  • Lets the user ADD a save folder by hand for anything the auto-locate misses.
  • BACKS UP each save folder to a safe place on a schedule - daily / weekly /
    monthly / every PC boot / on game launch / continuously while a game runs -
    with rotation (keep the last N) and change-detection (never re-copies an
    unchanged save).
  • RESTORES any backup, taking a safety snapshot of the current save first.

Every file operation goes through `resilience`, so a locked/AV-held file or a
transient error is healed silently instead of failing a backup. Nothing here
raises to the caller.
"""
from __future__ import annotations

import logging
import os
import sys
import re
import shutil
import time
from difflib import SequenceMatcher
from pathlib import Path

log = logging.getLogger(__name__)


def _real_home() -> Path:
    """The REAL Windows user profile - `C:\\Users\\<name>` - not whatever the
    `USERPROFILE` env var says.

    Why this matters: `Path.home()` / expanduser read `USERPROFILE`, and a
    launcher STARTED from an environment that redirects it (a sandbox, a
    dev IDE profile) inherits that redirection, so the default backup path
    landed under the redirected folder instead of the user's own home.
    `SHGetKnownFolderPath(FOLDERID_Profile)` reads the profile from the user's
    token/registry, which the env redirection does not touch, so it returns the
    genuine home. Falls back to Path.home() off-Windows / on any failure."""
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            class _GUID(ctypes.Structure):
                _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                            ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]

            # FOLDERID_Profile = {5E6C858F-0E22-4760-9AFE-EA3317B67173}
            fid = _GUID(0x5E6C858F, 0x0E22, 0x4760,
                        (ctypes.c_ubyte * 8)(0x9A, 0xFE, 0xEA, 0x33, 0x17, 0xB6, 0x71, 0x73))
            out = ctypes.c_wchar_p()
            shell32 = ctypes.windll.shell32
            shell32.SHGetKnownFolderPath.argtypes = [
                ctypes.POINTER(_GUID), wintypes.DWORD, wintypes.HANDLE,
                ctypes.POINTER(ctypes.c_wchar_p)]
            if shell32.SHGetKnownFolderPath(ctypes.byref(fid), 0, None,
                                            ctypes.byref(out)) == 0 and out.value:
                p = Path(out.value)
                ctypes.windll.ole32.CoTaskMemFree(out)
                return p
        except Exception:                                # pragma: no cover
            log.debug("save_backup: SHGetKnownFolderPath failed", exc_info=True)
    return Path.home()


_BACKUP_ROOT_DEFAULT = _real_home() / ".translation_manager" / "save_backups"


# ── Ubisoft product-id → game-name database (shipped) ─────────────────────
# Ubisoft Connect stores each save under `savegames\<account>\<numeric-id>`,
# where the number is the game's PRODUCT ID. The launcher's own local cache does
# NOT record that id inside its config text, so a 12,984-game static map (merged
# from the public iArtorias + Haoose ID lists) ships with the app and turns the
# bare folder number into the real title. Unknown ids fall back to the number.
_ubi_db: dict | None = None


def _ubisoft_db() -> dict:
    global _ubi_db
    if _ubi_db is not None:
        return _ubi_db
    _ubi_db = {}
    try:
        import json as _json
        base = getattr(sys, "_MEIPASS", None)
        cands = []
        if base:
            cands.append(Path(base) / "translation_manager" / "assets" / "ubisoft_games.json")
        cands.append(Path(__file__).resolve().parent.parent / "assets" / "ubisoft_games.json")
        for p in cands:
            if p.exists():
                data = _json.loads(p.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    _ubi_db = {str(k): str(v) for k, v in data.items()}
                    break
    except Exception:                                    # pragma: no cover
        log.debug("save_backup: ubisoft games db unavailable", exc_info=True)
    return _ubi_db


def ubisoft_game_name(number: str) -> str:
    """Real game title for a Ubisoft product id, or '' if unknown."""
    return _ubisoft_db().get(str(number), "")


# ── Save-folder size (for the heavy-backup warning) ──────────────────────
# Most game saves are tiny (<10 MB), but a few (e.g. Anno 1800's per-minute
# autosaves) can reach tens of GB. A backup of that copies the whole thing, so
# the user is warned + must confirm before adding such a folder.
HEAVY_BYTES = 500 * 1024 * 1024          # 500 MB → "heavy"
_SIZE_FILE_CAP = 300_000                 # stop walking after this many files (bound worst case)


def folder_size(path) -> tuple[int, bool]:
    """(total bytes, truncated?). A fast iterative os.scandir walk; stops after
    _SIZE_FILE_CAP files so a pathological folder can't hang the UI. `truncated`
    means the real size is at least this much."""
    total = 0
    seen = 0
    stack = [str(path)]
    try:
        while stack:
            d = stack.pop()
            try:
                with os.scandir(d) as it:
                    for e in it:
                        try:
                            if e.is_dir(follow_symlinks=False):
                                stack.append(e.path)
                            else:
                                total += e.stat(follow_symlinks=False).st_size
                                seen += 1
                                if seen >= _SIZE_FILE_CAP:
                                    return total, True
                        except OSError:
                            continue
            except OSError:
                continue
    except Exception:                                    # pragma: no cover
        pass
    return total, False


def fmt_size(n: int) -> str:
    """Human size: '8.4 MB', '~31 GB'."""
    f = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if f < 1024 or unit == "TB":
            return (f"{f:.0f} {unit}" if unit in ("B", "KB") or f >= 100
                    else f"{f:.1f} {unit}")
        f /= 1024
    return f"{n} B"

SCHEDULES = ("manual", "on_boot", "on_launch", "realtime", "daily", "weekly", "monthly")

# Files/dirs that are never a save (skip while scanning + while backing up).
_JUNK_NAMES = {"crashreports", "logs", "cache", "temp", "tmp", "screenshots",
               "videoclips", "config", "settings"}
_SAVE_EXTS = {".sav", ".save", ".dat", ".bin", ".profile", ".slot", ".sl2",
              ".ess", ".es3", ".json", ".xml", ".ckp", ".cfg", ".bak"}

# A Ubisoft ACCOUNT folder is UUID-named; a game folder under it is a numeric id.
_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")

# LocalLow is shared by games AND ordinary apps - these vendor folders are NOT
# games, so the "all games" heuristic sweep skips them (case-insensitive).
_NONGAME_VENDORS = {
    "amd", "adobe", "microsoft", "intel", "nvidia", "nvidia corporation", "iobit",
    "sun", "google", "mozilla", "oracle", "apple", "apple computer", "packages",
    "temp", "connecteddevicesplatform", "dropbox", "logishrd", "logitech", "razer",
    "corsair", "overwolf", "discord", "spotify", "zoom", "citrix", "vmware",
    "realtek", "waves audio", "elgato", "obs-studio", "teamspeak", "cef",
    "unrealengine", "unreal engine", "unity", "unitytechnologies",
}


def default_config() -> dict:
    return {
        "destination": str(_BACKUP_ROOT_DEFAULT),
        "schedule":    "daily",
        "keep":        10,
        "entries":     [],       # [{id, game_id, label, source, auto, enabled}]
        "last":        {},       # {entry_id: {"at": epoch, "fp": [...], "count": n}}
    }


# ─────────────────────────────────────────────────────────────
# Common Windows save roots - searched in this order of likelihood
# ─────────────────────────────────────────────────────────────
def _env(name: str) -> str | None:
    """Env value, but the USER-scoped folders resolved to the REAL profile.

    Game saves live under the genuine user home (Saved Games, Documents\\My
    Games, AppData\\LocalLow, …) because the GAMES run as that user - NOT in
    whatever environment launched us. So when USERPROFILE/LOCALAPPDATA/APPDATA
    are redirected (a sandbox / dev IDE profile), reading them verbatim points
    detection at an empty folder and it finds nothing but Ubisoft (whose path is
    under %PROGRAMFILES%, which is never redirected - exactly the symptom). Map
    the user-scoped vars onto _real_home(); everything else is read as-is. For a
    normal user these are identical, so nothing changes."""
    n = name.upper()
    if n == "USERPROFILE":
        return str(_real_home())
    if n == "LOCALAPPDATA":
        return str(_real_home() / "AppData" / "Local")
    if n == "APPDATA":
        return str(_real_home() / "AppData" / "Roaming")
    return os.environ.get(name)


_VAR_RE = re.compile(r"%([^%]+)%")


def _expandvars_real(tmpl: str) -> str:
    """os.path.expandvars, but %USERPROFILE%/%LOCALAPPDATA%/%APPDATA% resolve to
    the REAL profile (via _env). Non-user vars (%PROGRAMFILES(X86)%, %PUBLIC%)
    fall through to the environment unchanged."""
    def sub(m):
        v = _env(m.group(1))
        return v if v is not None else m.group(0)
    return _VAR_RE.sub(sub, tmpl)


def _save_roots() -> list[Path]:
    home = _real_home()
    roots: list[Path] = []

    def add(p: Path | None) -> None:
        if p and p not in roots:
            roots.append(p)

    add(home / "Saved Games")
    add(home / "Documents" / "My Games")
    add(home / "Documents")
    lad = _env("LOCALAPPDATA")
    if lad:
        add(Path(lad))
        add(Path(lad + "Low"))          # Unity games use %LOCALAPPDATA%Low
    ad = _env("APPDATA")
    if ad:
        add(Path(ad))
    pub = _env("PUBLIC")
    if pub:
        add(Path(pub) / "Documents")
    return [r for r in roots if r.exists()]


# ─────────────────────────────────────────────────────────────
# Known save-path database - authoritative for the tricky games.
# Cloud-extendable: register_known(cloud_rows) merges new games at runtime, so a
# game added on the website gets correct save detection with NO app update.
# Templates use %ENVVAR% + are matched case-insensitively.
# ─────────────────────────────────────────────────────────────
# Ubisoft Connect: savegames\<account-uuid>\<ubisoft-game-id>\. NOT under
# %LOCALAPPDATA% (an earlier guess) - it lives beside the launcher itself. The
# trailing `*` is a wildcard expanded by _expand_all() → one candidate per ACCOUNT.
_UBI_SAVES = r"%PROGRAMFILES(X86)%\Ubisoft\Ubisoft Game Launcher\savegames\*"

_KNOWN: dict[str, list[str]] = {
    "cyberpunk":       [r"%USERPROFILE%\Saved Games\CD Projekt Red\Cyberpunk 2077"],
    "witcher3":        [r"%USERPROFILE%\Documents\The Witcher 3\gamesaves"],
    "spiderman2":      [r"%USERPROFILE%\Documents\Marvel's Spider-Man 2\Saved Games"],
    "gowragnarok":     [r"%USERPROFILE%\Saved Games\God of War Ragnarok"],
    "hogwarts":        [r"%LOCALAPPDATA%\Hogwarts Legacy\Saved\SaveGames"],
    "watchdogs2":      [r"%USERPROFILE%\Documents\My Games\Watch Dogs 2"],
    "anno1800":        [r"%USERPROFILE%\Documents\Anno 1800\accounts"],
    "gtav":            [r"%USERPROFILE%\Documents\Rockstar Games\GTA V\Profiles"],
    "rdr2":            [r"%USERPROFILE%\Documents\Rockstar Games\Red Dead Redemption 2\Profiles"],
    "tlou1":           [r"%USERPROFILE%\Saved Games\The Last of Us Part I"],
    "tlou2":           [r"%USERPROFILE%\Saved Games\The Last of Us Part II"],
    "plague-tale-requiem": [r"%LOCALAPPDATA%\Focus Interactive\APlagueTaleRequiem"],
    # Ubisoft Connect keeps saves as savegames\<account-uuid>\<ubisoft-game-id>\.
    # The `*` matches EVERY account, so a PC with several Ubisoft users yields one
    # candidate per account - all of them backed up, even for the same game (the
    # account uuid is folded into the label so they never overwrite each other).
    # We deliberately stop at the ACCOUNT folder rather than guessing the numeric
    # per-game id: it backs up that account's Ubisoft saves wholesale, which is
    # what a backup wants. A user who wants ONE exact game can still add the
    # `<account>\<game-id>` folder by hand (manual folders are fully supported).
    "acshadows":       [_UBI_SAVES],
    "watchdogs2":      [_UBI_SAVES],
    "anno1800":        [r"%USERPROFILE%\Documents\Anno 1800\accounts", _UBI_SAVES],
    "acblackflag":     [_UBI_SAVES],
    "acunity":         [_UBI_SAVES],
    "ac2":             [_UBI_SAVES],
}


def register_known(rows: list[dict]) -> int:
    """Merge cloud-supplied save-path templates from catalog rows
    (`row["savePaths"] = ["%USERPROFILE%\\..."]`). Additive, idempotent."""
    added = 0
    try:
        for row in rows or []:
            cid = row.get("id")
            paths = row.get("savePaths") or row.get("save_paths")
            if isinstance(paths, str):
                paths = [paths]
            if not (isinstance(cid, str) and isinstance(paths, list)):
                continue
            have = _KNOWN.setdefault(cid, [])
            for tmpl in paths:
                if isinstance(tmpl, str) and tmpl.strip() and tmpl not in have:
                    have.append(tmpl.strip())
                    added += 1
    except Exception:                                    # pragma: no cover
        pass
    return added


def _expand(tmpl: str) -> Path:
    return Path(_expandvars_real(tmpl))


def _expand_all(tmpl: str) -> list[Path]:
    """Expand a template into every folder it matches.

    Supports a `*` WILDCARD, which is what makes multi-account launchers work:
    Ubisoft stores saves as `savegames\\<account-uuid>\\<game-id>`, so several
    Windows/Ubisoft users on one PC each get their own uuid folder. The wildcard
    yields ONE candidate per account, so every user's saves are backed up - even
    for the same game - instead of only whichever account happened to be first.
    Also used by cloud-supplied `savePaths`, so a future game can ship a wildcard
    template with no app update. Returns [] when nothing matches."""
    raw = _expandvars_real(tmpl)
    if "*" not in raw and "?" not in raw:
        p = Path(raw)
        return [p] if p.is_dir() else []
    try:
        # Anchor the glob at the last fixed ancestor so we never walk from a drive root.
        parts = Path(raw).parts
        fixed = [q for q in parts if "*" not in q and "?" not in q]
        idx   = len(fixed)
        base  = Path(*parts[:idx]) if idx else Path(raw).anchor
        pat   = str(Path(*parts[idx:])) if idx < len(parts) else "*"
        if not base.is_dir():
            return []
        # Skip junk that lives beside a real save folder - most importantly a
        # DOT-folder like `.tmp.driveupload` (a Google-Drive backup temp dir that
        # sits inside Ubisoft's `savegames\`), plus known non-save names. Without
        # this the Ubisoft `savegames\*` wildcard matched `.tmp.driveupload`
        # instead of the real account-uuid folder.
        return sorted(
            (p for p in base.glob(pat)
             if p.is_dir() and not p.name.startswith(".")
             and p.name.lower() not in _JUNK_NAMES),
            key=lambda p: p.name,
        )
    except (OSError, ValueError, IndexError):            # pragma: no cover
        return []


# ─────────────────────────────────────────────────────────────
# The smart auto-locate ("AI brain")
# ─────────────────────────────────────────────────────────────
def _norm(s: str) -> str:
    try:
        from .. import game_detector
        return game_detector._norm(s)
    except Exception:                                    # pragma: no cover
        import re
        return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def _looks_like_saves(folder: Path) -> float:
    """0..1 - how much this folder looks like a real save folder: it has files,
    they were touched recently, and some carry save-like extensions."""
    try:
        recent = 0
        save_ext = 0
        total = 0
        now = time.time()
        for f in folder.rglob("*"):
            try:
                if not f.is_file():
                    continue
                total += 1
                if total > 400:                          # cap the walk - cheap
                    break
                age = now - f.stat().st_mtime
                if age < 60 * 86400:                     # touched in the last 60d
                    recent += 1
                if f.suffix.lower() in _SAVE_EXTS:
                    save_ext += 1
            except OSError:
                continue
        if total == 0:
            return 0.0
        score = 0.35 * min(1.0, recent / max(1, total)) \
            + 0.35 * min(1.0, save_ext / max(1, total)) \
            + 0.30
        return round(min(1.0, score), 3)
    except Exception:                                    # pragma: no cover
        return 0.0


def _name_score(a: str, b: str) -> float:
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    if na in nb or nb in na:
        return 0.9
    return SequenceMatcher(None, na, nb).ratio()


def detect_for_game(game_id: str, title: str = "") -> list[dict]:
    """Best-guess save folders for one game, best-first.
    Each candidate: {path, source: 'known'|'heuristic', confidence, label}."""
    out: list[dict] = []
    seen: set[str] = set()

    def add(p: Path, source: str, conf: float, label: str) -> None:
        try:
            rp = str(p.resolve()).lower()
        except Exception:                                # pragma: no cover
            rp = str(p).lower()
        if rp in seen or not p.exists() or not p.is_dir():
            return
        seen.add(rp)
        out.append({"path": str(p), "source": source,
                    "confidence": round(conf, 3), "label": label or title or game_id})

    # 1) Authoritative known paths - highest confidence. A template may contain a
    #    `*` (Ubisoft's per-ACCOUNT uuid folder) and then expands to one candidate
    #    per account. Each gets the account folded into its LABEL, so two accounts
    #    with the same game land in separate backup folders and never overwrite
    #    each other (the label is what backup_entry uses as the destination dir).
    for tmpl in _KNOWN.get(game_id, []):
        matches = _expand_all(tmpl)
        multi = len(matches) > 1
        for p in matches:
            label = title or game_id
            if multi:
                label = f"{label} ({p.name})"
            add(p, "known", 0.98, label)

    # 2) Heuristic scan of the common roots (name similarity × save-likeness).
    label_terms = [t for t in (title, game_id) if t]
    for root in _save_roots():
        try:
            children = list(root.iterdir())
        except (OSError, PermissionError):
            continue
        for child in children:
            try:
                if not child.is_dir() or child.name.lower() in _JUNK_NAMES:
                    continue
            except OSError:
                continue
            ns = max((_name_score(t, child.name) for t in label_terms), default=0.0)
            if ns < 0.6:
                continue
            like = _looks_like_saves(child)
            conf = round(0.6 * ns + 0.4 * like, 3)
            if conf >= 0.55:
                add(child, "heuristic", conf, title or child.name)

    out.sort(key=lambda c: c["confidence"], reverse=True)
    return out


def detect_all(games: list[dict]) -> list[dict]:
    """Run auto-locate across every installed game. `games` = [{id, title}]."""
    results: list[dict] = []
    for g in games or []:
        gid = g.get("id")
        if not gid:
            continue
        cands = detect_for_game(gid, g.get("title") or g.get("titleEn") or "")
        if cands:
            results.append({"game_id": gid,
                            "title": g.get("title") or g.get("titleEn") or gid,
                            "candidates": cands})
    return results


# ─────────────────────────────────────────────────────────────
# Universal detection - ALL games, not just the catalog. Ubisoft is a special
# case (per-account, per-game-id folders), plus a heuristic sweep of the
# game-dedicated save roots so a game with no translation / not in the catalog is
# still backed up.
# ─────────────────────────────────────────────────────────────
def _ubi_savegames_root() -> "Path | None":
    p = Path(os.path.expandvars(
        r"%PROGRAMFILES(X86)%\Ubisoft\Ubisoft Game Launcher\savegames"))
    return p if p.is_dir() else None


def _clean_children(folder: Path) -> list[Path]:
    """Real sub-folders, skipping dot-junk (`.tmp.driveupload`) + known non-saves."""
    try:
        return sorted(
            (c for c in folder.iterdir()
             if c.is_dir() and not c.name.startswith(".")
             and c.name.lower() not in _JUNK_NAMES),
            key=lambda c: c.name,
        )
    except (OSError, PermissionError):
        return []


def detect_ubisoft_accounts() -> list[dict]:
    """Every Ubisoft Connect ACCOUNT that has saves, and every GAME under it - by
    its numeric Ubisoft id, INCLUDING games the launcher doesn't know. Saves live
    at `savegames\\<account-uuid>\\<game-id>`. An account = a UUID-named folder; it
    may sit directly under savegames OR one level down inside a user-made container
    (e.g. a "עוד משתמשים" folder holding extra accounts). Returns one group per
    account: [{account, accountShort, container, path, games:[{number, path}]}]."""
    root = _ubi_savegames_root()
    if root is None:
        return []
    found: list[tuple[Path, "str | None"]] = []
    for c in _clean_children(root):
        if _UUID_RE.match(c.name):
            found.append((c, None))                      # account directly under savegames
        else:                                            # a container folder → look one level in
            for cc in _clean_children(c):
                if _UUID_RE.match(cc.name):
                    found.append((cc, c.name))
    out: list[dict] = []
    for acc, container in found:
        games = [{"number": g.name, "path": str(g),
                  "name": ubisoft_game_name(g.name)}      # resolved title, '' if unknown
                 for g in _clean_children(acc)]
        if games:
            out.append({"account": acc.name, "accountShort": acc.name[:8],
                        "container": container, "path": str(acc), "games": games})
    return out


def _game_save_roots() -> list[tuple[Path, bool]]:
    """(root, dedicated?) - a DEDICATED root is game-only (every subfolder is a
    game); LocalLow is MIXED (games + ordinary apps → vendor-blocklist + heuristic)."""
    home = Path.home()
    roots: list[tuple[Path, bool]] = [
        (home / "Saved Games", True),
        (home / "Documents" / "My Games", True),
    ]
    lad = _env("LOCALAPPDATA")
    if lad:
        roots.append((Path(lad + "Low"), False))         # Unity games live here (+ apps)
    return [(r, d) for (r, d) in roots if r.exists()]


def detect_generic_saves(exclude: set[str]) -> list[dict]:
    """Sweep the game-dedicated roots for ANY game save, so a game NOT in the
    catalog is still offered. `exclude` = lowercased paths already covered (catalog
    + Ubisoft). A Saved-Games / My-Games subfolder IS a game (surfaced directly);
    LocalLow is filtered by the non-game vendor blocklist + the save-likeness score."""
    out: list[dict] = []
    seen = {p.lower() for p in exclude}
    for root, dedicated in _game_save_roots():
        for child in _clean_children(root):
            rp = str(child).lower()
            if rp in seen or child.name.lower() in _NONGAME_VENDORS:
                continue
            if dedicated:
                conf = 0.8
            else:
                like = _looks_like_saves(child)
                if like < 0.55:
                    continue
                conf = round(like, 3)
            seen.add(rp)
            out.append({"game_id": "generic", "title": child.name, "path": str(child),
                        "source": "heuristic", "confidence": conf, "label": child.name})
    out.sort(key=lambda c: c["confidence"], reverse=True)
    return out


# ─────────────────────────────────────────────────────────────
# Backup engine
# ─────────────────────────────────────────────────────────────
def _safe_name(s: str) -> str:
    keep = "".join(c if (c.isalnum() or c in " ._-") else "_" for c in (s or "backup"))
    return keep.strip().strip(".") or "backup"


def _fingerprint(folder: Path) -> tuple[int, int, float]:
    """(file_count, total_bytes, newest_mtime) - a cheap change signal so we
    never re-copy a save that hasn't changed since the last backup."""
    count = 0
    size = 0
    newest = 0.0
    try:
        for f in folder.rglob("*"):
            try:
                if not f.is_file():
                    continue
                st = f.stat()
                count += 1
                size += st.st_size
                if st.st_mtime > newest:
                    newest = st.st_mtime
            except OSError:
                continue
    except Exception:                                    # pragma: no cover
        pass
    return count, size, round(newest, 3)


def backup_entry(entry: dict, config: dict, *, force: bool = False,
                 name: str = "") -> dict:
    """Back up one entry's save folder. Skips silently when the save is unchanged
    (unless force). Returns {ok, skipped?, path?, error?}.

    Every backup lands in the SAFE folder under `<destination>/<game label>/` in
    its own dated subfolder named by the FULL timestamp (YYYY-MM-DD_HH-MM-SS), so
    the archive is always sorted by date. An optional `name` (for a manual "back
    up now") is appended to that folder so the user can label a snapshot."""
    from .. import resilience
    src = Path(entry.get("source", ""))
    if not src.exists() or not src.is_dir():
        return {"ok": False, "error": "source-missing"}

    fp = _fingerprint(src)
    eid = entry.get("id", "")
    last = (config.get("last") or {}).get(eid) or {}
    if not force and last.get("fp") and list(last["fp"]) == list(fp):
        return {"ok": True, "skipped": True, "reason": "unchanged"}

    dest_root = Path(config.get("destination") or _BACKUP_ROOT_DEFAULT)
    stamp = time.strftime("%Y-%m-%d_%H-%M-%S")     # full date+time: year-month-day_h-m-s
    folder = stamp + ("_" + _safe_name(name) if name else "")
    label = _safe_name(entry.get("label") or entry.get("game_id") or "save")
    dest = dest_root / label / folder

    # Disk-space pre-flight: never START a copy we can't finish (a full target
    # drive would leave a partial backup). The game's SOURCE saves are read-only
    # here, so this only guards the DESTINATION - a full disk can never touch them.
    need = fp[1]                                          # total source bytes
    try:
        probe = dest_root if dest_root.exists() else Path(dest_root.anchor or ".")
        free = shutil.disk_usage(probe).free
    except Exception:                                    # pragma: no cover
        free = None
    if free is not None and need and free < need + 50 * 1048576:      # 50 MB margin
        return {"ok": False, "error": "diskfull",
                "needed_mb": round(need / 1048576, 1),
                "free_mb": round(free / 1048576, 1)}

    def _copy() -> bool:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dest,
                        ignore=shutil.ignore_patterns(*_JUNK_NAMES),
                        dirs_exist_ok=True)
        return True

    ok = resilience.attempt(_copy, fallback=False,
                            name=f"savebackup.copy:{label}", path=dest)
    if not ok:
        # A mid-copy failure may leave a partial folder - remove it so there's no
        # half-backup, then re-check free space to report disk-full precisely.
        resilience.file_op(shutil.rmtree, dest, name="savebackup.cleanup",
                           path=dest, ignore_errors=True)
        try:
            probe = dest_root if dest_root.exists() else Path(dest_root.anchor or ".")
            if shutil.disk_usage(probe).free < (need or 0):
                return {"ok": False, "error": "diskfull"}
        except Exception:                                # pragma: no cover
            pass
        return {"ok": False, "error": "copy-failed"}

    # keep = 0 → UNLIMITED (keep every backup). `config.get("keep") or 10` would
    # wrongly turn 0 into 10, so read it explicitly.
    keep = config.get("keep")
    _rotate(dest_root / label, int(keep) if keep is not None else 10)

    last_map = config.setdefault("last", {})
    last_map[eid] = {"at": int(time.time()), "fp": list(fp), "count": fp[0]}
    return {"ok": True, "path": str(dest), "files": fp[0]}


def _is_named(folder_name: str) -> bool:
    """A NAMED manual snapshot (`<date>_<time>_<name>`) vs a bare automatic
    timestamp (`<date>_<time>`). Bare = exactly 2 underscore parts."""
    return folder_name.count("_") > 1


def _rotate(folder: Path, keep: int) -> None:
    """Keep only the newest `keep` AUTOMATIC (timestamp-only) backups under
    `folder`. NAMED manual snapshots are intentional and never auto-deleted."""
    if keep <= 0:
        return
    from .. import resilience
    try:
        subs = [d for d in folder.iterdir() if d.is_dir() and not _is_named(d.name)]
    except (OSError, PermissionError):
        return
    subs.sort(key=lambda d: d.name)                      # timestamp names sort chronologically
    for old in subs[:-keep]:
        resilience.file_op(shutil.rmtree, old, name="savebackup.rotate",
                           path=old, ignore_errors=True)


def list_backups(config: dict) -> list[dict]:
    """Every backup on disk, newest-first: {label, when, path, files, size_mb}."""
    dest_root = Path(config.get("destination") or _BACKUP_ROOT_DEFAULT)
    out: list[dict] = []
    if not dest_root.exists():
        return out
    try:
        for label_dir in dest_root.iterdir():
            if not label_dir.is_dir():
                continue
            for snap in label_dir.iterdir():
                if not snap.is_dir():
                    continue
                count, size, mtime = _fingerprint(snap)
                out.append({
                    "label":   label_dir.name,
                    "when":    snap.name,
                    "at":      mtime,
                    "path":    str(snap),
                    "files":   count,
                    "size_mb": round(size / 1048576, 2),
                })
    except (OSError, PermissionError):
        pass
    out.sort(key=lambda b: b["at"], reverse=True)
    return out


def restore(backup_path: str, target: str) -> dict:
    """Restore a backup over the live save folder. Takes a SAFETY snapshot of the
    current state first (into a `.pre-restore` sibling) so a restore is itself
    reversible. Returns {ok, safety?, error?}."""
    from .. import resilience
    bp = Path(backup_path)
    tgt = Path(target)
    if not bp.exists() or not bp.is_dir():
        return {"ok": False, "error": "backup-missing"}

    safety = None
    if tgt.exists():
        stamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        safety = tgt.parent / f"{tgt.name}.pre-restore-{stamp}"
        resilience.file_op(shutil.copytree, tgt, safety,
                           name="savebackup.safety", path=safety, dirs_exist_ok=True)

    def _do() -> bool:
        tgt.mkdir(parents=True, exist_ok=True)
        shutil.copytree(bp, tgt, dirs_exist_ok=True)
        return True

    ok = resilience.attempt(_do, fallback=False, name="savebackup.restore", path=tgt)
    if not ok:
        return {"ok": False, "error": "restore-failed",
                "safety": str(safety) if safety else None}
    return {"ok": True, "safety": str(safety) if safety else None}


# ─────────────────────────────────────────────────────────────
# Scheduling helpers (used by the host)
# ─────────────────────────────────────────────────────────────
_PERIOD_S = {
    "daily":   86400,
    "weekly":  7 * 86400,
    "monthly": 30 * 86400,
}


def is_due(entry: dict, config: dict, *, now: float | None = None) -> bool:
    """Should this entry be backed up right now, given the schedule?"""
    sched = config.get("schedule", "manual")
    if sched in ("manual", "on_boot", "on_launch"):
        return False                                     # driven by explicit events
    now = now if now is not None else time.time()
    last = (config.get("last") or {}).get(entry.get("id", "")) or {}
    last_at = float(last.get("at") or 0)
    if sched == "realtime":
        return (now - last_at) >= 300                    # at most every 5 min while playing
    period = _PERIOD_S.get(sched)
    if period is None:
        return False
    return (now - last_at) >= period
