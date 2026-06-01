"""Pull ALL MENU_LOBBY_*, MENU_PAUSE_*, MAIN_HUB_*, MENU_SETTINGS_*  + the
canonical short BTN_* keys. This gives the actual main-menu UI surface for
the test translation."""
import os, json

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
WORK = os.path.join(ROOT, "games", "spiderman2", "work")
ARABIC = json.load(open(os.path.join(WORK, "arabic.json"), "r", encoding="utf-8"))

def all_with_prefix(prefix):
    return {k: v for k, v in ARABIC.items() if k.startswith(prefix)}

for pref in ("MENU_LOBBY_", "MENU_PAUSE_", "MENU_SETTINGS_", "MAIN_HUB_", "FRONTEND_", "STARTSCREEN_",
             "MAIN_MENU_", "MENU_MAIN_", "MENU_LANGUAGE_", "MENU_AUDIO_", "MENU_DISPLAY_",
             "MENU_CREDITS_", "MENU_OPTIONS_", "MENU_OPTION_"):
    d = all_with_prefix(pref)
    print(f"\n=== {pref}* ({len(d)} entries) ===")
    for k, v in list(d.items())[:25]:
        print(f"  {k:<55}  {v}")
    if len(d) > 25:
        print(f"   ... +{len(d)-25} more")

# Also: short string single-words that are very likely menu items
print("\n=== short, single-word Arabic values for very common BTN_* keys ===")
common_btns = [
    "BTN_ACCEPT","BTN_CANCEL","BTN_CLOSE","BTN_CONTINUE","BTN_MENU_BACK",
    "BTN_MENU_SELECT","BTN_APPLY_CHANGES","BTN_APPLYANDRELOAD",
    "BTN_COLLAPSEALL","BTN_EXPANDALL","BTN_PHOTO_HIDEUI",
]
for k in common_btns:
    if k in ARABIC:
        print(f"  {k:<55}  {ARABIC[k]}")
