#!/usr/bin/env python3
"""verify_uireview.py — adjudicate the UI-label review's proposed changes with a SECOND,
independent model pass, and apply only the ones it confirms.

🔴 WHY A SECOND PASS AT ALL. The review pass (`drain_tokenheavy.py --review`) is monotonic by
instruction, not by construction: told "default to leaving it alone", it still rewrote roughly
one line in eight, and a hand-read of the first 30 showed the changes split about evenly
between REAL fixes (`Sip` was translated `שב` = *sit*) and pointless or harmful churn
(`Bath` `אמבטיה` -> `אמבט`, `Tick` `קרץ` -> `טיק`). Applying that wholesale is a coin flip.
So this is the project's proven review -> adversarial-verify shape: a model will not refute
its own proposal, but a fresh one, shown only OLD vs NEW and asked to pick, will — and its
default answer is OLD.

🔴 AND AN EARLIER, WORSE IDEA THAT THIS REPLACES. The first attempt was ARBITRATE mode:
"the English may be mis-paired, follow the majority of the game's other languages". It made
things measurably worse, because on a mis-paired key the sibling panel is mis-paired too, so
the "majority" is confidently wrong — the model dutifully rewrote correct lines into broken
ones, moving `~o~`/`~HC_~1p~~` wrapper tokens OUT of the phrase they wrap. An arbiter that
shares the suspect's defect is not an arbiter.

    python verify_uireview.py            # adjudicate, report, write nothing
    python verify_uireview.py --apply
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
# ⚠️ HERE ONLY. Adding `universal/` to sys.path shadowed this fleet's own
# `fleet_providers.py` with the universal copy, whose `load_keys` reads a different key file —
# every single call then came back `HTTP Error 401: Unauthorized`, which reads exactly like a
# dead key pool and cost a whole run. Import the same module the workers import, nothing else.
sys.path.insert(0, HERE)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

CORPUS = os.path.join(HERE, "corpus_uireview.json")
BANK = os.path.join(HERE, "hebrew_missing.json")
# sorts after every out_zz* the review wrote, so a confirmed fix wins the merge
OUT = os.path.join(HERE, "banks_missing", "out_zzzverify.json")

STRUCT = re.compile(r"~[^~]*~|\{[^}]*\}|%%|%[#0-9.*\-+]*[a-zA-Z]+")
NIQ = re.compile(r"[֑-ֽֿ-ׇ]")
HEB = re.compile(r"[א-ת]")
FOREIGN = re.compile(r"[Ѐ-ӿ؀-ۿ一-鿿぀-ヿ가-힯]")

SYS = (
    "אתה בורר לשוני. לכל פריט אתה מקבל תווית ממשק של Red Dead Redemption 2: "
    "en (אנגלית), תרגומי המשחק לשפות נוספות, ושתי גרסאות עבריות: OLD ו-NEW.\n"
    "החלט איזו מהן נכונה יותר כתווית ממשק.\n"
    "ברירת המחדל היא OLD. בחר NEW רק אם OLD פשוט שגויה במשמעות — מילה אחרת לגמרי מהאנגלית "
    "ומהשפות האחרות, או שגיאת עברית ממשית.\n"
    "אם ההבדל הוא ניסוח, מילה נרדפת, יידוע, או העדפת סגנון — בחר OLD.\n"
    "החזר JSON בלבד: {\"<key>\": \"OLD\"} או {\"<key>\": \"NEW\"} לכל מפתח."
)


def sane(en: str, he: str) -> bool:
    """A candidate must at least be structurally shippable before it is even adjudicated."""
    if not he.strip() or not HEB.search(he):
        return False
    if NIQ.search(he) or FOREIGN.search(he):
        return False
    return sorted(STRUCT.findall(he)) == sorted(STRUCT.findall(en))


def main() -> None:
    apply = "--apply" in sys.argv
    corpus = json.load(open(CORPUS, encoding="utf-8"))
    prop: dict[str, str] = {}
    for f in sorted(glob.glob(os.path.join(HERE, "banks_missing", "out_zzui*.json"))):
        prop.update(json.load(open(f, encoding="utf-8")))
    cand = {k: v for k, v in prop.items()
            if k in corpus and v.strip() != corpus[k]["he"].strip()}
    print(f"reviewed {len(prop):,} · proposed changes {len(cand):,}")

    unsafe = {k for k, v in cand.items() if not sane(corpus[k]["en"], v)}
    if unsafe:
        print(f"  dropped {len(unsafe):,} structurally unsafe proposals before adjudication")
    cand = {k: v for k, v in cand.items() if k not in unsafe}
    if not cand:
        print("nothing to adjudicate")
        return

    from fleet_providers import Fleet, load_keys           # noqa: E402
    fleet = Fleet(load_keys(HERE))
    keys = sorted(cand)
    took: dict[str, str] = {}
    B = 10
    for i in range(0, len(keys), B):
        sub = keys[i:i + B]
        payload = {}
        for k in sub:
            v = corpus[k]
            row = {"en": v["en"], "OLD": v["he"], "NEW": cand[k]}
            for n, t in list(v.get("refs", {}).items())[:4]:
                row[n] = t
            payload[k] = row
        try:
            raw = fleet.complete(SYS, "Judge:\n" + json.dumps(payload, ensure_ascii=False),
                                 retries=3, timeout=70, max_tokens=900)
        except Exception as e:                              # noqa: BLE001
            print(f"  [{i//B+1}] provider: {e}")
            continue
        try:
            got = json.loads(re.search(r"\{.*\}", raw or "", re.S).group(0))
        except Exception:                                   # noqa: BLE001
            got = {}
        for k in sub:
            # 🔑 Anything that is not an explicit NEW is treated as OLD — a dropped key, a
            # malformed reply and a provider failure must never silently promote a change.
            if str(got.get(k, "OLD")).strip().upper() == "NEW":
                took[k] = cand[k]
        print(f"  [{i//B+1}/{(len(keys)+B-1)//B}] confirmed {len(took):,}", flush=True)

    print(f"\nconfirmed {len(took):,} of {len(cand):,} proposals "
          f"({100*len(took)/max(1,len(cand)):.0f}%)")
    for k in list(took)[:25]:
        print(f"   EN={corpus[k]['en'][:26]!r}  {corpus[k]['he'][:24]!r} -> {took[k][:24]!r}")
    if not apply:
        print("\n(report only — pass --apply)")
        return
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(took, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"\n-> {OUT} ({len(took)})")


if __name__ == "__main__":
    main()
