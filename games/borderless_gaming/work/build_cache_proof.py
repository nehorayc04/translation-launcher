"""Proof that the compiled-effect CACHE is a writable Hebrew path.

Rounds 1-2 established:
  * a user-side .slang DOES override the installed one (the CRT tree showed
    ZZ-A-LATIN-ZZ and ZZ-B-UESC-ZZ in place of CRT Easymode / CRT Geom, still
    5 entries, not 9), so the user folder is a real override mechanism;
  * but Hebrew cannot survive Slang's reflection step - raw UTF-8 (with and
    without BOM) is rejected with "'3' is an invalid escapable character
    within a JSON string", and \\uXXXX is swallowed undecoded (it rendered as
    "05D705D3...").

The cache skips that stage: strings there are plain length-prefixed UTF-8, and
its validity key is the SHA-256 of the SOURCE, which we never touch.

This patches the whole "Film" category (3 effects) so ONE screenshot shows:
  * the category header in Hebrew                      -> categories translatable
  * ZZ-CACHE-OK-ZZ where "Film Grain" was              -> the cache IS the UI text
  * that effect's parameter labels + tooltips in Hebrew -> the real payload

    python work/build_cache_proof.py --deploy
    python work/build_cache_proof.py --revert
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import bg_cache as C  # noqa: E402
from build_menu_proof import real_appdata  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GAME_EFFECTS = Path(r"F:/SteamLibrary/steamapps/common/Borderless Gaming/effects")
CACHE = real_appdata() / "coreutils" / "borderless-gaming" / "cache" / "effects"

CATEGORY_HE = "סרט"
FILM = ["Film/FilmGrain.slang", "Film/VintageFilm.slang", "VHS/VHS.slang"]

MARKER = "ZZ-CACHE-OK-ZZ"
DESC_HE = "גרעין סרט פרוצדורלי עם עוצמה מותאמת לבהירות."
PARAMS_HE = {
    "grainAmount": ("עוצמת הגרעין", "עוצמת שכבת הגרעין"),
    "colorAmount": ("עוצמת הצבע", "שונות צבע לכל ערוץ בגרעין"),
    "grainSize": ("גודל הגרעין", "גודל גרגרי הגרעין"),
    "lumAmount": ("השפעת הבהירות", "עד כמה בהירות התמונה משפיעה על הגרעין"),
    "colored": ("רעש צבעוני", "השתמש ברעש צבעוני במקום מונוכרום"),
}


def bin_of(rel: str) -> Path:
    return CACHE / (rel.replace("/", "_").replace(".slang", "") + ".slang.bin")


def backup_of(rel: str) -> Path:
    return bin_of(rel).with_suffix(".bin.orig")


def patch_one(rel: str, translate_all: bool) -> None:
    path = bin_of(rel)
    if not path.exists():
        print(f"  SKIP (not compiled yet) {rel}")
        return
    if not backup_of(rel).exists():
        shutil.copy2(path, backup_of(rel))

    buf = backup_of(rel).read_bytes()
    head = C.read_header(buf)
    edits: list[tuple[tuple[int, int], str]] = [(head["category_span"], CATEGORY_HE)]

    if translate_all:
        edits.append((head["name_span"], MARKER))
        edits.append((head["description_span"], DESC_HE))
        src = GAME_EFFECTS / rel
        for var, label, tip in C.source_params(src):
            he = PARAMS_HE.get(var)
            if not he:
                continue
            edits.append((C.span_of(buf, var, 1, head["end"]), he[0]))
            if tip:
                edits.append((C.span_of(buf, var, 2, head["end"]), he[1]))

    path.write_bytes(C.replace_spans(buf, edits))
    after = C.read_header(path.read_bytes())
    assert after["sha"] == head["sha"], "hash must survive - it is the validity key"
    print(f"  patched {rel:26} category={after['category']!r} name={after['name']!r}")


def deploy() -> None:
    for rel in FILM:
        patch_one(rel, translate_all=(rel == "Film/FilmGrain.slang"))
    print("\nRestart Borderless Gaming (tray -> Exit), open the effects editor,")
    print("expand the Hebrew category where 'Film' used to be, and screenshot it.")


def revert() -> None:
    for rel in FILM:
        b = backup_of(rel)
        if b.exists():
            shutil.copy2(b, bin_of(rel))
            b.unlink()
            print(f"restored {bin_of(rel).name}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--deploy", action="store_true")
    ap.add_argument("--revert", action="store_true")
    a = ap.parse_args()
    if a.revert:
        revert()
    elif a.deploy:
        deploy()
    else:
        for rel in FILM:
            p = bin_of(rel)
            print(f"{rel:26} cache={p.exists()}  patched={backup_of(rel).exists()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
