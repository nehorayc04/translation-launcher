"""
Build the Far Cry 6 community-/translate upload from the live common.fat oasis.

Two clean, build-mappable text sets (both have a validated Arabic deploy slot in
common.fat -- 100% shared (nameCRC,id) keys with the English source):

  UI/HUD/items/missions  english master 5de3f8f3f2bdfd29  ->  Arabic 14f790b7fb9610c2
  story dialogue/subs    english        ac6c6b98881697fc  ->  Arabic 0ea78cb51ffc5bf5

string_key = "<set>:<nameCRC>:<id>"  (set in {ui,sub}) -- unique, and the Phase-2
build maps it straight back onto (oasis, section, id) via fc6_oasis.edit.

Categories (Hebrew section labels -> the site's category chips, by visibility):
  1 ממשק ותפריטים          UI labels / menus / HUD / buttons
  2 פריטים, נשקים וציוד     item / weapon / gear names + stats
  3 כתוביות עלילה           story dialogue / cutscene subtitles (the 21,715 set)
  4 תיאורים, משימות ותוכן   long prose: notes, codex, mission/objective text

Output: extract/ct_upload.json  (+ a printed category report).
Run with the repo .venv python.
"""
import sys, os, re, json, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fc6_fat import Fat
import fc6_oasis as O

FAT = os.environ.get("FC6_FAT", r"F:/Game Lab/Far Cry 6/data_final/pc/common.fat")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "extract", "ct_upload.json")

EN_UI  = 0x5de3f8f3f2bdfd29    # english master (1118 sec / 26,795)
AR_UI  = 0x14f790b7fb9610c2    # arabic  UI deploy slot (1117 sec / 26,793)
EN_SUB = 0xac6c6b98881697fc    # english story dialogue / subtitles (21,715)
AR_SUB = 0x0ea78cb51ffc5bf5    # arabic  subtitle deploy slot (21,715)

CAT_UI, CAT_ITEM, CAT_SUB, CAT_PROSE = (
    "ממשק ותפריטים", "פריטים, נשקים וציוד", "כתוביות עלילה", "תיאורים, משימות ותוכן")
CAT_ORDER = [CAT_UI, CAT_ITEM, CAT_SUB, CAT_PROSE]

# engine tokens to strip when deciding "is there real translatable text?"
_TOK = re.compile(r"\[[^\]]*\]|\{[^}]*\}|%[#0-9.*\-+ ]*[a-zA-Z]|&[a-zA-Z#0-9]+;|\\[nrt]")
_WORD = re.compile(r"[A-Za-z\u00C0-\u024F]+")   # latin incl. accented
# item / weapon / combat signal (route to CAT_ITEM)
_ITEM = re.compile(
    r"\b(damage|ammo|rounds|reload|magazine|resist|resistance|deals?|supremo|resolver|"
    r"weapon|rifle|pistol|shotgun|sniper|silencer|suppressor|scope|mod|perk|armou?r|"
    r"grenade|explosive|incendiary|poison|blast|clip|caliber|holster|gunpowder|"
    r"machetero|guerrillero|explorador|capit[aá]n|esp[ií]a)\b", re.I)
_STAT = re.compile(r"FORMAT_TETRA|ICON_RANK|\[STYLE|\d+\s*(m|kg|%|rounds?|dmg)\b", re.I)
_SENT_END = re.compile(r"[.!?…]\s*$")


def load(h):
    _, secs = O.parse(Fat(FAT).read_data(Fat(FAT).by_hash[h]))
    m = {}
    for s in secs:
        for sid, val in s.values.items():
            m[(s.nameCRC, sid)] = val
    return m


def core(s):
    return _TOK.sub(" ", s).strip()


def translatable(s):
    c = core(s)
    return bool(_WORD.search(c))          # needs at least one real word after tokens


def ui_category(en):
    if _ITEM.search(en) or _STAT.search(en):
        return CAT_ITEM
    c = core(en)
    wc = len(c.split())
    # short label with no sentence ending, OR an ALL-CAPS heading -> UI
    if (wc <= 5 and not _SENT_END.search(c)) or (c.isupper() and wc <= 8):
        return CAT_UI
    return CAT_PROSE


def main():
    en_ui, en_sub = load(EN_UI), load(EN_SUB)
    ar_ui_keys, ar_sub_keys = set(load(AR_UI)), set(load(AR_SUB))

    rows = []
    dropped = collections.Counter()

    # --- UI set: only keys that also exist in the Arabic slot (deployable) ---
    for k in en_ui:
        if k not in ar_ui_keys:
            dropped["ui_no_arabic_slot"] += 1; continue
        en = en_ui[k]
        if not translatable(en):
            dropped["ui_nontranslatable"] += 1; continue
        rows.append(("ui", k, en, ui_category(en)))

    # --- subtitle set ---
    for k in en_sub:
        if k not in ar_sub_keys:
            dropped["sub_no_arabic_slot"] += 1; continue
        en = en_sub[k]
        if not translatable(en):
            dropped["sub_nontranslatable"] += 1; continue
        rows.append(("sub", k, en, CAT_SUB))

    # order by category visibility, then keep a stable order inside each
    by_cat = collections.defaultdict(list)
    for setname, k, en, cat in rows:
        by_cat[cat].append((setname, k, en))

    out = []
    for ci, cat in enumerate(CAT_ORDER):
        for j, (setname, (nameCRC, sid), en) in enumerate(by_cat[cat]):
            out.append({
                "string_key":  f"{setname}:{nameCRC}:{sid}",
                "source_en":   en,
                "current_he":  "",
                "context":     "",
                "section":     cat,
                "order_index": ci * 1_000_000 + j,
            })

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)

    print(f"wrote {len(out)} rows -> {os.path.abspath(OUT)}")
    for cat in CAT_ORDER:
        print(f"   {cat:22} {len(by_cat[cat]):>6}")
    print("dropped:", dict(dropped))
    lens = sorted(len(r["source_en"]) for r in out)
    if lens:
        print(f"source_en len  min/med/max = {lens[0]}/{lens[len(lens)//2]}/{lens[-1]}")
    keymax = max(len(r["string_key"]) for r in out)
    print(f"string_key max len = {keymax}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
