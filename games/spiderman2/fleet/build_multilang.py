# -*- coding: utf-8 -*-
"""עידן חדש 2 — build the Spider-Man 2 REVIEW corpus with the UNIVERSAL engine.

This REPLACES the old hand-rolled `sm2_build_corpus.py` (עידן חדש 1), whose row was a flat
{en, he, ar, ru, pl, es, it, ag, num, formal}. The universal engine adds what that could not:

  * the DETERMINISTIC GENDER PARTITION — a language is stored as a [feminine, masculine] PAIR,
    so a line whose own shipped translations DIFFER between the two is flagged `gendered`
    with `split_langs`, instead of the gender being re-derived per game by a regex that has to
    be kept in lockstep across two files (the SM2 v1 builder and its worker each carried their
    OWN copy of the Arabic parser, with a "keep them identical" comment — exactly the drift
    hazard this removes).
  * det side-flags (niqqud / foreign script / dropped {brace} / leading-Latin / English run),
  * linguistic tags (axis, formality, number, imperative, homograph candidate),
  * engine tags (vars, number/name injection, line breaks, overflow risk, lore terms).

SM2 is ALREADY translated, so every row with Hebrew comes out `mode="review"` (monotonic: fix
only real errors, else return the line unchanged) and any row without Hebrew comes out
`mode="translate"` — the engine decides that per row, not per game.

⚠️ SM2 has ONE Hebrew string per id (no femaleVariant/maleVariant pair like CP2077), so the
spine passes the same value for both slots; `he_split` is then correctly False everywhere and
the gender signal comes purely from the reference panel.

Reference panel: the game's own 10 shipped locales. Roles per universal/NEW_ERA_LANGUAGE_ROLES:
ru/pl mark speaker AND addressee gender + number, es/esmx/fr/it/pt referent gender, de register,
ar the Semitic near-match (SM2's Arabic is EGYPTIAN COLLOQUIAL and unvocalized — kept in the
panel for a human/LLM to read, never parsed by a rule).

Run:  python build_multilang.py     -> fleet/review_corpus/{subtitles,dialogue}.final.jsonl
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
WORK = os.path.join(ROOT, "games", "spiderman2", "work")
EXTRACT = os.path.join(HERE, "extract")
OUT = os.path.join(HERE, "review_corpus")
sys.path.insert(0, os.path.join(ROOT, "universal"))
import multilang_review as mlr
import gender_oracle as go

# extract filename -> the engine's canonical language code
LANGS = {"en": "en", "ar": "ar", "ru": "ru", "pl": "pl", "de": "de", "fr": "fr",
         "it": "it", "es": "es", "esmx": "es-mx", "pt": "pt", "zh": "zh"}

CFG = mlr.Cfg(
    langs=("en", "ar", "ru", "pl", "de", "fr", "it", "es", "es-mx", "pt", "zh"),
    gender_langs=("ru", "pl", "es", "es-mx", "fr", "it", "pt", "ar"),
    addressee_langs=("ru", "pl", "ar"),
    speaker_langs=("ru", "pl"),
)

# A subtitle carries the engine's own timing markers; everything else is UI/dialogue. Splitting
# by the GAME's own convention (not a length heuristic) keeps the two kinds separately
# schedulable and lets the fleet do the story lines first.
def kind_of(en):
    return "subtitles" if "<ts=" in (en or "") else "dialogue"


_HINT = {"m": "נמען=זכר", "f": "נמען=נקבה", "pl": "נמען=רבים"}


def gender_hint(pk, langs):
    """The engine's `gendered` flag needs a fv/mv PAIR that differs; SM2 (like Skyrim) ships one
    string per language, so it can never fire. The gender signal therefore has to come from the
    MORPHOLOGY of the gendered locales instead — exactly what the Skyrim adapter does.

    🔴 Precision over recall, on purpose. `ar_addressee_strict` (pronouns + VOCALISED ـكَ/ـكِ +
    plural + a curated 2nd-fem verb list) — never the loose `ت…ين`, which false-fires on masdars
    and plurals; and never a colloquial `بت/هت…ي` rule, measured 482/551 WRONG on THIS corpus.
    A wrong hint actively corrupts good Hebrew; a missing one just leaves the line to the model
    reading the raw ru/pl, which every row carries anyway. [[gender-hint-needs-closed-set]]
    """
    ar = (langs.get("ar", {}).get(pk) or "")
    ru = (langs.get("ru", {}).get(pk) or "")
    g = (go.ar_addressee_strict(ar) if ar else None) or (go.ru_addressee(ru) if ru else None)
    return _HINT.get(g, "")


def main():
    langs = {}
    for fn, code in LANGS.items():
        p = os.path.join(EXTRACT, fn + ".json")
        if os.path.exists(p):
            langs[code] = json.load(open(p, encoding="utf-8"))
        else:
            print(f"  (no {fn}.json — skipping {code})")

    he = {}
    for fn in ("subtitles_he.json", "dialogue_he.json"):
        he.update(json.load(open(os.path.join(WORK, fn), encoding="utf-8")))

    en_map = langs.get("en", {})
    # only lines the mod actually ships Hebrew for are in scope for a REVIEW pass
    ids = [k for k in he if en_map.get(k, "").strip()]
    print(f"languages {len(langs)} | hebrew {len(he):,} | in scope {len(ids):,}")

    buckets = {}
    for pk in ids:
        buckets.setdefault(kind_of(en_map.get(pk, "")), []).append(pk)

    for kind, keys in sorted(buckets.items()):
        panel, spine = {}, {}
        for order, pk in enumerate(keys):
            # every language as a [feminine, masculine] PAIR. SM2 ships one string per id per
            # language, so both slots carry it; a genuine fv/mv divergence in the panel is what
            # the engine turns into the `gendered` flag.
            p = {}
            for code, m in langs.items():
                v = (m.get(pk) or "").strip()
                if v:
                    p[code] = [v, v]
            panel[pk] = p
            h = (he.get(pk) or "").strip()
            spine[pk] = (kind, order, h, h)
        st = mlr.build(kind, panel, spine, OUT, cfg=CFG)
        # attach the morphological hint as a post-pass: the engine is game-agnostic and must
        # not learn per-game oracles, so the ADAPTER owns this (same split as Skyrim).
        hints = 0
        rows = []
        with open(st["out"], encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                r = json.loads(line)
                pk = r["id"].split(":", 1)[1] if ":" in r["id"] else r["id"]
                h = gender_hint(pk, langs)
                if h:
                    r["gender_hint"] = h; hints += 1
                rows.append(r)
        with open(st["out"], "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"  {kind:<10} n={st['n']:>6,}  review={st['review']:>6,}  translate={st['translate']:>5,}  "
              f"gender_hint={hints:>5,}  vars={st['vars']:>5,}  nl={st['nl']:>5,}  ovf={st['ovf']:>5,}")
        print(f"             -> {st['out']}")


if __name__ == "__main__":
    main()
