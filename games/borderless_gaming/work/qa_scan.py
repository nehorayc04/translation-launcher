"""QA gate for hebrew.json - run before every build.

Checks, per key, against the English source:
  coverage      every EN key present, nothing invented
  tokens        {0}/{1} multiset and \n count identical to the English
  niqqud        none (U+0591-U+05C7)
  foreign       no script other than Hebrew/Latin/digits/punctuation
  untranslated  still byte-identical to the English (allowed only for the
                whitelist: brands, "X:", "Y:", the language code, ...)
  bidi_controls no RLM/LRM/RLE/PDF - Avalonia runs the UBA, we store LOGICAL
  consistency   a quoted 'option name' inside a description must match the
                Hebrew label of that option (the classic cross-reference drift)
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import bg_lang as B  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent.parent
EN = Path(r"F:/SteamLibrary/steamapps/common/Borderless Gaming/languages/en-US.json")

TOKEN = re.compile(r"\{\d+\}")
NIQQUD = re.compile(r"[֑-ׇ]")
BIDI = re.compile(r"[‎‏‪-‮⁦-⁩]")

# Values that may legitimately stay identical to the English.
KEEP_EN = {
    "App.Title", "Tray.Tooltip",            # brand name stays Latin
    "Language.Code",                        # a BCP-47 tag, must stay he-IL
    "Profile.Fields.Position.X", "Profile.Fields.Position.Y",
    "EffectEditor.Scaling.X", "EffectEditor.Scaling.Y",
}

# description-key -> label-key whose Hebrew text it quotes
CROSS_REF = {
    "Profile.Options.NudgeWindow.Description": "Profile.Options.FlipProcessingOrder.Label",
}


def script_of(ch: str) -> str:
    if ch.isascii():
        return "latin"
    if "֐" <= ch <= "׿":
        return "hebrew"
    if unicodedata.category(ch).startswith(("P", "S", "Z", "N", "M", "C")):
        return "neutral"
    return unicodedata.name(ch, "?").split()[0].lower()


def main() -> int:
    en = B.flatten(B.load(EN))
    he = json.loads((HERE / "hebrew.json").read_text("utf-8"))
    bad: list[str] = []

    missing = [k for k in en if k not in he]
    extra = [k for k in he if k not in en]
    if missing:
        bad.append(f"MISSING {len(missing)}: {missing[:8]}")
    if extra:
        bad.append(f"EXTRA (not a real key) {len(extra)}: {extra[:8]}")

    for k, src in en.items():
        v = he.get(k)
        if v is None:
            continue
        if not v.strip():
            bad.append(f"EMPTY  {k}")
            continue
        if sorted(TOKEN.findall(v)) != sorted(TOKEN.findall(src)):
            bad.append(f"TOKENS {k}: {TOKEN.findall(src)} -> {TOKEN.findall(v)}")
        if v.count("\n") != src.count("\n"):
            bad.append(f"NEWLINE {k}: {src.count(chr(10))} -> {v.count(chr(10))}")
        if NIQQUD.search(v):
            bad.append(f"NIQQUD {k}")
        if BIDI.search(v):
            bad.append(f"BIDI-CONTROL {k} (store LOGICAL, no marks)")
        foreign = {script_of(c) for c in v} - {"latin", "hebrew", "neutral"}
        if foreign:
            bad.append(f"FOREIGN {k}: {foreign}")
        if v == src and k not in KEEP_EN:
            bad.append(f"UNTRANSLATED {k}: {src!r}")
        if k not in KEEP_EN and not re.search(r"[א-ת]", v):
            bad.append(f"NO-HEBREW {k}: {v!r}")

    for desc_key, label_key in CROSS_REF.items():
        label = he.get(label_key, "")
        if label and label not in he.get(desc_key, ""):
            bad.append(f"CROSS-REF {desc_key} does not quote {label!r}")

    print(f"keys EN={len(en)} HE={len(he)}")
    if bad:
        print(f"\n{len(bad)} PROBLEM(S):")
        for b in bad:
            print("  " + b)
        return 1
    print("QA CLEAN - coverage, tokens, newlines, niqqud, foreign, bidi, cross-refs all OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
