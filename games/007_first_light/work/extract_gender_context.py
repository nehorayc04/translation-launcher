"""
extract_gender_context.py — pull RU/ES/FR/IT/BR(pt) alongside EN from the same LOCR/DLGE
containers `extract_corpus.py` already reads, and join them to the `ct_upload.json` string_key
(= "en:" + md5(en_text), same scheme as build_ct_pool.py's key_of()) so the fleet's gender
oracle can look a line's Hebrew-relevant gender/number up directly by string_key.

Slot map (LANGS_007 in gl_dlge.py, same order for LOCR's CLNG list):
  en=1 fr=2 it=3 de=4 es=5 ru=6 mx=7 br=8
RU = speaker/addressee gender (past tense -л/-ла). ES/FR/IT/BR = referent/addressee gender
(-o/-a). Per PIPELINE.md step 8 (gender oracle, no Arabic slot in this game).

Output: games/007_first_light/fleet/gender_context.json
  {"en:<md5>": {"ru": "...", "es": "...", "fr": "...", "it": "...", "pt": "..."}}
Only EN keys already present in ct_upload.json are kept (dedup-by-EN, same as the pool).
"""
import os
import sys
import re
import json
import hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
from gl_rpkg import RPKG
import gl_locr as L
import gl_dlge as D

GAME = r"F:\Game Lab\007 First Light"
CHUNKS = [os.path.join(GAME, "Runtime", "chunk0.rpkg"),
          os.path.join(GAME, "Runtime", "chunk1.rpkg")]
FLEET = os.path.join(HERE, "..", "fleet")

SLOT = {"fr": 2, "it": 3, "es": 5, "ru": 6, "pt": 8}   # LOCR list index (br==pt, slot 8)
DLGE_CODE = {"fr": "fr", "it": "it", "es": "es", "ru": "ru", "pt": "br"}

_META = re.compile(r"^(?://.*?\\\\)+")
_SPEAKER = re.compile(r"^//\[([^\]]*)\]\\\\")


def clean_sub(s):
    return _META.sub("", s)


def key_of(en):
    return "en:" + hashlib.md5(en.encode("utf-8")).hexdigest()


def main():
    ct = json.load(open(os.path.join(HERE, "..", "extract", "ct_upload.json"), encoding="utf-8"))
    wanted = {r["string_key"] for r in ct}
    print(f"ct_upload keys: {len(wanted):,}")

    out = {}   # string_key -> {lang: text}

    for path in CHUNKS:
        R = RPKG(path)
        for i in R.indices("LOCR"):
            r = R.resources[i]
            try:
                ver, langs = L.decode_locr(R.read(i))
            except Exception:
                continue
            en_block = langs[1] if len(langs) > 1 else None
            if not en_block:
                continue
            en_by_lh = {lh: s for lh, s in en_block}
            for lang, slot in SLOT.items():
                if slot >= len(langs) or not langs[slot]:
                    continue
                for lh, s in langs[slot]:
                    en = en_by_lh.get(lh)
                    if not en:
                        continue
                    k = key_of(en)
                    if k not in wanted:
                        continue
                    out.setdefault(k, {})[lang] = s

        for i in R.indices("DLGE"):
            r = R.resources[i]
            try:
                wavs, ok = D.decode_dlge(R.read(i))
            except Exception:
                continue
            if not ok:
                continue
            for w in wavs:
                en = w["langs"].get("en")
                if not en:
                    continue
                clean_en = clean_sub(en)
                k = key_of(clean_en)
                if k not in wanted:
                    continue
                for lang, code in DLGE_CODE.items():
                    s = w["langs"].get(code)
                    if s:
                        out.setdefault(k, {})[lang] = clean_sub(s)

    covered = {lang: sum(1 for v in out.values() if lang in v) for lang in SLOT}
    json.dump(out, open(os.path.join(FLEET, "gender_context.json"), "w", encoding="utf-8"),
              ensure_ascii=False)
    print(f"joined {len(out):,}/{len(wanted):,} keys with >=1 reference language")
    for lang, n in covered.items():
        print(f"  {lang}: {n:,}")
    print("-> fleet/gender_context.json")


if __name__ == "__main__":
    main()
