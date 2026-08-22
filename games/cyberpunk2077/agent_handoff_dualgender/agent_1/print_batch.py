import json
d = json.load(open('current_batch.json', encoding='utf-8'))
with open('batch_text.txt', 'w', encoding='utf-8') as f:
    for i, (k, v) in enumerate(d.items()):
        f.write(f"[{i}] {k}\n{v['he_female']}\n---\n")
