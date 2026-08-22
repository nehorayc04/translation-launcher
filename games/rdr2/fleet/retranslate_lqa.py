#!/usr/bin/env python3
"""retranslate_lqa.py — send the LQA-CONFIRMED defective lines back to the FLEET.

The multi-lens LQA (6 lenses, each finding independently refuted by a skeptic) confirmed 15
defects. Two systematic passes -- `fix_imperative_number.py` (number) and
`fix_moonshine_term.py` (a calqued role name) -- fixed 5 of them across 565 lines. The other
10 are not a mechanical class: an English idiom calqued word-for-word, an adjective that
disagrees with its own noun, a plural noun where the English is singular. Those need a real
re-translation, so they go back to the SAME providers the fleet uses -- Claude never
translates the corpus itself.

Each line is re-served WITH the verified critique in the prompt, which is the whole point: a
plain re-ask would very likely reproduce the same calque, while "this specific thing is wrong,
here is why" is information the first pass never had.

The structural guard is the fleet's own: the engine-token multiset must survive, the result
must be Hebrew, must not be a copy of the English, and must not carry niqqud.

    python retranslate_lqa.py            # dry run: show what would be sent
    python retranslate_lqa.py --apply    # translate + write into hebrew_missing.json
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BANK = os.path.join(HERE, "hebrew_missing.json")
CORPUS = os.path.join(HERE, "corpus_missing.json")
KEYS_FALLBACK = r"C:\rdrwd\keys.json"

STRUCT = re.compile(r"~[^~]*~|%[0-9.\-+#]*[a-zA-Z]")
NIQ = re.compile(r"[\u0591-\u05C7]")
HEB = re.compile(r"[א-ת]")

# key -> the verified critique, in the translator's own working language
JOBS = {
    "0x6CC34A0D": "כל פעלי הציווי בפסקה מופנים לאותו שחקן יחיד — חייבים להיות כולם בזכר יחיד "
                  "(שלוף / כוון / השלך / התקרב), לא ערבוב של יחיד ורבים.",
    "0x4EA0C9F1": "זו שורת פיד על שחקן אחד (~1p~) בגוף שלישי עבר — 'בדק את הזמן', לא ציווי "
                  "וגם לא רבים. השורות האחיות בפיד: בירך / רשם / הודה.",
    "0x75636F46": "‏'target' באנגלית הוא יחיד, והמפתח האח מתרגם אותו 'היעד'. צריך יחיד ואותו "
                  "מונח, לא 'המטרות'.",
    "0x53952474": "‏'מזוודה' היא נקבה, אז הפועל חייב להתאים לה. גם סדר המילים טבעי יותר "
                  "כשהנושא ראשון.",
    "0x01275721": "‏'קשת' היא נקבה — התואר חייב להתאים. באותה שורה עצמה כבר כתוב נכון "
                  "'קשת משופרת'.",
    "0x65656C46": "יעד משימה — ציווי בזכר יחיד כמו שאר היעדים (קפוץ, עלה, הרוג, עקוב).",
    "0x1068C6F2": "‏'in person' זה 'באופן אישי' / 'פנים אל פנים'. 'באישיות' הוא תרגום מילולי "
                  "שגוי.",
    "0x9C929A78": "‏'Poor thing' הוא ביטוי חמלה — 'מסכן' / 'מסכנה', לא 'דבר עלוב'. "
                  "'Hope it doesn't miss this' = 'אני מקווה שהוא לא יתגעגע לזה'.",
    "0x5E11E84F": "‏'ranches and farms' תורגם 'בחוות ובחוות' — אותה מילה פעמיים. צריך שתי "
                  "מילים שונות, למשל 'בחוות בקר ובאחוזות חקלאיות'.",
    "0x93625D14": "‏'in order for these settings to be applied' תורגם 'כדי לאפליקציה' — שיבוש. "
                  "צריך 'כדי להחיל את ההגדרות האלה'. וגם: 'יש להפעיל מחדש את המשחק'.",
    "0x961A4B8B": "‏'rival moonshiners' הם מתחרים שמייצרים מונשיין — לא 'המבריקים' (shine). "
                  "וכל הציוויים בזכר יחיד: טפל / אל תהרוג.",
}

SYS = (
    "אתה מתרגם מקצועי של Red Dead Redemption 2 לעברית. תקבל שורה עם התרגום הנוכחי שלה "
    "וביקורת מאומתת שמסבירה מה שגוי בו. תקן רק את מה שהביקורת מצביעה עליו ושמור על שאר "
    "השורה.\n"
    "כללים קשיחים:\n"
    "1. כל אסימון מנוע (~...~ ו-%s/%d) חייב להופיע בפלט בדיוק כמו בקלט, באותו מספר מופעים.\n"
    "2. עברית תקינה בלבד, בלי ניקוד, בלי אנגלית מלבד שמות מותג.\n"
    "3. פנייה לשחקן: זכר יחיד.\n"
    "4. אין להוסיף הסברים. החזר JSON בלבד: {\"<key>\": \"<hebrew>\"}"
)


def _atomic(path: str, obj) -> bool:
    """Windows loses os.replace to whatever else has the file open — and the 5-minute merge
    has this one open often. Use a PID-unique temp (two writers must not share it) and back
    off; report failure instead of raising, so a locked bank never costs the caller its work."""
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)
    for wait in (0, 0.4, 1.0, 2.5, 5.0):
        if wait:
            time.sleep(wait)
        try:
            os.replace(tmp, path)
            return True
        except OSError:
            continue
    try:
        os.remove(tmp)
    except OSError:
        pass
    return False


def en_of(v) -> str:
    if isinstance(v, dict):
        return (v.get("en") or "").strip()
    return str(v or "").strip()


def ok(en: str, he: str) -> str:
    if not he or not HEB.search(he):
        return "no-hebrew"
    if NIQ.search(he):
        return "niqqud"
    if he.strip() == en.strip():
        return "copy-en"
    a = sorted(STRUCT.findall(en))
    b = sorted(STRUCT.findall(he))
    if a != b:
        return f"token-mismatch {a} != {b}"
    return ""


def main() -> None:
    apply = "--apply" in sys.argv
    bank = json.load(open(BANK, encoding="utf-8"))
    corpus = json.load(open(CORPUS, encoding="utf-8"))

    import fleet_providers as fp

    keys = fp.load_keys(HERE)
    if not keys and os.path.exists(KEYS_FALLBACK):
        keys = json.load(open(KEYS_FALLBACK, encoding="utf-8"))
    if not keys:
        sys.exit("!! no provider keys found (keys.json)")
    fleet = fp.Fleet(keys)
    print(f"providers: {[p for p, *_ in fleet.avail]}")

    # a re-run must retry ONLY what failed (a provider timeout, a guard rejection) — re-asking
    # a line that already passed both costs a call and can only make it worse.
    done_ov = {}
    ov_path = os.path.join(HERE, "lqa_overrides.json")
    if os.path.exists(ov_path):
        done_ov = json.load(open(ov_path, encoding="utf-8"))

    out, fails = {}, []
    for k, critique in JOBS.items():
        if k in done_ov and "--force" not in sys.argv:
            continue
        en = en_of(corpus.get(k))
        cur = bank.get(k, "")
        if not en or not cur:
            print(f"  {k}: not in the bank yet — skipped")
            continue
        user = (f'מפתח: {k}\n'
                f'אנגלית: {en}\n'
                f'תרגום נוכחי: {cur}\n'
                f'הביקורת המאומתת: {critique}\n'
                f'החזר JSON: {{"{k}": "<התרגום המתוקן>"}}')
        if not apply:
            print(f"\n--- {k}\n  en : {en[:120]}\n  cur: {cur[:120]}\n  fix: {critique[:120]}")
            continue
        raw = ""
        try:
            raw = fleet.complete(SYS, user, retries=3, timeout=120, max_tokens=1200)
        except Exception as e:                                   # noqa: BLE001
            fails.append((k, f"provider error: {e}"))
            continue
        m = re.search(r"\{.*\}", raw or "", re.S)
        he = ""
        if m:
            try:
                he = (json.loads(m.group(0)) or {}).get(k, "") or ""
            except Exception:                                     # noqa: BLE001
                he = ""
        why = ok(en, he) if he else "no-json"
        if why:
            fails.append((k, f"{why} | raw={ (raw or '')[:90] }"))
            continue
        out[k] = he
        print(f"  {k}\n   -  {cur[:100]}\n   +  {he[:100]}")

    if not apply:
        print(f"\n(dry run — {len(JOBS)} lines would be re-served; pass --apply)")
        return

    print(f"\nfixed {len(out)} · failed {len(fails)}")
    for k, why in fails:
        print(f"  !! {k}: {why}")
    if not out:
        return
    # 🔴 THE OVERLAY IS WRITTEN FIRST, AND IT IS THE REAL DELIVERABLE. The 5-minute merge
    # rebuilds hebrew_missing.json from the banks, so anything written straight into the bank
    # is reverted on the next pull; and the merge holds the file often enough that os.replace
    # loses a race with it (WinError 5 — which is exactly what threw away the first run's 11
    # good translations). Persist to the overlay, then best-effort the bank.
    ov = os.path.join(HERE, "lqa_overrides.json")
    prev = json.load(open(ov, encoding="utf-8")) if os.path.exists(ov) else {}
    prev.update(out)
    _atomic(ov, prev)
    print(f"overlay {os.path.basename(ov)} now holds {len(prev)} lines")

    ts = time.strftime("%Y%m%d_%H%M%S")
    try:
        shutil.copy2(BANK, f"{BANK}.bak.lqa.{ts}")
    except OSError:
        pass
    bank.update(out)
    if _atomic(BANK, bank):
        print(f"bank updated · backup {os.path.basename(BANK)}.bak.lqa.{ts}")
    else:
        print("bank was locked by the merge — the overlay will re-apply it on the next pull")


if __name__ == "__main__":
    main()
