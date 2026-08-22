import json

with open('current_batch.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

with open('en_texts.txt', 'w', encoding='utf-8') as f:
    for k, v in d.items():
        f.write(f"{k}:: {v['en']}\n")
