"""Validate + record the FIXED lines (CP2077 fix-only flow). Unlike the review
flow there is NO "OK" — every line in the batch is objectively broken, so the
only accepted output is a corrected Hebrew line whose SAME defect is gone. This
is what makes it unfakeable: a script can't pass without actually repairing each
line.

Reads : fix_fixes.json {key: "corrected hebrew"}   (one entry per batch line)
        fix_batch.json, corpus.json
Writes: fix_corrections.json {key: corrected_hebrew}
        fix_done.json (keys with an accepted fix)
Rejects: identical-to-original, "OK"/empty, broken markup, changed tags/
placeholders, the SAME defect still present (foreign/seam/dangling), niqqud,
and the gaming patterns (whitespace-only / punct-append / pasted-English).
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

STRUCT = re.compile(r'<[^>]*>|\{[^}]*\}|%%|%[#0-9.*\-+ ]*[a-zA-Z]+|&[a-zA-Z#0-9]+;')
_EN_RUN = re.compile(r"[A-Za-z][A-Za-z'.\-]*(?:\s+[A-Za-z][A-Za-z'.\-]*){3,}")
OK_MARKS = {"ok", "okay", "fine", "תקין", "-", "same", "v", "✓"}


def P(n): return os.path.join(HERE, n)


def jload(p, d):
    try: return json.load(open(p, encoding="utf-8"))
    except Exception: return d


def struct_tokens(s):
    return Counter(STRUCT.findall(fd.strip_ctrl(s or "")))


def ws_only(old, new):
    o, n = fd.strip_ctrl(old or "").strip(), fd.strip_ctrl(new or "").strip()
    return o != n and re.sub(r"\s+", " ", o) == re.sub(r"\s+", " ", n)


def injected_english(en, old, new):
    o, n = fd.strip_ctrl(old or ""), fd.strip_ctrl(new or "")
    return any(m in en and m not in o for m in _EN_RUN.findall(n))


def main():
    # GUARD: this folder may hold ONLY the task files — no automation scripts anywhere.
    ALLOWED = {"corpus.json", "fix_get_batch.py", "fix_merge.py", "fix_defects.py",
               "fix_done.json", "fix_corrections.json", "fix_corrections.json.tmp",
               "fix_fixes.json", "fix_batch.json", "INSTRUCTIONS.md"}
    extra = sorted(os.path.basename(p) for p in glob.glob(P("*"))
                   if os.path.isfile(p) and os.path.basename(p) not in ALLOWED)
    if extra:
        print(f"ERROR: unexpected file(s) {extra}. NO scripts/temp files anywhere — read fix_batch.json "
              "and fix BY HAND. Delete it. Nothing saved.")
        sys.exit(1)
    repo = HERE
    for _ in range(6):
        if os.path.isdir(os.path.join(repo, "orchestration")) and os.path.isdir(os.path.join(repo, "games")):
            break
        nd = os.path.dirname(repo)
        if nd == repo: repo = None; break
        repo = nd
    if repo:
        deny = {"solve.py", "auto_qa.py", "gen_fixes.py", "do_translate.py", "fix.py", "process.py", "auto.py"}
        rb = sorted(n for n in deny if os.path.isfile(os.path.join(repo, n)))
        if rb:
            print(f"ERROR: agent-script(s) in the repo root: {rb}. Work BY HAND. Nothing saved.")
            sys.exit(1)

    corpus = jload(P("corpus.json"), {})
    fixes = jload(P("fix_fixes.json"), {})
    batch = jload(P("fix_batch.json"), [])
    corr = jload(P("fix_corrections.json"), {})
    done = set(jload(P("fix_done.json"), []))
    batch_keys = {str(r["key"]) for r in batch}
    if not batch_keys:
        print("ERROR: fix_batch.json missing/empty — run fix_get_batch.py first. Nothing saved.")
        sys.exit(1)

    ok = 0; bad = []
    for key, val in fixes.items():
        key = str(key)
        if key not in corpus:
            bad.append((key, "UNKNOWN KEY")); continue
        s = (val or "").strip()
        en = corpus[key]["en"]; orig = corpus[key]["he"]; defect = corpus[key].get("defect", "")
        if s.lower() in OK_MARKS or not s:
            bad.append((key, 'NO "OK" HERE — this line is broken, you MUST rewrite it correctly.')); continue
        if s == orig.strip() or s == orig:
            bad.append((key, "IDENTICAL to the broken original — actually fix it.")); continue
        if mk.parse_slots(s) is None:
            bad.append((key, "BROKEN MARKUP (parse failed)")); continue
        if struct_tokens(s) != struct_tokens(orig):
            bad.append((key, "TAG/PLACEHOLDER MISMATCH — copy every <tag>/{value}/%spec verbatim.")); continue
        if ws_only(orig, s):
            bad.append((key, "WHITESPACE-ONLY change — not a fix.")); continue
        if injected_english(en, orig, s):
            bad.append((key, "ENGLISH PASTED IN — translate it to Hebrew, don't append the source.")); continue
        if fd.NIQQUD.search(s):
            bad.append((key, "NIQQUD — remove vowel points.")); continue
        c = fd.core(s)
        # the SAME defect must be gone in the fix:
        if defect == "foreign" and fd.FOREIGN.search(c):
            bad.append((key, "FOREIGN SCRIPT still present — translate that word to Hebrew.")); continue
        if defect == "seam" and fd.SEAM.search(c):
            bad.append((key, "Hebrew+Latin still GLUED — fix the transliteration / add a space.")); continue
        if defect == "truncated" and fd.DANGLING.search(fd.visible(s)):
            bad.append((key, "still ends on a dangling connector — COMPLETE the sentence.")); continue
        if not fd.HEB.search(s):
            bad.append((key, "no Hebrew — this must be a Hebrew line.")); continue
        corr[key] = s; done.add(key); ok += 1

    if bad:
        for key, r in bad[:60]:
            print(f"REJECT {r} :: {key} he={corpus.get(key,{}).get('he','')[:45]!r}")
        print(f"--- {len(bad)} rejected — fix ONLY those in fix_fixes.json, re-run fix_merge ---")
    if ok:
        json.dump(corr, open(P("fix_corrections.json") + ".tmp", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
        os.replace(P("fix_corrections.json") + ".tmp", P("fix_corrections.json"))
    json.dump(sorted(done), open(P("fix_done.json"), "w", encoding="utf-8"), ensure_ascii=False)

    missing = batch_keys - set(corr.keys()) - {k for k in done if k in batch_keys}
    really_missing = batch_keys - done
    print(f"accepted {ok} fixes (total {len(corr)}); done {len(batch_keys & done)}/{len(batch_keys)} of this batch "
          f"(total fixed {len(done)})")
    if really_missing:
        print(f"WARN {len(really_missing)} line(s) NOT fixed yet -> they RE-APPEAR until each has a valid fix.")


if __name__ == "__main__":
    main()
