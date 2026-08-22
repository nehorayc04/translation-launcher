# -*- coding: utf-8 -*-
"""SKYRIM ADAPTER for the universal multi-language review/translate engine (New-Era 2).

PREP ONLY — this builds the fleet-ready corpus files; it does NOT dispatch any translation.
No fleet/stream is started here. Per games/skyrim/*.md: Phase 1 (mount/bidi/font/layout) is
DONE and deployed in-game; the launcher (a separate resource surface, RT_STRING/RT_BITMAP) is
ALREADY 100% translated and is excluded from this corpus. This adapter covers the remaining
~78,042-line game corpus (.STRINGS/.DLSTRINGS/.ILSTRINGS) + the 649-entry UI table
(interface/translate_english.txt) -- both still 0% Hebrew, so every row here is TRANSLATE mode.

Thin, like the CP2077 reference (games/cyberpunk2077/fleet/build_multilang.py): it only builds
Skyrim's NORMALIZED panel + spine, then hands them to universal/multilang_review.py, which does
ALL the game-agnostic work (corpus + linguistic tags + engine tags). Read-only vs every game file.

ONE STRING PER (id, language) -- unlike CP2077's femaleVariant/maleVariant pairs, a Bethesda
string table has no gendered-variant split baked into the format (gendered dialogue branches via
entirely separate FormIDs/string-IDs at the quest-graph level, not a fv/mv pair under one id).
So panel[id][lang] = [text, text] (both slots identical) is the HONEST representation: the
engine's automatic fv!=mv gender-partition will never fire for Skyrim, same as it never fires for
any single-string game (RDR2 / Hogwarts / Plague Tale). What the panel DOES give the fleet is the
FULL reference text in every shipped language to read directly -- which is the primary New-Era
mechanism. On top of that this adapter attaches a deterministic `gender_hint` per row from the
Russian reference via universal/gender_oracle.py (ru_addressee/ru_speaker, past-tense morphology),
the same mechanism already used by build_ct_strings.py for the /translate pool's `context` field.

Run:  python build_multilang.py
"""
import sys, os, json

HERE = os.path.dirname(os.path.abspath(__file__))
GAME_ROOT = os.path.dirname(HERE)                          # games/skyrim
REPO_ROOT = os.path.dirname(os.path.dirname(GAME_ROOT))    # repo root
sys.path.insert(0, os.path.join(REPO_ROOT, "universal"))
import multilang_review as mlr                              # noqa: E402

try:
    from gender_oracle import ru_addressee, ru_speaker
except Exception:                                            # noqa: BLE001
    ru_addressee = ru_speaker = lambda _s: None              # noqa: E731

E = os.path.join(GAME_ROOT, "extract")
OUT = os.path.join(HERE, "review_corpus")

# Bethesda language-folder name -> canonical multilang_review code
LANG_MAP = {"english": "en", "french": "fr", "german": "de", "italian": "it",
            "spanish": "es", "polish": "pl", "russian": "ru", "japanese": "ja"}

SKYRIM_LANGS = ["en", "ru", "pl", "es", "fr", "it", "de", "ja"]
SKYRIM_CFG = mlr.Cfg(
    langs=SKYRIM_LANGS,
    # every one of these is a candidate gender signal IF Skyrim ever had fv/mv pairs (it doesn't) --
    # kept so the engine's linguistic tags (formality/number) still read them from `refs`.
    gender_langs=("ru", "pl", "es", "fr", "it", "de"),
    addressee_langs=("pl",),      # Polish marks 2nd-person addressee gender (-łaś/-łeś-class agreement)
    speaker_langs=("ru",),        # Russian past tense marks SPEAKER gender (-ла/-л)
)

STRING_KINDS = ("strings", "dlstrings", "ilstrings")


def _load(path):
    p = os.path.join(E, path)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}


def build_panel_strings(kind):
    """pk -> {lang: [text, text]}  from extract/en_all.json + extract/langs/<lang>.json.

    pk = "<plugin>|<sid>" -- MUST carry the plugin prefix: Bethesda string ids are small
    per-plugin sequential integers, so a bare sid collides heavily ACROSS different plugins
    (verified: flattening by bare sid alone silently dropped 48,994 -> 34,855 "strings" rows).
    `section` in the spine is still the bare plugin name, so grouping/context stays clean; the
    final row id (built by the engine as f"{section}:{pk}") reads "<plugin>:<plugin>|<sid>" --
    redundant but harmless and, crucially, collision-free."""
    langs = {}
    for folder, code in LANG_MAP.items():
        d = _load(os.path.join("langs", f"{folder}.json"))
        if d:
            langs[code] = d
    panel = {}           # "<plug>|<sid>" -> {lang: [t, t]}
    for k, en_text in langs.get("en", {}).items():
        plug, sid, kn = k.split("|")
        if kn != kind:
            continue
        panel[f"{plug}|{sid}"] = {"en": [en_text, en_text]}
    for code, d in langs.items():
        if code == "en":
            continue
        for k, text in d.items():
            plug, sid, kn = k.split("|")
            if kn != kind:
                continue
            row = panel.get(f"{plug}|{sid}")
            if row is not None:
                row[code] = [text, text]
    return panel


def build_panel_ui():
    """$key -> {lang: [text, text]}  from extract/ui_langs/<lang>.json (no Japanese UI table).
    UI keys are already globally unique (the full English sentence), no collision risk."""
    row = {}
    for folder, code in LANG_MAP.items():
        d = _load(os.path.join("ui_langs", f"{folder}.json"))
        if not d:
            continue
        for key, text in d.items():
            row.setdefault(key, {})[code] = [text, text]
    return row


def build_spine_strings(panel):
    """pk="<plug>|<sid>" -> (section=<plug>, order, "", "")  -- ALL translate mode."""
    out = {}
    for order, pk in enumerate(sorted(panel, key=lambda k: (k.split("|", 1)[0], k))):
        plug = pk.split("|", 1)[0]
        out[pk] = (plug, order, "", "")
    return out


def build_spine_ui(panel):
    return {k: ("interface", i, "", "") for i, k in enumerate(sorted(panel))}


def attach_gender_hints(path):
    """Post-pass: read the .final.jsonl the engine wrote, attach a deterministic `gender_hint`
    string derived from the Russian reference (the real gender signal for a single-string game --
    the engine's own fv!=mv `gendered` flag never fires here, see module docstring)."""
    if not os.path.exists(path):
        return 0
    rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    n = 0
    for r in rows:
        ru = (r.get("refs", {}).get("ru") or ["", ""])[0]
        if not ru:
            continue
        a, s = ru_addressee(ru), ru_speaker(ru)
        if not (a or s):
            continue
        parts = []
        if a:
            parts.append("נמען=" + {"f": "נקבה", "m": "זכר", "pl": "רבים"}.get(a, a))
        if s:
            parts.append("דובר=" + {"f": "נקבה", "m": "זכר", "pl": "רבים"}.get(s, s))
        r["gender_hint"] = ", ".join(parts)
        n += 1
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return n


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    print("Skyrim multi-language corpus (universal engine) -- PREP ONLY, no fleet dispatched")
    print(f"  langs: {SKYRIM_LANGS}  gender_langs: {SKYRIM_CFG.gender_langs}"
          f"  addressee: {SKYRIM_CFG.addressee_langs}  speaker: {SKYRIM_CFG.speaker_langs}\n")

    for kind in STRING_KINDS:
        panel = build_panel_strings(kind)
        spine = build_spine_strings(panel)
        st = mlr.build(kind, panel, spine, OUT, SKYRIM_CFG)
        print(mlr.report(kind, st))
        n = attach_gender_hints(st["out"])
        print(f"     gender_hint attached (from Russian past-tense/pronoun): {n:,}\n")

    print("  ui: building panel + spine ...")
    ui_panel = build_panel_ui()
    ui_spine = build_spine_ui(ui_panel)
    st = mlr.build("ui", ui_panel, ui_spine, OUT, SKYRIM_CFG)
    print(mlr.report("ui", st))
    n = attach_gender_hints(st["out"])
    print(f"     gender_hint attached (from Russian past-tense/pronoun): {n:,}")


if __name__ == "__main__":
    main()
