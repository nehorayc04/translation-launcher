import json
import re

# Load batch_part1.json
part1_source = json.load(open("batch_part1.json", encoding="utf-8"))

# Load write_part1_combined.py lines
with open("write_part1_combined.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

untranslated = []
for line in lines:
    m = re.match(r'^\s*"(\d+)":\s*"",\s*#\s*(.*)$', line)
    if m:
        key = m.group(1)
        eng = m.group(2)
        untranslated.append((key, eng))

print(f"Total untranslated in Part 1: {len(untranslated)}")
# Output them in chunks or list them
for k, e in untranslated[:30]:
    print(f'"{k}": "", # {e}')
