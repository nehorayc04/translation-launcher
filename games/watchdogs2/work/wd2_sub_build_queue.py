"""Build the WD2 SUBTITLE/dialogue translation queue from the CLEAN oasis XML.

The spoken lines (the part excluded from the UI pass) live in the oasis set with
enum="soundbinary\\N.bnk". The loctool .loc.txt decode is GARBLED for barks, so the
authoritative English is the oasis XML value (LineId -> clean English).

Output: C:/tmp/wd2_sub_queue.json  [{id, enum, en}, ...]
Order : soundbinary subtitles FIRST (highest value), then the remaining
        translatable named content; within each, real-words-first (so the model
        spends the run on real text, not codes). Pure proper-name enums and ids
        already translated (UI hebrew.json) or parked (skip) are excluded.
"""
import json, os, re

HERE   = os.path.dirname(os.path.abspath(__file__))
ROOT   = os.path.dirname(HERE)
OASIS  = os.path.join(ROOT, "extract", "en_oasis", "languages", "english",
                      "oasisstrings_converted.xml")

UI_DONE  = r"C:/tmp/wd2_ui_he.json"      # already-translated UI ids (don't redo)
UI_ALL   = r"C:/tmp/wd2_ui_all.json"     # earlier UI ids
HANDOFF  = os.path.join(ROOT, "agent_handoff", "hebrew.json")  # final UI hebrew
SUB_HE   = r"C:/tmp/wd2_sub_he.json"     # already-done subtitles (resume)
SKIP     = r"C:/tmp/wd2_sub_skip.json"
OUT      = r"C:/tmp/wd2_sub_queue.json"

# pure proper-name enums — stay Latin, not worth an LM call; excluded from queue
NAME_ENUM = re.compile(r'^(Name|Surname|First_?Name|Last_?Name|Artist_Name|Song_Name|name_\d+|firstname_\d+|surname_\d+)$', re.I)

STRING_RE = re.compile(r'<string\s+enum="([^"]*)"\s+LineId="(\d+)"\s+value="([^"]*)"\s*/>')

def jload(p, d):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return d

def clean_en(raw):
    # unescape the safe XML entities; keep numeric &#..; as literal tokens (preserved).
    s = raw.replace("&apos;", "'").replace("&quot;", '"')
    s = s.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
    # protect line-based batch parsing: a real newline/CR -> space. The literal
    # backslash-n ("\\n", a forced game line-break) is left intact for the model.
    s = s.replace("\r", " ").replace("\n", " ")
    return s.strip()

def has_real_word(s):
    core = re.sub(r'\[[A-Za-z0-9_]+\]|\{[^}]*\}|%[0-9.]*[a-z]+|&#?\w+;', '', s)
    return bool(re.search(r'[A-Za-z]{3,}', core))

def main():
    done = set(jload(UI_DONE, {})) | set(jload(UI_ALL, {})) | set(jload(SUB_HE, {}))
    done |= {str(k) for k in jload(HANDOFF, {})}
    skip = set(jload(SKIP, []))
    exclude = done | skip

    subs, named = [], []
    seen = set()
    with open(OASIS, encoding="utf-8") as f:
        for m in STRING_RE.finditer(f.read()):
            enum, lid, raw = m.group(1), m.group(2), m.group(3)
            if lid in exclude or lid in seen:
                continue
            en = clean_en(raw)
            if not en or not has_real_word(en):
                continue
            if NAME_ENUM.match(enum):
                continue
            seen.add(lid)
            row = {"id": int(lid), "enum": enum, "en": en}
            (subs if enum.startswith("soundbinary") else named).append(row)

    # Order for steady, low-risk throughput: SHORT real-word lines first (the bulk
    # of subtitles — fast, high success), the long multi-paragraph / mixed-language
    # narratives LAST (slow + leak-prone). Pure-code/no-word rows sink to the end.
    keyf = lambda r: (0 if has_real_word(r["en"]) else 1, len(r["en"]))
    subs.sort(key=keyf)
    named.sort(key=keyf)
    queue = subs + named

    json.dump(queue, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"subtitles (soundbinary): {len(subs)}")
    print(f"other translatable named: {len(named)}")
    print(f"TOTAL queue: {len(queue)}  (excluded already-done/skip: {len(exclude)})")
    print(f"-> {OUT}")
    for r in queue[:3]:
        print("  ", r["id"], repr(r["en"][:70]))

if __name__ == "__main__":
    main()
