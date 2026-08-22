"""Validate + record the agent's QA review of a batch (CP2077). Does NOT translate.

ATTESTATION CONTRACT (anti-cheat): qa_fixes.json must carry an entry for EVERY
key in the batch — the corrected Hebrew (a real fix) OR the literal "OK" (read
it, it's fine). A key is marked reviewed ONLY when attested here. An empty /
partial / {} file advances NOTHING.

THREE hard guards against scripted "mark everything OK without reading":
  1. NO auto-runner scripts in the folder (only qa_get_batch.py + qa_merge.py).
  2. batch size is LOCKED to CANON_SIZE — a modified qa_get_batch.py is rejected.
  3. FIX-DENSITY floor — the CP2077 Hebrew genuinely has ~10% errors, so a review
     that produces ~0 corrections over hundreds of lines is not a real review:
     warns at 300 reviewed, HARD-BLOCKS (records nothing) at 600 reviewed if the
     correction rate is < 1%. A pure-"OK" run can therefore never reach "QA done!".

Reads  : qa_fixes.json {key: "corrected hebrew" | "OK"}   (one entry PER batch line)
         qa_batch.json, corpus.json
Writes : corrections.json {key: corrected_hebrew}   (accumulates accepted fixes)
         qa_reviewed.json (adds ONLY attested batch keys)
Validation: corrected text must keep the SAME markup/placeholder slots as the
original (parse_slots), no foreign script, no niqqud, real Hebrew (unless the EN
source is a name/code). Then DELETE qa_fixes.json and loop.
"""
import json, os, re, sys, glob
from collections import Counter
HERE = os.path.dirname(os.path.abspath(__file__))
# cp2077_markup_translate.py lives at games/cyberpunk2077/ — two levels up from agent_K/
for cand in (os.path.dirname(os.path.dirname(HERE)), os.path.dirname(HERE)):
    if os.path.exists(os.path.join(cand, "cp2077_markup_translate.py")):
        sys.path.insert(0, cand)
        break
import cp2077_markup_translate as mk

def P(n): return os.path.join(HERE, n)

CANON_SIZE = 40
# Floors must BITE WITHIN a 500-line slice (an agent bragged it cleared 500 via
# bulk-"OK" because the old 600 block never fired on a 500 slice). 200/2% blocks a
# bulk-OK run mid-slice; an honest CP2077 review (~10% real errors, meaty lines
# first) clears 2% easily.
WARN_AFTER, WARN_RATE = 100, 0.04
BLOCK_AFTER, BLOCK_RATE = 200, 0.02

NIQQUD = re.compile(r'[֑-ׇ]')
FOREIGN = re.compile(r'[؀-ۿЀ-ӿͰ-Ͽ฀-๿'
                     r'ऀ-ॿ一-鿿가-힯぀-ヿĀ-ɏ]')
HEB = re.compile(r'[א-ת]')
LATIN_WORD = re.compile(r"[A-Za-z]{2,}")
OK_MARKS = {"ok", "okay", "fine", "✓", "v", "תקין", "good", "-", "same"}


# Only the STRUCTURAL tokens must be preserved across a correction — real tags
# `<...>`, placeholders `{...}`, printf specs `%d`/`%%`, entities `&...;`. The
# plain TEXT (Hebrew prose) is exactly what a fix is allowed to change, so it must
# NOT be part of this comparison. (parse_slots' "FIX" kind also covers plain
# non-English chunks — Hebrew included — so it can't be used here: it would force
# the Hebrew itself to stay identical and reject every genuine text fix.)
STRUCT = re.compile(r'<[^>]*>|\{[^}]*\}|%%|%[#0-9.*\-+ ]*[a-zA-Z]+|&[a-zA-Z#0-9]+;')


def struct_tokens(s):
    """Multiset of tags/placeholders/format-specs (leading control byte ignored —
    apply_corrections re-adds it)."""
    s = s or ""
    if s and 0x01 <= ord(s[0]) <= 0x05:
        s = s[1:]
    return Counter(STRUCT.findall(s))


# --- scripted-output signatures (moved here from qa_verify so they're rejected at
# SUBMIT time, not just post-hoc). A script can write its junk anywhere, but its
# OUTPUT can never pass these. ---
_DANGLING = re.compile(r'(?:^|\s)(?:ו|של|את|אל|על|עם|כי|אבל|או|גם|כדי|לפני|אחרי|בגלל|ב|ל|מ|ה|ש)$')
_TRAIL = re.compile(r'[\s.?!…:,;״"\'\-־)]+$')


def _strip_ctrl(s):
    return s[1:] if s and 0x01 <= ord(s[0]) <= 0x05 else s


def _norm(s):
    return _strip_ctrl(s or "").strip()


def _visible(s):
    return re.sub(r'<[^>]*>|\{[^}]*\}|%[#0-9.lhs%d]+|&[a-zA-Z#0-9]+;', "", _strip_ctrl(s or "")).strip()


def _punct_append(old, new):
    """new == old with ONLY trailing punctuation tacked on — the density-gaming cheat."""
    o, n = _norm(old), _norm(new)
    return n != o and n.startswith(o) and bool(n[len(o):]) and all(c in ".?!…:,;״\"' " for c in n[len(o):])


def _trivial(old, new):
    """new differs from old only by trailing punctuation/whitespace -> not a real fix."""
    return _TRAIL.sub("", _norm(old)) == _TRAIL.sub("", _norm(new))


def _ws_only(old, new):
    """new differs from old ONLY by whitespace (e.g. an inserted double space mid-
    string) — a junk diff manufactured to game the fix-density floor."""
    o, n = _norm(old), _norm(new)
    return o != n and re.sub(r"\s+", " ", o) == re.sub(r"\s+", " ", n)


_EN_RUN = re.compile(r"[A-Za-z][A-Za-z'.\-]*(?:\s+[A-Za-z][A-Za-z'.\-]*){3,}")


def _injected_english(en, old, new):
    """A 4+ word English run in NEW lifted straight from the EN source but absent
    from OLD = the agent pasted the untranslated source instead of translating it
    (observed: 'אפקט פעיל בזמן סריקה: Effect active when scanning')."""
    o, n = _strip_ctrl(old or ""), _strip_ctrl(new or "")
    for m in _EN_RUN.findall(n):
        if m in en and m not in o:
            return True
    return False


def is_namey(en):
    core = re.sub(r'<[^>]*>|\{[^}]*\}', "", en).strip()
    words = re.findall(r"[A-Za-z][A-Za-z'.\-]*", core)
    return (bool(words) and len(words) <= 4 and all(w[0].isupper() for w in words)) \
        or not re.search(r'[a-z]{2,}', core)


def main():
    # GUARD 1: strict whitelist — the folder may hold ONLY the task files. Catches an
    # automation script under ANY name/extension (auto_qa.py, run_qa.txt, *.bat, ...).
    ALLOWED = {"corpus.json", "qa_get_batch.py", "qa_merge.py", "qa_reviewed.json",
               "corrections.json", "corrections.json.tmp", "qa_fixes.json",
               "qa_batch.json", "INSTRUCTIONS.md"}
    extra = sorted(os.path.basename(p) for p in glob.glob(P("*"))
                   if os.path.isfile(p) and os.path.basename(p) not in ALLOWED)
    if extra:
        print(f"ERROR: unexpected file(s) in this folder: {extra}. This folder may contain ONLY the "
              "task files. You MUST review each line YOURSELF — NO automation of ANY kind (a .py / "
              ".txt / .bat script, an inline loop, a find-replace, or random punctuation to game the "
              "fix-rate). Delete it and run the loop BY HAND. Nothing saved.")
        sys.exit(1)

    # GUARD 1b: the PARENT folder too — agents tried to dodge the per-folder check by
    # writing their scripts one level up (../temp_script.py, ../fix_3.py, ...).
    ROOT = os.path.dirname(HERE)
    PARENT_OK = {"apply_corrections.py", "build_corpus.py", "corpus.json", "monitor.py",
                 "monitor.log", "prep_agents.py", "qa_get_batch.py", "qa_merge.py",
                 "qa_verify.py", "progress_corrections.json", "progress_reviewed.json",
                 "verified_corrections.json"}
    pextra = sorted(os.path.basename(p) for p in glob.glob(os.path.join(ROOT, "*"))
                    if os.path.isfile(p) and os.path.basename(p) not in PARENT_OK)
    if pextra:
        print(f"ERROR: stray file(s) in the PARENT folder: {pextra}. Do NOT write scripts/temp files "
              "anywhere — not in your folder and not in the parent. Delete them and work BY HAND. "
              "Nothing saved.")
        sys.exit(1)

    # GUARD 1c: the agents wrote automation scripts (solve.py / auto_qa.py) into the
    # REPO ROOT to dodge the per-folder + parent guards. Reject known agent-script
    # names anywhere up the tree to the repo root.
    repo = HERE
    for _ in range(6):
        if os.path.isdir(os.path.join(repo, "orchestration")) and os.path.isdir(os.path.join(repo, "games")):
            break
        nd = os.path.dirname(repo)
        if nd == repo:
            repo = None; break
        repo = nd
    if repo:
        SCRIPT_DENY = {"solve.py", "auto_qa.py", "gen_fixes.py", "run_qa.py", "fix.py", "format.py",
                       "qa_auto.py", "apply_glossary.py", "batch_fix.py", "auto.py", "process.py"}
        root_bad = sorted(n for n in SCRIPT_DENY if os.path.isfile(os.path.join(repo, n)))
        if root_bad:
            print(f"ERROR: agent-script file(s) detected in the repo root: {root_bad}. Do NOT write "
                  "automation scripts ANYWHERE (folder, parent, repo root, or scratch). Delete them and "
                  "review each line BY HAND. Nothing saved.")
            sys.exit(1)

    corpus = json.load(open(P("corpus.json"), encoding="utf-8"))
    fixes = json.load(open(P("qa_fixes.json"), encoding="utf-8")) if os.path.exists(P("qa_fixes.json")) else {}
    batch = json.load(open(P("qa_batch.json"), encoding="utf-8")) if os.path.exists(P("qa_batch.json")) else []
    corr = json.load(open(P("corrections.json"), encoding="utf-8")) if os.path.exists(P("corrections.json")) else {}
    batch_keys = {str(r["key"]) for r in batch}
    he_by_key = {str(r["key"]): r.get("he", "") for r in batch}

    # GUARD 2: batch size locked — a tampered qa_get_batch.py (bigger SIZE) is rejected.
    if len(batch) > CANON_SIZE:
        print(f"ERROR: qa_batch.json has {len(batch)} lines (max {CANON_SIZE}). qa_get_batch.py was "
              f"modified — restore SIZE={CANON_SIZE}. A giant batch = you're not reading. Nothing saved.")
        sys.exit(1)

    ok = 0; bad = []; attested = set()
    for key, val in fixes.items():
        key = str(key)
        if key not in corpus:
            bad.append((key, "UNKNOWN KEY")); continue
        s = (val or "").strip()
        if s.lower() in OK_MARKS:
            attested.add(key); continue
        if not s:
            bad.append((key, 'EMPTY (use "OK" if fine)')); continue
        if s == (he_by_key.get(key) or "").strip():
            attested.add(key); continue
        en = corpus[key]["en"]
        orig = corpus[key]["he"]
        if mk.parse_slots(s) is None:          # truncated/broken tag in the fix
            bad.append((key, "BROKEN MARKUP (parse failed)")); continue
        if struct_tokens(s) != struct_tokens(orig):   # tags/placeholders must match; TEXT may change
            bad.append((key, "TAG/PLACEHOLDER MISMATCH vs original")); continue
        # --- scripted-output rejections (a script can't fake a fix past these) ---
        if _punct_append(orig, s):
            bad.append((key, 'PUNCT-APPEND: added only trailing punctuation. Use "OK" if the line is fine.')); continue
        if _trivial(orig, s):
            bad.append((key, 'TRIVIAL: differs from the original only by trailing punctuation/space. Use "OK".')); continue
        if _ws_only(orig, s):
            bad.append((key, 'WHITESPACE-ONLY: you only changed spacing (e.g. a double space). Not a real fix — use "OK".')); continue
        vis = _visible(s)
        if vis and _DANGLING.search(vis):
            bad.append((key, "TRUNCATED: ends on a dangling Hebrew connector — complete the sentence from the EN.")); continue
        if vis and len(_visible(en)) > 25 and len(vis) * 2.4 < len(_visible(en)):
            bad.append((key, "TRUNCATED-SHORT: far shorter than the English source — complete it.")); continue
        _es = en.count("\\n") + en.count("<br") + en.count("\n")
        _ns = s.count("\\n") + s.count("<br") + s.count("\n")
        if _es >= 4 and _ns * 2 < _es:
            bad.append((key, "SEG-MISMATCH: lost most of the source's speaker/line segments — keep them all.")); continue
        if _injected_english(en, orig, s):
            bad.append((key, "ENGLISH INJECTED: a run of the English source was pasted in — TRANSLATE it to Hebrew, don't append the English.")); continue
        if FOREIGN.search(s):
            bad.append((key, "FOREIGN SCRIPT")); continue
        if NIQQUD.search(s):
            bad.append((key, "NIQQUD")); continue
        if not HEB.search(s) and not is_namey(en):
            bad.append((key, "NO HEBREW (and source is not a name/code)")); continue
        corr[key] = s; attested.add(key); ok += 1

    if bad:
        for key, r in bad[:60]:
            print(f"REJECT {r} :: {key} en={corpus.get(key,{}).get('en','')[:50]!r}")
        print(f"--- {len(bad)} rejected — fix ONLY those in qa_fixes.json, re-run qa_merge ---")
    if ok:
        json.dump(corr, open(P("corrections.json") + ".tmp", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
        os.replace(P("corrections.json") + ".tmp", P("corrections.json"))

    # ANTI-CHEAT: qa_batch.json MUST exist and be non-empty — no bypass by skipping qa_get_batch.py
    if not batch_keys:
        print("ERROR: qa_batch.json missing or empty. Run qa_get_batch.py first. Nothing saved.")
        sys.exit(1)

    review_now = {k for k in attested if k in batch_keys}
    reviewed = set(json.load(open(P("qa_reviewed.json"), encoding="utf-8"))) if os.path.exists(P("qa_reviewed.json")) else set()
    cand = reviewed | review_now
    rate = (len(corr) / len(cand)) if cand else 0.0

    # GUARD 3: fix-density floor — a real review of the CP2077 Hebrew finds ~10% errors.
    if len(cand) >= BLOCK_AFTER and rate < BLOCK_RATE:
        print(f"ERROR: only {len(corr)} corrections over {len(cand)} reviewed lines ({rate:.1%}). "
              f"The CP2077 Hebrew has REAL errors in ~10% of lines — {len(corr)} is impossible for an "
              "honest review. You are marking 'OK' WITHOUT reading. THIS BATCH IS NOT RECORDED. "
              "Go back, READ each line vs the English, and submit GENUINE fixes. A pure-'OK' run can "
              "NEVER reach 'QA done!'.")
        sys.exit(1)

    json.dump(sorted(cand), open(P("qa_reviewed.json"), "w", encoding="utf-8"), ensure_ascii=False)
    reviewed = cand

    missing = batch_keys - attested
    print(f"accepted {ok} corrections (total {len(corr)}); attested {len(review_now)}/{len(batch_keys)} "
          f"of this batch (total reviewed {len(reviewed)}, fix-rate {rate:.1%})")
    if missing:
        print(f"WARN {len(missing)} line(s) NOT attested -> they RE-APPEAR until you add an entry "
              f'(a fix, or "OK") for EVERY key. Writing {{}} advances nothing.')
    if len(cand) >= WARN_AFTER and rate < WARN_RATE:
        print(f"WARN fix-density {rate:.1%} is very low ({len(corr)}/{len(cand)}). A real review finds "
              f"~10%. Keep submitting only 'OK' and you'll be BLOCKED at {BLOCK_AFTER} lines.")


if __name__ == "__main__":
    main()
