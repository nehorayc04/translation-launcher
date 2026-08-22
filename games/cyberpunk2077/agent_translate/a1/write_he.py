import json

data = {
    "onscreens/onscreens.json|20139": {"f": "Eva Cole", "m": "Eva Cole"},
    "onscreens/onscreens.json|22030": {"f": "Preset 4", "m": "Preset 4"},
    "onscreens/onscreens.json|27491": {"f": "WNS News", "m": "WNS News"},
    "onscreens/onscreens.json|43811": {"f": "Mat Duda", "m": "Mat Duda"},
    "onscreens/onscreens_final.json|44006": {"f": "Asa Risu", "m": "Asa Risu"},
    "onscreens/onscreens_final.json|49902": {"f": "N54 News", "m": "N54 News"},
    "onscreens/onscreens_final.json|49942": {"f": "Jiro Oba", "m": "Jiro Oba"},
    "onscreens/onscreens_final.json|71918": {"f": "Mary Ann", "m": "Mary Ann"},
    "onscreens/onscreens_final.json|77696": {"f": "Solo Set", "m": "Solo Set"},
    "onscreens/onscreens_final.json|78393": {"f": "Jam Sesh", "m": "Jam Sesh"},
    "onscreens/onscreens_final.json|83283": {"f": "Take Off", "m": "Take Off"},
    "onscreens/onscreens_final.json|96250": {"f": "The Hunt", "m": "The Hunt"},
    "onscreens/onscreens_final.json|97003": {"f": "Mob Boss", "m": "Mob Boss"},
    "subtitles/open_world/passenger/thepassenger.json|4550924115854127104": {"f": "יאלה נו.", "m": "יאלה נו."},
    "subtitles/open_world/scenes/hey_spr_chat_009.json|1832676858104766464": {"f": "עדיין לא.", "m": "עדיין לא."},
    "subtitles/open_world/scenes/wbr_nok_chat_002.json|1978243987740659712": {"f": "כן, אני.", "m": "כן, אני."},
    "subtitles/open_world/street_stories/sts_std_arr_12_diner_scene.json|1508372319725596672": {"f": "זה אני.", "m": "זה אני."},
    "subtitles/open_world/voicesets/civ_low_f_114_car_30.json|1949189022034206724": {"f": "שלום לך.", "m": "שלום לך."},
    "subtitles/open_world/voicesets/civ_low_f_31_enus_15_sml.json|1949184078878728196": {"f": "אלוהים!", "m": "אלוהים!"},
    "subtitles/open_world/voicesets/civ_low_m_01_enus_15_sml.json|1922615250492334084": {"f": "תפסיקי!", "m": "תפסיק!"}
}

with open("current_batch_he.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=1)
print("written")
