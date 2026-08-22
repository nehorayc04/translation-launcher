"""97_fix_boxglyphs_and_numspans.py — clear the remaining tofu-box glyphs and the
reversed number-in-span values, all found by the deep font-coverage + Arabic diff.

A. Box glyphs our Heebo font cannot draw (the font-coverage scan flagged them):
   - U+061F ARABIC QUESTION MARK (؟) → "?"     (PAUSE_GEN_UNKNOWN "؟؟؟" = "???")
   - U+060C ARABIC COMMA (،)        → ","
   - U+FFFC OBJECT REPLACEMENT CHAR → ""        (a stray embed placeholder)

B. Number-only <span> content reversed vs Arabic: a span whose content is purely
   digits/%/./space renders with the "%" on the wrong side under our pipeline
   (e.g. "25%" shows as "%25"). The shipped Arabic stores the same unit in the
   order that renders correctly ("%%25", ".1 ", "%%110"). Since the content is
   language-neutral, copy the Arabic span's exact content. (10_build's
   format-aware percent pass then turns the display "%%" into a single "%".)
   Catches the damage perks, gadget capacities, music acts, suit-mod %, etc.

NOTE: the foreign-language NATIVE names (中文 / ΕΛΛΗΝΙΚΑ / 日本語 …) in the language
list also box in Heebo, but they are legitimately each language's own name — left
as-is (the Hebrew gloss in parentheses is readable).

Run from work/ BEFORE the 10→15→80 rebuild.
"""
import json, glob, re, sys, os

def out(*a):
    sys.stdout.write(" ".join(str(x) for x in a).encode("ascii", "backslashreplace").decode() + "\n")

BOX = {"؟": "?", "،": ",", "￼": ""}
SPAN = re.compile(r'(<span[^>]*>)([^<]*)(</span>)')
NUM_ONLY = re.compile(r'^[\d%.\s]+$')

def fix_numspan(hv: str, av: str) -> str:
    hm = list(SPAN.finditer(hv)); am = list(SPAN.finditer(av))
    if not hm or not am:
        return hv
    h, a = hm[-1], am[-1]
    ac = a.group(2)
    if ac.strip() and NUM_ONLY.match(ac) and ac != h.group(2):
        return hv[:h.start(2)] + ac + hv[h.end(2):]
    return hv

def main() -> int:
    ar = json.load(open("arabic.json", encoding="utf-8"))
    files = sorted(glob.glob("menus*_he.json")) + ["settings_he.json"]
    n_box = n_num = 0
    samples = []
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
            if any(c in nv for c in BOX):
                for c, r in BOX.items():
                    nv = nv.replace(c, r)
                n_box += 1
            if "<span" in nv and k in ar:
                nv2 = fix_numspan(nv, ar[k])
                if nv2 != nv:
                    nv = nv2; n_num += 1
                    if len(samples) < 10:
                        samples.append((k, v[-45:], nv[-45:]))
            if nv != v:
                d[k] = nv; changed = True
        if changed:
            json.dump(d, open(fn, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    out(f"box-glyph strings fixed (؟ ، U+FFFC): {n_box}")
    out(f"number-span content matched to Arabic: {n_num}")
    for k, o, n in samples:
        out(f"  {k}\n    OLD: {o!r}\n    NEW: {n!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
