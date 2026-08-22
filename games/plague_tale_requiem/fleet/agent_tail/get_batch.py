#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Serve the next batch of untranslated PT Requiem tail lines to the agent.

Usage:  python get_batch.py [N]        (default N=60)
Writes current_batch.json = {id: {en, ar}} of the next untranslated lines.
A line is 'done' if it's already in the fleet bank (../hebrew.json) OR in the agent bank
(../banks/out_agent.json) — so the agent never re-does what NIM or a previous batch finished.
Prints "All done!" when nothing is left.
"""
import json, os, sys

HERE  = os.path.dirname(os.path.abspath(__file__))
FLEET = os.path.dirname(HERE)
TT    = os.path.join(HERE, "to_translate.json")
BANK  = os.path.join(FLEET, "hebrew.json")
OUTAG = os.path.join(FLEET, "banks", "out_agent.json")
BATCH = os.path.join(HERE, "current_batch.json")


def load(p, d):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return d


def done_key(v):
    return isinstance(v, str) and v.strip() != ""


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    tt = load(TT, {})
    bank = load(BANK, {})
    ag = load(OUTAG, {})
    done = {k for k, v in bank.items() if done_key(v)} | {k for k, v in ag.items() if done_key(v)}
    todo = [(k, v) for k, v in tt.items() if k not in done]
    if not todo:
        print("All done! 0 remaining.")
        try:
            os.remove(BATCH)
        except OSError:
            pass
        return
    batch = dict(todo[:n])
    json.dump(batch, open(BATCH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"Wrote {len(batch)} lines to current_batch.json  ({len(todo)} remaining, {len(done)} done).")
    print("Translate each 'en' into fluent period Hebrew (value), keep {STR_} and | verbatim, then run merge_batch.py.")


if __name__ == "__main__":
    main()
