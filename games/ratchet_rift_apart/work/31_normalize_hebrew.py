"""Deterministic QA-normalize of the community-compute Hebrew (UNTRUSTED output).

The volunteer fleet finished all 17,624 lines (cc_lines status=done). The content is
good, but the RAW output has three DETERMINISTICALLY-REPAIRABLE structure issues that
are pure string ops, never translation decisions ("repair, don't reject"):

  1. niqqud            — strip U+0591..U+05C7 (192 lines)
  2. New-Era panel leak — a worker echoed the reference panel; cut at the first
                          "\nFR:" / "\nDE:" / ... marker (+ a spurious leading "EN: ")
  3. structural prefix — the game's loc value carries a leading <name="..">/<ts="..">
                          (HTML-escaped &quot;) that some workers dropped or un-escaped.
                          Restore the EN's exact escaped leading prefix, and re-escape
                          the whole line to the loc-native form (& -> &amp;, " -> &quot;).

Everything is rebuilt against the ENGLISH source (games/.../extract/ct_upload.json), so
no Hebrew meaning is invented. Genuinely-wrong lines (content misaligned to the key,
garbled mixed-script hallucination, EN duplicated, spurious/missing printf) can't be
fixed by a string op -> written to redo.json for a targeted re-translation (delegated).

    python 31_normalize_hebrew.py            # write hebrew_clean.json + redo.json
    python 31_normalize_hebrew.py --apply    # also overwrite hebrew.json (backs up first)
"""
import json, os, re, sys, shutil, time

HERE = os.path.dirname(os.path.abspath(__file__))
HEB  = os.path.join(HERE, "hebrew.json")
CT   = os.path.join(HERE, "..", "extract", "ct_upload.json")
CLEAN= os.path.join(HERE, "hebrew_clean.json")
REDO = os.path.join(HERE, "redo.json")

heb  = json.load(open(HEB, encoding="utf-8"))
_ct  = json.load(open(CT, encoding="utf-8"))
en      = {r["string_key"]: r["source_en"] for r in _ct}
section = {r["string_key"]: r.get("section", "") for r in _ct}

NIQQUD = re.compile(r'[֑-ׇ]')
PANEL  = re.compile(r'\n\s*(?:FR|DE|IT|ES|RU|PL|EN)\s*:')     # leaked reference panel
LEADLBL= re.compile(r'^\s*(?:EN|FR|DE|IT|ES|RU|PL)\s*:\s*')   # spurious "EN: " prefix
LEAD   = re.compile(r'^\s*((?:<name="[^"]*">)?(?:<ts="[^"]*">)?)')  # struct prefix (unescaped)
TS     = re.compile(r'<ts="[^"]*">')
_PF = re.compile(r'%[#0-9.\-+]*[dsifuxX]')                   # a real conversion (NO space flag)
def PRINTF_set(s):                                          # %% is an escaped literal, not a conv
    return sorted(_PF.findall(s.replace("%%", "")))
HEBREW = re.compile(r'[֐-׿]')
# foreign scripts that are a hallucination (Ω U+03A9 weapon symbol is intentional -> excluded)
BADFOREIGN = re.compile(r'[؀-ۿЀ-ӿ一-鿿฀-๿'
                        r'Ͱ-ΨΪ-Ͽ가-힯ऀ-ॿ'
                        r'Ⴀ-ჿ぀-ヿ]')

def unesc(s):
    # tolerate a worker's malformed entity (&quot without the semicolon)
    return s.replace("&quot;", '"').replace("&quot", '"').replace("&amp;", "&")
def esc(s):    return s.replace("&", "&amp;").replace('"', "&quot;")
def is_namey(e):
    return bool(re.sub(r'[^A-Za-z ]', '', e).strip()) and not re.search(r'\b[a-z]{3,}\b', e)

clean, redo = {}, {}
stats = dict(niqqud=0, panel=0, prefix=0, en_copy_stripped=0, marker_added_removed=0,
             redo_garbled=0, redo_printf=0, redo_misalign=0, redo_nocontent=0,
             passthrough=0)

def strip_en_copy(eu, hu):
    """Worker sometimes echoes the ENGLISH then appends the Hebrew on a new line:
    'Increase max ammo.\\nמגדיל...'. If a leading \\n-delimited chunk has NO Hebrew and
    the Hebrew lives after it, drop the English echo and keep the Hebrew."""
    if "\n" not in hu or HEBREW.search(hu.split("\n", 1)[0]):
        return hu, False
    head, tail = hu.split("\n", 1)
    if HEBREW.search(tail) and not HEBREW.search(head) and re.search(r'[A-Za-z]', head):
        return tail.strip(), True
    return hu, False

for k, raw in heb.items():
    e  = en.get(k, "")
    eu = unesc(e)
    h  = raw

    # 1) niqqud (deterministic)
    if NIQQUD.search(h): h = NIQQUD.sub("", h); stats["niqqud"] += 1
    # 2) leaked New-Era reference panel + spurious "EN:" label
    m = PANEL.search(h)
    if m: h = h[:m.start()].rstrip(); stats["panel"] += 1
    h = LEADLBL.sub("", h)

    hu = unesc(h).strip()
    # 2b) strip an English echo that precedes the Hebrew
    hu, did = strip_en_copy(eu, hu)
    if did: stats["en_copy_stripped"] += 1
    # 2c) if the EN loc value carries NO <ts>/<name> at all (a lyric / plain line), remove any
    #     structural marker the worker invented — the game renders it as plain text.
    if not re.search(r'<(?:ts|name)="', eu):
        stripped = re.sub(r'<(?:ts|name)="[^"]*">', '', hu)
        if stripped != hu:
            hu = re.sub(r'\s+', ' ', stripped).strip()
            stats["marker_added_removed"] += 1

    en_has_word = bool(re.search(r'\b[a-z]{3,}\b', eu))

    # ---- REDO only genuine CONTENT failures (can't be a string op) ----
    # (a) garbled mixed-script hallucination (Ω weapon symbol is excluded from BADFOREIGN)
    if BADFOREIGN.search(hu):
        redo[k] = e; stats["redo_garbled"] += 1; continue
    # (b) printf conversions dropped/added (a real number/format error; %% is a literal)
    if PRINTF_set(eu) != PRINTF_set(hu):
        redo[k] = e; stats["redo_printf"] += 1; continue
    # (c) EN is real prose but HE carries NO Hebrew and is NOT a name/code passthrough.
    #     Proper-noun venue names / URLs / credits headers legitimately stay Latin.
    if not HEBREW.search(hu):
        looks_passthrough = (
            is_namey(e) or not en_has_word
            or "http" in eu.lower() or eu.strip().startswith("<h2>")
            or section.get(k) == "קרדיטים"
            or len(re.findall(r'\b[a-z]{3,}\b', eu)) <= 1   # proper-noun phrase (≤1 real lowercase word)
        )
        if looks_passthrough:
            clean[k] = esc(hu); stats["passthrough"] += 1; continue
        redo[k] = e; stats["redo_nocontent"] += 1; continue
    # NOTE: a length-based "misalignment" check is pure noise here — a good long subtitle
    # that merely dropped its <ts> prefix (restored deterministically below) trips it. The
    # one genuine misalignment (NEFCITY_026, Hebrew=ammo-desc for a subtitle key) is already
    # caught by the printf check above (its HE carries a %d the subtitle EN never had).

    # 3) restore the EN's exact leading structural prefix (escaped, native form)
    ep = LEAD.match(eu).group(1)
    if ep:
        hp = LEAD.match(hu).group(1)
        if hp != ep:
            hu = ep + hu[len(hp):]
            stats["prefix"] += 1

    clean[k] = esc(hu)

json.dump(clean, open(CLEAN, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump(redo,  open(REDO,  "w", encoding="utf-8"), ensure_ascii=False, indent=1)

print(f"in={len(heb)}  clean={len(clean)}  redo={len(redo)}")
for kk, vv in stats.items(): print(f"  {kk:14} {vv}")
print(f"\n[+] {CLEAN}")
print(f"[+] {REDO}")

if "--apply" in sys.argv:
    bak = HEB + f".bak.{time.strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(HEB, bak)
    json.dump(clean, open(HEB, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[+] applied -> {HEB}  (backup {os.path.basename(bak)})")
    print(f"    redo lines stay in redo.json; clean set = {len(clean)}")
