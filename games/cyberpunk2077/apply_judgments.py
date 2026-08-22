"""
apply_judgments.py — apply the judged fixes (Claude + gemma) to the base
spine, and write the human-review file.

Sources: claude_queue.jsonl (n -> refs/original), claude_judgments.jsonl,
local_judgments.jsonl. Every fix — including Claude's (its adversarial
Verify phase never ran) — must pass judge_local.gates_ok. DLC refs are NOT
written (the DLC archive was just baked); they're saved to
dlc_pending_fixes.jsonl for the next DLC bake cycle.

Output: human_review.md (everything needing the user's eyes).
"""
import os, sys, json, time, shutil, collections

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, "universal"))
import get_next_audit_batch as G
import cp2077_qa_defects as Q
from judge_local import gates_ok

queue = {json.loads(l)["n"]: json.loads(l)
         for l in open(os.path.join(HERE, "claude_queue.jsonl"), encoding="utf-8") if l.strip()}
verdicts = {}
for fn in ("claude_judgments.jsonl", "local_judgments.jsonl"):
    p = os.path.join(HERE, fn)
    if os.path.exists(p):
        for l in open(p, encoding="utf-8"):
            try:
                r = json.loads(l)
                verdicts.setdefault(r["n"], r)   # claude (loaded first) wins
            except Exception:
                pass

fixes, humans, rejected = [], [], []
for n, v in verdicts.items():
    row = queue.get(n)
    if not row:
        continue
    if v["verdict"] == "fix" and v.get("fixed"):
        if gates_ok(row, v["fixed"]):
            fixes.append((row, v))
        else:
            rejected.append((row, v))
    elif v["verdict"] == "human":
        humans.append((row, v))

print(f"verdicts={len(verdicts)} fix-pass-gates={len(fixes)} "
      f"fix-rejected={len(rejected)} human={len(humans)}")

# ── apply to the BASE spine; defer DLC refs ──
data = json.load(open(G.BASE_TR, encoding="utf-8"))
idx = {}
for sec, rows in data.items():
    if isinstance(rows, list):
        for e in rows:
            if isinstance(e, dict):
                pk = str(e.get("primaryKey") or e.get("stringId"))
                idx[(sec, pk)] = e

applied = 0
dlc_pending = []
touched_sub_sections = set()
if not Q.acquire_lock("apply_judgments"):
    sys.exit("[abort] QA lock held")
try:
    for row, v in fixes:
        for ref in row["refs"]:
            proj, sec, pk, fld = ref.split("|", 3)
            if proj == "dlc":
                dlc_pending.append({"ref": ref, "fixed": v["fixed"]})
                continue
            e = idx.get((sec, pk))
            if e is not None:
                e[fld] = v["fixed"]
                applied += 1
                if sec.startswith("subtitles"):
                    touched_sub_sections.add(sec)
    bak = f"{G.BASE_TR}.bak.judged.{time.strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(G.BASE_TR, bak)
    tmp = G.BASE_TR + ".tmp"
    json.dump(data, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(tmp, G.BASE_TR)
    print(f"applied {applied} (backup {os.path.basename(bak)}); dlc deferred {len(dlc_pending)}")
finally:
    Q.release_lock()

with open(os.path.join(HERE, "dlc_pending_fixes.jsonl"), "a", encoding="utf-8") as f:
    for x in dlc_pending:
        f.write(json.dumps(x, ensure_ascii=False) + "\n")
with open(os.path.join(HERE, "judged_sub_sections.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(sorted(touched_sub_sections)))

# ── human review file ──
lines = ["# בדיקה אנושית — ממצאים שהשופטים לא הכריעו",
         f"(Claude+gemma; {len(humans)} לא הוכרעו, {len(rejected)} תיקונים נפסלו בשערים)", ""]
by_cat = collections.defaultdict(list)
for row, v in humans + rejected:
    by_cat[row["category"]].append((row, v))
for cat, items in sorted(by_cat.items(), key=lambda kv: -len(kv[1])):
    lines.append(f"\n## {cat} — {len(items)}")
    for row, v in items:
        what = "תיקון שנפסל" if v["verdict"] == "fix" else (v.get("note") or "")
        lines.append(f"- pk={row['refs'][0].split('|')[2]} word={row.get('word','')!r} :: {row['hebrew'][:90]}")
        if row.get("english"):
            lines.append(f"    EN: {row['english'][:80]}")
        if what:
            lines.append(f"    הערה: {what}")
        if v["verdict"] == "fix":
            lines.append(f"    הצעה (נפסלה): {v['fixed'][:90]}")
open(os.path.join(HERE, "human_review.md"), "w", encoding="utf-8").write("\n".join(lines))
print(f"human_review.md written ({len(humans)+len(rejected)} items); "
      f"subtitle sections touched: {len(touched_sub_sections)}")
