"""96_fix_span_punct_numbers.py — match the official Arabic for the two cases
where content lives INSIDE a <span> at the sentence end and my generic trailing
`&rlm;` (work/95) was the wrong tool.

Confirmed against arabic.json:

A. Subtitle/caption EXAMPLE ("…אני בדרך!"): the dialogue text sits inside a
   <span class='subtitleColor'>. The container's base is LTR, so the trailing "!"
   flips to the right. Arabic fixes it by writing the punctuation at the LOGICAL
   START of the span — `<span>!أنا في طريقي</span>` — so under LTR base it lands at
   the visual-left (sentence end). We do the same: move the trailing run of
   . ! ? … to the front of the LAST span's content, and drop the stray trailing
   `&rlm;`.

B. Opacity descs ("…של 25%."): Arabic puts the whole number unit inside the span
   WITH the period and a trailing space — `<span>.%25 </span>` — and nothing after
   </span>. Our `<span>25%</span>.&rlm;` loses the space before the number and
   leaves the period dangling. Fix = keep the Hebrew prose up to the <span>, then
   splice the Arabic's exact `<span>…</span>` tail (same number, language-neutral).

Run from work/ BEFORE the 10→15→80 rebuild.
"""
import json, glob, re, sys, os

def out(*a):
    sys.stdout.write(" ".join(str(x) for x in a).encode("ascii", "backslashreplace").decode() + "\n")

RLM = "‏"
PUNCT = "!?.…"
# move a trailing punctuation run that sits just before the LAST </span> to the
# front of that span's content.
LAST_SPAN_PUNCT = re.compile(r'(<span[^>]*>)([^<]*?)([' + PUNCT + r']+)(</span>)(\s*)$')

def main() -> int:
    ar = json.load(open("arabic.json", encoding="utf-8"))
    files = sorted(glob.glob("menus*_he.json")) + ["settings_he.json"]

    n_example = n_opacity = 0
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

            # ── B. opacity number-span: splice Arabic's <span>…</span> tail ──
            if k in ar and "<span>.%" in ar[k] and "<span" in nv:
                hi = nv.find("<span")
                ai = ar[k].find("<span")
                cand = nv[:hi] + ar[k][ai:]
                if cand != nv:
                    nv = cand; n_opacity += 1

            # ── A. example: move trailing punct inside the last span to its front ──
            elif k.endswith("_EXAMPLE"):
                stripped = re.sub(r'(?:&rlm;|' + RLM + r')+(\s*)$', r'\1', nv)
                m = LAST_SPAN_PUNCT.search(stripped)
                if m:
                    nv = (stripped[:m.start()] + m.group(1) + m.group(3) +
                          m.group(2) + m.group(4) + m.group(5))
                    n_example += 1

            if nv != v:
                d[k] = nv
                changed = True
                if len(samples) < 8:
                    samples.append((k, v, nv))
        if changed:
            json.dump(d, open(fn, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    out(f"opacity number-spans matched to Arabic: {n_opacity}")
    out(f"example punctuation moved to span-front: {n_example}")
    for k, o, n in samples:
        out(f"  {k}")
        out(f"    OLD: {o[-55:]!r}")
        out(f"    NEW: {n[-55:]!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
