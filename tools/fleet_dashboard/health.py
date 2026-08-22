# -*- coding: utf-8 -*-
"""Health rules for the fleet dashboard. Every finding carries the REASON, not just a colour.

Design rule learned the hard way on this fleet: an alive-check and a productivity-check answer
different questions, and BOTH are needed. A worker can be alive and banking nothing (rate-limited,
stalled, or holding a corpus it already finished), and a MISSING worker can be perfectly healthy
(it printed ALL DONE and exited). So each rule states what it measured and what it concluded.
"""
from __future__ import annotations

import re

ERROR, WARN, INFO = "error", "warn", "info"
_429 = re.compile(r"429|Too Many Requests")
_TRACE = re.compile(r"Traceback|Exception|Error(?! 429)|refused|SSLError", re.I)
_DONE = re.compile(r"ALL DONE")


def _tail_reason(tail: list[str]) -> str:
    if not tail:
        return "הלוג ריק"
    if any(_DONE.search(t) for t in tail):
        return "הלוג מסתיים ב-ALL DONE"
    thr = sum(1 for t in tail if _429.search(t))
    if thr >= 2:
        return f"{thr} שורות 429 רצופות (חניקת ספק)"
    if thr and _429.search(tail[-1]):
        return "השורה האחרונה בלוג היא 429 (חניקת ספק)"
    for t in reversed(tail):
        if _TRACE.search(t):
            return f"שגיאה בלוג: {t.strip()[:120]}"
    return f"שורה אחרונה בלוג: {tail[-1].strip()[:120]}"


def _throttled(tail: list[str], th: dict) -> bool:
    """A provider is throttling us if the tail is full of 429s **or simply ENDS on one** — the
    worker prints one 429 line per refused batch, so a stream that just got refused has a single
    matching line. Requiring N lines raised a red ERROR ("stuck, no evidence of 429") on streams
    whose very last log line was `HTTP Error 429` — a false alarm on the most common state there is.
    """
    if not tail:
        return False
    n = sum(1 for t in tail if _429.search(t))
    return n >= th["throttle_lines"] or bool(_429.search(tail[-1]))


def _fmt_age(sec: float) -> str:
    if sec is None or sec < 0:
        return "לא ידוע"
    if sec < 90:
        return f"{int(sec)} ש'"
    if sec < 5400:
        return f"{int(sec / 60)} דק'"
    return f"{sec / 3600:.1f} שע'"


def stream_state(s: dict, th: dict) -> tuple[str, str]:
    """(state, reason) for one stream — the single label the table shows."""
    if not s["probe_ok"]:
        # A failed ssh probe says nothing about the WORK. The bank is local evidence and outranks
        # it: if the stream banked lines inside the rate window, it is producing — the machine is
        # merely too loaded to answer in time (the same trap that once looked like a hung guest).
        why = f"הבדיקה נכשלה: {s.get('probe_error') or 'אין תשובה'}"
        if s.get("rate"):
            return "עובד", why + " — אבל הבנק זז בחלון, כלומר הזרם מייצר; המכונה פשוט עמוסה"
        return "לא נבדק", why
    tail = s["tail"]
    if s["alive"] == 0:
        if s["remaining"] == 0:
            return "סיים", "המנה הושלמה והתהליך יצא כמתוכנן"
        return "מת", _tail_reason(tail)
    if s["alive"] > 1:
        return "כפול", f"{s['alive']} תהליכים לאותו ספק — ה-lock לא תפס"
    age = s["out_age"]
    throttled = _throttled(tail, th)
    if s["remaining"] > 0 and age is not None and age >= 0:
        if age > th["stall_minutes"] * 60:
            # Same distinction the findings make, so the table label and the warning agree: a stall
            # whose log is all 429s is the provider throttling us, not something to go fix.
            lbl = "חנוק ותקוע" if throttled else "תקוע"
            return lbl, f"קובץ הפלט לא זז {_fmt_age(age)} · {_tail_reason(tail)}"
        if age > th["slow_minutes"] * 60:
            return "איטי", f"קובץ הפלט לא זז {_fmt_age(age)} · {_tail_reason(tail)}"
    if throttled:
        return "חנוק 429", "הספק מחזיר 429 — הצי ממשיך דרך שאר הספקים"
    # POOL MODE: alive, not throttled — and yet the queue has not heard from it for a full
    # lease. Labelling that "עובד" is the false-reassurance this panel exists to prevent: it
    # is neither claiming nor submitting, and the lines it holds are about to be re-served.
    if s.get("pool_missing"):
        return "לא מדווח", "התהליך חי אך המאגר לא שמע ממנו יותר מ-20 דק' (משך ה-lease)"
    if s["remaining"] == 0:
        return "סיים", "המנה הושלמה"
    return "עובד", ""


def check(cfg: dict, snap: dict, strikes: dict) -> list[dict]:
    """All findings, most severe first. `strikes` persists unreachable counts between ticks."""
    th = cfg["thresholds"]
    f: list[dict] = []

    def add(sev, scope, title, reason, action=""):
        f.append({"sev": sev, "scope": scope, "title": title, "reason": reason, "action": action})

    # ---- per stream
    for s in snap["streams"]:
        # The number leads, so a finding can be quoted as "#7" without spelling out the triple.
        who = f"#{s.get('num', 0)} · {s['game']} · {s['machine']} · {s['provider']}"
        st, reason = stream_state(s, th)
        if st == "מת":
            add(ERROR, who, "זרם מת", reason,
                f"schtasks /run /tn <task> על {s['machine']} (או run3.bat מקומי)")
        elif st == "חנוק ותקוע":
            # The fleet is designed to keep going through the other two providers, so this is a
            # WARN: nothing to fix, but you should see it.
            add(WARN, who, "זרם חנוק ולא מתקדם", reason,
                "לא נדרשת פעולה — הספק מגביל; אם זה נמשך שעות, לשקול להעביר את המנה לספק אחר")
        elif st == "תקוע":
            add(ERROR, who, "זרם תקוע", reason,
                "לבדוק את הלוג; אין עדות ל-429 — להרוג ולהשיק מחדש דרך ה-task")
        elif st == "איטי":
            add(WARN, who, "זרם איטי", reason, "לרוב חניקת ספק — לעקוב, לא לגעת")
        elif st == "כפול":
            add(WARN, who, "כפילות תהליך", reason, "להרוג את העודף (PID-lock לא תפס)")
        elif st == "חנוק 429":
            add(INFO, who, "חניקת ספק (429)", reason)
        # community-compute streams have NO local corpus file at all by design (they pull
        # lines from the Supabase queue) - collector.collect_cc always stamps corpus_bytes=0
        # for them, which is not a fallback signal here, just the honest absence of a
        # concept that doesn't apply to this worker shape. Skip, same as the per-machine
        # loop below already does via g.get("cc").
        # A POOL client has no corpus file either — it pulls every line from the queue, so
        # the absence is the design, not a fallback to the old md5%3 split.
        if (s["probe_ok"] and s["corpus_bytes"] == 0
                and s.get("kind") != "community" and not s.get("pool")):
            add(ERROR, who, "חסר קובץ מנה",
                "corpus_<provider>.json לא קיים על המכונה — ה-worker חזר לחלוקת md5%3 הישנה",
                "להעביר מחדש את המנה (fleet_reslice_equal.py + scp)")
        # POOL MODE's own silent failure: the process is up but the queue has not heard from
        # it for a full lease, so it is neither claiming nor submitting. Invisible to every
        # other check — the process is alive and its log may look normal.
        if s.get("pool") and s.get("pool_missing") and s["alive"] == 1:
            add(WARN, who, "חי אך לא מדווח למאגר",
                "התהליך רץ, אבל המאגר לא שמע ממנו יותר מ-20 דק' (משך ה-lease) — הוא לא מושך "
                "ולא מגיש שורות",
                "לבדוק את הלוג; אם הוא תקוע בקריאה לספק — להרוג ולהשיק דרך ה-task")
        if (s["probe_ok"] and s["alive"] == 1 and s["remaining"] > 0
                and s["rate"] is not None and s["rate"] == 0):
            add(WARN, who, "אפס תפוקה בחלון",
                f"חי, אבל 0 שורות בבנק בחלון של {cfg['refresh']['rate_window_minutes']} דק' · "
                f"{_tail_reason(s['tail'])}")

    # ---- per machine
    for g in snap["games"]:
        if g.get("cc"):        # community-compute pilot: no NIM-fleet machines to probe
            continue
        for m in g["machines"]:
            who = f"{g['id']} · {m['name']}"
            pr = m.get("probe") or {}
            if not pr.get("ok"):
                k = f"{g['id']}:{m['name']}"
                strikes[k] = strikes.get(k, 0) + 1
                n = strikes[k]
                sev = ERROR if n >= th["unreachable_strikes"] else WARN
                add(sev, who, f"המכונה לא נענתה ({n} פעמים רצוף)",
                    f"{pr.get('error') or 'אין תשובה'} — שים לב: עומס גבוה יכול לגרום לאיחור "
                    f"בתשובת ssh; זה לא בהכרח guest תקוע",
                    "אם חוזר: בדיקה עם timeout ארוך, ורק אז power-cycle")
                continue
            strikes[f"{g['id']}:{m['name']}"] = 0
            if pr.get("legacy", 0):
                add(ERROR, who, "worker legacy משכפל עבודה",
                    f"{pr['legacy']} תהליכים של {g['worker']}.py בלי ארגומנט ספק — קוראים את כל "
                    f"ה-corpus בלי חלוקה וכותבים out.json ללא סיומת",
                    "להרוג אותם ולהשיק דרך ה-task; לוודא שה-heal מתוקן")
            for z in (pr.get("zombies") or []):
                add(WARN, who, "worker של פרויקט שסיים",
                    f"{str(z)[:150]} — גוזל את אותן מכסות API של הצי החי",
                    "להרוג + להשבית את ה-*Boot task שלו")
            fg = pr.get("free_gb")
            if fg is not None and fg < th["disk_free_gb"]:
                add(WARN, who, "מעט מקום בכונן",
                    f"{fg} GB פנויים — כתיבה שנכשלת קופאת בשקט ומחזירה מדדים אפס",
                    "לפנות מקום")
            tsk = pr.get("task")
            if m.get("no_task"):
                tsk = None            # by design: this machine is healed locally, not by a task
            if tsk and tsk not in ("Ready", "Running"):
                add(WARN, who, "task ההשקה לא זמין",
                    f"{g['task']} במצב {tsk} — אין מי שיחזיר זרם שמת",
                    f"schtasks /change /tn {g['task']} /enable")
            vm = m.get("vm")
            if vm and snap.get("vbox") and vm not in snap["vbox"]:
                add(ERROR, who, "ה-VM לא רץ", f"VirtualBox לא מדווח על '{vm}' כרץ",
                    f'VBoxManage startvm "{vm}" --type headless')

    # ---- per game
    for g in snap["games"]:
        if g.get("cc"):        # community pilot has no pull/merge/pusher of the NIM-fleet shape
            continue
        who = g["id"]
        # POOL MODE has no banks, no merge and no shards by construction: every answer goes
        # straight to the queue. Running the bank rules there produces three guaranteed false
        # findings ("no banks found", "merge frozen", "duplicate work") on a perfectly healthy
        # fleet — the exact kind of noise that trains you to ignore the panel.
        if not g.get("pool"):
            if g["corrupt"]:
                add(ERROR, who, "בנק פגום",
                    "קבצים שלא נפרסים (חשד ל-NUL אחרי power-cycle): " + ", ".join(g["corrupt"][:4]),
                    "להעביר הצידה כ-.corrupt ולתת ל-pull להביא מחדש")
            cad = g["pull_cadence"] * 60
            age = g.get("merge_age", -1)
            if age is None or age < 0:
                add(WARN, who, "לא נמצאו בנקים", "אין קבצי בנק לחישוב טריות המיזוג", "לבדוק את ה-pull")
            elif age > cad * 2.5:
                add(ERROR, who, "המיזוג (pull) קפוא",
                    f"אף בנק לא עודכן {_fmt_age(age)} (קצב מתוכנן: כל {g['pull_cadence']} דק') — "
                    f"עבודה שהושלמה נערמת על המכונות ולא נכנסת לבנקים",
                    "להריץ את pull_*.sh ידנית ולבדוק את ה-scheduled task")
            if g["rows"] and g["dupes"] > 0.15 * g["rows"]:
                add(WARN, who, "עבודה כפולה בבנקים (מצטבר)",
                    f"{g['dupes']:,} מתוך {g['rows']:,} שורות בבנקים הן ביקורת שנעשתה יותר מפעם אחת "
                    f"({g['dupes'] / g['rows'] * 100:.0f}%). זהו נתון היסטורי — הוא לא נמחק אחרי reslice, "
                    f"אבל אם הוא ממשיך לגדול סימן שהפרוסות חופפות שוב",
                    "לבדוק שכל זרם קורא corpus_<provider>.json ולא md5%3")
        pushers = [c for c in (snap["local"].get("pushers") or []) if g["pusher_match"] in str(c)]
        if len(pushers) == 0:
            add(WARN, who, "ה-pusher לא רץ",
                "אין תהליך שמזרים את ההתקדמות לאתר — הדשבורד באתר יקפא",
                "ה-pull מחזיר אותו לבד בריצה הבאה")
        elif len(pushers) > 1:
            add(ERROR, who, f"{len(pushers)} pushers במקביל",
                "כל אחד מוסיף דגימות לאותו קובץ היסטוריה — חלון הקצב באתר יקרא 0/שעה על צי בריא",
                "להשאיר את הראשון ולהרוג את השאר")
        if g["remaining"] > 0 and g["rate"] is not None and g["rate"] == 0:
            add(ERROR, who, "אפס תפוקה למשחק",
                f"0 שורות בחלון של {cfg['refresh']['rate_window_minutes']} דק' עם "
                f"{g['remaining']:,} שורות פתוחות", "לבדוק את הזרמים למעלה")

    order = {ERROR: 0, WARN: 1, INFO: 2}
    f.sort(key=lambda x: order[x["sev"]])
    return f
