r"""
Build the New-Era agent handoff for VirtualDJ (all 12 shipped languages as the
context/gender/meaning oracle).

Reads ../extract/langs_orig/*.xml (carved from the exe) and emits:
  to_translate.json : {key: {"en": src, "refs": {lang: text, ...}}}  (all langs)
  hebrew.json       : {}   (agent output; grows)
  skip.json         : {key: en}  non-translatable (no translatable letters)

`key` = "Section/Key" (identical across all languages). English = the source of
truth; every other language is a cross-check for meaning + gender + number.
"""
import re
import sys
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GAME = HERE.parent
sys.path.insert(0, str(GAME / "tools"))
import vdj_lang  # noqa: E402

LANG_DIR = GAME / "extract" / "langs_orig"
# order = usefulness for the New-Era oracle (source first, then gender/meaning bearers)
LANGS = ["English", "German", "French", "Spanish", "Italian", "Russian",
         "Portuguese", "Dutch", "Greek", "Japanese", "Chinese (simplified)",
         "Arabic"]
CODE = {"English": "en", "German": "de", "French": "fr", "Spanish": "es",
        "Italian": "it", "Russian": "ru", "Portuguese": "pt", "Dutch": "nl",
        "Greek": "el", "Japanese": "ja", "Chinese (simplified)": "zh",
        "Arabic": "ar"}

LATIN_WORD = re.compile(r"[A-Za-z]")


def load_all():
    maps = {}
    for name in LANGS:
        p = LANG_DIR / f"{name}.xml"
        _, secs = vdj_lang.parse(p.read_bytes())
        maps[CODE[name]] = vdj_lang.flatten(secs)
    return maps


def main():
    maps = load_all()
    en = maps["en"]
    # visibility order: UI sections first, the technical VDJScript `Actions`
    # command docs last (so an interrupted run finishes the visible UI first).
    ordered = ([k for k in en if not k.startswith("Actions/")] +
               [k for k in en if k.startswith("Actions/")])
    to_translate, skip = {}, {}
    for key in ordered:
        src = en[key]
        # non-translatable = no latin letter at all (pure %i / numbers / symbols)
        if not LATIN_WORD.search(src):
            skip[key] = src
            continue
        refs = {}
        for code in ("de", "fr", "es", "it", "ru", "pt", "nl", "el", "ja",
                     "zh", "ar"):
            v = maps[code].get(key)
            if v and v != src:            # only include a real, differing ref
                refs[code] = v
        to_translate[key] = {"en": src, "refs": refs}

    json.dump(to_translate, open(HERE / "to_translate.json", "w",
              encoding="utf-8"), ensure_ascii=False, indent=0)
    json.dump(skip, open(HERE / "skip.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=0)
    if not (HERE / "hebrew.json").exists():
        json.dump({}, open(HERE / "hebrew.json", "w", encoding="utf-8"))

    print(f"to_translate = {len(to_translate)}  skip = {len(skip)}")
    # sanity: how rich is the oracle
    avg = sum(len(v['refs']) for v in to_translate.values()) / max(1, len(to_translate))
    print(f"avg reference languages per line = {avg:.1f} / 11")


if __name__ == "__main__":
    main()
