"""Phase-6b DIALOGUE PROOF: rebuild content0 ar.w3strings from the ORIGINAL backup with BOTH the
main-menu ids AND ~240 short dialogue/objective ids overridden to VISUAL Hebrew. Lets the user start
a New Game and see whether spoken subtitles / objectives render VISUAL-correct (like the menu).

Usage:  py build_dialogue_proof.py --deploy   # backup(if needed) + overwrite content0 ar.w3strings
        py build_dialogue_proof.py --revert    # restore original
"""
import os, sys, json, shutil
import w3strings as W
from build_menu_proof import MENU, visual_line, AR, BAK, revert

HERE = os.path.dirname(os.path.abspath(__file__))
HEB_FILES = ["dialogue_batch_he.json", "opening_batch_he.json"]


def build(deploy=False):
    src = BAK if os.path.exists(BAK) else AR
    d = W.decode(open(src, "rb").read())
    assert d["keyid"] == 0
    dia = {}
    for fn in HEB_FILES:
        p = os.path.join(HERE, fn)
        if os.path.exists(p):
            dia.update({int(k): v for k, v in json.load(open(p, encoding="utf-8")).items()})
    present = {e["str_id"] for e in d["entries"]}
    n_menu = n_dia = 0
    for e in d["entries"]:
        if e["str_id"] in MENU:
            e["text"] = visual_line(MENU[e["str_id"]]); n_menu += 1
        elif e["str_id"] in dia:
            e["text"] = visual_line(dia[e["str_id"]]); n_dia += 1
    hit = sum(1 for k in dia if k in present)
    print(f"menu overrides: {n_menu}   dialogue overrides: {n_dia}/{len(dia)} (in content0: {hit})")
    for k in list(dia)[:8]:
        if k in present:
            print(f"  {k:>9}  {dia[k]!r} -> visual {visual_line(dia[k])!r}")

    rebuilt = W.encode(d["entries"], d["block2"], version=d["version"])
    d2 = W.decode(rebuilt)
    m2 = {e["str_id"]: e["text"] for e in d2["entries"]}
    ok = all(m2.get(k) == visual_line(v) for k, v in dia.items() if k in present)
    print(f"re-decode check: dialogue overrides intact = {ok}  (total {len(d2['entries'])})")

    if deploy:
        if not os.path.exists(BAK):
            shutil.copy2(AR, BAK); print(f"backed up -> {BAK}")
        open(AR, "wb").write(rebuilt)
        print(f"DEPLOYED menu+dialogue proof -> {AR} ({len(rebuilt):,} bytes)")
        print("Start a NEW GAME (Text Language=Arabic). Watch the opening/first conversations for Hebrew subtitles.")
    else:
        print("(dry-run) re-run with --deploy")


if __name__ == "__main__":
    if "--revert" in sys.argv:
        revert()
    else:
        build(deploy="--deploy" in sys.argv)
