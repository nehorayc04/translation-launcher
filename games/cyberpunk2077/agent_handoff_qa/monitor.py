"""monitor.py — at-a-glance health + cheat check for the parallel QA agents.

Run any time (Claude runs it to "follow" the agents). For each agent_K it shows
progress (reviewed/slice), genuine fixes, fix-rate, and FLAGS cheating:
  - forbidden files in the folder (auto-runner scripts under any name)
  - junk fixes (random punct-append / trivial no-op) via qa_verify.classify
  - density-gaming signature (big reviewed, ~0 genuine, high junk%)
Prints OK / ALERT per agent. READ-ONLY.

Usage: python monitor.py
"""
import json, os, re, glob, sys, importlib.util
HERE = os.path.dirname(os.path.abspath(__file__))

spec = importlib.util.spec_from_file_location("qv", os.path.join(HERE, "qa_verify.py"))
qv = importlib.util.module_from_spec(spec); spec.loader.exec_module(qv)

ALLOWED = {"corpus.json", "qa_get_batch.py", "qa_merge.py", "qa_reviewed.json",
           "corrections.json", "corrections.json.tmp", "qa_fixes.json",
           "qa_batch.json", "INSTRUCTIONS.md"}


def jload(p, d):
    try: return json.load(open(p, encoding="utf-8"))
    except Exception: return d


def main():
    corpus = jload(os.path.join(HERE, "corpus.json"), {})
    agents = sorted(d for d in glob.glob(os.path.join(HERE, "agent_*"))
                    if os.path.isdir(d) and re.fullmatch(r"agent_\d+", os.path.basename(d)))
    if not agents:
        print("no agent_* folders — run prep_agents.py N [CAP]"); return
    any_alert = False
    print(f"{'agent':9} {'reviewed':>10} {'genuine':>8} {'junk':>6} {'rate':>6}  status")
    for d in agents:
        name = os.path.basename(d)
        slice_n = len(jload(os.path.join(d, "corpus.json"), {}))
        reviewed = len(jload(os.path.join(d, "qa_reviewed.json"), []))
        corr = jload(os.path.join(d, "corrections.json"), {})
        cslice = jload(os.path.join(d, "corpus.json"), {})
        genuine = junk = 0
        reasons = {}
        for k, new in corr.items():
            ent = cslice.get(k) or corpus.get(k)
            if not ent:
                junk += 1; reasons["unknown_key"] = reasons.get("unknown_key", 0) + 1; continue
            r = qv.classify(ent["en"], ent["he"], new)
            if r:
                junk += 1; reasons[r] = reasons.get(r, 0) + 1
            else:
                genuine += 1
        forbidden = sorted(os.path.basename(p) for p in glob.glob(os.path.join(d, "*"))
                           if os.path.isfile(p) and os.path.basename(p) not in ALLOWED)
        rate = genuine / reviewed if reviewed else 0.0
        alert = []
        if forbidden:
            alert.append(f"FORBIDDEN {forbidden}")
        if junk:
            alert.append(f"JUNK {reasons}")
        if reviewed >= 200 and rate < 0.02:
            alert.append(f"SHALLOW (rate {rate:.1%} — bulk-OK?)")
        status = "OK" if not alert else "ALERT: " + " | ".join(alert)
        if alert:
            any_alert = True
        done = "done" if slice_n and reviewed >= slice_n else ""
        print(f"{name:9} {reviewed:>6}/{slice_n:<3} {genuine:>8} {junk:>6} {rate:>5.0%}  {status} {done}")
    print("\n" + ("⚠️  ALERTS above — investigate before applying that slice."
                  if any_alert else "✅ all agents clean."))


if __name__ == "__main__":
    main()
