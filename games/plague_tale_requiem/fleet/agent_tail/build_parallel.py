#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Split the PT Requiem TAIL into N disjoint, ISOLATED agent folders (agent_1..agent_N) for parallel
translation — no collisions (md5(key)%N slots), each with its OWN bank file out_agent<k>.json that the
fleet pull folds into hebrew.json. Each folder is self-contained (get_batch/merge_batch/to_translate/
INSTRUCTIONS) so one agent editing/deleting files can't break another.

Usage: python build_parallel.py [N]   (default N=3)
Re-run any time to refresh the slices (already-banked lines drop out; agents keep their out_agent<k>.json).
"""
import json, os, sys, hashlib, glob

HERE   = os.path.dirname(os.path.abspath(__file__))
FLEET  = os.path.dirname(HERE)
MASTER = os.path.join(FLEET, "..", "extract", "gender_source.json")
BANK   = os.path.join(FLEET, "hebrew.json")
BANKS  = os.path.join(FLEET, "banks")


def load(p, d):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return d


def nonempty(v):
    return isinstance(v, str) and v.strip() != ""


GET_BATCH = r'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Serve the next batch for THIS agent slot (a disjoint md5 slice of the PT tail).
Usage: python get_batch.py [N]   (default 60). Prints "All done!" when the slot is empty."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
FLEET = os.path.abspath(os.path.join(HERE, "..", ".."))
TT = os.path.join(HERE, "to_translate.json")
BANK = os.path.join(FLEET, "hebrew.json")
MYBANK = os.path.join(FLEET, "banks", "__BANK__")
BATCH = os.path.join(HERE, "current_batch.json")
def load(p, d):
    try: return json.load(open(p, encoding="utf-8"))
    except Exception: return d
def ne(v): return isinstance(v, str) and v.strip() != ""
def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    tt = load(TT, {}); bank = load(BANK, {}); mine = load(MYBANK, {})
    done = {k for k, v in bank.items() if ne(v)} | {k for k, v in mine.items() if ne(v)}
    todo = [(k, v) for k, v in tt.items() if k not in done]
    if not todo:
        print("All done! 0 remaining in this slot.")
        try: os.remove(BATCH)
        except OSError: pass
        return
    json.dump(dict(todo[:n]), open(BATCH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("Wrote %d lines to current_batch.json (%d remaining, %d done)." % (min(n, len(todo)), len(todo), len(done)))
    print("Translate each 'en' into Hebrew (value); keep {STR_...} and the pipe | verbatim; then run merge_batch.py.")
if __name__ == "__main__": main()
'''

MERGE = r'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate + merge THIS agent's batch into its own fleet bank (../../banks/__BANK__).
The fleet pull folds every ../../banks/out_*.json into hebrew.json -> the site dashboard moves.
LOGICAL Hebrew (RTL baked later). Anti-cheat: no foreign/niqqud, {STR_}/|/% token multiset must match,
real English prose must be translated (bare name/code copy allowed)."""
import json, os, re
HERE = os.path.dirname(os.path.abspath(__file__))
FLEET = os.path.abspath(os.path.join(HERE, "..", ".."))
TT = os.path.join(HERE, "to_translate.json")
BATCH = os.path.join(HERE, "current_batch.json")
BANKS = os.path.join(FLEET, "banks")
MYBANK = os.path.join(BANKS, "__BANK__")
STRUCT  = re.compile(r'\{[^}]*\}|\||%%|%[#0-9.*\-+]*[a-zA-Z]+')
FOREIGN = re.compile(r'[؀-ۿЀ-ӿ一-鿿぀-ヿ가-힯฀-๿]')
NIQ = re.compile(r'[֑-ׇ]')
HEB = re.compile(r'[א-ת]')
LOWERW = re.compile(r'[a-z]{2,}')
def load(p, d):
    try: return json.load(open(p, encoding="utf-8"))
    except Exception: return d
def is_namey(en):
    core = STRUCT.sub(" ", en).strip()
    if not LOWERW.search(core): return True
    words = re.findall(r"[A-Za-z']+", core)
    return bool(words) and len(words) <= 4 and all(w[:1].isupper() for w in words)
def valid(he, en):
    if not he or not he.strip(): return False, "empty"
    if FOREIGN.search(he): return False, "foreign-script"
    if NIQ.search(he): return False, "niqqud"
    if sorted(STRUCT.findall(he)) != sorted(STRUCT.findall(en)): return False, "token-mismatch"
    if not HEB.search(he):
        if he.strip() == en.strip() and is_namey(en): return True, "name-passthrough"
        return False, "no-hebrew"
    return True, "ok"
def main():
    tt = load(TT, {}); batch = load(BATCH, {})
    if not batch:
        print("No current_batch.json - run get_batch.py first."); return
    os.makedirs(BANKS, exist_ok=True)
    mine = load(MYBANK, {}); merged = skipped = 0; reasons = {}
    for k, v in batch.items():
        if k not in tt: continue
        he = v.get("he") if isinstance(v, dict) else v
        he = (he or "").strip()
        he = NIQ.sub("", he).replace("‎", "").replace("‏", "").replace("​", "")
        ok, why = valid(he, tt[k]["en"])
        if ok: mine[k] = he; merged += 1
        else: skipped += 1; reasons[why] = reasons.get(why, 0) + 1
    tmp = MYBANK + ".tmp"
    json.dump(mine, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(tmp, MYBANK)
    remaining = sum(1 for k in tt if k not in mine)
    print("merged %d, rejected %d  %s" % (merged, skipped, reasons if reasons else ""))
    print("%s now %d  (~%d of this slot left). The fleet pull (~3 min) folds it into hebrew.json." % ("__BANK__", len(mine), remaining))
    if remaining == 0: print("All done! This slot is fully translated.")
if __name__ == "__main__": main()
'''

INSTR = '''# A Plague Tale: Requiem - Hebrew TAIL translation - AGENT {k} of {n}

You are a senior **Hebrew** game localizer. Translate the remaining lines of **A Plague Tale: Requiem**
(grim historical fiction, **1349 plague-ravaged southern France** - Inquisition, rats, alchemy;
characters **Amicia, Hugo, Lucas, Beatrice, Vaudin, Sophia**). Serious, literary, period register.

This is agent **{k}** - your slice is DISJOINT from the other agents (no overlap). Work ONLY in THIS
folder, in a loop, ~60 lines at a time, until "All done!".

## The loop
1. `python get_batch.py 60`  -> writes `current_batch.json` = `{{ "KEY": {{"en":"...","ar":"..."}} }}`.
   If it prints **"All done!"**, you're finished - report the total and stop.
2. In `current_batch.json`, translate every `en` into fluent period Hebrew, put the Hebrew in the value
   (replace the object with the string, or add `"he":"..."`).
3. `python merge_batch.py`  -> validates + banks the good ones; rejected lines return next round.
4. Repeat.

## Hard rules (rejected if broken)
- Hebrew only (Hebrew + Latin/digits). No Arabic/Cyrillic/CJK/Thai. No niqqud.
- Keep every token VERBATIM, same count: `{{STR_...}}` button tokens; the pipe **`|`** (a LINE BREAK);
  `%d`/`%s`/`%%`.
- Meaning = **`en`**. **`ar`** is ONLY the gender/number oracle (Arabic marks what English hides:
  addressee أنتَ=אתה / أنتِ=את / أنتم=אתם, speaker gender, feminine ـة -> ...ה, plurals). Match that
  gender/number. Do NOT translate from Arabic and never copy Arabic words.
- Names -> Hebrew transliteration (Amicia->אמיסיה, Hugo->הוגו, Lucas->לוקא). Brand/code tokens stay Latin.
- Write **LOGICAL** Hebrew (normal order) - do NOT reverse anything; RTL is baked later.

## Do NOT
- Do not edit get_batch.py / merge_batch.py / to_translate.json.
- Do not write an auto/MT script or fill values with English/placeholders - the gate rejects untranslated
  English prose and it just wastes rounds.
'''


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    master = load(MASTER, {})
    bank = load(BANK, {})
    done = {k for k, v in bank.items() if nonempty(v)}
    for f in glob.glob(os.path.join(BANKS, "out_*.json")):
        for k, v in load(f, {}).items():
            if nonempty(v):
                done.add(k)
    markers = set(load(os.path.join(FLEET, "marker_keys.json"), []))
    slices = [{} for _ in range(n)]
    for k, v in master.items():
        if k in done or k in markers:      # skip banked + non-translatable markers (keep Arabic)
            continue
        en = (v.get("en") if isinstance(v, dict) else v) or ""
        if not en.strip():
            continue
        slot = int(hashlib.md5(k.encode("utf-8")).hexdigest(), 16) % n
        slices[slot][k] = {"en": en, "ar": (v.get("ar") if isinstance(v, dict) else "") or ""}
    total = sum(len(s) for s in slices)
    print(f"remaining tail = {total}  -> {n} disjoint slots")
    for i in range(n):
        k = i + 1
        d = os.path.join(HERE, f"agent_{k}")
        os.makedirs(d, exist_ok=True)
        bankname = f"out_agent{k}.json"
        json.dump(slices[i], open(os.path.join(d, "to_translate.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        open(os.path.join(d, "get_batch.py"), "w", encoding="utf-8").write(GET_BATCH.replace("__BANK__", bankname))
        open(os.path.join(d, "merge_batch.py"), "w", encoding="utf-8").write(MERGE.replace("__BANK__", bankname))
        open(os.path.join(d, "INSTRUCTIONS.md"), "w", encoding="utf-8").write(INSTR.format(k=k, n=n))
        print(f"  agent_{k}: {len(slices[i]):5d} lines -> bank {bankname}")
    # sanity: disjoint + complete
    allk = set()
    for s in slices:
        allk |= set(s)
    assert len(allk) == total == sum(len(s) for s in slices), "SLOTS NOT DISJOINT/COMPLETE"
    print(f"OK: {n} slots disjoint + cover all {total} remaining tail lines.")


if __name__ == "__main__":
    main()
