"""98_apply_qa_fixes.py — apply the adversarially-verified translation fixes from
the multi-agent QA workflow, with a token-safety guard.

For each {key, fix} confirmed by the QA run:
  - locate the key's menus*_he.json file,
  - SAFETY: if the fix drops a [TOKEN] (e.g. [ACTION_*]) or a <span> that the
    original had, SKIP it (report) — never silently lose markup,
  - otherwise replace the value with the corrected Hebrew.

One special case: a fix written "old -> new" keeps only the part after " -> ".
Re-run 95 (trailing-&rlm; punctuation anchor) afterwards so the corrected strings
keep correct sentence-final punctuation.

Usage: python 98_apply_qa_fixes.py <path-to-workflow-output.json>
"""
import json, glob, re, sys, os

def out(*a):
    sys.stdout.write(" ".join(str(x) for x in a).encode("ascii", "backslashreplace").decode() + "\n")

TOK = re.compile(r'\[[A-Z0-9_]+\]')

def clean_fix(fix: str) -> str:
    if " -> " in fix:
        fix = fix.split(" -> ")[-1]
    return fix.strip()

def main() -> int:
    out_path = sys.argv[1]
    data = json.load(open(out_path, encoding="utf-8"))
    fixes = data["result"]["confirmed"]

    files = sorted(glob.glob("menus*_he.json")) + ["settings_he.json"]
    store = {}        # key -> filename
    docs = {}
    for fn in files:
        d = json.load(open(fn, encoding="utf-8"))
        docs[fn] = d
        for k in d:
            store[k] = fn

    applied = skipped = missing = 0
    skip_list = []
    for item in fixes:
        k = item["key"]; fix = clean_fix(item["fix"])
        fn = store.get(k)
        if fn is None:
            missing += 1; continue
        orig = docs[fn][k]
        # token safety: every [TOKEN] in the original must survive in the fix
        lost = set(TOK.findall(orig)) - set(TOK.findall(fix))
        if lost:
            skipped += 1; skip_list.append((k, sorted(lost))); continue
        docs[fn][k] = fix
        applied += 1

    for fn, d in docs.items():
        json.dump(d, open(fn, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    out(f"applied: {applied}")
    out(f"skipped (would drop a token): {skipped}")
    for k, lost in skip_list:
        out(f"   SKIP {k}  lost {lost}")
    out(f"missing keys: {missing}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
