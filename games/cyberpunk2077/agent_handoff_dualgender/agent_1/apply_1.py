import json

fixes = {
    "base|onscreens/onscreens_final.json|92696": "לחץ על <Input context=\"Abilities\" actionName=\"IconicCyberware\" color=\"MainColors.Blue\" hold=\"Hide\"></> כדי להפעיל.\n\nכאשר מופעל:\n+{int_6}% damage הפחתת נזק\nהבריאות אינה יכולה לרדת מתחת ל-{int_0}%\nלא ניתן להשתמש בפריטים\nנשק קר בלבד\n-{int_1}% Stamina עלות סיבולת להתקפות קפא\"פ\n\n<Rich color=\"TooltipText.cyberwareDescriptionHighlightColor\" style=\"Semi-Bold\">+{int_2}% attack מהירות התקפה</>\n<Rich color=\"TooltipText.cyberwareDescriptionHighlightColor\" style=\"Semi-Bold\">-{int_3}% fall נזק מנפילה</>\n\nלחץ על <Input context=\"Combat\" actionName=\"QuickMelee\" color=\"MainColors.Blue\" hold=\"Hide\"></> באוויר עם נשק קהה כדי להטיח בקרקע <Rich color=\"TooltipText.cyberwareDescriptionHighlightColor\" style=\"Semi-Bold\">נחיתת גיבור-על</>.\n\nכאשר זה מסתיים:\n<Rich color=\"TooltipText.cyberwareDescriptionHighlightColor\" style=\"Semi-Bold\">+{int_4}% Health בריאות</> עבור כל אויב שנוטרל.\n\n<Rich color=\"TooltipText.cyberwareDescriptionHighlightColor\" style=\"Semi-Bold\">משך:</> {int_5} שניות.",
    "base|onscreens/onscreens_final.json|49089": "אתה בטח תוהה למה זה ענייני. הנה האמת – מגפת ה\"סייברפסיכוזה\" הזאת ממש נכנסת לי מתחת לעור. מספר התקריות גבוה מדי. יש לי את העקצוץ הזה מהימים שלי כעיתונאית – משהו פשוט לא מסתדר. אני רוצה לגלות מה גורם להתפרצויות האלה ומי אחראי להן. אני לא קונה את הסיפור שזה בגלל \"יותר מדי שתלים\" – זה לא הגיוני. חייב להיות הסבר אחר.",
    "base|onscreens/onscreens_final.json|42184": "מה לעזאזל עובר עליך?! הכל היה פאקינג דבש, טיפ-טופ, צבעי קשת בענן – ואז אתה חוזר ומחרבן על הכל? לעזאזל איתך, V...",
    "base|onscreens/onscreens_final.json|42197": "לחץ על <Input context=\"VehicleTankDrive\" actionName=\"ShootSecondary\" color=\"Tutorial.InputHint\"></> כדי לירות טיל מתביית.\nהחזק את <Input context=\"VehicleTankDrive\" actionName=\"ShootSecondary\" color=\"Tutorial.InputHint\"></> כדי להינעל על מטרות.",
    "base|onscreens/onscreens_final.json|43493": "המטרה שלך היא להכניס את הרצף של ICEpick ל-Buffer.\n\nכדי להוסיף תו מה-Code Matrix ל-Buffer, רחף מעליו ולחץ על <Input context=\"UIMenu\" actionName=\"click\" color=\"Tutorial.InputHint\"></>.",
    "base|onscreens/onscreens_final.json|47944": "ה-NCPD מנפיק פרסים (bounties) על כמה מהפושעים המבוקשים של העיר. אם תביס אדם מבוקש, העיר תתגמל אותך בהעברת כספים נדיבה.",
    "base|onscreens/onscreens_final.json|49430": "הכל מוכן. המעגל מצויר, הטלה מחכה לשחיטה. בוא כמה שיותר מהר. אנחנו לא יכולים לחכות יותר – הסיליקון שלי צמא לדם. הכבלים רוחשים, החיבורים מעלים ניצוצות, המודמים נאנחים כל כך חזק שאני לא יכולה לחשוב! התהום חסרת סבלנות. התהום רעבה.",
    "base|onscreens/onscreens_final.json|42599": "תראה, אם עבודה מתחילה כמו תעלומת רצח קלאסית – איזו פאם פאטאל (femme fatale) מתקשרת אליך, מסרבת לתת פרטים ורק קובעת פגישה – אחד משלושה דברים קורה: אתה חולם, אתה מריץ (scrollin') בריינדאנס (BD) מחורבן או שמישהו מותח אותך טוב-טוב. נראה לי שאתה יכול למחוק את השניים הראשונים.",
    "base|onscreens/onscreens_final.json|43113": "גלה את הפירומן הפנימי שבך והצת את אויביך בעזרת קליעים מלאי חומר נפץ. ככל שיותר אויבים בוערים בו-זמנית, כך תטען מהר יותר וסיכוי הפגיעה הקריטית שלך יהיה גבוה יותר. קדימה, סמוראי – יש לנו עיר לשרוף.",
    "base|onscreens/onscreens_final.json|40407": "לאט אבל בטוח, אתה עושה את דרכך לפסגה. כל מה שאני יכול להגיד זה שאני שמח שאנחנו שם לעזור אחד לשני. אוקיי, מספיק שאני נהיה רגשני – יש לי כמה גיגים חדשים בשבילך לבדוק. מזל טוב, V.",
    "base|onscreens/onscreens_final.json|45239": "כאשר רייצ' בארטמוס שחרר את וירוסי ה-R.A.B.I.D.S. שלו, הרשת העולמית נותרה בהריסות. בימינו, נותרו רק כמה מקטעים מבודדים של הרשת. כדי להגיע לאחד כזה, לרוב תצטרך למצוא את נקודת הגישה הקרובה ביותר.",
    "base|onscreens/onscreens_final.json|3947": " כובע מומלץ אם אתה סובל מ הפרעה בקבלת תשומת לב",
    "base|onscreens/onscreens_final.json|3950": " קצת מזוקק, אבל לפחות תיודע את רמות האבק באוויר"
}

with open('current_batch.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

for k, v in d.items():
    if k in fixes:
        v['fixed_male'] = fixes[k]
    else:
        v['fixed_male'] = v['he_female']

with open('current_batch.json', 'w', encoding='utf-8') as f:
    json.dump(d, f, ensure_ascii=False, indent=1)

print("Batch applied.")
