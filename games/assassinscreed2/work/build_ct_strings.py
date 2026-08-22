"""Build the AC2 community-translation upload for hebrew-translation-hub.com/translate.

Per the standing rule the pool is CATEGORISED by visibility so contributors are served the
most-seen text first:  ממשק ותפריטים  ->  כתוביות עלילה.

string_key keeps the SAME 'ui:<id>' / 'sub:<id>' prefix the fleet corpus uses, so an approved
line maps straight back onto the right LocalizationPackage at build time.

New-Era bonus: the game ships the same line in up to 9 languages, so we derive the gender /
number the English hides and put it in `context` — the contributor sees the answer instead of
guessing (same idea as the Hogwarts pool).
"""
import sys, os, json, re
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
FLEET = os.path.join(HERE, "..", "fleet")

corpus = json.load(open(os.path.join(FLEET, "corpus_full.json"), encoding="utf-8"))
try:
    heb = json.load(open(os.path.join(FLEET, "hebrew.json"), encoding="utf-8"))
except Exception:
    heb = {}

CAT = {"ui": "ממשק ותפריטים", "sub": "כתוביות עלילה"}

# ---- gender / number oracle -------------------------------------------------------------
# Romance: an -a / -e ending on a past participle or adjective marks a feminine referent;
# Polish past tense -la / -lam / -las is feminine, -l / -lem / -les masculine; plural -li / -ly.
PL_F = re.compile(r'\b\w+ła(?:m|ś)?\b')
PL_M = re.compile(r'\b\w+ł(?:em|eś)?\b')
PL_PL = re.compile(r'\b\w+(?:li|ły)(?:śmy|ście)?\b')
# ⚠️ DELIBERATELY no auto-derived gender guess.
# A Romance article (la/una) marks the NOUN's gender, not the addressee's; and a Polish -ł/-li
# ending hits ordinary nouns too ("Forli" -> 'plural', "dół" -> 'masculine'). Without a lexicon
# those guesses are wrong more often than right, and a wrong hint is worse than none.
# Instead the contributor gets the ACTUAL sentence in the languages that DO mark what Hebrew
# needs - Italian (the game is set in Italy), Polish (speaker/addressee gender) - plus the
# German register, which IS a reliable closed set of pronouns.
FORMAL = re.compile(r'\b(?:Sie|Ihnen|Ihre[nmrs]?)\b')
INFORMAL = re.compile(r'\b(?:du|dich|dir|dein[emrs]?)\b')


def hint(refs):
    de = refs.get("de", "")
    if de and FORMAL.search(de):   return "פנייה רשמית"
    if de and INFORMAL.search(de): return "פנייה ידידותית"
    return ""


rows, order = [], 0
skipped = 0
for key, v in sorted(corpus.items(), key=lambda kv: (0 if kv[0].startswith("ui:") else 1, len(kv[1]["en"]))):
    en = v["en"]
    if not re.search(r"[A-Za-z]{2,}", en):
        skipped += 1; continue
    sec = key.split(":", 1)[0]
    refs = v.get("refs") or {}
    ctx = [CAT[sec]]
    h = hint(refs)
    if h: ctx.append(h)
    # the reference sentences themselves: they SHOW the gender / number / register English hides
    if refs.get("it"): ctx.append("איטלקית: " + refs["it"][:140])   # the game IS set in Italy
    if refs.get("pl"): ctx.append("פולנית: " + refs["pl"][:140])    # marks speaker+addressee gender
    order += 1
    rows.append({
        "string_key": key,
        "source_en": en,
        "current_he": heb.get(key, ""),
        "context": " | ".join(ctx)[:500],
        "section": CAT[sec],
        "order_index": order,
    })

out = os.path.join(HERE, "..", "extract", "ct_strings.json")
os.makedirs(os.path.dirname(out), exist_ok=True)
json.dump(rows, open(out, "w", encoding="utf-8"), ensure_ascii=False)
ui = sum(1 for r in rows if r["section"] == CAT["ui"])
withhe = sum(1 for r in rows if r["current_he"])
withhint = sum(1 for r in rows if "פנייה" in r["context"])
print(f"rows            : {len(rows)}   (skipped {skipped} non-translatable)")
print(f"  ממשק ותפריטים : {ui}")
print(f"  כתוביות עלילה : {len(rows)-ui}")
print(f"already Hebrew  : {withhe}")
print(f"with register hint: {withhint}")
print("->", out)
