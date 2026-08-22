import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _tokens import tokens, strip_tokens

# Load current batch
if not os.path.exists("current_batch.json"):
    print("current_batch.json not found")
    sys.exit(1)

batch = json.load(open("current_batch.json", encoding="utf-8"))

# Load skip.json
skip_path = "skip.json"
if os.path.exists(skip_path):
    try:
        skips = set(json.load(open(skip_path, encoding="utf-8")))
    except Exception:
        skips = set()
else:
    skips = set()

# Helper to check if string should be skipped
def should_skip(guid, val):
    val_strip = val.strip()
    if not val_strip:
        return True
    if val_strip.startswith("!"):
        return True
    
    # Check if all caps and underscores
    # Allow some numbers but mostly caps/underscores, e.g. MOVIE_CAPTURE_1
    if re.match(r"^[A-Z0-9_]+$", val_strip):
        return True
        
    # Check if it is a single internal token or placeholder pattern
    if re.match(r"^(Human\d+|Profile_.*|TEST_.*|small_feedback_ship\d+|[a-z0-9_]+\d+)$", val_strip):
        return True

    # Check if only tokens (printf, tags, data-binds) and no other text
    stripped = strip_tokens(val).strip()
    if not stripped:
        return True
        
    # If it is only punctuation or symbols left
    if re.match(r"^[ \t\r\n.,;:!?()\"'\-\[\]<>/*#%+=$&@]*$", stripped):
        return True
        
    return False

to_translate = {}
skipped_in_batch = []

for guid, val in batch.items():
    if should_skip(guid, val):
        skips.add(guid)
        skipped_in_batch.append(guid)
    else:
        to_translate[guid] = val

# Save updated skips
json.dump(sorted(list(skips), key=lambda x: int(x)), open(skip_path, "w", encoding="utf-8"), ensure_ascii=False, indent=0)

# Save remaining to translate
json.dump(to_translate, open("to_translate_batch.json", "w", encoding="utf-8"), ensure_ascii=False, indent=4)

print(f"Total in batch: {len(batch)}")
print(f"Auto-skipped: {len(skipped_in_batch)}")
print(f"Remaining to translate: {len(to_translate)}")
