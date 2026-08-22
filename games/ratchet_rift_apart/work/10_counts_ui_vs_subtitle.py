"""UI vs SUBTITLE vs SKIP classification of the R&C Rift Apart localization.

Loads the English variant (variant_18), parses its DAT1 (payload=raw[36:]),
reads every (key, english_value) pair from KEYS/VALUES via KEY_OFFSETS/
TEXT_OFFSETS/ENTRY_COUNT, then classifies each entry by KEY PREFIX + value
shape into UI / SUBTITLE / SKIP. Read-only. Playbook Stage 7 count report."""
import os, sys, io, re, struct, json
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
LOCS = os.path.join(ROOT, "games", "ratchet_rift_apart", "extracted", "loc_variants")
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import dat1lib, dat1lib.types.dat1

TAG_VALUES       = 0x70A382B8
TAG_KEYS         = 0x4D73CEBD
TAG_TEXT_OFFSETS = 0xF80DEEB4
TAG_KEY_OFFSETS  = 0xA4EA55B2
TAG_ENTRY_COUNT  = 0xD540A903

EN = os.path.join(LOCS, "variant_18_idx312859.localization")
raw = open(EN, "rb").read()
payload = raw[36:]
dat = dat1lib.types.dat1.DAT1(io.BytesIO(payload), None)
secs = {sh.tag: (sh.offset, sh.size) for sh in dat.header.sections}
def sec(tag): o, s = secs[tag]; return payload[o:o+s]

n = struct.unpack("<I", sec(TAG_ENTRY_COUNT))[0]
keys_blob, values_blob = sec(TAG_KEYS), sec(TAG_VALUES)
toff = list(struct.unpack(f"<{n}I", sec(TAG_TEXT_OFFSETS)))
koff = list(struct.unpack(f"<{n}I", sec(TAG_KEY_OFFSETS)))
def cstr(buf, off):
    e = buf.find(b"\x00", off); e = e if e >= 0 else len(buf)
    return buf[off:e]

entries = []
for i in range(n):
    k = cstr(keys_blob, koff[i]).decode("utf-8", "replace")
    v = cstr(values_blob, toff[i]).decode("utf-8", "replace")
    entries.append((k, v))

# --- prefix breakdown (token before the first _ ; else whole key) -----------
def prefix(k):
    m = re.match(r"^([A-Za-z0-9]+)", k)
    return m.group(1).upper() if m else "(none)"

pref_counter = Counter(prefix(k) for k, _ in entries)
pref_sample = {}
for k, v in entries:
    p = prefix(k)
    if p not in pref_sample:
        pref_sample[p] = (k, v)

# --- classification ---------------------------------------------------------
# strip markup/tokens for the "letters" test
TOK = re.compile(r"<[^>]+>|\{[^}]*\}|\[[^\]]*\]|\\[nrt]|&[a-z]+;|%[0-9.]*[sdfx%]")
def visible(v): return TOK.sub("", v)
WORD = re.compile(r"[A-Za-zÀ-ɏ]+")

UI_PREFIXES = {
    "MENU","BTN","BUTTON","HUD","SETTING","SETTINGS","OPTION","OPTIONS","TEXT","LABEL",
    "WEAPON","GADGET","ITEM","ARMOR","ARMOUR","EQUIP","GEAR","AMMO","SKIN",
    "ACTIVITY","CARD","TROPHY","TUTORIAL","TUT","HELP","TIP","LOADING","LOAD",
    "UI","FE","FRONTEND","PAUSE","MAP","PLANET","LEVEL","AREA","STORE","SHOP",
    "GALACTIC","VENDOR","UPGRADE","STAT","CURRENCY","BOLT","RAND","PLAN","HOLO",
    "CONTROLLER","CONTROL","KEY","BIND","PLATFORM","SYSTEM","SYS","ERR","ERROR",
    "MSG","NOTIF","POPUP","DIALOG_UI","OBJECTIVE","QUEST_UI","MISSION","GOAL",
    "CREDIT","CREDITS","LANG","LANGUAGE","ACCESSIBILITY","DIFFICULTY","DIFF",
    "GAMEPLAY","DISPLAY","AUDIO","VIDEO","GRAPHICS","SAVE","GLOSSARY","LORE",
    "NAME","TITLE","DESC","DESCRIPTION","HEADER","FOOTER","TAB","PROMPT",
    "COLLECTIBLE","COLLECT","ARENA","CHALLENGE","REWARD","ENEMY","BOSS",
    "ACHIEVEMENT","STATUS","EFFECT","MOD","MODIFIER","PERK","ABILITY",
}
SUB_PREFIXES = {
    "DIALOG","DIALOGUE","SUBTITLE","SUB","CINE","CINEMATIC","VO","BARK",
    "CONVO","CONVERSATION","LINE","SPEECH","CUTSCENE","SCENE","AMBIENT",
    "CHATTER","COMM","RADIO","BANTER","NARRATION","NARR","STORY_VO",
}
SKIP_VALUE = re.compile(r"^\s*$|^INVALID$|^[\W\d_]+$", re.I)

TS_TAG = re.compile(r"<ts\b|<ts=")   # Insomniac VO/subtitle timing tag = spoken line

def classify(k, v):
    p = prefix(k)
    vis = visible(v).strip()
    words = WORD.findall(vis)
    letters = sum(len(w) for w in words)
    # SKIP: empty / dev tokens / pure symbol-number / no letters at all
    if not vis or SKIP_VALUE.match(vis) or vis.upper() in ("INVALID","TODO","PLACEHOLDER","DEBUG","N/A","---"):
        return "skip"
    if letters == 0:
        return "skip"
    # DECISIVE subtitle signal: a <ts=...> timing tag = a timed spoken VO line
    # (same Insomniac marker as SM2). Wins over everything, incl. short barks.
    if TS_TAG.search(v):
        return "subtitle"
    # explicit prefix routing
    if p in SUB_PREFIXES:
        return "subtitle"
    if p in UI_PREFIXES:
        return "ui"
    # shape heuristic: subtitle = long, sentence-like prose
    #   long value OR ends with sentence punctuation and multiple words OR has <br>
    long = len(vis) >= 90
    many_words = len(words) >= 8
    sentence_end = bool(re.search(r"[.!?…]\s*$", vis)) and len(words) >= 4
    has_break = "<br" in v.lower() or "\\n" in v
    if long or (many_words and (sentence_end or has_break)):
        return "subtitle"
    return "ui"

buckets = Counter()
bucket_prefix = defaultdict(Counter)
for k, v in entries:
    c = classify(k, v)
    buckets[c] += 1
    bucket_prefix[c][prefix(k)] += 1

# --- report -----------------------------------------------------------------
print(f"[*] entries parsed: {len(entries)} (entry_count={n})\n")
print("=== top 30 key prefixes ===")
for p, cnt in pref_counter.most_common(30):
    k, v = pref_sample[p]
    s = v.replace("\n", " ")[:70]
    print(f"  {p:22} {cnt:6}  e.g. {k[:34]:34} = {s!r}")

print("\n=== UI / SUBTITLE / SKIP split ===")
tot = len(entries)
for b in ("ui", "subtitle", "skip"):
    print(f"  {b:9} {buckets[b]:7}  ({100*buckets[b]/tot:.1f}%)")
transl = buckets["ui"] + buckets["subtitle"]
print(f"  translatable (ui+subtitle) = {transl}")

print("\n=== top prefixes per bucket ===")
for b in ("ui", "subtitle", "skip"):
    top = ", ".join(f"{p}({c})" for p, c in bucket_prefix[b].most_common(12))
    print(f"  {b}: {top}")

# machine-readable dump
out = {
    "total_keys": len(entries),
    "ui": buckets["ui"], "subtitle": buckets["subtitle"], "skip": buckets["skip"],
    "translatable": transl,
    "prefixes": {p: c for p, c in pref_counter.most_common(30)},
}
json.dump(out, open(os.path.join(HERE, "counts_ui_vs_subtitle.json"), "w"), ensure_ascii=False, indent=2)
print("\n[+] wrote counts_ui_vs_subtitle.json")
