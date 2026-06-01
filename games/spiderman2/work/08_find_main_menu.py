"""Narrow the search to the *actual* main menu — short Arabic strings whose key
matches MAINMENU/TITLE_SCREEN/NEW_GAME/CONTINUE/EXIT/QUIT/LOAD/SAVE words.
Then dump the short-list to main_menu_candidates.tsv for hand-translation."""
import os, json

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
WORK = os.path.join(ROOT, "games", "spiderman2", "work")
ARABIC = json.load(open(os.path.join(WORK, "arabic.json"), "r", encoding="utf-8"))
print(f"[+] loaded {len(ARABIC)} entries")

# Tier-1: exact-prefix matches that almost certainly are main menu
EXACT_PREFIXES = (
    "MAINMENU_", "MAIN_MENU_", "TITLE_SCREEN_", "STARTSCREEN_", "TITLE_",
    "NEW_GAME", "CONTINUE_GAME", "RESUME_", "LOAD_GAME", "QUIT_GAME",
    "EXIT_GAME", "EXIT_TO_DESKTOP", "RETURN_TO_DESKTOP", "RETURN_TO_TITLE",
    "PRESS_ANY", "PRESS_START", "PRESS_TO_", "STORY_MODE",
    "PAUSEMENU_", "PAUSE_MENU_", "PAUSEMODE_",
    "FRONTEND_", "BOOTFLOW_", "STARTFLOW_",
)

# Tier-2: contains these tokens (broader)
TOKENS = ("NEWGAME","STARTGAME","RESUMEGAME","CONTINUEGAME","LOADGAME","QUITGAME",
          "EXITGAME","SAVEGAME","SETTINGS_MAIN","MAINMENU","TITLE_SCREEN")

tier1 = {k: v for k, v in ARABIC.items() if any(k.upper().startswith(p) for p in EXACT_PREFIXES)}
tier2 = {k: v for k, v in ARABIC.items()
         if k not in tier1 and any(t in k.upper() for t in TOKENS)}

# Tier-3: ALL very short Arabic strings (<=20 chars) whose key includes BTN/BUTTON/LABEL
def is_short_ar(s):
    return s and len(s) <= 20 and any('؀' <= c <= 'ۿ' for c in s)

tier3 = {k: v for k, v in ARABIC.items()
         if k not in tier1 and k not in tier2
         and any(tok in k.upper() for tok in ("BTN_","BUTTON_","LABEL_","LBL_"))
         and is_short_ar(v)}

print(f"[+] tier1 (strict main-menu prefixes): {len(tier1)}")
print(f"[+] tier2 (token contains):            {len(tier2)}")
print(f"[+] tier3 (BTN/BUTTON + short Arabic): {len(tier3)}")

def show(name, d, n=None):
    print()
    print(f"=== {name} ({len(d)} entries{', showing all' if n is None or len(d)<=n else f', first {n}'}) ===")
    items = list(d.items())[:n] if n else list(d.items())
    for k, v in items:
        print(f"  {k:<55}  {v}")

show("TIER 1", tier1)
show("TIER 2 — first 40", tier2, 40)
show("TIER 3 — first 30", tier3, 30)

# Dump candidates for hand-translation
out = os.path.join(WORK, "main_menu_candidates.tsv")
with open(out, "w", encoding="utf-8") as f:
    f.write("tier\tkey\tarabic_original\thebrew_translation\n")
    for k, v in tier1.items():
        f.write(f"1\t{k}\t{v}\t\n")
    for k, v in tier2.items():
        f.write(f"2\t{k}\t{v}\t\n")
print()
print(f"[+] candidates → {out}  (tier1+tier2 = {len(tier1)+len(tier2)} rows)")
