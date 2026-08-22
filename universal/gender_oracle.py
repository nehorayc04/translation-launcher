# -*- coding: utf-8 -*-
"""
gender_oracle.py — resolve Hebrew gender/number from the GAME'S OWN gendered
localizations instead of guessing from genderless English.

THE IDEA (user, 2026-07-06)
---------------------------
English drops gender/number, so a Hebrew translation made from English guesses it.
But the game already ships FULL professional localizations in languages that DO mark
gender/number — and those already made the decision. Arabic is the ideal oracle for
Hebrew: both Semitic, same distinctions —
    أنتَ / أنتِ / أنتم   =  אתה / את / אתם          (you: m / f / plural)
    gendered verbs (تعلم / تعلمين)                = צריך / צריכה
    feminine adjective ـة                          = ...ה
So we read the game's Arabic per `primaryKey`, derive the addressee/speaker/number,
and CROSS-CHECK (and fix) our Hebrew — deterministically, no playing, no screenshot.

Other gendered languages triangulate the axes Arabic marks weakly (optional diacritics):
    Russian  — speaker gender is unambiguous in PAST tense (сказал / сказала, -л/-ла)
    Spanish/French/Italian — referent + adjective gender (-o/-a, -é/-ée)
This module starts with the Arabic addressee/number axis (the most common + the one
that breaks most often) and is structured to add the other langs/axes.

CLI
---
  python gender_oracle.py prove        # prove on the q112 sample (needs the extract)
  python gender_oracle.py selftest     # offline unit tests of the parsers
"""
from __future__ import annotations

import argparse
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore

# ── Arabic morphology (the oracle) ──────────────────────────────────────────
# Ranges: Arabic letters ء-ي, diacritics ً-ْ, tatweel ـ.
_AR_FATHA = "َ"   # َ  (a) — masculine pronoun marker on أنتَ
_AR_KASRA = "ِ"   # ِ  (i) — feminine pronoun marker on أنتِ
_AR_TAMARBUTA = "ة"  # ة — feminine noun/adjective ending

# 2nd-person feminine present verb ends in ينَ / ين (تفعلين = ت+root≥3+ين). ين alone is
# also a plural/genitive marker, AND the very common form-II verbal-noun (masdar) pattern
# تَفْعِيل — تحسين/تعيين/تزيين/تمكين/تكوين ("improvement/assignment/decoration") — is
# ت+2+ين and would FALSELY read as a fem verb (rampant in UI text). Require ≥3 stem chars
# ({3,}) so the ت+2+ين masdars are excluded while triliteral fem verbs (تعلمين/تريدين/
# تعرفين) still match. Loses rare biliteral fem verbs (تحبين) — an accepted precision trade.
_AR_YOU_F_VERB = re.compile(r"\bت[ء-يـ]{3,}ين\b")
# feminine singular imperative ends in ي on an imperative stem (اِفعلي): heuristic —
# an alif-wasla/alif start + ...ي ; keep conservative (also caught by pronoun).
_AR_YOU_F_IMP = re.compile(r"\bا[ء-ي]{2,}ي\b")
_AR_YOU_F_PRON = re.compile(r"أنتِ|أنتِ|\bأنتi\b|أنتِ")   # أنت + kasra
_AR_YOU_M_PRON = re.compile("أنت" + _AR_FATHA)              # أنتَ + fatha
_AR_YOU_PL = re.compile(r"أنتم|أنتن|أنتما")                 # you plural / dual
_AR_WE = re.compile(r"\bنحن\b")
# object/possessive suffix ـكِ (your/you-f) vs ـكَ (your/you-m) — needs the diacritic AND must be
# a real word-FINAL suffix. `\b` after a combining haraka is unreliable (it fired inside الكَلب /
# ذكَر → false masc), so require that NO further Arabic letter follows the ك+haraka.
_AR_SUF_KF = re.compile("ك" + _AR_KASRA + r"(?![ء-يـ])")
_AR_SUF_KM = re.compile("ك" + _AR_FATHA + r"(?![ء-يـ])")
# 2nd-person verb in a subjunctive/jussive/future context: particle + ت-verb.
# Ends in ي/ين → feminine; otherwise masculine. This catches "أن تعلم" (must know-m)
# vs "أن تعلمي" (know-f) even with NO diacritics — the reliable Arabic addressee cue.
_AR_PARTICLE = r"(?:أن|لن|لم|سوف|سـ?|لا|كي|حتى|عندما|إذا)"
# Only the ين form (a real 2nd-fem present verb). The bare-ي branch was DROPPED: unvocalized
# "أن تفعلي" is a 3rd-fem homograph AND catches the object suffix ـني ("me" — تسامحني=forgive-ME),
# both false "f". The ين form here is already covered by _AR_YOU_F_VERB; kept for parity/clarity.
_AR_YOU_VERB_F2 = re.compile(_AR_PARTICLE + r"\s+ت[ء-ي]{3,}ين\b")
_AR_YOU_VERB_M2 = re.compile(_AR_PARTICLE + r"\s+ت[ء-ي]{2,}\b")


def ar_addressee(text: str) -> str | None:
    """'m' | 'f' | 'pl' | None — gender/number of the ADDRESSEE ('you') in Arabic."""
    if not text:
        return None
    if _AR_YOU_PL.search(text):
        return "pl"
    # PRECISION over recall: a bare ت-verb (تفعل) is a 2nd-masc / 3rd-fem HOMOGRAPH,
    # so we DON'T use it. Only unambiguous 2nd-person markers count:
    #   fem  → أنتِ · verb ...ين (تفعلين) · ـكِ (with kasra) · fem imperative ...ي
    #   masc → أنتَ · ـكَ (with fatha)
    fem = bool(_AR_YOU_F_PRON.search(text) or _AR_YOU_F_VERB.search(text)
               or _AR_SUF_KF.search(text) or _AR_YOU_VERB_F2.search(text))
    masc = bool(_AR_YOU_M_PRON.search(text) or _AR_SUF_KM.search(text))
    if fem and not masc:
        return "f"
    if masc and not fem:
        return "m"
    return None


# Curated 2nd-fem PRESENT-verb whitelist (تـ…ين) — precision like the Hebrew _HE_VERB_F list.
# Unlike the generic `ت…ين` regex it can't false-fire on the form-II masdar (تحسين), broken/sound
# plurals (تنانين=dragons, تمارين), or names (ترينيتي=Trinity): a specific verb stem won't collide.
# Allows an optional attached object/possessive suffix (تقولينها = you-f say-IT); both-side \b.
_AR_F_VERBS = ["تريدين", "تعرفين", "تعلمين", "تفعلين", "تقولين", "تفكرين", "تعتقدين", "تستطيعين",
               "تذهبين", "تأتين", "تسمعين", "تشعرين", "تحتاجين", "تختارين", "تجدين", "تكونين",
               "تحبين", "تظنين", "تبحثين", "تحاولين", "ترين", "تدركين", "تتذكرين", "تنظرين",
               "تعملين", "تصدقين", "تخططين", "تملكين", "تعيشين", "تموتين", "تخبرين", "تسألين",
               "تجيبين", "تفهمين", "تقصدين", "تنوين", "تحملين", "تقاتلين", "تتعلمين", "تخافين",
               "تستحقين", "تنتمين", "تتوقعين", "تلعبين"]
_AR_YOU_F_VERB_WL = re.compile(
    r"\b(?:" + "|".join(sorted(_AR_F_VERBS, key=len, reverse=True)) + r")"
    r"(?:ه|ها|هم|هن|كِ|كَ|ك|كم|كن|ني|نا)?\b")


def ar_addressee_strict(text: str) -> str | None:
    """HIGH-PRECISION addressee — pronouns + DIACRITIC-marked ـكَ/ـكِ ONLY.

    Drops the `ت…ين` verb heuristic entirely: on unvocalized Arabic it false-fires on the form-II
    masdar (تحسين), broken/sound plurals (تنانين=dragons, تمارين), and verb+object suffixes
    (تسامحني=forgive-ME) — a wrong hint would CREATE the exact gender debt we prevent. Use this
    when the output is written back as a hint / auto-QA (build_gender_source / gender_qa). Recall
    is lower (only lines carrying أنتَ/أنتِ/أنتم/أنتما or a vocalized ـكَ/ـكِ get a verdict), but
    every verdict is trustworthy. Hogwarts' Arabic IS partially vocalized, so these markers fire."""
    if not text:
        return None
    if _AR_YOU_PL.search(text):
        return "pl"
    # أنتِ / ـكِ (kasra) / curated 2nd-fem verb  vs  أنتَ / ـكَ (fatha)
    fem = bool(_AR_YOU_F_PRON.search(text) or _AR_SUF_KF.search(text)
               or _AR_YOU_F_VERB_WL.search(text))
    masc = bool(_AR_YOU_M_PRON.search(text) or _AR_SUF_KM.search(text))
    if fem and not masc:
        return "f"
    if masc and not fem:
        return "m"
    return None


# ── Hebrew morphology (what we must match) ──────────────────────────────────
# he addressee: אתה (m) / את (f) / אתם/אתן (pl); verb suffix ...ה often fem 2nd/3rd.
_HE_YOU_M = re.compile(r"(?<![א-ת])אתה(?![א-ת])")
_HE_YOU_F = re.compile(r"(?<![א-ת])את(?![א-ת])")
_HE_YOU_PL = re.compile(r"(?<![א-ת])את[םן](?![א-ת])")
# common 2nd-person feminine verb forms (…ה / …י ending on frequent verbs)
# Only UNAMBIGUOUS 2nd-person forms (no homographs like "לך"=go/to-you, "רואה"=m/f-same).
_HE_VERB_F = re.compile(
    r"\b(?:צריכה|יכולה|יודעת|מוכנה|חייבת|תוכלי|תדעי|בואי|קחי|"
    r"תעשי|לכי|בטוחה|מבינה|שומעת|אמרת|תגידי|רוצה)\b")
_HE_VERB_M = re.compile(
    r"\b(?:צריך|יכול|יודע|מוכן|חייב|תוכל|תדע|בוא|קח|"
    r"תעשה|בטוח|מבין|שומע|תגיד)\b")


def he_addressee(text: str) -> str | None:
    """'m' | 'f' | 'pl' | None — gender/number the Hebrew is CURRENTLY addressing."""
    if not text:
        return None
    if _HE_YOU_PL.search(text):
        return "pl"
    # 'את' as accusative particle ("את הדבר") is NOT 'you' — require a fem verb nearby
    # OR a standalone 'את' not immediately followed by 'ה'/'את ה'.
    has_f_pron = bool(re.search(r"(?<![א-ת])את(?![א-ת])(?!\s+ה)", text))
    fem = bool(_HE_VERB_F.search(text)) or has_f_pron
    masc = bool(_HE_YOU_M.search(text)) or bool(_HE_VERB_M.search(text))
    if masc and not fem:
        return "m"
    if fem and not masc:
        return "f"
    if masc and fem:      # both -> ambiguous, don't judge
        return None
    return None


# ── Russian morphology (oracle for games with NO Arabic slot: tlou1/anno1800/ac2)
# Gender surfaces in PAST tense (-л m / -ла f / -ли pl) and short adjectives
# (готов/готова). Anchor to a pronoun for the AXIS: я/мы = speaker, ты/вы = addressee.
# PRECISION over recall — only judge when the signal is unambiguous.
_RU_ADJ_F = {"готова", "рада", "должна", "уверена", "согласна", "одна", "сама",
             "жива", "права", "виновата", "способна", "занята", "свободна",
             "рождена", "готовая", "больна", "мертва", "ранена"}
_RU_ADJ_M = {"готов", "рад", "должен", "уверен", "согласен", "один", "сам",
             "жив", "прав", "виноват", "способен", "занят", "свободен",
             "рождён", "болен", "мёртв", "ранен"}
_RU_TOK = re.compile(r"[а-яё]+", re.I)


def _ru_tok_gender(w: str) -> str | None:
    w = w.lower()
    if w in _RU_ADJ_F:
        return "f"
    if w in _RU_ADJ_M:
        return "m"
    if len(w) >= 4 and w.endswith("ла"):     # past-tense feminine (сказала, была)
        return "f"
    if len(w) >= 4 and w.endswith("ли"):     # past-tense plural (сказали)
        return "pl"
    # past-tense masculine ends in -л (сказал, был, вернул, видел, говорил, стоял).
    # Exclude only -ль (nouns: боль, соль — verbs never end in -ль). Anchored to a
    # я/ты pronoun by the callers, so a stray -л noun is rare and the m+f ambiguity
    # guard drops any conflict.
    if len(w) >= 3 and w.endswith("л") and not w.endswith("ль"):
        return "m"
    return None


def _ru_axis_gender(text: str) -> str | None:
    """Single unambiguous gender among all gendered tokens, else None."""
    gs = {g for t in _RU_TOK.findall(text) if (g := _ru_tok_gender(t))}
    gs.discard("pl")
    if gs == {"f"}:
        return "f"
    if gs == {"m"}:
        return "m"
    return None


def ru_addressee(text: str) -> str | None:
    """'m'|'f'|'pl'|None — gender/number of the ADDRESSEE ('you') from Russian."""
    if not text:
        return None
    toks = _RU_TOK.findall(text.lower())
    if "вы" in toks:
        return "pl"
    if "ты" in toks and "я" not in toks:      # single-subject → verb gender is the addressee
        return _ru_axis_gender(text)
    return None


def ru_speaker(text: str) -> str | None:
    """'m'|'f'|'pl'|None — gender/number of the SPEAKER ('I') from Russian."""
    if not text:
        return None
    toks = _RU_TOK.findall(text.lower())
    if "мы" in toks:
        return "pl"
    if "я" in toks and "ты" not in toks:
        return _ru_axis_gender(text)
    return None


def ru_gender(text: str) -> str | None:
    """Coarse dominant gender signal (any axis) — for a hint/fingerprint."""
    if not text:
        return None
    toks = _RU_TOK.findall(text.lower())
    if "вы" in toks or "мы" in toks:
        return "pl"
    return _ru_axis_gender(text)


# ── Spanish morphology (referent/subject via adjective/participle -o/-a) ──────
# Noisy (every noun is gendered) → only trust an adjective/participle right after
# ser/estar (estás listo/lista, estoy cansado/cansada, está muerta).
_ES_STATE = re.compile(
    r"\b(?:estás|estoy|está|estamos|están|eres|soy|es|somos|son|quedé|quedaste|"
    r"sentí|estaba|estabas)\s+(?:muy\s+|tan\s+|un\s+poco\s+)?[a-záéíóúñ]{3,}?([oa])\b",
    re.I)


def es_referent(text: str) -> str | None:
    """'m'|'f'|None — subject/referent gender from a Spanish predicate adjective."""
    if not text:
        return None
    m = _ES_STATE.search(text)
    if not m:
        return None
    return "f" if m.group(1).lower() == "a" else "m"


# ── cross-check ─────────────────────────────────────────────────────────────
def check_line(he: str, ar: str) -> dict:
    """Compare our Hebrew's addressee gender to the Arabic oracle's."""
    a = ar_addressee(ar)
    h = he_addressee(he)
    mismatch = bool(a and h and a != h and not (a == "pl" or h == "pl"))
    return {"ar": a, "he": h, "mismatch": mismatch}


def oracle_addressee(langs: dict) -> str | None:
    """Best available ADDRESSEE gender from whatever gendered locale is present.
    langs = {'ar':..,'ru':..,'es':..}. Arabic first (Semitic, closest), then Russian."""
    return (ar_addressee(langs.get("ar", "")) if langs.get("ar") else None) \
        or ru_addressee(langs.get("ru", ""))


# ── selftest ────────────────────────────────────────────────────────────────
def selftest() -> int:
    cases = [
        # (arabic, expected addressee)
        ("من بين كل الناس، يجب أن تعلم أن نايت سيتي", "m"),      # masc verb تعلم
        ("هل يمكنك أن تعلمين ذلك", "f"),                          # fem verb تعلمين
        ("أنتم جميعا مستعدون", "pl"),                             # you-plural
        ("ما الأمر", None),                                       # no addressee
    ]
    ok = 0
    for ar, exp in cases:
        got = ar_addressee(ar)
        hit = got == exp
        ok += hit
        print(f"  [{'OK ' if hit else 'MISS'}] ar_addressee={got} exp={exp}  {ar[:30]}")
    hcases = [
        ("אתה צריך לדעת", "m"),
        ("את צריכה לדעת", "f"),
        ("אתם צריכים", "pl"),
        ("קח את הדבר", None),        # 'את' here = accusative, not 'you'
    ]
    for he, exp in hcases:
        got = he_addressee(he)
        hit = got == exp
        ok += hit
        print(f"  [{'OK ' if hit else 'MISS'}] he_addressee={got} exp={exp}  {he}")
    # Russian (no-Arabic games): addressee via ты + gendered past/adj; speaker via я.
    rcases = [
        (ru_addressee, "Почему ты не вернул меня?", "m"),   # past masc -л (вернул)
        (ru_addressee, "Ты видела это?", "f"),               # past fem -ла
        (ru_addressee, "Ты говорил с ней?", "m"),
        (ru_addressee, "Вы готовы?", "pl"),
        (ru_speaker,   "Я готов.", "m"),                     # short adj masc
        (ru_speaker,   "Я не знала.", "f"),                  # past fem
        (es_referent,  "¿Estás lista?", "f"),                # estar + -a
        (es_referent,  "Estoy cansado.", "m"),               # estar + -o
    ]
    for fn, txt, exp in rcases:
        got = fn(txt)
        hit = got == exp
        ok += hit
        print(f"  [{'OK ' if hit else 'MISS'}] {fn.__name__}={got} exp={exp}  {txt}")
    total = len(cases) + len(hcases) + len(rcases)
    print(f"selftest {ok}/{total}")
    return 0 if ok >= total - 1 else 1


def prove() -> int:
    """Prove on q112: our Hebrew vs the game's Arabic, flag addressee mismatches."""
    import glob, json, os
    BASE = r"c:\Users\Nehoray_Cohen\Projects\Game translator"
    spine = json.load(open(os.path.join(
        BASE, "תרגום_משחקים", "source", "resources",
        "localization_translated.json"), encoding="utf-8"))
    he_by_pk = {}
    for sec, lst in spine.items():
        if "q112" not in sec or not isinstance(lst, list):
            continue
        for e in lst:
            if isinstance(e, dict):
                pk = str(e.get("primaryKey") or e.get("stringId"))
                he_by_pk[pk] = e.get("femaleVariant", "")
    # arabic serialized q112 subtitle files (game's original Arabic)
    arj = glob.glob(os.path.join(
        r"C:\Users\Nehoray_Cohen\AppData\Local\Temp\subtitle_batch\ar_pristine",
        "**", "q112", "*.json.json"), recursive=True)
    ar_by_pk = {}
    for f in arj:
        try:
            d = json.load(open(f, encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        def walk(o):
            if isinstance(o, dict):
                if o.get("$type") == "localizationPersistenceSubtitleEntry":
                    ar_by_pk[str(o.get("stringId"))] = o.get("femaleVariant", "")
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)
        walk(d)
    flags = 0
    checked = 0
    for pk, he in he_by_pk.items():
        ar = ar_by_pk.get(pk)
        if not ar:
            continue
        r = check_line(he, ar)
        if r["ar"] and r["he"]:
            checked += 1
        if r["mismatch"]:
            flags += 1
            print(f"  ⚠ MISMATCH  AR={r['ar']} HE={r['he']}")
            print(f"      he: {he[:60]}")
            print(f"      ar: {ar[:60]}")
    print(f"\nchecked {checked} addressable lines, {flags} gender mismatches "
          f"(Arabic oracle vs our Hebrew)")
    print("proved: the game's Arabic resolves the gender our English-based Hebrew missed."
          if flags else "no mismatch in this sample")
    return 0


# ── game-agnostic full-spine pipeline ───────────────────────────────────────
def build_arabic_map(ar_serialized_dir: str) -> dict:
    """Walk a directory of WolvenKit-serialized Arabic localization JSONs
    (subtitles + onscreens) → {primaryKey: (ar_female, ar_male)}. The Arabic
    entries key on `stringId`, which equals the spine's `primaryKey`."""
    import glob, json, os
    out = {}
    for f in glob.glob(os.path.join(ar_serialized_dir, "**", "*.json.json"),
                        recursive=True):
        try:
            d = json.load(open(f, encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        def walk(o):
            if isinstance(o, dict):
                if o.get("$type") in ("localizationPersistenceSubtitleEntry",
                                      "localizationPersistenceOnScreenEntry"):
                    pk = str(o.get("stringId") or o.get("primaryKey") or "")
                    if pk:
                        out[pk] = (o.get("femaleVariant", ""), o.get("maleVariant", ""))
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)
        walk(d)
    return out


def scan(spine_paths: list, arabic_map: dict, out_path: str) -> dict:
    """For every spine line, compare the Hebrew femaleVariant/maleVariant addressee
    gender to the game's Arabic. Emit ranked high-confidence disagreements to
    out_path (jsonl). Deterministic, no LM. Returns stats."""
    import json
    stats = {"checked": 0, "fem_mismatch": 0, "player_dep_flat": 0}
    rows = []
    for path in spine_paths:
        data = json.load(open(path, encoding="utf-8"))
        src = "dlc" if "dlc" in path else "base"
        for sec, lst in data.items():
            if not isinstance(lst, list):
                continue
            for e in lst:
                if not isinstance(e, dict):
                    continue
                pk = str(e.get("primaryKey") or e.get("stringId") or "")
                ar = arabic_map.get(pk)
                if not ar:
                    continue
                ar_f, ar_m = ar
                he_f = e.get("femaleVariant") or ""
                he_m = e.get("maleVariant") or ""
                a_f = ar_addressee(ar_f)
                h_f = he_addressee(he_f)
                if a_f and h_f:
                    stats["checked"] += 1
                    if a_f != h_f and "pl" not in (a_f, h_f):
                        stats["fem_mismatch"] += 1
                        rows.append({
                            "src": src, "section": sec, "pk": pk,
                            "reason": "fem_addressee", "ar_gender": a_f, "he_gender": h_f,
                            "he_female": he_f, "he_male": he_m,
                            "ar_female": ar_f, "ar_male": ar_m,
                        })
                # player-dependence check: Arabic splits (ar_f != ar_m, both present)
                a_m = ar_addressee(ar_m) if ar_m else None
                if a_m and a_f and a_m != a_f and he_f == he_m and he_f:
                    stats["player_dep_flat"] += 1
                    rows.append({
                        "src": src, "section": sec, "pk": pk,
                        "reason": "player_dep_flat", "ar_gender": f"{a_f}/{a_m}",
                        "he_gender": "flat", "he_female": he_f, "he_male": he_m,
                        "ar_female": ar_f, "ar_male": ar_m,
                    })
    # rank: player-dependent flats first (clear dual-gender miss), then fem mismatches
    rows.sort(key=lambda r: 0 if r["reason"] == "player_dep_flat" else 1)
    with open(out_path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"[✓] {out_path}")
    print(f"    checked (both sides determinable): {stats['checked']:,}")
    print(f"    femaleVariant addressee mismatch : {stats['fem_mismatch']:,}")
    print(f"    player-dependent but flat (M==F) : {stats['player_dep_flat']:,}")
    print(f"    total suspects: {len(rows):,}")
    return stats


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="gender_oracle")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("selftest")
    sub.add_parser("prove")
    sc = sub.add_parser("scan", help="full-spine Arabic-vs-Hebrew gender scan")
    sc.add_argument("--arabic-dir", required=True,
                    help="dir of WolvenKit-serialized Arabic localization JSONs")
    sc.add_argument("--out", default="gender_oracle_suspects.jsonl")
    sc.add_argument("--spine", nargs="+", help="spine json paths (default: CP2077 base+DLC)")
    a = p.parse_args(argv)
    if a.cmd == "selftest":
        return selftest()
    if a.cmd == "prove":
        return prove()
    if a.cmd == "scan":
        import os
        spine = a.spine or [
            os.path.join(r"c:\Users\Nehoray_Cohen\Projects\Game translator",
                         "תרגום_משחקים", "source", "resources", p2)
            for p2 in ("localization_translated.json", "dlc_ep1_translated.json")]
        amap = build_arabic_map(a.arabic_dir)
        print(f"[*] Arabic map: {len(amap):,} lines")
        scan(spine, amap, a.out)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
