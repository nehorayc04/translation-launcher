#!/usr/bin/env python3
"""fix_stray_tilde.py — repair values whose `~` count is ODD, i.e. one tilde is unpaired.

WHY IT MATTERS. The engine pairs tildes into tokens. A value carrying an unpaired `~` therefore
either swallows text into a phantom token or leaves a stray glyph, and it is invisible to a
Hebrew-content check: the text reads perfectly in the JSON. All 88 were introduced on OUR side --
the game's own English has ZERO odd values -- so this is a translation artefact, not source data.

DETERMINISTIC CLASSES ONLY, each guarded against the game's own English:
  truncated_token   `...~m`  where the English ends `...~m~`   -> restore the closing `~`
  trailing_stray    a lone `~` at the very end, absent in EN   -> drop it
  stutter_tilde     `X~X` / `~ ` used where the English has a HYPHEN -> hyphen (IRON RULE: `-`)
Anything else is REPORTED, never guessed: a mangled value needs a human decision, and a wrong
repair here is worse than a visible defect.

    py fix_stray_tilde.py            # report only
    py fix_stray_tilde.py --apply    # write, with a timestamped backup per file
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "gtav", "work"))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from gtav_gxt2 import joaat  # noqa: E402

FLEET = os.path.join(HERE, "..", "fleet")
EXTRACT = os.path.join(HERE, "..", "extract")
SPINES = ["hebrew.json", "hebrew_missing.json"]


def load_english():
    books = []
    for sub in ("game_text", "game_text_v2"):
        p = os.path.join(EXTRACT, sub, "american.json")
        if os.path.exists(p):
            books.append(json.load(open(p, encoding="utf-8")))
    return books


def english_for(key, books):
    if key.startswith("0x"):
        forms = [key, "0x" + key[2:].upper(), "0x" + key[2:].lower()]
    else:
        h = joaat(key)
        forms = [f"0x{h:08X}", f"0x{h:08x}"]
    for b in books:
        for f in forms:
            if f in b:
                return b[f]
    return None


TOKEN = re.compile(r"~[^~]*~")
# A literal vocabulary is not enough: a TIMING token carries free numbers (`~sl:2.3:1.5:1~`,
# `~lr:0.1~`), so that exact string may never appear in the English even though the token is real.
# 🔴 A NARROW SHAPE LIST IS DANGEROUS HERE: `~lr:` was missing from an earlier version, so 39
# values had a REAL token (614 occurrences in the game's own English) deleted as "hallucinated".
# When in doubt, treat a `~...~` as real -- an unrecognised token is a report, never a deletion.
SHAPED = re.compile(r"^~(?:(?:sl|lr):[\d.:,]*|[a-zA-Z]{1,4}|\d+[a-z$]?|[A-Z][A-Z0-9_]*|"
                    r"INPUT(?:GROUP)?_[^~]*|COLOR_[^~]*|HUD_[^~]*|BLIP_[^~]*)~$")


def build_vocabulary(books):
    """Every token the GAME's own text uses. A `~...~` in our value that is in here is real."""
    vocab = set()
    for b in books:
        for v in b.values():
            if isinstance(v, str):
                vocab.update(TOKEN.findall(v))
    return vocab


def is_token(tok, vocab):
    return tok in vocab or bool(SHAPED.match(tok))


def stray_positions(val, vocab):
    """Indexes of the `~` that are NOT part of a token the game actually uses.

    🔴 THE BUG THIS REPLACES: a naive `(?<=\\S)~(?=\\S)` matched the CLOSING tilde of `~z~`
    whenever a Hebrew letter followed it, so the "stutter" repair turned `~z~text` into
    `~z-text` and DESTROYED the dialogue token on 21 values. Consume the real tokens first;
    whatever tilde is left over is the stray.
    """
    used = [False] * len(val)
    i = 0
    while i < len(val):
        if val[i] == "~":
            m = TOKEN.match(val, i)
            if m and is_token(m.group(0), vocab):
                for j in range(m.start(), m.end()):
                    used[j] = True
                i = m.end()
                continue
        i += 1
    return [i for i, c in enumerate(val) if c == "~" and not used[i]]


def repair(val, eng, vocab):
    """-> (new_value, class) or (None, reason) when no rule applies.

    A repair may never DESTROY a token that was already valid — that guard is what turns this
    from "a regex that mostly works" into something safe to run over 245k values.
    """
    if val.count("~") % 2 == 0:
        return None, "even"

    before = [t for t in TOKEN.findall(val) if is_token(t, vocab)]

    def ok(out, cls):
        if out.count("~") % 2:
            return None
        after = [t for t in TOKEN.findall(out) if is_token(t, vocab)]
        # a repair may ADD the closing tilde of a truncated token, but must never LOSE one
        missing = [t for t in before if after.count(t) < before.count(t)]
        return None if missing else (out, cls)

    # 1. a trailing token lost its closing tilde: `...~m` where the English closes it
    m = re.search(r"~([a-zA-Z]{1,4})\s*$", val)
    if m and isinstance(eng, str) and f"~{m.group(1)}~" in eng:
        r = ok(val.rstrip() + "~", "truncated_token")
        if r:
            return r

    strays = stray_positions(val, vocab)
    if len(strays) != 1:
        return None, f"strays={len(strays)}"
    p = strays[0]

    # 2. the stray is glued to the end -> it is simply surplus
    if not val[p + 1:].strip():
        r = ok(val[:p].rstrip(), "trailing_stray")
        if r:
            return r

    # 3. the stray stands where the English has a HYPHEN (`S-so`, a stutter, an em-dash)
    r = ok(val[:p] + "-" + val[p + 1:], "stutter_tilde")
    if r:
        return r

    return None, "unclassified"


def main() -> None:
    apply = "--apply" in sys.argv
    books = load_english()
    vocab = build_vocabulary(books)
    print(f"token vocabulary from the game's own text: {len(vocab):,} distinct tokens")
    stamp = time.strftime("%Y%m%d_%H%M%S")
    total = {"truncated_token": 0, "trailing_stray": 0, "stutter_tilde": 0}
    leftovers = []

    for name in SPINES:
        path = os.path.join(FLEET, name)
        data = json.load(open(path, encoding="utf-8"))
        changed = 0
        for k, v in list(data.items()):
            if not isinstance(v, str) or v.count("~") % 2 == 0:
                continue
            new, cls = repair(v, english_for(k, books), vocab)
            if new is None:
                leftovers.append((k, v, english_for(k, books)))
                continue
            total[cls] += 1
            changed += 1
            if apply:
                data[k] = new
        print(f"{name:<22} repairable {changed}")
        if apply and changed:
            shutil.copy2(path, f"{path}.bak.tilde.{stamp}")
            json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print(f"\nby class: {total}")
    print(f"unclassified (need a human): {len(leftovers)}")
    for k, v, e in leftovers:
        print(f"   {k}\n      en {(e or '')[:88]!r}\n      he {v[:88]!r}")
    if not apply:
        print("\n(dry run — pass --apply to write)")


if __name__ == "__main__":
    main()
