import json
import os

with open(r'c:\Users\Nehoray_Cohen\Projects\Game translator\games\godofwar_ragnarok\agent_handoff_english\current_batch.json', 'r', encoding='utf-8') as f:
    batch = json.load(f)

for k, v in batch.items():
    if k == "81386":
        v["he"] = "עלינו\n\\n\nאנחנו Sony Interactive Entertainment. אנא עיין במדיניות הפרטיות שלנו לקבלת מידע נוסף על האופן שבו אנו אוספים ומעבדים את המידע האישי שלך, ועל אופן יצירת הקשר איתנו בכתובת playstation.com/legal/privacy-policy."
    elif k == "81388":
        v["he"] = "אפשר איסוף של נתונים מסוימים לגבי השימוש שלך ב-God of War ראגנארוק כפי שמוסבר במדיניות הפרטיות שלנו.\n(playstation.com/legal/privacy-policy)"
    elif k == "81391":
        v["he"] = "לשם מה אנו משתמשים בנתוני משחק?\nנתונים מוגבלים -- ואם תאפשר זאת, נתונים מלאים -- משמשים כפי שמוסבר במדיניות הפרטיות שלנו (playstation.com/legal/privacy-policy).\nזה כולל שימוש בנתוני משחק כדי:\n•\tלספק לך את המשחקים שלנו.\n•\tלהבין את השימוש והביצועים של המשחק שבו אתה משחק, ולפתח שיפורים למשחק.\n•\tלפתח מוצרים ושירותים חדשים.\n•\tלזהות, לחקור ולצמצם התנהגות זדונית, בלתי מורשית או הונאה.\n•\tמטרות ביקורת, תאימות ומשפטיות (לדוגמה, הגשה או הגנה מפני תביעות או פעילויות הנדרשות לצורך ציות לחוק)."

with open(r'c:\Users\Nehoray_Cohen\Projects\Game translator\games\godofwar_ragnarok\agent_handoff_english\current_batch.json', 'w', encoding='utf-8') as f:
    json.dump(batch, f, ensure_ascii=False, indent=1)
