import json
d = json.load(open('current_batch.json', encoding='utf-8'))
lines = []
for k, v in d.items():
    lines.append(f"--- {k} ---")
    lines.append(v['he_female'])
    lines.append("")
open('review.txt', 'w', encoding='utf-8').write('\n'.join(lines))
