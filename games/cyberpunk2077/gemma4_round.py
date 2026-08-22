# -*- coding: utf-8 -*-
"""gemma4_round.py — the "gemma-4 does everything" round.

Runs AFTER the subtitle bake finishes (the bash chain waits). Stages:
  1. unify   — apply unify_glossary.py to BASE and DLC spines (1,342+ renames)
  2. queue   — build gemma4_queue.jsonl: every still-open item
               (anomalies minus judged-settled, english_only/foreign residue,
                clean_translate failures, pk 21153)
  3. judge   — judge_local.py with MODEL gemma-4-31b-it over that queue
  4. merge   — gate every fix (judge_local.gates_ok) and write into the
               spines (base + DLC); collect touched subtitle sections
  5. report  — rescan anomalies, print the before/after

The bash chain then bakes: onscreens -> touched subtitles -> DLC.
"""
import os, sys, json, re, time, shutil, subprocess, collections

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, "universal"))
import get_next_audit_batch as G
import cp2077_qa_defects as Q

PY = sys.executable
QUEUE = os.path.join(HERE, "gemma4_queue.jsonl")
RESULTS = os.path.join(HERE, "gemma4_judgments.jsonl")
N_BASE = 10000          # id offset so n never collides with claude_queue


def run(args, **kw):
    print(f"$ {' '.join(os.path.basename(a) for a in args[:2])} ...", flush=True)
    r = subprocess.run(args, cwd=HERE, **kw)
    if r.returncode != 0:
        print(f"  [!] exit {r.returncode}")
    return r.returncode


def stage_unify():
    run([PY, os.path.join(HERE, "unify_glossary.py")])
    run([PY, os.path.join(HERE, "unify_glossary.py"), "--dlc"])


def stage_queue():
    # fresh anomaly scan AFTER unify
    run([PY, os.path.join(HERE, "scan_word_anomalies.py")])
    anoms = [json.loads(l) for l in open(os.path.join(HERE, "word_anomalies.jsonl"), encoding="utf-8") if l.strip()]
    # settled = judged ok/applied-fix (claude + gemma2 rounds)
    settled = set()
    qpath = os.path.join(HERE, "claude_queue.jsonl")
    queue1 = {json.loads(l)["n"]: json.loads(l) for l in open(qpath, encoding="utf-8") if l.strip()}
    from judge_local import gates_ok
    for fn in ("claude_judgments.jsonl", "local_judgments.jsonl"):
        p = os.path.join(HERE, fn)
        if not os.path.exists(p):
            continue
        for l in open(p, encoding="utf-8"):
            try:
                v = json.loads(l)
            except Exception:
                continue
            row = queue1.get(v.get("n"))
            if not row:
                continue
            ok = v["verdict"] == "ok" or (v["verdict"] == "fix" and v.get("fixed") and gates_ok(row, v["fixed"]))
            if ok:
                for ref in row["refs"]:
                    p_, sec, pk, fld = ref.split("|", 3)
                    settled.add((sec, pk, fld, row["category"], row.get("word", "")))
    rows = [r for r in anoms if (r["section"], r["pk"], r["field"], r["category"], r.get("word", "")) not in settled]

    # + language-report english_only / foreign residue
    lp = os.path.join(HERE, "language_report.jsonl")
    if os.path.exists(lp):
        for l in open(lp, encoding="utf-8"):
            r = json.loads(l)
            if r.get("kind") in ("english_only", "foreign_script"):
                r["category"] = r["kind"]
                rows.append(r)
    # + clean_translate failures (the hard tail)
    tq = os.path.join(HERE, "translation_queue.jsonl")
    tr = os.path.join(HERE, "translation_results.jsonl")
    if os.path.exists(tq) and os.path.exists(tr):
        failed = {json.loads(l)["id"] for l in open(tr, encoding="utf-8")
                  if l.strip() and not json.loads(l).get("translated")}
        for l in open(tq, encoding="utf-8"):
            r = json.loads(l)
            if r.get("id") in failed:
                parts = r["id"].split("|")
                rows.append({"project": parts[0], "section": parts[1], "pk": parts[2],
                             "field": parts[3], "category": "untranslated",
                             "word": "", "hebrew": r.get("hebrew", ""),
                             "english": r.get("english", "")})

    # group exact duplicates -> one judged row, many refs
    groups = collections.OrderedDict()
    for r in rows:
        k = (r["category"], r.get("word", ""), r["hebrew"], r.get("english", ""))
        g = groups.setdefault(k, {"category": r["category"], "word": r.get("word", ""),
                                  "hebrew": r["hebrew"], "english": r.get("english", ""), "refs": []})
        ref = f'{r.get("project","base")}|{r["section"]}|{r["pk"]}|{r["field"]}'
        if ref not in g["refs"]:
            g["refs"].append(ref)
    uniq = list(groups.values())
    with open(QUEUE, "w", encoding="utf-8") as f:
        for i, g in enumerate(uniq):
            g["n"] = N_BASE + i
            f.write(json.dumps(g, ensure_ascii=False) + "\n")
    print(f"gemma4 queue: {len(uniq)} unique groups (from {len(rows)} rows)")


def stage_judge():
    env = dict(os.environ, JL_QUEUE=QUEUE, JL_OUT=RESULTS, PYTHONUTF8="1")
    run([PY, os.path.join(HERE, "judge_local.py")], env=env)


def stage_merge():
    from judge_local import gates_ok
    queue = {json.loads(l)["n"]: json.loads(l) for l in open(QUEUE, encoding="utf-8") if l.strip()}
    fixes, humans = [], []
    for l in open(RESULTS, encoding="utf-8"):
        v = json.loads(l)
        row = queue.get(v["n"])
        if not row:
            continue
        if v["verdict"] == "fix" and v.get("fixed") and gates_ok(row, v["fixed"]):
            fixes.append((row, v))
        elif v["verdict"] != "ok":
            humans.append((row, v))
    print(f"gemma4 verdicts: fixes-pass-gates={len(fixes)} open={len(humans)}")

    touched_subs = set()
    for label, path in (("base", G.BASE_TR), ("dlc", G.DLC_TR)):
        data = json.load(open(path, encoding="utf-8"))
        idx = {}
        for sec, rows in data.items():
            if isinstance(rows, list):
                for e in rows:
                    if isinstance(e, dict):
                        idx[(sec, str(e.get("primaryKey") or e.get("stringId")))] = e
        n = 0
        for row, v in fixes:
            for ref in row["refs"]:
                proj, sec, pk, fld = ref.split("|", 3)
                if proj != label:
                    continue
                e = idx.get((sec, pk))
                if e is not None:
                    e[fld] = v["fixed"]
                    n += 1
                    if label == "base" and sec.startswith("subtitles"):
                        touched_subs.add(sec)
        if n:
            if not Q.acquire_lock("gemma4_round"):
                sys.exit("[abort] QA lock held")
            try:
                bak = f"{path}.bak.g4.{time.strftime('%Y%m%d_%H%M%S')}"
                shutil.copy2(path, bak)
                tmp = path + ".tmp"
                json.dump(data, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
                os.replace(tmp, path)
                print(f"[{label}] applied {n}; backup {os.path.basename(bak)}")
            finally:
                Q.release_lock()
    open(os.path.join(HERE, "gemma4_sub_sections.txt"), "w", encoding="utf-8").write(
        "\n".join(sorted(touched_subs)))
    # open items -> human review file
    with open(os.path.join(HERE, "human_review_g4.md"), "w", encoding="utf-8") as f:
        f.write(f"# בדיקה אנושית — סבב gemma-4 ({len(humans)} פתוחים)\n\n")
        for row, v in humans:
            f.write(f"- [{row['category']}] {row['refs'][0]}\n  HE: {row['hebrew'][:90]}\n")
            if row.get("english"):
                f.write(f"  EN: {row['english'][:80]}\n")
            if v.get("note"):
                f.write(f"  הערה: {v['note']}\n")
    print(f"touched subtitle sections: {len(touched_subs)}; open -> human_review_g4.md")


def stage_report():
    run([PY, os.path.join(HERE, "scan_word_anomalies.py")])
    run([PY, os.path.join(HERE, "make_review_html.py")])


if __name__ == "__main__":
    stages = sys.argv[1:] or ["unify", "queue", "judge", "merge", "report"]
    for s in stages:
        print(f"\n===== STAGE {s} =====", flush=True)
        {"unify": stage_unify, "queue": stage_queue, "judge": stage_judge,
         "merge": stage_merge, "report": stage_report}[s]()
    print("\ngemma4 round COMPLETE")
