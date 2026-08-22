# -*- coding: utf-8 -*-
import json

# Patch trans_7_part_1.json
with open("trans_7_part_1.json", "r", encoding="utf-8") as f:
    part1 = json.load(f)

part1["62222"] = "אני חושש שהמסירות דועכת בקרב האחרים. אם ברצוננו לגרש את האסיר מואנאהיים, ישנם דברים שעלינו לעשות ללא היסוס.\\n\\nקורבנות חייבים להיעשות, ואם אני המתרגל היחיד עם מספיק אומץ להקריב אותם, אז שיהיה כך. \\n\\nבחיים אני זועק.\\n\\nבמוות אני שר.\\n\\nבדם אני בוטח.\\n\\nאני הנקמה של הארצות הללו."
part1["62228"] = "השולחן מלא.\\n\\pמעדנים שמקורם הן מהואניר והן מהאסיר הוכנו כדי לסמל את איחוד העמים. פירות עסיסיים לעורר את התיאבון, מוגשים לצד עורן המומלח והפריך של תרנגולות צעירות. דלועים, צלויים ואז מצופים בדבש, ולחמים שנאפו בבורות הלבה של אלדג'יה יוגשו כמנה השנייה. מנחה של סהרימניר תפסה את מרכז השולחן, למרות שרבים מהואניר כנראה יסרבו לטעום ממנה.\\n\\pנתחי בשר רכים לקטנטנים נערמו לגובה; הם לא יישארו רעבים הלילה. אחרון חביב, חביות של תמד גולגלו במספרים גדולים כדי לתת מענה לצמא שחגיגות כאלו מביאות על אורחיהן. הלילה אנו סועדים כאילו ראגנארוק יגיע אלינו בבוקר."
part1["62232"] = "ברכה על איחודם של פריה ואודין ביום זה.\\n\\nשגשוג לתושבי ואנאהיים ואסגארד.\\n\\nכפי שהשמש זורחת והירח מאיר.\\n\\nכך ייוותרו הממלכות יציבות בשלום."
part1["62242"] = "\"קאדלין, מוחצת האומללים, חיסלה כאן קן של עשרים.\" \\n \\nאגדה או התרברבות אני תוהה? הלוואי ש'קאדלין' זו הייתה בסביבה כדי להאיר את עינינו באסטרטגיות שלה."

with open("trans_7_part_1.json", "w", encoding="utf-8") as f:
    json.dump(part1, f, ensure_ascii=False, indent=2)

# Patch trans_7_part_2.json
with open("trans_7_part_2.json", "r", encoding="utf-8") as f:
    part2 = json.load(f)

part2["62333"] = " "
part2["62383"] = "זעם ספרטני — [style=Highlight]חימה[/style]: [style=Highlight]עלויות תקיפה ויציאה מזעם[/style] הן [style=Highlight]מופחתות[/style] בהרבה, אך [style=Highlight]הריפוי[/style] בזמן חימה הוא גם [style=Highlight]מופחת[/style]."

with open("trans_7_part_2.json", "w", encoding="utf-8") as f:
    json.dump(part2, f, ensure_ascii=False, indent=2)

# Patch trans_7_part_3.json
with open("trans_7_part_3.json", "r", encoding="utf-8") as f:
    part3 = json.load(f)

part3["63134"] = "דחף קלות את [MovementButton] כדי ללכת בנחת או דחף את [MovementButton] עד הסוף כדי לרוץ."

with open("trans_7_part_3.json", "w", encoding="utf-8") as f:
    json.dump(part3, f, ensure_ascii=False, indent=2)

print("Patching successful!")
