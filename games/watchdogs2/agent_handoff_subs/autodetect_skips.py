import json
import re
import os

# Load skip.json
skip_file = "skip.json"
if os.path.exists(skip_file):
    skip_set = set(json.load(open(skip_file, encoding="utf-8")))
else:
    skip_set = set()

# Load current_batch.json
current_batch = json.load(open("current_batch.json", encoding="utf-8"))

detected = {}

# Patterns
PHONE = re.compile(r'^\d{3}-\d{4}$')
CODE = re.compile(
    r'(^[a-zA-Z_][a-zA-Z0-9_\.]*\s*=\s*(true|false);?$)'
    r'|(^read\.csv\(.*$)'
    r'|(^predict\(.*$)'
    r'|(^class\s+[a-zA-Z_].*$)'
    r'|(^disp\(.*$)'
    r'|(\.\.\.\{trends%)'
    r'|(^params\..*$)'
)
PLACEHOLDER = re.compile(r'^\[#img_[a-zA-Z0-9_-]+\]$')
SPANISH = re.compile(r'^(Que tal\?|Como estas\?)$', re.I)

# Handles / specific known ones
HANDLES = {
    "eKart08", "trooobadooor", "pwns U", "patzer", "TinkerTailor", 
    "turDUCKen", "xxxxxxxxxx", "doge", "retch"
}

for k, val in current_batch.items():
    val_strip = val.strip()
    reason = None
    if PHONE.match(val_strip):
        reason = "phone_number"
    elif CODE.search(val_strip):
        reason = "code_snippet"
    elif PLACEHOLDER.match(val_strip):
        reason = "image_placeholder"
    elif SPANISH.match(val_strip):
        reason = "spanish_dialogue"
    elif val_strip in HANDLES:
        reason = "handle"
    
    if reason:
        detected[k] = (val, reason)

# Print detected and add to skip_set
print(f"Detected {len(detected)} keys to skip:")
for k, (val, r) in sorted(detected.items(), key=lambda x: int(x[0]))[:30]:
    print(f"  {k}: {repr(val)} ({r})")

if len(detected) > 30:
    print(f"  ... and {len(detected) - 30} more.")

# Write updated skip.json
new_skips = sorted(list(skip_set.union(detected.keys())), key=lambda x: int(x))
json.dump(new_skips, open(skip_file, "w", encoding="utf-8"), ensure_ascii=False, indent=4)
print(f"Total skips in skip.json: {len(new_skips)} (added {len(detected)} keys)")
