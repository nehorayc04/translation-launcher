"""99_stamp_version.py <N> — stamp a visible build tag " vN" onto every settings
page header, so you can SEE in-game which build is actually loaded (the #1 way to
tell a fresh install from a stale one). Idempotent: re-running with a new N strips
the old tag first. Default N=8.

Run AFTER 91_match_arabic_structure.py and BEFORE the 10->15->80 rebuild.
"""
import json, glob, sys, re, os

N = sys.argv[1] if len(sys.argv) > 1 else "8"
HEADERS = {
    "MENU_LOBBY_COMMONSETTINGS_HEADER", "MENU_GAME_HEADER", "PAUSE_UISETTINGS_TITLE",
    "MENU_SUBTITLECAPTIONS_HEADER", "MENU_GAMEPAD_HEADER", "MENU_SHORTCUT_HEADER",
    "PAUSE_ACCESSIBILITYSETTINGS_TITLE",
}
TAG = re.compile(r'\s*v\d+\s*(?:‏|&rlm;)?\s*$')   # strip a prior " vNN" tag

cnt = 0
for fn in sorted(glob.glob("menus*_he.json")) + ["settings_he.json"]:
    if not os.path.exists(fn):
        continue
    d = json.load(open(fn, encoding="utf-8"))
    if not isinstance(d, dict):
        continue
    changed = False
    for k in HEADERS:
        if k in d and isinstance(d[k], str):
            base = TAG.sub('', d[k]).rstrip()
            d[k] = f"{base} v{N}"
            changed = True
            cnt += 1
    if changed:
        json.dump(d, open(fn, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

print(f"stamped ' v{N}' on {cnt} settings headers")
