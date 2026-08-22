import json
import os
import re

handoff = r"c:\Users\Nehoray_Cohen\Projects\Game translator\games\anno1800\agent_handoff"

to_translate_path = os.path.join(handoff, "to_translate_batch.json")
if not os.path.exists(to_translate_path):
    print("to_translate_batch.json not found")
    sys.exit(1)

with open(to_translate_path, "r", encoding="utf-8") as f:
    batch = json.load(f)

trans = {}
skips = []

for guid, val in batch.items():
    # Detect skips based on patterns
    val_lower = val.lower()
    if ("moviecapture" in val_lower or 
        "test" in val_lower or 
        "sample_" in val_lower or 
        "dummy" in val_lower or 
        "context pool" in val_lower or 
        "objective pool" in val_lower or
        "asset pool" in val_lower or
        re.match(r"^[A-Z0-9_]+$", val) or
        val.startswith("QC") or 
        val.startswith("CQ_") or
        re.match(r"^(Human\d+|Profile_.*|TEST_.*|small_feedback_ship\d+|[a-z0-9_]+\d+)$", val)):
        skips.append(guid)
    else:
        trans[guid] = val

template_content = f"""import json
import os

handoff = r"c:\\Users\\Nehoray_Cohen\\Projects\\Game translator\\games\\anno1800\\agent_handoff"

trans = {{
"""

for guid, val in trans.items():
    # Escape quotes
    escaped_val = val.replace('\\', '\\\\').replace('"', '\\"')
    template_content += f'    "{guid}": "{escaped_val}",\n'

template_content += """}

skips_to_add = [
"""

for guid in skips:
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
"""

with open(os.path.join(handoff, "translate_current_batch_11.py"), "w", encoding="utf-8") as f:
    f.write(template_content)

print(f"Generated template for Batch 11. trans: {len(trans)}, skips: {len(skips)}")
