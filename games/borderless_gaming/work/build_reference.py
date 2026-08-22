"""Build the New-Era reference corpus: every key beside its EN + the shipped
translations in the languages that actually disambiguate English.

Why these languages:
  ar  RTL sibling - shows noun-vs-imperative ("Search windows..." -> masdar,
      not a command) and how an RTL UI phrases things. Strongest oracle here.
  de  compounds + capitalised nouns -> tells a NOUN from a VERB ("Monitor",
      "Display", "Profile", "Match")
  fr  article/gender -> tells a noun's role; "Restaurer" vs "Restauration"
  ru  aspect + case -> imperative vs noun, singular vs plural
  es  romance cross-check
  it  romance cross-check

Outputs:
  extract/reference.json  {key: {en, ar, de, fr, ru, es, it}}
  extract/reference.txt   the same, human-readable, ordered like en-US.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import bg_lang as B  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

INSTALL = Path(r"F:/SteamLibrary/steamapps/common/Borderless Gaming")
LANGS = INSTALL / "languages"
REFS = [("ar", "ar-SA"), ("de", "de-DE"), ("fr", "fr-FR"),
        ("ru", "ru-RU"), ("es", "es-ES"), ("it", "it-IT")]

HERE = Path(__file__).resolve().parent.parent


def main() -> int:
    en = B.flatten(B.load(LANGS / "en-US.json"))
    refs = {tag: B.flatten(B.load(LANGS / f"{code}.json")) for tag, code in REFS}

    out = {}
    for k, v in en.items():
        row = {"en": v}
        for tag in refs:
            t = refs[tag].get(k, "")
            if t and t != v:          # skip untranslated echoes of the English
                row[tag] = t
        out[k] = row

    (HERE / "extract").mkdir(exist_ok=True)
    (HERE / "extract" / "reference.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    lines = []
    for k, row in out.items():
        lines.append(f"### {k}")
        lines.append(f"en  {row['en']}")
        for tag in ("ar", "de", "fr", "ru", "es", "it"):
            if tag in row:
                lines.append(f"{tag}  {row[tag]}")
        lines.append("")
    (HERE / "extract" / "reference.txt").write_text(
        "\n".join(lines), encoding="utf-8")

    print(f"{len(out)} keys -> extract/reference.{{json,txt}}")
    cov = {t: sum(1 for r in out.values() if t in r) for t in refs}
    print("reference coverage:", cov)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
