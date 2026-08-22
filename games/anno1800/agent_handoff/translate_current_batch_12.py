import json
import os

handoff = r"c:\Users\Nehoray_Cohen\Projects\Game translator\games\anno1800\agent_handoff"

trans = {
    "10000087": "ברגע שספינתך קרובה אל המטרה, בחר בה ולחץ[GamepadActionManager GamepadActionTooltip(TargetManagerSecondaryActionPress)] כדי לאסוף אותה. אם אין ברשותך די מקום, תוכל להשליך כל דבר על ידי בחירתו ולחיצה על [GamepadActionManager GamepadActionTooltip(ShipOMThrowOverboard)]..",
    "10000088": "הבא ספינה אל קרבת ספינת המטרה כדי להתחיל בליווי. תוכל למצוא אותה על ידי פתיחת מעקב המשימות ולחיצה על [GamepadActionManager GamepadActionTooltip(JumpToQuestLocation)].",
    "10000089": "תוכל להורות לספינותיך ללוות באופן אוטומטי על ידי בחירת ספינתך ולחיצה על [GamepadActionManager GamepadActionTooltip(TargetManagerSecondaryActionPress)] בעת ריחוף מעל ספינת המטרה.",
    "10000090": "הבא ספינה אל המיקום המבוקש. תוכל למצוא אותו על ידי גישה למעקב המשימות ולחיצה על [GamepadActionManager GamepadActionTooltip(JumpToQuestLocation)].",
    "10000091": "גש למעקב המשימות ולחץ על [GamepadActionManager GamepadActionTooltip(EnterPhotoMode)] כדי לצלם. נווט אל עבר מושא הצילום באמצעות [GamepadActionManager GamepadButtonTooltip(LS_all)] ו-[GamepadActionManager GamepadButtonTooltip(RS_all)].",
    "10000092": "אם אין ברשותך מקום פנוי, השלך דבר-מה אחר אל מעבר לסיפון על ידי לחיצה על [GamepadActionManager GamepadActionTooltip(ShipOMThrowOverboard)] בעת ריחוף מעל פריט טעון.",
    "10000093": "אסוף את המתנה על ידי בחירת התיבה לצד תושב המשימה.",
    "10000094": "ברגע שספינתך קרובה אל המיקום המבוקש, קבל את המטען. אם אין ברשותך די מקום למטען, תוכל להשליך פריטים בלחיצה על [GamepadActionManager GamepadActionTooltip(ShipOMThrowOverboard)] בעת בחירת חפץ בתא מטען.",
    "10000095": "גש למעקב המשימות ולחץ[GamepadActionManager GamepadActionTooltip(JumpToQuestLocation)] כדי לקפוץ אל המיקום המבוקש.",
    "10000096": "לחץ על [GamepadActionManager GamepadActionTooltip(ShipOMActivateItem)] בעת ריחוף מעל הטורפדו כדי לבחור בו, ואז לחץ על [GamepadActionManager GamepadActionTooltip(TargetManagerSecondaryActionPress)] במקום שבו ברצונך לשגרו.",
    "10000098": "סע אל נמלו של אדוארד שנמצא מדרום-מערב לאי שלך. תוכל גם לגשת למעקב המשימות וללחוץ על [GamepadActionManager GamepadActionTooltip(JumpToQuestLocation)] כדי להניע את המצלמה אל נמלו של אדוארד.",
    "10000099": "גש למעקב המשימות ולחץ על [GamepadActionManager GamepadActionTooltip(JumpToQuestLocation)] כדי להניע את המצלמה אל המיקום שבו נמצאים הניצולים.",
    "10000100": "מבט מצלמה מרוחק מלמעלה למטה מעניק סקירה טובה יותר: לחץ על [GamepadActionManager GamepadActionTooltip(CameraPitch)] + [GamepadActionManager GamepadButtonTooltip(RS_Vertical)] כדי להטות את המצלמה כלפי מטה.",
    "10000101": "כדי לצלם את מספנת ספינות המפרש שלך, גש למעקב המשימות ולחץ על [GamepadActionManager GamepadActionTooltip(EnterPhotoMode)].",
    "10000102": "על המספנה להיות בתוך מסגרת הצילום. תוכל להשתמש ב-[GamepadActionManager GamepadButtonTooltip(LS_all)] וב-[GamepadActionManager GamepadButtonTooltip(RS_all)] כדי להתאים את מיקום מצלמתך.",
    "10000103": "מכור ספינה על ידי הבאתה אל נמלו של ארצ'יבלד. לאחר מכן, בחר בספינה והפעל את כפתור \"מכור\" בפינה הימנית התחתונה.",
    "10000104": "תוכל להעביר ספינות מהעולם הישן אל העולם החדש על ידי הפעלת כפתור מפת העולם בפינה !הימנית העליונה של תפריט הספינה.",
    "10000105": "תוכל להורות לספינותיך ללוות את ספינתה של איזבל באופן אוטומטי על ידי בחירת ספינתך ולחיצה על [GamepadActionManager GamepadActionTooltip(TargetManagerSecondaryActionPress)] בעת ריחוף מעל אחת מספינותיה של איזבל.",
    "10000106": "כאשר כלי ההריסה נבחר, לחץ על [GamepadActionManager GamepadActionTooltip(TargetManagerModifier)] כדי לשנות את מה שברצונך להרוס. תוכל לבחור להרוס רחובות מבלי להשפיע על המבנים שלך.",
    "10000110": "מהירות משחק מוסתרת",
    "10000113": "איש אינו נהנה מחיים המוקפים בזיהום... תוכל לבדוק את רמות הזיהום של האי שלך על ידי פתיחת  <b>תפריט מידע על האי</b> ומעבר אל <b>לשונית אטרקטיביות</b>.",
    "10000114": "קפוץ בין תחנות סחר שלוש פעמים בלחיצה[GamepadActionManager GamepadActionTooltip(CameraNavigateToKontorOrNextOfSelection)] <br />(בטל תחילה את הבחירה בכל מבנה או ספינה)",
    "10000115": "בחר את האיגוד המקצועי שלך, ואז בחר חריץ כלשהו כדי לצייד פריט.",
    "10000116": "...ואז השתמש בפונקציית הטלפורט כדי לקפוץ לכל מיקום על המפה.",
    "10000132": "ניתן לבנות תחנות סחר אך ורק על <b>חוף</b> של אי. בחר בצללית השקופה של תחנת סחר כדי לבנות אותה.",
    "10000133": "סוף כל סוף ביכולתנו לשלוח משלחות אל העולם! פתח את תפריט המשלחות והבט ביעדים האפשריים השונים!",
    "10000138": "חייב להיות באורך של שתי משבצות לפחות"
}

skips_to_add = []

# Load to_translate_batch.json to verify we covered all keys
with open(os.path.join(handoff, "to_translate_batch.json"), "r", encoding="utf-8") as f:
    batch = json.load(f)

# Sanity Check
all_covered_keys = set(trans.keys()).union(set(skips_to_add))
batch_keys = set(batch.keys())

missing_in_our_code = batch_keys - all_covered_keys
extra_in_our_code = all_covered_keys - batch_keys

print(f"Batch size: {len(batch)}")
print(f"Translated in our code: {len(trans)}")
print(f"Skipped in our code: {len(skips_to_add)}")
print(f"Total covered: {len(all_covered_keys)}")

if missing_in_our_code:
    print(f"CRITICAL ERROR: Keys missing in our code: {missing_in_our_code}")
if extra_in_our_code:
    print(f"CRITICAL ERROR: Extra keys in our code: {extra_in_our_code}")

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
