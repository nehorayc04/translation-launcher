"""dev_overlay.py — live preview of the Game Co-Pilot overlay.

Runs ONLY the overlay panel, on the REAL desktop, with the REAL DWM
Acrylic backdrop. No launcher build, no installer, no UAC.

    .venv\\Scripts\\python.exe dev_overlay.py

Edit ``translation_manager/qt_shell/game_copilot_runtime.py`` and this
restarts itself within a second — a paint tweak becomes visible in ~2s
instead of a ~10-minute build+install cycle. That loop is the whole
point of the file: the panel's look can only be judged on a real screen
over real content, and an offscreen pixel test cannot do it.

The small control window cycles every state (dock edge, collapse,
loading / answer / error, short vs long text) so all of them can be
checked without touching code.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # repo root (this script lives in scripts/)
SRC = ROOT / "translation_manager" / "qt_shell" / "game_copilot_runtime.py"
# The overlay's whole look is now CSS, so editing the page must restart the
# child too - otherwise the fast loop only covers half the design.
PAGE = ROOT / "translation_manager" / "qt_shell" / "copilot_overlay.html"
SELF = Path(__file__).resolve()
RESTART_CODE = 42

SHORT = (
    "🎮 אתה במשימה הראשית בליל סיטי\n"
    "📍 המפה מראה יעד מסומן בצפון-מזרח\n"
    "🎯 לך ליעד ודבר עם ג'קי\n"
)

# Deliberately long - full paragraphs, ~50 lines. A three-line answer proves
# nothing about the scroll area, the wrap, or how the panel reads when the
# model actually explains something; this is the worst realistic case.
LONG = (
    "🎮 אתה במסך שדרוגי הסייברוור אצל ויקטור ורקטור, הריפרדוק שמתחת לבניין שלך\n"
    "בליטל צ'יינה. זה אחד המסכים שתחזור אליו הכי הרבה פעמים במשחק, אז שווה\n"
    "להבין אותו לעומק פעם אחת במקום לנחש בכל ביקור.\n"
    "\n"
    "📍 המסך מחולק לשלושה אזורים. בצד ימין רשימת חלקי הגוף - ראש, מערכת הפעלה,\n"
    "שלד, מערכת החיסון, מערכת העצבים, זרועות, רגליים. בכל חלק יש מספר חריצים,\n"
    "וכל חריץ יכול להחזיק שתל אחד בלבד. במרכז מופיעים השתלים שזמינים לחלק שבחרת,\n"
    "ובצד שמאל התצוגה המקדימה עם המחיר, דרישת הרמה ודרישות התכונות.\n"
    "\n"
    "🎯 המטרה שלך עכשיו: לשדרג את מערכת ההפעלה כדי לפתוח עוד חריצי תוכנות פריצה.\n"
    "מערכת ההפעלה היא הבסיס לכל הפריצה במשחק - היא קובעת כמה תוכנות אתה יכול\n"
    "להעלות בו-זמנית, כמה RAM עומד לרשותך, ובאיזו מהירות הוא מתמלא מחדש.\n"
    "\n"
    "📋 1. בחר את הקטגוריה 'מערכת הפעלה' ברשימה שבצד ימין. שים לב שהמערכת\n"
    "הנוכחית שלך מסומנת ומופיעה למעלה, מעל האפשרויות שניתן לקנות.\n"
    "\n"
    "2. השווה בין הדגמים. שלושת המספרים שחשובים באמת הם: כמות חריצי התוכנות,\n"
    "כמות ה-RAM, וזמן ההתאוששות. דגם עם הרבה חריצים אבל מעט RAM ייתקע לך\n"
    "באמצע קרב, ודגם עם הרבה RAM ומעט חריצים יגביל אותך לשתיים-שלוש תוכנות.\n"
    "האיזון הנכון תלוי בסגנון המשחק שלך.\n"
    "\n"
    "3. בדוק את דרישת הרמה ואת דרישת התכונה. רוב המערכות המתקדמות דורשות\n"
    "אינטליגנציה גבוהה, ואם עוד לא הגעת לסף פשוט לא תוכל להתקין אותן - הכפתור\n"
    "יופיע אפור עם הסבר קצר מתחתיו.\n"
    "\n"
    "4. ודא שיש לך מספיק אדי-דולר לפני האישור. המחירים כאן קופצים מהר, ואם\n"
    "תישאר בלי כסף אחרי השדרוג לא יישאר לך לתחמושת או לרכיבים.\n"
    "\n"
    "5. אשר את ההתקנה. תראה אנימציה קצרה של ההרדמה, ואחריה תחזור למסך עם\n"
    "המערכת החדשה מותקנת. זה לא הפיך בחינם - החלפה חוזרת עולה שוב.\n"
    "\n"
    "6. פתח את התפריט המהיר ובדוק את רשימת תוכנות הפריצה. החריצים החדשים\n"
    "מופיעים ריקים, ואתה צריך לשבץ בהם תוכנות ידנית - הן לא נכנסות לבד.\n"
    "\n"
    "💡 טיפים שחוסכים זמן וכסף:\n"
    "\n"
    "• שדרוג מערכת ההפעלה משפיע גם על נזק הפריצה, לא רק על כמות התוכנות.\n"
    "כדאי לעשות אותו לפני קרב גדול או לפני משימה עם הרבה אויבים מרושתים.\n"
    "\n"
    "• תוכנות אולטימטיביות תופסות חריץ שלם ודורשות הרבה RAM, אבל הן מסיימות\n"
    "קרב שלם בלחיצה אחת. שווה להשאיר להן מקום.\n"
    "\n"
    "• אם אתה משחק בסגנון חשאי, העדף מערכת עם התאוששות RAM מהירה על פני\n"
    "מערכת עם הרבה חריצים - תשתמש באותן שתיים-שלוש תוכנות שוב ושוב.\n"
    "\n"
    "• יש ריפרדוקים נוספים בכל אזור במפה, וחלקם מוכרים דגמים שוויקטור לא\n"
    "מחזיק. אם משהו ברשימה נראה חלש מדי, שווה לבדוק אצל אחר לפני שקונים.\n"
    "\n"
    "• אחרי כל שדרוג משמעותי כדאי לחזור לתפריט התכונות. שדרוגים מסוימים\n"
    "פותחים פרקים חדשים בעץ הכישורים שלא היו זמינים קודם.\n"
)


def _watch_and_run() -> int:
    """Parent process: keep a child alive, restart it when a source file
    changes. The child signals a wanted restart with RESTART_CODE."""
    while True:
        rc = subprocess.call([sys.executable, str(SELF), "--child"])
        if rc != RESTART_CODE:
            return rc
        print("[dev_overlay] source changed — restarting", flush=True)


def _child() -> int:
    sys.path.insert(0, str(ROOT))

    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtWidgets import (
        QApplication,
        QGridLayout,
        QLabel,
        QPushButton,
        QVBoxLayout,
        QWidget,
    )

    from translation_manager.qt_shell import game_copilot_runtime as gcr

    app = QApplication.instance() or QApplication(sys.argv)

    panel = gcr._OverlayPanel(on_close=lambda: None, on_refresh=lambda: None)
    panel.set_hotkey_label("Ctrl+Shift+G")
    panel.set_content("Cyberpunk 2077", SHORT)
    panel.show_animated()

    # ---- control window (a normal, focusable window) -------------------
    ctl = QWidget()
    ctl.setWindowTitle("Co-Pilot — תצוגה חיה")
    ctl.setWindowFlag(Qt.WindowStaysOnTopHint, True)
    ctl.setStyleSheet(
        "QWidget{background:#14161f;color:#e8ecf8;font-family:'Segoe UI';font-size:12px}"
    )
    lay = QVBoxLayout(ctl)
    lay.setContentsMargins(12, 12, 12, 12)
    lay.setSpacing(8)
    lay.addWidget(QLabel("עריכת game_copilot_runtime.py → רענון אוטומטי"))

    grid = QGridLayout()
    grid.setSpacing(6)
    lay.addLayout(grid)

    def add(row: int, col: int, text: str, fn) -> None:
        b = QPushButton(text)
        b.setMinimumHeight(28)
        b.setStyleSheet(
            "QPushButton{background:#252a38;color:#e8ecf8;border:1px solid #3a4256;"
            "border-radius:6px;padding:4px 10px}"
            "QPushButton:hover{background:#2f3648}"
        )
        b.clicked.connect(fn)
        grid.addWidget(b, row, col)

    add(0, 0, "◀ שמאל", lambda: panel.set_edge("left", 0.5))
    add(0, 1, "ימין ▶", lambda: panel.set_edge("right", 0.5))
    add(0, 2, "▲ למעלה", lambda: panel.set_edge("top", 0.5))
    add(0, 3, "▼ למטה", lambda: panel.set_edge("bottom", 0.5))

    add(1, 0, "כיווץ/פתיחה", panel._toggle_collapsed)
    add(1, 1, "טקסט קצר", lambda: panel.set_content("Cyberpunk 2077", SHORT))
    add(1, 2, "טקסט ארוך", lambda: panel.set_content("Cyberpunk 2077", LONG))
    add(1, 3, "טוען…", lambda: panel.set_loading("Elden Ring"))

    add(2, 0, "שגיאה", lambda: panel.set_error(
        "המפתח נדחה — Gemini: API key not valid. Please pass a valid API key."))
    add(2, 1, "הסתר", panel.hide_animated)
    add(2, 2, "הצג", panel.show_animated)
    add(2, 3, "יציאה", app.quit)

    ctl.resize(520, 150)
    ctl.move(60, 60)
    ctl.show()

    # ---- source watcher -----------------------------------------------
    watched = {p: p.stat().st_mtime for p in (SRC, PAGE, SELF) if p.exists()}

    def _poll() -> None:
        for p, was in watched.items():
            try:
                now = p.stat().st_mtime
            except OSError:
                continue
            if now != was:
                app.exit(RESTART_CODE)
                return

    t = QTimer()
    t.timeout.connect(_poll)
    t.start(500)

    if "--selftest" in sys.argv:
        QTimer.singleShot(400, lambda: app.exit(0))

    return app.exec()


if __name__ == "__main__":
    sys.exit(_child() if "--child" in sys.argv or "--selftest" in sys.argv
             else _watch_and_run())
