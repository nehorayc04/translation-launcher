#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Non-translatable MARKERS must keep the shipping Arabic value (exactly like the pro Arabic
localization does), NOT be force-translated. The over-strict has-Hebrew gate made the agents invent
Hebrew for them. This: (1) computes the marker key-set from the master corpus, (2) writes
fleet/marker_keys.json (the pull filters these so they never enter hebrew.json), (3) purges marker
keys from every banks/out_*.json and from the agent to_translate.json slices.

Marker = EN is  onom|mono|empty  (case-insensitive, the sound/empty cue markers, AR ships as mono/MONO)
             OR a URL (^048…^000 / www. / http)
             OR pure non-Latin/non-Hebrew native script (the language-menu names 한국어/日本語/… — AR keeps native)
             OR an empty source.
Real interjections ("Yes!","Ah!","What?") are NOT markers — they translate normally.
"""
import json, os, re, glob

HERE   = os.path.dirname(os.path.abspath(__file__))
FLEET  = os.path.dirname(HERE)
MASTER = os.path.join(FLEET, "..", "extract", "gender_source.json")
BANKS  = os.path.join(FLEET, "banks")
MKEYS  = os.path.join(FLEET, "marker_keys.json")

MARKER = re.compile(r'^(?:onom|mono|empty)$', re.I)
URLISH = re.compile(r'https?://|www\.|\^048')
NATIVE = re.compile(r'^[^\x00-\x7f֐-׿]+$')   # no ASCII + no Hebrew = pure foreign (CJK/Korean)


def is_marker(en):
    s = (en or "").strip()
    if not s:
        return True
    if MARKER.match(s):
        return True
    if URLISH.search(en):
        return True
    if NATIVE.match(s):
        return True
    return False


def load(p, d):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return d


def atomic(p, obj):
    tmp = p + ".tmp"
    json.dump(obj, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(tmp, p)


def main():
    master = load(MASTER, {})
    marker_keys = set()
    for k, v in master.items():
        en = (v.get("en") if isinstance(v, dict) else v) or ""
        if is_marker(en):
            marker_keys.add(k)
    atomic(MKEYS, sorted(marker_keys))
    print(f"marker keys = {len(marker_keys)}  -> {os.path.relpath(MKEYS, FLEET)}")

    # purge from every bank file
    purged_banks = 0
    for f in glob.glob(os.path.join(BANKS, "out_*.json")):
        d = load(f, {})
        rm = [k for k in d if k in marker_keys]
        if rm:
            for k in rm:
                del d[k]
            atomic(f, d)
            purged_banks += len(rm)
            print(f"  {os.path.basename(f)}: purged {len(rm)}")
    print(f"purged {purged_banks} marker entries from bank files")

    # purge from the agent slices + the single-tail file so they stop being served
    for f in (glob.glob(os.path.join(HERE, "agent_*", "to_translate.json"))
              + [os.path.join(HERE, "to_translate.json")]):
        d = load(f, {})
        rm = [k for k in d if k in marker_keys]
        if rm:
            for k in rm:
                del d[k]
            atomic(f, d)
            print(f"  {os.path.relpath(f, HERE)}: removed {len(rm)} markers ({len(d)} left)")


if __name__ == "__main__":
    main()
