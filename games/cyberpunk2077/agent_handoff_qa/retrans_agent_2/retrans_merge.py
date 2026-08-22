"""Validate + record a fresh dual-gender RE-TRANSLATION (CP2077). The agent
translates each English line from scratch and gives BOTH variants:
  { "key": {"f": "<female-V Hebrew>", "m": "<male-V Hebrew>"} }
CP2077 lets the player be female V (engine -> femaleVariant) or male V (-> male
Variant). For impersonal lines f and m are identical; for lines that address or
are spoken by V they differ in grammatical gender. There is no "OK" and the
source is English, so a script can't fake it.

Reads : retrans_fixes.json {key: {"f":..,"m":..}}   (one per batch line)
        retrans_batch.json, corpus.json
Writes: retrans_corrections.json {key: {"f":..,"m":..}}, retrans_done.json
Rejects per variant: empty/"OK", identical-to-English, no Hebrew, changed/dropped
tags vs the source, foreign script, niqqud, absurd length.
"""
import json, os, re, sys, glob
from collections import Counter
HERE = os.path.dirname(os.path.abspath(__file__))
for cand in (os.path.dirname(os.path.dirname(HERE)), os.path.dirname(HERE)):
    if os.path.exists(os.path.join(cand, "cp2077_markup_translate.py")):
        sys.path.insert(0, cand)
        break
import cp2077_markup_translate as mk
sys.path.insert(0, HERE)
import fix_defects as fd

STRUCT = re.compile(r'<[^>]*>|\{[^}]*\}|%%|%[#0-9.*\-+]*[a-zA-Z]+|&[a-zA-Z#0-9]+;')
OK_MARKS = {"ok", "okay", "fine", "תקין", "-", "same", "v", "✓"}


def P(n): return os.path.join(HERE, n)


def jload(p, d):
    try: return json.load(open(p, encoding="utf-8"))
    except Exception: return d


def st(s): return Counter(STRUCT.findall(fd.strip_ctrl(s or "")))


def is_namey(en):
    core = re.sub(r'<[^>]*>|\{[^}]*\}', "", en).strip()
    words = re.findall(r"[A-Za-z][A-Za-z'.\-]*", core)
    return (bool(words) and len(words) <= 4 and all(w[0].isupper() for w in words)) \
        or not re.search(r'[a-z]{2,}', core)


def check_variant(s, en, label):
    """Return an error string for variant value s, or None if valid."""
    s = (s or "").strip()
    if s.lower() in OK_MARKS or not s:
        return f'{label}: empty / "OK" — translate the line into Hebrew.'
    if s == en.strip() or s == en:
        return f"{label}: identical to the English — translate it."
    ve = fd.visible(en)
    if len(ve) >= 12 and ve in fd.visible(s):
        return f"{label}: contains the WHOLE English source verbatim — actually TRANSLATE it, don't append the English."
    if mk.parse_slots(s) is None:
        return f"{label}: BROKEN MARKUP."
    if st(s) != st(en):
        return f"{label}: TAG/PLACEHOLDER MISMATCH vs the source."
    if fd.FOREIGN.search(fd.core(s)):
        return f"{label}: FOREIGN SCRIPT."
    if fd.NIQQUD.search(s):
        return f"{label}: NIQQUD."
    if not fd.HEB.search(s) and not is_namey(en):
        return f"{label}: NO HEBREW."
    ve, vs = len(fd.visible(en)), len(fd.visible(s))
    if ve > 25 and vs * 2.6 < ve:
        return f"{label}: TOO SHORT vs the English."
    if ve > 12 and vs > ve * 2.6 + 30:
        return f"{label}: TOO LONG vs the English."
    return None


def main():
    ALLOWED = {"corpus.json", "retrans_get_batch.py", "retrans_merge.py", "fix_defects.py",
               "retrans_done.json", "retrans_corrections.json", "retrans_corrections.json.tmp",
               "retrans_fixes.json", "retrans_batch.json", "INSTRUCTIONS.md"}
    extra = sorted(os.path.basename(p) for p in glob.glob(P("*"))
                   if os.path.isfile(p) and os.path.basename(p) not in ALLOWED)
    if extra:
        print(f"ERROR: unexpected file(s) {extra}. NO scripts — translate BY HAND. Delete it. Nothing saved.")
        sys.exit(1)
    repo = HERE
    for _ in range(6):
        if os.path.isdir(os.path.join(repo, "orchestration")) and os.path.isdir(os.path.join(repo, "games")):
            break
        nd = os.path.dirname(repo)
        if nd == repo: repo = None; break
        repo = nd
    if repo:
        deny = {"solve.py", "auto_qa.py", "gen_fixes.py", "do_translate.py", "fix.py", "process.py", "auto.py", "translate.py"}
        rb = sorted(n for n in deny if os.path.isfile(os.path.join(repo, n)))
        if rb:
            print(f"ERROR: agent-script(s) in the repo root: {rb}. Translate BY HAND. Nothing saved.")
            sys.exit(1)

    corpus = jload(P("corpus.json"), {})
    fixes = jload(P("retrans_fixes.json"), {})
    batch = jload(P("retrans_batch.json"), [])
    corr = jload(P("retrans_corrections.json"), {})
    done = set(jload(P("retrans_done.json"), []))
    batch_keys = {str(r["key"]) for r in batch}
    if not batch_keys:
        print("ERROR: retrans_batch.json missing/empty — run retrans_get_batch.py first. Nothing saved.")
        sys.exit(1)
    if len(batch) > 30:
        print(f"ERROR: retrans_batch.json has {len(batch)} lines (max 30). retrans_get_batch.py was modified "
              "to enlarge the batch — restore SIZE=20 and translate carefully, batch by batch. Nothing saved.")
        sys.exit(1)

    ok = 0; bad = []
    for key, val in fixes.items():
        key = str(key)
        if key not in corpus:
            bad.append((key, "UNKNOWN KEY")); continue
        if not isinstance(val, dict) or "f" not in val or "m" not in val:
            bad.append((key, 'FORMAT: give {"f":"<female Hebrew>","m":"<male Hebrew>"} for this key.')); continue
        en = corpus[key]["en"]
        ef = check_variant(val.get("f", ""), en, "female(f)")
        if ef:
            bad.append((key, ef)); continue
        em = check_variant(val.get("m", ""), en, "male(m)")
        if em:
            bad.append((key, em)); continue
        corr[key] = {"f": val["f"].strip(), "m": val["m"].strip()}
        done.add(key); ok += 1

    if bad:
        for key, r in bad[:60]:
            print(f"REJECT {r} :: {key} en={corpus.get(key,{}).get('en','')[:48]!r}")
        print(f"--- {len(bad)} rejected — fix ONLY those in retrans_fixes.json, re-run retrans_merge ---")
    if ok:
        json.dump(corr, open(P("retrans_corrections.json") + ".tmp", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
        os.replace(P("retrans_corrections.json") + ".tmp", P("retrans_corrections.json"))
    json.dump(sorted(done), open(P("retrans_done.json"), "w", encoding="utf-8"), ensure_ascii=False)

    missing = batch_keys - done
    print(f"accepted {ok} dual-gender translations (total {len(corr)}); done {len(batch_keys & done)}/{len(batch_keys)} "
          f"of this batch (total {len(done)})")
    if missing:
        print(f"WARN {len(missing)} line(s) not done -> they RE-APPEAR until each has a valid {{f,m}} pair.")


if __name__ == "__main__":
    main()
