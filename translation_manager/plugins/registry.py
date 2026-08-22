"""
plugins.registry - the plugin catalog, install state, and the DRM gate.

    available()          → the CLOUD catalog of installable plugins
    installed()          → {pid: {enabled, version, installed_at, config}}
    install(pid)         → register + enable (gated on can_use_plugins)
    remove(pid)          → unregister + let the host stop it
    set_enabled(pid, on)
    get_config(pid) / set_config(pid, cfg)
    can_use_plugins()    → True iff signed in AND owns ≥1 GAME (not software)

State lives in `~/.translation_manager/plugins/state.json`, read/written through
`resilience` so a corrupt file self-heals instead of wiping the user's plugin
setup. The catalog is fetched from the cloud (Worker slug `plugins`), with a
BUNDLED fallback definition so the feature works before the cloud is wired /
while offline - the DEFINITION is tiny metadata; nothing executable ships.
"""
from __future__ import annotations

import logging
import re
import time
from pathlib import Path
from typing import Callable

log = logging.getLogger(__name__)

_DIR   = Path.home() / ".translation_manager" / "plugins"
_STATE = _DIR / "state.json"

# The Worker slug the plugin catalog is served under (same infra as mod_source).
CATALOG_SLUG = "plugins"

# The plugin KINDS this build's host can actually run. A cloud manifest naming a
# kind we don't have is ignored (forward-compat: an older app just won't show a
# plugin that needs a newer host).
SUPPORTED_KINDS = {"save_backup", "game_copilot", "community_compute"}


# ─────────────────────────────────────────────────────────────
# The save-backup plugin's DECLARATIVE UI manifest (drawn by the launcher's
# generic renderer, driven by plugins/engine.py's audited primitives). Because
# this is DATA, the whole panel - labels/buttons/icons/layout - is editable from
# the cloud (admin site_config.plugins) with NO app rebuild. `{{field}}` binds to
# engine state; `visibleWhen`/`disabledWhen` are tiny truthiness checks; each
# button's `action` maps to an audited primitive (never downloaded code).
# ─────────────────────────────────────────────────────────────
_SAVE_BACKUP_UI = [
    {"type": "grid2", "children": [
        {"type": "field", "control": "select", "label": "מתי לגבות",
         "bind": "schedule", "optionsBind": "scheduleOptions", "action": "set_schedule"},
        {"type": "field", "control": "number", "label": "כמה גיבויים לשמור לכל משחק (0 = ללא הגבלה)",
         "bind": "keep", "min": 0, "max": 9999, "action": "set_field"},
    ]},
    {"type": "box",
     "header": {"text": "מיקום הגיבוי",
                "button": {"label": "שנה מיקום", "icon": "opt-btn-browse-folder",
                           "variant": "ghost", "action": "pick_destination"}},
     "children": [
         {"type": "text", "value": "{{destination}}", "dir": "ltr", "muted": True},
         # Only rendered when the user has actually moved off the default.
         {"type": "row", "visibleWhen": "destinationIsCustom", "children": [
             {"type": "button", "label": "איפוס לברירת המחדל",
              "icon": "opt-btn-reset", "variant": "ghost", "action": "reset_destination"},
         ]},
     ]},
    {"type": "section", "title": "שמירות שמגובות ({{entriesCount}})",
     "icon": "opt-section-backed-saves",
     "headerActions": [
         {"type": "input", "bind": "local.snapName",
          "placeholder": "שם לגיבוי (לא חובה)", "width": "160px"},
         {"type": "button", "label": "איתור אוטומטי", "busyLabel": "מאתר…",
          "icon": "app-plugins-btn-autodetect", "variant": "ghost", "action": "detect"},
         {"type": "button", "label": "גבה עכשיו", "busyLabel": "…",
          "icon": "app-plugins-btn-backup-now", "variant": "primary", "action": "backup_now",
          "args": {"name": "{{local.snapName}}"}, "disabledWhen": "!hasEntries",
          "then": {"clearLocal": ["snapName"]}},
         {"type": "button", "label": "תיקיית הגיבויים",
          "icon": "app-plugins-btn-open-folder", "variant": "ghost",
          "action": "open_backup_folder"},
     ],
     "children": [
         {"type": "text", "muted": True, "visibleWhen": "!hasEntries",
          "value": ("עוד לא נבחרו שמירות. לחצו \"איתור אוטומטי\" כדי שהתוכנה תמצא "
                    "לבד, או הוסיפו תיקייה ידנית למטה.")},
         {"type": "list", "bind": "entries", "item": {
             "text": "{{label}}", "subtext": "{{source}}",
             "editableAction": "rename_entry",
             "buttons": [
                 {"icon": "app-plugins-btn-open-folder", "variant": "icon",
                  "action": "open_folder", "args": {"path": "{{source}}"}},
                 {"label": "הסר", "icon": "opt-btn-remove-entry", "variant": "danger",
                  "action": "remove_entry", "args": {"id": "{{id}}"}},
             ]}},
     ]},
    {"type": "box", "visibleWhen": "detectedCount",
     "header": {"text": "נמצאו אוטומטית - לחצו \"הוסף\":",
                "button": {"label": "הוסף הכל", "icon": "opt-btn-add-detected",
                           "variant": "primarySm", "action": "add_all",
                           "args": {"items": {"$bind": "detected"}}}},
     "children": [
         {"type": "list", "bind": "detected", "item": {
             "text": "{{title}}", "subtext": "{{path}}", "badge": "{{confidencePct}}%",
             "buttons": [
                 {"label": "הוסף", "icon": "opt-btn-add-detected", "variant": "primarySm",
                  "action": "add_detected",
                  "args": {"game_id": "{{game_id}}", "path": "{{path}}", "label": "{{label}}"}},
             ]}},
     ]},
    {"type": "ubitree", "bind": "ubisoftAccounts", "visibleWhen": "hasUbisoft",
     "title": "יוביסופט - שמירות לפי חשבון", "icon": "opt-section-backed-saves"},
    {"type": "box", "title": "הוספת תיקייה ידנית", "children": [
        {"type": "row", "children": [
            {"type": "input", "bind": "local.manualLabel",
             "placeholder": "שם (למשל: Elden Ring)", "flex": 1},
            {"type": "input", "bind": "local.manualPath",
             "placeholder": "נתיב תיקיית השמירות", "dir": "ltr", "flex": 2},
            {"type": "button", "label": "עיון…", "icon": "opt-btn-browse-folder",
             "variant": "ghost", "action": "pick_folder",
             "then": {"setLocalFrom": {"manualPath": "path"}}},
            {"type": "button", "label": "הוסף", "variant": "primary", "action": "add_manual",
             "args": {"path": "{{local.manualPath}}", "label": "{{local.manualLabel}}"},
             "disabledWhen": "!local.manualPath",
             "then": {"clearLocal": ["manualPath", "manualLabel"]}},
        ]},
    ]},
    {"type": "section", "visibleWhen": "hasBackups",
     "title": "היסטוריית גיבויים ({{backupsCount}})", "icon": "opt-section-backup-history",
     "children": [
         {"type": "list", "bind": "backups", "maxHeight": "16rem", "item": {
             "text": "{{label}}",
             "subtext": "{{whenDisplay}} · {{files}} קבצים · {{sizeMb}} MB",
             "buttons": [
                 {"icon": "app-plugins-btn-open-folder", "variant": "icon",
                  "action": "open_folder", "args": {"path": "{{path}}"}},
                 {"label": "שחזר", "icon": "opt-btn-restore-backup", "variant": "warn",
                  "visibleWhen": "canRestore", "action": "restore",
                  "args": {"backup_path": "{{path}}", "label": "{{label}}"},
                  "confirm": "לשחזר את הגיבוי? המצב הנוכחי יגובה קודם למקרה חירום."},
             ]}},
     ]},
]


# ─────────────────────────────────────────────────────────────
# The Game Co-Pilot plugin's DECLARATIVE UI manifest. Same drawing/dispatch
# machinery as save-backup above; the audited primitives live in
# `plugins/game_copilot.py` (config only - the actual overlay window + global
# hotkey are a Qt-specific runtime, see `qt_shell/game_copilot_runtime.py`).
# ─────────────────────────────────────────────────────────────
def _game_copilot_ui() -> list[dict]:
    return [
        {"type": "box", "children": [
            {"type": "text", "value": "{{statusText}}", "muted": True},
        ]},
        {"type": "grid2", "children": [
            {"type": "field", "control": "select", "label": "ספק ה-AI",
             "bind": "provider", "optionsBind": "providerOptions", "action": "set_provider"},
            {"type": "field", "control": "select", "label": "מודל",
             "bind": "model", "optionsBind": "modelOptions", "action": "set_model"},
        ]},
        {"type": "text", "muted": True, "visibleWhen": "!modelSupportsVision",
         "value": "⚠️ המודל הזה לא תומך בניתוח תמונות - ההסבר יתבסס רק על שם המשחק, לא על מה שמוצג במסך"},
        {"type": "box", "title": "מפתח API אישי", "children": [
            {"type": "text", "muted": True, "visibleWhen": "!hasApiKey",
             "value": ("עוד לא הוגדר מפתח API. קבלו מפתח (בדרך כלל בחינם) והדביקו אותו "
                       "כאן - הוא נשמר מוצפן על המחשב שלכם בלבד, ולא נשלח לשום מקום חוץ "
                       "מהספק שבחרתם.")},
            {"type": "text", "muted": True, "visibleWhen": "hasApiKey",
             "value": "מפתח מוגדר ✓ (מוצפן על המחשב שלכם)"},
            {"type": "row", "children": [
                {"type": "input", "bind": "local.apiKey", "dir": "ltr", "flex": 1,
                 "placeholder": "הדביקו כאן את מפתח ה-API"},
                {"type": "button", "label": "שמור מפתח", "busyLabel": "שומר ובודק מול הספק…",
                 "variant": "primary", "action": "set_api_key", "args": {"key": "{{local.apiKey}}"},
                 "disabledWhen": "!local.apiKey", "then": {"clearLocal": ["apiKey"]}},
            ]},
            {"type": "row", "visibleWhen": "hasApiKey", "children": [
                {"type": "button", "label": "מחיקת המפתח", "variant": "danger",
                 "action": "clear_api_key"},
            ]},
            {"type": "row", "visibleWhen": "keyUrl", "children": [
                {"type": "button", "label": "קבלו מפתח API (בדרך כלל בחינם) ↗", "variant": "ghost",
                 "action": "open_url", "args": {"url": "{{keyUrl}}"}},
            ]},
        ]},
        {"type": "grid2", "children": [
            {"type": "box", "title": "מקש קיצור להצגה/הסתרה של החלונית", "children": [
                {"type": "text", "value": "{{hotkeyLabel}}"},
                {"type": "row", "children": [
                    {"type": "button", "label": "עריכה", "variant": "primarySm",
                     "action": "start_capture",
                     "busyLabel": "לחצו על מקש/ים או כפתור/י שלט (Esc לביטול)…"},
                    {"type": "button", "label": "איפוס לברירת מחדל", "icon": "opt-btn-reset",
                     "variant": "ghost", "action": "reset_hotkey"},
                ]},
            ]},
            {"type": "field", "control": "select",
             "label": "עמדת החלונית על המסך (או גררו את החץ שלה בלחיצה ארוכה, גם כשהיא סגורה)",
             "bind": "edge", "optionsBind": "edgeOptions", "action": "set_corner"},
            {"type": "field", "control": "select",
             "label": "מראה החלונית",
             "bind": "surface", "optionsBind": "surfaceOptions", "action": "set_surface"},
        ]},
        {"type": "row", "children": [
            {"type": "button", "label": "הצג / הסתר את החלונית עכשיו", "variant": "primary",
             "action": "toggle_overlay"},
            {"type": "button", "label": "נתחו את המסך עכשיו", "busyLabel": "מנתח…",
             "variant": "ghost", "action": "test_now", "disabledWhen": "!hasApiKey"},
        ]},
        {"type": "box", "visibleWhen": "hasLastResult", "title": "התוצאה האחרונה", "children": [
            {"type": "text", "muted": True, "value": "{{lastGame}} · {{lastAtDisplay}}"},
            {"type": "text", "visibleWhen": "lastOk", "value": "{{lastText}}"},
            {"type": "text", "visibleWhen": "!lastOk", "value": "⚠️ {{lastError}}"},
        ]},
    ]


def _community_compute_ui() -> list[dict]:
    # THREE zones, in the order a volunteer needs them:
    #   1. a hero with the ONE switch (and the status it reflects),
    #   2. the numbers, as equal tiles,
    #   3. the setup (keys) - with everything technical folded away.
    # The old layout was five identical grey boxes stacked, so the switch, the
    # numbers and the server address all read as equally important.
    return [
        {"type": "hero", "title": "{{statusText}}", "subtitle": "{{heroHint}}",
         "toggle": {"bind": "enabled", "action": "set_enabled",
                    "onLabel": "תורם", "offLabel": "כבוי",
                    "disabledWhen": "!hasKeys",
                    "blockedHint": "צריך קודם מפתח API אחד"},
         "children": [
             {"type": "button", "label": "בדיקת חיבור", "busyLabel": "בודק…",
              "variant": "ghost", "action": "test"},
         ]},

        {"type": "stats", "items": [
            {"label": "שורות שתרמת", "value": "{{linesDisplay}}", "tone": "accent",
             "caption": "{{byProviderText}}"},
            {"label": "זמן פעילות", "value": "{{uptimeDisplay}}", "caption": "{{connText}}"},
            {"label": "בעבודה כעת", "value": "{{queueDisplay}}", "caption": "{{queueCaption}}"},
        ]},

        # A CARD per provider: its own paste field, its own "get a key" button, and
        # its own step-by-step guide. The old shape was one shared field + a "ספק"
        # dropdown, so the user had to pick the provider by hand - and a mis-pick
        # silently stored a Groq key under SambaNova (a key that then always fails).
        {"type": "box", "title": "מפתחות API חינמיים", "children": [
            {"type": "text", "muted": True,
             "value": ("מפתח אחד מספיק כדי להתחיל. המפתחות נשמרים מוצפנים במחשב שלכם "
                       "ולעולם לא נשלחים לשום שרת - רק לספק שבחרתם, ישירות מהמחשב.")},
            {"type": "cards", "bind": "keyRows", "card": {
                "title": "{{label}}", "note": "{{note}}",
                "chip": "{{mark}}", "chipWhen": "has",
                "input": {"bind": "local.k_{{id}}", "dir": "ltr", "secret": True,
                          "placeholder": "הדביקו כאן את המפתח של {{label}}"},
                "steps": {"bind": "steps", "title": "איך משיגים מפתח? (שלב אחרי שלב)"},
                # RTL: the field is first in the DOM so it sits on the RIGHT, and
                # the buttons land to its LEFT. "קבלת מפתח" comes first because on
                # an empty card that is the only action a new volunteer can take.
                "buttons": [
                    {"label": "קבלת מפתח ↗", "variant": "ghost",
                     "action": "open_url", "args": {"url": "{{url}}"}},
                    {"label": "שמירה", "busyLabel": "שומר…", "variant": "primarySm",
                     "action": "set_api_key",
                     "args": {"provider": "{{id}}", "key": "{{inputValue}}"},
                     "disabledWhen": "!inputValue", "clearInput": True},
                    {"label": "הסרה", "variant": "danger", "visibleWhen": "has",
                     "confirm": "להסיר את המפתח של {{label}}?",
                     "action": "clear_api_key", "args": {"provider": "{{id}}"}},
                ]}},
        ]},

        {"type": "collapse", "title": "העברת מפתחות למחשב אחר", "children": [
            {"type": "text", "muted": True,
             "value": ("ייצוא מעתיק את המפתחות ללוח (או לקובץ) כדי להעביר אותם למחשב "
                       "או לטלפון; ייבוא קולט הדבקה, קובץ, או מפתח בודד - ומזהה לבד "
                       "לאיזה ספק הוא שייך.")},
            {"type": "row", "children": [
                {"type": "button", "label": "העתקה ללוח", "variant": "ghost",
                 "action": "export_keys", "args": {"to": "clipboard"},
                 "disabledWhen": "!hasKeys"},
                {"type": "button", "label": "שמירה לקובץ", "variant": "ghost",
                 "action": "export_keys", "args": {"to": "file"},
                 "disabledWhen": "!hasKeys"},
                {"type": "button", "label": "הדבקה מהלוח", "variant": "primarySm",
                 "busyLabel": "טוען…", "action": "import_keys",
                 "args": {"from": "clipboard"}},
                {"type": "button", "label": "טעינה מקובץ", "variant": "primarySm",
                 "action": "import_keys", "args": {"from": "file"}},
            ]},
        ]},

        {"type": "collapse", "title": "הגדרות מתקדמות", "children": [
            {"type": "text", "muted": True,
             "value": ("שרת: {{serverLabel}} · מזהה מכשיר: {{workerId}} · {{serverInfo}}. "
                       "שאר ההגדרות מגיעות מהשרת ומתעדכנות לבד.")},
            {"type": "row", "children": [
                {"type": "input", "bind": "local.base", "dir": "ltr", "flex": 2,
                 "placeholder": "כתובת שרת אחרת (ריק = ברירת המחדל)"},
                {"type": "button", "label": "החל", "variant": "primarySm",
                 "action": "set_base", "args": {"url": "{{local.base}}"},
                 "then": {"clearLocal": ["base"]}},
            ]},
        ]},
    ]



# ─────────────────────────────────────────────────────────────
# Bundled fallback catalog - the DEFINITION only (no code, no data payload).
# Used when the cloud feed is unreachable so the feature is still usable.
# ─────────────────────────────────────────────────────────────
def _bundled_catalog() -> list[dict]:
    return [
        {
            "id":          "save-backup",
            "kind":        "save_backup",
            "name":        "גיבוי אוטומטי לשמירות משחקים",
            "tagline":     "מגבה את קבצי השמירה שלך למקום בטוח - אוטומטית",
            "description": (
                "מאתר לבד היכן נשמרות שמירות המשחק (עם מנוע הזיהוי החכם של "
                "התוכנה), מאפשר גם להוסיף תיקייה ידנית, ומגבה אותן לפי לוח זמנים "
                "שתבחר: כל יום / שבוע / חודש, בכל הפעלה של המחשב, או תוך כדי משחק."
            ),
            "icon":         "💾",
            "version":      "1.0.0",
            "accent":       "#22c55e",
            "capabilities": ["detect", "entries", "backup", "restore",
                             "schedule", "picker"],
            "ui":           _SAVE_BACKUP_UI,
        },
        {
            "id":          "game-copilot",
            "kind":        "game_copilot",
            "name":        "עוזר משחק חי (AI)",
            "tagline":     "חלונית AI צפה שרואה מה קורה במשחק ומסבירה לכם בעברית מה לעשות",
            "description": (
                "פועל ברקע בזמן שמשחק פועל: בלחיצת מקש קיצור (או מכפתור כאן) נפתחת "
                "חלונית קטנה וצפה מעל המשחק. התוסף מזהה - מהתמונה על המסך ומהחלון "
                "הפעיל - באיזה משחק אתם משחקים ומה כנראה המצב/המשימה הנוכחית, שולח "
                "את זה למודל AI (לפי בחירתכם, עם מפתח API אישי משלכם) ומציג הסבר "
                "ברור בעברית: מה קורה, מה המטרה, ושלב אחרי שלב מה לעשות ולמה. "
                "לא נוגע בקבצי המשחק ולא דורש שום שינוי בהתקנה שלו."
            ),
            "icon":         "🧭",
            "version":      "1.0.0",
            "accent":       "#38bdf8",
            "capabilities": ["overlay", "hotkey", "screen_capture", "ai_analysis"],
            "ui":           _game_copilot_ui(),
        },
        {
            "id":          "community-compute",
            "kind":        "community_compute",
            "name":        "מחשוב קהילתי - תרמו כוח תרגום",
            "tagline":     "המחשב שלכם עוזר לתרגם משחקים לעברית, ברקע ובחינם",
            "description": (
                "מתנדבים תורמים כוח-תרגום לפרויקט: כשהתוסף פעיל, המחשב מושך שורות "
                "מהמאגר המשותף, מתרגם אותן עם מפתח API חינמי משלכם (Groq / SambaNova / "
                "NVIDIA NIM), ומחזיר את התוצאה. אין עלות ואין צורך בתוכנה נוספת.\n\n"
                "פרטיות: המפתחות נשמרים מוצפנים במחשב שלכם ולא נשלחים לשום שרת - רק "
                "לספק שבחרתם, ישירות מהמחשב. השרת אף פעם לא מתחבר אליכם, אלא אתם אליו, "
                "כך שכתובת ה-IP שלכם לא נחשפת. אם החיבור נופל - העבודה נאגרת ונשלחת "
                "כשהוא חוזר; אם המחשב נסגר באמצע - השורות חוזרות לתור ואף אחת לא הולכת "
                "לאיבוד. כל תרגום עובר בקרת איכות ואישור לפני שהוא נכנס למשחק."
            ),
            "icon":         "🤝",
            "version":      "1.0.0",
            "accent":       "#4ade80",
            "capabilities": ["background_worker", "byok", "pull_queue"],
            # NOT behind the purchase gate - see registry.is_free().
            "free":         True,
            "ui":           _community_compute_ui(),
        },
    ]


# ─────────────────────────────────────────────────────────────
# Cloud catalog (with the bundled fallback)
# ─────────────────────────────────────────────────────────────
# The admin-managed catalog lives in the hub site-config (`config.plugins`), so
# the maintainer controls which plugins appear + their title/description/version/
# availability from the ADMIN site with NO app rebuild (public GET, 30s-cached).
_CONFIG_URL = "https://hebrew-translation-hub.com/api/config"


def _fetch_cloud_catalog() -> list[dict] | None:
    """The plugin catalog from the admin-managed site config
    (`/api/config` → `config.plugins`), or None on any failure → the bundled
    fallback keeps the feature usable offline / before the admin seeds it."""
    try:
        import requests
        r = requests.get(_CONFIG_URL, headers={"Accept": "application/json"}, timeout=8)
        if not r.ok:
            return None
        doc = r.json()
    except Exception:                                    # pragma: no cover
        return None
    cfg = doc.get("config") if isinstance(doc, dict) else None
    plugins = cfg.get("plugins") if isinstance(cfg, dict) else None
    return plugins if isinstance(plugins, list) else None


def available() -> list[dict]:
    """The installable-plugin catalog: admin-managed cloud config first, bundled
    fallback otherwise. Only plugins whose `kind` THIS build can run are
    returned, and an admin can hide one by setting `available: false`.

    A cloud row is MERGED over the bundled entry with the same id, so a
    metadata-only cloud row still inherits the bundled `ui` manifest +
    `capabilities` (the panel renders) - while a cloud row MAY override any field,
    including shipping its OWN `ui`, which is how the plugin's UI changes with NO
    app rebuild."""
    from .. import swr_cache
    cat = swr_cache.swr("plugins", _fetch_cloud_catalog, ttl=300.0)
    bundled = {p["id"]: p for p in _bundled_catalog()}
    if not cat:
        cat = list(bundled.values())
    else:
        # A plugin that ships in THIS build but is not (yet) in the admin's cloud
        # list is still ours to show: the cloud row exists to RETUNE or HIDE a
        # plugin (`available: false`), not to be the gate on its existence. Before
        # this, a newly-shipped bundled plugin was invisible to every user with
        # working internet - the cloud fetch succeeds, and the loop below only
        # ever iterated what the cloud listed - which reads exactly like the
        # feature is broken.
        listed = {p.get("id") for p in cat if isinstance(p, dict)}
        cat = list(cat) + [b for pid, b in bundled.items() if pid not in listed]
    out = []
    for p in cat:
        if not isinstance(p, dict) or not p.get("id"):
            continue
        base = bundled.get(p["id"])
        # bundled defaults, then cloud overrides (skip None so a cloud null never
        # wipes a bundled default like the ui manifest). kind/available are read
        # from the MERGED entry so a metadata-only cloud row still resolves them.
        merged = {**base, **{k: v for k, v in p.items() if v is not None}} if base else dict(p)
        if merged.get("kind") in SUPPORTED_KINDS and merged.get("available", True) is not False:
            out.append(merged)
    return out


def by_id(pid: str) -> dict | None:
    for p in available():
        if p.get("id") == pid:
            return p
    return None


def refresh_catalog() -> bool:
    """Fetch the catalog NOW and overwrite the cache, bypassing the 300s TTL.

    Without this an admin's change (a new plugin, a hidden one, a bumped
    version) only surfaces when the SWR entry expires - and a user staring at a
    screen that "should" have changed cannot tell a slow cache from a broken
    feature. A FAILED fetch leaves the cache alone on purpose: stale-but-working
    beats blanking the list on a blip. Returns True iff the cloud answered."""
    fresh = _fetch_cloud_catalog()
    if fresh is None:
        return False
    try:
        from .. import swr_cache
        swr_cache.put("plugins", fresh)
    except Exception:                                    # pragma: no cover
        pass
    return True


def _ver_key(v: object) -> tuple:
    """Compare versions NUMERICALLY ('1.10.0' > '1.9.0'); a non-numeric tail
    sorts below the same numeric prefix so '1.2.0' beats '1.2.0-beta.1'."""
    s = str(v or "0").strip()
    nums, pre = [], 0
    for part in re.split(r"[.\-+]", s):
        if part.isdigit():
            nums.append(int(part))
        elif part:
            pre = 1                                       # any tag ⇒ pre-release
            break
    while len(nums) < 3:
        nums.append(0)
    return (*nums[:3], 0 if pre else 1)


def has_update(pid: str) -> bool:
    """True iff the CATALOG offers a newer version than the one installed."""
    meta, ent = by_id(pid), _load_state().get(pid)
    if not meta or not ent:
        return False
    return _ver_key(meta.get("version")) > _ver_key(ent.get("version"))


def update(pid: str) -> dict:
    """Adopt the catalog's current version for an INSTALLED plugin.

    A plugin's UI manifest is read live from the catalog, so labels/layout
    already update by themselves. What does NOT: the stored version stamp and
    the config, whose defaults are captured once at install - so a setting ADDED
    by a newer version is missing from the user's config and every field bound to
    it renders empty. This merges the missing defaults in WITHOUT touching a
    single value the user chose."""
    meta = by_id(pid)
    if meta is None:
        return {"ok": False, "error": "unknown-plugin"}
    state = _load_state()
    ent = state.get(pid)
    if ent is None:
        return {"ok": False, "error": "not-installed"}

    cfg = dict(ent.get("config") or {})
    added = [k for k, v in (_default_config(meta.get("kind")) or {}).items()
             if k not in cfg and (cfg.setdefault(k, v), True)[1]]
    ent["config"] = cfg
    ent["version"] = meta.get("version", ent.get("version"))
    ent["kind"] = meta.get("kind", ent.get("kind"))
    ent["updated_at"] = int(time.time())
    state[pid] = ent
    if not _save_state(state):
        return {"ok": False, "error": "state-write-failed"}
    _host_sync()
    return {"ok": True, "version": ent["version"], "addedSettings": added}


# ─────────────────────────────────────────────────────────────
# Install state (self-healing JSON)
# ─────────────────────────────────────────────────────────────
def _load_state() -> dict:
    from .. import resilience
    data = resilience.read_json(_STATE, default={}, name="plugins.state")
    return data if isinstance(data, dict) else {}


def _save_state(state: dict) -> bool:
    from .. import resilience
    return bool(resilience.write_json(_STATE, state, name="plugins.state"))


def installed() -> dict:
    """{pid: {enabled, version, installed_at, config}} for this machine."""
    return _load_state()


def is_installed(pid: str) -> bool:
    return pid in _load_state()


def is_enabled(pid: str) -> bool:
    ent = _load_state().get(pid)
    return bool(ent and ent.get("enabled"))


# ─────────────────────────────────────────────────────────────
# The DRM gate - a signed-in user who bought ≥1 GAME (not software)
# ─────────────────────────────────────────────────────────────
# Set by main_eel at import so registry stays decoupled from the RPC module.
_owns_any_game_cb: Callable[[], bool] | None = None
_signed_in_cb: Callable[[], bool] | None = None


def configure(*, owns_any_game: Callable[[], bool] | None = None,
              signed_in: Callable[[], bool] | None = None) -> None:
    global _owns_any_game_cb, _signed_in_cb
    if owns_any_game is not None:
        _owns_any_game_cb = owns_any_game
    if signed_in is not None:
        _signed_in_cb = signed_in


def can_use_plugins() -> bool:
    """True iff the user may use PAID plugins. Fails CLOSED (a network blip or
    a signed-out user simply can't turn plugins on) - but an ALREADY-installed +
    enabled plugin keeps running (see host), so a blip doesn't kill a backup."""
    if _owns_any_game_cb is None:
        return False
    try:
        return bool(_owns_any_game_cb())
    except Exception:                                    # pragma: no cover
        return False


def is_signed_in() -> bool:
    """The gate for a FREE plugin: an account, nothing more. Reads the ON-DISK
    identity cache (no network), so a blip can never lock a volunteer out of a
    plugin they are DONATING to."""
    if _signed_in_cb is None:
        return False
    try:
        return bool(_signed_in_cb())
    except Exception:                                    # pragma: no cover
        return False


def can_use(pid: str) -> bool:
    """The real gate for ONE plugin: a free plugin needs only an account."""
    return is_signed_in() if is_free(pid) else can_use_plugins()


# ─────────────────────────────────────────────────────────────
# Install / remove / enable / configure
# ─────────────────────────────────────────────────────────────
def is_free(pid: str) -> bool:
    """A plugin the user GIVES with rather than gets from is not gated.

    The purchase gate exists so paid add-ons follow the paid catalog. Applying it
    to the community-compute worker would be backwards: it asks a volunteer to
    buy a game before they are allowed to donate their own machine and their own
    API quota to the project - which would simply cost us volunteers."""
    meta = by_id(pid) or {}
    return bool(meta.get("free"))


def install(pid: str) -> dict:
    """Register + enable a plugin. Gated (unless the plugin is free)."""
    meta = by_id(pid)
    if meta is None:
        return {"ok": False, "error": "unknown-plugin"}
    if not can_use(pid):
        return {"ok": False, "error": "not-entitled",
                "message": ("התוסף הזה זמין לכל משתמש מחובר - התחברו לחשבון."
                            if meta.get("free") else
                            "התוספים זמינים למשתמש מחובר שרכש לפחות משחק אחד.")}

    state = _load_state()
    ent = state.get(pid) or {}
    ent.update({
        "enabled":      True,
        "version":      meta.get("version", "1.0.0"),
        "kind":         meta.get("kind"),
        "installed_at": ent.get("installed_at") or int(time.time()),
    })
    ent.setdefault("config", _default_config(meta.get("kind")))
    state[pid] = ent
    if not _save_state(state):
        return {"ok": False, "error": "state-write-failed"}

    _host_sync()
    return {"ok": True}


def remove(pid: str) -> dict:
    """Unregister a plugin (stops its background work). Keeps nothing running."""
    state = _load_state()
    if pid in state:
        del state[pid]
        _save_state(state)
    _host_sync()
    return {"ok": True}


def set_enabled(pid: str, enabled: bool) -> dict:
    if enabled and not can_use(pid):
        return {"ok": False, "error": "not-entitled"}
    state = _load_state()
    ent = state.get(pid)
    if ent is None:
        # Enabling a not-yet-installed plugin installs it first.
        if enabled:
            return install(pid)
        return {"ok": True}
    ent["enabled"] = bool(enabled)
    _save_state(state)
    _host_sync()
    return {"ok": True}


def get_config(pid: str) -> dict:
    ent = _load_state().get(pid) or {}
    return ent.get("config") or {}


def set_config(pid: str, config: dict) -> dict:
    if not isinstance(config, dict):
        return {"ok": False, "error": "bad-config"}
    state = _load_state()
    ent = state.get(pid)
    if ent is None:
        return {"ok": False, "error": "not-installed"}
    ent["config"] = config
    if not _save_state(state):
        return {"ok": False, "error": "state-write-failed"}
    _host_sync()
    return {"ok": True}


def patch_config(pid: str, patch: dict) -> dict:
    """Merge ``patch`` onto the LATEST on-disk config for ``pid`` - never the
    caller's own, possibly-stale, in-memory snapshot.

    `set_config` above does a full-object REPLACE with whatever dict the
    caller passes - correct for a quick UI action, where read-then-write is
    one fast round trip so nothing else can change the config in between.
    It is UNSAFE for a caller that reads the config, then does something
    SLOW (a multi-second AI call, a 30s hotkey-capture wait, a network
    request) before writing back: if something else changes an UNRELATED
    key in that window (e.g. the user picks a different provider while a
    game_copilot analysis is still running), the slow caller's eventual
    write-back silently reverts it, because its local dict still carries
    the STALE value for every key it never touched itself - a classic
    lost-update. `patch_config` closes that: only the keys named in `patch`
    are applied, on top of whatever the config looks like RIGHT NOW, so a
    concurrent change to any OTHER key can never be clobbered by a late
    write-back that was only ever trying to update its own few fields."""
    if not isinstance(patch, dict):
        return {"ok": False, "error": "bad-config"}
    state = _load_state()
    ent = state.get(pid)
    if ent is None:
        return {"ok": False, "error": "not-installed"}
    cur = dict(ent.get("config") or {})
    cur.update(patch)
    ent["config"] = cur
    if not _save_state(state):
        return {"ok": False, "error": "state-write-failed"}
    _host_sync()
    return {"ok": True}


def patch_nested(pid: str, key: str, sub_patch: dict) -> dict:
    """Like `patch_config`, one level deeper: merge `sub_patch` onto whatever
    `config[key]` (itself a dict) looks like RIGHT NOW - leaving every other
    top-level field, AND every other sub-key of `key`, untouched.

    Built for save_backup's per-entry `last`-run map: a scheduled or manual
    backup run can take minutes (real disk copies, one per entry), and during
    that window a DIFFERENT concurrent run (a "back up now" for other
    entries, or another scheduled tick) can legitimately update OTHER entry
    ids under that same `last` key. A flat `patch_config(pid, {key: value})`
    would still replace the whole sub-dict wholesale and lose that
    concurrent write - this merges one level in, so only the ids actually
    named in `sub_patch` move."""
    if not isinstance(sub_patch, dict):
        return {"ok": False, "error": "bad-config"}
    state = _load_state()
    ent = state.get(pid)
    if ent is None:
        return {"ok": False, "error": "not-installed"}
    cur = dict(ent.get("config") or {})
    inner = dict(cur.get(key) or {})
    inner.update(sub_patch)
    cur[key] = inner
    ent["config"] = cur
    if not _save_state(state):
        return {"ok": False, "error": "state-write-failed"}
    _host_sync()
    return {"ok": True}


def _default_config(kind: str | None) -> dict:
    if kind == "save_backup":
        from . import save_backup
        return save_backup.default_config()
    if kind == "game_copilot":
        from . import game_copilot
        return game_copilot.default_config()
    if kind == "community_compute":
        from . import community_compute
        return community_compute.default_config()
    return {}


# ─────────────────────────────────────────────────────────────
# Host coupling (the runtime that actually does the background work)
# ─────────────────────────────────────────────────────────────
def _host_sync() -> None:
    """Tell the host that install-state changed so it can start/stop work.
    Best-effort - never raises, and the host is optional (e.g. in tests)."""
    try:
        from . import host
        host.sync()
    except Exception:                                    # pragma: no cover
        pass


def snapshot() -> dict:
    """One call the UI reads: the catalog + install-state + the DRM gate,
    merged, so the Plugins tab renders in a single round-trip."""
    inst = _load_state()
    entitled = can_use_plugins()
    signed = is_signed_in()
    cat = []
    for meta in available():
        pid = meta["id"]
        ent = inst.get(pid) or {}
        # `free` + `usable` travel WITH each card: the gate is per plugin now, so a
        # single global `entitled` flag can no longer decide whether the install
        # button works (that mismatch is what locked the free plugin in the UI even
        # though install() would have allowed it).
        installed = pid in inst
        cat.append({
            **meta,
            "installed": installed,
            "enabled":   bool(ent.get("enabled")),
            "free":      bool(meta.get("free")),
            "usable":    signed if meta.get("free") else entitled,
            # An update is a CATALOG fact - it needs no new app code, because the
            # UI manifest is already read live. What it carries is the version
            # stamp + any config default a newer version added.
            "installedVersion": ent.get("version") if installed else None,
            "updateAvailable":  bool(installed and
                                     _ver_key(meta.get("version")) > _ver_key(ent.get("version"))),
        })
    return {"entitled": entitled, "signedIn": signed, "plugins": cat}
