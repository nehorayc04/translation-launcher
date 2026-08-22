"""95_fix_percent_and_punct.py — two residual render fixes + a structural audit.

1. `%%` → `%`  : the engine does NOT collapse the printf-style double percent in
   these display strings, so "25%%"/"110%%" show literally. Single % is correct.

2. Anchor trailing punctuation: a string ending in . ! ? … : ; (optionally after a
   closing tag) needs a trailing `&rlm;` so the final punctuation pins to the LEFT
   (RTL end) under the LTR container base — otherwise it flips to the right. The
   Arabic skeleton only anchored ~1347 strings; 287 punctuation-enders (errors,
   fail texts, subtitle previews like "…בדרך!", and `</span>.`-ending perks) were
   left unanchored. The font now renders `&rlm;` invisibly (work/94), so anchoring
   them all is safe and uniform.

Then prints a read-only audit of other structural defects so we can eyeball that
nothing else is off.  Run from work/ BEFORE the 10→15→80 rebuild.
"""
import json, glob, re, sys, os

def out(*a):
    sys.stdout.write(" ".join(str(x) for x in a).encode("ascii", "backslashreplace").decode() + "\n")

RLM = "‏"
PUNC = set(".!?…:;")
TRAIL_TAGS = re.compile(r'(?:<[^>]+>)+$')

def needs_anchor(v: str) -> bool:
    c = v.rstrip()
    if c.endswith("&rlm;") or c.endswith(RLM):
        return False
    cc = TRAIL_TAGS.sub('', c).rstrip()
    return bool(cc) and cc[-1] in PUNC

def main() -> int:
    n_pct = n_anchor = 0
    files = sorted(glob.glob("menus*_he.json")) + ["settings_he.json"]
    for fn in files:
        if not os.path.exists(fn):
            continue
        d = json.load(open(fn, encoding="utf-8"))
        if not isinstance(d, dict):
            continue
        changed = False
        for k, v in list(d.items()):
            if not isinstance(v, str):
                continue
            nv = v
            if "%%" in nv:
                nv = nv.replace("%%", "%"); n_pct += 1
            if needs_anchor(nv):
                nv = nv.rstrip() + "&rlm;"; n_anchor += 1
            if nv != v:
                d[k] = nv; changed = True
        if changed:
            json.dump(d, open(fn, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    out(f"'%%' -> '%' on {n_pct} strings")
    out(f"trailing &rlm; anchor added to {n_anchor} punctuation-ending strings")

    # ---- read-only audit of anything else structurally suspicious ----
    he = {}
    for fn in files:
        he.update(json.load(open(fn, encoding="utf-8")))
    HEB = re.compile(r'[֐-׿]')
    FOREIGN = re.compile(r'[ऀ-ॿ぀-ヿ가-힣Ѐ-ӿ-Ͽ฀-๿]')  # Deva/Kana/Hangul/Cyrillic/Greek/Thai
    empty = unbal_span = unbal_brkt = foreign = dbl_pct = lone = 0
    foreign_ex = []
    for k, v in he.items():
        if not isinstance(v, str):
            continue
        if not v.strip():
            empty += 1
        if v.count("<span") != v.count("</span>"):
            unbal_span += 1
        if v.count("[") != v.count("]"):
            unbal_brkt += 1
        if "%%" in v:
            dbl_pct += 1
        m = FOREIGN.search(v)
        if m:
            foreign += 1
            if len(foreign_ex) < 6:
                foreign_ex.append((k, m.group(0)))
    out("\n--- residual audit ---")
    out(f"  empty values:        {empty}")
    out(f"  unbalanced <span>:   {unbal_span}")
    out(f"  unbalanced [ ]:      {unbal_brkt}")
    out(f"  remaining '%%':      {dbl_pct}")
    out(f"  foreign-script hits: {foreign}")
    for k, ch in foreign_ex:
        out(f"      {k}: {ch!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
