import json

translations = {
    "Skin/CdModeNudge": "מצב CD (הזזה)",
    "Skin/ControllerLeSkin": "סקין CONTROLLER LE",
    "Skin/DropASongHereTo": "גרור שיר לכאן כדי לטעון",
    "Skin/HamsterInverted": "Hamster (הפוך)",
    "tooltips/browser_shortcut": "[ערך]",
    "tooltips/cue_button": "[ערך]",
    "tooltips/filter_label": "[ריק]",
    "tooltips/get_battery": "[ערך]",
    "tooltips/get_clock": "[ערך]",
    "tooltips/get_date": "[ערך]",
    "tooltips/pad": "[ערך]",
    "tooltips/play_button": "[ערך]",
    "tooltips/sampler_pad": "[ערך]",
    "tooltips/skin_panel": "[ריק]",
    "tooltips/stop_button": "[ערך]",
    "Actions/color": "color \"red\"\\ncolor \"#C08040\"\\ncolor 0.8 0.5 0.25\\ncolor 75% \"red\" (מחזיר אדום מעומעם)\\ncolor 0.66 (מחזיר אפור)"
}

with open('current_batch.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

for k, v in translations.items():
    if k in d:
        d[k]['he'] = v

with open('current_batch.json', 'w', encoding='utf-8') as f:
    json.dump(d, f, ensure_ascii=False, indent=1)
