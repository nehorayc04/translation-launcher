#!/usr/bin/env python3
"""Corsair Cove -- build + deploy the FULL Hebrew translation.

This is the Phase-2 builder. It reuses the exact mechanics the round-3 menu proof already
validated in-game (`build_menu_proof.py`), swapping the 20-string PLAN for the real corpus:

    hebrew.json {"<ns>|<key>": "…"}          <- the fleet / the /translate pool export
      -> QA gate (refuses to build on a defect)
      -> cc_rtl.to_logical  (store natural Hebrew + one leading RLM; iron rule applied)
      -> cc_locres.save     (byte-identical codec, 12/12 cultures)
      -> repak pack V11     -> pakchunk0_s2-WinGDK.pak   (a shipped 339-byte EMPTY stub)
      -> Hebrew fonts       -> pakchunk0_s4-WinGDK.pak

WHY THE STUB: an ADDED pak is never mounted on this Store/GDK build (proven over two
rounds: ~mods, flat Paks/, an invented pakchunk999 and a manifest-known _P name were ALL
ignored). 24 shipped `pakchunk0_sN` paks are 339-byte ZERO-ENTRY stubs whose real content
lives in the IoStore half, so overwriting one loses nothing and it IS mounted.
`_assert_stub_is_empty` refuses to touch any pak whose entry count is not 0.

ACTIVATION COSTS THE USER NOTHING: there is no RTL locale, so we hijack `en`, which is the
default culture -- install and play.

    python build_hebrew.py --check              QA the corpus, build nothing
    python build_hebrew.py                      build + verify, do NOT deploy
    python build_hebrew.py --deploy             build, verify, write into the game
    python build_hebrew.py --revert             restore the pristine 339-byte stubs
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GAME_DIR = os.path.dirname(HERE)
REPO = os.path.abspath(os.path.join(GAME_DIR, "..", ".."))
sys.path.insert(0, os.path.join(GAME_DIR, "tools"))
sys.path.insert(0, os.path.join(REPO, "universal"))

import cc_locres  # noqa: E402
import cc_rtl  # noqa: E402
from text_norm import has_long_dash  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# reuse the proof's proven paths/mechanics rather than duplicating them
sys.path.insert(0, HERE)
import build_menu_proof as P  # noqa: E402

HEBREW = os.path.join(HERE, "hebrew.json")
REGISTRY = os.path.join(HERE, "name_registry.json")
CORPUS = os.path.join(GAME_DIR, "extract", "context_source.json")

TOKEN = re.compile(r"<[^<>]{1,80}>|\{[^{}]{0,80}\}")
NIQQUD = re.compile(r"[֑-ֽֿ-ׇ]")
HEB = re.compile(r"[א-ת]")
# any letter that is neither Hebrew nor Latin = a foreign-script leak.
# Built from explicit escapes: writing the ranges as literal characters puts real
# control bytes in the source and Python refuses to compile it.
FOREIGN = re.compile(
    "[^"
    "\u0000-\u024f"              # ASCII, Latin-1 and Latin Extended
    "\u0590-\u05ff"              # Hebrew
    "\u200e\u200f\u202a-\u202e"  # bidi controls
    "\u2010-\u203a"              # dashes, quotes, ellipsis
    "]")


def is_namey(en: str) -> bool:
    """Name/code/brand PASSTHROUGH -- the same rule this project applies everywhere else
    (Playbook §7): a UI label made only of ALL-CAPS acronyms, CamelCase identifiers, or
    Title-Case brand/product words legitimately stays in English (DLSS, FSR, DirectX 11,
    AMD FidelityFX Super Resolution, PlaceholderLocaKey, Alt/Shift keybind labels...).
    A real English SENTENCE always has at least one lowercase-STARTING word (an article,
    preposition or verb) among its space-separated tokens -- that's the discriminator."""
    words = en.split()
    if not words or len(words) > 6:
        return False
    for w in words:
        w = w.strip('™®©.,!?:;"()')
        if not w:
            continue
        # a single character (x, +, -, ...) is a math/operator symbol, never prose
        if w[0].islower() and len(w) > 1:
            return False
    return True


def is_format_template(en: str, token_re) -> bool:
    """A string made ENTIRELY of {VAR} tokens plus separator punctuation and single-char
    operators (x, +, -, :) carries no language content at all -- there is nothing to
    translate. Distinct from is_namey (which is about SHORT title-case labels): this one
    has no word-count cap, because a format template like a full stat formula can be long
    while still containing zero real English words."""
    words = en.split()
    if not words:
        return False
    for w in words:
        core = token_re.sub("", w)
        core = core.strip('™®©.,!?:;"()+-')
        if core and not (len(core) == 1):
            return False
    return True


# ── QA gate ────────────────────────────────────────────────────────────────────
def qa(heb: dict, corpus: dict) -> list:
    """Refuse to build on a defect. Each rule is a real failure class this project has
    shipped before, not a style preference."""
    bad = []
    for k, he in heb.items():
        src = corpus.get(k)
        if src is None:
            bad.append((k, "key not in the corpus", he[:40]))
            continue
        en = (src.get("en") or "").strip()
        if not he or not he.strip():
            bad.append((k, "empty", ""))
            continue
        if NIQQUD.search(he):
            bad.append((k, "niqqud", he[:40]))
        # a symbol already present verbatim in the English source (e.g. ★, ™) is
        # not a translation defect -- only flag a script that is NEW to this line
        leaked = [c for c in FOREIGN.findall(he) if c not in en]
        if leaked:
            bad.append((k, "foreign script", he[:40]))
        if has_long_dash(he):
            bad.append((k, "long dash (iron rule)", he[:40]))
        # token multiset must survive verbatim, or the engine breaks
        if sorted(TOKEN.findall(en)) != sorted(TOKEN.findall(he)):
            bad.append((k, "token multiset changed", he[:40]))
        # a real newline is load-bearing here (762 lines carry one)
        if en.count("\n") != he.count("\n"):
            bad.append((k, "newline count changed", he[:40]))
        # still English: no Hebrew at all on a line that has real words
        if not HEB.search(he) and re.search(r"[A-Za-z]{3,}", TOKEN.sub(" ", en)):
            if he.strip() == en and not is_namey(en) and not is_format_template(en, TOKEN):
                bad.append((k, "untranslated (identical to English)", he[:40]))
    return bad


def check_registry(heb: dict, corpus: dict) -> list:
    """Report lines whose English contains a registry term but whose Hebrew does not use the
    canonical form. Advisory: Hebrew inflects, so this LISTS rather than blocks."""
    if not os.path.isfile(REGISTRY):
        return []
    reg = json.load(open(REGISTRY, encoding="utf-8"))["terms"]
    out = []
    for k, he in heb.items():
        en = (corpus.get(k, {}).get("en") or "")
        for term, t in reg.items():
            if t["mode"] == "keep" or len(term) < 4:
                continue
            if re.search(r"\b" + re.escape(term) + r"\b", en) and t["he"] not in he:
                out.append((k, term, t["he"]))
                break
    return out


# ── build ──────────────────────────────────────────────────────────────────────
def build_locres(heb: dict):
    stage = P._stage("full_loc")
    parsed = cc_locres.load(os.path.join(P.PRISTINE, P.LOC_REL))
    index = {(ns["name"], e["key"]): e
             for ns in parsed["namespaces"] for e in ns["entries"]}
    applied = missing = 0
    for k, he in heb.items():
        ns, _, key = k.partition("|")
        e = index.get((ns, key))
        if e is None:
            missing += 1
            continue
        e["value"] = cc_rtl.to_logical(he)     # iron rule + RLM base, in one place
        applied += 1
    dst = os.path.join(stage, P.LOC_REL)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    cc_locres.save(parsed, dst)
    print(f"  locres: applied {applied:,}  (missing keys {missing})")
    return P._pack(stage, os.path.join(P.WORK, "S2_locres_full.pak")), applied


def verify(pak, heb: dict, sample=200):
    """Read the built pak BACK and confirm the Hebrew is really in it -- never trust the
    builder's own count."""
    out = os.path.join(P.WORK, "_verify_full")
    P._force_rmtree(out)
    os.makedirs(out, exist_ok=True)
    P._run([P.REPAK, "unpack", "--output", out, pak])
    got = cc_locres.load(os.path.join(out, P.LOC_REL))
    idx = {(ns["name"], e["key"]): e["value"]
           for ns in got["namespaces"] for e in ns["entries"]}
    keys = list(heb)[:sample]
    ok = sum(1 for k in keys
             if idx.get((k.split("|", 1)[0], k.split("|", 1)[1])) == cc_rtl.to_logical(heb[k]))
    print(f"  read-back: {ok}/{len(keys)} sampled keys match")
    P._force_rmtree(out)
    return ok == len(keys)


def main(argv):
    if "--revert" in argv:
        return P.revert()

    if not os.path.isfile(HEBREW):
        print("no hebrew.json yet - the translation has not been delivered.")
        print("  expected: %s  {\"<namespace>|<key>\": \"…\"}" % HEBREW)
        print("  source:   the /translate pool export, or the agent/fleet handoff")
        return 1

    heb = json.load(open(HEBREW, encoding="utf-8"))
    corpus = json.load(open(CORPUS, encoding="utf-8"))
    print(f"  corpus {len(corpus):,} rows · hebrew.json {len(heb):,} lines "
          f"({len(heb) / len(corpus) * 100:.1f}%)")

    defects = qa(heb, corpus)
    if defects:
        print(f"\n  QA FAILED - {len(defects)} defects (first 20):")
        for k, why, s in defects[:20]:
            print(f"    {why:<34} {k}  {s}")
        return 1
    print("  QA clean")

    drift = check_registry(heb, corpus)
    if drift:
        print(f"  ⚠ name-registry drift on {len(drift)} lines (advisory, not blocking):")
        for k, term, want in drift[:8]:
            print(f"    {term} -> {want}   {k}")

    if "--check" in argv:
        return 0

    pak, applied = build_locres(heb)
    fonts = P.build_fonts()
    print(f"  packed: {os.path.basename(pak)} ({os.path.getsize(pak):,} B), "
          f"{os.path.basename(fonts)} ({os.path.getsize(fonts):,} B)")
    if not verify(pak, heb):
        print("  VERIFY FAILED - not deploying")
        return 1

    if "--deploy" not in argv:
        print("\n  built + verified. Pass --deploy to write it into the game.")
        return 0

    P._remove_added(quiet=True)               # clear anything rounds 1-2 left behind
    os.makedirs(P.STUB_BAK, exist_ok=True)
    for src, stub in ((pak, P.STUB_LOC), (fonts, P.STUB_FNT)):
        dst = os.path.join(P.PAKS, stub)
        bak = os.path.join(P.STUB_BAK, stub + ".orig")
        if not os.path.isfile(bak):
            # First write ever: the live pak must still be a genuine 339-byte empty stub.
            # (If the menu proof already ran, the backup exists and the live pak holds the
            #  PROOF -- checking it for emptiness there would abort on our own output.)
            P._assert_stub_is_empty(dst)
            shutil.copy2(dst, bak)
            print(f"  backed up pristine stub -> {stub} ({os.path.getsize(bak):,} B)")
        shutil.copy2(src, dst)
        print(f"  deployed -> {stub} ({os.path.getsize(dst):,} B)")
    print("\n  DONE. Launch the game - `en` is the default culture, no setting to change.")
    print("  revert: python build_hebrew.py --revert")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
