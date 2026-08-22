#!/usr/bin/env python3
"""loop_merge.py — validate + merge a translated batch into hebrew.json (atomic).

Usage:
    python loop_merge.py batch_he.json      # batch_he.json = {key: hebrew_LOGICAL}

For each pair it checks against to_translate.json[key] (the English source):
  * token multiset identical (~r~ ~s~ <C> %s ...)  -> else REJECT (re-do next round)
  * no niqqud, no foreign script                    -> else REJECT
  * has Hebrew, UNLESS the source is a pure name/code (no real lowercase word) -> then
    the Latin value is accepted as-is (passthrough), key still recorded as done.
Rejected keys are reported and simply left untranslated (they reappear in get_batch).
Accepted pairs are merged into hebrew.json. The Hebrew stays LOGICAL — visual reversal
happens later in work/gtav_build.py, never here.
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from _tokens import tokens, has_hebrew, has_niqqud, foreign_chars, real_word  # noqa

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def load(name, default):
    p = os.path.join(HERE, name)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else default


def atomic_write(name, obj):
    p = os.path.join(HERE, name)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, sort_keys=True)
    os.replace(tmp, p)


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: python loop_merge.py <batch_he.json>")
    batch = json.load(open(sys.argv[1], encoding="utf-8"))
    src = load("to_translate.json", {})
    done = load("hebrew.json", {})
    skip = set(load("skip.json", []))

    merged = rejected = passthrough = 0
    reasons = {}
    for k, he in batch.items():
        en = src.get(k, "")
        if tokens(he) != tokens(en):
            rejected += 1; reasons[k] = "token-mismatch"; continue
        if has_niqqud(he):
            rejected += 1; reasons[k] = "niqqud"; continue
        f = foreign_chars(he)
        if f:
            rejected += 1; reasons[k] = "foreign:" + "".join(f[:4]); continue
        if not has_hebrew(he):
            if not real_word(en):
                passthrough += 1            # name/code, Latin OK
            else:
                rejected += 1; reasons[k] = "no-hebrew"; continue
        done[k] = he
        merged += 1

    atomic_write("hebrew.json", done)
    todo = sum(1 for k in src if k not in done and k not in skip)
    print(f"[merge] +{merged} merged ({passthrough} Latin passthrough), "
          f"{rejected} rejected. {len(done)}/{len(src)} done, {todo} left.")
    if reasons:
        for k, r in list(reasons.items())[:15]:
            print(f"   REJECT {k}: {r}  ::  {batch[k][:60]!r}")
    if not todo:
        print("All done!")


if __name__ == "__main__":
    main()
