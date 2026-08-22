"""Comprehensive WD2 Hebrew QA scanner — find EVERY defect class across the whole
translated corpus, deterministically (no LM). Reads the SAME translation sources
the build combines, classifies each id's render orientation from the oasis enum,
and flags every issue the user reported in-game.

Issue classes:
  MISORIENTED   - stored LOGICAL but enum is NOT soundbinary -> renders REVERSED in
                  the non-bidi frontend (the big one: descriptions/missions/menus).
  TOKEN_MISMATCH- preserved-token multiset differs EN vs HE (structural).
  ENGLISH_LEAK  - a real lowercase English word left in the Hebrew (not a token/name).
  FOREIGN       - non-Hebrew/non-Latin script leaked in.
  NIQQUD        - Hebrew vowel points (banned).
  ICON_TOKEN    - carries a HUD icon token ([..ICON]/[HACKERSPACE]/...) that may show
                  as tofu (square) in the Arabic-slot font -> needs investigation.
  BRACKET       - ()/[]/{} imbalance in HE vs EN (after stripping tokens).
  OVERFLOW      - HE visibly much longer than EN -> clipping risk in fixed UI boxes.
  PLACENAME     - EN contains a real-world place/brand -> glossary consistency target.
  UNTRANSLATED  - HE empty / identical to EN / no Hebrew though EN has real words.

  python wd2_full_qa_scan.py            # summary + writes c:/tmp/wd2_qa_report/*
"""
import json, os, re, sys, collections
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE  = os.path.dirname(os.path.abspath(__file__))
ROOT  = os.path.dirname(HERE)
OASIS = os.path.join(ROOT, "extract", "en_oasis", "languages", "english",
                     "oasisstrings_converted.xml")
UI_ALL   = r"C:/tmp/wd2_ui_all.json"
UI_HE    = r"C:/tmp/wd2_ui_he.json"
HANDOFF  = os.path.join(ROOT, "agent_handoff", "hebrew.json")
SUB_HE   = os.path.join(ROOT, "agent_handoff_subs", "hebrew.json")
OUTDIR   = r"C:/tmp/wd2_qa_report"

STRING_RE = re.compile(r'<string\s+enum="([^"]*)"\s+LineId="(\d+)"\s+value="([^"]*)"\s*/>')
TOKEN = re.compile(r'\[[A-Za-z0-9_]+\]|\{[^}]*\}|%[0-9.]*[diufslxeDIUFSLXE]+|%%|&#?[A-Za-z0-9]+;')
NL    = re.compile(r'\\n')
NIQQUD = re.compile(r'[֑-ׇ]')
FOREIGN = re.compile(r'[Ѐ-ӿ؀-ۿ฀-๿Ͱ-Ͽ'
                     r'一-鿿가-힯぀-ヿऀ-ॿ]')
HEB   = re.compile(r'[א-ת]')
ICON  = re.compile(r'\[[A-Z][A-Z0-9_]*(?:ICON|SHOPICON|HACKERSPACE|_ACCESS)[A-Z0-9_]*\]'
                   r'|\[HACKERSPACE\]|\[CLOTHINGSHOPICON\]|\[CAR[A-Z_]*ICON\]')
LOWER_WORD = re.compile(r'(?<![A-Za-z])[a-z][a-z]{2,}(?![A-Za-z])')

# real-world places + brands that need a consistent canonical Hebrew rendering
PLACES = [
    "Bay Area", "San Francisco", "Oakland", "Marin", "Silicon Valley", "Alcatraz",
    "Golden Gate", "Nob Hill", "Chinatown", "Sausalito", "Berkeley", "Palo Alto",
    "Fremont", "Menlo Park", "San Mateo", "Bakersfield", "Castro", "Tenderloin",
    "Pacific Heights", "Mission District", "Marina", "Embarcadero", "East Bay",
    "Peninsula", "Point Bonita", "Los Angeles", "New York", "Frisco",
]
PLACE_RE = re.compile("|".join(re.escape(p) for p in sorted(PLACES, key=len, reverse=True)))

def jload(p, d):
    try: return json.load(open(p, encoding="utf-8"))
    except Exception: return d

def clean_en(raw):
    s = raw.replace("&apos;", "'").replace("&quot;", '"')
    s = s.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
    return s.replace("\r", " ").replace("\n", " ").strip()

def strip_tokens(s):
    s = TOKEN.sub(" ", s); s = NL.sub(" ", s)
    return s

def _lbnorm(s):
    for r in ("&#xA;", "&#xa;", "&#xD;", "&#xd;", "\\n", "\\r", "\r", "\n"):
        s = s.replace(r, "\x00")
    return s

def toks_norm(s):
    """token multiset with EVERY line-break representation collapsed to one <LB>
    marker, so &#xA; vs \\n vs a real newline is NOT a false TOKEN_MISMATCH."""
    n = _lbnorm(s)
    c = collections.Counter(TOKEN.findall(n)); c["<LB>"] = n.count("\x00")
    return c

def is_namey(en):
    """EN is a pure proper-noun / code (Latin OK to keep) -> not a real 'untranslated'."""
    core = strip_tokens(en).strip()
    words = re.findall(r"[A-Za-z][A-Za-z'.\-]*", core)
    return (bool(words) and len(words) <= 4 and all(w[0].isupper() for w in words)) \
        or not re.search(r'[a-z]{2,}', core)

def main():
    os.makedirs(OUTDIR, exist_ok=True)
    # oasis: id -> (enum, en)
    meta = {}
    with open(OASIS, encoding="utf-8") as f:
        for m in STRING_RE.finditer(f.read()):
            meta[int(m.group(2))] = (m.group(1), clean_en(m.group(3)))
    sound = {i for i, (e, _) in meta.items() if e.startswith("soundbinary")}

    ui = {}
    for p in (UI_ALL, UI_HE, HANDOFF):           # later wins (handoff = final)
        ui.update({int(k): v for k, v in jload(p, {}).items()})
    sub = {int(k): v for k, v in jload(SUB_HE, {}).items()}

    # effective storage: in ui -> visual; elif in sub -> logical
    rows = []
    for i, (enum, en) in meta.items():
        he = None; storage = None
        if i in ui and str(ui[i]).strip():
            he, storage = ui[i], "visual"
        elif i in sub and str(sub[i]).strip():
            he, storage = sub[i], "logical"
        if he is None:
            continue
        flags = []
        # 1 orientation
        if storage == "logical" and i not in sound:
            flags.append("MISORIENTED")
        # 2 token multiset (line-break representations normalized -> no false flags)
        if toks_norm(en) != toks_norm(he):
            flags.append("TOKEN_MISMATCH")
        # 3 english leak (lowercase real word left in HE that's not a token)
        core = strip_tokens(he)
        leaks = LOWER_WORD.findall(core)
        if leaks and HEB.search(core):
            flags.append("ENGLISH_LEAK")
        # 4 foreign script
        if FOREIGN.search(he):
            flags.append("FOREIGN")
        # 5 niqqud
        if NIQQUD.search(he):
            flags.append("NIQQUD")
        # 6 icon token
        if ICON.search(en) or ICON.search(he):
            flags.append("ICON_TOKEN")
        # 7 bracket balance (after stripping preserved tokens)
        hb = strip_tokens(he)
        for op, cl in (("(", ")"), ("[", "]"), ("{", "}")):
            if hb.count(op) != hb.count(cl):
                flags.append("BRACKET"); break
        # 8 overflow: HE visible much longer than EN visible (label clipping)
        ev = len(re.sub(r"\s+", " ", strip_tokens(en)).strip())
        hv = len(re.sub(r"\s+", " ", strip_tokens(he)).strip())
        single = "\\n" not in he and "[LF]" not in he and "[CR]" not in he
        if ev and ((single and ev <= 70 and hv > ev * 1.35 + 6) or hv > ev * 1.7 + 12):
            flags.append("OVERFLOW")
        # 9 placename
        if PLACE_RE.search(en):
            flags.append("PLACENAME")
        # 10 untranslated (skip pure name/code passthroughs — Latin is correct there)
        if not is_namey(en) and (he.strip() == en.strip() or
           (not HEB.search(he) and re.search(r"[A-Za-z]{3,}", strip_tokens(en)) and not ICON.search(he))):
            flags.append("UNTRANSLATED")
        if flags:
            rows.append({"id": i, "enum": enum, "storage": storage,
                         "sound": i in sound, "flags": flags, "en": en, "he": he})

    # report
    counts = collections.Counter(f for r in rows for f in r["flags"])
    by_enum_misor = collections.Counter(r["enum"].split("\\")[0].split("_")[0]
                                        for r in rows if "MISORIENTED" in r["flags"])
    total_tr = sum(1 for i in meta if (i in ui and str(ui[i]).strip()) or (i in sub and str(sub[i]).strip()))
    print(f"translated ids: {total_tr}   (ui/visual={sum(1 for i in meta if i in ui and str(ui.get(i,'')).strip())}, "
          f"sub/logical={sum(1 for i in meta if i in sub and str(sub.get(i,'')).strip() and not(i in ui and str(ui.get(i,'')).strip()))})")
    print(f"flagged ids   : {len(rows)}")
    print("--- by class ---")
    for k, c in counts.most_common():
        print(f"  {k:14} {c}")
    print("--- MISORIENTED by enum-family (top 20) ---")
    for k, c in by_enum_misor.most_common(20):
        print(f"  {k:26} {c}")

    # dumps
    with open(os.path.join(OUTDIR, "flags.jsonl"), "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    for cls in counts:
        with open(os.path.join(OUTDIR, f"{cls}.jsonl"), "w", encoding="utf-8") as f:
            for r in rows:
                if cls in r["flags"]:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\n-> {OUTDIR}/flags.jsonl (+ per-class files)")

if __name__ == "__main__":
    main()
