import json

updates = {
 "134123": "[[S:ODIN:vo_int9_cbt_bntr_odn_att_blast_ice_005:440-1920:67182]]\nאיספרנגיה!",
 "134124": "[[S:ODIN:vo_int9_cbt_bntr_odn_att_blast_ice_006:490-1850:67183]]\nאיספרנגיה!",
 "134125": "[[S:ODIN:vo_int9_cbt_bntr_odn_att_spear_shot_001:70-780:54794]]\nלייפטרה!",
 "134126": "[[S:ODIN:vo_int9_cbt_bntr_odn_att_spear_shot_002:70-950:67184]]\nלייפטרה!",
 "134127": "[[S:ODIN:vo_int9_cbt_bntr_odn_att_spear_shot_003:60-810:67185]]\nלייפטרה!",
 "134128": "[[S:ODIN:vo_int9_cbt_bntr_odn_att_spear_shot_004:96-983:67186]]\nלייפטרה!",
 "134129": "[[S:ODIN:vo_int9_cbt_bntr_odn_att_spear_shot_005:87-966:67187]]\nלייפטרה!",
 "134133": "[[S:ODIN:vo_int9_cbt_bntr_odn_att_raven_group_001:30-600:54800]]\nדריפה!",
 "134134": "[[S:ODIN:vo_int9_cbt_bntr_odn_att_raven_group_002:94-544:67190]]\nדריפה!",
 "134135": "[[S:ODIN:vo_int9_cbt_bntr_odn_att_raven_group_003:94-778:67191]]\nדריפה!",
 "134136": "[[S:ODIN:vo_int9_cbt_bntr_odn_att_raven_group_004:30-620:67192]]\nדריפה!",
 "134137": "[[S:ODIN:vo_int9_cbt_bntr_odn_att_raven_group_005:99-571:67193]]\nדריפה!",
 "134138": "[[S:ODIN:vo_int9_cbt_bntr_odn_att_fire_beam_001:50-620:54803]]\nסוויד'ה!",
 "134139": "[[S:ODIN:vo_int9_cbt_bntr_odn_att_fire_beam_002:60-560:67194]]\nסוויד'ה!",
 "134140": "[[S:ODIN:vo_int9_cbt_bntr_odn_att_fire_beam_003:60-740:67195]]\nסוויד'ה!",
 "134141": "[[S:ODIN:vo_int9_cbt_bntr_odn_att_fire_beam_004:60-610:67196]]\nסוויד'ה!",
 "134142": "[[S:ODIN:vo_int9_cbt_bntr_odn_att_fire_beam_005:40-760:67197]]\nסוויד'ה!",
 "134143": "[[S:ODIN:vo_int9_cbt_bntr_odn_att_fire_beam_006:60-830:67198]]\nסוויד'ה!",
 "134149": "[[S:ODIN:vo_int9_cbt_bntr_odn_att_rain_ice_001:94-1163:65352]]\nדיניה איס!",
 "134150": "[[S:ODIN:vo_int9_cbt_bntr_odn_att_rain_ice_002:70-1330:67203]]\nדיניה איס!",
 "134151": "[[S:ODIN:vo_int9_cbt_bntr_odn_att_rain_ice_003:90-1540:67204]]\nדיניה איס!",
 "134152": "[[S:ODIN:vo_int9_cbt_bntr_odn_att_rain_ice_004:94-1269:67205]]\nדיניה איס!",
 "134153": "[[S:ODIN:vo_int9_cbt_bntr_odn_att_rain_ice_005:94-1583:67206]]\nדיניה איס!",
 "134154": "[[S:ODIN:vo_int9_cbt_bntr_odn_att_rain_ice_006:95-1631:67207]]\nדיניה איס!",
 "134165": "[[S:ODIN:vo_int9_cbt_bntr_odn_armor_ice_001:95-1730:65360]]\nהרנסקיה איס!",
 "134166": "[[S:ODIN:vo_int9_cbt_bntr_odn_armor_ice_002:98-2031:67216]]\nהרנסקיה איס!",
 "134167": "[[S:ODIN:vo_int9_cbt_bntr_odn_armor_ice_003:96-2028:67217]]\nהרנסקיה איס!",
 "134168": "[[S:ODIN:vo_int9_cbt_bntr_odn_armor_ice_004:96-2384:67218]]\nהרנסקיה איס!",
 "134169": "[[S:ODIN:vo_int9_cbt_bntr_odn_armor_ice_005:97-1561:67219]]\nהרנסקיה איס!",
 "134170": "[[S:ODIN:vo_int9_cbt_bntr_odn_armor_ice_006:96-1858:67220]]\nהרנסקיה איס!",
 "134176": "[[S:ODIN:vo_int9_cbt_bntr_odn_armor_gen_001:96-1406:65365]]\nהרנסקיה!",
 "134177": "[[S:ODIN:vo_int9_cbt_bntr_odn_armor_gen_002:92-1121:67225]]\nהרנסקיה!",
 "134178": "[[S:ODIN:vo_int9_cbt_bntr_odn_armor_gen_003:98-1277:67226]]\nהרנסקיה!",
 "134520": "[[S:::30969-33083:77895]]\nאוקאר אי מד'אל!",
 "135091": "[[S:KRATOS:vo_int9dlc_lvl_val_hub_main_s050_030_kra:0-3520:76329]]\n“ראד'ה סיאלפר סינום האטום.”",
 "135092": "[[S:KRATOS:vo_int9dlc_lvl_val_hub_main_s050_031_kra:53-3126:77399]]\n“ראד'ה סיאלפר סינום האטום.”"
}

with open("current_batch.json", "r", encoding="utf-8") as f:
    data = json.load(f)

for k, v in updates.items():
    if k in data:
        data[k]["he"] = v

with open("current_batch.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=1, ensure_ascii=False)
