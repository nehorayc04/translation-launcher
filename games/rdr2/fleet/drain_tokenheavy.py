#!/usr/bin/env python3
"""drain_tokenheavy.py — translate the token-heavy tail with the engine tokens MASKED.

🔴 THE PROBLEM, measured: of the 682 lines the fleet still had not banked, **428 (63 %) carry
3+ engine tokens** — `Take the ~COLOR_MP_OBJECTIVE_FRIENDLY~Saboteur~s~ ~1~` is five words and
three tokens. The worker sends the raw English, so the model has to reproduce
`~COLOR_MP_OBJECTIVE_FRIENDLY~` and `~s~` byte-for-byte inside Hebrew text, and it keeps eating
the `s` out of `~s~`. The guard then correctly rejects the line, it is re-served, and the same
thing happens — the `+0/13` batches in the worker logs are exactly this.

**THE FIX IS TO STOP SHOWING THE MODEL SOMETHING IT CAN BREAK.** Each token is replaced by a
compact opaque marker `⟦0⟧`, `⟦1⟧` … before the call and restored after. The model cannot
mangle a token it never saw; the markers are short, carry no meaning to "translate", and they
also shrink the prompt, which matters on groq where `max_tokens` is charged against the
per-minute budget. This is the same atomic-placeholder technique `rdr2_rtl` already uses to
protect tokens from the bidi algorithm — applied one layer earlier, to the model.

Deliberately a SEPARATE process, not an edit to `rdr2_nim.py`: the 21-stream fleet is running
and mid-run surgery on the worker would risk stopping it. This one only ADDS lines; a key the
fleet banks first simply never reaches here.

    python drain_tokenheavy.py            # dry run — show the masking on a few real lines
    python drain_tokenheavy.py --apply [--max N]
"""
from __future__ import annotations

import json
import os
import re
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
# 🔴 The merge is `sorted(glob("out_*.json"))` + `dict.update()`, so the LAST filename
# wins. `out_maskdrain*` loses to `out_vm*` — meaning a still-running worker that
# rewrites its own bank restores a line this drain just fixed (and undoes a purge).
# `out_zzmask*` sorts last, so the masked, panel-informed translation always wins.
OUT = os.path.join(HERE, "banks_missing", "out_zzmask.json")

STRUCT = re.compile(r"~[^~]*~|\{[^}]*\}|%%|%[#0-9.*\-+]*[a-zA-Z]+")
NIQ = re.compile(r"[֑-ׇ]")
HEB = re.compile(r"[א-ת]")
FOREIGN = re.compile(r"[Ѐ-ӿ؀-ۿ一-鿿぀-ヿ가-힯]")
MARK = re.compile(r"⟦(\d+)⟧")

SYS = (
    "אתה מתרגם מקצועי של Red Dead Redemption 2 לעברית.\n"
    "לכל שורה אתה מקבל את האנגלית ואת התרגומים המקצועיים של המשחק עצמו לשפות נוספות "
    "(ru=רוסית, pl=פולנית, de=גרמנית, fr=צרפתית, es=ספרדית, it=איטלקית, br=פורטוגזית).\n"
    "הכרע את העברית מול כל השפות יחד, לא מהאנגלית לבדה:\n"
    "• רוסית ופולנית מגלות מגדר של הדובר ושל הנמען (עבר -л/-ла, -łem/-łam) — אנגלית מסתירה את זה.\n"
    "• צרפתית/ספרדית/איטלקית מגלות מגדר של המושא; גרמנית מגלה רמת פנייה.\n"
    "• אם שפה אחת חורגת מכולן — היא זו שטועה.\n"
    "בטקסט יש סמנים בצורה ⟦0⟧ ⟦1⟧ ⟦2⟧ — הם מייצגים קוד של המנוע.\n"
    "כללים קשיחים:\n"
    "1. העתק כל סמן ⟦n⟧ בדיוק כמו שהוא, עם אותו מספר, ואותו מספר מופעים. אל תתרגם אותו ואל "
    "תשנה אותו. מותר להזיז אותו למקום הטבעי במשפט העברי.\n"
    "2. עברית תקינה בלבד, בלי ניקוד. שמות מותג ושמות פרטיים נשארים באנגלית.\n"
    "3. פנייה לשחקן: זכר יחיד.\n"
    "4. החזר JSON בלבד: {\"<key>\": \"<hebrew>\"} — בלי הסברים."
)

# 🔴 ARBITRATE MODE — for lines whose ENGLISH is not trustworthy.
# The `.yldb` extraction pairs a hash with the wrong string on ~27 % of keys (proven: at
# `SPEAKER_NBX_BANK_TELLER` it produced "Look Through Window" while de/fr/it/es all say
# "clerk"). The game's own OTHER languages are extracted the same way, but their errors are
# NOT perfectly correlated, so a 3-of-4 agreement against the English is strong evidence the
# English is the mis-paired one. This prompt therefore inverts the usual authority: the
# majority of the panel wins, and the English is just one more vote.
SYS_ARB = (
    "אתה מתרגם מקצועי של Red Dead Redemption 2 לעברית.\n"
    "לכל שורה אתה מקבל טקסט באנגלית + התרגומים הרשמיים של המשחק לשפות נוספות.\n"
    "🔴 האנגלית כאן אינה אמינה — בחלק מהשורות היא שויכה בטעות לשורה אחרת לגמרי.\n"
    "לכן: הכרע לפי הרוב. אם שתי שפות או יותר מסכימות על משמעות אחת והאנגלית אומרת משהו אחר "
    "— תרגם את משמעות הרוב והתעלם מהאנגלית. אם כולן מסכימות — תרגם רגיל.\n"
    "בטקסט יש סמנים בצורה ⟦0⟧ ⟦1⟧ — הם קוד של המנוע.\n"
    "כללים קשיחים:\n"
    "1. העתק כל סמן ⟦n⟧ בדיוק, אותו מספר ואותו מספר מופעים. מותר להזיז אותו למקום הטבעי.\n"
    "2. עברית תקינה בלבד, בלי ניקוד. שמות מותג ושמות פרטיים נשארים באנגלית.\n"
    "3. אלה תוויות ממשק קצרות — תרגם קצר וענייני, בלי משפט שלם ובלי נקודה בסוף.\n"
    "4. פנייה לשחקן: זכר יחיד.\n"
    "5. החזר JSON בלבד: {\"<key>\": \"<hebrew>\"} — בלי הסברים."
)

ARBITRATE = "--arbitrate" in sys.argv

# 🔴 REVIEW MODE — monotonic QA of lines that already have Hebrew.
# ⚠️ ARBITRATE ("follow the panel majority") was tried first and made things WORSE: on a
# mis-paired key the sibling panel is mis-paired too, so the majority is confidently wrong,
# and the model duly rewrote correct lines into broken ones (it moved `~o~`/`~HC_~1p~~`
# wrapper markers OUT of the phrase they wrap). Review mode is the safe shape: it is used
# ONLY where the panel was measured COHERENT (low length dispersion across languages), it
# shows the model the current Hebrew, and its default is to return that Hebrew unchanged.
SYS_REV = (
    "אתה עורך לשוני של תרגום Red Dead Redemption 2 לעברית.\n"
    "לכל שורה אתה מקבל: en (אנגלית), he (התרגום הקיים), ותרגומי המשחק לשפות נוספות.\n"
    "המשימה: לתקן רק שגיאה אמיתית. ברירת המחדל היא להחזיר את he כמו שהוא.\n"
    "תקן רק אם: המשמעות פשוט שגויה (מילה אחרת לגמרי), או שיש שגיאת עברית ממשית.\n"
    "אל תתקן ניסוח, סגנון, או בחירת מילה נרדפת. אל תוסיף נקודה בסוף. אלה תוויות ממשק קצרות.\n"
    "אם שפה אחת בפאנל חורגת מכולן — התעלם ממנה, היא מפתח שגוי.\n"
    "בטקסט יש סמנים ⟦0⟧ ⟦1⟧ — קוד של המנוע. העתק אותם בדיוק, אותו מספר ואותם מופעים, "
    "ואל תוציא אותם מהביטוי שהם עוטפים.\n"
    "שמות מותג ושמות פרטיים נשארים באנגלית. בלי ניקוד.\n"
    "החזר JSON בלבד: {\"<key>\": \"<hebrew>\"} — לכל מפתח, גם אם לא שינית."
)
REVIEW = "--review" in sys.argv

# The corpus stores the game's own locales under short codes; name them for the model.
LANGNAME = {"ru": "ru", "ro": "ru", "po": "pl", "pl": "pl", "ge": "de", "de": "de",
            "fr": "fr", "sp": "es", "es": "es", "it": "it", "br": "br", "pt": "br"}


def en_of(v) -> str:
    if isinstance(v, dict):
        return (v.get("en") or "").strip()
    return str(v or "").strip()


def mask(en: str):
    toks: list[str] = []

    def _sub(m):
        toks.append(m.group(0))
        return f"⟦{len(toks) - 1}⟧"

    return STRUCT.sub(_sub, en), toks


def mask_with(txt: str, toks: list[str]) -> str:
    """Mask a REFERENCE language's line using the ENGLISH line's token numbering.

    A sibling language carries the same engine tokens, so `~s~` there must show up as the same
    `⟦n⟧` the model is asked to reproduce — otherwise the panel teaches it a second, conflicting
    spelling of the very thing we are hiding. A token the English line does not have becomes
    `⟦?⟧`: it survives into the output as a literal marker, matches no `STRUCT`, and is therefore
    REJECTED by the guard — fail-closed, never a silently mangled token.
    """
    def _sub(m):
        t = m.group(0)
        return f"⟦{toks.index(t)}⟧" if t in toks else "⟦?⟧"

    return STRUCT.sub(_sub, txt)


def unmask(he: str, toks: list[str]) -> str:
    return MARK.sub(lambda m: toks[int(m.group(1))]
                    if int(m.group(1)) < len(toks) else m.group(0), he)


def bad(en: str, he: str) -> str:
    if not he or not he.strip():
        return "empty"
    if not HEB.search(he):
        return "no-hebrew"
    if NIQ.search(he):
        return "niqqud"
    if FOREIGN.search(he):
        return "foreign-script"
    if he.strip() == en.strip():
        return "copy-en"
    if sorted(STRUCT.findall(he)) != sorted(STRUCT.findall(en)):
        return "token-mismatch"
    if MARK.search(he) or "⟦" in he:
        # A leftover marker is INVISIBLE to the token check (markers are not `STRUCT`), so an
        # unmatched `⟦?⟧` — or a `⟦7⟧` the model invented past the end of the token list — would
        # otherwise ship as literal junk on screen. Measured: 1 leak in 360 lines.
        return "marker-leak"
    return ""


def main() -> None:
    apply = "--apply" in sys.argv
    cap = 10 ** 9
    if "--max" in sys.argv:
        cap = int(sys.argv[sys.argv.index("--max") + 1])

    # `--corpus F --out G`: run the same masked/panel path over ANY key set (used for the
    # 105-line English-gap sweep, which lives outside corpus_missing.json).
    if "--corpus" in sys.argv:
        globals()["CORPUS"] = sys.argv[sys.argv.index("--corpus") + 1]
    if "--out" in sys.argv:
        globals()["OUT"] = sys.argv[sys.argv.index("--out") + 1]
        globals()["BANK"] = os.devnull

    corpus = json.load(open(CORPUS, encoding="utf-8"))
    bank = json.load(open(BANK, encoding="utf-8")) if os.path.getsize(BANK or os.devnull) else {}
    have = dict(json.load(open(OUT, encoding="utf-8"))) if os.path.exists(OUT) else {}

    # --redo: also re-translate what THIS script already produced. The first pass sent the
    # English alone; the merge rebuilds the bank from `out_*.json` on every tick, so simply
    # overwriting our own file replaces those lines with the panel-informed ones — nothing has
    # to be un-banked, and a key the FLEET banked is still left alone.
    redo = "--redo" in sys.argv
    # `--min-tokens 0` widens this from the token-heavy tail to EVERY remaining line: masking is
    # a no-op on a line with no tokens, and the panel is the method either way. Worth it when the
    # fleet's own rate has collapsed on the tail and this path is measurably accepting.
    minfl = 2
    if "--min-tokens" in sys.argv:
        minfl = int(sys.argv[sys.argv.index("--min-tokens") + 1])
    todo = [(k, corpus[k]) for k in corpus
            if len(STRUCT.findall(en_of(corpus[k]))) >= minfl
            and (k in have if redo else True)
            and (k not in bank or (redo and k in have))
            and (redo or k not in have)]
    # `--slice i/n`: disjoint md5-free split by position so several copies can run at once.
    # Each slice writes its OWN out file, so two processes never race on one `os.replace`
    # (the merge globs `out_*.json`, so extra files cost nothing).
    if "--slice" in sys.argv:
        i, n = (int(x) for x in sys.argv[sys.argv.index("--slice") + 1].split("/"))
        todo = [kv for j, kv in enumerate(sorted(todo)) if j % n == i]
        globals()["OUT"] = OUT.replace(".json", f"_s{i}.json")
        have = dict(json.load(open(OUT, encoding="utf-8"))) if os.path.exists(OUT) else {}
        todo = [kv for kv in todo if kv[0] not in have]
        print(f"  slice {i}/{n} -> {len(todo)} lines -> {os.path.basename(OUT)}")
    todo.sort(key=lambda kv: len(en_of(kv[1])))
    print(f"token-heavy lines {'to re-do with the panel' if redo else 'still missing'}: {len(todo)}")

    if not apply:
        for k, v in todo[:5]:
            en = en_of(v)
            m, t = mask(en)
            print(f"\n  {k}\n    raw   : {en[:100]}\n    masked: {m[:100]}\n    toks  : {t}")
        print("\n(dry run — pass --apply)")
        return

    import fleet_providers as fp
    keys = fp.load_keys(HERE)
    fleet = fp.Fleet(keys)
    print(f"providers: {[p for p, *_ in fleet.avail]}")

    ok = fail = 0
    # 🔴 PACK BY CHARACTER BUDGET, NOT BY COUNT. The tail is long-form (median 129 chars, max
    # 1,277): a fixed batch of 8 builds a prompt whose Hebrew answer cannot fit any sane
    # max_tokens, so the JSON is truncated mid-object and arrives as `raw 689ch parsed 0`. A
    # budget puts a 1,277-char catalogue entry in a batch of its OWN and still packs 8 short
    # ones together — the same lesson as the fleet's own batching.
    BUDGET, MAXLINES = 700, 8
    if "--budget" in sys.argv:      # `--budget 1` = one line per call, for the stubborn tail
        BUDGET = int(sys.argv[sys.argv.index("--budget") + 1])
    batches, cur, curlen = [], [], 0
    for kv in todo[:cap]:
        n = len(en_of(kv[1]))
        if cur and (curlen + n > BUDGET or len(cur) >= MAXLINES):
            batches.append(cur)
            cur, curlen = [], 0
        cur.append(kv)
        curlen += n
    if cur:
        batches.append(cur)
    print(f"  {len(batches)} batches (median {sorted(len(b) for b in batches)[len(batches)//2]} lines)")

    for i, sub in enumerate(batches):
        payload, tokmap = {}, {}
        for k, v in sub:
            m, t = mask(en_of(v))
            tokmap[k] = t
            # 🔴 NEW-ERA: the reference panel is masked TOO, so a token the model copies from a
            # sibling language is a marker, never a raw `~s~` it can break. 226 of the 227
            # remaining lines carry a panel (avg 5.9 languages) — translating them from the
            # English alone throws away the gender/register evidence the game already made.
            row = {"en": m}
            if REVIEW and isinstance(v, dict) and v.get("he"):
                row["he"] = mask_with(str(v["he"]), t)
            refs = v.get("refs") if isinstance(v, dict) else None
            if isinstance(refs, dict):
                vals = [str(x) for x in refs.values() if x]
                # 0.28 % of panels are ONE identical ASCII string in every language (a tiny
                # shared token like `~1~`/`+`, or a hash collision). Such a panel teaches the
                # model nothing and can only mislead — drop it, keep the English.
                collided = len(set(vals)) == 1 and vals and vals[0].isascii()
                if not collided:
                    for code, txt in refs.items():
                        if txt:
                            row[LANGNAME.get(code, code)] = mask_with(str(txt), t)
            payload[k] = row
        masked = {k: payload[k]["en"] for k, _ in sub}
        # 🔴 A REASONING model spends its thinking against `max_tokens` and leaves `content`
        # EMPTY when the budget is tight — which arrives here as `+0/8 ok=0 fail=0`, i.e.
        # indistinguishable from "the model dropped every key". A 325-token budget produced
        # exactly that while the SAME batch answered perfectly at a larger one. Budget for the
        # preamble, the long ids the model must echo verbatim, and Hebrew at ~1 token/char.
        mx = min(6000, 900 + sum(len(k) for k, _ in sub) // 2
                 + int(sum(len(masked[k]) for k, _ in sub) * 2))
        try:
            raw = fleet.complete(SYS_REV if REVIEW else SYS_ARB if ARBITRATE else SYS,
                                 "Translate:\n" + json.dumps(payload, ensure_ascii=False),
                                 retries=3, timeout=70, max_tokens=mx)
        except Exception as e:                                  # noqa: BLE001
            print(f"  [{i+1}] provider: {e}")
            continue
        mm = re.search(r"\{.*\}", raw or "", re.S)
        try:
            got = json.loads(mm.group(0)) if mm else {}
        except Exception:                                       # noqa: BLE001
            got = {}
        if not got and raw:
            # 🔴 SALVAGE A TRUNCATED REPLY. A long batch can run out of `max_tokens` mid-object;
            # `re.search(r"\{.*\}")` then finds no closing brace and the WHOLE batch is discarded —
            # seven finished translations thrown away because the eighth was cut off. Scrape the
            # complete `"key": "value"` pairs instead; each still passes the guard on its own.
            got = {k: v for k, v in re.findall(
                r'"(0x[0-9A-Fa-f]+)"\s*:\s*"((?:[^"\\]|\\.)*)"', raw)}
            got = {k: json.loads(f'"{v}"') for k, v in got.items()}
        n = 0
        for k, v in sub:
            he = got.get(k)
            # 🔴 A model MIRRORS THE INPUT SHAPE. The moment the payload became nested
            # ({key: {en, pl, de, …}} for the reference panel) the replies came back nested too
            # — 8 keys parsed, 0 usable, which the counters showed as `ok=0 fail=0`, i.e.
            # identical to "the model dropped every key". Accept either shape: from a dict, take
            # the first value that actually contains a Hebrew letter.
            if isinstance(he, dict):
                he = next((x for x in he.values() if isinstance(x, str) and HEB.search(x)), None)
            if not isinstance(he, str):
                continue
            he = unmask(he.strip(), tokmap[k])
            why = bad(en_of(v), he)
            if why:
                fail += 1
                continue
            have[k] = he
            ok += 1
            n += 1
        # Print the RAW length beside the parsed count: `raw 0 chars, parsed 0/8` names an empty
        # reasoning reply instantly, while `+0/8` alone reads as model dropout (the documented
        # trap). Only on a zero batch, so a healthy run stays quiet.
        note = "" if n else f"  [raw {len(raw or '')}ch parsed {len(got)}]"
        print(f"  [{i+1}/{len(batches)}] +{n}/{len(sub)}  ok={ok} fail={fail}{note}", flush=True)
        if n:
            tmp = f"{OUT}.{os.getpid()}.tmp"
            os.makedirs(os.path.dirname(OUT), exist_ok=True)
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(have, f, ensure_ascii=False)
            for w in (0, 0.4, 1.5):
                if w:
                    time.sleep(w)
                try:
                    os.replace(tmp, OUT)
                    break
                except OSError:
                    continue
    print(f"\ndone: {ok} translated · {fail} rejected → {os.path.basename(OUT)} ({len(have)})")


if __name__ == "__main__":
    main()
