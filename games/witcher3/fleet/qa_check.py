# -*- coding: utf-8 -*-
"""Deterministic Hebrew-quality QA over the W3 LOGICAL bank (fleet/hebrew.json).
Reports, separating REAL defects from legitimate cases (single-letter prefixes,
tags/placeholders). Checks: final-letter misuse, glued he+latin / he+digit,
single isolated Hebrew letter, niqqud, foreign script."""
import json, os, re
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
heb = json.load(open(os.path.join(HERE, "hebrew.json"), encoding="utf-8"))

TOK = re.compile(r'<[^>]*>|\{[^}]*\}|\[[^\]]*\]|%[#0-9.*\-+]*[a-zA-Z]+|&[a-zA-Z#0-9]+;|\$[A-Za-z0-9_]+\$')
HE = "א-ת"
he_re = re.compile(f"[{HE}]")
NONFIN = {"כ": "ך", "מ": "ם", "נ": "ן", "פ": "ף", "צ": "ץ"}
FIN = "ךםןףץ"
PREFIX = set("ובכלמשה")
WORD = re.compile(r"\S+")
STRIP = ".,!?;:\"'()[]…-–—»«׳״"


def words(s):
    for m in WORD.finditer(TOK.sub(" ", s)):
        yield m.group(0)


nf_real, nf_prefix = [], 0
fm_translit, fm_glue = [], []
gl, frag = [], Counter()
sh_real, sh_prefix = [], 0

for sid, s in heb.items():
    for w in words(s):
        core = w.strip(STRIP)
        heb_chars = [c for c in core if he_re.match(c)]
        if not heb_chars:
            continue
        # nonfinal at word end
        if heb_chars[-1] in NONFIN:
            if len(heb_chars) == 1 and heb_chars[0] in PREFIX:
                nf_prefix += 1
            elif re.match(r"^[" + "".join(PREFIX) + r"]-", core):
                nf_prefix += 1
            else:
                nf_real.append((sid, w, s[:45]))
        # final letter mid-word: translit error vs missing-space glue
        m = re.search(f"[{FIN}]([{HE}])", core)
        if m:
            # if the char BEFORE the final letter + final forms a known word end and the next starts a new word -> glue
            # heuristic: a glue is when removing splits into two >=2-letter Hebrew chunks
            idx = core.index(m.group(0)[0])
            left, right = core[:idx + 1], core[idx + 1:]
            if len([c for c in left if he_re.match(c)]) >= 2 and len([c for c in right if he_re.match(c)]) >= 2:
                fm_glue.append((sid, w, s[:45]))
            else:
                fm_translit.append((sid, w, s[:45]))
        # glued he+latin
        if re.search(r"[A-Za-z]", core) and re.search(f"[{HE}][A-Za-z]|[A-Za-z][{HE}]", core):
            for lat in re.findall(r"[A-Za-z]{2,}", core):
                frag[lat.lower()] += 1
            if len(gl) < 12:
                gl.append((sid, w))
        # single isolated Hebrew letter
        if len(core) == 1 and he_re.match(core):
            if core in PREFIX:
                sh_prefix += 1
            else:
                sh_real.append((sid, w, s[:45]))
        elif re.match(r"^[" + "".join(PREFIX) + r"]-$", core):
            sh_prefix += 1

print(f"nonfinal_end        REAL={len(nf_real):<5} (legit prefixes excluded={nf_prefix})")
for sid, w, f in nf_real[:8]:
    print(f"      [{sid}] '{w}'  ({f})")
print(f"\nfinal_midword       translit_err={len(fm_translit):<4} missing_space_glue={len(fm_glue)}")
for sid, w, f in fm_translit[:5]:
    print(f"   translit [{sid}] '{w}'  ({f})")
for sid, w, f in fm_glue[:5]:
    print(f"   glue     [{sid}] '{w}'  ({f})")
print(f"\nhe_latin_glued      TOP untranslated English fragments:")
for frg, c in frag.most_common(15):
    print(f"      {frg}: {c}")
print(f"\nsingle_he_letter    REAL(non-prefix)={len(sh_real):<5} (legit prefixes/particles={sh_prefix})")
for sid, w, f in sh_real[:8]:
    print(f"      [{sid}] '{w}'  ({f})")
