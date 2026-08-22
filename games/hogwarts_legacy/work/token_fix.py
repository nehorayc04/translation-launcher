#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""token_fix.py — restore engine tokens the fleet mangled in work/hebrew.json.

Hogwarts tokens that MUST be preserved verbatim: input-glyph bindings `{Protego}`
/`{UMGNextCreature}` (the game swaps them for a key/button icon), runtime values
`{0}`/`{PlayerName}`, and `<i>`/`<br>` tags. The fleet TRANSLATED the identifier
inside some `{...}` (`{UMGModMainMenuTabRight}` -> `{UMGלשונית...}`), which renders
as literal garbage. `[[dialogue choice]]` brackets are NOT tokens — their content
is meant to be translated — so they're excluded.

Deterministic, safe fixes:
  A. token-ONLY value (strip tokens+ws -> empty)         -> HE = EN verbatim
  B. prose with EQUAL per-bracket {..}/<..> counts        -> positionally swap EN's
     tokens back into HE (fleet kept the slot, translated the identifier)
  C. anything else (a token truly dropped/added/retyped)  -> token_requeue_keys.json

    python token_fix.py            # apply A+B, write token_requeue_keys.json
"""
import json, re, shutil, time
from pathlib import Path
from collections import Counter

HERE = Path(__file__).resolve().parent
EX = HERE.parent / "extract"
HE_PATH = HERE / "hebrew.json"

BR = {"{": re.compile(r"\{[^}]*\}"), "<": re.compile(r"<[^>]+>")}
HARD = re.compile(r"\{[^}]*\}|<[^>]+>|%[#0-9.\*\-\+ ]*[a-zA-Z]|&[a-z]+;|\[[^\]]+\]")


def strip_choice(s):
    return re.sub(r"\[\[.*?\]\]", " ", s, flags=re.S)   # [[choice]] is translatable, not a token


def toks(s):
    return Counter(HARD.findall(strip_choice(s)))


def main():
    he = json.loads(HE_PATH.read_text(encoding="utf-8"))
    me = json.loads((EX / "main_en.json").read_text(encoding="utf-8"))
    se = json.loads((EX / "sub_en.json").read_text(encoding="utf-8"))

    def en(k):
        p, b = k.split(":", 1)
        return (me if p == "MAIN" else se).get(b)

    fix_eq = fix_pos = requeue = 0
    req_keys = []
    for k, hv in list(he.items()):
        ev = en(k)
        if ev is None or toks(ev) == toks(hv):
            continue
        # A: token-only English value
        if not strip_choice(HARD.sub(" ", ev)).strip():
            he[k] = ev
            fix_eq += 1
            continue
        # B: equal per-bracket counts -> positional swap of {..} and <..>
        ok = True
        new = hv
        for br, rx in BR.items():
            e_list = rx.findall(strip_choice(ev))
            h_list = rx.findall(strip_choice(new))
            if len(e_list) != len(h_list):
                ok = len(e_list) == 0 and len(h_list) == 0
                if len(e_list) != len(h_list):
                    ok = False
                    break
            it = iter(e_list)
            # replace inside prose only (choices are stripped from matching but present in text)
            def repl(m, it=it):
                try:
                    return next(it)
                except StopIteration:
                    return m.group(0)
            # swap only the tokens that appear OUTSIDE [[..]] choices
            parts = re.split(r"(\[\[.*?\]\])", new, flags=re.S)
            for i in range(0, len(parts), 2):
                parts[i] = rx.sub(repl, parts[i])
            new = "".join(parts)
        if ok and toks(en(k)) == toks(new):
            he[k] = new
            fix_pos += 1
        else:
            requeue += 1
            req_keys.append(k)

    print(f"token fixes: A(token-only=HE:=EN) {fix_eq} | B(positional) {fix_pos} | "
          f"C(re-queue) {requeue}")
    if fix_eq or fix_pos:
        bak = HE_PATH.with_suffix(f".json.bak.token.{time.strftime('%Y%m%d_%H%M%S')}")
        shutil.copy2(HE_PATH, bak)
        HE_PATH.write_text(json.dumps(he, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"applied {fix_eq + fix_pos} into hebrew.json (backup {bak.name})")
    (HERE / "token_requeue_keys.json").write_text(
        json.dumps(sorted(req_keys), ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote token_requeue_keys.json ({len(req_keys)})")


if __name__ == "__main__":
    main()
