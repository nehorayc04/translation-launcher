"""qa_v17_apply.py — apply the workflow's adversarially-verified Hebrew fixes,
with a STRONG markup-preservation guard. Never lets an AI fix corrupt structure.

Reads a JSON file: either {confirmed:[{key,fix,...}]} or a bare list [{key,fix}].
For each fix:
  - locate the key's *_he.json file,
  - GUARD: the fix must preserve, vs the ORIGINAL he value:
      * every [TOKEN] (set, no loss),
      * the count of <br>, <span, </span>, &rlm;, &nbsp;,
      * the multiset of printf specifiers (%d/%s/%%/...),
    else SKIP + report,
  - strip any niqqud from the fix (defensive),
  - apply.

Backs up each changed file to <name>.bak.aiqa before writing.
Usage: python qa_v17_apply.py <fixes.json> [--dry-run]
"""
import os, sys, json, glob, re, shutil, unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)

def out(*a):
    sys.stdout.write(" ".join(str(x) for x in a).encode("ascii", "backslashreplace").decode() + "\n")

TOK = re.compile(r'\[[A-Z0-9_]+\]')
SPEC = re.compile(r'%[-+ #0]*\d*(?:\.\d+)?[diouxXeEfFgGaAcspn%]')

def counts(s):
    return {
        'br': len(re.findall(r'<br\s*/?>', s, re.I)),
        'span_o': len(re.findall(r'<span\b', s, re.I)),
        'span_c': len(re.findall(r'</span>', s, re.I)),
        'rlm': s.count('&rlm;'),
        'nbsp': s.count('&nbsp;'),
    }

def strip_niqqud(s):
    return ''.join(c for c in s if not (0x0591 <= ord(c) <= 0x05C7 and unicodedata.category(c) == 'Mn'))

def guard(orig, fix):
    """Return (ok, reason). Fix must preserve all markup vs orig."""
    lost_tok = set(TOK.findall(orig)) - set(TOK.findall(fix))
    if lost_tok:
        return False, f"drops token {sorted(lost_tok)}"
    co, cf = counts(orig), counts(fix)
    for kk in co:
        if co[kk] != cf[kk]:
            return False, f"{kk} count {co[kk]}->{cf[kk]}"
    if sorted(SPEC.findall(orig)) != sorted(SPEC.findall(fix)):
        return False, f"printf specs {sorted(SPEC.findall(orig))}->{sorted(SPEC.findall(fix))}"
    return True, ""

def main():
    path = sys.argv[1]
    dry = "--dry-run" in sys.argv
    data = json.load(open(path, encoding="utf-8"))
    fixes = data.get("confirmed", data) if isinstance(data, dict) else data

    files = sorted(glob.glob("menus*_he.json")) + ["settings_he.json"]
    store, docs = {}, {}
    for fn in files:
        d = json.load(open(fn, encoding="utf-8"))
        docs[fn] = d
        for k in d:
            store[k] = fn

    applied = skipped = missing = noop = 0
    skip_list = []
    touched = set()
    # de-dupe: last fix per key wins
    bykey = {}
    for it in fixes:
        if isinstance(it, dict) and it.get("key") and it.get("fix") is not None:
            bykey[it["key"]] = it["fix"]

    for k, fix in bykey.items():
        fn = store.get(k)
        if fn is None:
            missing += 1; continue
        orig = docs[fn][k]
        fix = strip_niqqud(fix)
        if fix == orig:
            noop += 1; continue
        ok, why = guard(orig, fix)
        if not ok:
            skipped += 1; skip_list.append((k, why)); continue
        if not dry:
            docs[fn][k] = fix
        touched.add(fn); applied += 1

    if not dry:
        for fn in touched:
            shutil.copyfile(fn, fn + ".bak.aiqa")
            json.dump(docs[fn], open(fn, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    out(f"applied: {applied}")
    out(f"skipped (guard): {skipped}")
    for k, why in skip_list:
        out(f"   SKIP {k}  ({why})")
    out(f"no-op (fix==orig): {noop}")
    out(f"missing keys: {missing}")
    out(f"files touched: {len(touched)}")

if __name__ == "__main__":
    main()
