"""
borderless_gaming_mod.py - local lifecycle for the Borderless Gaming Hebrew
translation (Avalonia window/upscaling utility, Steam appid 388080).

Two surfaces, both written ONLY under the user's data folder
(`%APPDATA%\\coreutils\\borderless-gaming`) - the Steam install is never
touched, so "Verify integrity of game files" cannot revert the translation and
no admin rights are needed:

  1. interface      -> `languages\\he-IL.json`, a real added locale (the picker
                       scans that folder), plus `settings.json` `"language"`.
  2. effect editor  -> the categories / effect names / parameter labels and
                       tooltips are authored INSIDE the .slang shader sources,
                       which cannot hold Hebrew: Slang's reflection step
                       serialises non-ASCII with C-style octal escapes and the
                       app rejects the file as invalid JSON. So we patch the
                       COMPILED EFFECT CACHE instead - its strings are plain
                       length-prefixed UTF-8 and its validity key is the SHA-256
                       of the SOURCE, which we never touch, so the patch stays
                       valid and the app never recompiles.

Cloud, NOT bundled: the payload comes from the Worker (slug
`borderless-gaming-hebrew` -> GitHub release) via `mod_source`; only the catalog
metadata ships in `software_catalog.py`.

Backup: a pristine copy of every cache entry lives under
`hebrew_backup\\effects\\` next to the cache, and the patch is always rebuilt
from it - so enabling twice cannot double-apply, and disable() restores
byte-identical files.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import time
from pathlib import Path
from typing import Callable

# cb(phase, pct, detail)
ProgressCB = Callable[[str, float, str], None]

CACHE_DIR = Path.home() / ".translation_manager" / "mod_cache" / "borderless-gaming"
STATE_FILE = CACHE_DIR / "state.json"
CACHE_LANG = CACHE_DIR / "he-IL.json"
CACHE_TABLES = CACHE_DIR / "effects_he"

TABLES = ("categories", "names", "descriptions", "labels", "tooltips")


# ── user data folder ──────────────────────────────────────────
def data_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    return Path(base) / "coreutils" / "borderless-gaming"


def _lang_target() -> Path:
    return data_dir() / "languages" / "he-IL.json"


def _effects_cache() -> Path:
    return data_dir() / "cache" / "effects"


def _effects_backup() -> Path:
    return data_dir() / "hebrew_backup" / "effects"


def _settings() -> Path:
    return data_dir() / "settings.json"


# ── the compiled-cache codec (.NET BinaryWriter stream) ───────
def _read_7bit(buf: bytes, pos: int) -> tuple[int, int]:
    n = shift = 0
    while True:
        b = buf[pos]
        pos += 1
        n |= (b & 0x7F) << shift
        if not b & 0x80:
            return n, pos
        shift += 7


def _read_str(buf: bytes, pos: int) -> tuple[str, int]:
    n, pos = _read_7bit(buf, pos)
    return buf[pos:pos + n].decode("utf-8"), pos + n


def _enc_str(s: str) -> bytes:
    b = s.encode("utf-8")
    out = bytearray()
    n = len(b)
    while n >= 0x80:
        out.append((n & 0x7F) | 0x80)
        n >>= 7
    out.append(n)
    return bytes(out) + b


def _header(buf: bytes) -> dict:
    pos = 4
    out: dict = {}
    for field in ("sha", "key", "name", "source", "category", "description"):
        start = pos
        val, pos = _read_str(buf, pos)
        out[field] = val
        out[field + "_span"] = (start, pos)
    out["end"] = pos
    return out


def _span_of(buf: bytes, anchor: str, which: int, start: int) -> tuple[int, int]:
    needle = _enc_str(anchor)
    i = buf.find(needle, start)
    if i < 0 or buf.find(needle, i + 1) >= 0:
        raise KeyError(anchor)          # missing, or ambiguous - never guess
    pos = i
    for _ in range(which):
        _, pos = _read_str(buf, pos)
    s = pos
    _, pos = _read_str(buf, s)
    return s, pos


def _replace(buf: bytes, edits: list[tuple[tuple[int, int], str]]) -> bytes:
    out = bytearray(buf)
    for (a, b), text in sorted(edits, key=lambda e: -e[0][0]):
        out[a:b] = _enc_str(text)
    return bytes(out)


_PARAM_RE = re.compile(
    r"\[bgfx::PARAM(?:_INT|_BOOL)?\(([^\]]*)\)\]\s*(?:\w[\w:<>, ]*?)\s+(\w+)\s*;", re.S)
_QUOTED = re.compile(r'"([^"]*)"')


def _source_params(slang: Path) -> list[tuple[str, str, str]]:
    try:
        text = slang.read_text("utf-8", errors="replace")
    except OSError:
        return []
    out = []
    for args, var in _PARAM_RE.findall(text):
        qs = _QUOTED.findall(args)
        if qs:
            out.append((var, qs[0], qs[-1] if len(qs) > 1 else ""))
    return out


# ── state ─────────────────────────────────────────────────────
def read_state() -> dict:
    if not STATE_FILE.exists():
        return {}
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write_state(state: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(STATE_FILE)


def is_cached() -> bool:
    return STATE_FILE.exists() and CACHE_LANG.exists()


def status() -> dict:
    st = read_state()
    enabled = bool(st.get("enabled", False))
    if enabled and not _lang_target().exists():
        enabled = False
    return {"cached": is_cached(), "enabled": enabled, "version": st.get("version")}


# ── cache population (from a cloud download) ──────────────────
def populate_cache(src: Path, version: str) -> dict:
    lang = src / "he-IL.json"
    if not lang.is_file():
        found = next(iter(src.rglob("he-IL.json")), None)
        lang = found if found else lang
    if not lang.is_file():
        return {"ok": False, "error": "לא נמצא he-IL.json בחבילה שהורדה"}

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(lang, CACHE_LANG)

    tables_src = lang.parent / "effects_he"
    if tables_src.is_dir():
        CACHE_TABLES.mkdir(parents=True, exist_ok=True)
        for name in TABLES:
            f = tables_src / f"{name}.json"
            if f.is_file():
                shutil.copy2(f, CACHE_TABLES / f"{name}.json")

    _write_state({"version": version, "cached_at": int(time.time()), "enabled": False})
    return {"ok": True, "count": 1}


# ── the two surfaces ──────────────────────────────────────────
def _set_language(code: str) -> None:
    try:
        p = _settings()
        data = json.loads(p.read_text("utf-8")) if p.is_file() else {}
        data["language"] = code
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                     encoding="utf-8", newline="\r\n")
    except (OSError, json.JSONDecodeError):
        pass                                    # the user can pick it in Settings


def _load_tables() -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for name in TABLES:
        f = CACHE_TABLES / f"{name}.json"
        try:
            out[name] = json.loads(f.read_text("utf-8")) if f.is_file() else {}
        except (OSError, json.JSONDecodeError):
            out[name] = {}
    return out


def _patch_effects(effects_dir: Path | None) -> int:
    """Patch every compiled effect. Returns the number of strings written."""
    cache = _effects_cache()
    if not cache.is_dir():
        return 0
    tables = _load_tables()
    if not any(tables.values()):
        return 0
    backup = _effects_backup()
    backup.mkdir(parents=True, exist_ok=True)

    written = 0
    for path in sorted(cache.glob("*.bin")):
        try:
            cur = path.read_bytes()
            bak = backup / path.name
            if bak.is_file():
                old = bak.read_bytes()
                try:
                    buf = old if _header(old)["sha"] == _header(cur)["sha"] else cur
                except (IndexError, UnicodeDecodeError):
                    buf = cur
                if buf is cur:
                    bak.write_bytes(cur)        # the app recompiled - refresh
            else:
                bak.write_bytes(cur)
                buf = cur

            head = _header(buf)
            edits: list[tuple[tuple[int, int], str]] = []
            for field, table in (("name", "names"), ("category", "categories"),
                                 ("description", "descriptions")):
                he = tables[table].get(head[field])
                if he:
                    edits.append((head[field + "_span"], he))

            src = None
            if effects_dir is not None:
                src = effects_dir / (head["key"].replace("\\", "/") + ".slang")
            if src is not None and src.is_file():
                for var, label, tip in _source_params(src):
                    for which, table, en in ((1, "labels", label), (2, "tooltips", tip)):
                        he = tables[table].get(en)
                        if not he:
                            continue
                        try:
                            edits.append((_span_of(buf, var, which, head["end"]), he))
                        except KeyError:
                            pass
            if edits:
                path.write_bytes(_replace(buf, edits))
                written += len(edits)
        except (OSError, IndexError, UnicodeDecodeError):
            continue                            # one bad entry must not stop the rest
    return written


def enable(cb: ProgressCB | None = None, effects_dir: Path | None = None) -> dict:
    """Install both surfaces. `effects_dir` = <install>\\effects (for the
    parameter anchors); without it only the header strings are translated."""
    if not is_cached():
        return {"ok": False, "error": "אין מטמון מקומי - יש להתקין קודם"}
    if cb:
        cb("apply", 15.0, "מתקין את קובץ השפה")
    try:
        target = _lang_target()
        target.parent.mkdir(parents=True, exist_ok=True)
        orig = target.with_suffix(".json.orig")
        if target.exists() and not orig.exists():
            shutil.copy2(target, orig)
        shutil.copy2(CACHE_LANG, target)
    except OSError as e:
        return {"ok": False, "error": f"כשל בכתיבת קובץ השפה: {e}"}

    _set_language("he-IL")
    if cb:
        cb("apply", 55.0, "מתרגם את עורך האפקטים")
    written = _patch_effects(effects_dir)

    st = read_state()
    st["enabled"] = True
    st["effect_strings"] = written
    _write_state(st)
    if cb:
        cb("apply", 100.0, "הושלם")
    return {"ok": True, "count": 1, "effectStrings": written}


def disable(cb: ProgressCB | None = None) -> dict:
    target = _lang_target()
    orig = target.with_suffix(".json.orig")
    try:
        if orig.exists():
            shutil.copy2(orig, target)
            orig.unlink(missing_ok=True)
        elif target.exists():
            target.unlink()
    except OSError as e:
        return {"ok": False, "error": f"כשל בשחזור: {e}"}

    try:
        if json.loads(_settings().read_text("utf-8")).get("language") == "he-IL":
            _set_language("")
    except (OSError, json.JSONDecodeError):
        pass

    backup = _effects_backup()
    if backup.is_dir():
        for b in sorted(backup.glob("*.bin")):
            try:
                t = _effects_cache() / b.name
                if t.is_file():
                    shutil.copy2(b, t)
                b.unlink()
            except OSError:
                continue

    st = read_state()
    st["enabled"] = False
    _write_state(st)
    return {"ok": True}


def clear_cache() -> dict:
    disable()
    shutil.rmtree(CACHE_DIR, ignore_errors=True)
    return {"ok": True}
