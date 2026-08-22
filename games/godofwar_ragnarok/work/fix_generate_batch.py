# -*- coding: utf-8 -*-
import json
import sys
import re

# Configure UTF-8 stdout
sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, 'games/godofwar_ragnarok/work')
import generate_batch

english_path = 'games/godofwar_ragnarok/work/english.json'
english_data = json.load(open(english_path, encoding='utf-8'))

batch = generate_batch.batch

# Fix key 9771 and 9772 (style spacing)
if "9771" in batch:
    batch["9771"] = batch["9771"].replace("[style=Highlight]", "[style= Highlight]")
if "9772" in batch:
    batch["9772"] = batch["9772"].replace("[style=Highlight]", "[style= Highlight]")

# Fix key 10025 (escaped newline -> real newline)
if "10025" in batch:
    # In generate_batch.py it was "כוונן את עוצמת תנועת המצלמה\\nהסביבתית..."
    # English: "Adjust the strength of ambient camera\nmotion. This emulates..."
    # Let's replace the literal \\n with a real newline \n
    batch["10025"] = batch["10025"].replace("\\n", "\n")

# For the other keys (mostly paragraph break \\n\\p vs \\n\\n):
# Let's align the paragraph breaks to match English exactly.
for k in batch:
    if k in english_data:
        eng_val = english_data[k]
        heb_val = batch[k]
        
        # If English has \\n\\p and Hebrew has \\n\\n, let's replace it
        if "\\n\\p" in eng_val and "\\n\\n" in heb_val:
            # Replace \\n\\n with \\n\\p in Hebrew to match paragraph break structure
            # Let's see if we can do it count-based or simple replace
            # Let's check the counts of both
            eng_np_count = eng_val.count("\\n\\p")
            heb_nn_count = heb_val.count("\\n\\n")
            if eng_np_count == heb_nn_count:
                batch[k] = heb_val.replace("\\n\\n", "\\n\\p")
                print(f"Fixed paragraph breaks in key {k}")
            else:
                # If counts differ, let's look at the occurrences and replace them
                # Let's print a message to handle it
                print(f"Manual check needed for key {k}: English \\n\\p count = {eng_np_count}, Hebrew \\n\\n count = {heb_nn_count}")

# Check mismatches again after automatic fixing
def get_tags(t):
    return sorted(re.findall(r'\[.*?\]|%.|\\n|\\r|\\p', t))

mismatches = [k for k, v in batch.items() if k in english_data and get_tags(english_data[k]) != get_tags(v)]
print(f"Remaining mismatches: {mismatches}")

# Save the corrected generate_batch.py
with open('games/godofwar_ragnarok/work/generate_batch.py', 'w', encoding='utf-8') as f:
    f.write("# -*- coding: utf-8 -*-\nimport json\n\nbatch = {\n")
    for k, v in batch.items():
        val_str = json.dumps(v, ensure_ascii=False)
        f.write(f'  "{k}": {val_str},\n')
    f.write("}\n")

print("Saved corrected generate_batch.py")
