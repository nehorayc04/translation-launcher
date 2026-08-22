import json

with open("untranslated_all_parts.txt", "w", encoding="utf-8") as out:
    for i in range(1, 5):
        b = json.load(open(f"batch_part{i}.json", encoding="utf-8"))
        # We also want to know which are already in skip.json or hebrew.json
        # (Though we ran loop_split, so batch_part files contain only remaining untranslated).
        out.write(f"=== PART {i} ===\n")
        for k in sorted(b.keys(), key=lambda x: int(x)):
            eng = b[k]
            out.write(f"{k}: {repr(eng)}\n")
print("Done writing to untranslated_all_parts.txt")
