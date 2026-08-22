import json

fixes = {
    "base|onscreens/onscreens_final.json|40405": "הולי שיט, V! אתה על גל מזדיין! הלוואי שכולם היו קורעים את התחת כמוך! השם שלך מתחיל לעשות באזז בחוגים מסוימים – כאלה עם עבודות גדולות ומזומנים לבזבז. הוכחת את היכולות שלך, זה ברור מספיק. מזל טוב – הרווחת את זה.",
    "base|onscreens/onscreens_final.json|40406": "V, תמיד תענוג לעשות איתך עסקים, ובעסקים האלה הכל סובב סביב אמון, נכון? ובכן, אני סומך עליך מספיק כדי לפתוח עבורך כמה גיגים ברמה הבאה. אז שוב – תודה ומזל טוב. אני מעריך את העבודה הקשה שלך.",
    "base|onscreens/onscreens_final.json|42187": "תקשיב, מה שקרה עכשיו אסור שיקרה שוב לעולם. ברור? למה לחבל בעצמך בלי סיבה? זה נראה רע, חד וחלק – לך ולי. אולי בפעם הבאה תחשוב פעמיים ותשתמש בראש שלך לפני שתעשה משהו כל כך גונק.",
    "base|onscreens/onscreens_final.json|42595": "\u0003V, אני יודעת שאתה נטראנר (Netrunner) ששווה משהו, אז אני שולחת לך את זה: [FILE]. זה שד (Daemon) שיעזור לך למצוא את אנה. תעלה אותו לתת-רשת (subnet) ליד הבזאר ותאתר איפה היא התחברה בפעם האחרונה.",
    "base|onscreens/onscreens_final.json|40308": "אנו שמחים לקבל את פניך כאורח החדש שלנו! מספר החדר שלך הוא: 203. אנו מאחלים לך שהייה נעימה! :)\\nזוהי הודעה אוטומטית. נא לא להשיב.",
    "base|onscreens/onscreens_final.json|43450": "סריקה מבליטה עצמים מעניינים בסביבה שלך ויכולה לספק מידע בעל ערך עליהם.\\nאויבים מסומנים ב<Rich color=\"MainColors.Red\" style=\"Bold\">אדום</>, עצמים אינטראקטיביים מסומנים ב<Rich color=\"MainColors.Blue\" style=\"Bold\">כחול</>, ועצמים הקשורים לעבודות מסומנים ב<Rich color=\"MainColors.Yellow\" style=\"Bold\">זהב</>.\\nמכשירים עוינים הניתנים לפריצה צבועים בתבנית דיגיטלית ומסומנים בסמל <Image id=\"MappinIcons.HackableDeviceMappin\" align=\"bottom\" width=\"75\" height=\"75\"></>. מכשירים ניטרליים מסומנים ב<Rich color=\"MainColors.Hacking\" style=\"Bold\">ירוק</>.\\nכוון למסך ולחץ על <Input actionName=\"OpenQuickHackPanel\" color=\"Tutorial.InputHint\"></> כדי לפתוח את תפריט הקוויקהאק.",
    "base|onscreens/onscreens_final.json|43109": "מסך המלאי מציג את רשימת הפריטים שבבעלותך שניתן להצטייד בהם. לחץ <Input context=\"UIMenu\" actionName=\"click\" color=\"Tutorial.InputHint\"></> על פריט כדי להקצות אותו למשבצת המתאימה.",
    "base|onscreens/onscreens_final.json|42992": "ניתן לחטוף רכבים תפוסים כל עוד אתה עומד בדרישות תכונת הגוף (Body Attribute Requirement). רק תזהר מהמשטרה – הם לא יוותרו לך בקלות.",
    "base|onscreens/onscreens_final.json|49490": "הכרה\\n\\nלזכות בכבוד של כמה שחקנים מרכזיים, לפרסם את השם שלך בחוץ – ככה בונים מותג חזק בעיר הזאת. אם הדרך לפסגה קשה ומלאת סכנות – טוב מאוד. תהילה אמיתית לא באה משום מקום. כבוד צריך להרוויח, אחרת אתה לא יותר מפוזר (poser).",
    "base|onscreens/onscreens_final.json|42850": "הרליק (Relic) הולך להרוג אותך, ובקרוב. אם אתה רוצה לחיות, אתה חייב למצוא כל מי שקשור לביו-שבב, לגרום להם לשפוך כל מידע שאולי יש להם. אולי תמצא דרך כלשהי לעצור את זה... או לפחות תמות תוך כדי ניסיון.",
    "base|onscreens/onscreens_final.json|45220": "אתה אומר שתגיע ואז אתה חוזר בך מהמילה שלך? עם מי לעזאזל אתה חושב שאתה מתעסק? חושב שאתה יכול פשוט לעשות ממני צחוק? הייתי שומר על הגב שלי אם הייתי במקומך."
}

d = json.load(open('current_batch.json', encoding='utf-8'))
for k, v in fixes.items():
    if k in d:
        d[k]['fixed_male'] = v

json.dump(d, open('current_batch.json', 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
