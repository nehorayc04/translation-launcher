#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build to_translate.json = the PT Requiem TAIL (every line not yet banked), gender-aware {en,ar}.

Source = the master extract/gender_source.json ({k:{en,ar,hint}}); a line is EXCLUDED once it is
banked in the fleet (fleet/hebrew.json) OR already done by the agent (fleet/banks/out_agent.json).
Re-run any time to refresh (agent + NIM fleet share the bank, so this shrinks as either produces).

Usage: python build_tail.py
"""
import json, os

HERE   = os.path.dirname(os.path.abspath(__file__))
FLEET  = os.path.dirname(HERE)
MASTER = os.path.join(FLEET, "..", "extract", "gender_source.json")
BANK   = os.path.join(FLEET, "hebrew.json")
OUTAG  = os.path.join(FLEET, "banks", "out_agent.json")
TT     = os.path.join(HERE, "to_translate.json")


def load(p, d):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return d


def done_key(v):
    return isinstance(v, str) and v.strip() != ""


def main():
    master = load(MASTER, {})
    bank = load(BANK, {})
    ag = load(OUTAG, {})
    markers = set(load(os.path.join(FLEET, "marker_keys.json"), []))
    done = {k for k, v in bank.items() if done_key(v)} | {k for k, v in ag.items() if done_key(v)}
    tt = {}
    for k, v in master.items():
        if k in done or k in markers:      # skip banked + non-translatable markers (keep Arabic)
            continue
        en = (v.get("en") if isinstance(v, dict) else v) or ""
        if not en.strip():
            continue
        tt[k] = {"en": en, "ar": (v.get("ar") if isinstance(v, dict) else "") or ""}
    json.dump(tt, open(TT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"master={len(master)}  banked/done={len(done)}  -> to_translate.json = {len(tt)} lines")


if __name__ == "__main__":
    main()
