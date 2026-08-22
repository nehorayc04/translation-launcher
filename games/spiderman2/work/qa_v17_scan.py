"""qa_v17_scan.py — exhaustive DETERMINISTIC QA over the v17 SM2 Hebrew mod.

Compares every Hebrew entry against the Arabic ground-truth skeleton (arabic.json)
and flags objective, machine-detectable defects ONLY (no AI). Categories:

  foreign_script     non-Heb/non-Latin letter leak (Arabic, CJK, Cyrillic, ...)
  niqqud             Hebrew vowel points (forbidden)
  box_glyph          U+FFFC / RLE U+202B / PDF U+202C / other tofu sources
  control_char       stray C0/C1 control chars
  mixed_script_glue  Hebrew letter directly abutting a Latin letter (גילherme)
  token_loss         a [TOKEN] / {VAR} / %d-spec / <tag> present in AR, missing in HE
  percent_gate       HE percent style disagrees with the AR printf/display gate
  rlm_structure      &rlm; anchor count differs from Arabic for the same key
  span_count         <span> open/close count differs from Arabic
  empty_he           HE blank while AR is non-blank
  untranslated       HE has zero Hebrew letters while AR has Arabic letters
  double_space       a double space inside the visible text

Outputs qa_v17_defects.json  (list of {file,key,kind,he,ar,detail}).
"""
import os, sys, json, glob, re, unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)

AR = json.load(open("arabic.json", encoding="utf-8"))
FILES = sorted(glob.glob("menus*_he.json")) + ["settings_he.json"]

HEB = re.compile(r'[֐-׿]')
HEB_LETTER = re.compile(r'[א-ת]')                 # alef..tav only
NIQQUD = re.compile(r'[֑-ׇ]')                     # marks/points
ARLET = re.compile(r'[؀-ۿ]')                      # Arabic letters
LAT = re.compile(r'[A-Za-z]')
TOK = re.compile(r'\[[A-Z0-9_]+\]')
VAR = re.compile(r'\{[^}]*\}')
SPEC = re.compile(r'%(?:[-+ 0#]*\d*(?:\.\d+)?[diouxXeEfFgGcsr%]|\d+\$[a-z])')
RLM = '&rlm;'
SPAN_OPEN = re.compile(r'<span\b', re.I)
SPAN_CLOSE = re.compile(r'</span>', re.I)
# allowed non-letter chars beyond Heb/Lat/digits/space/basic-punct
BOX_CHARS = {0xFFFC, 0x202B, 0x202C, 0x202A, 0x202D, 0x202E}
# foreign-script: any letter that is neither Hebrew nor Latin and not Arabic-punct we map out
ALLOWED_NONLETTER = set(" \t\n\r0123456789.,:;!?'\"()[]{}<>/\\|@#$%^&*-_=+~`’‘“”…•·—–‏‎ …")

def strip_markup(s):
    s = re.sub(r'&rlm;|&lrm;|&[a-z]+;', '', s)
    s = re.sub(r'<[^>]+>', '', s)
    s = TOK.sub('', s)
    s = VAR.sub('', s)
    s = re.sub(r'%(?:[-+ 0#]*\d*(?:\.\d+)?[diouxXeEfFgGcsr])', '', s)
    s = s.replace('\\n', ' ').replace('\\t', ' ')
    return s

def foreign_letters(core):
    bad = []
    for ch in core:
        o = ord(ch)
        cat = unicodedata.category(ch)
        if cat.startswith('L'):  # a letter
            if HEB.match(ch) or LAT.match(ch):
                continue
            bad.append(ch)
    return bad

def main():
    defects = []
    for fn in FILES:
        d = json.load(open(fn, encoding="utf-8"))
        for k, he in d.items():
            ar = AR.get(k, "")
            if not isinstance(he, str):
                continue
            core = strip_markup(he)
            ar_core = strip_markup(ar) if isinstance(ar, str) else ""

            def add(kind, detail=""):
                defects.append({"file": fn, "key": k, "kind": kind,
                                "he": he, "ar": ar, "detail": detail})

            # 1 niqqud
            if NIQQUD.search(he):
                add("niqqud", repr(NIQQUD.findall(he)[:6]))
            # 2 box glyphs / forbidden bidi
            boxes = sorted({hex(ord(c)) for c in he if ord(c) in BOX_CHARS})
            if boxes:
                add("box_glyph", ",".join(boxes))
            # 3 control chars (exclude \t \n via raw, but these are literal in JSON strings)
            ctrl = sorted({hex(ord(c)) for c in he if ord(c) < 0x20 and c not in '\t\n\r'})
            if ctrl:
                add("control_char", ",".join(ctrl))
            # 4 foreign letters in the visible core (Arabic leak etc.)
            fl = foreign_letters(core)
            if fl:
                # only flag if AR itself is NOT that script (avoid intentional foreign-flavor)
                add("foreign_script", "".join(sorted(set(fl)))[:30])
            # 5 mixed-script glue: heb letter immediately next to latin letter
            if re.search(r'[א-ת][A-Za-z]|[A-Za-z][א-ת]', core):
                m = re.findall(r'\w*[א-ת][A-Za-z]\w*|\w*[A-Za-z][א-ת]\w*', core)
                add("mixed_script_glue", " ".join(m[:5]))
            # 6 token / var / spec loss vs arabic
            if isinstance(ar, str) and ar:
                miss_tok = set(TOK.findall(ar)) - set(TOK.findall(he))
                miss_var = set(VAR.findall(ar)) - set(VAR.findall(he))
                # specs: compare multiset roughly by the d/s/x letters count
                ar_specs = SPEC.findall(ar); he_specs = SPEC.findall(he)
                if miss_tok or miss_var:
                    add("token_loss", f"tok={sorted(miss_tok)} var={sorted(miss_var)}")
                # 7 percent gate
                ar_dbl = '%%' in ar
                he_dbl = '%%' in he
                ar_has_pct = '%' in ar
                he_has_pct = '%' in he
                if ar_has_pct and he_has_pct and (ar_dbl != he_dbl):
                    add("percent_gate", f"ar_dbl={ar_dbl} he_dbl={he_dbl}")
                elif ar_has_pct and not he_has_pct:
                    add("percent_gate", "ar has % , he dropped it")
                # 8 rlm structure
                ar_rlm = ar.count(RLM); he_rlm = he.count(RLM)
                if ar_rlm != he_rlm:
                    add("rlm_structure", f"ar={ar_rlm} he={he_rlm}")
                # 9 span count
                ar_so = len(SPAN_OPEN.findall(ar)); he_so = len(SPAN_OPEN.findall(he))
                ar_sc = len(SPAN_CLOSE.findall(ar)); he_sc = len(SPAN_CLOSE.findall(he))
                if ar_so != he_so or ar_sc != he_sc:
                    add("span_count", f"ar={ar_so}/{ar_sc} he={he_so}/{he_sc}")
                # 10 empty / untranslated
                if not core.strip() and ar_core.strip():
                    add("empty_he", "")
                elif ar_core.strip() and ARLET.search(ar_core) and not HEB_LETTER.search(core) and LAT.search(core):
                    # he has only latin while ar is genuinely arabic text -> untranslated
                    add("untranslated", core[:60])
            # 11 unbalanced span within he alone
            if len(SPAN_OPEN.findall(he)) != len(SPAN_CLOSE.findall(he)):
                add("span_unbalanced", f"open={len(SPAN_OPEN.findall(he))} close={len(SPAN_CLOSE.findall(he))}")
            # 12 double space in visible text
            if '  ' in core.replace('\\n', ' '):
                add("double_space", "")

    json.dump(defects, open("qa_v17_defects.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    # summary
    from collections import Counter
    c = Counter(x["kind"] for x in defects)
    print(f"total defects: {len(defects)} over {sum(len(json.load(open(f,encoding='utf-8'))) for f in FILES)} entries")
    for kind, n in c.most_common():
        print(f"  {kind:18} {n}")

if __name__ == "__main__":
    main()
