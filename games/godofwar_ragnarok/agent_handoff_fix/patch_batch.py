import json

translations = {
    "134056": "[[S:GUNNR:vo_int9dlc_gbs_gun_s135_AttractTurnIn_200:0-1713:74286]]\nהפכת את זה לכדאי...!",
    "134057": "[[S:GUNNR:vo_int9dlc_gbs_gun_s135_AttractTurnIn_201:0-1803:75308]]\nאני רואה שהפכת את זה לכדאי...!",
    "134060": "[[S:GUNNR:vo_int9dlc_gbs_gun_s135_AttractTurnIn_204:0-1573:75311]]\nהפכת את זה לכדאי...!",
    "134110": "[[S:GUNNR:vo_int9dlc_gbs_gun_s140_GenericTurnIns_151:0-740:75316]]\nקח את זה...",
    "134521": "[[S:MIMIR:vo_int9dlc_gbs_mim_s100_GPM_WakeUpKratos_061:47-4081:78954]]\nבצד החיובי, לא איבדנו הרבה התקדמות. בוא ננסה שוב!",
    "134920": "[[S:GUNNR:vo_int9dlc_lvl_val_hub_main_s400_030_gun:78-1880:74601]]\nאני לא בטוחה בזה...",
    "134921": "[[S:SIGRUN:vo_int9dlc_lvl_val_hub_main_s400_040_sig:788-6051:74602]]\nששש. אייר יכולה לרפא אותו.",
    "134922": "[[S:EIR:vo_int9dlc_lvl_val_hub_main_s400_050_eir:0-1701:74603]]\nזה ייקח זמן.",
    "134923": "[[S:SIGRUN:vo_int9dlc_lvl_val_hub_main_s400_060_sig:0-5661:74605]]\nקדימה, קרייטוס. תחזור לשם ותעשה מה שאתה צריך לעשות.",
    "134924": "[[S:EIR:vo_int9dlc_lvl_val_hub_main_s400_070_eir:17-600:74606]]\nששש...",
    "134925": "[[S:MIMIR:vo_int9dlc_lvl_val_hub_main_s405_010_mim:60-2730:79220]]\nובכן, זה היה מפחיד לגמרי...",
    "134926": "[[S:::3150-6964:79220]]\nרגע אחד הייתי ביער, ואז מצאתי את עצמי בכלוב בוער...",
    "135098": "[[S:MIMIR:vo_int9dlc_gbs_mim_s320_MagniModiSharedBarks_080:0-2442:78115]]\nהתקרבות להילה תפגע בך!"
}

with open('current_batch.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

for key, val in translations.items():
    if key in data:
        data[key]['he'] = val

# Special case for 137887
if "137887" in data:
    ar_text = data["137887"]["ar"]
    data["137887"]["he"] = ar_text.replace("الأعداء بالداخل لا يرتقون للمعايير التي تبحث عنها...", "האויבים בפנים לא עומדים בסטנדרטים שאתה מחפש...")

with open('current_batch.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=1)

print("Updated current_batch.json")
