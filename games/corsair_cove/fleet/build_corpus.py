"""Corsair Cove -> fleet corpus.json (New-Era, full 6-language panel).

The corpus a worker reads. One entry per translatable line, ordered by VISIBILITY (UI/menus
first, then recorded dialogue) so a partial run always covers what a player sees first.

WHY THE PANEL IS UNUSUALLY WIDE HERE
    Corsair Cove ships 11 other cultures at 100.0% key parity, so every reference language is
    FREE. The corpus is also small (12,778 lines over 9 streams = ~1,420 each), which means the
    extra prompt tokens cost minutes, not days -- so we send the WHOLE useful panel rather than
    the thin one a 200k-line game has to settle for. Roles (universal/NEW_ERA_LANGUAGE_ROLES.md):
        ru, pl  -> speaker AND addressee gender + NUMBER (past tense / imperative)
        de      -> register (Sie/du), and the length budget: if German fits, Hebrew fits
        fr, es, it -> referent gender agreement

WHY THE GENDER FIELD IS NARROW ON PURPOSE
    The dev kit's `AddresseeGender` column is mostly `variable` (1,014 rows). Measured, that does
    NOT mean "the player, unknown" -- it means the addressee is a GROUP written as a name
    ("Guards", "Captains"), and ru/pl resolve it with a plural imperative
    (`Остановите их!` / `Płyńcie, szubrawcy!`). So `ag` carries ONLY the hard male/female/plural
    values (128 rows) that the guard can verify, and everything else is read off the panel by the
    model. A guess outside a closed set manufactures confident garbage
    ([[gender-hint-needs-closed-set]]).

    python build_corpus.py            write corpus.json
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
GAME = os.path.dirname(HERE)
SRC = os.path.join(GAME, "extract", "context_source.json")
OUT = os.path.join(HERE, "corpus.json")

PANEL = ("ru", "pl", "de", "fr", "es", "it")

# Same filter the /translate pool uses, so the fleet and the public pool cover the SAME set and
# an approved community line and a fleet line are interchangeable at build time.
TOKEN = re.compile(r"<[^<>]{1,80}>|\{[^{}]{0,80}\}|&[a-zA-Z#0-9]{1,10};|[\d\W_]+")
DEV_KEYS = {"DummyTable|DummyKey"}

# the dev kit's gender column, restricted to values a guard can actually verify
HARD_GENDER = {"male": "m", "female": "f", "plural": "pl"}


def has_word(en: str) -> bool:
    return bool(re.search(r"[A-Za-z]{2,}", TOKEN.sub(" ", en or "")))


def main() -> int:
    d = json.load(open(SRC, encoding="utf-8"))
    ui, subs, dropped = [], [], 0
    for key, v in d.items():
        en = (v.get("en") or "").strip()
        if key in DEV_KEYS or not en or not has_word(en):
            dropped += 1
            continue
        refs = v.get("refs") or {}
        row = {"en": en, "sec": "subs" if v.get("vo") else "ui"}
        if v.get("context"):
            row["ctx"] = str(v["context"]).strip()[:160]
        if v.get("speaker"):
            row["sp"] = str(v["speaker"]).strip()
        if v.get("addressee"):
            row["ad"] = str(v["addressee"]).strip()
        ag = HARD_GENDER.get((v.get("addressee_gender") or "").strip().lower(), "")
        sg = HARD_GENDER.get((v.get("speaker_gender") or "").strip().lower(), "")
        if ag:
            row["ag"] = ag
        if sg and sg != "pl":
            row["sg"] = sg
        for L in PANEL:
            t = (refs.get(L) or "").strip()
            if t:
                row[L] = t
        (subs if row["sec"] == "subs" else ui).append((key, row))

    corpus = {}
    for k, row in ui + subs:                 # visibility order: UI before dialogue
        corpus[k] = row
    tmp = OUT + ".tmp"
    json.dump(corpus, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(tmp, OUT)

    ng = sum(1 for v in corpus.values() if v.get("ag"))
    nsg = sum(1 for v in corpus.values() if v.get("sg"))
    nctx = sum(1 for v in corpus.values() if v.get("ctx"))
    full = sum(1 for v in corpus.values() if all(v.get(L) for L in PANEL))
    print(f"  corpus.json: {len(corpus):,} lines  (dropped {dropped} token-only/dev)")
    print(f"    ui {len(ui):,} -> subs {len(subs):,}   (visibility order)")
    print(f"    context on {nctx:,} · addressee-gender {ng:,} · speaker-gender {nsg:,}")
    print(f"    full {len(PANEL)}-language panel on {full:,} lines "
          f"({100.0 * full / max(1, len(corpus)):.1f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
