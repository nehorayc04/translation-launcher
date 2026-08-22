"""Borderless Gaming - Hebrew translation installer.

Everything is written to your USER folder
(%APPDATA%\\coreutils\\borderless-gaming). The Steam install folder is never
touched, so "Verify integrity of game files" can never undo the translation and
no administrator rights are needed.

    python install.py            install
    python install.py --revert   remove
    python install.py "D:\\path\\to\\Borderless Gaming"   if auto-detect fails

Two surfaces are translated:
  1. the app interface  -> languages\\he-IL.json
  2. the effect editor  -> the compiled effect cache is patched in place
     (the shader metadata is authored inside the .slang sources, which cannot
     hold Hebrew - see קרא_אותי.txt)
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bg_cache as C  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = Path(__file__).resolve().parent
APPDATA = Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming"))
ROOT = APPDATA / "coreutils" / "borderless-gaming"
LANGS = ROOT / "languages"
CACHE = ROOT / "cache" / "effects"
BACKUP = ROOT / "hebrew_backup" / "effects"
SETTINGS = ROOT / "settings.json"
TABLES = ("categories", "names", "descriptions", "labels", "tooltips")


# ---------------------------------------------------------------- locate the app

def steam_libraries() -> list[Path]:
    libs: list[Path] = []
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as k:
            libs.append(Path(winreg.QueryValueEx(k, "SteamPath")[0]))
    except Exception:
        pass
    libs += [Path(r"C:\Program Files (x86)\Steam"), Path(r"C:\Steam")]
    out = list(libs)
    for base in libs:
        vdf = base / "steamapps" / "libraryfolders.vdf"
        if vdf.is_file():
            for line in vdf.read_text("utf-8", errors="replace").splitlines():
                if '"path"' in line:
                    parts = line.split('"')
                    if len(parts) >= 4:
                        out.append(Path(parts[3].replace("\\\\", "\\")))
    return out


def find_effects(explicit: str | None) -> Path | None:
    cands: list[Path] = []
    if explicit:
        p = Path(explicit)
        cands += [p / "effects", p]
    for lib in steam_libraries():
        cands.append(lib / "steamapps" / "common" / "Borderless Gaming" / "effects")
    for c in cands:
        if c.is_dir() and any(c.rglob("*.slang")):
            return c
    return None


# ---------------------------------------------------------------- the two surfaces

def install_language() -> None:
    LANGS.mkdir(parents=True, exist_ok=True)
    shutil.copy2(HERE / "he-IL.json", LANGS / "he-IL.json")
    print(f"  interface  -> {LANGS / 'he-IL.json'}")
    try:
        data = json.loads(SETTINGS.read_text("utf-8")) if SETTINGS.is_file() else {}
        data["language"] = "he-IL"
        SETTINGS.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                            encoding="utf-8", newline="\r\n")
        print("  language set to he-IL")
    except Exception as exc:
        print(f"  (could not set the language automatically: {exc})")
        print("  -> pick עברית in Settings > Language")


def install_effects(effects: Path | None) -> None:
    if not CACHE.is_dir() or not any(CACHE.glob("*.bin")):
        print("  effects    -> SKIPPED: no compiled effects yet.")
        print("               Start Borderless Gaming once, then run this installer again.")
        return
    if effects is None:
        print("  effects    -> SKIPPED: could not find the Borderless Gaming folder.")
        print("               Re-run as:  python install.py \"<path to Borderless Gaming>\"")
        return

    tables = {n: json.loads((HERE / "effects_he" / f"{n}.json").read_text("utf-8"))
              for n in TABLES}
    BACKUP.mkdir(parents=True, exist_ok=True)
    patched = 0
    for path in sorted(CACHE.glob("*.bin")):
        bak = BACKUP / path.name
        cur = path.read_bytes()
        if bak.is_file():
            old = bak.read_bytes()
            try:
                buf = old if C.read_header(old)["sha"] == C.read_header(cur)["sha"] else cur
            except Exception:
                buf = cur
            if buf is cur:
                bak.write_bytes(cur)
        else:
            bak.write_bytes(cur)
            buf = cur

        try:
            head = C.read_header(buf)
        except Exception:
            continue
        edits = []
        for field, table in (("name", "names"), ("category", "categories"),
                             ("description", "descriptions")):
            he = tables[table].get(head[field])
            if he:
                edits.append((head[field + "_span"], he))
        src = effects / (head["key"].replace("\\", "/") + ".slang")
        if src.is_file():
            for var, label, tip in C.source_params(src):
                for which, table, en in ((1, "labels", label), (2, "tooltips", tip)):
                    he = tables[table].get(en)
                    if not he:
                        continue
                    try:
                        edits.append((C.span_of(buf, var, which, head["end"]), he))
                    except Exception:
                        pass
        if edits:
            path.write_bytes(C.replace_spans(buf, edits))
            patched += len(edits)
    print(f"  effects    -> {patched} strings patched in the effect cache")


def revert() -> None:
    f = LANGS / "he-IL.json"
    if f.is_file():
        f.unlink()
        print(f"  removed {f}")
    try:
        if SETTINGS.is_file():
            data = json.loads(SETTINGS.read_text("utf-8"))
            if data.get("language") == "he-IL":
                data["language"] = ""
                SETTINGS.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                                    encoding="utf-8", newline="\r\n")
                print("  language reset to the app default")
    except Exception:
        pass
    n = 0
    if BACKUP.is_dir():
        for b in sorted(BACKUP.glob("*.bin")):
            t = CACHE / b.name
            if t.is_file():
                shutil.copy2(b, t)
                n += 1
            b.unlink()
    print(f"  restored {n} effect cache entries")


def main() -> int:
    args = sys.argv[1:]
    if "--revert" in args:
        print("Borderless Gaming - removing the Hebrew translation")
        revert()
        print("\nDone. Restart Borderless Gaming (tray > Exit).")
        return 0

    explicit = next((a for a in args if not a.startswith("--")), None)
    print("Borderless Gaming - installing the Hebrew translation")
    effects = find_effects(explicit)
    if effects:
        print(f"  found the app at {effects.parent}")
    install_language()
    install_effects(effects)
    print("\nDone. Restart Borderless Gaming (tray > Exit) and it comes up in Hebrew.")
    print("After a Borderless Gaming update, run this installer again.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
