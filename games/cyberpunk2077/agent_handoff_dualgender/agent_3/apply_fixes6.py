import json

def fix_batch():
    with open('current_batch.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    # For empty lines or ones with no gender, fixed_male = he_female
    for k, v in data.items():
        data[k]['fixed_male'] = v['he_female']

    # Replacements map
    reps = {
        "base|subtitles/quest/q203/q203_02b_kerry.json|1792416786472890368": [("חושבת", "חושב"), ("את חייבת", "אתה חייב")],
        "base|subtitles/quest/q203/q203_02c_judy.json|1316934202107228176": [("הייתי מודדת", "הייתי מודד")],
        "base|subtitles/quest/q203/q203_02c_judy.json|1489318391824642048": [("את שולטת", "אתה שולט"), ("תסתכלי על עצמך", "תסתכל על עצמך"), ("מלכת", "מלך")],
        "base|subtitles/quest/q203/q203_02c_judy.json|1792187546099904512": [("אוהבת", "אוהב")],
        "base|subtitles/quest/q203/q203_02d_panam.json|1794965985928278016": [("את יודעת", "אתה יודע")],
        "base|subtitles/quest/q203/q203_03_sobchak.json|1490670359985909760": [("עייפה", "עייף")],
        "base|subtitles/quest/q203/q203_03_sobchak.json|1490686684200300544": [("תני", "תן"), ("את יודעת", "אתה יודע")],
        "base|subtitles/quest/q203/q203_03_sobchak.json|1793788726836064256": [("את מתנהגת", "אתה מתנהג")],
        "base|subtitles/quest/q203/q203_03_sobchak.json|1793867342705979392": [("שומעת", "שומע")],
        "base|subtitles/quest/q203/q203_03_sobchak.json|1793927191598854144": [("יכולה", "יכול")],
        "base|subtitles/quest/q203/q203_04_delamain.json|1795191990295064576": [("מוכנה", "מוכן")],
        "base|subtitles/quest/q203/q203_05_afterlife.json|1795378485677125632": [("חושבות", "חושב")],
        "base|subtitles/quest/q203/q203_05_afterlife.json|1873364335832199168": [("תעשו", "תעשה")],
        "base|subtitles/quest/q203/q203_05_afterlife.json|2251576361321951276": [("את יודעת", "אתה יודע")],
        "base|subtitles/quest/q204/q204_03b_after_dad.json|1794068307836469248": [("תישבי", "תשב")],
        "base|subtitles/quest/q204/q204_04_to_music_store.json|1695524777422970880": [("את לעולם", "אתה לעולם"), ("תגיעי", "תגיע")],
        "base|subtitles/quest/q204/q204_04_to_music_store.json|1807045968079314944": [("תרגישי", "תרגיש")],
        "base|subtitles/quest/q204/q204_06_to_columbarium.json|1306606769115516928": [("תדאגי", "תדאג")],
        "base|subtitles/quest/q204/q204_08_farewell.json|1324254346278035456": [("חכמה", "חכם"), ("מתכוונת", "מתכוון")],
        "base|subtitles/quest/q204/q204_08_farewell.json|1730506789040644124": [("חכמה", "חכם"), ("מתכוונת", "מתכוון")],
        "base|subtitles/quest/sq004/sq004_02_intro.json|1976559210580484096": [("את רוצה", "אתה רוצה"), ("חושבת", "חושב")],
        "base|subtitles/quest/sq004/sq004_05_infiltration.json|1895274609636089856": [("תזכרי", "תזכור"), ("תמצאי", "תמצא"), ("ותקבלי", "ותקבל")],
        "base|subtitles/quest/sq004/sq004_08_farm.json|1902428838280634368": [("את יודעת", "אתה יודע")],
        "base|subtitles/quest/sq006/sq006_00a_phonecall.json|1803999933419884544": [("תבואי", "תבוא")],
        "base|subtitles/quest/sq006/sq006_01a_apartment_welcome.json|1641297074078224396": [("את יודעת", "אתה יודע")],
        "base|subtitles/quest/sq006/sq006_02b_investigation.json|1928884172073603072": [("את לא נולדת", "אתה לא נולדת")],
        "base|subtitles/quest/sq006/sq006_02c_conclusion.json|1638782639983415296": [("תני", "תן"), ("תגידי", "תגיד")],
        "base|subtitles/quest/sq006/sq006_06a_clandestine.json|1287787148156203008": [("נשבעת", "נשבע")],
        "base|subtitles/quest/sq006/sq006_06a_clandestine.json|1751880320431558688": [("אמורה", "אמור")],
        "base|subtitles/quest/sq006/sq006_06a_clandestine.json|2007011551433854976": [("חושבת", "חושב"), ("יודעת", "יודע")],
        "base|subtitles/quest/sq006/sq006_07a_final_choice.json|1640192441187946496": [("את בצרה", "אתה בצרה"), ("שחשבת", "שחשבת")],
        "base|subtitles/quest/sq006/sq006_07a_final_choice.json|1806995175916048384": [("השתמשי", "השתמש"), ("תיבחרי", "תיבחר"), ("תשכחי", "תשכח")],
        "base|subtitles/quest/sq011/sq011_00_intro.json|1827314219883450368": [("את רוצה", "אתה רוצה")],
        "base|subtitles/quest/sq011/sq011_01_kerry_mansion.json|1804282907004198912": [("שבי", "שב"), ("תספרי", "תספר")],
        "base|subtitles/quest/sq011/sq011_07a_royce.json|1805820681423380480": [("היית ממקמת", "היית ממקם")],
        "base|subtitles/quest/sq012/sq012_00_phonecalls.json|1893957585009860608": [("מניחה", "מניח")],
        "base|subtitles/quest/sq012/sq012_02a_braindance.json|1873252197612216320": [("תגלולי", "תגלול"), ("שתראי", "שתראה")],
        "base|subtitles/quest/sq012/sq012_05a_sex_shop.json|1699562983975931904": [("חושבת", "חושב")],
        "base|subtitles/quest/sq012/sq012_06a_rqr_ext.json|1938950781984792576": [("תדחפי", "תדחוף"), ("תסתכלי", "תסתכל")],
        "base|subtitles/quest/sq012/sq012_06b_rqr_investigation.json|2309881230934106112": [("נראית", "נראה")],
        "base|subtitles/quest/sq017/sq017_01_phone_call_1.json|1760261024984461312": [("בטוחה", "בטוח")],
        "base|subtitles/quest/sq017/sq017_08_club_outside.json|1822903452017844224": [("צריכה", "צריך")],
        "base|subtitles/quest/sq017/sq017_10_us_crack_intro.json|1805095865072349184": [("תעשי", "תעשה"), ("תשכחי", "תשכח")],
        "base|subtitles/quest/sq017/sq017_10_us_crack_intro.json|1833008389427949568": [("תעשי", "תעשה")],
        "base|subtitles/quest/sq017/sq017_10_us_crack_intro.json|1833092088005783552": [("תראי", "תראה")],
        "base|subtitles/quest/sq017/sq017_10_us_crack_intro.json|2231683495934226432": [("תני", "תן")],
        "base|subtitles/quest/sq017/sq017_10_us_crack_intro.json|2231689121133424640": [("תרצי", "תרצה")],
        "base|subtitles/quest/sq017/sq017_16_phone_call_3.json|1851712470296162304": [("תכירי", "תכיר")],
        "base|subtitles/quest/sq017/sq017_18_premiere.json|1805317543501099008": [("מתכוונה", "מתכוון")],
        "base|subtitles/quest/sq017/sq017_18_premiere.json|1805356442214592512": [("יכולה", "יכול")],
        "base|subtitles/quest/sq017/sq017_18_premiere.json|1807175567529435152": [("אוהבת", "אוהב")],
        "base|subtitles/quest/sq017/sq017_18_premiere.json|1835575061699489792": [("נראית", "נראה")],
        "base|subtitles/quest/sq017/sq017_18_premiere.json|1851697876399943688": [("תוכלי", "תוכל"), ("בואי", "בוא")],
        "base|subtitles/quest/sq018/sq018_03_funeral.json|1725639810939265024": [("עשי", "עשה")],
        "base|subtitles/quest/sq021/sq021_01_hook.json|1960749992517799940": [("תיזהרי", "תיזהר")],
        "base|subtitles/quest/sq021/sq021_01_hook.json|1960749992769458208": [("את יודעת", "אתה יודע"), ("יכולה", "יכול")],
        "base|subtitles/quest/sq021/sq021_02_ride.json|1780929152491163648": [("מודאגת", "מודאג")],
        "base|subtitles/quest/sq023/sq023_03_call.json|1937457934571114548": [("אחת", "אחד"), ("הייתה מפגרת", "היה מפגר")],
        "base|subtitles/quest/sq023/sq023_03_call.json|1944777926857691140": [("תשכחי", "תשכח")],
        "base|subtitles/quest/sq023/sq023_04_glorias_house.json|1811270692494663680": [("אומרת", "אומר")],
        "base|subtitles/quest/sq023/sq023_11_01a_after_chase.json|1755096294062841856": [("את לא צריכה", "אתה לא צריך")],
        "base|subtitles/quest/sq024/sq024_00_claire_hook.json|1854661037271420928": [("בואי", "בוא")],
        "base|subtitles/quest/sq024/sq024_03_badlands_race.json|2237382175312973828": [("שתתעלמי", "שתתעלם")],
        "base|subtitles/quest/sq024/sq024_05b_trauma_team.json|2230470618041683968": [("את שואלת", "אתה שואל")],
        "base|subtitles/quest/sq025/sq025_04_briefing.json|1753300600082309120": [("בודקת", "בודק")],
        "base|subtitles/quest/sq025/sq025_04_briefing.json|1925668355809239040": [("מודעת", "מודע")],
        "base|subtitles/quest/sq026/sq026_04_maiko.json|1906901358081982480": [("תצפי", "תצפה"), ("תפספסי", "תפספס")],
        "base|subtitles/quest/sq026/sq026_04_maiko.json|1914387122130477064": [("תדעי", "תדע")],
        "base|subtitles/quest/sq026/sq026_05a_leave.json|1908185979209891840": [("שתיכן עושות", "שניכם עושים")],
        "base|subtitles/quest/sq026/sq026_08_plan.json|1888075344719339520": [("יכולה", "יכול"), ("מתכוונת", "מתכוון")],
        "base|subtitles/quest/sq026/sq026_08_plan.json|1914453796397473792": [("את המנהלת", "אתה המנהל")],
        "base|subtitles/quest/sq026/sq026_11_to_penthouse.json|1782122785958510596": [("מתעייפת", "מתעייף"), ("חיילה", "חייל")],
        "base|subtitles/quest/sq026/sq026_13_hiromi.json|1775011148273270784": [("שאת הולכת", "שאתה הולך"), ("חוזרת", "חוזר")],
        "base|subtitles/quest/sq026/sq026_13_hiromi.json|1890950806667747328": [("את מצפה", "אתה מצפה")],
        "base|subtitles/quest/sq026/sq026_15_end.json|1775210963204554752": [("את לקחת", "אתה לקחת")],
        "base|subtitles/quest/sq027/sq027_04_preparations_panam.json|1774999854673891328": [("את מתכוונת", "אתה מתכוון")],
        "base|subtitles/quest/sq027/sq027_04_preparations_panam.json|1775008137216331776": [("אוהבת", "אוהב"), ("שאת עדיין נלחמת", "שאתה עדיין נלחם")],
        "base|subtitles/quest/sq027/sq027_04_preparations_panam.json|1804201750793883648": [("חופשייה", "חופשי"), ("את יכולה", "אתה יכול")],
        "base|subtitles/quest/sq027/sq027_05_ambush.json|1940441613620498436": [("יודעת", "יודע")],
        "base|subtitles/quest/sq027/sq027_05a_transport_delivered.json|1786911707226722304": [("את רוצה", "אתה רוצה")],
        "base|subtitles/quest/sq027/sq027_06_panzer.json|1812617215895474176": [("את תחווי", "אתה תחווה")],
        "base|subtitles/quest/sq027/sq027_06_panzer.json|1812860043766599680": [("תרגישי", "תרגיש")],
        "base|subtitles/quest/sq027/sq027_09_new_camp_wakeup.json|1947490954582290432": [("תוכלי", "תוכל")],
        "base|subtitles/quest/sq027/sq027_09_new_camp_wakeup.json|1999573728327495680": [("את מבינה", "אתה מבין")],
        "base|subtitles/quest/sq029/sq029_02a_arrival.json|1731407383472607232": [("בטוחה", "בטוח")],
        "base|subtitles/quest/sq029/sq029_02a_arrival.json|1978198353207119872": [("אמורות", "אמורים")],
        "base|subtitles/quest/sq029/sq029_04a_dinner.json|1960615632837947428": [("שאת יודעת", "שאתה יודע"), ("את מדברת", "אתה מדבר")],
        "base|subtitles/quest/sq030/sq030_03_dam_equipment.json|1933107706867023872": [("נראית", "נראה"), ("מוכנה", "מוכן")],
        "base|subtitles/quest/sq030/sq030_05_lake_test.json|1901029829892882432": [("שתצליחי", "שתצליח")],
        "base|subtitles/quest/sq030/sq030_09_pier.json|1844453760582770692": [("את רק", "אתה רק"), ("שהיית מאשימה את עצמך", "שהיית מאשים את עצמך")],
        "base|subtitles/quest/sq030/sq030_11_morning.json|1765040187331559424": [("את יודעת", "אתה יודע"), ("תסדרי", "תסדר")],
        "base|subtitles/quest/sq030/sq030_11_morning.json|1799767162566172672": [("יכולה", "יכול")],
        "base|subtitles/quest/sq031/sq031_00_johnny.json|1892422717713174528": [("תעבירי", "תעביר"), ("ותקפצי", "ותקפוץ")],
        "base|subtitles/quest/sq031/sq031_08_movie.json|1902595884960206848": [("את מנסה", "אתה מנסה")],
        "base|subtitles/quest/sq032/sq032_03_third_episode.json|1863703184203603968": [("הקשיבי", "הקשב"), ("יודעת", "יודע")],
        "base|subtitles/quest/sq032/sq032_04_fourth_episode.json|1814232836967669760": [("אומרת", "אומר"), ("מתעבת", "מתעב")],
        "base|subtitles/quest/sq032/sq032_04_fourth_episode.json|1869152073719242752": [("את מגלה", "אתה מגלה")],
        "base|subtitles/quest/sq032/sq032_06_sixth_episode.json|1904359839421194240": [("היית מתיידדת", "היית מתיידד")],
        "base|subtitles/quest/sq032/sq032_07_finale.json|1905471416752955408": [("אישה", "איש"), ("את אמרת", "אתה אמרת")],
        "base|subtitles/quest/sq032/sq032_07_finale.json|1905471416853618692": [("את תזרקי", "אתה תזרוק")],
        "base|subtitles/quest/sq032/sq032_07_finale.json|1905471417155608576": [("שתעשי", "שתעשה"), ("תנסי", "תנסה")],
        "base|subtitles/quest/victor/victor_vector_default.json|1995626137400139776": [("את יודעת", "אתה יודע")],
        "dlc|ep1/onscreens/onscreens_final.json|89420": [("תדאגי", "תדאג")],
        "dlc|ep1/onscreens/onscreens_final.json|87409": [("צריכה", "צריך")],
        "base|onscreens/onscreens_final.json|48084": [("את יוצאת", "אתה יוצא")],
        "base|onscreens/onscreens_final.json|43380": [("תבלעי", "תבלע")],
        "base|onscreens/onscreens_final.json|79312": [("תני", "תן")],
        "base|onscreens/onscreens_final.json|12086": [("לכי", "לך")],
        "base|subtitles/open_world/voicesets/civ_low_f_16_enus_30.json|1908072369610039300": [("תבלי", "תבלה"), ("את הולכת", "אתה הולך")],
        "base|onscreens/onscreens_final.json|10432": [("עלי", "עלה")],
        "base|onscreens/onscreens_final.json|48654": [("את מבריזה", "אתה מבריז")],
        "base|onscreens/onscreens_final.json|14242": [("עני", "ענה")]
    }

    for k, v in data.items():
        if k in reps:
            fixed = v['he_female']
            for old, new in reps[k]:
                fixed = fixed.replace(old, new)
            data[k]['fixed_male'] = fixed

    with open('current_batch.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    fix_batch()
