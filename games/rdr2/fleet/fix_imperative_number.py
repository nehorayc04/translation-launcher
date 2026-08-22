#!/usr/bin/env python3
"""fix_imperative_number.py — unify 2nd-person IMPERATIVES to masculine SINGULAR.

🔑 THE CORPUS DECIDED THIS, NOT TASTE. Across the 217k already-shipping lines the singular
imperative beats the plural **3,088 : 693 (82 %)** — so the game's own voice is masculine
singular, and the 335 plural lines the fleet produced in the new bank are the odd ones out.
The multi-lens LQA independently confirmed the same defect from the other side: a single
tutorial paragraph that flips שלפו / כוון / והשליכו inside one instruction, and byte-identical
English compendium boilerplate rendered השתמשו on one key and השתמש on another.

🔴🔴 A BLIND PLURAL->SINGULAR SWAP CORRUPTS CORRECT HEBREW. Hebrew's 2nd-person plural
imperative is spelled identically to the 3rd-person plural PAST: `הם פתחו את הכלוב` = "they
opened the cage" and `פתחו באש` = "open fire" share the word. And a line whose English really
does address a group (`You and your thieving chums go back...`) is correctly plural. So every
swap is ENGLISH-GUARDED twice over:

  1. the English must actually carry that verb as an IMPERATIVE -- sentence-initial once the
     engine tokens and a leading `~z~` are stripped (this alone kills the past-tense trap,
     because "they opened up the cage" does not start with "Open"); and
  2. the line must not carry a plural-addressee cue (`you all`, `boys`, `everyone`, ...).

A UI objective/prompt (`~INPUT_`, `~COLOR_MP_OBJECTIVE`, `~BLIP_`) is always addressed to the
single player, so it takes the swap on rule 1 alone.

    python fix_imperative_number.py            # report
    python fix_imperative_number.py --apply    # write (backs the bank up first)
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
BANK = os.path.join(HERE, "hebrew_missing.json")
CORPUS = os.path.join(HERE, "corpus_missing.json")

# english imperative -> (plural Hebrew that must not ship, masculine singular that must)
VERBS = {
    "use":      [("השתמשו", "השתמש")],
    "hold":     [("החזיקו", "החזק")],
    "press":    [("לחצו", "לחץ")],
    "check":    [("בדקו", "בדוק")],
    "take":     [("קחו", "קח")],
    "open":     [("פתחו", "פתח")],
    "choose":   [("בחרו", "בחר")],
    "select":   [("בחרו", "בחר")],
    "release":  [("שחררו", "שחרר")],
    "free":     [("שחררו", "שחרר")],
    "aim":      [("כוונו", "כוון"), ("כוון", "כוון")],
    "go":       [("לכו", "לך"), ("גשו", "גש")],
    "return":   [("חזרו", "חזור")],
    "wait":     [("המתינו", "המתן")],
    "try":      [("נסו", "נסה")],
    "equip":    [("שלפו", "שלוף"), ("הפעילו", "הפעל")],
    "draw":     [("שלפו", "שלוף")],
    "throw":    [("השליכו", "השלך"), ("זרקו", "זרוק")],
    "approach": [("התקרבו", "התקרב")],
    "continue": [("המשיכו", "המשך")],
    "keep":     [("המשיכו", "המשך")],
    "stop":     [("עצרו", "עצור")],
    "look":     [("הביטו", "הבט")],
    "speak":    [("דברו", "דבר")],
    "talk":     [("דברו", "דבר")],
    "ride":     [("רכבו", "רכב")],
    "shoot":    [("ירו", "ירה")],
    "fire":     [("ירו", "ירה")],
    "watch":    [("שימו", "שים"), ("צפו", "צפה")],
    "put":      [("שימו", "שים")],
    "move":     [("זוזו", "זוז")],
    "follow":   [("עקבו", "עקוב")],
    "find":     [("מצאו", "מצא")],
    "kill":     [("הרגו", "הרוג")],
    "deliver":  [("מסרו", "מסור")],
    "help":     [("עזרו", "עזור")],
    "search":   [("חפשו", "חפש")],
    "buy":      [("קנו", "קנה")],
    "sell":     [("מכרו", "מכור")],
    "visit":    [("בקרו", "בקר")],
    "enter":    [("היכנסו", "היכנס")],
    "leave":    [("עזבו", "עזוב")],
    "let":      [("תנו", "תן")],
    "see":      [("ראו", "ראה")],
}

# an English line that really does address a group keeps its plural
PLURAL_CUE = re.compile(
    r"\b(you all|y'?all|boys|men|gentlemen|everyone|everybody|folks|lads|fellas|"
    r"gang|all of you|both of you)\b", re.I)

UI_TOKEN = re.compile(r"~(INPUT_|COLOR_MP_OBJECTIVE|BLIP_|COLOR_MENU)")
STRIP = re.compile(r"~[^~]*~|%[0-9.\-+#]*[a-zA-Z]|\[[^\]]*\]")


def _he(w: str) -> re.Pattern:
    """word-boundary for Hebrew: `\\b` is useless here (Hebrew letters are \\w), and a bare
    substring match would rewrite a longer word that merely ends with the form. One attached
    prefix letter is allowed, since Hebrew glues ו/ה/ש/כ to the next word."""
    return re.compile(r"(?<![א-ת])([והשכ]?)" + re.escape(w) + r"(?![א-ת])")


PATS = {p: (_he(p), s) for subs in VERBS.values() for (p, s) in subs}


def en_of(v):
    if isinstance(v, dict):
        return (v.get("en") or "").strip()
    return str(v or "").strip()


def leading_verbs(en: str) -> set[str]:
    """The English verbs that appear in IMPERATIVE position: the first word of the whole line
    or of any sentence/clause inside it, once engine tokens are stripped. A tutorial paragraph
    chains several ('Aim with X and throw your Lasso... approach the animal'), and every one of
    them addresses the same single player."""
    txt = STRIP.sub(" ", en)
    out = set()
    for part in re.split(r"[.!?;\n]+|\bthen\b|\band\b", txt, flags=re.I):
        w = part.strip().split()
        if w:
            out.add(w[0].strip(",:").lower())
    return out


def main() -> None:
    apply = "--apply" in sys.argv
    bank = json.load(open(BANK, encoding="utf-8"))
    corpus = json.load(open(CORPUS, encoding="utf-8"))

    changed, per_verb, skipped_cue, skipped_nolead = {}, {}, 0, 0
    for k, he in bank.items():
        if not isinstance(he, str) or not he:
            continue
        en = en_of(corpus.get(k))
        if not en:
            continue
        hits = [(p, s) for p, (rx, s) in PATS.items() if rx.search(he)]
        if not hits:
            continue
        if PLURAL_CUE.search(en):
            skipped_cue += 1
            continue
        lead = leading_verbs(en)
        ui = bool(UI_TOKEN.search(en))
        new = he
        for pl, sg in hits:
            ok = any(pl in [q for (q, _r) in VERBS.get(v, [])] for v in lead)
            if not ok and ui:
                # a UI objective/prompt is always addressed to the single player; still require
                # the English to name the verb somewhere, so we never touch unrelated prose
                ok = any(pl in [q for (q, _r) in VERBS.get(v, [])]
                         for v in re.findall(r"[A-Za-z']+", STRIP.sub(" ", en).lower()))
            if not ok:
                continue
            n2 = PATS[pl][0].sub(lambda m: m.group(1) + sg, new)
            if n2 != new:
                per_verb[pl] = per_verb.get(pl, 0) + 1
                new = n2
        if new != he:
            changed[k] = new
        elif not any(any(p in [q for (q, _r) in VERBS.get(v, [])] for v in lead)
                     for p, _s in hits):
            skipped_nolead += 1

    print(f"bank {len(bank):,} · lines to fix: {len(changed):,}")
    print(f"  left alone: {skipped_cue} (English addresses a group) · "
          f"{skipped_nolead} (verb not in imperative position — past tense / unrelated)")
    for v, n in sorted(per_verb.items(), key=lambda kv: -kv[1]):
        print(f"    {v:10} {n:4}")
    for k in list(changed)[:8]:
        print(f"  en: {en_of(corpus.get(k))[:78]}")
        print(f"   -  {bank[k][:78]}")
        print(f"   +  {changed[k][:78]}")
    if not changed or not apply:
        if changed:
            print("\n(report only — pass --apply to write)")
        return

    ts = time.strftime("%Y%m%d_%H%M%S")
    shutil.copy2(BANK, f"{BANK}.bak.imper.{ts}")
    bank.update(changed)
    tmp = BANK + ".tmp"
    json.dump(bank, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(tmp, BANK)
    print(f"applied {len(changed):,} · backup {os.path.basename(BANK)}.bak.imper.{ts}")


if __name__ == "__main__":
    main()
