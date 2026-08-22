# -*- coding: utf-8 -*-
"""names_apply.py — deterministically replace Latin character/place names in the
Hebrew subtitle+dialogue spine with their canonical Hebrew, from names_research.json
(the agent-filled registry). SAFE: whole-token word boundaries, protects <ts> tags +
[TOKEN]/{VALUE} placeholders, longest-name-first, never touches non-registry words.

Usage:  python names_apply.py            # apply (backup .bak_names2)
        python names_apply.py --dry      # preview counts + samples, write nothing
"""
import json, os, re, shutil, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
DRY = "--dry" in sys.argv
RUN_TS = time.strftime("%Y%m%d_%H%M%S")

# HOLD: common nouns / abilities / geographic common-parts that are EMBEDDED inside
# compound proper names — replacing them standalone corrupts the name (Time Twister ->
# "זמן Twister", Music Man -> "מוזיקה Man", Bird[=Charlie Parker] -> "ציפור"). Proper
# nouns (person/place/org) stay APPLIED; these are held for a later phrase-level pass.
HOLD = {
 # abilities / game mechanics
 "Web","Web-Shooter","Web-Shooters","Web-strike","Spider-Sense","Dash","Strike","Surge",
 "Smash","Blast","Finishers","Ricochet",
 # common nouns
 "Time","Field","Bird","Demon","Music","Tower","Bridge","Suit","Base","Wings","Beasts",
 "Followers","Lightning","Spiders","Underground","Cultist","Brute","Brutes","Drummer",
 # geographic common-parts (break/mix inside place compounds)
 "Point","East","West","Hills","Forest","Square","Central","Upper","Side","River","Main",
 "Battery","Financial","District","Academy","Park","City","Island","Times",
 # dual-use / ambiguous -> safer to hold
 "Red","Big","Wheel","Sand","Hunter","Hunters","Friendly","Portside","Downtown",
}

# PHRASE_MAP: multi-word English proper names -> canonical Hebrew. Applied BEFORE the
# single-token pass (longest phrase first) so a compound place/character name is rendered
# as one clean Hebrew unit instead of a Hebrew+English hybrid (e.g. "קוני Island").
# Character/org names are Hebrew-Wikipedia-verified (2026-06-25 web audit); NYC places use
# the standard Hebrew transliteration/translation. Gameplay/ability compounds are NOT here
# (left English by design) — those are a separate editorial pass.
PHRASE_MAP = {
 # characters / orgs (Hebrew Marvel canon — Wikipedia-verified)
 "Black Cat": "החתולה השחורה",
 "Mr. Negative": "מיסטר נגטיב", "Mr Negative": "מיסטר נגטיב",
 "The Raft": "הרפסודה", "the Raft": "הרפסודה",
 # NYC places (standard Hebrew)
 "New York City": "ניו יורק סיטי",
 "Coney Island": "קוני איילנד",
 "Prospect Park": "פרוספקט פארק", "Central Park": "סנטרל פארק",
 "Battery Park": "בטרי פארק", "Garvey Park": "גארווי פארק",
 "Washington Square Park": "ושינגטון סקוור פארק",
 "Times Square": "כיכר טיימס", "Union Square": "יוניון סקוור",
 "Financial District": "הרובע הפיננסי",
 "Garment District": "גרמנט דיסטריקט", "Meatpacking District": "מיטפקינג דיסטריקט",
 "Upper East Side": "אפר איסט סייד", "Upper West Side": "אפר ווסט סייד",
 "Lower East Side": "לואר איסט סייד", "West Side": "ווסט סייד",
 "East River": "איסט ריבר", "East Harlem": "איסט הארלם",
 "East Village": "איסט וילג'", "West Village": "ווסט וילג'",
 "Brooklyn Bridge": "גשר ברוקלין", "Two Bridges": "טו ברידג'ס",
 "Downtown Brooklyn": "דאונטאון ברוקלין", "Downtown Queens": "דאונטאון קווינס",
 "Forest Hills": "פורסט הילס", "Long Island": "לונג איילנד",
 "Oscorp Tower": "מגדל אוסקורפ", "City Hall": "סיטי הול",
 "Brooklyn Visions Academy": "אקדמיית ברוקלין ויז'נס",
 "Hunters Point": "האנטרס פוינט", "Red Hook": "רד הוק",
 "Grand Central Terminal": "תחנת גרנד סנטרל", "Upper Chinatown": "אפר צ'יינהטאון",
}
reg_raw = json.load(open(os.path.join(HERE, "names_research.json"), encoding="utf-8"))
# build {english_token: hebrew}, dropping SKIP / blank / hebrew==english / HOLD
REG = {}
held = 0
for tok, info in reg_raw.items():
    he = (info.get("hebrew") or "").strip() if isinstance(info, dict) else str(info).strip()
    if not he or he.upper() == "SKIP":
        continue
    if re.fullmatch(r'[A-Za-z].*', he):     # agent left it Latin on purpose -> not a translation
        continue
    if tok in HOLD:
        held += 1
        continue
    REG[tok] = he
# LOWERCASE common-noun siblings of a capitalized registry entry: the registry is built
# from names_research.json's Title-Case keys, and NAME_RE is case-SENSITIVE, so a lowercase
# usage of the same word as an ordinary noun ("the symbiote consumed him", "laced with venom")
# silently bypassed substitution even though the corpus already has an established rendering
# for the capitalized form (Symbiote/Symbiotes -> סימביוט/סימביוטים, Venom -> ונום). Found
# 2026-08-15 re-scanning post-New-Era-2-review (18+ subtitle + 5 dialogue instances). Added as
# explicit extra keys (not a blanket re.IGNORECASE on the whole alternation, which would also
# lowercase-match unrelated common English words that happen to collide with a PERSON name).
LOWER_EXTRA = {"symbiote": "סימביוט", "symbiotes": "סימביוטים", "venom": "ונום"}
for tok, he in LOWER_EXTRA.items():
    REG.setdefault(tok, he)
print(f"registry: {len(REG)} name tokens to apply  ({held} common-noun/ability tokens HELD)")

# alternation regex, LONGEST token first (so 'New York' style multi-part & 'Spider-Man' win)
toks = sorted(REG, key=len, reverse=True)
# Latin word-boundary: not flanked by another Latin letter; allow trailing possessive 's
NAME_RE = re.compile(r"(?<![A-Za-z])(" + "|".join(re.escape(t) for t in toks) + r")(['’]s)?(?![A-Za-z])")
# PHRASE pass — multi-word, LONGEST phrase first, word-bounded, optional possessive 's.
ph_keys = sorted(PHRASE_MAP, key=len, reverse=True)
PHRASE_RE = re.compile(r"(?<![A-Za-z])(" + "|".join(re.escape(t) for t in ph_keys) + r")(['’]s)?(?![A-Za-z])")
print(f"phrase map: {len(PHRASE_MAP)} multi-word names")
TS = re.compile(r'<ts="[^"]*">')
PH = re.compile(r'\[[A-Z0-9_]+\]|\{[A-Za-z0-9_]+\}')
# LITERAL_HOLD: exact multi-word phrases that must NEVER be touched by name substitution
# even though a single word inside them collides with an unrelated character's registry
# entry -- e.g. the CCAP_MUS_LIC_* song-credit "Donna Lee" (a real Charlie Parker jazz
# standard) got half-swapped to "Donna לי" because "Lee" is registered for Ganke Lee.
# Found 2026-08-15 re-scanning post-New-Era-2-review.
LITERAL_HOLD = ["Donna Lee"]
LITERAL_RE = re.compile("|".join(re.escape(s) for s in LITERAL_HOLD)) if LITERAL_HOLD else None
# a Hebrew one-letter prefix + maqaf was only there to attach to a LATIN name;
# once the name is Hebrew, the prefix attaches directly (ו-מיילס -> ומיילס).
HE_NAMES = sorted(set(REG.values()) | set(PHRASE_MAP.values()), key=len, reverse=True)
MAQAF_FIX = re.compile(r'(?<![א-ת])([ובלהמשכ])-(?=(?:' + "|".join(re.escape(h) for h in HE_NAMES) + r'))') if HE_NAMES else None
# title+period is dropped ONLY when directly followed by one of the canonical Hebrew names
# (see repl_text below) -- never a bare lookahead on "any Hebrew letter", which also matches
# an unrelated sentence starting right after ("גברת. תודה" = two full sentences, not a title).
TITLE_RE = re.compile(r'(?<![א-ת])(ד"ר|דוקטור|מר|מיסטר|גברת|גב\'|דוק)\.(?=\s*(?:'
                       + "|".join(re.escape(h) for h in HE_NAMES) + r')\b)') if HE_NAMES else None

def repl_text(t):
    # protect placeholders
    holds = []
    def stash(m):
        holds.append(m.group(0)); return f"\x00{len(holds)-1}\x00"
    t = PH.sub(stash, t)
    if LITERAL_RE:
        t = LITERAL_RE.sub(stash, t)
    t = PHRASE_RE.sub(lambda m: PHRASE_MAP[m.group(1)], t)   # multi-word names first
    def rn(m):
        return REG[m.group(1)]      # drop the English possessive 's (Hebrew uses של)
    t = NAME_RE.sub(rn, t)
    if MAQAF_FIX:
        t = MAQAF_FIX.sub(r'\1', t)  # ו-מיילס -> ומיילס  (only before an inserted Hebrew name)
    # drop the English-title period after an inserted Hebrew title (Dr. Connors -> ד"ר קונורס)
    # (?<![א-ת]) is REQUIRED: without a word-start anchor this also matches "מר" inside an
    # ORDINARY word ending in those two letters right before a sentence period (e.g. "אומר."
    # = או + מר + '.'  -> silently ate the full-stop). Found live 2026-08-15 re-scanning
    # post-New-Era-2-review: it fired on unrelated entries with no name substitution at all.
    # The lookahead ALSO must be scoped to an actual inserted NAME (not "\s|$|[א-ת]", which
    # matched "גברת. תודה" -- "Ma'am. Thanks" as two separate sentences, not a title+name --
    # and silently ate that period too). Only fire when this title is immediately followed
    # by one of the canonical Hebrew names we just substituted in.
    if TITLE_RE:
        t = TITLE_RE.sub(r'\1', t)
    t = re.sub(r'\x00(\d+)\x00', lambda m: holds[int(m.group(1))], t)
    return t

def apply_value(v):
    if not isinstance(v, str):
        return v
    parts = TS.split(v)
    tags = TS.findall(v)
    out = []
    for i, seg in enumerate(parts):
        out.append(repl_text(seg))
        if i < len(tags):
            out.append(tags[i])
    return "".join(out)

# KEY_SKIP_PREFIX: real-world song titles ("<Title> של <Artist>" music-license credits) --
# never run character-name substitution on these, a title word can collide with an unrelated
# character's registry entry (New Slang -> "ניו Slang", Donna Lee -> "Donna לי").
KEY_SKIP_PREFIX = ("CCAP_MUS_LIC_",)

total_changed = 0
for fn in ["subtitles_he.json", "dialogue_he.json"]:
    path = os.path.join(HERE, fn)
    d = json.load(open(path, encoding="utf-8"))
    changed = 0; samples = []
    nd = {}
    for k, v in d.items():
        if k.startswith(KEY_SKIP_PREFIX):
            nd[k] = v
            continue
        nv = apply_value(v)
        if nv != v:
            changed += 1
            if len(samples) < 5:
                samples.append((k, v[:80], nv[:90]))
        nd[k] = nv
    print(f"== {fn}: {changed} entries changed")
    for k, o, n in samples:
        print(f"   {k}\n     OLD {o}\n     NEW {n}")
    total_changed += changed
    if not DRY and changed:
        shutil.copyfile(path, path + f".bak_names2.{RUN_TS}")
        tmp = path + ".tmp"
        json.dump(nd, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        os.replace(tmp, path)
        print(f"   WRITTEN (backup {fn}.bak_names2.{RUN_TS})")
print(f"\n{'DRY-RUN' if DRY else 'DONE'} — {total_changed} entries changed")
