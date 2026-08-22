"""Extract the FULL English corpus of Skyrim SE / AE + an honest scope report.

Reads every *.bsa in the install, pulls each `strings/<plugin>_english.{strings,
dlstrings,ilstrings}`, and reports the THREE numbers that matter (records /
per-file uniques / GLOBAL uniques). Only the last one is the translation workload.

Also writes the parallel text of the other 7 shipped languages, which is the
New-Era / gender oracle panel (pl+ru mark speaker AND addressee gender, fr/es/it
mark referent gender, de marks register, ja marks politeness level).

out:  extract/en_all.json     {"<plugin>|<id>|<kind>": "english"}
      extract/langs/<lang>.json   same keying, per language
      extract/scope.json      the report
"""
from __future__ import annotations

import collections
import glob
import json
import os
import re
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "tools"))

from bsa import Bsa            # noqa: E402
import strings as ST           # noqa: E402

GAME = Path(os.environ.get("SKYRIM_GAME",
                           r"D:\Games\TES - Skyrim - Anniversary Edition"))
DATA = GAME / "Data"
EXTRACT = ROOT / "extract"

LANGS = ("english", "french", "german", "italian", "spanish",
         "polish", "russian", "japanese")
KINDS = ("strings", "dlstrings", "ilstrings")

TOKENS = {
    "<tag>": re.compile(r"<[^<>\n]{1,80}>"),
    "[bracket]": re.compile(r"\[[A-Za-z][A-Za-z0-9 _/]{0,30}\]"),
    "%spec": re.compile(r"%[sdi]"),
    "newline": re.compile(r"\r\n|\n"),
}


def collect() -> dict[str, dict[str, str]]:
    """-> {lang: {"plugin|id|kind": value}}"""
    out: dict[str, dict[str, str]] = {la: {} for la in LANGS}
    for p in sorted(glob.glob(str(DATA / "*.bsa"))):
        try:
            b = Bsa(p)
        except Exception as e:                       # noqa: BLE001
            print(f"  !! {os.path.basename(p)}: {e}")
            continue
        for f in b.files:
            if not f.path.startswith("strings/"):
                continue
            stem, _, kind = os.path.basename(f.path).rpartition(".")
            plug, _, lang = stem.rpartition("_")
            if lang not in out or kind not in KINDS:
                continue
            try:
                ent = ST.decode(b.read(f), kind in ("dlstrings", "ilstrings"))
            except Exception as e:                   # noqa: BLE001
                print(f"  !! {f.path}: {e}")
                continue
            for sid, v in ent.items():
                out[lang][f"{plug}|{sid}|{kind}"] = v
    return out


def report(en: dict[str, str], langs: dict[str, dict[str, str]]) -> dict:
    per_kind = collections.defaultdict(dict)
    per_plugin = collections.Counter()
    for k, v in en.items():
        plug, _sid, kind = k.split("|")
        per_kind[kind][k] = v
        per_plugin[plug] += 1
    uniq = set(en.values())
    lens = sorted(len(v) for v in uniq)
    tok = {n: sum(len(rx.findall(v)) for v in uniq) for n, rx in TOKENS.items()}
    rep = {
        "records": len(en),
        "unique_global": len(uniq),
        "chars_unique": sum(lens),
        "by_kind": {k: {"records": len(d), "unique": len(set(d.values())),
                        "chars": sum(len(x) for x in set(d.values()))}
                    for k, d in per_kind.items()},
        "plugins": len(per_plugin),
        "top_plugins": per_plugin.most_common(10),
        "length": {"median": statistics.median(lens),
                   "p90": lens[int(len(lens) * .9)], "max": max(lens),
                   "le25": sum(1 for x in lens if x <= 25),
                   "gt140": sum(1 for x in lens if x > 140)},
        "tokens": tok,
        "oracle_langs": {la: len(d) for la, d in langs.items() if la != "english"},
        "oracle_key_parity": {la: round(len(set(d) & set(en)) / max(len(en), 1), 4)
                              for la, d in langs.items() if la != "english"},
    }
    return rep


def main() -> int:
    EXTRACT.mkdir(parents=True, exist_ok=True)
    (EXTRACT / "langs").mkdir(exist_ok=True)
    print("scanning BSAs ...")
    langs = collect()
    en = langs["english"]
    for la, d in langs.items():
        (EXTRACT / "langs" / f"{la}.json").write_text(
            json.dumps(d, ensure_ascii=False), encoding="utf-8")
    (EXTRACT / "en_all.json").write_text(
        json.dumps(en, ensure_ascii=False), encoding="utf-8")
    rep = report(en, langs)
    (EXTRACT / "scope.json").write_text(
        json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\nrecords          {rep['records']:>8}")
    print(f"GLOBAL unique    {rep['unique_global']:>8}   <- the real workload")
    print(f"chars (unique)   {rep['chars_unique']:>8}")
    for k, d in rep["by_kind"].items():
        print(f"  {k:<10} records={d['records']:>7} unique={d['unique']:>7} chars={d['chars']:>9}")
    print(f"plugins {rep['plugins']}   tokens {rep['tokens']}")
    print(f"length {rep['length']}")
    print("oracle languages (key parity vs english):")
    for la, p in rep["oracle_key_parity"].items():
        print(f"  {la:<10} {rep['oracle_langs'][la]:>7} rows  parity={p:.1%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
