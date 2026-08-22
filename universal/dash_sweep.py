#!/usr/bin/env python3
"""
dash_sweep.py - retroactively apply the IRON RULE (plain `-`, never `—`) to a Hebrew
corpus that was translated BEFORE the rule existed.

The rule itself lives in `universal/text_norm.py` and is enforced at BUILD time from now
on, so a new line can never carry a long dash. This tool is the one-time catch-up for the
~431k lines already translated.

🔴 VALUES ONLY, NEVER KEYS. Several corpora are keyed by the ENGLISH SOURCE STRING
(`games/gtav/agent_handoff_full/reuse_he.json`, and every md5(EN)-keyed pool). Rewriting a
key silently orphans that line from the build - it stops matching and ships English. So
the walker rewrites leaf VALUES and copies every key verbatim.

⚠️ A corpus change is NOT visible in-game until that game is RE-BAKED. This tool touches
the source of truth only; it never deploys.

Verified safe before first use: across 11 shipped corpora only 3 long dashes sat inside a
`[...]`, and all three were AC2 translator PROSE (a stage direction the player reads), not
an engine token - so normalising them is correct. Re-run `--check-tokens` on any new corpus.

CLI:
    python dash_sweep.py <file.json> [more.json ...]           # dry run, reports only
    python dash_sweep.py --apply <file.json> [...]             # backup + rewrite
    python dash_sweep.py --check-tokens <file.json> [...]      # token-safety audit
"""
import json
import os
import re
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from text_norm import LONG_DASHES, has_long_dash, normalize_dashes  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TOKEN = re.compile(r"<[^<>]{1,80}>|\{[^{}]{0,80}\}|\[[^\[\]]{0,80}\]|~[^~]{0,40}~|%[#0-9.*\-+]*[a-zA-Z]")


def _walk_values(obj, fix, stats):
    """Rebuild `obj` with every leaf STRING VALUE normalised. Keys are copied verbatim."""
    if isinstance(obj, str):
        stats["values"] += 1
        out = fix(obj)
        if out != obj:
            stats["changed"] += 1
        return out
    if isinstance(obj, dict):
        return {k: _walk_values(v, fix, stats) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_walk_values(v, fix, stats) for v in obj]
    return obj


def check_tokens(path):
    data = json.load(open(path, encoding="utf-8"))
    hits = []

    def scan(o):
        if isinstance(o, str):
            if has_long_dash(o):
                for t in TOKEN.findall(o):
                    if any(c in LONG_DASHES for c in t):
                        hits.append(t)
        elif isinstance(o, dict):
            for v in o.values():
                scan(v)
        elif isinstance(o, list):
            for v in o:
                scan(v)

    scan(data)
    return hits


def sweep(path, apply=False):
    data = json.load(open(path, encoding="utf-8"))
    stats = {"values": 0, "changed": 0}
    new = _walk_values(data, normalize_dashes, stats)
    if apply and stats["changed"]:
        bak = "%s.bak.dash.%s" % (path, time.strftime("%Y%m%d_%H%M%S"))
        shutil.copy2(path, bak)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(new, fh, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
        # read back: the rule must actually hold on disk
        left = sum(1 for v in _iter_values(json.load(open(path, encoding="utf-8"))) if has_long_dash(v))
        stats["residual"] = left
    return stats


def _iter_values(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for v in o.values():
            yield from _iter_values(v)
    elif isinstance(o, list):
        for v in o:
            yield from _iter_values(v)


def main(argv):
    apply = "--apply" in argv
    tokens = "--check-tokens" in argv
    files = [a for a in argv if not a.startswith("--")]
    if not files:
        print(__doc__)
        return 2
    total = changed = 0
    for f in files:
        if not os.path.exists(f):
            print("MISSING  " + f)
            continue
        if tokens:
            hits = check_tokens(f)
            print("%-58s tokens-with-long-dash=%d" % (os.path.relpath(f), len(hits)))
            for h in hits[:5]:
                print("    " + repr(h))
            continue
        st = sweep(f, apply=apply)
        total += st["values"]
        changed += st["changed"]
        extra = ""
        if "residual" in st:
            extra = "  residual=%d %s" % (st["residual"], "OK" if st["residual"] == 0 else "!!")
        print("%-58s values=%-8d fixed=%-6d%s" % (os.path.relpath(f), st["values"], st["changed"], extra))
    if not tokens:
        print("\n%s %d of %d values" % ("FIXED" if apply else "WOULD FIX", changed, total))
        if not apply:
            print("(dry run - pass --apply to write, a .bak.dash.<ts> is kept)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
