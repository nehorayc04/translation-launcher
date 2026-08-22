with open("untranslated_all_parts.txt", "r", encoding="utf-8") as f:
    lines = f.readlines()
for idx, line in enumerate(lines):
    if "688537" in line:
        print(f"Line {idx+1}: {line}")
