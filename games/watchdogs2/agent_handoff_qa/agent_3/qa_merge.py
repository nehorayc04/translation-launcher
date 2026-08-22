"""Validate + record the agent's QA review of a batch. Does NOT translate.

ATTESTATION CONTRACT (anti-cheat): qa_fixes.json must carry an entry for EVERY pk
in the batch — either the corrected Hebrew (a real fix) OR the literal "OK"
(read it, it's fine). A pk is marked reviewed ONLY when it is attested here.
An empty / partial / `{}` file advances NOTHING, so a script that blindly writes
`{}` can never make the loop reach "QA done!" — the same batch returns forever.

Reads  : qa_fixes.json {pk: "corrected hebrew" | "OK"}   (one entry PER batch line)
         qa_batch.json  (the batch under review)
         corpus.json
Writes : corrections.json  {pk: corrected_hebrew}   (accumulates accepted fixes)
         qa_reviewed.json  (adds ONLY the pks attested in qa_fixes)
Reports rejected fixes + un-attested lines; fix those, re-run; then DELETE qa_fixes.json.
"""
import json, os, re
from collections import Counter
HERE = os.path.dirname(os.path.abspath(__file__))
def P(n): return os.path.join(HERE, n)

# preserved structural tokens (must survive a correction unchanged)
TOKEN = re.compile(r'\[[A-Za-z0-9_]+\]|\{[^}]*\}|%[0-9.]*[diufslxeDIUFSLXE]+|%%|&#?[A-Za-z0-9]+;')
NL    = re.compile(r'\\n')
NIQQUD = re.compile(r'[֑-ׇ]')
BAD    = re.compile(r'[؀-ۿЀ-ӿͰ-Ͽ฀-๿ऀ-ॿ一-鿿가-힯぀-ヿ]')
HEB    = re.compile(r'[א-ת]')

# "this line is fine, no change" markers (case/space tolerant)
OK_MARKS = {"ok", "okay", "fine", "✓", "v", "תקין", "good", "-", "same"}

def toks(s): return Counter(TOKEN.findall(s) + NL.findall(s))
def is_namey(en):
    core = TOKEN.sub("", en).strip()
    words = re.findall(r"[A-Za-z][A-Za-z'.\-]*", core)
    return (bool(words) and len(words) <= 4 and all(w[0].isupper() for w in words)) \
        or not re.search(r'[a-z]{2,}', core)

def main():
    corpus = json.load(open(P("corpus.json"), encoding="utf-8"))
    fixes = json.load(open(P("qa_fixes.json"), encoding="utf-8")) if os.path.exists(P("qa_fixes.json")) else {}
    batch = json.load(open(P("qa_batch.json"), encoding="utf-8")) if os.path.exists(P("qa_batch.json")) else []
    corr = json.load(open(P("corrections.json"), encoding="utf-8")) if os.path.exists(P("corrections.json")) else {}
    batch_pks = {str(r["pk"]) for r in batch}
    he_by_pk = {str(r["pk"]): r.get("he", "") for r in batch}

    ok = 0; bad = []; attested = set()
    for pk, val in fixes.items():
        pk = str(pk)
        if pk not in corpus: bad.append((pk, "UNKNOWN PK")); continue
        s = (val or "").strip()
        if s.lower() in OK_MARKS:                       # "OK" = read, no change
            attested.add(pk); continue
        if not s: bad.append((pk, "EMPTY (use \"OK\" if the line is fine)")); continue
        en = corpus[pk]["en"]
        # the agent re-typed the existing translation verbatim -> treat as OK
        if s == (he_by_pk.get(pk) or "").strip():
            attested.add(pk); continue
        if toks(s) != toks(en):
            bad.append((pk, "TOKEN/LINEBREAK MISMATCH vs EN")); continue
        if BAD.search(s): bad.append((pk, "FOREIGN SCRIPT")); continue
        if NIQQUD.search(s): bad.append((pk, "NIQQUD")); continue
        if not HEB.search(s) and not is_namey(en):
            bad.append((pk, "NO HEBREW (and source is not a name/code)")); continue
        corr[pk] = s; attested.add(pk); ok += 1

    if bad:
        for pk, r in bad[:60]:
            print(f"REJECT {r} :: {pk} en={corpus.get(pk,{}).get('en','')[:50]!r}")
        print(f"--- {len(bad)} rejected — fix ONLY those in qa_fixes.json, re-run qa_merge ---")
    if ok:
        json.dump(corr, open(P("corrections.json")+".tmp", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
        os.replace(P("corrections.json")+".tmp", P("corrections.json"))

    # mark reviewed ONLY the attested pks that belong to this batch
    review_now = {pk for pk in attested if pk in batch_pks} if batch_pks else attested
    reviewed = set(json.load(open(P("qa_reviewed.json"), encoding="utf-8"))) if os.path.exists(P("qa_reviewed.json")) else set()
    reviewed |= review_now
    json.dump(sorted(reviewed, key=int), open(P("qa_reviewed.json"), "w", encoding="utf-8"), ensure_ascii=False)

    missing = batch_pks - attested
    print(f"accepted {ok} corrections (total {len(corr)}); attested {len(review_now)}/{len(batch_pks)} "
          f"of this batch (total reviewed {len(reviewed)})")
    if missing:
        print(f"WARN {len(missing)} line(s) NOT attested -> they RE-APPEAR until you add an entry "
              f"(a fix, or \"OK\") for EVERY pk. Writing {{}} advances nothing.")

if __name__ == "__main__":
    main()
