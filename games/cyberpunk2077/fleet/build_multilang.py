# -*- coding: utf-8 -*-
"""CP2077 ADAPTER for the universal multi-language review/translate engine.

Thin: it only builds CP2077's NORMALIZED panel + spine from the already-serialized language dirs
and the Hebrew spine, then hands them to universal/multilang_review.py — which does ALL the
game-agnostic work (corpus + linguistic tags + engine tags, review-or-translate per row).

Supersedes the old CP2077-only trio (build_review_corpus.py + tag_corpus.py + tag_engine.py):
same output, but now produced by the shared engine so every game gets it for free.
Read-only vs the spine. Run:  python build_multilang.py
"""
import sys, os, json, collections
from pathlib import Path

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "..", "universal")))
import multilang_review as mlr

RES = os.path.join(HERE, "..", "..", "..", "תרגום_משחקים", "source", "resources")
ON_WORK = Path(r"C:\Users\NEHORA~1\AppData\Local\Temp\cp2077_langpanel")
SUB_WORK = Path(r"C:\Users\NEHORA~1\AppData\Local\Temp\cp2077_subpanel")
OUT = os.path.join(HERE, "review_corpus")

# CP2077 loc-folder names (kept as-is; the engine's register/gender detectors accept these variants).
CP_LANGS = ["en", "ar", "ru", "pl", "cs", "es-es", "es-mx", "fr", "it", "pt", "de",
            "ja", "ko", "zh-cn", "zh-tw", "tr", "th", "hu", "ua"]
CP_CFG = mlr.Cfg(
    langs=CP_LANGS,
    gender_langs=("ar", "ru", "pl", "cs", "es-es", "es-mx", "fr", "it", "pt", "de"),
    addressee_langs=("ar", "pl", "cs"),
    speaker_langs=("ru",),
)


def entries_of(tj):
    try:
        w = json.load(open(tj, encoding="utf-8"))
        return w["Data"]["RootChunk"]["root"]["Data"]["entries"]
    except Exception:
        return []


def build_panel(work, names):
    """pk -> {lang:(fv,mv)} from serialized dirs. names = allowed CR2W basenames (onscreens) or None."""
    panel = {}
    for scope in ("base", "ep1"):
        for lang in CP_LANGS:
            ex = work / scope / lang
            if not ex.exists():
                continue
            files = [p for p in ex.rglob("*.json.json") if names is None or p.name in names]
            for tj in files:
                for e in entries_of(str(tj)):
                    pk = e.get("primaryKey") or e.get("stringId")
                    if pk is None:
                        continue
                    fv = (e.get("femaleVariant") or "").strip()
                    mv = (e.get("maleVariant") or "").strip()
                    if fv or mv:
                        panel.setdefault(str(pk), {}).setdefault(lang, (fv, mv))
    return panel


def build_spine(kind):
    """pk -> (section, order, fv, mv) from the CP2077 Hebrew spine (empty fv/mv => translate mode)."""
    base = json.load(open(os.path.join(RES, "localization_translated.json"), encoding="utf-8"))
    dlc = {}
    try:
        dlc = json.load(open(os.path.join(RES, "dlc_ep1_translated.json"), encoding="utf-8"))
    except FileNotFoundError:
        pass
    rows = {}
    order = 0
    for spine in (base, dlc):
        for sec, items in spine.items():
            if kind not in sec:
                continue
            for it in items:
                pk = str(it.get("primaryKey") or it.get("stringId"))
                fv = it.get("femaleVariant", "") or ""
                mv = it.get("maleVariant", "") or ""
                if not fv and not mv:
                    continue
                rows.setdefault(pk, (sec, order, fv, mv))
                order += 1
    return rows


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    print("CP2077 multi-language corpus (universal engine)")

    print("  onscreens: building panel + spine ...")
    on_panel = build_panel(ON_WORK, {"onscreens.json.json", "onscreens_final.json.json"})
    st = mlr.build("onscreens", on_panel, build_spine("onscreens"), OUT, CP_CFG)
    print(mlr.report("onscreens", st))

    have_sub = any((SUB_WORK / sc / l).exists() and any((SUB_WORK / sc / l).rglob("*.json.json"))
                   for sc in ("base", "ep1") for l in CP_LANGS)
    if have_sub:
        print("  subtitles: building panel + spine ...")
        sub_panel = build_panel(SUB_WORK, None)
        st = mlr.build("subtitles", sub_panel, build_spine("subtitles"), OUT, CP_CFG)
        print(mlr.report("subtitles", st))
    else:
        print("  subtitles: serialized panel not present — skipped (re-run when extraction is available).")


if __name__ == "__main__":
    main()
