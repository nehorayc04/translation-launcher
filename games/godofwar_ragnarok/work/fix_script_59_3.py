# -*- coding: utf-8 -*-
import re
import os

HERE = os.path.dirname(os.path.abspath(__file__))
filepath = os.path.join(HERE, "write_trans_59_3.py")

with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# We want to replace the block of keys from "126078" to "126092"
replacement = """  "126078": "[[S:FREYA:vo_int9_gbs_fre_s941_FutureHel_Resumes_010:0-2550:60335]]\\nמימיר—עכשיו כשיש לנו רגע,",
  "126079": "[[S:::2550-5863:60335]]\\nאני יכולה לשאול על המשימה שלך \\\\nלהלהיים עם הילדיסוויני?",
  "126080": "[[S:KRATOS:vo_int9_gbs_kra_s941_FutureHel_Resumes_020:100-5050:60337]]\\nמימיר—מה בדיוק הבטחת \\\\nלציפור הגדולה בהלהיים?",
  "126081": "[[S:MIMIR:vo_int9_gbs_mim_s941_FutureHel_Resumes_030:50-2670:60339]]\\nאוה, שום דבר מזעזע [i]מדי...[/i]",
  "126082": "[[S:MIMIR:vo_int9_gbs_mim_s941_FutureHel_Resumes_040:60-2510:60341]]\\nכמו שאמרתי קודם לכן, \\\\nלגבי הרסוולגר…",
  "126083": "[[S:FREYA:vo_int9_gbs_fre_s941_FutureHel_Resumes_050:60-2412:60343]]\\nהיית רציני קודם לכן, מימיר?",
  "126084": "[[S:::2412-4961:60343]]\\nהרסוולגר באמת רוצה לפרוש?",
  "126085": "[[S:FREYA:vo_int9_gbs_fre_s941_FutureHel_Resumes_060:0-2716:60345]]\\nאז תן לי לראות אם הבנתי...",
  "126086": "[[S:::2716-7716:60345]]\\nאנחנו אמורים למצוא מישהו שיחליף \\\\nאת הרסוולגר ויהפוך ל-\\"הל\\"...?",
  "126087": "[[S:FREYA:vo_int9_gbs_fre_s941_FutureHel_Resumes_070:60-2918:60347]]\\nאז איך אנחנו אמורים למצוא \\\\nמישהו שיהיה מוכן לתפוס את",
  "126088": "[[S:::2918-7164:60347]]\\nמקומה של הרסוולגר בהלהיים? \\\\nזה נראה כמו עבודה כפויית טובה.",
  "126089": "[[S:MIMIR:vo_int9_gbs_mim_s941_FutureHel_Resumes_080:0-1142:60348]]\\nאכן...",
  "126090": "[[S:FREYA:vo_int9_gbs_fre_s941_FutureHel_Resumes_090:0-3933:60350]]\\nאז כמה מודאגים אנחנו צריכים להיות, מימיר?",
  "126091": "[[S:::3933-6068:60350]]\\nלגבי המצב של הרסוולגר...?",
  "126092": "[[S:MIMIR:vo_int9_gbs_mim_s941_FutureHel_Resumes_100:70-4859:60351]]\\nאוה, יהיו צרות לכולנו אם \\\\nהתפקיד יאויש על ידי מישהו שאינו מתאים…\","""

# Find the start line for "126078" and end line for "126092"
# Let's split by line and build new contents
lines = content.splitlines()
start_idx = -1
end_idx = -1

for idx, line in enumerate(lines):
    if '"126078":' in line:
        start_idx = idx
    if '"126092":' in line:
        end_idx = idx

if start_idx != -1 and end_idx != -1:
    # Find the end of the "126092" value (which might span multiple lines)
    # The next key starts with "126093"
    next_idx = -1
    for idx in range(end_idx + 1, len(lines)):
        if '"126093":' in lines[idx]:
            next_idx = idx
            break
    if next_idx != -1:
        new_lines = lines[:start_idx] + [replacement] + lines[next_idx:]
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(new_lines) + "\n")
        print("SUCCESS: write_trans_59_3.py was patched successfully!")
    else:
        print("ERROR: key 126093 not found")
else:
    print(f"ERROR: keys not found: start_idx={start_idx}, end_idx={end_idx}")
