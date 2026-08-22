"""Phase-6 MENU PROOF (v2, VISUAL): rebuild content0 ar.w3strings with the main-menu ids overridden
to Hebrew stored in VISUAL order (pre-reversed per line — the menu surface is NON-BIDI for Hebrew;
proof v1 showed logical+RLO renders reversed). Everything else = original Arabic. Backs up, then writes.

Usage:  py build_menu_proof.py            # dry-run (writes a side file, shows visual output)
        py build_menu_proof.py --deploy   # backup + overwrite content0 ar.w3strings
        py build_menu_proof.py --revert    # restore from backup
"""
import os, sys, shutil
import w3strings as W


def is_heb(ch):
    return "֐" <= ch <= "׿"


def visual_line(s):
    """Pre-reverse for a NON-BIDI renderer: reverse each Hebrew run, keep space/Latin/digit/symbol
    runs forward, flip the run order — per physical line. (WD2/Anno/GTA `visual()` pattern.)"""
    out = []
    for line in s.split("\n"):
        runs, cur, cat = [], "", None
        for ch in line:
            c = "h" if is_heb(ch) else ("s" if ch == " " else "o")
            if cur and c == cat:
                cur += ch
            else:
                if cur:
                    runs.append((cat, cur))
                cur, cat = ch, c
        if cur:
            runs.append((cat, cur))
        out.append("".join((t[::-1] if k == "h" else t) for k, t in reversed(runs)))
    return "\n".join(out)


GAME = r"D:\Games\The Witcher 3 - Complete Edition"
AR = os.path.join(GAME, "content", "content0", "ar.w3strings")
BAK = AR + ".he_backup"
HERE = os.path.dirname(os.path.abspath(__file__))

# str_id -> LOGICAL Hebrew (all candidate ids per visible main-menu item — overriding the superset
# guarantees we hit whichever id the menu actually uses). VISUAL is applied at build time.
MENU = {
    # Continue
    1065946: "המשך", 1083486: "המשך",
    # New Game
    401378: "משחק חדש", 1065947: "משחק חדש", 1083488: "משחק חדש",
    # Load Game
    1066020: "טעינת משחק", 1221899: "טעינת משחק",
    # Options
    1066021: "אפשרויות",
    # My Rewards / Extras
    1223224: "התגמולים שלי", 1066022: "תוספות",
    # Credits
    1066066: "קרדיטים",
    # Exit / Quit
    401380: "יציאה", 1066024: "יציאה",
    # Options sub-screen (visible if the user opens Options)
    1084788: "משחקיות", 1088178: "וידאו", 1066038: "שמע",
    1227809: "בקרות", 1086759: "רמת קושי", 1066026: "חזרה",
}


def revert():
    if os.path.exists(BAK):
        shutil.copy2(BAK, AR)
        print(f"reverted: restored {AR} from backup")
    else:
        print("no backup found — nothing to revert")


def build(deploy=False):
    # decode the ORIGINAL (use backup if we already deployed once, so we never double-apply)
    src = BAK if os.path.exists(BAK) else AR
    d = W.decode(open(src, "rb").read())
    assert d["keyid"] == 0, "content0 ar is not cleartext?!"
    present = {e["str_id"] for e in d["entries"]}
    applied = []
    for e in d["entries"]:
        if e["str_id"] in MENU:
            he = MENU[e["str_id"]]
            e["text"] = visual_line(he)            # VISUAL (pre-reversed), NO RLO
            applied.append((e["str_id"], he, e["text"]))
    missing = [(sid, MENU[sid]) for sid in MENU if sid not in present]
    print(f"menu ids present in content0 ar: {len(MENU)-len(missing)}/{len(MENU)}")
    for sid, he, vis in applied:
        print(f"  {sid:>10}  logical={he!r:16} -> visual={vis!r}")
    if missing:
        print("  NOT in content0 (skipped):", missing)

    rebuilt = W.encode(d["entries"], d["block2"], version=d["version"])
    d2 = W.decode(rebuilt)
    m2 = {e["str_id"]: e["text"] for e in d2["entries"]}
    ok = all(m2.get(sid) == vis for sid, he, vis in applied)
    print(f"re-decode check: overrides intact = {ok}  (total strings {len(d2['entries'])})")

    if deploy:
        if not os.path.exists(BAK):
            shutil.copy2(AR, BAK)
            print(f"backed up original -> {BAK}")
        with open(AR, "wb") as f:
            f.write(rebuilt)
        print(f"DEPLOYED VISUAL Hebrew-menu ar.w3strings -> {AR} ({len(rebuilt):,} bytes)")
        print("Launch with Text Language = Arabic (العربية); Speech = English.")
    else:
        out = os.path.join(HERE, "content0_ar_menuproof.w3strings")
        open(out, "wb").write(rebuilt)
        print(f"(dry-run) wrote {out} — re-run with --deploy to install.")


if __name__ == "__main__":
    if "--revert" in sys.argv:
        revert()
    else:
        build(deploy="--deploy" in sys.argv)
