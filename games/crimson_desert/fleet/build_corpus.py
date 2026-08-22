# -*- coding: utf-8 -*-
"""Flatten the דור-3 corpus into the worker's `corpus.json`.

The דור-3 engine (`build_multilang.py` -> review_corpus/*.final.jsonl) is the SOURCE OF TRUTH:
it carries the full language panel, the deterministic gender hint and the engine tags. The
worker wants one compact dict, so this is a pure projection — no new decisions are made here.

🔑 ORDERED BY VISIBILITY, not by id: UI/menus/items first, dialogue second, and SHORT before
LONG inside each. A partial run therefore always covers what a player sees first, and the
per-provider round-robin gives every stream the same easy:hard mix.
"""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "review_corpus")
OUT = os.path.join(HERE, "corpus.json")

# The panel the worker actually prints. ru+pl carry speaker AND addressee gender (past tense /
# -ł-), de the register + the length budget, fr/es/it/pt the referent agreement. tr/ko/ja/zh
# are shipped by the game but add little for Hebrew and would only inflate every prompt.
PANEL = ("ru", "pl", "de", "fr", "es", "it", "pt")
_HINT = re.compile(r"(נמען|דובר)=(נקבה|זכר|רבים)")
_G = {"נקבה": "f", "זכר": "m", "רבים": "pl"}


def main():
    rows = []
    for kind in ("ui", "dialogue"):
        p = os.path.join(SRC, f"{kind}.final.jsonl")
        for line in open(p, encoding="utf-8"):
            line = line.strip()
            if line:
                rows.append((kind, json.loads(line)))
    print(f"read {len(rows):,} rows")

    corpus, skipped = {}, 0
    for kind, r in rows:
        en = (r.get("en") or "").strip()
        # A line with no letter left once the engine tokens are stripped is not translatable
        # work (a bare {var}, a number, punctuation). Leaving it in is what pins a stream at
        # 0 lines/min: no output can satisfy the guard, so it is re-served forever.
        if not re.search(r"[A-Za-z]", re.sub(r"\{[^{}]*\}|<[^<>]*>", " ", en)):
            skipped += 1
            continue
        v = {"en": en, "kind": kind}
        refs = r.get("refs") or {}
        for L in PANEL:
            t = (refs.get(L) or [""])[0]
            if t:
                v[L] = t
        for m in _HINT.finditer(r.get("gender_hint") or ""):
            v["ag" if m.group(1) == "נמען" else "sg"] = _G[m.group(2)]
        corpus[r["id"]] = v

    order = {"ui": 0, "dialogue": 1}
    keys = sorted(corpus, key=lambda k: (order[corpus[k]["kind"]], len(corpus[k]["en"])))
    corpus = {k: corpus[k] for k in keys}

    tmp = OUT + ".tmp"
    json.dump(corpus, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(tmp, OUT)

    ui = sum(1 for v in corpus.values() if v["kind"] == "ui")
    ag = sum(1 for v in corpus.values() if v.get("ag") or v.get("sg"))
    wide = sum(1 for v in corpus.values() if sum(1 for L in PANEL if v.get(L)) >= 5)
    print(f"corpus {len(corpus):,}  (ui {ui:,} -> dialogue {len(corpus)-ui:,})")
    print(f"  gender hint {ag:,} · >=5 panel languages {wide:,} ({wide/len(corpus)*100:.1f}%)")
    print(f"  skipped token/number-only {skipped:,}")
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
