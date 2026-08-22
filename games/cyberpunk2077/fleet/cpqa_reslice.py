# -*- coding: utf-8 -*-
"""Re-split the UNREVIEWED CP2077 QA corpus (qa_corpus.json minus cpqa_out.json) into 7 disjoint,
balanced slices — one per fleet stream. The already-reviewed 33k+ stay safe in cpqa_out.json (the
monotonic merge preserves them), so a reslice loses NOTHING and creates NO redundant re-review:
each stream just gets 1/7 of what's LEFT. Round-robin over sorted keys => deterministic + balanced.
Writes splits/cpqa7_<stream>.json for: vm vm2 vm3 vm4 vm5 laptop desktop.
"""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
# W3 is DONE -> vm4+vm5 freed and rejoin CP2077 QA (user directive 2026-07-13). All 7 streams.
ALL_STREAMS = ["vm", "vm2", "vm3", "vm4", "vm5", "laptop", "desktop"]
# streams temporarily freed for OTHER translation work (fleet/paused_streams) get NO slice, so a
# reslice never hands CP2077 work to a VM that is busy on another game.
try:
    _paused = {l.strip() for l in open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                    "paused_streams"), encoding="utf-8") if l.strip()}
except Exception:
    _paused = set()
STREAMS = [s for s in ALL_STREAMS if s not in _paused]

corpus = json.load(open(os.path.join(HERE, "qa_corpus.json"), encoding="utf-8"))
try:
    done = set(json.load(open(os.path.join(HERE, "cpqa_out.json"), encoding="utf-8")))
except Exception:
    done = set()
todo = sorted(k for k in corpus if k not in done)
N = len(STREAMS)
slices = [{} for _ in range(N)]
for i, k in enumerate(todo):
    slices[i % N][k] = corpus[k]

os.makedirs(os.path.join(HERE, "splits"), exist_ok=True)
for i, nm in enumerate(STREAMS):
    p = os.path.join(HERE, "splits", f"cpqa7_{nm}.json")
    json.dump(slices[i], open(p, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"  {nm:7s} {len(slices[i])}")
print(f"total corpus={len(corpus)}  reviewed={len(done)}  unreviewed={len(todo)}  -> {N} streams")
