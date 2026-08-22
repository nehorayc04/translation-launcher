import json
with open('current_batch.json', 'r', encoding='utf-8') as f:
    d = json.load(f)
with open('extracted.txt', 'w', encoding='utf-8') as out:
    for k, v in d.items():
        out.write(f"KEY_START:{k}\n")
        out.write(v['he_female'] + "\n")
        out.write("KEY_END\n")
