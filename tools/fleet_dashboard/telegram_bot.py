# -*- coding: utf-8 -*-
"""Telegram front-end for the fleet dashboard — same data as FleetDash.exe / dash.py --once,
delivered as chat messages instead of a Qt window. Zero new logic: this file only formats
and pushes what collector.py + health.py already compute.

Setup (one-time, needs the user):
  1. In Telegram, message @BotFather -> /newbot -> follow the prompts -> copy the token
     it gives you (looks like "123456789:AA...").
  2. Message your new bot ANYTHING once (so Telegram has a chat with you to reply to).
  3. Run:  python telegram_bot.py --whoami
     It prints your numeric chat_id (reads it straight from getUpdates — no BotFather step
     needed for this part).
  4. Copy tools/fleet_dashboard/telegram_config.example.json -> telegram_config.json (gitignored)
     and fill in "token" + "chat_id".
  5. Run:  python telegram_bot.py            (foreground)  or
           pythonw telegram_bot.py            (no console window, background)

Commands the bot understands (any message from an unrecognised chat_id is silently ignored —
this is a private status tool, not a public bot):
  /status            full per-stream table (same as dash.py --once), chunked to fit Telegram's
                     4096-char limit
  /findings          just the warnings/errors section
  /rdr2 /spiderman2  … (any game id present in fleet_config.json) — that game's block only
  /help

Automatic alerts: every POLL_SECONDS the bot runs the same health.check() the dashboard uses
and pushes a message ONLY for a finding that is NEW since the last alert (tracked by
scope+title so a finding that persists doesn't spam every cycle, but a genuinely new one — or
one that changed severity — does). A finding that stops appearing is silently dropped from the
tracked set (no "resolved" spam either; /status always shows the live truth).
"""
import json
import os
import sys
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import collector as C  # noqa: E402
import health as H  # noqa: E402
from dash import fmt_eta, fmt_pct, fmt_rate, load_cfg  # noqa: E402

CFG_FILE = os.path.join(HERE, "telegram_config.json")
POLL_SECONDS = 300          # how often to run a fresh health check for automatic alerts
GETUPDATES_TIMEOUT = 25     # Telegram long-poll timeout (seconds)
MAX_MSG = 3800              # stay under Telegram's 4096 hard cap with room for markdown escaping


def log_dir() -> str:
    # Real-home resolved, like collector._state_root() -- a raw LOCALAPPDATA read lands in a
    # sandboxed dev-profile path when this process is launched from inside an Antigravity
    # session, so the bot's own log silently split from the one the user (and this dashboard)
    # actually look at.
    d = os.path.join(C._real_home(), "AppData", "Local", "FleetDash")
    os.makedirs(d, exist_ok=True)
    return d


def _log(msg: str) -> None:
    line = f"{time.strftime('%F %T')}  {msg}"
    print(line)
    try:
        with open(os.path.join(log_dir(), "telegram_bot.log"), "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


def load_bot_cfg() -> dict:
    if not os.path.exists(CFG_FILE):
        raise SystemExit(
            f"{CFG_FILE} not found.\n"
            f"Copy telegram_config.example.json -> telegram_config.json and fill in "
            f"token + chat_id (see the docstring at the top of this file)."
        )
    with open(CFG_FILE, encoding="utf-8") as fh:
        cfg = json.load(fh)
    if not cfg.get("token") or "PASTE" in cfg.get("token", ""):
        raise SystemExit("telegram_config.json: 'token' is not filled in.")
    return cfg


# --------------------------------------------------------------------------- Telegram HTTP

def _api(token: str, method: str, params: dict, timeout: int = 30) -> dict:
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def send_message(token: str, chat_id, text: str) -> None:
    # split on paragraph boundaries so a table row is never cut mid-line
    chunks = []
    cur = ""
    for line in text.split("\n"):
        if len(cur) + len(line) + 1 > MAX_MSG:
            chunks.append(cur)
            cur = ""
        cur = (cur + "\n" + line) if cur else line
    if cur:
        chunks.append(cur)
    for i, chunk in enumerate(chunks):
        try:
            resp = _api(token, "sendMessage", {
                "chat_id": chat_id,
                "text": chunk if len(chunks) == 1 else f"({i + 1}/{len(chunks)})\n{chunk}",
                "disable_web_page_preview": "true",
            })
            if not resp.get("ok"):
                _log(f"sendMessage failed: {resp}")
        except Exception as e:
            _log(f"sendMessage EXC: {e}")


def get_updates(token: str, offset: int) -> list:
    try:
        resp = _api(token, "getUpdates", {
            "offset": offset, "timeout": GETUPDATES_TIMEOUT,
        }, timeout=GETUPDATES_TIMEOUT + 10)
        return resp.get("result", []) if resp.get("ok") else []
    except (urllib.error.URLError, TimeoutError, Exception) as e:
        # a long-poll timing out or a transient network blip is normal, not an error worth
        # logging every cycle — only log genuinely unexpected exception types.
        if not isinstance(e, (urllib.error.URLError, TimeoutError)):
            _log(f"getUpdates EXC: {type(e).__name__}: {e}")
        return []


# --------------------------------------------------------------------------- fleet snapshot

def collect_once(cfg: dict):
    """One collection pass, same shape dash.py's once_text() does internally."""
    hist = C.load_history()
    remote = C.probe_all(cfg)
    snap = C.collect(cfg, remote, hist)
    findings = H.check(cfg, snap, {})
    C.save_history(hist)
    return snap, findings


# emoji + Hebrew label per state/severity — the whole point is a status a human scans in 2
# seconds, in clean Hebrew, without a single English word leaking into the running text.
STATE_EMOJI = {
    "עובד": "🟢", "סיים": "🔵", "חנוק 429": "🟡",
    "איטי": "🟠", "חנוק ותקוע": "🟠",
    "תקוע": "🔴", "מת": "🔴", "כפול": "🔴", "לא נבדק": "⚪",
}
SEV_EMOJI = {"error": "🔴", "warn": "🟡", "info": "🔵"}
SEV_TEXT = {"error": "תקלה", "warn": "אזהרה", "info": "מידע"}


def _finding_line(x: dict) -> str:
    emoji = SEV_EMOJI.get(x["sev"], "⚪")
    sev = SEV_TEXT.get(x["sev"], x["sev"])
    return f"{emoji} {sev} · {x['scope']}\n   {x['title']} — {x['reason'][:100]}"


def format_status(cfg: dict, snap: dict, findings: list, only_game: str | None = None) -> str:
    th = cfg["thresholds"]
    L: list[str] = []
    for g in snap["games"]:
        if only_game and g["id"] != only_game:
            continue
        if L:
            L.append("")
        L.append(f"🎮 {g.get('title') or g['id']}")
        L.append(f"התקדמות: {g['done']:,} מתוך {g['total']:,}  "
                  f"({fmt_pct(g['done'], g['total'], g['remaining'])})")
        L.append(f"נותרו: {g['remaining']:,}   קצב: {fmt_rate(g['rate'])}   "
                  f"זמן משוער: {fmt_eta(g['remaining'], g['rate'])}")
        states = [(s, *H.stream_state(s, th)) for s in g["streams"]]
        problems = [t for t in states if t[1] not in ("עובד", "סיים")]
        ok = len(states) - len(problems)
        L.append(f"זרמים תקינים: {ok} מתוך {len(states)}")
        for s, st, why in sorted(problems, key=lambda t: t[0].get("num", 0)):
            line = f"{STATE_EMOJI.get(st, '⚪')} #{s.get('num', 0)}  {s['machine']}/{s['provider']} — {st}"
            if why:
                line += f"\n   {why[:80]}"
            L.append(line)
    if not only_game:
        L.append("")
        L.append("📋 ממצאים")
        if not findings:
            L.append("✅ אין ממצאים — הכול תקין")
        else:
            L.extend(_finding_line(x) for x in findings)
    return "\n".join(L) if L else "אין נתונים למשחק הזה."


def format_findings(findings: list) -> str:
    if not findings:
        return "✅ כל הזרמים תקינים — אין ממצאים."
    L = ["📋 ממצאים"]
    L.extend(_finding_line(x) for x in findings)
    return "\n".join(L)


# --------------------------------------------------------------------------- alert de-dup

def _finding_key(x: dict) -> str:
    return f"{x['scope']}::{x['title']}"


def load_alerted() -> set:
    p = os.path.join(log_dir(), "telegram_alerted.json")
    try:
        return set(json.load(open(p, encoding="utf-8")))
    except Exception:
        return set()


def save_alerted(s: set) -> None:
    p = os.path.join(log_dir(), "telegram_alerted.json")
    tmp = p + ".tmp"
    json.dump(sorted(s), open(tmp, "w", encoding="utf-8"))
    os.replace(tmp, p)


# --------------------------------------------------------------------------- main loop

def handle_command(cfg: dict, bot_cfg: dict, chat_id, text: str) -> None:
    text = (text or "").strip()
    game_ids = {g["id"] for g in cfg["games"]}
    if text in ("/start", "/help"):
        ids = "  ".join(f"/{i}" for i in sorted(game_ids))
        send_message(bot_cfg["token"], chat_id,
                     "🌐 בוט מעקב תרגום\n\n"
                     "/status — מצב מלא של כל המשחקים\n"
                     "/findings — רק אזהרות ותקלות\n"
                     f"{ids}\n   ↳ מצב של משחק ספציפי")
        return
    if text == "/status":
        snap, findings = collect_once(cfg)
        send_message(bot_cfg["token"], chat_id, format_status(cfg, snap, findings))
        return
    if text == "/findings":
        _snap, findings = collect_once(cfg)
        send_message(bot_cfg["token"], chat_id, format_findings(findings))
        return
    gid = text.lstrip("/").split()[0] if text.startswith("/") else ""
    if gid in game_ids:
        snap, findings = collect_once(cfg)
        send_message(bot_cfg["token"], chat_id, format_status(cfg, snap, findings, only_game=gid))
        return
    # unrecognised text from the allowed chat -> quiet nudge, not silence (silence reads as "broken")
    send_message(bot_cfg["token"], chat_id, "לא זיהיתי את הפקודה. /help לרשימה.")


def poll_commands(cfg: dict, bot_cfg: dict, offset: int) -> int:
    allowed = str(bot_cfg["chat_id"])
    for upd in get_updates(bot_cfg["token"], offset):
        offset = upd["update_id"] + 1
        msg = upd.get("message") or upd.get("edited_message") or {}
        chat = msg.get("chat", {})
        if str(chat.get("id")) != allowed:
            _log(f"ignored message from unauthorised chat_id={chat.get('id')}")
            continue
        try:
            handle_command(cfg, bot_cfg, chat["id"], msg.get("text", ""))
        except Exception:
            _log("handle_command EXC:\n" + traceback.format_exc())
    return offset


def push_new_alerts(cfg: dict, bot_cfg: dict, alerted: set) -> set:
    try:
        _snap, findings = collect_once(cfg)
    except Exception:
        _log("push_new_alerts collect EXC:\n" + traceback.format_exc())
        return alerted
    fresh = [x for x in findings if x["sev"] in ("error", "warn")]
    new_keys = {_finding_key(x) for x in fresh}
    to_send = [x for x in fresh if _finding_key(x) not in alerted]
    if to_send:
        lines = ["🔔 ממצאים חדשים"]
        lines.extend(_finding_line(x) for x in to_send)
        send_message(bot_cfg["token"], bot_cfg["chat_id"], "\n".join(lines))
    return new_keys  # replace the tracked set with "currently active" — a resolved one drops silently


def whoami(bot_cfg: dict) -> None:
    _log("send any message to your bot now, then re-run --whoami if this prints nothing...")
    upds = get_updates(bot_cfg["token"], -5)
    for u in upds:
        chat = (u.get("message") or {}).get("chat", {})
        if chat:
            print(f"chat_id = {chat.get('id')}   (name: {chat.get('first_name', '')} "
                  f"{chat.get('last_name', '')} @{chat.get('username', '')})")
    if not upds:
        print("no recent messages seen — message your bot in Telegram first, then retry.")


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    bot_cfg = load_bot_cfg()

    if "--whoami" in sys.argv:
        whoami(bot_cfg)
        return 0

    cfg = load_cfg()
    _log(f"telegram_bot started — chat_id={bot_cfg['chat_id']}, poll={POLL_SECONDS}s")
    offset = 0
    alerted = load_alerted()
    last_alert_check = 0.0
    while True:
        try:
            offset = poll_commands(cfg, bot_cfg, offset)
            if time.time() - last_alert_check >= POLL_SECONDS:
                alerted = push_new_alerts(cfg, bot_cfg, alerted)
                save_alerted(alerted)
                last_alert_check = time.time()
        except Exception:
            _log("main loop EXC:\n" + traceback.format_exc())
            time.sleep(10)


if __name__ == "__main__":
    raise SystemExit(main())
