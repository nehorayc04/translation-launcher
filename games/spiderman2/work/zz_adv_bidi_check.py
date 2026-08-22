"""ADVERSARIAL bidi correctness check.
Re-derive the RTL-base visual for every description STRAIGHT FROM SOURCE
(*_he.json), not from the truncated bidi_sim_report.json. Flag suspicious
rendering: mis-sided sentence-final punctuation, mirrored bracket damage,
split/reversed English tokens, reversed numbers, mangled {VALUE} placeholders.
"""
import json, os, re, unicodedata
from bidi.algorithm import get_display

HERE = os.path.dirname(os.path.abspath(__file__))
RLM = "‏"
RLE = "‫"; PDF = "‬"; LRM = "‎"
WORD = re.compile(r"[A-Za-z][A-Za-z0-9]*")
NUM = re.compile(r"\d[\d.,]*")

def has_heb(s): return any("א" <= c <= "ת" for c in s)
def has_lat(s): return any(("A" <= c <= "Z") or ("a" <= c <= "z") for c in s)

def strip_inner_markup(s):
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"&[a-zA-Z]+;|&#\d+;|&#x[0-9a-fA-F]+;", "", s)
    return s

def vis(s, base):
    out = []
    for para in re.split(r"[\n\r]", s):
        out.append(get_display(para, base_dir=base))
    return "\n".join(out)

# ---- collect descriptions exactly like 90_bidi_sim.py ----
descs = {}
for fn in ["settings_he.json"] + [f"menus{n}_he.json" for n in range(2, 14)] + ["menus_he.json"]:
    p = os.path.join(HERE, fn)
    if not os.path.exists(p): continue
    d = json.load(open(p, encoding="utf-8"))
    for k, v in d.items():
        if isinstance(v, str) and v.startswith(RLM) and has_heb(v):
            descs.setdefault(k, v)

print(f"[*] {len(descs)} RLM+Hebrew descriptions")

flags = {"word_lost": [], "num_reversed": [], "value_mangled": [],
         "bracket_unbalanced": [], "punct_wrong_side": [], "bracket_in_visual_swapped": []}

# Bracket mirror pairs the UBA mirrors at render time
MIRROR = {"(": ")", ")": "(", "[": "]", "]": "[", "{": "}", "}": "{",
          "“": "”", "”": "“"}

for k, raw in descs.items():
    logical = raw[len(RLM):]
    # keep {VALUE} placeholders intact for the placeholder test, strip tags/entities
    text = strip_inner_markup(logical)
    vR = vis(RLM + text, "R").replace(RLM, "").replace(LRM, "")

    # 1. every Latin word present verbatim
    for w in WORD.findall(text):
        if w not in vR:
            flags["word_lost"].append((k, w))

    # 2. every multi-digit number present verbatim (not reversed)
    for m in NUM.findall(text):
        core = m.rstrip(".,")
        if len(core) >= 2 and core not in vR and core[::-1] in vR:
            flags["num_reversed"].append((k, core))

    # 3. {VALUE...} placeholders survive intact
    for ph in re.findall(r"\{[^}]*\}", text):
        if ph not in vR:
            flags["value_mangled"].append((k, ph, vR[:60]))

    # 4. bracket balance preserved (count of each kind identical logical vs visual)
    for op, cl in [("(", ")"), ("[", "]")]:
        if (text.count(op) != vR.count(op)) or (text.count(cl) != vR.count(cl)):
            flags["bracket_unbalanced"].append((k, op, text.count(op), text.count(cl), vR.count(op), vR.count(cl)))

    # 5. sentence-final punctuation side check (Hebrew RTL: '.'/'!'/'?'/':' should
    #    end the LOGICAL string and in RTL visual land at the LEFT edge i.e. index 0..2)
    t = text.rstrip()
    if t and t[-1] in ".!?:" and has_heb(t):
        # find that terminal punct in visual; for correct RTL it should be at left (low idx)
        # but only meaningful when there's no trailing Latin run
        idx = vR.find(t[-1])
        # heuristic record only; hand-verify later
        flags["punct_wrong_side"].append((k, t[-1], idx, len(vR)))

print("\n==== AUTOMATED FLAGS ====")
for name, items in flags.items():
    print(f"  {name:24}: {len(items)}")

# dump the serious ones
for name in ["word_lost", "num_reversed", "value_mangled", "bracket_unbalanced"]:
    if flags[name]:
        print(f"\n--- {name} (all) ---")
        for it in flags[name][:40]:
            print("   ", it)

json.dump(flags, open(os.path.join(HERE, "zz_adv_bidi_flags.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("\n[+] wrote zz_adv_bidi_flags.json")
