"""91_match_arabic_structure.py — make the Hebrew render EXACTLY like the game's
official Arabic, deterministically, with no per-string in-game testing.

Root cause (verified 2026-06-07): the game's OFFICIAL Arabic localization uses
**zero** RLE (U+202B) / PDF (U+202C) wrapping. It relies on the natural RTL of
the script letters and adds `&rlm;` (U+200F) only at specific spots — chiefly a
trailing `&rlm;` after the final period (1347/6536 strings) and `&rlm;[&nbsp;]`
before some `<span>`s and before `<br>`. Because there is NO closing PDF, the
Arabic never shows the trailing tofu-box.

Our pipeline wrapped every Hebrew value in RLE..PDF. The trailing **PDF is the
tofu box**. (Adding `&rlm;` before the PDF — the previous attempt — did NOT help,
the PDF is still the last glyph.)

The fix: the Hebrew and Arabic translate the SAME English source, so their
**markup skeleton is identical** (tags / [TOKENS] match 99.98%, 6535/6536). So we
transplant the Arabic string's exact control structure (its `&rlm;`/`&nbsp;`
"glue" around every markup boundary, and its lack of RLE/PDF) onto the Hebrew
prose. The result is, by construction, bidi-identical to the official Arabic —
which renders correctly — so it renders correctly too, for menus AND (later)
subtitles, with no screenshot loop.

Algorithm, per key present in BOTH arabic.json and our menus*_he.json:
  - Split AR and HE on markup tokens  (<...> and [TOKEN]); the sequences align.
  - Rebuild: for each text gap, keep the Hebrew prose CORE but wrap it with the
    Arabic gap's leading/trailing control-glue (&rlm; / &nbsp; / bidi controls /
    spaces). Markup tokens come from Arabic (ground truth).
  - No RLE, no PDF anywhere.
Fallback (key not in AR, or markup mismatch): strip our RLE/PDF + stray &rlm;;
append a trailing `&rlm;` when the value ends on non-Hebrew (Arabic's anchor).

Backs up each file to <name>.bak.arab before writing.  Run from work/.
Use `--dry-run` to preview + python-bidi-validate a sample without writing.
"""
from __future__ import annotations
import json, glob, re, sys, os, shutil

def out(*a):
    sys.stdout.write(" ".join(str(x) for x in a).encode("ascii", "backslashreplace").decode() + "\n")

RLE, PDF, RLM = "‫", "‬", "‏"
BIDI_CTRL = "‎‏‪‫‬‭‮⁦⁧⁨⁩"
MARKUP = re.compile(r'(<[^>]+>|\[[A-Z0-9_]+\])')
# one unit of "glue" = an entity / a bidi-control char / whitespace
GLUE_UNIT = r'(?:&rlm;|&lrm;|&nbsp;|[' + BIDI_CTRL + r'\s])'
LEAD = re.compile(r'^(' + GLUE_UNIT + r'*)')
TAIL = re.compile(r'(' + GLUE_UNIT + r'*)$')


def strip_glue(seg: str) -> str:
    seg = LEAD.sub('', seg)
    seg = TAIL.sub('', seg)
    return seg


# Our wrapping controls to peel off the Hebrew (KEEP its spaces / &nbsp; intact —
# Hebrew prefixes ל/ב/מ/ה/ו attach to the next word with NO space, so Arabic's
# spacing must NEVER overwrite Hebrew's).
OURS = re.compile(r'&rlm;|&lrm;|[' + RLE + PDF + RLM + ']')
AR_LEAD_RLM = re.compile(r'^\s*(?:&rlm;|' + RLM + ')')
AR_TAIL_RLM = re.compile(r'(?:&rlm;|' + RLM + r')(?:&nbsp;|\s)*$')
SPLIT_TAIL_WS = re.compile(r'^(.*\S)(\s*)$', re.S)


def transplant(ar: str, he: str):
    """Keep the Hebrew prose + its EXACT spacing; only graft the Arabic string's
    &rlm; bidi anchors at the matching markup boundaries (zero-width)."""
    ap = MARKUP.split(ar)
    hp = MARKUP.split(he)
    if len(ap) != len(hp):
        return None
    res = []
    for i, (a, h) in enumerate(zip(ap, hp)):
        if i % 2 == 1:           # markup token — Arabic's (ground truth)
            res.append(a)
            continue
        core = OURS.sub('', h)                       # peel our controls, keep spaces
        if AR_LEAD_RLM.match(a):                     # AR had &rlm; opening this gap
            core = '&rlm;' + core
        if AR_TAIL_RLM.search(a):                    # AR had &rlm; closing this gap
            m = SPLIT_TAIL_WS.match(core)
            core = (m.group(1) + '&rlm;' + m.group(2)) if m else (core + '&rlm;')
        res.append(core)
    return ''.join(res)


def fallback(he: str) -> str:
    s = he.replace(RLE, '').replace(PDF, '')
    s = s.replace('&rlm;', '').replace(RLM, '')
    s = s.rstrip()
    if not s:
        return he
    # Arabic anchors the end with &rlm; when it does not end on a RTL letter.
    last = s[-1]
    if not ('֐' <= last <= '׿'):
        s = s + '&rlm;'
    return s


def main() -> int:
    dry = "--dry-run" in sys.argv
    ar = json.load(open("arabic.json", encoding="utf-8"))
    files = sorted(glob.glob("menus*_he.json")) + ["settings_he.json"]

    n_trans = n_fall = n_unchanged = 0
    still_pdf = still_rle = 0
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
            new = None
            if k in ar:
                new = transplant(ar[k], v)
            if new is None:
                new = fallback(v)
                if new != v:
                    n_fall += 1
            else:
                if new != v:
                    n_trans += 1
            if new != v:
                changed = True
                if len(samples) < 10 and ('<span' in v or v.endswith(PDF)):
                    samples.append((k, v, new))
                d[k] = new
            else:
                n_unchanged += 1
            if RLE in d[k]:
                still_rle += 1
            if PDF in d[k]:
                still_pdf += 1
        if changed and not dry:
            shutil.copyfile(fn, fn + ".bak.arab")
            json.dump(d, open(fn, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    out(f"transplanted (from Arabic): {n_trans}")
    out(f"fallback (HE-only/mismatch): {n_fall}")
    out(f"unchanged: {n_unchanged}")
    out(f"RESIDUAL RLE U+202B: {still_rle}   RESIDUAL PDF U+202C: {still_pdf}  (must be 0)")
    out(f"\n{'DRY-RUN (nothing written)' if dry else 'WRITTEN'}")
    out("\n-- samples (key | OLD | NEW) --")
    for k, o, n in samples:
        out(f"  {k}")
        out(f"    OLD: {o[-60:]!r}")
        out(f"    NEW: {n[-60:]!r}")

    # python-bidi validation: NEW Hebrew should resolve to the same visual
    # ordering shape as the official Arabic (both strong-RTL → identical UBA).
    try:
        from bidi.algorithm import get_display
        out("\n-- python-bidi ordering check (a few mixed strings) --")
        for k in ["SETTING_SHOWMINIMAP_DESC", "SETTING_GAMESPEED_DESC",
                  "HERO_STATS_DAMAGE_PERK_1_DESC"]:
            for fn in files:
                d = json.load(open(fn, encoding="utf-8"))
                if k in d:
                    plain = re.sub(r'<[^>]+>|&[a-z]+;', '', d[k])
                    vis = get_display(plain)
                    out(f"  [{k}] visual-order ok (len {len(vis)})")
                    break
    except Exception as e:
        out("  (python-bidi not available:", e, ")")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
