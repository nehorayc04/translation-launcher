"""apply_corrections.py — fold the parallel agents' QA corrections back into the
CP2077 spine, the SAME safe way the Opus loop does.

  1. harvest progress_* + every agent_*/{corrections.json, qa_reviewed.json}.
  2. for each {key: new}: reconstruct `old` byte-exact from corpus[key].he
     (preserves the leading control byte), guard the control byte on `new`,
     skip no-ops + broken markup -> write universal/opus_qa_fixes.jsonl.
  3. run qa_review_apply.py (QA-lock + backup + atomic + parse_slots guard +
     old==current no-op + sibling onscreens.json mirror + 3-backup prune).
  4. add ALL reviewed keys to the GLOBAL checkpoint so build_corpus never
     re-serves them.
Then the operator bakes: python ../rebuild_onscreens_and_pack.py  (game CLOSED).

Usage: python apply_corrections.py [--apply]   (default: preview)
"""
import json, os, re, sys, glob, subprocess
HERE = os.path.dirname(os.path.abspath(__file__))
CP = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(CP))
UNIV = os.path.join(ROOT, "universal")
sys.path.insert(0, CP)
import cp2077_markup_translate as mk

CORPUS = os.path.join(HERE, "corpus.json")
FIXES = os.path.join(UNIV, "opus_qa_fixes.jsonl")
CHECKPOINT = os.path.join(UNIV, "opus_qa_checkpoint.json")


def jload(p, d):
    try: return json.load(open(p, encoding="utf-8"))
    except Exception: return d


def main():
    do_apply = "--apply" in sys.argv
    corpus = jload(CORPUS, {})

    reviewed = set(jload(os.path.join(HERE, "progress_reviewed.json"), []))
    for d in glob.glob(os.path.join(HERE, "agent_*")):
        if not (os.path.isdir(d) and re.fullmatch(r"agent_\d+", os.path.basename(d))):
            continue
        reviewed |= set(jload(os.path.join(d, "qa_reviewed.json"), []))

    # Prefer the hard-verified clean set (qa_verify.py --clean) — junk/invalid fixes
    # already dropped. Fall back to raw harvest only if it wasn't produced.
    verified = os.path.join(HERE, "verified_corrections.json")
    if os.path.exists(verified):
        corr = jload(verified, {})
        print(f"using verified_corrections.json ({len(corr)} clean fixes)")
    else:
        print("WARNING: no verified_corrections.json — run `python qa_verify.py --clean` first "
              "to drop junk. Falling back to raw agent corrections.")
        corr = jload(os.path.join(HERE, "progress_corrections.json"), {})
        for d in glob.glob(os.path.join(HERE, "agent_*")):
            if os.path.isdir(d) and re.fullmatch(r"agent_\d+", os.path.basename(d)):
                corr.update(jload(os.path.join(d, "corrections.json"), {}))
    reviewed |= set(corr.keys())

    rows, skipped = [], 0
    for key, new in corr.items():
        ent = corpus.get(key)
        if not ent:
            skipped += 1; continue
        old = ent["he"]
        if old and ord(old[0]) < 0x20 and (not new or new[0] != old[0]):
            new = old[0] + new
        if not new or new == old or mk.parse_slots(new) is None:
            skipped += 1; continue
        sec = key.rsplit("|", 1)[0]            # "onscreens/onscreens_final.json"
        rows.append({"sec": sec, "pk": ent["pk"], "field": "femaleVariant",
                     "old": old, "new": new, "reason": "agent-qa"})

    print(f"corrections harvested {len(corr)} | applicable fixes {len(rows)} "
          f"(skipped {skipped}) | reviewed keys {len(reviewed)}")
    if not do_apply:
        print("(preview only — add --apply to write spine + checkpoint)")
        return

    with open(FIXES, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    # apply to spine (consumes opus_qa_fixes.jsonl)
    env = dict(os.environ); env["PYTHONIOENCODING"] = "utf-8"
    r = subprocess.run([sys.executable, os.path.join(CP, "qa_review_apply.py")],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    print((r.stdout or "").strip())
    if r.returncode != 0:
        print("APPLY FAILED:", (r.stderr or "")[-400:]); return

    # commit reviewed keys to the global checkpoint
    cp = set(jload(CHECKPOINT, {}).get("reviewed", []))
    before = len(cp)
    cp |= reviewed
    tmp = CHECKPOINT + ".tmp"
    json.dump({"reviewed": sorted(cp)}, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(tmp, CHECKPOINT)
    print(f"global checkpoint: {len(cp)} reviewed (+{len(cp) - before})")
    print("NEXT: python games/cyberpunk2077/rebuild_onscreens_and_pack.py  (game CLOSED)")


if __name__ == "__main__":
    main()
