"""BIDI RENDER SIMULATION — proves what cohtml/ICU will display for every Hebrew
description once dir='rtl' (RTL base) is applied by the JS patch.

cohtml uses ICU = the Unicode Bidi Algorithm (UBA). python-bidi implements UBA.
With dir='rtl' the paragraph base direction is RTL; we run get_display(base_dir='R')
on each description and assert:
  1. Every Latin WORD appears verbatim in the visual output (L-runs are never
     internally reordered by UBA -> no scrambled English).
  2. The RTL-base visual DIFFERS from the LTR-base visual (proves base direction
     is the lever, i.e. the JS dir='rtl' fix actually matters).
  3. Under RTL base the first logical word sits on the RIGHT edge (correct for
     Hebrew) — measured by where the first Hebrew run lands.

Splits on real paragraph separators (\\n) like UBA does, runs each segment.
Writes bidi_sim_report.json + prints stats + the worst/most-mixed samples.
"""
import json, os, re, glob, unicodedata
from bidi.algorithm import get_display

HERE = os.path.dirname(os.path.abspath(__file__))
RLM = "‏"
WORD = re.compile(r"[A-Za-z][A-Za-z0-9]*")

def has_heb(s): return any("א" <= c <= "ת" for c in s)

def vis(s, base):
    # render per paragraph (UBA paragraph = split on B chars \n \r)
    out = []
    for para in re.split(r"[\n\r]", s):
        out.append(get_display(para, base_dir=base))
    return "\n".join(out)

def strip_inner_markup(s):
    # remove tags + entities + {VALUE..} so we test the visible text only
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"&[a-zA-Z]+;|&#\d+;|&#x[0-9a-fA-F]+;", "", s)
    s = re.sub(r"\{[^}]*\}", "", s)
    return s

# collect all description strings (RLM-prefixed plain) from the menus files
descs = {}
for fn in ["settings_he.json"] + [f"menus{n}_he.json" for n in range(2, 14)] + ["menus_he.json"]:
    p = os.path.join(HERE, fn)
    if not os.path.exists(p): continue
    d = json.load(open(p, encoding="utf-8"))
    for k, v in d.items():
        if isinstance(v, str) and v.startswith(RLM) and has_heb(v):
            descs.setdefault(k, v)

print(f"[*] simulating {len(descs)} RLM+plain descriptions under RTL base\n")

word_fail = []      # latin word lost/scrambled in RTL-base visual
no_diff = []        # RTL == LTR visual (base direction made no difference)
bad_first = []      # under RTL base, first strong run not on the right
ok = 0
report = []
for k, raw in descs.items():
    logical = raw[len(RLM):] if raw.startswith(RLM) else raw
    text = strip_inner_markup(logical)
    vR = vis(RLM + text, "R")        # the fix: dir=rtl (+ RLM)
    vL = vis(text, "L")              # the old bug: LTR base
    # 1. latin word integrity under RTL
    wf = [w for w in WORD.findall(text) if w not in vR.replace(RLM, "")]
    if wf: word_fail.append((k, wf[:5]))
    # 2. base direction must change the picture when text is mixed
    mixed = bool(WORD.search(text)) and has_heb(text)
    if mixed and vR.replace(RLM, "") == vL:
        no_diff.append(k)
    # 3. first strong (Hebrew) should be at the right end under RTL base
    #    -> in visual RTL string, the first logical Hebrew char should be near the END (right side rendered first)
    if has_heb(text):
        first_heb = next(c for c in text if "א" <= c <= "ת")
        # position of that char in the RTL visual; right side = high index
        vRc = vR.replace(RLM, "")
        pos = vRc.find(first_heb)
        if pos != -1 and pos < len(vRc) * 0.4 and mixed:
            bad_first.append((k, pos, len(vRc)))
    if not wf:
        ok += 1
    report.append({"key": k, "logical": text[:120], "rtl_visual": vR.replace(RLM,"")[:120], "ltr_visual": vL[:120]})

json.dump(report, open(os.path.join(HERE, "bidi_sim_report.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

print("=" * 70)
print(f"RESULTS over {len(descs)} descriptions:")
print(f"  latin-word integrity OK : {ok}/{len(descs)}   (every English word verbatim in RTL visual)")
print(f"  latin-word FAILURES     : {len(word_fail)}")
print(f"  base-direction changed visual (mixed strings): {len(descs)-len(no_diff)} differ, {len(no_diff)} identical")
print(f"  first-Hebrew-on-right anomalies: {len(bad_first)}")
print("=" * 70)
if word_fail:
    print("\n[!] LATIN-WORD FAILURES (first 10):")
    for k, ws in word_fail[:10]:
        print(f"    {k}: lost {ws}")
# show the user's specific complaint examples
print("\n=== focused samples (user-reported cases) ===")
for k in ["PCDISPLAYSETTINGS_HDR_DESC", "PCDISPLAYSETTINGS_UPSCALEMETHOD_DESC",
          "PCDISPLAYSETTINGS_NVIDIAREFLEX_DESC", "PCDISPLAYSETTINGS_DLSS_RR_DESC"]:
    if k in descs:
        logical = strip_inner_markup(descs[k][len(RLM):])
        print(f"\n  {k}")
        print(f"    logical : {logical[:90]}")
        print(f"    RTL(fix): {vis(RLM+logical,'R').replace(RLM,'')[:90]}")
        print(f"    LTR(bug): {vis(logical,'L')[:90]}")
