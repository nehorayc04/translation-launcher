#!/usr/bin/env python3
"""qa_missing.py — the end-of-run gate for the 28,101 "missing lines" fleet run.

The fleet's own guard runs per line at translate time; this runs over the MERGED bank, which
is the only place two different streams can be compared against each other. Two jobs:

  1. STRUCTURAL — re-apply the worker's guard to every banked line. A line can be in the bank
     and still be wrong: the guard was tightened mid-run (invented-number), and a
     hard-killed worker can bank a partially-written value.
  2. CONSISTENCY — the thing a per-line guard structurally CANNOT see: the same English
     rendered differently by two streams. With 21 streams that is the dominant defect class,
     and it is repaired at MERGE (majority vote), never by re-translating.

Deterministic repairs are APPLIED; anything needing a translation decision is RE-QUEUED
(deleted from the bank AND from the owning worker's out.json, or the worker still counts it
done and never re-serves it).

    python qa_missing.py             # report only
    python qa_missing.py --apply     # repair + write the re-queue list
"""
import json
import os
import re
import shutil
import sys
import time
from collections import Counter, defaultdict

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
BANK = os.path.join(HERE, "hebrew_missing.json")
CORPUS = os.path.join(HERE, "corpus_missing.json")
BANKS = os.path.join(HERE, "banks_missing")

FOREIGN = re.compile(r"[؀-ۿ぀-ヿ一-鿿가-힯Ѐ-ӿ]")
NIQ = re.compile(r"[֑-ֽֿׁׂ]")
HEB = re.compile(r"[א-ת]")
STRUCT = re.compile(r"~[^~]*~|\{[^}]*\}|%%|%[#0-9.*\-+]*[a-zA-Z]+")
LOWER = re.compile(r"[a-z]{2,}")
DIG = re.compile(r"\d+")
PANEL = re.compile(r"(?m)^\s*(?:EN|AR|RU|PL|DE|FR|ES|IT|BR)\s*:")
CTRL = "".join(chr(c) for c in range(0x20))
ORD = re.compile(r"^(\d+)(?:st|nd|rd|th)$", re.I)
URLISH = re.compile(
    r"^(?:https?://\S+|www\.\S+|[\w.\-]+@[\w.\-]+\.\w{2,}|[\w\-]+(?:\.[\w\-]+)+)$", re.I)
_NAMEWORD = re.compile(r"^[A-Z0-9][\w.\-'’/®™©]*$")


def NAMEY(en):
    ws = (en or "").strip().split()
    return bool(ws) and len(ws) <= 4 and all(_NAMEWORD.match(w) for w in ws)


def en_of(src):
    return src.get("en", "") if isinstance(src, dict) else (src or "")


def established_map():
    """EN -> the Hebrew ALREADY shipping in the game, for short terms only.

    Built by joining the 217k-line main corpus (keyed by LML key = a label or 0xHASH) onto
    the game's own English database (keyed by 0xHASH) — the same joaat join
    build_missing_corpus.py uses. Only terms with ONE settled Hebrew form across the whole
    corpus are returned: a term the shipping game itself renders two ways has no authority
    to lend. Returns {} rather than failing if the game text has not been extracted.
    """
    main = os.path.join(HERE, "hebrew.json")
    game = os.path.abspath(os.path.join(HERE, "..", "extract", "game_text", "american.json"))
    if not (os.path.exists(main) and os.path.exists(game)):
        print("[est] no established corpus (need hebrew.json + extract/game_text/american.json)")
        return {}
    sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "gtav", "work")))
    try:
        from gtav_gxt2 import joaat
    except Exception as e:
        print("[est] no joaat:", e)
        return {}
    en_by_hash = {k.lower(): v for k, v in json.load(open(game, encoding="utf-8")).items()}
    heb = json.load(open(main, encoding="utf-8"))
    pool = defaultdict(Counter)
    for key, he in heb.items():
        # 🔴 NORMALISE THE HEX CASE ON BOTH SIDES. `key.upper()` turns 0xAB into "0XAB" — an
        # uppercase X that matches nothing — so every hex-keyed line (92,149 of them, 58,302
        # of which do resolve) silently dropped out, and the only survivors for a common term
        # like "Color" were joaat collisions from dead labels. The map then looked authoritative
        # and was garbage ('Color' -> 'ויקיופ').
        h = key.lower() if key.lower().startswith("0x") else ("0x%08x" % joaat(key))
        en = (en_by_hash.get(h) or "").strip()
        if en and len(en) <= 40 and he.strip():
            pool[en][he.strip()] += 1
    out = {}
    for en, forms in pool.items():
        total = sum(forms.values())
        # ⚠️ A single supporting line is NOT authority: a dead label whose joaat collides with a
        # live entry produces exactly one confident-looking wrong pair. Require real support —
        # two INDEPENDENT lines agreeing is already out of reach for a lone collision.
        if total < 2:
            continue
        best, n = forms.most_common(1)[0]
        if (total == 2 and n == 2) or (total >= 3 and n * 2 > total):
            out[en] = best
    print(f"[est] {len(out):,} settled terms from the shipping corpus")
    return out


def classify(k, en, he):
    """'' when the line is fine, else (kind, repaired_or_None)."""
    if not he or not he.strip():
        return "empty", None
    if NIQ.search(he):                                   # deterministic: strip
        return "niqqud", NIQ.sub("", he).strip()
    if PANEL.search(he):                                 # the model echoed the reference panel
        body = [ln for ln in he.splitlines() if not PANEL.match(ln)]
        body = "\n".join(body).strip()
        return "panel-leak", (body if body and HEB.search(body) else None)
    if FOREIGN.search(he):
        return "foreign", None
    if sorted(STRUCT.findall(he)) != sorted(STRUCT.findall(en)):
        return "token-mismatch", None
    core = STRUCT.sub(" ", en)
    if set(DIG.findall(STRUCT.sub(" ", he))) - set(DIG.findall(core)):
        return "invented-number", None
    bare = he.lstrip(CTRL).strip()
    if LOWER.search(core) and not HEB.search(he) and bare != en.strip():
        # A no-Hebrew answer is CORRECT for three classes, and the gate must know all three
        # or it re-queues its own good work: a URL/domain/email, a proper-noun passthrough,
        # and an English ordinal suffix (`6th` -> `6` — a Hebrew date is bare, and the game's
        # own Russian agrees). This gate is `valid()` re-run over the merged bank, so any
        # exemption the worker has must exist here too.
        if ORD.match(en.strip()) and he.strip() == ORD.match(en.strip()).group(1):
            return "", None
        if URLISH.match(en.strip()) or NAMEY(en):
            return "", None
        return "no-hebrew", None
    return "", None


def main():
    apply = "--apply" in sys.argv
    heb = json.load(open(BANK, encoding="utf-8"))
    cor = json.load(open(CORPUS, encoding="utf-8"))
    print(f"bank {len(heb):,} / corpus {len(cor):,}")

    # ---- 1. structural ---------------------------------------------------------------
    repaired, requeue = {}, {}
    kinds = Counter()
    for k, v in heb.items():
        en = en_of(cor.get(k))
        kind, fix = classify(k, en, v)
        if not kind:
            continue
        kinds[kind] += 1
        if fix:
            repaired[k] = fix
        else:
            requeue[k] = (en, v)
    print("\nstructural:")
    for kind, n in kinds.most_common():
        print(f"  {kind:18} {n}")
    print(f"  -> repairable {len(repaired)} · re-queue {len(requeue)}")

    # ---- 2. consistency --------------------------------------------------------------
    # 🔑 The authority is the 217k lines ALREADY IN THE GAME, not a vote among 21 fresh
    # streams: a term like "Lawman" or "Stranger" has had a settled Hebrew form for months,
    # and a new line that disagrees with it is the defect — even when it is the local
    # majority. The established corpus is consulted first, the vote only breaks what it
    # does not cover.
    est = established_map()
    # Only short UI-ish strings: for a full sentence two different renderings are normal.
    by_en = defaultdict(list)
    for k, v in heb.items():
        en = en_of(cor.get(k)).strip()
        if en and len(en) <= 40 and k not in requeue:
            by_en[en].append((k, repaired.get(k, v)))
    diverged, canon, from_est = 0, {}, 0
    for en, rows in by_en.items():
        forms = Counter(v for _k, v in rows)
        if len(forms) == 1 and en not in est:
            continue
        best = None
        if en in est:
            best = est[en]                            # the form already shipping in-game
            if best in forms or len(forms) > 1:
                from_est += 1
            else:
                best = None                           # every stream agreed on something else
        if best is None:
            if len(forms) == 1:
                continue
            cand, n = forms.most_common(1)[0]
            if n > 1 and n * 2 > len(rows):            # a real majority, not a 1-1 tie
                best = cand
        if best is None:
            diverged += 1
            continue
        if len(forms) > 1:
            diverged += 1
        for k, v in rows:
            if v != best:
                canon[k] = best
    print(f"\nconsistency: {diverged} English terms rendered >1 way; "
          f"{len(canon)} lines unified ({from_est} against the already-shipping corpus)")

    if not apply:
        print("\n(report only — pass --apply to write)")
        for k, (en, v) in list(requeue.items())[:10]:
            print(f"  requeue {k}: {en!r} -> {v!r}")
        return

    # ---- write -----------------------------------------------------------------------
    ts = time.strftime("%Y%m%d_%H%M%S")
    shutil.copy2(BANK, f"{BANK}.bak.qa.{ts}")
    for k, v in repaired.items():
        heb[k] = v
    for k, v in canon.items():
        heb[k] = v
    for k in requeue:
        heb.pop(k, None)
    tmp = BANK + ".tmp"
    json.dump(heb, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(tmp, BANK)
    print(f"\nwrote {len(heb):,} lines "
          f"(+{len(repaired)} repaired, +{len(canon)} unified, -{len(requeue)} re-queued)")

    # a worker never re-serves a key already in its own out.json -> delete it there too
    ids = list(requeue)
    json.dump(ids, open(os.path.join(HERE, "requeue_ids.json"), "w"), ensure_ascii=False)
    removed = 0
    for f in sorted(os.listdir(BANKS)) if os.path.isdir(BANKS) else []:
        if not f.startswith("out_") or not f.endswith(".json"):
            continue
        p = os.path.join(BANKS, f)
        try:
            d = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        n = sum(1 for k in ids if d.pop(k, None) is not None)
        if n:
            json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False)
            removed += n
    print(f"cleared {removed} of the re-queued keys from the local bank copies")
    print("⚠️  the same keys must also be removed from each machine's C:\\rdrw\\out_*.json "
          "(requeue_ids.json) before the workers will re-serve them")


if __name__ == "__main__":
    main()
