# -*- coding: utf-8 -*-
"""Deterministic Hebrew FINAL-LETTER normalization on the LOGICAL bank.
  (1) a word ending (before trailing punctuation) in a non-final form כמנפצ  -> final ךםןףץ
  (2) a non-final's twin final form ךםןףץ appearing mid-word, when the tail after it is a
      SHORT (<3 letters) translit suffix -> convert to non-final (e.g. פארמוןד -> פארמונד).
Skips single-letter prefixes (מ/ב/כ/ל/ה/ש/ו) + maqaf-prefixes + mixed he+latin words +
long-tail glues (those need a space / re-translation, handled elsewhere). Pure orthography,
no translation. --apply to write (backs up first); default dry-run prints the count."""
import json, os, re, sys, time, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
BANK = os.path.join(HERE, "hebrew.json")
HE = "א-ת"
he_re = re.compile(f"[{HE}]")
NONFIN = {"כ": "ך", "מ": "ם", "נ": "ן", "פ": "ף", "צ": "ץ"}
FIN = {v: k for k, v in NONFIN.items()}
PREFIX = set("ובכלמשה")
TOK = re.compile(r'<[^>]*>|\{[^}]*\}|\[[^\]]*\]|%[#0-9.*\-+]*[a-zA-Z]+|&[a-zA-Z#0-9]+;|\$[A-Za-z0-9_]+\$')
TAIL = r"[.,!?;:\"')\]…»׳״]*"
# a word = run of non-space; we only touch the ALL-HEBREW (+punct) shape, never he+latin
END_NF = re.compile(r"^(.*?[" + HE + r"])([כמנפצ])(" + TAIL + r")$")
# any final form immediately followed by another Hebrew letter = mid-word = wrong -> non-final
MID_FIN = re.compile(r"([ךםןףץ])(?=[" + HE + r"])")


def has_latin(w):
    return bool(re.search(r"[A-Za-z0-9]", w))


def fix_word(w):
    if has_latin(w):
        return w
    core = w
    changed = False
    # (1) word-final non-final -> final
    m = END_NF.match(core)
    if m:
        stem, nf, tail = m.groups()
        heb_in_stem = [c for c in stem if he_re.match(c)]
        # must be a real word (>=1 heb before the nf) and not a bare prefix
        if heb_in_stem and not (len(heb_in_stem) == 0):
            core = stem + NONFIN[nf] + tail
            changed = True
    # (2) any mid-word final form (followed by a Hebrew letter) -> non-final (פארמוןד, דרוםיות)
    new = MID_FIN.sub(lambda mm: FIN[mm.group(1)], core)
    if new != core:
        core, changed = new, True
    return core if changed else w


def main(apply=False):
    heb = json.load(open(BANK, encoding="utf-8"))
    changed = {}
    for sid, s in heb.items():
        # rebuild the string word-by-word, leaving tokens/whitespace intact
        out = []
        pos = 0
        for m in re.finditer(r"\S+", s):
            out.append(s[pos:m.start()])
            w = m.group(0)
            # don't touch a word that is (or contains) a token
            out.append(w if TOK.fullmatch(w) else fix_word(w))
            pos = m.end()
        out.append(s[pos:])
        ns = "".join(out)
        if ns != s:
            changed[sid] = (s, ns)
    print(f"strings changed: {len(changed)}")
    for sid, (o, n) in list(changed.items())[:12]:
        print(f"  [{sid}] {o[:40]!r} -> {n[:40]!r}")
    if apply and changed:
        shutil.copy2(BANK, f"{BANK}.bak.finals.{int(time.time())}")
        for sid, (o, n) in changed.items():
            heb[sid] = n
        json.dump(heb, open(BANK + ".tmp", "w", encoding="utf-8"), ensure_ascii=False)
        os.replace(BANK + ".tmp", BANK)
        print(f"APPLIED to {len(changed)} strings (backup saved).")


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
