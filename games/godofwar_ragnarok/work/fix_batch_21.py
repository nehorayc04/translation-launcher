# -*- coding: utf-8 -*-
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))

# Fix trans_21_part_2.json - keys 102754, 102756
fn2 = os.path.join(HERE, "trans_21_part_2.json")
data2 = json.load(open(fn2, encoding="utf-8"))
# 102754: needs \\n - "saved him from a \\nterrible fate"
data2["102754"] = "[[S:::6159-10132:10506]]\nהצלת אותו מגורל \\nנורא\u2014זה לא כלום."
# 102756: needs \\n - "Father's not \\ngonna go along"
data2["102756"] = "[[S:ATREUS:vo_int9_lvl_rbr03_s005_030_son:80-4044:10507]]\nאולי... אבל אבא לא \\nיזרום עם זה לנצח."
with open(fn2, "w", encoding="utf-8") as f:
    json.dump(data2, f, ensure_ascii=False, indent=2)
print("Fixed 102754, 102756 in trans_21_part_2.json")

# Fix trans_21_part_3.json - keys 102764, 102801, 102853
fn3 = os.path.join(HERE, "trans_21_part_3.json")
data3 = json.load(open(fn3, encoding="utf-8"))
# 102764: needs \\n - "certain the \\nGiants"
data3["102764"] = "[[S:::11416-14330:7011]]\nאתה בטוח שהענקים \\nלא היו ממליצים על מלחמה?"
# 102801: needs \\n - "whenever your \\n[i]father's[/i]"
data3["102801"] = "[[S:::2720-5460:10526]]\nובכן, מתי ש\\n[i]אבא[/i] שלך מוכן, אני צריך לומר."
# 102853: needs \\n - "polished \\noff all"
data3["102853"] = "[[S:::83599-86306:21914]]\nעכשיו, אחרי שחיסלתי \\nאת כל השרף הזה עבורך\u2014"
with open(fn3, "w", encoding="utf-8") as f:
    json.dump(data3, f, ensure_ascii=False, indent=2)
print("Fixed 102764, 102801, 102853 in trans_21_part_3.json")
