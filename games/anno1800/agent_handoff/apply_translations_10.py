import json
import os
import sys

handoff = r"c:\Users\Nehoray_Cohen\Projects\Game translator\games\anno1800\agent_handoff"
sys.path.insert(0, handoff)

from do_translate_10_data import translations_1
from do_translate_10_data_2 import translations_2
from do_translate_10_data_3 import translations_3

all_trans = {}
all_trans.update(translations_1)
all_trans.update(translations_2)
all_trans.update(translations_3)

# Add missing translations and fix problematic tags/scripts
all_trans["803490"] = "<b>פחות חשאי מכפי שדמיינת.</b> כשאתה חומק אל הטיילת שמאחורי הקזינו, אתה נפגש בבריזת ריביירה חמימה ובמראה של דקלים אקזוטיים. אתה מטפס על החומה ללא תקלות, אך אז מועד בטעות דרך צוהר. אתה נוחת ברעש על השטיח של חדר שינה לאורחים בגשם של קריסטל מנופץ. למרבה המזל, האורח נמצא למטה ומשחק קוביות, ולא יגלה את הבלגן הזה אלא הרבה יותר מאוחר. בניסיון לגייס את כל החן שנותר לך, <b>אתה עושה את דרכך אל תוך הקזינו ומתלבט מהי הדרך הטובה ביותר למצוא את המלכה.</b>"
all_trans["803501"] = "<b>המלכה ברחה מהקזינו במהירות גבוהה,</b> והכרכרה שלך נמצאת במרחק מה מאחור. הנהג שלך חושב שהיא פונה במעלה החוף, אולי לספינה. <b>אתה יכול להמשיך במרדף, או למהר לספינה שלך,</b> אשר, אם מולאו הפקודות שנתת לקפטן, אמורה להמתין במרינה של מונגסקה."
all_trans["803523"] = "<b>הרופא מגחך.</b> \"הנה,\" הוא אומר, ומחלק לכל נפש מוכה שיקוי מתיק התרופות שלו, \"זה אמור להקל על העניינים.\" במהרה כולם שקועים בשינה עמוקה, והם מתעוררים למחרת בהרגשה רעננה. מבלי לדעת שרימית, אוכלי הפרחים מתרשמים! בדרך כלל איש אינו מתמודד כה טוב עם המפגש הראשון שלו עם הפרח. <b>כשהם רואים בכך סימן, הם מציעים לך משהו יקר ערך באותה מידה.</b>"
all_trans["803524"] = "<b>הרופא המודאג נותן חומר מקיא,</b> \"תקיאו את זה, זה רעל!\" הוא אומר. לאחר מכן, הצוות מרגיש חלש ביותר, אך השפעת הסם אכן מתחילה להתפוגג. \"פשוט לא היה לנו את האומץ לזה,\" מלח מנגב את פיו. הראית חולשה גופנית. מסביב, אוכלי הפרחים מתבדחים על חשבון הצוות. <b>אתה עוזב מושפל.</b>"
all_trans["803548"] = "<b>הספינה תוקנה, אך הציידים עדיין לא חזרו.</b> מוטב שתחליט אם כדאי לקחת את הסיכון ללכת בעקבותיהם."
all_trans["803588"] = "<b>מאחר שמצאו כאן מעט מאוד מזון, האנשים מתחילים לריב</b> על מי זקוק לו ביותר. המתח גובר, והם יהיו בגרונו של זה אם לא ייעשה דבר."
all_trans["803623"] = "<b>\"זו חייבת להיות גרסה נדירה של אבעבועות שחורות!\"</b> הרופא הרגיש שלך אפילו לא רוכן קרוב מספיק לשלפוחיות לפני שהוא צווח: \"התרחקו מהם! האנשים האלה אבודים — אין לנו מה לעשות מלבד להימנע מהדבקה!\" פאניקה מתעוררת, ואלה שלא נפגעו מהפריחה נמלטים בבהלה. הקבוצה הכואבת ננטשת בצורה לא אחראית ומושארת מאחור."
all_trans["803656"] = "<b>קול של צרחה אנושית מבהיל את המשלחת שלך</b> כשהם עוברים בכפר קטן ביער. המצפון מחייב אותם לחקור, בין אם <b>בגלוי</b> או <b>בסתר</b>, אלא אם כן הם מרגישים שעדיף <b>לא להתערב</b> בעניינים מקומיים."
all_trans["803658"] = "<b>אתה בוחר בשניים מהטובים ביותר שלך,</b> שמתפצלים כלאחר יד מהקבוצה. האנשים באזור זה רגילים למבקרים מערביים, וחשדות אינם מתעוררים. בהצצה לתוך בקתה, סוכניך מבחינים ב<b>אישה המוחזקת על ידי שני גברים, בעוד שלישי נראה כמכריח אותה לשתות סוג של מרקחת צמחים.</b>"

# Read to_translate_batch.json to verify all keys
with open(os.path.join(handoff, "to_translate_batch.json"), "r", encoding="utf-8") as f:
    batch = json.load(f)

# Define skips
skips_to_add = [
    "601956", "601958", "601959", "601960", "601961", "601962", "601964", "601988",
    "602021", "602023", "602033",
    "602059", "602073", "602110", "602112", "700000", "700040", "700041", "700042",
    "700043", "700046", "700139", "700140", "700141", "700142", "700143", "700144",
    "700145", "700146", "700148", "700149", "700152", "700153", "803493", "803536",
    "803544"
]

# We need to make sure sample mercier escort gaming (601957) is skipped, wait, did we translate it or skip it?
# In translations_1 it is NOT translated. In generation it was in trans. So it would be missing. Let's make sure it is in skips_to_add.
if "601957" not in skips_to_add and "601957" not in all_trans:
    skips_to_add.append("601957")

# Verify if all keys in batch are covered
batch_keys = set(batch.keys())
covered_keys = set(all_trans.keys()).union(set(skips_to_add))

missing_keys = batch_keys - covered_keys
extra_keys = covered_keys - batch_keys

print(f"Batch size: {len(batch)}")
print(f"Translated: {len(all_trans)}")
print(f"Skipped: {len(skips_to_add)}")
print(f"Total covered: {len(covered_keys)}")

if missing_keys:
    print(f"Missing keys: {missing_keys}")
if extra_keys:
    print(f"Extra keys: {extra_keys}")

# Write out the clean translate_current_batch_10.py
template_content = f"""import json
import os

handoff = r"c:\\Users\\Nehoray_Cohen\\Projects\\Game translator\\games\\anno1800\\agent_handoff"

trans = {{
"""

# Sort trans by key to make it clean
for guid in sorted(all_trans.keys(), key=lambda x: int(x)):
    val = all_trans[guid]
    escaped_val = val.replace('\\', '\\\\').replace('"', '\\"')
    template_content += f'    "{guid}": "{escaped_val}",\n'

template_content += """}

skips_to_add = [
"""

for guid in sorted(skips_to_add, key=lambda x: int(x)):
    template_content += f'    "{guid}",\n'

template_content += """]

# Load to_translate_batch.json to verify we covered all keys
with open(os.path.join(handoff, "to_translate_batch.json"), "r", encoding="utf-8") as f:
    batch = json.load(f)

# Sanity Check
all_covered_keys = set(trans.keys()).union(set(skips_to_add))
batch_keys = set(batch.keys())

missing_in_our_code = batch_keys - all_covered_keys
extra_in_our_code = all_covered_keys - batch_keys

print(f"Batch size: {{len(batch)}}")
print(f"Translated in our code: {{len(trans)}}")
print(f"Skipped in our code: {{len(skips_to_add)}}")
print(f"Total covered: {{len(all_covered_keys)}}")

if missing_in_our_code:
    print(f"CRITICAL ERROR: Keys missing in our code: {{missing_in_our_code}}")
if extra_in_our_code:
    print(f"CRITICAL ERROR: Extra keys in our code: {{extra_in_our_code}}")

if not missing_in_our_code and not extra_in_our_code:
    print("Verification passed! Writing outputs...")
    
    # Save trans_part_1.json
    out_path = os.path.join(handoff, "trans_part_1.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(trans, f, ensure_ascii=False, indent=0)
    
    # Update skip.json
    skip_path = os.path.join(handoff, "skip.json")
    if os.path.exists(skip_path):
        with open(skip_path, "r", encoding="utf-8") as f:
            skips = json.load(f)
    else:
        skips = []
        
    skips.extend(skips_to_add)
    # Sort and remove duplicates
    skips = sorted(list(set(skips)), key=lambda x: int(x))
    
    with open(skip_path, "w", encoding="utf-8") as f:
        json.dump(skips, f, ensure_ascii=False, indent=0)
        
    print("Files updated successfully!")
else:
    print("Verification failed! Not writing files.")
"""

with open(os.path.join(handoff, "translate_current_batch_10.py"), "w", encoding="utf-8") as f:
    f.write(template_content)

print("translate_current_batch_10.py rewritten successfully!")
