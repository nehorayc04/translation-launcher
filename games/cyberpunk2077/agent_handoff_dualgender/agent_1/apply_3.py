import json
import re

with open('current_batch.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

for k, v in d.items():
    fm = v['fixed_male']
    # remove niqqud using the same regex
    fm = re.sub(r"[֑-ׇ]", "", fm)
    # also fix the verb "נראית" to "נראה" (V speaking)
    fm = fm.replace("נראית", "נראה")
    v['fixed_male'] = fm

with open('current_batch.json', 'w', encoding='utf-8') as f:
    json.dump(d, f, ensure_ascii=False, indent=1)
