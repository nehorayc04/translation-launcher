#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""orchestrate.py — מרכז השליטה של תרגום המשחקים.

CLI דק (stdlib בלבד) שמנהל את לוח המצב המרכזי. state.json הוא מקור האמת;
games.json הוא רישום הניתוב לכל משחק. אל תערוך את MISSION.md ידנית.

פקודות:
  board               מייצר מחדש את MISSION.md מתוך state.json
  status              מדפיס טבלה קומפקטית לטרמינל (וגם מרענן את MISSION.md)
  next                מדפיס את הצעדים הכי כדאיים עכשיו (מנוע ה"הצעות")
  game <id>           מציג מצב + ניתוב מלא של משחק אחד
  set <t> <f> <v>     מעדכן שדה של משחק / launcher
  slots <game> <N>    מייצר N קבצי SLOT לתרגום מקבילי + רושם משימה + מצביעים
  dispatch <g> <t> .. רושם משימה פעילה + מצביעים (ידני)
  clear-dispatch      מנקה את המשימה הפעילה
  doctor              בודק תקינות: state↔games↔דיסק
  help                רשימת הפקודות
"""
import sys
import json
import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # gotcha — UTF-8 stdout
except Exception:
    pass

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
STATE = HERE / "state.json"
GAMES = HERE / "games.json"
BOARD = HERE / "MISSION.md"
ACTIVE = HERE / "active"

PHASE_HE = {
    "groundwork": "🧱 קרקע",
    "translating": "🌍 מתרגם",
    "qa": "🔎 ביקורת",
    "building": "🔨 בונה",
    "shipped": "✅ פורסם",
    "maintenance": "🛠 תחזוקה",
    "beta": "🧪 בטא",
}
PHASE_ORDER = {"building": 0, "translating": 1, "qa": 2, "groundwork": 3,
               "maintenance": 4, "beta": 5, "shipped": 6}
TASK_PHASE = {"translate": "translating", "qa": "qa", "build": "building"}


def load():
    return json.loads(STATE.read_text(encoding="utf-8"))


def load_games():
    return json.loads(GAMES.read_text(encoding="utf-8")).get("games", {})


def save(d):
    d["updated"] = datetime.datetime.now().isoformat(timespec="seconds")
    tmp = STATE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(STATE)  # atomic


def fmt_phase(p):
    return PHASE_HE.get(p, p or "—")


def fmt_prog(p):
    return f"{p}%" if isinstance(p, (int, float)) else (p or "—")


def sorted_games(d):
    items = list(d.get("games", {}).items())
    items.sort(key=lambda kv: (PHASE_ORDER.get(kv[1].get("phase"), 9), kv[0]))
    return items


def render_board(d):
    games = d.get("games", {})
    L = []
    L.append("# 🎛 MISSION — לוח מצב תרגום המשחקים")
    L.append("")
    L.append(f"_נוצר מ-`state.json` · עודכן: {d.get('updated', '—')}_")
    L.append("")
    # summary line
    counts = {}
    for g in games.values():
        counts[g.get("phase")] = counts.get(g.get("phase"), 0) + 1
    summ = " · ".join(f"{fmt_phase(p)} {n}" for p, n in
                      sorted(counts.items(), key=lambda x: PHASE_ORDER.get(x[0], 9)))
    L.append(f"**{len(games)} משחקים:** {summ}")
    L.append("")
    L.append("> אל תערוך קובץ זה ידנית — נוצר ע\"י `python orchestration/orchestrate.py board`.")
    L.append("")

    disp = d.get("dispatch")
    if disp and disp.get("game"):
        L.append("## 🚀 משימה פעילה כעת")
        L.append("")
        L.append(f"**{disp.get('game')}** · {disp.get('task')} · {len(disp.get('pointers', []))} סוכנים")
        L.append("")
        L.append("שורות מצביע להדבקה (אחת לכל סוכן):")
        L.append("")
        for i, p in enumerate(disp.get("pointers", []), 1):
            L.append(f"{i}. `קרא {p} ובצע לפי ההוראות עד 'All done'`")
        L.append("")

    L.append("## 🎮 משחקים")
    L.append("")
    L.append("| משחק | שלב | התקדמות | סוכנים | גרסה | הצעד הבא |")
    L.append("|---|---|---:|---:|---|---|")
    for gid, g in sorted_games(d):
        gate = f" 🔒{g['gate']}" if g.get("gate") else ""
        ag = g.get("agents", 0) or "—"
        L.append(
            f"| **{gid}**<br><sub>{g.get('title', '')}</sub> "
            f"| {fmt_phase(g.get('phase'))} | {fmt_prog(g.get('progress'))} "
            f"| {ag} | {g.get('version', '—')} | {g.get('next', '—')}{gate} |"
        )
    L.append("")

    l = d.get("launcher")
    if l:
        L.append("## 🖥 לאנצ'ר")
        L.append("")
        L.append(f"- שלב: {fmt_phase(l.get('phase'))} · גרסה: {l.get('version', '—')} · הצעד הבא: {l.get('next', '—')}")
        if l.get("notes"):
            L.append(f"- {l['notes']}")
        L.append("")

    props = [(gid, g) for gid, g in sorted_games(d) if g.get("next") and g["next"] != "—"]
    if l and l.get("next") and l["next"] != "—":
        props.append(("launcher", l))
    if props:
        L.append("## 👉 הצעות לצעד הבא (ממתינות לאישורך)")
        L.append("")
        for gid, g in props:
            gate = f"  ⚠️ דורש אישור: {g['gate']}" if g.get("gate") else ""
            L.append(f"- **{gid}**: {g['next']}{gate}")
        L.append("")

    L.append("---")
    L.append("_🔒 = דורש אישור מפורש לפני ביצוע (פרסום / שיגור לאנצ'ר / דריסת קבצי משחק)._")
    return "\n".join(L) + "\n"


def write_board(d):
    BOARD.write_text(render_board(d), encoding="utf-8")


# ---------- commands ----------

def cmd_board(args):
    d = load()
    write_board(d)
    print(f"✓ MISSION.md עודכן ({len(d.get('games', {}))} משחקים)")


def cmd_status(args):
    d = load()
    write_board(d)
    print("לוח מצב — תרגום משחקים\n" + "=" * 44)
    for gid, g in sorted_games(d):
        ag = f" · {g['agents']} סוכנים" if g.get("agents") else ""
        gate = f" 🔒{g['gate']}" if g.get("gate") else ""
        print(f"{gid:18} {fmt_phase(g.get('phase')):11} {fmt_prog(g.get('progress')):>6}{ag} → {g.get('next', '—')}{gate}")
    disp = d.get("dispatch")
    if disp and disp.get("game"):
        print("-" * 44)
        print(f"פעיל: {disp['game']} / {disp['task']} / {len(disp.get('pointers', []))} סוכנים")


def cmd_next(args):
    d = load()
    rows = [(gid, g) for gid, g in sorted_games(d) if g.get("next") and g["next"] != "—"]
    l = d.get("launcher")
    if l and l.get("next") and l["next"] != "—":
        rows.append(("launcher", l))
    if not rows:
        print("אין צעד פתוח — הכול במצב יציב. תן פקודה (תרגם/בקר <game> <N>).")
        return
    print("👉 הצעות לצעד הבא:\n")
    for i, (gid, g) in enumerate(rows, 1):
        gate = f"   ⚠️ דורש אישור: {g['gate']}" if g.get("gate") else ""
        print(f"{i}. {gid}: {g['next']}{gate}")


def cmd_game(args):
    if not args:
        sys.exit("שימוש: game <id>")
    gid = args[0]
    d = load()
    cfg = load_games().get(gid, {})
    st = d.get("games", {}).get(gid, {})
    if not cfg and not st:
        sys.exit(f"לא נמצא משחק: {gid}")
    print(f"=== {gid} — {st.get('title') or cfg.get('title', '')} ===")
    print(f"שלב: {fmt_phase(st.get('phase'))} · התקדמות: {fmt_prog(st.get('progress'))} · "
          f"גרסה: {st.get('version', '—')} · סוכנים: {st.get('agents', 0)}")
    print(f"הצעד הבא: {st.get('next', '—')}")
    print("-" * 44)
    for k in ("engine", "repo", "slug", "release_tag", "translate_handoff",
              "translate_handoff_subs", "qa_handoff", "qa_engine", "publish", "build_doc"):
        if cfg.get(k):
            print(f"{k:22} {cfg[k]}")
    if cfg.get("notes"):
        print(f"\nהערות: {cfg['notes']}")


def cmd_set(args):
    if len(args) < 3:
        sys.exit("שימוש: set <game|launcher> <field> <value>")
    target, field, value = args[0], args[1], " ".join(args[2:])
    if field in ("progress", "agents"):
        try:
            value = int(value)
        except ValueError:
            pass
    if value == "null":
        value = None
    d = load()
    node = d["launcher"] if target == "launcher" else d["games"].get(target)
    if node is None:
        sys.exit(f"לא נמצא יעד: {target}")
    node[field] = value
    save(d)
    write_board(d)
    print(f"✓ {target}.{field} = {value}")


def cmd_slots(args):
    if len(args) < 2:
        sys.exit("שימוש: slots <game> <N>")
    gid, n = args[0], int(args[1])
    cfg = load_games().get(gid)
    if not cfg:
        sys.exit(f"לא נמצא משחק ב-games.json: {gid}")
    hd = cfg.get("translate_handoff")
    if not hd:
        sys.exit(f"ל-{gid} אין translate_handoff מקבילי. לביקורת השתמש ב-qa_handoff/prep_agents.py.")
    instr = f"{hd}/INSTRUCTIONS.md"
    par = cfg.get("parallel")  # מאומת per-game (None = נופלים ל-INSTRUCTIONS.md)
    out_dir = ACTIVE / gid
    out_dir.mkdir(parents=True, exist_ok=True)
    pointers = []
    for k in range(1, n + 1):
        slot = k - 1  # 0-based partition index
        if par:
            fill = par.get("fill", "current_batch_{slot}.json").format(slot=slot, n=n)
            steps = (
                f"לולאה עד **\"All done!\"**:\n"
                f"1. `{par['get'].format(slot=slot, n=n)}`  → כותב את המנה שלך ({fill})\n"
                f"2. תרגם בקובץ {fill} כל ערך לעברית — שמור tokens בדיוק.\n"
                f"3. `{par['merge'].format(slot=slot, n=n)}`  → ממזג + בודק מבנה (hebrew_{slot}.json).\n"
                f"4. חזור ל-1 עד \"All done!\".\n"
            )
        else:
            steps = (
                f"בצע את **לולאת התרגום המקבילי שב-INSTRUCTIONS.md** כשהסלוט שלך = {slot} "
                f"ומספר הסוכנים = {n}. חזור עד \"All done!\".\n"
            )
        body = (
            f"# SLOT {k}/{n} — {cfg.get('title', gid)} · תרגום מקבילי\n\n"
            f"אתה סוכן **{k} מתוך {n}**. עבוד אך ורק על המנה שלך (חלוקת md5 — אפס התנגשות עם השאר).\n\n"
            f"{steps}\n"
            f"⚠️ אל תתרגם שם/קוד שאין לו מילה אנגלית אמיתית — השאר כמו שהוא.\n"
            f"⚠️ אל תזייף \"done\" עם אנגלית — המיזוג דוחה ומחזיר את אותה מנה.\n\n"
            f"ההנחיות המלאות + הכללים + המילון: `{instr}`\n"
        )
        f = out_dir / f"SLOT_{k}.md"
        f.write_text(body, encoding="utf-8")
        pointers.append(f"orchestration/active/{gid}/SLOT_{k}.md")
    d = load()
    d["dispatch"] = {"game": gid, "task": "translate", "agents": n, "pointers": pointers}
    if gid in d["games"]:
        d["games"][gid]["agents"] = n
        d["games"][gid]["phase"] = "translating"
    save(d)
    write_board(d)
    print(f"✓ נוצרו {n} סלוטים ל-{gid}. שורות מצביע להדבקה (אחת לכל סוכן):\n")
    for i, p in enumerate(pointers, 1):
        print(f"{i}. קרא {p} ובצע עד 'All done'")


def cmd_dispatch(args):
    if len(args) < 3:
        sys.exit("שימוש: dispatch <game> <task> <pointer1> [pointer2 ...]")
    game, task = args[0], args[1]
    pointers = args[2:]
    d = load()
    d["dispatch"] = {"game": game, "task": task, "agents": len(pointers), "pointers": pointers}
    if game in d["games"]:
        d["games"][game]["agents"] = len(pointers)
        if task in TASK_PHASE:
            d["games"][game]["phase"] = TASK_PHASE[task]
    save(d)
    write_board(d)
    print(f"✓ משימה פעילה: {game}/{task} · {len(pointers)} סוכנים")
    for i, p in enumerate(pointers, 1):
        print(f"  {i}. קרא {p} ובצע עד 'All done'")


def cmd_clear_dispatch(args):
    d = load()
    g = (d.get("dispatch") or {}).get("game")
    d["dispatch"] = None
    if g and g in d["games"]:
        d["games"][g]["agents"] = 0
    save(d)
    write_board(d)
    print("✓ המשימה הפעילה נוקתה")


def cmd_doctor(args):
    problems, oks = [], 0
    try:
        d = load()
        oks += 1
    except Exception as e:
        sys.exit(f"✗ state.json לא נטען: {e}")
    try:
        games = load_games()
        oks += 1
    except Exception as e:
        sys.exit(f"✗ games.json לא נטען: {e}")
    sg, cg = set(d.get("games", {})), set(games)
    for g in sg - cg:
        problems.append(f"משחק ב-state.json בלי רישום ב-games.json: {g}")
    for g in cg - sg:
        problems.append(f"משחק ב-games.json בלי מצב ב-state.json: {g}")
    for gid, cfg in games.items():
        for key in ("translate_handoff", "translate_handoff_subs", "qa_handoff", "publish"):
            p = cfg.get(key)
            if p and not p.startswith(("universal/", "CLAUDE.md")) and not (REPO / p).exists():
                problems.append(f"{gid}.{key} מצביע לנתיב שלא קיים: {p}")
    if not problems:
        print(f"✓ הכול תקין ({len(games)} משחקים, state↔games↔דיסק מסונכרנים)")
    else:
        print(f"נמצאו {len(problems)} בעיות:")
        for p in problems:
            print(f"  ✗ {p}")


GAME_BOOT = (
    "עידן חדש: קרא orchestration/DOCTRINE.md + README.md + COMMANDS.md + RULES.md, והרץ\n"
    "python orchestration/orchestrate.py game {gid}. מעכשיו אתה הסשן הממוקד של {gid}\n"
    "תחת המוח המרכזי (MAX): פועל לפי האמנה, מעדכן את state.json דרך orchestrate.py\n"
    "כשמשתנה מצב, כפוף ל-3 השערים (פרסום/לאנצ'ר/קבצי משחק), לא סומך על \"done\" של סוכן,\n"
    "מאציל תרגום לסוכני Gemini. סכם את מצב {gid} מהלוח והצע את הצעד הבא."
)
LAUNCHER_BOOT = (
    "עידן חדש: קרא orchestration/DOCTRINE.md + README.md + COMMANDS.md + RULES.md, והרץ\n"
    "python orchestration/orchestrate.py status. מעכשיו אתה הסשן הממוקד של \"תוכנה ואתר\"\n"
    "(הלאנצ'ר + website/) תחת המוח המרכזי (MAX): פועל לפי האמנה, מעדכן את שורת ה-launcher\n"
    "ב-state.json דרך orchestrate.py set launcher ..., וכפוף לשערים — שיגור לאנצ'ר\n"
    "(build_exe.bat → publish_release) ופריסת אתר (vercel --prod) דורשים אישור מפורש.\n"
    "לא סומך על \"done\", מאמת בהרצה. סכם את מצב הלאנצ'ר+אתר והצע את הצעד הבא."
)


def cmd_boot(args):
    games = load_games()
    L = ["# 🚀 BOOT — שורות אתחול לכל צ'אט (העידן החדש)", "",
         "_נוצר ע\"י `python orchestration/orchestrate.py boot`. הדבק את הבלוק של הצ'אט "
         "הרלוונטי כדי לסנכרן אותו לאמנה ולמוח המרכזי._", "",
         "**צ'אט חדש בפרויקט לא צריך שום דבר** — הוא טוען לבד את CLAUDE.md + הזיכרון. "
         "הבלוקים האלה הם רק לצ'אט שכבר פתוח.", "",
         "> כלל זהב: **משחק אחד = צ'אט פעיל אחד.** רק המוח המרכזי (MAX) מנתב חוצה-משחקים.", ""]
    for gid in sorted(games):
        title = games[gid].get("title", gid)
        L += [f"## {gid} — {title}", "", "```", GAME_BOOT.format(gid=gid), "```", ""]
    L += ["## תוכנה ואתר (הלאנצ'ר + website/)", "", "```", LAUNCHER_BOOT, "```", ""]
    (HERE / "BOOT.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"✓ BOOT.md נוצר ({len(games)} משחקים + תוכנה ואתר)")


def cmd_help(args):
    print(__doc__)


CMDS = {
    "board": cmd_board, "status": cmd_status, "next": cmd_next, "game": cmd_game,
    "set": cmd_set, "slots": cmd_slots, "dispatch": cmd_dispatch,
    "clear-dispatch": cmd_clear_dispatch, "boot": cmd_boot, "doctor": cmd_doctor,
    "help": cmd_help,
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in CMDS:
        sys.exit("פקודות: " + " | ".join(CMDS))
    CMDS[sys.argv[1]](sys.argv[2:])


if __name__ == "__main__":
    main()
