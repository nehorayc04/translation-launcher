# -*- coding: utf-8 -*-
"""The Witcher 3: Wild Hunt - Hebrew translation.  Interactive installer (plain terminal).

Started by the double-click launcher (התקנה.bat) or directly:  python install_console.py
A simple text menu opens - paste the game folder, then choose [1] install / [2] remove.

Hidden automation modes (self-test only):
    install_console.py --check            "<game>"
    install_console.py --selftest-install "<game>"
    install_console.py --selftest-revert  "<game>"
"""
import os
import sys

import install as core

BAR = "=" * 60


def pr(s=""):
    """Print a line, pre-reversed so Hebrew reads correctly in a non-BiDi console."""
    print(core.vis(str(s)))


# ----------------------------------------------------------------- automation hooks (raw, no BiDi)
def _headless():
    args = sys.argv[1:]
    if not args or args[0] not in ("--check", "--selftest-install", "--selftest-revert"):
        return False
    mode = args[0]
    rest = [a for a in args[1:] if not a.startswith("-")]
    game = rest[0] if rest else (core.find_game(args) or "")
    out_path = os.environ.get("W3_SELFTEST_OUT")
    fh = open(out_path, "w", encoding="utf-8") if out_path else None
    emit = (lambda m: (fh.write(str(m) + "\n"), fh.flush())) if fh else print
    try:
        if mode == "--check":
            ok, why = core.validate_game(game)
            emit("VALID" if ok else f"INVALID: {why}")
            import json
            man = json.load(open(os.path.join(core.DATA, "w3strings", "manifest.json"), encoding="utf-8"))
            emit(f"data ok: {len(man)} w3strings entries reachable from {core.DATA}")
        elif mode == "--selftest-install":
            core.install(game, log=emit)
        elif mode == "--selftest-revert":
            core.revert(game, log=emit)
    finally:
        if fh:
            fh.close()
    return True


# ----------------------------------------------------------------- interactive console
def _ask_path():
    pr()
    pr("הדבק את נתיב תיקיית המשחק ולחץ Enter.")
    pr("זו תיקיית השורש של המשחק - זו שמכילה בתוכה את content.")
    pr("לדוגמה:")
    print("  C:\\Program Files (x86)\\Steam\\steamapps\\common\\The Witcher 3")
    while True:
        raw = input(core.vis("\nנתיב המשחק: ")).strip().strip('"').strip()
        if not raw:
            pr("  לא הוזן נתיב. נסה שוב, או סגור את החלון כדי לצאת.")
            continue
        game = os.path.normpath(raw)
        ok, why = core.validate_game(game)
        if ok:
            return game
        pr(f"  נתיב לא תקין: {why}")


def _menu(game):
    while True:
        pr()
        print(BAR)
        print("  " + game)
        print(BAR)
        pr("  1. התקנת התרגום לעברית")
        pr("  2. הסרת התרגום - חזרה למקורי")
        pr("  3. בחירת נתיב אחר")
        pr("  0. יציאה")
        choice = input(core.vis("\n  בחירה: ")).strip()
        if choice == "1":
            _run("install", game)
        elif choice == "2":
            ans = input(core.vis("  להסיר ולחזור למקורי? הקש כן/y ואז Enter: ")).strip().lower()
            if ans in ("כן", "כ", "y", "yes"):
                _run("revert", game)
            else:
                pr("  בוטל.")
        elif choice == "3":
            return "again"
        elif choice == "0":
            return "quit"
        else:
            pr("  בחירה לא מוכרת. הקש 1, 2, 3 או 0.")


def _run(action, game):
    pr()
    pr("  ודא שהמשחק סגור לגמרי.")
    print("  " + "-" * 56)
    try:
        if action == "install":
            core.install(game)                     # core prints its own (pre-reversed) progress
            pr("")
            pr("  *** ההתקנה הושלמה! ***")
            pr("  במשחק בחר:")
            print("     Options -> Language -> Text = Hebrew")
        else:
            core.revert(game)
            pr("")
            pr("  *** התרגום הוסר. המשחק חזר למצב המקורי. ***")
    except PermissionError:
        pr("")
        pr("  שגיאה: קובץ נעול - כנראה המשחק פתוח. סגור אותו ונסה שוב.")
    except Exception as ex:                         # noqa: BLE001
        pr("")
        pr(f"  שגיאה: {ex}")
        import traceback
        traceback.print_exc()


def _run_console():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    try:
        os.system("")                               # enable ANSI/UTF-8 on legacy consoles
    except Exception:
        pass
    print(BAR)
    print("  The Witcher 3: Wild Hunt")
    pr("  תרגום מלא לעברית - המכשף 3: ציד פראי")
    print(BAR)
    pr("  כ-97,000 שורות: תפריטים, משימות, דיאלוגים, כתוביות, ספרים.")
    pr("  חשוב: המשחק חייב להיות סגור בזמן ההתקנה או ההסרה.")
    while True:
        game = _ask_path()
        if _menu(game) == "quit":
            break
    pr("\nלהתראות.")


if __name__ == "__main__":
    if not _headless():
        try:
            _run_console()
        except (KeyboardInterrupt, EOFError):
            pass
        try:
            input(core.vis("\nלחץ Enter כדי לסגור..."))
        except Exception:
            pass
