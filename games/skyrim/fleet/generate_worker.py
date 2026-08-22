import os

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "../../corsair_cove/fleet/cc_nim.py"), "r", encoding="utf-8") as f:
    code = f.read()

# Replace game-specific prompt
old_prompt = """S1 = ("You are a senior Hebrew localizer for Corsair Cove — a Caribbean pirate haven in the age "
      "of sail: ships and crews, forts and harbours, plunder, smuggling, trade and the colonial "
      "navies hunting you. The cast is fixed: Rambullion, Teach, Kanja, Honorata, Jonah, Chen, "
      "Scarlet, Enrique, Amara, Akua, Audenzia, Admiral Machado. Write natural, fluent, MODERN "
      "Hebrew with a seafaring flavour — captain, crew, deck, broadside, plunder, harbour — but "
      "never archaic or biblical-sounding Hebrew. Keep each speaker's voice; crude language "
      "stays crude. UI labels stay terse and functional, like real game menus. "
      "Each input line gives 'en' = the English MEANING to translate, plus the SAME line as the "
      "game's own professional translators shipped it: 'ru' 'pl' 'de' 'fr' 'es' 'it'. Translate "
      "the MEANING from 'en'. Use the other languages ONLY as the grammar oracle, because "
      "English hides what Hebrew must state: ru and pl mark the SPEAKER's and the ADDRESSEE's "
      "gender and NUMBER (a plural imperative there means address a GROUP — אתם and plural "
      "verbs), fr/es/it mark the referent's gender, de shows the register. Follow them: a woman "
      "gets את and feminine verbs, a man אתה, a group אתם. Do NOT translate from those "
      "languages and NEVER copy a foreign word — Cyrillic or Greek letters in your output are "
      "always a bug. "
      "'ctx' is the developers' own note about what the string IS, and 'sp'/'ad' are who says it "
      "to whom — use them to pick the right register and the right gender. "
      "ADDRESS THE PLAYER IN MASCULINE SINGULAR, consistently. The game's own translators "
      "settled this: German uses du / deine and Polish uses the singular imperative "
      "(Ukoncz, Wznies, Zatrudnij). So an objective or a menu instruction is "
      "גייס / בנה / השלם / קנה / שלך — never the plural גייסו / בנו / השלימו, and never a "
      "plural verb with a singular possessive in the same line. Only address a GROUP with "
      "אתם when the line really is spoken to several people (ru/pl will show a plural there). "
      "Never put a hyphen between a Hebrew prefix and a Hebrew word: write בשבעת הימים, not "
      "ב-שבעת הימים. A hyphen after a prefix is only for Latin or digits (ל-NPC, ב-2024). "
      "Keep every token VERBATIM from the English, same count and same position: the {VAR} "
      "placeholders and the <tag> markup (<hl> <b> </> <img .../>). Keep the SAME number of line "
      "breaks and never merge text across one. "
      "Use the plain hyphen '-'. Never use a long dash. No niqqud. "
      "Proper names use their accepted Hebrew form; brand/code tokens stay Latin. "
      "If a line is an ALL-CAPS code, a file path or unreadable gibberish, return it UNCHANGED. "
      "SPECIAL SYNTAX: a token followed by |plural(one=X, other=Y) is an ENGINE FORMATTING RULE, not prose -- it picks X when the number is 1, Y otherwise. Translate X and Y, but NEVER leave one side empty (Hebrew almost never needs a different word for the two cases here -- if so, put the SAME Hebrew word/phrase on both sides rather than leaving one blank), and keep EACH plural(...) clause in its OWN role: if the English has TWO separate plural(...) clauses (e.g. one for a verb like is/are, one for a noun like pirate/pirates), your Hebrew must have the SAME two clauses in the SAME order, each translating only its own English clause -- never swap content between them. "
      "Output JSON {id: hebrew} only, with exactly the same ids as the input.")"""

new_prompt = """S1 = ("You are a senior Hebrew localizer for The Elder Scrolls V: Skyrim Anniversary Edition. "
      "A high-fantasy Nordic world: dragons, Jarls, hold guards, magic, Daedric princes, "
      "the civil war between the Imperials and Stormcloaks, the Dragonborn (Dovahkiin). "
      "Write natural, fluent, MODERN Hebrew with a high-fantasy flavour — slightly archaic "
      "and respectful for nobles (Jarls), rough for bandits, but never biblical-sounding Hebrew. "
      "Each input line gives 'en' = the English MEANING to translate, plus the SAME line as the "
      "game's own professional translators shipped it: 'ru' 'pl' 'de' 'fr' 'es' 'it'. Translate "
      "the MEANING from 'en'. Use the other languages ONLY as the grammar oracle, because "
      "English hides what Hebrew must state: ru and pl mark the SPEAKER's and the ADDRESSEE's "
      "gender and NUMBER (a plural imperative there means address a GROUP — אתם and plural "
      "verbs), fr/es/it mark the referent's gender, de shows the register. Follow them: a woman "
      "gets את and feminine verbs, a man אתה, a group אתם. Do NOT translate from those "
      "languages and NEVER copy a foreign word — Cyrillic or Greek letters in your output are "
      "always a bug. "
      "'gender_hint' may be provided from the Russian morphology; use it to pick the right gender. "
      "ADDRESS THE PLAYER IN MASCULINE SINGULAR (אתה), consistently. "
      "Never put a hyphen between a Hebrew prefix and a Hebrew word: write בשבעת הימים, not "
      "ב-שבעת הימים. A hyphen after a prefix is only for Latin or digits (ל-NPC, ב-2024). "
      "Keep every token VERBATIM from the English, same count and same position: {VAR} "
      "placeholders and <tag> markup. Keep the SAME number of line breaks. "
      "Use the plain hyphen '-'. Never use a long dash. No niqqud. "
      "Proper names use their accepted Hebrew form (e.g. וייטראן for Whiterun, אלדוין for Alduin). "
      "Output JSON {id: hebrew} only, with exactly the same ids as the input.")"""

code = code.replace(old_prompt, new_prompt)

# Modify _en to handle Skyrim's corpus structure
old_en = """def _en(v):
    return v.get("en", "") if isinstance(v, dict) else (v or "")"""

new_en = """def _en(v):
    return v.get("en", "") if isinstance(v, dict) else (v or "")"""

code = code.replace(old_en, new_en)

# Fix gender conflict checks (Skyrim doesn't have sp/ad from cc)
old_gc = """def gender_conflict(new, v=None):
    if not v or not isinstance(v, dict): return ""
    ag = v.get("ad")
    if ag == "female":
        if he_addressee(new) == "m": return "ag-female-but-hebrew-m"
    elif ag == "male":
        if he_addressee(new) == "f": return "ag-male-but-hebrew-f"
    elif ag == "plural":
        if he_addressee(new) in ("m", "f"): return f"ag-plural-but-hebrew-{he_addressee(new)}"
    return ""
"""

new_gc = """def gender_conflict(new, v=None):
    return "" # Handled by reviewer later
"""
if "def gender_conflict" in code:
    import re
    code = re.sub(r'def gender_conflict\(.*?(?=def |# ── )', new_gc, code, flags=re.DOTALL)

# Adjust payload builder
old_payload = """        for k, v in batch:
            en = _en(v)
            if not en.strip(): continue
            ctx = v.get("ctx") or ""
            sp, ad = v.get("sp") or "", v.get("ad") or ""
            line = {"id": k, "en": en}
            if ctx: line["ctx"] = ctx
            if sp: line["sp"] = sp
            if ad: line["ad"] = ad
            for l in PANEL:
                if v.get(l): line[l] = v[l]
            lines.append(line)"""

new_payload = """        for k, v in batch:
            en = _en(v)
            if not en.strip(): continue
            gh = v.get("gender_hint") or ""
            refs = v.get("refs") or {}
            line = {"id": k, "en": en}
            if gh: line["gender_hint"] = gh
            for l in PANEL:
                if refs.get(l): line[l] = refs[l][0]
            lines.append(line)"""

code = code.replace(old_payload, new_payload)

# Name replacements
code = code.replace("Corsair Cove translator worker", "Skyrim translator worker")
code = code.replace("cc_nim.py", "skyrim_nim.py")
code = code.replace("CcMP", "SkyrimMP")

with open(os.path.join(HERE, "skyrim_nim.py"), "w", encoding="utf-8") as f:
    f.write(code)
