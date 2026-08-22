"""Apply the Hebrew shader metadata by patching the compiled-effect cache.

Why the cache and not the .slang sources: a user-side .slang DOES override the
installed one (proven in-app), but Slang's reflection step serialises non-ASCII
attribute text with C-style octal escapes, which is not valid JSON, so any file
containing Hebrew is rejected outright. The cache skips that stage; see
work/bg_cache.py for the format.

Idempotent and re-runnable. Each entry keeps a pristine copy under
    %APPDATA%\\coreutils\\borderless-gaming\\hebrew_backup\\effects\\
and a patch is always built from that copy, so running twice cannot double-
apply. If the app ever recompiles an entry (the software updated, so the source
hash changed), the backup is refreshed from the new compile first and the
Hebrew is re-applied on top - which is exactly what "run it again after an
update" has to mean.

    python work/build_effects.py            # dry run: what would change
    python work/build_effects.py --deploy
    python work/build_effects.py --revert
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import bg_cache as C  # noqa: E402
from build_menu_proof import real_appdata  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent.parent
GAME_EFFECTS = Path(r"F:/SteamLibrary/steamapps/common/Borderless Gaming/effects")
ROOT = real_appdata() / "coreutils" / "borderless-gaming"
CACHE = ROOT / "cache" / "effects"
BACKUP = ROOT / "hebrew_backup" / "effects"


def load_tables() -> dict[str, dict[str, str]]:
    d = HERE / "effects_he"
    return {name: json.loads((d / f"{name}.json").read_text("utf-8"))
            for name in ("categories", "names", "descriptions", "labels", "tooltips")}


def qa() -> None:
    r = subprocess.run([sys.executable, str(HERE / "work" / "qa_effects.py")],
                       capture_output=True, text=True, encoding="utf-8")
    print(r.stdout.strip())
    if r.returncode != 0:
        sys.exit("QA failed - not deploying.")


def base_bytes(path: Path, bak: Path) -> bytes:
    """The pristine English compile to patch from, refreshing a stale backup."""
    cur = path.read_bytes()
    if bak.exists():
        old = bak.read_bytes()
        try:
            if C.read_header(old)["sha"] == C.read_header(cur)["sha"]:
                return old            # our own patch, or an untouched re-run
        except Exception:
            pass
        bak.write_bytes(cur)          # the app recompiled from a new source
        return cur
    bak.parent.mkdir(parents=True, exist_ok=True)
    bak.write_bytes(cur)
    return cur


def patch_one(path: Path, t: dict[str, dict[str, str]], apply: bool) -> tuple[int, list[str]]:
    bak = BACKUP / path.name
    buf = base_bytes(path, bak) if apply else path.read_bytes()
    head = C.read_header(buf)
    edits: list[tuple[tuple[int, int], str]] = []
    notes: list[str] = []

    for field, table in (("name", "names"), ("category", "categories"),
                         ("description", "descriptions")):
        he = t[table].get(head[field])
        if he:
            edits.append((head[field + "_span"], he))

    src = GAME_EFFECTS / (head["key"].replace("\\", "/") + ".slang")
    if src.exists():
        for var, label, tip in C.source_params(src):
            for which, table, en in ((1, "labels", label), (2, "tooltips", tip)):
                he = t[table].get(en)
                if not he:
                    continue
                try:
                    edits.append((C.span_of(buf, var, which, head["end"]), he))
                except (KeyError, ValueError) as exc:
                    notes.append(f"{path.name}: {var} -> {exc}")

    if apply and edits:
        out = C.replace_spans(buf, edits)
        assert C.read_header(out)["sha"] == head["sha"], "hash must survive"
        path.write_bytes(out)
    return len(edits), notes


def run(apply: bool) -> int:
    if apply:
        qa()
    t = load_tables()
    bins = sorted(CACHE.glob("*.bin"))
    if not bins:
        sys.exit("no compiled effects yet - start the app once")
    total = 0
    problems: list[str] = []
    for p in bins:
        n, notes = patch_one(p, t, apply)
        total += n
        problems += notes
    print(f"{len(bins)} effects, {total} strings {'patched' if apply else 'translatable'}")
    for n in problems[:20]:
        print("  SKIPPED (ambiguous anchor) " + n)
    if apply:
        print("\nRestart Borderless Gaming (tray -> Exit) to see it.")
        print("Re-run this after a software update - a recompiled cache comes back in English.")
    return 0


def revert() -> int:
    n = 0
    for b in sorted(BACKUP.glob("*.bin")):
        target = CACHE / b.name
        if target.exists():
            shutil.copy2(b, target)
            n += 1
        b.unlink()
    print(f"restored {n} effects")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--deploy", action="store_true")
    ap.add_argument("--revert", action="store_true")
    a = ap.parse_args()
    return revert() if a.revert else run(a.deploy)


if __name__ == "__main__":
    raise SystemExit(main())
