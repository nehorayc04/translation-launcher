"""Apply the agent's accepted QA corrections back into the right SOURCE file so the
next build picks them up. Orientation (visual/logical) is decided later by the build
from the oasis enum — here we only write the LOGICAL Hebrew into its source:
  src=="ui"  -> agent_handoff/hebrew.json
  src=="sub" -> agent_handoff_subs/hebrew.json
Backs up each source file first; atomic writes. Run by Claude (NOT the agent).
"""
import json, os, shutil, time, glob
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CORPUS = os.path.join(HERE, "corpus.json")
# merge corrections from: persistent progress + every current agent_* round + the
# earlier single-dir fixes. Dynamic (any number of agents across any number of rounds).
CORR_FILES = ([os.path.join(HERE, "progress_corrections.json"),
               os.path.join(HERE, "corrections.json")]
              + sorted(glob.glob(os.path.join(HERE, "agent_*", "corrections.json"))))
UI_SRC  = os.path.join(ROOT, "agent_handoff", "hebrew.json")
SUB_SRC = os.path.join(ROOT, "agent_handoff_subs", "hebrew.json")
SUB_MIRROR = r"C:/tmp/wd2_sub_he.json"

def jload(p): return json.load(open(p, encoding="utf-8"))
def atomic(p, obj):
    json.dump(obj, open(p+".tmp", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    os.replace(p+".tmp", p)

def main():
    corpus = jload(CORPUS)
    corr = {}
    for cf in CORR_FILES:
        if os.path.exists(cf):
            corr.update(jload(cf))
    if not corr:
        print("no corrections to apply"); return
    ui = jload(UI_SRC); sub = jload(SUB_SRC)
    ts = time.strftime("%Y%m%d_%H%M%S")
    shutil.copy2(UI_SRC, UI_SRC + f".bak_qa_{ts}")
    shutil.copy2(SUB_SRC, SUB_SRC + f".bak_qa_{ts}")
    nui = nsub = miss = 0
    for pk, he in corr.items():
        src = corpus.get(pk, {}).get("src")
        if src == "ui":
            ui[pk] = he; nui += 1
        elif src == "sub":
            sub[pk] = he; nsub += 1
        else:
            miss += 1
    atomic(UI_SRC, ui); atomic(SUB_SRC, sub)
    try: atomic(SUB_MIRROR, {str(k): v for k, v in sub.items()})
    except OSError: pass
    print(f"applied {nui} UI + {nsub} subtitle corrections (unmapped {miss}); "
          f"backups *.bak_qa_{ts}")

if __name__ == "__main__":
    main()
