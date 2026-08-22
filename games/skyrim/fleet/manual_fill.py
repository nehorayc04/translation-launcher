# -*- coding: utf-8 -*-
"""Hand-fill the Skyrim book tail — the lines the fleet + the drain could not close.

⚠️ Used ONLY under an explicit user override of [[delegate-all-translation]] ("תתרגם אותם אתה").
Everything here is machinery + a STRUCTURAL GATE; the Hebrew itself is written by hand.

    python manual_fill.py list                 # what is still open
    python manual_fill.py dump <id> [out.txt]  # the exact English, to translate from
    python manual_fill.py put  <id> <he.txt>   # validate + bank (refuses on any defect)

🔑 The bank is `banks/out_zzzclaude.json` — `zzz` sorts LAST, so `pull_skyrim.sh`'s
`sorted(glob) + dict.update()` gives a hand-written line the final word over anything the
drain produces for the same id. `put` also refuses to overwrite a line the drain has since
banked, so the two can run at the same time without a race.
"""
import json, os, re, sys, glob

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
BANK = os.path.join(HERE, "banks", "out_zzzclaude.json")

# the drain's own token classes, so a hand-written line is held to the SAME contract
STRUCT = re.compile(r"\[pagebreak\]|<[^<>]{1,400}>|\{[^{}]{0,80}\}")
NIQ = re.compile(r"[֑-ׇֽֿׁׂ]")
HEB = re.compile(r"[א-ת]")
FOREIGN = re.compile(r"[Ѐ-ӿ؀-ۿ぀-ヿ一-鿿가-힯]")


def corpus():
    c = {}
    for f in glob.glob(os.path.join(HERE, "review_corpus", "*.final.jsonl")):
        for line in open(f, encoding="utf-8"):
            line = line.strip()
            if line:
                r = json.loads(line)
                c[r["id"]] = r
    return c


def banked():
    b = {}
    for f in sorted(glob.glob(os.path.join(HERE, "banks", "out_*.json"))):
        try:
            b.update(json.load(open(f, encoding="utf-8")))
        except Exception:
            pass
    return b


def excluded():
    e = set()
    for fn in ("empty.json", "noncontent.json", "oversized.json"):
        p = os.path.join(HERE, fn)
        if os.path.exists(p):
            try:
                e |= set(json.load(open(p, encoding="utf-8")))
            except Exception:
                pass
    return e


def check(he, en):
    """The reason to refuse, or '' to accept. Mirrors drain_books.why_invalid."""
    if not he.strip():
        return "empty"
    if NIQ.search(he):
        return "niqqud"
    if FOREIGN.search(he):
        return "foreign-script"
    if not HEB.search(he):
        return "no-hebrew"
    a, b = sorted(STRUCT.findall(en)), sorted(STRUCT.findall(he))
    if a != b:
        miss = [t for t in a if a.count(t) > b.count(t)]
        extra = [t for t in b if b.count(t) > a.count(t)]
        return f"token-mismatch missing={miss[:4]} extra={extra[:4]}"
    # \r\n is LOAD-BEARING in a book page: the engine lays the page out on it. This is the
    # exact check that kept rejecting the fleet, so a hand-written line must satisfy it too.
    if en.count("\n") != he.count("\n"):
        return f"newline-count {en.count(chr(10))} -> {he.count(chr(10))}"
    if en.count("\r") != he.count("\r"):
        return f"cr-count {en.count(chr(13))} -> {he.count(chr(13))}"
    return ""


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    c, b, ex = corpus(), banked(), excluded()
    left = [k for k in c if k not in b and k not in ex]

    if cmd == "list":
        print(f"open: {len(left)}")
        for k in sorted(left, key=lambda k: len(c[k]["en"])):
            en = c[k]["en"]
            print(f"  {k:34s} {len(en):6d}ch  nl={en.count(chr(10)):4d}  {en[:56]!r}")
        return 0

    if cmd == "dump":
        k = sys.argv[2]
        out = sys.argv[3] if len(sys.argv) > 3 else os.path.join(HERE, "_page.txt")
        open(out, "w", encoding="utf-8", newline="").write(c[k]["en"])
        en = c[k]["en"]
        print(f"{k}  {len(en)}ch  \\n={en.count(chr(10))}  \\r={en.count(chr(13))}  "
              f"tokens={len(STRUCT.findall(en))}")
        print("->", out)
        return 0

    if cmd == "put":
        k, src = sys.argv[2], sys.argv[3]
        if k in b:
            print(f"SKIP {k}: already banked by the fleet since the dump — not overwriting")
            return 0
        he = open(src, encoding="utf-8", newline="").read()
        why = check(he, c[k]["en"])
        if why:
            print(f"REFUSED {k}: {why}")
            return 1
        cur = {}
        if os.path.exists(BANK):
            try:
                cur = json.load(open(BANK, encoding="utf-8"))
            except Exception:
                pass
        cur[k] = he
        tmp = BANK + ".tmp"
        json.dump(cur, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
        os.replace(tmp, BANK)
        print(f"BANKED {k}  ({len(he)}ch)  bank now {len(cur)}")
        return 0

    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
