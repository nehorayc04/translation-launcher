#!/usr/bin/env python3
r"""
build_ct_strings.py - extract the TLOU Part I EN translation corpus + the GENDER
SOURCE from the three `text2` loc files.

English drops gender/number, so a Hebrew translation from English guesses it. The
game itself ships professional localizations in gender-marking languages, so we
attach, to every line, the parallel **Russian** (speaker/addressee gender via past
-л/-ла) + **Spanish**/**French** (referent) text - the translator reads the ACTUAL
gender instead of guessing. Join key = SID (identical across every language file).

Dedup: many SIDs share an identical EN; we dedup GLOBALLY by EN (the agent
translates each unique string once). Measured on the real corpus: of 6,376
duplicate ENs only ~6 have any conflicting gender across their SIDs, so dedup is
gender-SAFE - the gender source is taken from a representative SID per unique EN.

A string is translatable only if a real LETTER remains after stripping every
markup tag + island token (`tlou_rtl` grammar) - pure tokens/numbers/punct skip.

Outputs (games/tlou1/):
  extract/ct_strings.json            community pool [{string_key, source_en, section, order_index}]
  extract/report.txt                 counts
  agent_handoff/to_translate.json    {md5key: en}     (unique, translatable)
  agent_handoff/gender_source.json   {md5key: {ru, es, fr, gender?}}   parallel gendered text + hint
  agent_handoff/hebrew.json          {} (agents fill; md5key -> LOGICAL Hebrew)
  agent_handoff/skip.json            [en, ...] non-translatable uniques (informational)

    python build_ct_strings.py
"""
import os
import sys
import json
import hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "universal"))
import tlou_loc                       # noqa: E402
import tlou_rtl                       # noqa: E402
import gender_oracle as go            # noqa: E402

EXTRACT = os.path.join(HERE, "..", "extract")
LANG = os.path.join(EXTRACT, "lang")
HANDOFF = os.path.join(HERE, "..", "agent_handoff")
FILES = ["eng.common", "eng.subtitles", "eng.subtitles-systemic"]
GENDER_LANGS = ["rus", "spa", "fre"]     # speaker/addressee (ru) + referent (es/fr)
_LBL = {"m": "זכר", "f": "נקבה", "pl": "רבים"}
# Hebrew categories, ordered by VISIBILITY ([[community-pool-by-category]]): the pool's
# `section` AND the handoff's batch order both use these, so the most-seen text finishes first.
CAT = {"common": "ממשק ותפריטים", "subtitles": "כתוביות עלילה",
       "subtitles-systemic": "דיבורי רקע"}


def is_translatable(en: str) -> bool:
    if not en or not en.strip():
        return False
    stripped = tlou_rtl.TOKEN_RE.sub(" ", en).replace("\\n", " ")
    return any(c.isalpha() for c in stripped)


def key_of(en: str) -> str:
    return hashlib.md5(en.encode("utf-8")).hexdigest()[:16]


def _gender_hint(ru, es):
    """Short Hebrew hint derived from the gendered locales (best-effort)."""
    addr, spk, ref = go.ru_addressee(ru), go.ru_speaker(ru), go.es_referent(es)
    parts = []
    if addr in _LBL:
        parts.append(f"נמען={_LBL[addr]}")
    if spk in _LBL:
        parts.append(f"דובר={_LBL[spk]}")
    if ref in _LBL and ref not in (addr, spk):
        parts.append(f"רפרנט={_LBL[ref]}")
    return " · ".join(parts)


def main():
    os.makedirs(HANDOFF, exist_ok=True)
    uniq_en, gender_source, categories = {}, {}, {}
    skip = set()
    ct = []
    per_file = {}
    order = 0
    n_hint = 0

    for fname in FILES:
        section = fname.split(".", 1)[1]
        with open(os.path.join(EXTRACT, fname), "rb") as f:
            m = tlou_loc.to_map(f.read())               # {sid_hex: en}
        lang_maps = {}
        for lg in GENDER_LANGS:
            lp = os.path.join(LANG, f"{lg}.{section}")
            lang_maps[lg] = tlou_loc.to_map(open(lp, "rb").read()) if os.path.isfile(lp) else {}
        n_tr = 0
        for sid, en in m.items():
            if is_translatable(en):
                k = key_of(en)
                if k not in uniq_en:
                    uniq_en[k] = en
                    cat = CAT.get(section, section)
                    categories[k] = cat
                    ct.append({"string_key": k, "source_en": en,
                               "section": cat, "order_index": order})
                    order += 1
                    ru = lang_maps["rus"].get(sid, "")
                    es = lang_maps["spa"].get(sid, "")
                    fr = lang_maps["fre"].get(sid, "")
                    gsrc = {"ru": ru, "es": es, "fr": fr}
                    hint = _gender_hint(ru, es)
                    if hint:
                        gsrc["gender"] = hint
                        n_hint += 1
                    gender_source[k] = gsrc
                n_tr += 1
            else:
                skip.add(en)
        per_file[fname] = {"records": len(m), "translatable_records": n_tr}

    skip = sorted(k for k in skip if k.strip())

    def dump(name, obj, **kw):
        with open(os.path.join(HANDOFF, name), "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, **kw)

    with open(os.path.join(EXTRACT, "ct_strings.json"), "w", encoding="utf-8") as f:
        json.dump(ct, f, ensure_ascii=False)
    dump("to_translate.json", uniq_en, indent=0)
    dump("gender_source.json", gender_source)
    dump("categories.json", categories)     # {key: Hebrew category} -> get_batch visibility order
    dump("skip.json", skip)
    hp = os.path.join(HANDOFF, "hebrew.json")
    if not os.path.isfile(hp):
        dump("hebrew.json", {})

    lines = ["TLOU Part I - EN corpus + gender source", "=" * 40]
    tot_rec = tot_tr = 0
    for fn in FILES:
        d = per_file[fn]
        tot_rec += d["records"]; tot_tr += d["translatable_records"]
        lines.append(f"{fn:26} records={d['records']:>6}  translatable={d['translatable_records']:>6}")
    lines.append("-" * 40)
    lines.append(f"total records                {tot_rec:>6}")
    lines.append(f"total translatable records   {tot_tr:>6}")
    lines.append(f"UNIQUE translatable (dedup by EN): {len(uniq_en)}")
    lines.append(f"  with a gender hint from RU/ES:   {n_hint}")
    lines.append(f"non-translatable uniques:          {len(skip)}")
    rep = "\n".join(lines)
    with open(os.path.join(EXTRACT, "report.txt"), "w", encoding="utf-8") as f:
        f.write(rep + "\n")
    print(rep)
    print(f"\n-> extract/ct_strings.json ({len(ct)} rows)"
          f"\n-> agent_handoff/to_translate.json ({len(uniq_en)} unique)"
          f"\n-> agent_handoff/gender_source.json ({len(gender_source)} with RU/ES/FR)")


if __name__ == "__main__":
    main()
