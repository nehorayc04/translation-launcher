# -*- coding: utf-8 -*-
"""
gender_filter.py — flag which English source strings COULD require a
gender / number decision in Hebrew.

WHY
---
English drops the info Hebrew needs: "you" → אתה / את / אתם / אתן, "I'm ready" →
מוכן / מוכנה, "we" → אנחנו + a gendered verb. Most UI lines are gender-NEUTRAL
though (names, numbers, item nouns, nominalizable labels). So instead of screen-
shotting + annotating EVERY line, this classifier keeps only the ones that
genuinely carry a gender/number choice — the set the /translate pool + the agent
handoff should surface with a screenshot + a gender tag.

It is **game-agnostic** — it operates on a plain English string (+ optional
conversation context + speaker). A per-game adapter feeds it the corpus.

CP2077 nuance (the engine already helps)
----------------------------------------
CP2077 ships TWO gender slots per line — `femaleVariant` / `maleVariant` — and the
engine picks by the player's chosen gender for the protagonist **V**. So a line
whose gender depends on V (the player is the *addressee* "you", or V is the
*speaker* "I") is **PLAYER-gender-dependent**: the fix is to fill BOTH variants
differently and let the engine resolve it — NO screenshot needed. A line whose
gender is a FIXED referent (an NPC, or "the team") needs real context (speaker cue
/ screenshot). The CP2077 adapter tags which is which, and flags lines that are
player-gender-dependent yet currently have identical variants (the wasted slot).

CLI
---
  python gender_filter.py selftest                 # offline unit tests
  python gender_filter.py cp2077 --report          # run on the real CP2077 corpus
  python gender_filter.py cp2077 --out amb.jsonl   # + write the ambiguous set
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore

# ── axes of ambiguity ────────────────────────────────────────────────────────
AXIS_ADDRESSEE = "addressee_gender"   # "you" / imperative → אתה/את/אתם/אתן
AXIS_SPEAKER   = "speaker_gender"     # 1st-person predicate → מוכן/מוכנה
AXIS_REFERENT  = "referent_gender"    # he/she/named person + a gendered predicate
AXIS_NUMBER    = "number"             # we/they/team → יחיד/רבים

# ── signal lexicons ──────────────────────────────────────────────────────────
_SECOND = re.compile(r"\byou(?:r|rs|rself|rselves)?\b", re.I)
_FIRST  = re.compile(r"(?:\bI\b|\bI['’](?:m|ve|ll|d)\b|\b(?:me|my|mine|myself)\b)")
_GROUP  = re.compile(
    r"\b(?:we|us|our|ours|ourselves|they|them|their|themselves|"
    r"guys|team|crew|squad|everyone|everybody|y['’]all|folks|"
    r"all of you|both of you)\b", re.I)
_THIRD  = re.compile(r"\b(?:he|she|him|her|hers|his|himself|herself)\b", re.I)

# predicate adjectives / participles that INFLECT for gender in Hebrew when
# applied to a person ("ready" → מוכן/מוכנה). Presence of one of these next to a
# person pronoun is a strong gender signal; alone (HUD label) it's a weak one.
_PERSON_ADJ = {
    "ready", "dead", "alive", "sure", "done", "fine", "okay", "ok", "safe",
    "hurt", "injured", "wounded", "alone", "late", "early", "careful",
    "welcome", "proud", "sorry", "scared", "afraid", "tired", "exhausted",
    "lucky", "free", "gone", "back", "lost", "found", "ready", "armed",
    "trapped", "surrounded", "outnumbered", "wanted", "detected", "hidden",
    "poisoned", "stunned", "blinded", "silenced", "revived", "downed",
    "married", "born", "prepared", "committed", "convinced", "worried",
    "happy", "angry", "confused", "certain", "responsible", "guilty",
    "innocent", "strong", "weak", "fast", "slow", "smart", "brave",
}

# common game IMPERATIVE / action verbs — a string that STARTS with one is a
# 2nd-person instruction to the player (Hebrew imperative is gendered).
_IMPERATIVE_VERBS = {
    "open", "close", "press", "hold", "tap", "release", "follow", "go", "get",
    "take", "grab", "use", "find", "kill", "defeat", "eliminate", "talk",
    "speak", "call", "wait", "stop", "run", "walk", "move", "hide", "escape",
    "flee", "defend", "protect", "save", "rescue", "choose", "select", "pick",
    "continue", "confirm", "cancel", "accept", "decline", "equip", "unequip",
    "craft", "upgrade", "install", "uninstall", "jack", "hack", "scan", "aim",
    "shoot", "fire", "reload", "drive", "enter", "exit", "leave", "return",
    "meet", "look", "listen", "check", "search", "collect", "deliver",
    "activate", "deactivate", "disable", "enable", "avoid", "reach", "climb",
    "jump", "dodge", "block", "attack", "loot", "steal", "buy", "sell",
    "trade", "drop", "throw", "place", "build", "destroy", "repair", "heal",
    "wake", "sleep", "eat", "drink", "read", "write", "sign", "pay", "give",
    "bring", "send", "answer", "ask", "tell", "show", "hide", "turn", "push",
    "pull", "lift", "carry", "let", "keep", "start", "begin", "finish",
    "complete", "help", "watch", "beware", "remember", "forget", "focus",
    "prepare", "gear", "explore", "investigate", "interrogate", "negotiate",
}

# function / stop words used to decide "is this just a proper-noun phrase?"
_FUNC = {
    "the", "a", "an", "of", "and", "or", "to", "in", "on", "at", "for", "with",
    "by", "from", "as", "is", "are", "be", "this", "that", "these", "those",
    "&", "-", "/", "'s", "vs", "vs.",
}

_WORD = re.compile(r"[A-Za-z][A-Za-z'’]*")


def _tokens(s: str) -> list[str]:
    return _WORD.findall(s)


def _has_letters(s: str) -> bool:
    return bool(re.search(r"[A-Za-z]", s))


def _first_word(s: str) -> str | None:
    m = _WORD.search(s)
    return m.group(0).lower() if m else None


def _is_proper_noun_phrase(s: str) -> bool:
    """All alphabetic tokens Capitalized, none of them a lexical verb/adj/pronoun
    → a name / title (Night City, Arasaka Tower). Gender-neutral."""
    toks = _tokens(s)
    if not toks:
        return False
    letters = [t for t in toks if t.lower() not in _FUNC]
    if not letters:
        return False
    for t in letters:
        if not t[0].isupper():
            return False
        low = t.lower()
        if low in _IMPERATIVE_VERBS or low in _PERSON_ADJ:
            return False
        if low in ("you", "i", "we", "he", "she", "they"):
            return False
    return True


@dataclass
class Verdict:
    ambiguous: bool
    axes: list[str] = field(default_factory=list)
    signals: list[str] = field(default_factory=list)
    confidence: str = "low"          # low | med | high
    player_dependent: bool = False   # gender follows the player-controlled char
    reason: str = ""

    def as_dict(self) -> dict:
        return {
            "ambiguous": self.ambiguous,
            "axes": self.axes,
            "signals": self.signals,
            "confidence": self.confidence,
            "player_dependent": self.player_dependent,
            "reason": self.reason,
        }


def classify(en: str, context: str | None = None,
             speaker: str | None = None) -> Verdict:
    """Decide whether the English string COULD require a gender/number choice in
    Hebrew. `speaker` (if known, e.g. from a subtitle cue) refines who the 1st
    person is — a named NPC speaker = a fixed referent, not the player."""
    s = (en or "").strip()

    # ── definitely-safe short-circuits ───────────────────────────────────────
    if not s:
        return Verdict(False, reason="empty")
    if not _has_letters(s):
        return Verdict(False, reason="no letters (number/code/symbol)")
    toks = _tokens(s)
    if len(toks) == 1:
        w = toks[0].lower()
        if w in _IMPERATIVE_VERBS:
            return Verdict(True, [AXIS_ADDRESSEE], [f"imperative:{w}"],
                           "low", True, "single-word imperative (nominalizable)")
        if w in _PERSON_ADJ:
            return Verdict(True, [AXIS_REFERENT], [f"adj:{w}"],
                           "low", False, "lone person-adjective (HUD state?)")
        return Verdict(False, reason="single noun / name")
    if _is_proper_noun_phrase(s):
        return Verdict(False, reason="proper-noun phrase (name/title)")

    axes: list[str] = []
    signals: list[str] = []
    player_dep = False
    conf = "low"

    low = s.lower()
    adj_present = any(t.lower() in _PERSON_ADJ for t in toks)

    # ── 2nd person / imperative → addressee gender ───────────────────────────
    m2 = _SECOND.search(s)
    if m2:
        axes.append(AXIS_ADDRESSEE)
        signals.append(f"2nd:{m2.group(0)}")
        player_dep = True
        conf = "high"
    else:
        fw = _first_word(s)
        if fw in _IMPERATIVE_VERBS and len(toks) >= 2:
            axes.append(AXIS_ADDRESSEE)
            signals.append(f"imperative:{fw}")
            player_dep = True
            # a multi-word imperative with an object rarely nominalizes cleanly
            conf = "med"

    # ── plural / group → number (and group gender) ───────────────────────────
    mg = _GROUP.search(s)
    if mg:
        if AXIS_NUMBER not in axes:
            axes.append(AXIS_NUMBER)
        signals.append(f"group:{mg.group(0).lower()}")
        conf = "high"
        # "we"/"us"/"our" → the SPEAKER is inside the group → speaker gender too
        if re.search(r"\b(we|us|our|ours|ourselves)\b", low):
            if AXIS_SPEAKER not in axes:
                axes.append(AXIS_SPEAKER)

    # ── 1st person predicate → speaker gender ────────────────────────────────
    if _FIRST.search(s):
        # a bare "my X" noun rarely needs gender; a 1st-person + adjective does
        if adj_present or re.search(r"\bI\b|\bI['’](?:m|ve|ll|d)\b", s):
            if AXIS_SPEAKER not in axes:
                axes.append(AXIS_SPEAKER)
            signals.append("1st-person")
            conf = "high" if adj_present else max_conf(conf, "med")
            # if no named NPC speaker, the "I" is plausibly the player
            if speaker is None:
                player_dep = player_dep or True

    # ── 3rd-person person pronoun + gendered predicate → referent gender ──────
    m3 = _THIRD.search(s)
    if m3:
        if AXIS_REFERENT not in axes:
            axes.append(AXIS_REFERENT)
        signals.append(f"3rd:{m3.group(0).lower()}")
        conf = max_conf(conf, "med")

    # ── lone person-adjective in a longer phrase (e.g. "Objective complete") ──
    if not axes and adj_present:
        axes.append(AXIS_REFERENT)
        signals.append("person-adj")
        conf = "low"

    if not axes:
        return Verdict(False, reason="no gendered/number signal")

    reason = "player-gender (V) → fill both variants" if player_dep \
        else "fixed referent → needs context/screenshot"
    return Verdict(True, axes, signals, conf, player_dep, reason)


def max_conf(a: str, b: str) -> str:
    order = {"low": 0, "med": 1, "high": 2}
    return a if order[a] >= order[b] else b


# ── CP2077 adapter ───────────────────────────────────────────────────────────
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_CP_EN   = os.path.join(_ROOT, "Game Lab", "Cyberpunk 2077", "localization_export.json")
_CP_SPINE = os.path.join(_ROOT, "תרגום_משחקים", "source", "resources",
                         "localization_translated.json")


def _cp_load(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def cp2077_report(out_path: str | None, limit_sections: int | None = None,
                  onscreens_only: bool = True) -> None:
    """Run the classifier over the real CP2077 corpus and print statistics.

    English source text lives in the export's `femaleVariant` field (the
    engine's gender-neutral English). The Hebrew spine's femaleVariant/maleVariant
    let us also flag PLAYER-dependent lines whose two variants are currently
    IDENTICAL — the wasted-slot quality gap.
    """
    en = _cp_load(_CP_EN)
    spine = {}
    try:
        spine = _cp_load(_CP_SPINE)
    except Exception as exc:
        print(f"[warn] spine not loaded ({exc}); skipping variant-gap stat")

    def spine_index(section: str) -> dict:
        rows = spine.get(section, [])
        idx = {}
        for r in rows:
            idx[r.get("primaryKey")] = r
        return idx

    total = amb = 0
    by_axis: dict[str, int] = {}
    by_conf: dict[str, int] = {}
    player_dep = fixed_ref = 0
    wasted_slot = 0   # player-dependent + variants currently identical
    written = 0
    out = open(out_path, "w", encoding="utf-8") if out_path else None

    sections = list(en.keys())
    if onscreens_only:
        sections = [s for s in sections if s.startswith("onscreens/")]
    if limit_sections:
        sections = sections[:limit_sections]

    for section in sections:
        rows = en.get(section)
        if not isinstance(rows, list):
            continue
        sidx = spine_index(section)
        for r in rows:
            if not isinstance(r, dict):
                continue
            src = (r.get("femaleVariant") or "").strip()  # English text
            if not src:
                continue
            total += 1
            v = classify(src)
            if not v.ambiguous:
                continue
            amb += 1
            for ax in v.axes:
                by_axis[ax] = by_axis.get(ax, 0) + 1
            by_conf[v.confidence] = by_conf.get(v.confidence, 0) + 1
            if v.player_dependent:
                player_dep += 1
                sp = sidx.get(r.get("primaryKey"))
                if sp:
                    fvar = (sp.get("femaleVariant") or "").strip()
                    mvar = (sp.get("maleVariant") or "").strip()
                    if fvar and (mvar == "" or mvar == fvar):
                        wasted_slot += 1
            else:
                fixed_ref += 1
            if out:
                out.write(json.dumps({
                    "section": section,
                    "primaryKey": r.get("primaryKey"),
                    "secondaryKey": r.get("secondaryKey"),
                    "en": src,
                    **v.as_dict(),
                }, ensure_ascii=False) + "\n")
                written += 1
    if out:
        out.close()

    pct = (100.0 * amb / total) if total else 0.0
    print(f"\n=== CP2077 gender/number ambiguity ({'onscreens' if onscreens_only else 'ALL'}) ===")
    print(f"total translatable lines : {total:,}")
    print(f"AMBIGUOUS (need a choice) : {amb:,}  ({pct:.1f}%)")
    print(f"gender-NEUTRAL (skip)     : {total - amb:,}  ({100-pct:.1f}%)")
    print(f"\nby confidence: " + ", ".join(f"{k}={by_conf.get(k,0):,}" for k in ("high", "med", "low")))
    print("by axis:")
    for ax in (AXIS_ADDRESSEE, AXIS_SPEAKER, AXIS_REFERENT, AXIS_NUMBER):
        print(f"   {ax:18s}: {by_axis.get(ax,0):,}")
    print(f"\nplayer-gender-dependent (V → fill BOTH variants, engine resolves): {player_dep:,}")
    print(f"fixed referent (NPC/group → needs context/screenshot)          : {fixed_ref:,}")
    if spine:
        print(f"** wasted dual-slot (player-dep but variants IDENTICAL now)    : {wasted_slot:,}")
        print("   ^ these are lines where V's gender matters but the current mod")
        print("     ships the same Hebrew for male+female V — the fixable gap.")
    if out_path:
        print(f"\nwrote {written:,} ambiguous rows → {out_path}")


# ── offline selftest ─────────────────────────────────────────────────────────
def selftest() -> int:
    cases = [
        # (english, expect_ambiguous, note)
        ("News", False, "single noun"),
        ("Night City", False, "proper noun phrase"),
        ("100%", False, "number"),
        ("HDR10", False, "code"),
        ("Combat Knife", False, "item noun phrase"),
        ("Settings", False, "UI noun"),
        ("Are you sure?", True, "2nd person"),
        ("Follow Jackie.", True, "imperative + object"),
        ("Press to jump", True, "imperative"),
        ("I'm ready.", True, "1st person + adj"),
        ("We need to go.", True, "group + speaker"),
        ("Your team is waiting.", True, "2nd + group"),
        ("She's dead.", True, "3rd person + adj"),
        ("Objective complete", False, "about an object — gender fixed by the noun"),
        ("Save", True, "single imperative (low)"),
        ("Continue", True, "single imperative (low)"),
        ("Arasaka Tower", False, "name"),
    ]
    ok = True
    for en, expect, note in cases:
        v = classify(en)
        status = "OK" if v.ambiguous == expect else "FAIL"
        if v.ambiguous != expect:
            ok = False
        print(f"[{status}] {en!r:34s} amb={v.ambiguous!s:5s} "
              f"axes={v.axes} conf={v.confidence} pd={v.player_dependent}  ({note})")
    print("\nSELFTEST:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="gender_filter")
    p.add_argument("command", nargs="?", default="selftest",
                   choices=["selftest", "cp2077"])
    p.add_argument("--report", action="store_true", help="print corpus stats")
    p.add_argument("--out", default=None, help="write ambiguous rows to JSONL")
    p.add_argument("--all-sections", action="store_true",
                   help="include subtitles too (default: onscreens only)")
    p.add_argument("--limit", type=int, default=None,
                   help="limit number of sections (debug)")
    a = p.parse_args(argv)

    if a.command == "selftest":
        return selftest()
    if a.command == "cp2077":
        cp2077_report(a.out, limit_sections=a.limit,
                      onscreens_only=not a.all_sections)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
