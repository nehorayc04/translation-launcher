#!/usr/bin/env python3
r"""
build_ct_strings.py - extract the TLOU Part II Remastered EN corpus + the GENDER
SOURCE from the three `text2` loc files, and emit the community `/translate`
upload file directly.

English drops gender/number, so a Hebrew translation from English guesses it. The
game itself ships professional localizations in gender-marking languages (it has NO
Arabic slot), so we attach to every unique line the parallel **Russian** (speaker/
addressee gender via past -л/-ла, short adjectives) + **Spanish**/**French**
(referent -o/-a) text - the translator reads the ACTUAL gender instead of guessing.
Join key = SID (identical across every language file). Builds NO gender debt.

Dedup: many SIDs share an identical EN; we dedup GLOBALLY by EN (each unique string
translated once). md5(EN)[:16] is the string_key (same key the build/export use).

A string is translatable only if a real LETTER remains after stripping every markup
tag + island token (`tlou_rtl` grammar) - pure tokens/numbers/punct skip.

Outputs (games/tlou2/):
  extract/ct_upload.json    the /translate upload  [{string_key, source_en, current_he:"",
                            section:<Hebrew category>, order_index, context:<gender hint>}]
  extract/ct_strings.json   raw pool  [{string_key, source_en, section, order_index}]
  extract/report.txt        counts
  agent_handoff/to_translate.json    {md5key: en}   (unique, translatable)
  agent_handoff/gender_source.json   {md5key: {ru, es, fr, gender?}}
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
# raw section -> Hebrew community category (what shows on the /translate site)
CATEGORY = {
    "common": "ממשק ותפריטים",
    "subtitles": "כתוביות עלילה",
    "subtitles-systemic": "דיבורי רקע",
}


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
    ct = []          # raw pool
    upload = []      # normalized /translate upload
    per_file = {}
    order = 0
    n_hint = 0

    for fname in FILES:
        section = fname.split(".", 1)[1]
        cat = CATEGORY[section]
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
                    ru = lang_maps["rus"].get(sid, "")
                    es = lang_maps["spa"].get(sid, "")
                    fr = lang_maps["fre"].get(sid, "")
                    gsrc = {"ru": ru, "es": es, "fr": fr}
                    hint = _gender_hint(ru, es)
                    if hint:
                        gsrc["gender"] = hint
                        n_hint += 1
                    gender_source[k] = gsrc
                    categories[k] = cat
                    ct.append({"string_key": k, "source_en": en,
                               "section": section, "order_index": order})
                    upload.append({"string_key": k, "source_en": en, "current_he": "",
                                   "section": cat, "order_index": order,
                                   "context": (f"מגדר: {hint}" if hint else "")})
                    order += 1
                n_tr += 1
            else:
                skip.add(en)
        per_file[fname] = {"records": len(m), "translatable_records": n_tr}

    skip = sorted(k for k in skip if k.strip())

    def dump(path, obj, **kw):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, **kw)

    dump(os.path.join(EXTRACT, "ct_upload.json"), upload)
    dump(os.path.join(EXTRACT, "ct_strings.json"), ct)
    dump(os.path.join(HANDOFF, "to_translate.json"), uniq_en, indent=0)
    dump(os.path.join(HANDOFF, "gender_source.json"), gender_source)
    dump(os.path.join(HANDOFF, "categories.json"), categories)
    dump(os.path.join(HANDOFF, "skip.json"), skip)
    hp = os.path.join(HANDOFF, "hebrew.json")
    if not os.path.isfile(hp):
        dump(hp, {})

    lines = ["TLOU Part II Remastered - EN corpus + gender source", "=" * 44]
    tot_rec = tot_tr = 0
    for fn in FILES:
        d = per_file[fn]
        tot_rec += d["records"]; tot_tr += d["translatable_records"]
        lines.append(f"{fn:26} records={d['records']:>6}  translatable={d['translatable_records']:>6}")
    lines.append("-" * 44)
    lines.append(f"total records                {tot_rec:>6}")
    lines.append(f"total translatable records   {tot_tr:>6}")
    lines.append(f"UNIQUE translatable (dedup by EN): {len(uniq_en)}")
    lines.append(f"  with a gender hint from RU/ES:   {n_hint}")
    lines.append(f"non-translatable uniques:          {len(skip)}")
    # category breakdown of the upload
    from collections import Counter
    cats = Counter(r["section"] for r in upload)
    for c, n in cats.items():
        lines.append(f"  category {c}: {n}")
    rep = "\n".join(lines)
    with open(os.path.join(EXTRACT, "report.txt"), "w", encoding="utf-8") as f:
        f.write(rep + "\n")
    print(rep)
    print(f"\n-> extract/ct_upload.json ({len(upload)} rows, the /translate upload)"
          f"\n-> extract/ct_strings.json ({len(ct)} rows)"
          f"\n-> agent_handoff/to_translate.json ({len(uniq_en)} unique)"
          f"\n-> agent_handoff/gender_source.json ({len(gender_source)}; {n_hint} with a gender hint)")


if __name__ == "__main__":
    main()
