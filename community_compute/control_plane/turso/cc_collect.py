"""OPERATOR — pull finished lines out of the Turso cc queue THROUGH A QA GATE.

Volunteer output is UNTRUSTED: the Hogwarts run proved a device can mark a line
'done' while returning a leaked reference panel, the untranslated Arabic/English
reference, or text with dropped engine tokens — `done` is NOT a quality signal.
So every returned line is classified here:

  ok         -> merged into --out (the file the build consumes)
  passthrough-> kept as-is (pure token / ALL-CAPS brand / no-letter): legitimate
  recover    -> a leaked panel that strips DETERMINISTICALLY to one clean body
  requeue    -> defective (panel leak, untranslated echo, token drift, empty)
                -> reset to 'open' so the fleet redoes it (never silently shipped)

Usage:
  python cc_collect.py --game skyrim --out hebrew.json [--apply] [--src-en en.json]
    (dry-run by default; --apply writes the file, marks collected, re-queues the bad)"""
import argparse, json, os, re, time
import turso_client as tc

HEB = re.compile(r"[֐-׿]")
NIQQUD = re.compile(r"[֑-ׇ]")
LATIN = re.compile(r"[A-Za-z]")
ARABIC = re.compile(r"[؀-ۿ]")
CJK = re.compile(r"[　-鿿가-힯]")
# 🔴 The New-Era panel hands the model the game's OWN ru/pl/de/… lines, so the most likely
# "untranslated" failure is echoing one of THOSE, not the English. Cyrillic is the one that a
# Latin-only check silently misses (Crimson Desert's panel leads with Russian).
CYRILLIC = re.compile(r"[Ѐ-ӿ]")
LABEL = re.compile(r"^\s*(EN|AR|RU|PL|CS|ES|ES-MX|FR|IT|PT|DE|JA|KO|ZH|HE|CURRENT)\s*:", re.I | re.M)
TOKEN = re.compile(r"(\{[^{}]{0,60}\}|<[^<>]{1,60}>|%[sdifux]|\[[A-Z0-9_]{2,30}\]|&[a-z]+;)")


def strip_labels(s):
    """A leaked panel -> the lines that are NOT 'XX: ...' reference rows."""
    keep = [ln for ln in s.splitlines() if not LABEL.match(ln)]
    return "\n".join(keep).strip()


def unwrap_json(s):
    """A model that answered `{"he": "..."}` INSTEAD of the bare string.

    The prompt asks for `{id: hebrew}` and the app already extracts the id, so a value
    that is ITSELF a JSON object is a model formatting slip, not a translation error —
    the Hebrew inside is fine. That has exactly ONE correct answer, so REPAIR it instead
    of throwing a good translation away. Only unwraps an unambiguous single Hebrew value.
    [[repair-dont-reject-and-pid-is-not-identity]]
    """
    t = s.strip()
    if not (t.startswith("{") and t.endswith("}")):
        return s
    try:
        d = json.loads(t)
    except Exception:
        return s
    if not isinstance(d, dict):
        return s
    vals = [v.strip() for v in d.values() if isinstance(v, str) and HEB.search(v)]
    return vals[0] if len(vals) == 1 else s


def classify(out, src):
    o = (out or "").strip()
    if not o:
        return "requeue", "empty", o
    o2 = unwrap_json(o)
    unwrapped = o2 != o
    o = o2
    # 🔴 token multiset must survive (engine tokens are load-bearing) — and the check runs
    # in BOTH directions. `if want and want != got` skipped it entirely whenever the ENGLISH
    # had no tokens, so a model that ADDED braces/tags to a clean line passed silently (a
    # device shipped `{"he": "כלי רכב"}` for "Vehicle" straight through this gate). A
    # one-directional guard is half a guard.
    if src is not None:
        want, got = sorted(TOKEN.findall(src or "")), sorted(TOKEN.findall(o))
        if want != got:
            return "requeue", "token-drift", o
    if NIQQUD.search(o):
        o2 = NIQQUD.sub("", o)
        return ("ok", "niqqud-stripped", o2) if HEB.search(o2) else ("requeue", "niqqud-only", o)
    if LABEL.search(o):                      # a leaked reference panel
        body = strip_labels(o)
        if body and HEB.search(body) and not ARABIC.search(body) and not LABEL.search(body):
            return "recover", "panel-stripped", body
        return "requeue", "panel-leak", o
    if ARABIC.search(o) or CJK.search(o) or CYRILLIC.search(o):
        return "requeue", "foreign-script", o
    if HEB.search(o):
        return ("recover", "json-unwrapped", o) if unwrapped else ("ok", "", o)
    # no Hebrew: legitimate only if it is a pure token / brand / non-word
    core = TOKEN.sub("", o).strip()
    if not core or not LATIN.search(core) or not re.search(r"[a-z]", core):
        return "passthrough", "token-or-brand", o
    return "requeue", "untranslated-english", o


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", required=True)
    ap.add_argument("--out", default="")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    rows = tc.run([("SELECT id, target, out, src FROM cc_lines WHERE game=? AND status='done' AND collected=0",
                    [a.game])])[0]["rows"]
    print(f"{len(rows):,} finished, uncollected lines for '{a.game}'")
    good, requeue, counts = {}, [], {}
    for r in rows:
        verdict, why, val = classify(r["out"], r["src"])
        counts[f"{verdict}:{why}" if why else verdict] = counts.get(f"{verdict}:{why}" if why else verdict, 0) + 1
        if verdict in ("ok", "recover", "passthrough"):
            good[r["target"]] = val
        else:
            requeue.append(r["id"])
    for k in sorted(counts):
        print(f"  {k:<28} {counts[k]:>7,}")
    print(f"\n  -> accept {len(good):,}   requeue {len(requeue):,}")

    if not a.apply:
        print("\n(dry-run — pass --apply to write + mark collected + re-queue the defective)")
        return
    if a.out:
        prev = {}
        if os.path.exists(a.out):
            prev = json.load(open(a.out, encoding="utf-8"))
            os.replace(a.out, a.out + f".bak.{int(time.time())}")
        prev.update(good)
        json.dump(prev, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"wrote {a.out} ({len(prev):,} total lines)")
    now = int(time.time())
    ids = [r["id"] for r in rows if r["target"] in good]
    for i in range(0, len(ids), 400):
        grp = ids[i : i + 400]
        tc.run([(f"UPDATE cc_lines SET collected=1, updated_at={now} WHERE id IN ({','.join('?' * len(grp))})", grp)])
    for i in range(0, len(requeue), 400):
        grp = requeue[i : i + 400]
        tc.run([(f"UPDATE cc_lines SET status='open', out=NULL, worker_id=NULL, lease_until=NULL, "
                 f"updated_at={now} WHERE id IN ({','.join('?' * len(grp))})", grp)])
    print(f"marked {len(ids):,} collected; re-queued {len(requeue):,} defective")


if __name__ == "__main__":
    main()
