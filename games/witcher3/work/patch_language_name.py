# -*- coding: utf-8 -*-
"""Rename the language-selector entry the Hebrew mod hijacks: "Arabic" -> "Hebrew" / "עברית".

The mod ships Hebrew inside the Arabic text slot, so the in-game Options > Language > Text dropdown
lists it as "Arabic" — in EVERY language. A player sitting in the English (or German, or Polish…)
UI who wants Hebrew has no way to know that "Arabic" is the Hebrew option.

str_id **1084972** is that language name. This writes:
  * every OTHER language file  -> the Latin word "Hebrew"  (discoverable from any UI language,
    same trick the CP2077 mod uses — a Latin label is readable in every locale/script)
  * ar.w3strings               -> "עברית"  (handled by the main build via hebrew.json)

Backups: <lang>.w3strings.langname_backup. Revert with --revert. GAME MUST BE CLOSED.
"""
import os, sys, glob, shutil, json
import w3strings as W
import w3strings_patch as WP

GAME = os.environ.get("W3_GAME", r"D:\Games\The Witcher 3 - Complete Edition")
HERE = os.path.dirname(os.path.abspath(__file__))
HEB_JSON = os.path.join(HERE, "..", "fleet", "hebrew.json")
LANG_ID = 1084972
LATIN = "Hebrew"
SUFFIX = ".langname_backup"


def lang_files():
    """every content0 <lang>.w3strings EXCEPT the Arabic slot (that one is the mod itself)."""
    out = []
    for f in glob.glob(os.path.join(GAME, "content", "content0", "*.w3strings")):
        base = os.path.basename(f)
        if base == "ar.w3strings":
            continue
        out.append(f)
    return sorted(out)


def patch():
    # 1. the Arabic slot's own label -> עברית (goes through hebrew.json + build_mod.py)
    heb = json.load(open(HEB_JSON, encoding="utf-8"))
    cur = heb.get(str(LANG_ID))
    if cur != "עברית":
        heb[str(LANG_ID)] = "עברית"
        tmp = HEB_JSON + ".tmp"
        json.dump(heb, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        os.replace(tmp, HEB_JSON)
        print(f"hebrew.json[{LANG_ID}]: {cur!r} -> 'עברית'   (run build_mod.py --deploy to bake)")
    else:
        print(f"hebrew.json[{LANG_ID}] already 'עברית'")

    # 2. every other language file -> the Latin word "Hebrew"
    n = 0
    failed = []
    for f in lang_files():
        bak = f + SUFFIX
        src = bak if os.path.exists(bak) else f
        raw = open(src, "rb").read()
        try:
            d = W.decode(raw)
            hit = [e for e in d["entries"] if e["str_id"] == LANG_ID]
            if not hit:
                failed.append(f"{os.path.basename(f)} (id absent)")
                continue
            old = hit[0]["text"]
            if old == LATIN:
                print(f"  {os.path.basename(f):<14} already {LATIN!r}")
                continue
            # SURGICAL patch — never a full re-encode (that reorders the blob and bricks the file)
            rebuilt = WP.patch_string(raw, LANG_ID, LATIN)
            good, why = WP.verify(raw, rebuilt, LANG_ID, LATIN)
        except Exception as ex:
            failed.append(f"{os.path.basename(f)} ({type(ex).__name__})")
            continue
        if not good:
            # a locale that does not verify is LEFT UNTOUCHED rather than risking a broken UI
            failed.append(f"{os.path.basename(f)} ({why})")
            continue
        if not os.path.exists(bak):
            shutil.copy2(f, bak)
        open(f, "wb").write(rebuilt)
        print(f"  {os.path.basename(f):<14} {old!r} -> {LATIN!r}   (verified: only this id changed)")
        n += 1
    print(f"patched {n} language files")
    if failed:
        print(f"  (left untouched — failed verification: {', '.join(failed)})")


def revert():
    n = 0
    for f in lang_files():
        bak = f + SUFFIX
        if os.path.exists(bak):
            shutil.copy2(bak, f); os.remove(bak); n += 1
    print(f"reverted {n} language files")


if __name__ == "__main__":
    if "--revert" in sys.argv:
        revert()
    else:
        patch()
