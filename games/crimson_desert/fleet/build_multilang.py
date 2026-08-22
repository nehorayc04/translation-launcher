"""Crimson Desert — the THIN דור-3 adapter over the universal engine.

Contract (universal/MULTILANG_REVIEW.md §1/§12): build two NORMALISED structures from the
game's OWN container and hand them to `multilang_review.build`. Everything else — the
deterministic gender partition, the det flags, the linguistic + engine tags — is the shared
engine's job, so this file stays small and CD-specific.

    panel : id -> {lang: [fv, mv]}        every shipped language, canonical codes
    spine : id -> (section, order, fv, mv)   Hebrew; empty  => TRANSLATE mode

Crimson Desert ships **14 languages and NO Hebrew**, so every row is `mode=translate` and the
panel is unusually rich: ru+pl carry speaker AND addressee gender, cs is absent but tr/ko/ja
still disambiguate number, fr/it/es/es-mx/pt carry referent gender and de the register.

🔴 CD has ONE string per (id, language) — there is no femaleVariant/maleVariant pair in the
container — so the pair is always [text, ""] and the engine's automatic gender-split flag can
only fire ACROSS languages (`ar`-style within-language splitting does not exist here). That is
the same shape as Skyrim; it is not a bug and must not be "fixed" by inventing a second form.

Read-only against the game. Run with the repo .venv python (needs lz4 + cryptography).
"""
import os, sys, json

HERE = os.path.dirname(os.path.abspath(__file__))
GAME = os.path.dirname(HERE)                       # games/crimson_desert
REPO = os.path.dirname(os.path.dirname(GAME))      # repo root
sys.path.insert(0, os.path.join(REPO, "universal"))
sys.path.insert(0, os.path.join(GAME, "tools"))

import multilang_review as mlr                     # noqa: E402
import gender_oracle as go                         # noqa: E402
import cd_container as cd                          # noqa: E402

GAME_ROOT = r"C:\Games\Crimson Desert"

# group folder -> (game loc code, CANONICAL code the engine understands).
# Enumerated from the install, not guessed: every group holds exactly one
# gamedata/localizationstring_<code>.paloc.
LANG_GROUPS = [
    ("0020", "eng",    "en"),
    ("0022", "rus",    "ru"),
    ("0029", "pol",    "pl"),
    ("0027", "ger",    "de"),
    ("0026", "fre",    "fr"),
    ("0028", "ita",    "it"),
    ("0024", "spa-es", "es"),
    ("0025", "spa-mx", "es-mx"),
    ("0030", "por-br", "pt"),
    ("0023", "tur",    "tr"),
    ("0019", "kor",    "ko"),
    ("0021", "jpn",    "ja"),
    ("0031", "zho-tw", "zh-tw"),
    ("0032", "zho-cn", "zh-cn"),
]

# 🔑 The SPLIT is the engine's own key convention, not a length heuristic and not the file
# layout (all 187k rows live in ONE paloc per language). A purely-numeric key is an
# item/skill/tooltip/system string; a symbolic key follows questdialog_* / textdialog_* /
# aidialogstringinfogroup_* / <npc>_<zone>_<id> and is DIALOGUE.
DIALOGUE_PREFIXES = ("questdialog", "textdialog", "aidialogstringinfogroup")


def _read_lang(group, code):
    pamt = cd.parse_pamt(os.path.join(GAME_ROOT, group, "0.pamt"))
    want = f"gamedata/localizationstring_{code}.paloc"
    for e in pamt.file_entries:
        if e.path.lower() == want:
            return cd.parse_paloc(cd.read_file(e))
    raise SystemExit(f"{group}: {want} not found")


def _kind_of(key):
    if key.isdigit():
        return "ui"
    k = key.lower()
    if k.startswith(DIALOGUE_PREFIXES):
        return "dialogue"
    return "dialogue" if "_" in k else "ui"


_HE = {"f": "נקבה", "m": "זכר", "pl": "רבים"}


def attach_gender_hints(path):
    """Post-pass: CD stores ONE string per (id, language), so the engine's own `fv != mv`
    gender flag can never fire (it reported `gendered 0` on all 185,370 rows — correct, not a
    bug). The real signal is the Russian past tense / pronoun, which marks speaker AND
    addressee — exactly what English drops. Derive it deterministically from a CLOSED set
    (`universal/gender_oracle.py`) and attach it per row; never guess from an open class.
    [[gender-hint-needs-closed-set]]"""
    if not os.path.exists(path):
        return 0
    rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    n = 0
    for r in rows:
        ru = (r.get("refs", {}).get("ru") or ["", ""])[0]
        if not ru:
            continue
        a, s = go.ru_addressee(ru), go.ru_speaker(ru)
        if not (a or s):
            continue
        parts = []
        if a:
            parts.append("נמען=" + _HE.get(a, a))
        if s:
            parts.append("דובר=" + _HE.get(s, s))
        r["gender_hint"] = ", ".join(parts)
        n += 1
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(tmp, path)
    return n


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    out_dir = os.path.join(HERE, "review_corpus")
    os.makedirs(out_dir, exist_ok=True)

    panel, order_of, en_of = {}, {}, {}
    for group, code, canon in LANG_GROUPS:
        rows = _read_lang(group, code)
        n = 0
        for i, e in enumerate(rows):
            if not e.value:
                continue                       # 2,169 empty slots — nothing to translate/compare
            panel.setdefault(e.key, {})[canon] = [e.value, ""]
            if canon == "en":
                order_of[e.key] = i            # paloc order = the game's own order
                en_of[e.key] = e.value
            n += 1
        print(f"  {canon:6s} {group}  {n:,} non-empty")

    # English is the SOURCE: a row with no English cannot be translated from, and a row that
    # exists only in another language has nothing to key the build back onto.
    ids = [k for k in panel if k in en_of]
    print(f"panel {len(panel):,} ids · with English {len(ids):,}")

    stats = {}
    for kind in ("ui", "dialogue"):
        sel = [k for k in ids if _kind_of(k) == kind]
        sel.sort(key=lambda k: order_of[k])
        sub_panel = {k: panel[k] for k in sel}
        # TRANSLATE mode: no Hebrew ships for this game, so fv=mv="" on every row.
        spine = {k: (kind, i, "", "") for i, k in enumerate(sel)}
        st = mlr.build(kind, sub_panel, spine, out_dir, CFG)
        stats[kind] = st
        print(mlr.report(kind, st))
        n = attach_gender_hints(st["out"])
        print(f"     gender_hint attached (Russian past-tense/pronoun): {n:,}\n")
    return stats


# ru+pl mark speaker AND addressee (past tense / -ł-); cs is not shipped. fr/it/es/es-mx/pt
# mark the referent; de marks register. tr/ko/ja disambiguate number and politeness.
CFG = mlr.Cfg(
    langs=[c for _, _, c in LANG_GROUPS],
    gender_langs=("ru", "pl", "fr", "it", "es", "es-mx", "pt", "de"),
    addressee_langs=("ru", "pl", "de", "es", "fr"),
    speaker_langs=("ru", "pl"),
)

if __name__ == "__main__":
    main()
