"""Build the FULL-corpus QA review set for WD2 Hebrew (UI + subtitles together).

Produces corpus.json = {id: {en, he, src, flags}} for every TRANSLATED id, where
src marks which source file the corrected Hebrew must be written back to:
  "ui"  -> agent_handoff/hebrew.json   (frontend/menu/HUD, stored VISUAL at build)
  "sub" -> agent_handoff_subs/hebrew.json (spoken subtitle OR named content)
`flags` = the deterministic QA flags (ENGLISH_LEAK / UNTRANSLATED / OVERFLOW / ...)
from wd2_full_qa_scan so the loop reviews the worst lines FIRST.

The Hebrew here is LOGICAL (reading order) — the agent reviews/edits logical Hebrew;
the build applies visual()/bidi. The agent NEVER reverses anything.
"""
import json, os, re, collections
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OASIS = os.path.join(ROOT, "extract", "en_oasis", "languages", "english",
                     "oasisstrings_converted.xml")
UI_ALL  = r"C:/tmp/wd2_ui_all.json"
UI_HE   = r"C:/tmp/wd2_ui_he.json"
HANDOFF = os.path.join(ROOT, "agent_handoff", "hebrew.json")
SUB_HE  = os.path.join(ROOT, "agent_handoff_subs", "hebrew.json")
FLAGS   = r"C:/tmp/wd2_qa_report/flags.jsonl"
OUT     = os.path.join(HERE, "corpus.json")

SR = re.compile(r'<string\s+enum="([^"]*)"\s+LineId="(\d+)"\s+value="([^"]*)"\s*/>')
def clean_en(raw):
    s = raw.replace("&apos;","'").replace("&quot;",'"').replace("&lt;","<").replace("&gt;",">").replace("&amp;","&")
    return s.replace("\r"," ").replace("\n"," ").strip()
def jl(p, d):
    try: return json.load(open(p, encoding="utf-8"))
    except Exception: return d

def main():
    meta = {}
    for m in SR.finditer(open(OASIS, encoding="utf-8").read()):
        meta[int(m.group(2))] = clean_en(m.group(3))
    ui = {}
    for p in (UI_ALL, UI_HE, HANDOFF):
        ui.update({int(k): v for k, v in jl(p, {}).items()})
    sub = {int(k): v for k, v in jl(SUB_HE, {}).items()}
    flagmap = collections.defaultdict(list)
    if os.path.exists(FLAGS):
        for line in open(FLAGS, encoding="utf-8"):
            r = json.loads(line); flagmap[r["id"]] = r["flags"]

    corpus = {}
    for i, en in meta.items():
        if i in ui and str(ui[i]).strip():
            he, src = ui[i], "ui"
        elif i in sub and str(sub[i]).strip():
            he, src = sub[i], "sub"
        else:
            continue
        # the agent reviews lines with a real EN sentence; pure name/code lines skip
        corpus[str(i)] = {"en": en, "he": he, "src": src, "flags": flagmap.get(i, [])}
    json.dump(corpus, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    fl = sum(1 for v in corpus.values() if v["flags"])
    print(f"corpus: {len(corpus)} translated ids ({fl} carry deterministic flags) -> {OUT}")

if __name__ == "__main__":
    main()
