import json

# Load batch_part1.json
part1_source = json.load(open("batch_part1.json", encoding="utf-8"))

# Load write_part1.py translations
# We can extract them by executing the file or importing if it's importable, or parsing.
# Since write_part1.py is python, let's just import it or read it.
import write_part1
translated = write_part1.part1

missing = {k: part1_source[k] for k in part1_source if k not in translated}
print(f"Total keys in part 1 source: {len(part1_source)}")
print(f"Total keys in write_part1.py: {len(translated)}")
print(f"Missing keys: {len(missing)}")
if missing:
    first_missing = list(missing.keys())[0]
    print(f"First missing key: {first_missing} -> {missing[first_missing]}")
